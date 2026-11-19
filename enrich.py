#!/usr/bin/env python3
"""可选的 AI 文案增强：调用任意 OpenAI 兼容接口。

默认关闭；只有显式加 --enable 且设置 LLM_API_KEY / LLM_MODEL 才会发起请求。
生成 data/enriched_latest.json，供 python monitor.py report 使用。

示例：
    python enrich.py --dry-run                 # 只打印 prompt 与预估费用
    python enrich.py --enable                  # 调用接口并写入增强数据
    python enrich.py --enable --max-cost 0.05  # 费用上限（需设置单价）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from lib.config import load_config, root_path

REQUIRED_FIELDS = ("features", "audience", "value", "difficulty", "notes")

SYSTEM_PROMPT = (
    "你是一名严谨的中文技术编辑。你的任务是从候选 GitHub 项目中，"
    "挑出真正对普通人（非技术用户）有用的项目，并用具体、不套话的中文描述它们。"
    "不要编造功能；只依据给出的名称、描述、topics、星标、许可证。"
)


def build_prompt(candidates: list[dict], max_candidates: int = 10) -> str:
    compact = []
    for c in candidates[:max_candidates]:
        compact.append({
            "full_name": c.get("full_name", ""),
            "description": c.get("description", ""),
            "topics": (c.get("topics") or [])[:6],
            "stars": c.get("stars", 0),
            "language": c.get("language", ""),
            "license": c.get("license", ""),
            "difficulty_hint": c.get("difficulty", ""),
        })
    return (
        "下面是今日候选项目（JSON）。请逐个判断是否真的对普通人有价值，"
        "剔除纯开发者基础设施、描述含糊，或需要强技术背景且收益不明显的项目。\n\n"
        + json.dumps(compact, ensure_ascii=False, indent=2)
        + "\n\n只返回一个 JSON 对象，格式如下（不要 Markdown 代码块）：\n"
        + '{"items":[{"full_name":"owner/repo","features":"1-2 句具体功能",'
          '"audience":"具体到场景的适合人群","value":"对普通人省了什么/改善了什么",'
          '"difficulty":"低|中|高","notes":"许可证、维护状态、隐私或付费等真实提醒"}]}\n'
        + "items 的顺序就是推荐优先级。full_name 必须与候选完全一致。"
    )


def estimate_tokens(text: str) -> int:
    """粗估 token：约 4 个字符 = 1 token，只用于费用上限判断。"""
    return max(1, len(text or "") // 4)


def estimate_cost(prompt: str, max_output_tokens: int,
                  price_in_per_1m: float, price_out_per_1m: float) -> float:
    return (estimate_tokens(prompt) / 1_000_000 * price_in_per_1m
            + max_output_tokens / 1_000_000 * price_out_per_1m)


def parse_items(content: str) -> list[dict]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("模型返回里没有找到 JSON 对象")
    data = json.loads(text[start:end + 1])
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("模型返回缺少 items 列表")

    cleaned: list[dict] = []
    for x in items:
        if not isinstance(x, dict):
            continue
        fn = str(x.get("full_name") or "").strip()
        if not fn:
            continue
        item = {"full_name": fn}
        for key in REQUIRED_FIELDS:
            item[key] = str(x.get(key) or "").strip()
        if item["difficulty"] not in ("低", "中", "高"):
            item["difficulty"] = "中"
        if all(item[key] for key in REQUIRED_FIELDS):
            cleaned.append(item)
    return cleaned


def call_llm(base_url: str, api_key: str, model: str, prompt: str,
             max_tokens: int, timeout: int) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def main() -> int:
    ap = argparse.ArgumentParser(description="可选的 AI 文案增强")
    ap.add_argument("--enable", action="store_true", help="显式启用（默认关闭）")
    ap.add_argument("--input", default=None, help="候选 JSON（默认读 config 里的 candidates_file）")
    ap.add_argument("--output", default=None, help="输出 JSON（默认写 config 里的 enriched_file）")
    ap.add_argument("--max-candidates", type=int, default=10)
    ap.add_argument("--max-output-tokens", type=int, default=2000)
    ap.add_argument("--max-cost", type=float, default=0.0,
                    help="美元费用上限，0 = 不限制（需设置 LLM_PRICE_*）")
    ap.add_argument("--dry-run", action="store_true", help="只打印 prompt 与预估费用，不发请求")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    if not args.enable and not args.dry_run:
        print("AI 增强默认关闭。加 --enable 才会调用接口；不启用时报告使用规则兜底文案。")
        return 0

    cfg = load_config()
    input_path = Path(args.input) if args.input else root_path(cfg["output"]["candidates_file"])
    output_path = Path(args.output) if args.output else root_path(cfg["output"]["enriched_file"])
    if not input_path.exists():
        print(f"[错误] 找不到候选文件 {input_path}，请先运行 python monitor.py collect", file=sys.stderr)
        return 1

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    candidates = payload.get("candidates") or []
    if not candidates:
        print("[跳过] 候选为空，无需 AI 增强。")
        return 0

    prompt = build_prompt(candidates, args.max_candidates)
    price_in = float(os.environ.get("LLM_PRICE_INPUT_PER_1M", "0") or 0)
    price_out = float(os.environ.get("LLM_PRICE_OUTPUT_PER_1M", "0") or 0)
    cost = estimate_cost(prompt, args.max_output_tokens, price_in, price_out)
    print(f"[估算] 输入约 {estimate_tokens(prompt)} tokens，预估费用 ${cost:.4f}")

    if args.dry_run:
        print("--- prompt ---")
        print(prompt)
        return 0

    if not args.enable:
        print("AI 增强默认关闭。加 --enable 才会调用接口。")
        return 0

    api_key = os.environ.get("LLM_API_KEY", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    if not api_key or not model:
        print("[错误] 需要设置 LLM_API_KEY 和 LLM_MODEL。", file=sys.stderr)
        return 2

    if args.max_cost > 0:
        if price_in == 0 and price_out == 0:
            print("[错误] 设置了 --max-cost 但未设置 LLM_PRICE_INPUT_PER_1M / "
                  "LLM_PRICE_OUTPUT_PER_1M，无法估算费用。", file=sys.stderr)
            return 2
        if cost > args.max_cost:
            print(f"[中止] 预估费用 ${cost:.4f} 超过上限 ${args.max_cost:.4f}。",
                  file=sys.stderr)
            return 1

    try:
        content = call_llm(base_url, api_key, model, prompt,
                           args.max_output_tokens, args.timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(f"[HTTP {e.code}] {body}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[请求失败] {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    try:
        items = parse_items(content)
    except Exception as e:
        print(f"[解析失败] {e}", file=sys.stderr)
        return 1

    names = {c["full_name"] for c in candidates}
    items = [x for x in items if x["full_name"] in names]
    if not items:
        print("[失败] 模型没有返回可用项目（full_name 均不在候选内）。", file=sys.stderr)
        return 1

    output = {"date": payload.get("date"), "items": items}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[完成] 已写入 {output_path}（{len(items)} 项）")
    print("下一步：python monitor.py validate && python monitor.py report")
    return 0


if __name__ == "__main__":
    sys.exit(main())