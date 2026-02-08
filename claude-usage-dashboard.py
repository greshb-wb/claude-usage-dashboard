#!/usr/bin/env python3
"""
Claude Code Usage Dashboard
Generates a shareable HTML report from your local Claude Code stats.

Usage:
    python3 claude-usage-dashboard.py
    python3 claude-usage-dashboard.py --name "Gresh"
    python3 claude-usage-dashboard.py -o ~/Desktop/my-report.html
"""

import argparse
import html
import json
import os
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

# ── Anthropic pricing (per million tokens) ──────────────────────────
# Update these if pricing changes
PRICING = {
    "claude-opus-4-6": {
        "label": "Opus 4.6",
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.875,
        "cache_write": 18.75,
    },
    "claude-opus-4-5-20251101": {
        "label": "Opus 4.5",
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.875,
        "cache_write": 18.75,
    },
    "claude-sonnet-4-5-20250929": {
        "label": "Sonnet 4.5",
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
}

DEFAULT_PRICING = {
    "label": "Unknown Model",
    "input": 15.0,
    "output": 75.0,
    "cache_read": 1.875,
    "cache_write": 18.75,
}


def load_prompts_by_day(claude_dir: Path) -> dict[str, int]:
    """Parse history.jsonl and return {date_str: prompt_count}."""
    history_path = claude_dir / "history.jsonl"
    counts: dict[str, int] = {}
    if not history_path.exists():
        return counts
    with open(history_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp")
                if ts:
                    dt = datetime.fromtimestamp(ts / 1000)
                    day = dt.strftime("%Y-%m-%d")
                    counts[day] = counts.get(day, 0) + 1
            except (json.JSONDecodeError, ValueError, OSError):
                continue
    return counts


def load_stats(claude_dir: Path) -> dict:
    stats_path = claude_dir / "stats-cache.json"
    if not stats_path.exists():
        raise FileNotFoundError(
            f"No stats-cache.json found at {stats_path}.\n"
            "Make sure you've used Claude Code at least once."
        )
    with open(stats_path) as f:
        return json.load(f)


def estimate_cost(model: str, usage: dict) -> float:
    p = PRICING.get(model, DEFAULT_PRICING)
    cost = 0.0
    cost += usage.get("inputTokens", 0) / 1_000_000 * p["input"]
    cost += usage.get("outputTokens", 0) / 1_000_000 * p["output"]
    cost += usage.get("cacheReadInputTokens", 0) / 1_000_000 * p["cache_read"]
    cost += usage.get("cacheCreationInputTokens", 0) / 1_000_000 * p["cache_write"]
    return cost


def format_tokens(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def day_label(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%b %d")


def peak_hour_label(hour_counts: dict) -> str:
    if not hour_counts:
        return "N/A"
    peak = max(hour_counts, key=lambda h: hour_counts[h])
    h = int(peak)
    suffix = "AM" if h < 12 else "PM"
    display = h if h <= 12 else h - 12
    if display == 0:
        display = 12
    return f"{display} {suffix}"


def compute_streak(daily_activity: list) -> int:
    dates = sorted(
        datetime.strptime(d["date"], "%Y-%m-%d") for d in daily_activity
    )
    if not dates:
        return 0
    best = 1
    current = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def fun_title(total_tool_calls: int) -> str:
    if total_tool_calls > 2000:
        return "Claude Whisperer"
    if total_tool_calls > 500:
        return "Power User"
    if total_tool_calls > 100:
        return "Regular"
    if total_tool_calls > 10:
        return "Getting Started"
    return "Newbie"


def generate_html(stats: dict, prompts_by_day: dict[str, int], user_name: str) -> str:
    daily = stats.get("dailyActivity", [])
    daily_tokens = stats.get("dailyModelTokens", [])
    model_usage = stats.get("modelUsage", {})
    hour_counts = stats.get("hourCounts", {})
    total_sessions = stats.get("totalSessions", 0)
    total_messages = stats.get("totalMessages", 0)
    longest = stats.get("longestSession", {})
    first_date = stats.get("firstSessionDate", "")

    # ── Computed stats ──
    total_prompts = sum(prompts_by_day.values())
    total_tool_calls = sum(d.get("toolCallCount", 0) for d in daily)
    total_cost = sum(estimate_cost(m, u) for m, u in model_usage.items())
    total_input = sum(u.get("inputTokens", 0) for u in model_usage.values())
    total_output = sum(u.get("outputTokens", 0) for u in model_usage.values())
    total_cache_read = sum(
        u.get("cacheReadInputTokens", 0) for u in model_usage.values()
    )
    total_cache_write = sum(
        u.get("cacheCreationInputTokens", 0) for u in model_usage.values()
    )
    grand_total_tokens = total_input + total_output + total_cache_read + total_cache_write

    cache_savings_pct = 0
    if total_cache_read + total_input > 0:
        # Cache reads are much cheaper than full input reads
        cache_savings_pct = total_cache_read / (total_cache_read + total_input) * 100

    streak = compute_streak(daily)
    title = fun_title(total_tool_calls)
    peak_hour = peak_hour_label(hour_counts)

    busiest_day = max(daily, key=lambda d: d.get("toolCallCount", 0)) if daily else {}
    busiest_day_label = (
        day_label(busiest_day["date"]) if busiest_day else "N/A"
    )
    busiest_day_tools = busiest_day.get("toolCallCount", 0)

    first_date_fmt = ""
    if first_date:
        try:
            first_date_fmt = datetime.fromisoformat(
                first_date.replace("Z", "+00:00")
            ).strftime("%b %d, %Y")
        except Exception:
            first_date_fmt = first_date[:10]

    days_active = len(daily)
    avg_tools_per_day = round(total_tool_calls / days_active) if days_active else 0

    longest_duration_hrs = ""
    if longest.get("duration"):
        hrs = longest["duration"] / 1000 / 3600
        longest_duration_hrs = f"{hrs:.1f}h"

    # ── Chart data ──
    daily_dates_js = json.dumps([day_label(d["date"]) for d in daily])
    daily_prompts_js = json.dumps([prompts_by_day.get(d["date"], 0) for d in daily])
    daily_tools_js = json.dumps([d.get("toolCallCount", 0) for d in daily])
    daily_sessions_js = json.dumps([d.get("sessionCount", 0) for d in daily])

    # Daily tokens by model
    all_models = set()
    for entry in daily_tokens:
        all_models.update(entry.get("tokensByModel", {}).keys())
    all_models = sorted(all_models)

    model_colors = {
        "claude-opus-4-6": "#8b5cf6",
        "claude-opus-4-5-20251101": "#6366f1",
        "claude-sonnet-4-5-20250929": "#06b6d4",
    }
    fallback_colors = ["#f59e0b", "#ef4444", "#10b981", "#ec4899"]

    token_datasets_js = []
    for i, model in enumerate(all_models):
        label = PRICING.get(model, {}).get("label", model)
        color = model_colors.get(
            model, fallback_colors[i % len(fallback_colors)]
        )
        data = [
            entry.get("tokensByModel", {}).get(model, 0)
            for entry in daily_tokens
        ]
        token_datasets_js.append(
            {
                "label": label,
                "data": data,
                "backgroundColor": color,
                "borderColor": color,
                "borderWidth": 2,
                "tension": 0.3,
                "fill": True,
            }
        )
    token_dates_js = json.dumps(
        [day_label(d["date"]) for d in daily_tokens]
    )
    token_datasets_json = json.dumps(token_datasets_js)

    # Model usage pie chart
    model_pie_labels = []
    model_pie_data = []
    model_pie_colors = []
    for model, usage in model_usage.items():
        label = PRICING.get(model, {}).get("label", model)
        total = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
        color = model_colors.get(model, "#94a3b8")
        model_pie_labels.append(label)
        model_pie_data.append(total)
        model_pie_colors.append(color)
    model_pie_labels_js = json.dumps(model_pie_labels)
    model_pie_data_js = json.dumps(model_pie_data)
    model_pie_colors_js = json.dumps(model_pie_colors)

    # Hour of day bar chart
    hour_labels = [f"{h}:00" for h in range(24)]
    hour_data = [hour_counts.get(str(h), 0) for h in range(24)]
    hour_labels_js = json.dumps(hour_labels)
    hour_data_js = json.dumps(hour_data)

    # Token breakdown by model
    cost_rows = ""
    for model, usage in sorted(model_usage.items()):
        label = PRICING.get(model, {}).get("label", model)
        inp = usage.get("inputTokens", 0)
        out = usage.get("outputTokens", 0)
        cr = usage.get("cacheReadInputTokens", 0)
        cw = usage.get("cacheCreationInputTokens", 0)
        cost_rows += f"""
        <tr>
          <td>{html.escape(label)}</td>
          <td>{format_tokens(inp)}</td>
          <td>{format_tokens(out)}</td>
          <td>{format_tokens(cr)}</td>
          <td>{format_tokens(cw)}</td>
        </tr>"""

    generated_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Code Dashboard — {html.escape(user_name)}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f172a;
    --card: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --accent: #8b5cf6;
    --accent2: #06b6d4;
    --green: #10b981;
    --orange: #f59e0b;
    --pink: #ec4899;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 2rem;
    min-height: 100vh;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  header {{
    text-align: center;
    margin-bottom: 2.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border);
  }}
  header h1 {{
    font-size: 2rem;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.25rem;
  }}
  header .subtitle {{ color: var(--muted); font-size: 0.9rem; }}
  header .badge {{
    display: inline-block;
    margin-top: 0.75rem;
    padding: 0.3rem 1rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
    background: linear-gradient(135deg, var(--accent), var(--pink));
    color: white;
  }}

  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }}
  .stat-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem;
    text-align: center;
  }}
  .stat-card .value {{
    font-size: 1.8rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .stat-card .label {{
    font-size: 0.8rem;
    color: var(--muted);
    margin-top: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  .charts-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 2rem;
  }}
  .chart-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
  }}
  .chart-card.full {{ grid-column: 1 / -1; }}
  .chart-card h3 {{
    font-size: 1rem;
    margin-bottom: 1rem;
    color: var(--muted);
    font-weight: 500;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }}
  th, td {{
    padding: 0.6rem 0.8rem;
    text-align: right;
    border-bottom: 1px solid var(--border);
  }}
  th {{ color: var(--muted); font-weight: 500; text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.5px; }}
  td:first-child, th:first-child {{ text-align: left; }}
  .cost {{ color: var(--green); font-weight: 600; }}

  .footer {{
    text-align: center;
    color: var(--muted);
    font-size: 0.75rem;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
  }}

  @media (max-width: 768px) {{
    .charts-grid {{ grid-template-columns: 1fr; }}
    body {{ padding: 1rem; }}
  }}
</style>
</head>
<body>
<div class="container">

<header>
  <h1>{html.escape(user_name)}'s Claude Code Dashboard</h1>
  <div class="subtitle">Since {first_date_fmt} &middot; {days_active} active days</div>
  <div class="badge">{title}</div>
</header>

<div class="stats-grid">
  <div class="stat-card">
    <div class="value">{total_sessions}</div>
    <div class="label">Sessions</div>
  </div>
  <div class="stat-card">
    <div class="value">{longest_duration_hrs or 'N/A'}</div>
    <div class="label">Longest Session</div>
  </div>
  <div class="stat-card">
    <div class="value">{total_prompts:,}</div>
    <div class="label">Prompts</div>
  </div>
  <div class="stat-card">
    <div class="value">{total_tool_calls:,}</div>
    <div class="label">Actions Taken</div>
  </div>
  <div class="stat-card">
    <div class="value">{cache_savings_pct:.0f}%</div>
    <div class="label">Cache Hit Rate</div>
  </div>
  <div class="stat-card">
    <div class="value">{avg_tools_per_day:,}</div>
    <div class="label">Actions / Active Day</div>
  </div>
  <div class="stat-card">
    <div class="value">{streak}</div>
    <div class="label">Longest Streak (days)</div>
  </div>
  <div class="stat-card">
    <div class="value">{peak_hour}</div>
    <div class="label">Peak Hour</div>
  </div>
  <div class="stat-card">
    <div class="value">{busiest_day_label}</div>
    <div class="label">Busiest Day ({busiest_day_tools:,} tool calls)</div>
  </div>
</div>

<div class="charts-grid">

  <div class="chart-card full">
    <h3>Daily Prompts & Actions</h3>
    <canvas id="dailyChart"></canvas>
  </div>

  <div class="chart-card">
    <h3>Output Tokens by Model (Daily)</h3>
    <canvas id="tokenChart"></canvas>
  </div>

  <div class="chart-card">
    <h3>Model Usage (Input + Output)</h3>
    <canvas id="modelPie"></canvas>
  </div>

  <div class="chart-card full">
    <h3>Sessions by Hour of Day</h3>
    <canvas id="hourChart"></canvas>
  </div>

  <div class="chart-card full">
    <h3>Token Breakdown by Model</h3>
    <table>
      <thead>
        <tr><th>Model</th><th>Input</th><th>Output</th><th>Cache Read</th><th>Cache Write</th></tr>
      </thead>
      <tbody>
        {cost_rows}
        <tr style="font-weight:600; border-top:2px solid var(--border)">
          <td>Total</td>
          <td>{format_tokens(total_input)}</td>
          <td>{format_tokens(total_output)}</td>
          <td>{format_tokens(total_cache_read)}</td>
          <td>{format_tokens(total_cache_write)}</td>
        </tr>
      </tbody>
    </table>
  </div>

</div>

<div class="footer">
  Generated {generated_at} &middot; Data from ~/.claude/stats-cache.json
</div>

</div>

<script>
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';

// Daily prompts + actions
new Chart(document.getElementById('dailyChart'), {{
  type: 'bar',
  data: {{
    labels: {daily_dates_js},
    datasets: [
      {{
        label: 'Prompts',
        data: {daily_prompts_js},
        backgroundColor: 'rgba(139, 92, 246, 0.7)',
        borderColor: '#8b5cf6',
        borderWidth: 1,
        borderRadius: 4,
        order: 2,
      }},
      {{
        label: 'Actions Taken',
        data: {daily_tools_js},
        type: 'line',
        borderColor: '#06b6d4',
        backgroundColor: 'rgba(6, 182, 212, 0.1)',
        borderWidth: 2,
        tension: 0.3,
        fill: true,
        order: 1,
        pointRadius: 3,
      }},
      {{
        label: 'Sessions',
        data: {daily_sessions_js},
        type: 'line',
        borderColor: '#f59e0b',
        borderWidth: 2,
        tension: 0.3,
        order: 0,
        pointRadius: 3,
      }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'top' }} }},
    scales: {{
      y: {{ beginAtZero: true, grid: {{ color: '#1e293b' }} }},
      x: {{ grid: {{ display: false }} }}
    }}
  }}
}});

// Token stacked area
new Chart(document.getElementById('tokenChart'), {{
  type: 'line',
  data: {{
    labels: {token_dates_js},
    datasets: {token_datasets_json}
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'top' }} }},
    scales: {{
      y: {{
        stacked: true,
        beginAtZero: true,
        grid: {{ color: '#1e293b' }},
        ticks: {{
          callback: function(v) {{
            if (v >= 1000000) return (v/1000000).toFixed(0) + 'M';
            if (v >= 1000) return (v/1000).toFixed(0) + 'K';
            return v;
          }}
        }}
      }},
      x: {{ stacked: true, grid: {{ display: false }} }}
    }}
  }}
}});

// Model pie
new Chart(document.getElementById('modelPie'), {{
  type: 'doughnut',
  data: {{
    labels: {model_pie_labels_js},
    datasets: [{{
      data: {model_pie_data_js},
      backgroundColor: {model_pie_colors_js},
      borderWidth: 0,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: 'bottom' }},
      tooltip: {{
        callbacks: {{
          label: function(ctx) {{
            let v = ctx.raw;
            if (v >= 1000000) return ctx.label + ': ' + (v/1000000).toFixed(1) + 'M tokens';
            if (v >= 1000) return ctx.label + ': ' + (v/1000).toFixed(1) + 'K tokens';
            return ctx.label + ': ' + v + ' tokens';
          }}
        }}
      }}
    }}
  }}
}});

// Hour of day
new Chart(document.getElementById('hourChart'), {{
  type: 'bar',
  data: {{
    labels: {hour_labels_js},
    datasets: [{{
      label: 'Sessions Started',
      data: {hour_data_js},
      backgroundColor: function(ctx) {{
        const h = ctx.dataIndex;
        if (h >= 9 && h <= 17) return 'rgba(16, 185, 129, 0.7)';
        if (h >= 18 || h <= 5) return 'rgba(236, 72, 153, 0.7)';
        return 'rgba(245, 158, 11, 0.7)';
      }},
      borderRadius: 4,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          afterLabel: function(ctx) {{
            const h = ctx.dataIndex;
            if (h >= 9 && h <= 17) return '(work hours)';
            if (h >= 22 || h <= 5) return '(night owl)';
            return '';
          }}
        }}
      }}
    }},
    scales: {{
      y: {{ beginAtZero: true, grid: {{ color: '#1e293b' }}, ticks: {{ stepSize: 1 }} }},
      x: {{ grid: {{ display: false }} }}
    }}
  }}
}});
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(
        description="Generate a shareable Claude Code usage dashboard"
    )
    parser.add_argument(
        "--name", "-n",
        default=os.environ.get("USER", "Developer"),
        help="Your name for the report header",
    )
    parser.add_argument(
        "--claude-dir",
        default=Path.home() / ".claude",
        type=Path,
        help="Path to .claude directory (default: ~/.claude)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output HTML file path (default: ~/claude-dashboard.html)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't auto-open the report in browser",
    )
    args = parser.parse_args()

    output_path = Path(
        args.output or Path.home() / "claude-dashboard.html"
    )

    print(f"Loading stats from {args.claude_dir / 'stats-cache.json'}...")
    stats = load_stats(args.claude_dir)
    prompts_by_day = load_prompts_by_day(args.claude_dir)

    print("Generating dashboard...")
    html_content = generate_html(stats, prompts_by_day, args.name)

    output_path.write_text(html_content)
    print(f"Dashboard saved to {output_path}")

    if not args.no_open:
        webbrowser.open(f"file://{output_path.resolve()}")
        print("Opened in browser!")


if __name__ == "__main__":
    main()
