"""Generate a self-contained HTML dashboard from Bedrock evaluation history."""

import html
import json
from pathlib import Path

from check_evaluation_job import BUSINESS_WEIGHTS, HISTORY_PATH, load_history

OUTPUT_PATH = Path(__file__).with_name("evaluation_dashboard.html")


def quality_index(metrics):
    weighted = []
    for name, weight in BUSINESS_WEIGHTS.items():
        if name in metrics:
            weighted.append((metrics[name]["average"], weight))
    if not weighted:
        return None
    return sum(value * weight for value, weight in weighted) / sum(
        weight for _, weight in weighted
    )


def metric_rows(history):
    names = sorted({name for run in history for name in run.get("metrics", {})})
    rows = []
    for name in names:
        values = [run.get("metrics", {}).get(name, {}).get("average") for run in history]
        values = [value for value in values if value is not None]
        latest = values[-1] if values else None
        previous = values[-2] if len(values) > 1 else None
        change = latest - previous if latest is not None and previous is not None else None
        rows.append((name, values, latest, change))
    return rows


def svg_chart(rows, width=900, height=340):
    if not rows:
        return "<p>No metric history available yet.</p>"
    chart_rows = rows[:8]
    max_runs = max(len(values) for _, values, _, _ in chart_rows)
    left, right, top, bottom = 62, 20, 24, 42
    plot_width = width - left - right
    plot_height = height - top - bottom
    colors = ["#0f766e", "#2563eb", "#ca8a04", "#dc2626", "#7c3aed", "#0891b2", "#be123c", "#4f46e5"]
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Metric score trends">']
    for tick in range(0, 6):
        value = tick / 5
        y = top + (1 - value) * plot_height
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" class="axis">{value:.1f}</text>')
    for index in range(max_runs):
        x = left if max_runs == 1 else left + index * plot_width / (max_runs - 1)
        parts.append(f'<text x="{x:.1f}" y="{height-14}" text-anchor="middle" class="axis">Run {index+1}</text>')
    for row_index, (name, values, _, _) in enumerate(chart_rows):
        points = []
        for index, value in enumerate(values):
            x = left if max_runs == 1 else left + index * plot_width / (max_runs - 1)
            y = top + (1 - value) * plot_height
            points.append(f"{x:.1f},{y:.1f}")
        color = colors[row_index % len(colors)]
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3"/>')
        if points:
            x, y = points[-1].split(",")
            parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
    parts.append("</svg>")
    return "".join(parts)


def generate_dashboard(history):
    latest = history[-1] if history else {"metrics": {}}
    previous = history[-2] if len(history) > 1 else None
    rows = metric_rows(history)
    index = quality_index(latest.get("metrics", {}))
    previous_index = quality_index(previous.get("metrics", {})) if previous else None
    index_change = index - previous_index if index is not None and previous_index is not None else None

    cards = []
    for name, _, value, change in rows:
        if value is None:
            continue
        change_text = "Baseline" if change is None else f"{change:+.3f} vs previous"
        direction = "up" if change is not None and change >= 0 else "down"
        cards.append(
            f'<article class="metric"><span>{html.escape(name.replace("Builtin.", ""))}</span>'
            f'<strong>{value:.3f}</strong><small class="{direction}">{change_text}</small></article>'
        )
    cards_html = "".join(cards) or '<p class="muted">No completed Bedrock runs recorded.</p>'
    run_time = html.escape(latest.get("timestamp", "unknown"))
    job_id = html.escape(latest.get("job_identifier", "unknown"))
    index_text = "n/a" if index is None else f"{index:.3f}"
    index_change_text = "Baseline" if index_change is None else f"{index_change:+.3f} vs previous"
    metric_data = {
        name: [
            {
                "run": index + 1,
                "timestamp": run.get("timestamp", "unknown"),
                "score": run.get("metrics", {}).get(name, {}).get("average"),
                "count": run.get("metrics", {}).get(name, {}).get("count"),
            }
            for index, run in enumerate(history)
            if name in run.get("metrics", {})
        ]
        for name, _, _, _ in rows
    }
    metric_data_json = json.dumps(metric_data).replace("</", "<\\/")
    metric_options = "".join(
        f'<option value="{html.escape(name)}">{html.escape(name.replace("Builtin.", ""))}</option>'
        for name, _, _, _ in rows
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bedrock Evaluation Dashboard</title>
<style>
:root {{ --ink:#17202a; --muted:#64748b; --line:#dbe4e8; --paper:#f5f7f6; --teal:#0f766e; --amber:#ca8a04; }}
* {{ box-sizing:border-box; }} body {{ margin:0; color:var(--ink); background:var(--paper); font-family:Georgia, 'Times New Roman', serif; }}
main {{ max-width:1180px; margin:0 auto; padding:48px 24px 72px; }}
header {{ display:flex; justify-content:space-between; gap:24px; align-items:end; border-bottom:1px solid var(--line); padding-bottom:28px; }}
h1 {{ font-size:clamp(2rem,5vw,4.6rem); line-height:.95; margin:0; letter-spacing:0; font-weight:500; }}
.kicker {{ color:var(--teal); font:700 .74rem/1.2 Arial,sans-serif; letter-spacing:.12em; text-transform:uppercase; }}
.meta {{ color:var(--muted); font: .78rem/1.5 Arial,sans-serif; text-align:right; max-width:360px; }}
section {{ margin-top:34px; }} h2 {{ font-size:1.25rem; font-weight:500; margin:0 0 14px; }}
.index {{ background:var(--ink); color:white; padding:22px 24px; display:flex; justify-content:space-between; align-items:end; gap:18px; }}
.index strong {{ font-size:3rem; font-weight:500; }} .index small {{ color:#b8d6d2; font: .8rem Arial,sans-serif; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; }}
.metric {{ background:white; border:1px solid var(--line); padding:16px; min-height:112px; display:flex; flex-direction:column; justify-content:space-between; cursor:pointer; }}
.metric:hover, .metric:focus {{ border-color:var(--teal); outline:2px solid #b8d6d2; outline-offset:2px; }}
.metric span {{ color:var(--muted); font: .74rem Arial,sans-serif; }} .metric strong {{ font-size:1.8rem; font-weight:500; }} .metric small {{ font: .72rem Arial,sans-serif; }} .up {{ color:var(--teal); }} .down {{ color:#b42318; }}
.chart {{ background:white; border:1px solid var(--line); padding:16px; overflow:auto; }} svg {{ width:100%; min-width:620px; height:auto; }} .grid {{ stroke:#e7edef; stroke-width:1; }} .axis {{ fill:#718096; font:11px Arial,sans-serif; }}
.explorer {{ display:grid; grid-template-columns:minmax(180px, .7fr) 1.3fr; gap:16px; align-items:start; }}
.control, .detail {{ background:white; border:1px solid var(--line); padding:18px; }}
select {{ width:100%; border:1px solid var(--line); background:white; color:var(--ink); padding:10px; font: .9rem Arial,sans-serif; }}
.detail h3 {{ margin:0 0 4px; font-size:1.6rem; font-weight:500; }} .detail-meta {{ color:var(--muted); font: .76rem Arial,sans-serif; }}
.score-strip {{ display:flex; gap:8px; align-items:end; height:120px; margin:18px 0; border-bottom:1px solid var(--line); }}
.score-bar {{ flex:1; min-width:18px; background:var(--teal); position:relative; }} .score-bar span {{ position:absolute; bottom:calc(100% + 5px); width:100%; text-align:center; color:var(--muted); font:.68rem Arial,sans-serif; }}
.score-bar small {{ position:absolute; top:calc(100% + 5px); width:100%; text-align:center; color:var(--muted); font:.65rem Arial,sans-serif; }}
.detail-table {{ width:100%; border-collapse:collapse; font:.76rem Arial,sans-serif; }} .detail-table th, .detail-table td {{ padding:8px 4px; border-bottom:1px solid #edf1f2; text-align:left; }}
.note {{ color:var(--muted); font: .78rem/1.5 Arial,sans-serif; }}
@media (max-width:650px) {{ main {{ padding:30px 16px 48px; }} header {{ display:block; }} .meta {{ text-align:left; margin-top:18px; }} .explorer {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body><main id="dashboard-content">
<header><div><div class="kicker">AWS Bedrock / RAG evaluation</div><h1>Quality over time.</h1></div><div class="meta">Latest run: {run_time}<br>Job: {job_id}</div></header>
<section><div class="index"><div><div class="kicker" style="color:#8ed1c9">business value proxy</div><strong>{index_text}</strong></div><small>{index_change_text}<br>Weighted quality signal, not a dollar estimate.</small></div></section>
<section><h2>Latest metric scores</h2><div class="cards">{cards_html}</div></section>
<section><h2>Metric explorer</h2><div class="explorer"><div class="control"><label for="metric-select" class="kicker">Choose a metric</label><select id="metric-select">{metric_options}</select><p class="note">Inspect every recorded run, score count, and change context for one metric.</p></div><div class="detail" id="metric-detail"></div></div></section>
<section><h2>Metric trajectory</h2><div class="chart">{svg_chart(rows)}</div><p class="note">Scores come from Bedrock evaluator results stored in evaluation_history.jsonl. The dashboard shows association over runs, not proof that a specific code change caused a change in score.</p></section>
</main><script>
const metricData = {metric_data_json};
function renderMetric(name) {{
    const detail = document.querySelector('#metric-detail');
    const entries = metricData[name] || [];
    const latest = entries[entries.length - 1];
    const previous = entries[entries.length - 2];
    if (!detail || !latest) return;
    const delta = previous ? latest.score - previous.score : null;
    const deltaText = delta === null ? 'Baseline run' : `${{delta >= 0 ? '+' : ''}}${{delta.toFixed(3)}} vs previous`;
    const bars = entries.map(entry => `<div class="score-bar" style="height:${{Math.max(4, entry.score * 100)}}%"><span>${{entry.score.toFixed(3)}}</span><small>R${{entry.run}}</small></div>`).join('');
    const table = [...entries].reverse().map(entry => `<tr><td>Run ${{entry.run}}</td><td>${{entry.timestamp}}</td><td>${{entry.score.toFixed(3)}}</td><td>${{entry.count ?? 'n/a'}}</td></tr>`).join('');
    detail.innerHTML = `<h3>${{name.replace('Builtin.', '')}}</h3><div class="detail-meta">Latest score <strong>${{latest.score.toFixed(3)}}</strong> · ${{deltaText}}</div><div class="score-strip">${{bars}}</div><table class="detail-table"><thead><tr><th>Run</th><th>Timestamp</th><th>Score</th><th>Samples</th></tr></thead><tbody>${{table}}</tbody></table>`;
}}
document.addEventListener('click', event => {{
    const card = event.target.closest('.metric');
    if (card) {{
        const name = Object.keys(metricData).find(key => card.textContent.includes(key.replace('Builtin.', '')));
        if (name) {{ document.querySelector('#metric-select').value = name; renderMetric(name); }}
    }}
}});
document.addEventListener('change', event => {{
    if (event.target.id === 'metric-select') renderMetric(event.target.value);
}});
renderMetric(document.querySelector('#metric-select')?.value);
async function refreshDashboard() {{
    try {{
        const response = await fetch('/api/dashboard', {{cache: 'no-store'}});
        if (!response.ok) return;
        const documentText = await response.text();
        const parsed = new DOMParser().parseFromString(documentText, 'text/html');
        const latest = parsed.querySelector('#dashboard-content');
        const current = document.querySelector('#dashboard-content');
        if (latest && current) current.innerHTML = latest.innerHTML;
    }} catch (error) {{
        console.debug('Dashboard refresh unavailable', error);
    }}
}}
if (window.location.protocol.startsWith('http')) {{
    window.setInterval(refreshDashboard, 15000);
}}
</script></body></html>"""


def main():
    history = load_history()
    OUTPUT_PATH.write_text(generate_dashboard(history), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
