"""Generate a standalone HTML library insights report."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cratedigger.utils.db import get_connection


def _query_analysis_stats(db_path: Optional[Path] = None) -> dict:
    """Query audio_analysis table for aggregate stats."""
    conn = get_connection(db_path)

    stats = {}
    row = conn.execute("SELECT COUNT(*) FROM audio_analysis").fetchone()
    stats["total_tracks"] = row[0] if row else 0

    if stats["total_tracks"] == 0:
        conn.close()
        return stats

    # BPM stats
    row = conn.execute(
        "SELECT MIN(bpm), MAX(bpm), AVG(bpm) FROM audio_analysis WHERE bpm IS NOT NULL AND bpm > 0"
    ).fetchone()
    if row and row[0]:
        stats["bpm_min"] = round(row[0], 1)
        stats["bpm_max"] = round(row[1], 1)
        stats["bpm_avg"] = round(row[2], 1)

    # Key distribution
    rows = conn.execute(
        "SELECT key_camelot, COUNT(*) as cnt FROM audio_analysis "
        "WHERE key_camelot IS NOT NULL GROUP BY key_camelot ORDER BY cnt DESC"
    ).fetchall()
    stats["keys"] = [{"key": r[0], "count": r[1]} for r in rows]

    # Energy stats
    row = conn.execute(
        "SELECT MIN(energy), MAX(energy), AVG(energy) FROM audio_analysis WHERE energy IS NOT NULL"
    ).fetchone()
    if row and row[0] is not None:
        stats["energy_min"] = round(row[0], 2)
        stats["energy_max"] = round(row[1], 2)
        stats["energy_avg"] = round(row[2], 2)

    # Genre distribution
    rows = conn.execute(
        "SELECT genre, COUNT(*) as cnt FROM audio_analysis "
        "WHERE genre IS NOT NULL AND genre != '' GROUP BY genre ORDER BY cnt DESC"
    ).fetchall()
    stats["genres"] = [{"genre": r[0], "count": r[1]} for r in rows]

    # BPM distribution (buckets of 5)
    rows = conn.execute(
        "SELECT CAST(bpm / 5 AS INTEGER) * 5 as bucket, COUNT(*) as cnt "
        "FROM audio_analysis WHERE bpm IS NOT NULL AND bpm > 0 "
        "GROUP BY bucket ORDER BY bucket"
    ).fetchall()
    stats["bpm_buckets"] = [{"bpm": r[0], "count": r[1]} for r in rows]

    # Danceability stats
    row = conn.execute(
        "SELECT AVG(danceability) FROM audio_analysis WHERE danceability IS NOT NULL"
    ).fetchone()
    if row and row[0] is not None:
        stats["danceability_avg"] = round(row[0], 2)

    # Analyzed vs total
    row = conn.execute(
        "SELECT COUNT(*) FROM audio_analysis WHERE bpm IS NOT NULL AND bpm > 0"
    ).fetchone()
    stats["analyzed_count"] = row[0] if row else 0

    conn.close()
    return stats


def generate_html_report(
    db_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """Generate a standalone HTML library insights report.

    Args:
        db_path: SQLite database path. Uses default if None.
        output_path: Where to write the HTML. Defaults to library_report.html.

    Returns:
        Path to the generated HTML file.
    """
    stats = _query_analysis_stats(db_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if output_path is None:
        output_path = Path("library_report.html")

    # Build chart data
    bpm_labels = json.dumps([b["bpm"] for b in stats.get("bpm_buckets", [])])
    bpm_values = json.dumps([b["count"] for b in stats.get("bpm_buckets", [])])
    key_labels = json.dumps([k["key"] for k in stats.get("keys", [])[:12]])
    key_values = json.dumps([k["count"] for k in stats.get("keys", [])[:12]])
    genre_labels = json.dumps([g["genre"] for g in stats.get("genres", [])[:10]])
    genre_values = json.dumps([g["count"] for g in stats.get("genres", [])[:10]])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DJ CrateDigger — Library Insights</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --accent: #c084fc;
    --green: #3fb950;
    --yellow: #d29922;
    --red: #f85149;
    --cyan: #58a6ff;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem;
  }}
  .header {{
    text-align: center;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border);
  }}
  .header h1 {{ color: var(--accent); font-size: 2rem; font-weight: 700; }}
  .header p {{ color: var(--text-dim); margin-top: 0.5rem; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
    max-width: 1200px;
    margin: 0 auto;
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
  }}
  .card h2 {{
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-dim);
    margin-bottom: 1rem;
  }}
  .stat {{
    font-size: 2.5rem;
    font-weight: 700;
    color: var(--accent);
  }}
  .stat-label {{ color: var(--text-dim); font-size: 0.9rem; }}
  .stat-row {{
    display: flex;
    justify-content: space-between;
    padding: 0.4rem 0;
    border-bottom: 1px solid var(--border);
  }}
  .stat-row:last-child {{ border-bottom: none; }}
  .chart-container {{ position: relative; width: 100%; }}
  .wide {{ grid-column: span 2; }}
  @media (max-width: 700px) {{ .wide {{ grid-column: span 1; }} }}
  .footer {{
    text-align: center;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 0.85rem;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>DJ CrateDigger — Library Insights</h1>
  <p>Generated {now}</p>
</div>

<div class="grid">

  <div class="card">
    <h2>Library Size</h2>
    <div class="stat">{stats.get('total_tracks', 0)}</div>
    <div class="stat-label">tracks in database</div>
    <div style="margin-top: 1rem;">
      <div class="stat-row">
        <span>Analyzed</span>
        <span style="color: var(--green);">{stats.get('analyzed_count', 0)}</span>
      </div>
      <div class="stat-row">
        <span>Pending</span>
        <span style="color: var(--yellow);">{stats.get('total_tracks', 0) - stats.get('analyzed_count', 0)}</span>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>BPM Range</h2>
    <div class="stat">{stats.get('bpm_min', '?')} – {stats.get('bpm_max', '?')}</div>
    <div class="stat-label">average {stats.get('bpm_avg', '?')} BPM</div>
  </div>

  <div class="card">
    <h2>Energy & Danceability</h2>
    <div class="stat-row">
      <span>Avg Energy</span>
      <span style="color: var(--cyan);">{stats.get('energy_avg', '?')}</span>
    </div>
    <div class="stat-row">
      <span>Energy Range</span>
      <span>{stats.get('energy_min', '?')} – {stats.get('energy_max', '?')}</span>
    </div>
    <div class="stat-row">
      <span>Avg Danceability</span>
      <span style="color: var(--accent);">{stats.get('danceability_avg', '?')}</span>
    </div>
  </div>

  <div class="card wide">
    <h2>BPM Distribution</h2>
    <div class="chart-container">
      <canvas id="bpmChart"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>Top Keys</h2>
    <div class="chart-container">
      <canvas id="keyChart"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>Top Genres</h2>
    <div class="chart-container">
      <canvas id="genreChart"></canvas>
    </div>
  </div>

</div>

<div class="footer">
  Built by DJ CrateDigger AI
</div>

<script>
Chart.defaults.color = '#8b949e';
Chart.defaults.borderColor = '#30363d';

new Chart(document.getElementById('bpmChart'), {{
  type: 'bar',
  data: {{
    labels: {bpm_labels},
    datasets: [{{ label: 'Tracks', data: {bpm_values},
      backgroundColor: 'rgba(192, 132, 252, 0.6)', borderColor: '#c084fc', borderWidth: 1 }}]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true }}, x: {{ title: {{ display: true, text: 'BPM' }} }} }} }}
}});

new Chart(document.getElementById('keyChart'), {{
  type: 'doughnut',
  data: {{
    labels: {key_labels},
    datasets: [{{ data: {key_values},
      backgroundColor: ['#c084fc','#58a6ff','#3fb950','#d29922','#f85149','#f0883e',
                         '#a371f7','#79c0ff','#56d364','#e3b341','#ff7b72','#ffa657'] }}]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12 }} }} }} }}
}});

new Chart(document.getElementById('genreChart'), {{
  type: 'bar',
  data: {{
    labels: {genre_labels},
    datasets: [{{ label: 'Tracks', data: {genre_values},
      backgroundColor: 'rgba(88, 166, 255, 0.6)', borderColor: '#58a6ff', borderWidth: 1 }}]
  }},
  options: {{ indexAxis: 'y', responsive: true, plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ beginAtZero: true }} }} }}
}});
</script>

</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return output_path
