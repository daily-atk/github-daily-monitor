# Reddit launch draft

**Suggested subreddits** (pick one first, read each subreddit's self-promotion rules):

- r/github
- r/selfhosted
- r/Python
- r/opensource

**Title**

I built a zero-dependency Python tool that turns GitHub into a daily digest for non-technical people

---

**Body**

Hi everyone,

I kept running into the same problem: GitHub Trending and most "awesome" lists are written for developers. My family and friends don't care about SDKs or self-hosted infrastructure — they want to know what they could actually use today.

So I built **GitHub Daily Monitor**, a small Python tool that produces a daily Chinese digest for ordinary people.

**What it does**

- Searches GitHub for recently created and recently updated projects across five domains: learning, daily life, productivity, health, and personal finance.
- Filters out developer infrastructure, tutorial collections, missing descriptions, and suspicious fork ratios.
- Uses local phrase validation for precision: the query `habit tracker` rejects `habitat`.
- Applies a 30-day recommendation cooldown and a 7-day "seen but not selected" cooldown.
- Caps each domain at 3 items so one category cannot dominate.
- Generates Markdown and a self-contained HTML report with platform, last-update date, and license.

**What makes it different**

It is a **tool**, not a hand-curated magazine. You can run it with your own keywords, schedule it, and publish the result for your family, friends, or community.

**Technical notes**

- Python 3.10+, standard library only — no `pip install`.
- Optional AI enrichment via any OpenAI-compatible endpoint. It is off by default and has `--dry-run` plus a cost cap.
- Optional GitHub Actions workflow that publishes the report and an archive index to GitHub Pages.
- 36 unit tests, no network calls; CI runs on Python 3.10 and 3.13.
- MIT licensed, not affiliated with GitHub.

**Quick start**

```bash
git clone https://github.com/daily-atk/github-daily-monitor.git
cd github-daily-monitor
./run.sh          # macOS/Linux
# or double-click 运行日报.bat on Windows
```

**Limitations**

- The filtering is heuristic, so quality varies.
- "Useful for ordinary people" is subjective; feedback is welcome.
- It does not guarantee 10 items per day; it prefers fewer, better items.
- It only aggregates public information and never installs anything.

Repo: https://github.com/daily-atk/github-daily-monitor
Demo: https://daily-atk.github.io/github-daily-monitor/

I'd love feedback on two things: which projects should be filtered out, and whether the "ordinary people" framing is clear. I'm the author and this is open source — happy to answer questions.

---

**Posting notes**

- Read the subreddit rules before posting; some communities restrict self-promotion to specific days or require participation history.
- Use the appropriate flair (e.g., "Show and Tell", "Project", or "Open Source").
- Do not post the same text to several subreddits on the same day; tailor the opening paragraph.
- Disclose that you are the author (already in the draft).
- Do not ask for stars or upvotes. Ask for specific feedback instead.
- If a moderator removes the post, ask which rule was violated rather than reposting.