# Claude Code Usage Dashboard

A Python script that generates a shareable HTML dashboard from your local [Claude Code](https://docs.anthropic.com/en/docs/claude-code) usage stats.

![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue)
![No Dependencies](https://img.shields.io/badge/dependencies-none-green)

## What it shows

- **Prompts** — how many times you've talked to Claude
- **Actions Taken** — file reads, edits, bash commands, searches Claude performed
- **Sessions** & **Longest Session** duration
- **Cache Hit Rate** — how efficiently prompt caching is working
- **Longest Streak** of consecutive active days
- **Peak Hour** & **Busiest Day**
- **Daily Prompts & Actions** chart
- **Output Tokens by Model** over time
- **Model Usage** breakdown (doughnut chart)
- **Sessions by Hour of Day** (color-coded: work hours vs night owl)
- **Token Breakdown** table by model

## Quick Start

```bash
python3 claude-usage-dashboard.py
```

That's it. No dependencies needed — just Python 3.8+ and a browser.

It reads `~/.claude/stats-cache.json` and `~/.claude/history.jsonl` (generated automatically by Claude Code) and opens an HTML report in your browser.

## Options

```
python3 claude-usage-dashboard.py --name "Your Name"    # Custom name in header
python3 claude-usage-dashboard.py -o report.html         # Custom output path
python3 claude-usage-dashboard.py --no-open              # Don't auto-open browser
python3 claude-usage-dashboard.py --claude-dir /path     # Custom .claude directory
```

## Sharing with your team

Everyone runs it on their own machine and shares the generated HTML file. The output is a single self-contained HTML file (charts use Chart.js from CDN).

## Data Source

All data comes from local files that Claude Code writes automatically:

| File | What it contains |
|------|-----------------|
| `~/.claude/stats-cache.json` | Aggregated usage stats (sessions, tokens, tool calls by day/model) |
| `~/.claude/history.jsonl` | Every prompt you've typed with timestamps |

No data is sent anywhere. The script is fully offline (except Chart.js loaded from CDN in the HTML output).
