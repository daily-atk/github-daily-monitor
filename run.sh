#!/usr/bin/env bash
# 每日 GitHub 日报 · macOS / Linux 一键运行
set -euo pipefail
cd "$(dirname "$0")"

version_ok() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
    >/dev/null 2>&1
}

find_python() {
  if [ -n "${PYTHON:-}" ] && version_ok "$PYTHON"; then
    echo "$PYTHON"
    return 0
  fi
  if version_ok python3; then
    echo python3
    return 0
  fi
  if version_ok python; then
    echo python
    return 0
  fi

  # Windows Git Bash / MSYS：绕过微软商店的占位程序，找真实安装
  local candidates=()
  if command -v cygpath >/dev/null 2>&1 && [ -n "${LOCALAPPDATA:-}" ]; then
    candidates+=("$(cygpath -u "$LOCALAPPDATA")"/Programs/Python/Python3*/python.exe)
  fi
  candidates+=(/c/Program\ Files/Python3*/python.exe)
  candidates+=("$HOME"/AppData/Local/Programs/Python/Python3*/python.exe)
  for candidate in "${candidates[@]}"; do
    if [ -e "$candidate" ] && version_ok "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

PY="$(find_python)" || {
  echo "[失败] 没有找到 Python 3.10+，请先安装：https://www.python.org/downloads/"
  exit 1
}

echo "============================================================"
echo "  每日 GitHub 日报"
echo "  正在采集并生成报告，通常需要 1-3 分钟，请不要关闭窗口"
echo "============================================================"
echo

"$PY" monitor.py run "$@"

LATEST=$(ls -1t reports/github-daily-*.html 2>/dev/null | head -n 1 || true)
if [ -n "$LATEST" ]; then
  echo
  echo "[完成] 最新报告：$LATEST"
  case "$(uname -s)" in
    Darwin) open "$LATEST" 2>/dev/null || true ;;
    Linux) command -v xdg-open >/dev/null 2>&1 && xdg-open "$LATEST" >/dev/null 2>&1 || true ;;
  esac
else
  echo "[提示] reports/ 里还没有 HTML 报告。"
fi