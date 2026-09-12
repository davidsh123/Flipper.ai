"""
Builds a self-contained HTML report for the Kijiji Flipper — no internet connection or
external assets required, so it still opens fine on flaky hackathon wifi.
"""

import json
import os
import webbrowser
from datetime import datetime

TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Kijiji Flipper Results</title>
<style>
  :root {
    --bg: #F4F6F3;
    --surface: #FFFFFF;
    --ink: #172420;
    --ink-muted: #57685F;
    --accent: #12805F;
    --accent-ink: #FFFFFF;
    --line: #DEE5E0;
    --deal: #B4762A;
    --deal-soft: #FBF0DF;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, "Segoe UI", ui-sans-serif, sans-serif;
  }
  .page { max-width: 980px; margin: 0 auto; padding: 32px 24px 80px; }
  header { margin-bottom: 28px; }
  .eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--accent);
    margin: 0 0 6px;
  }
  h1 { font-size: 1.7rem; margin: 0 0 14px; letter-spacing: -0.01em; }
  .stats {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
  .stat {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 12px 16px;
    min-width: 140px;
  }
  .stat-label { font-size: 0.72rem; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .stat-value { font-size: 1.3rem; font-weight: 700; font-variant-numeric: tabular-nums; margin-top: 2px; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
    margin-top: 24px;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 14px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .card-img {
    width: 100%;
    height: 160px;
    object-fit: cover;
    background: var(--line);
    display: block;
  }
  .card-body { padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 8px; flex: 1; }
  .card-title { font-weight: 600; font-size: 0.95rem; line-height: 1.3; }
  .price-row { display: flex; align-items: baseline; gap: 8px; }
  .price { font-weight: 700; font-size: 1.4rem; color: var(--accent); font-variant-numeric: tabular-nums; }
  .below { font-size: 0.75rem; color: var(--deal); background: var(--deal-soft); padding: 2px 8px; border-radius: 999px; font-weight: 600; }
  .meta { font-size: 0.78rem; color: var(--ink-muted); }
  .message-box {
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 0.82rem;
    font-style: italic;
    color: var(--ink);
    margin-top: 4px;
  }
  .card a.view-link {
    margin-top: auto;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--accent-ink);
    background: var(--ink);
    text-decoration: none;
    text-align: center;
    padding: 9px;
    border-radius: 8px;
  }
  .empty { color: var(--ink-muted); padding: 40px 0; text-align: center; }
</style>
</head>
<body>
  <div class="page">
    <header>
      <p class="eyebrow">Kijiji Flipper &middot; __GENERATED_AT__</p>
      <h1>__DEAL_COUNT__ potential deal(s) found</h1>
      <div class="stats">
        <div class="stat"><div class="stat-label">Listings Scanned</div><div class="stat-value">__LISTING_COUNT__</div></div>
        <div class="stat"><div class="stat-label">Median Price</div><div class="stat-value">$__MEDIAN_PRICE__</div></div>
        <div class="stat"><div class="stat-label">Deal Threshold</div><div class="stat-value">$__THRESHOLD_PRICE__</div></div>
      </div>
    </header>
    <div class="grid" id="grid"></div>
  </div>
<script>
  const deals = __DEALS_JSON__;
  const grid = document.getElementById("grid");
  if (deals.length === 0) {
    grid.innerHTML = '<div class="empty">No underpriced listings this run — try a different search or lower the threshold.</div>';
  } else {
    for (const d of deals) {
      const card = document.createElement("div");
      card.className = "card";
      const pct = Math.round((1 - d.price / d.median) * 100);
      card.innerHTML = `
        <img class="card-img" src="${d.image || ''}" onerror="this.style.display='none'" alt="">
        <div class="card-body">
          <div class="card-title">${d.title}</div>
          <div class="price-row">
            <span class="price">$${d.price.toFixed(2)}</span>
            <span class="below">${pct}% below market</span>
          </div>
          <div class="meta">${d.location} &middot; ${d.date}</div>
          <div class="message-box">&ldquo;${d.message}&rdquo;</div>
          <a class="view-link" href="${d.url}" target="_blank" rel="noopener">View listing &rarr;</a>
        </div>`;
      grid.appendChild(card);
    }
  }
</script>
</body>
</html>
"""


def generate_report(listings, deals, median_price, threshold, messages_by_url):
    deals_json = json.dumps([
        {
            "title": d["title"],
            "price": d["price"],
            "median": median_price,
            "location": d["location"],
            "date": d["date"],
            "url": d["url"],
            "image": d["image"],
            "message": messages_by_url.get(d["url"], ""),
        }
        for d in deals
    ])

    html = (
        TEMPLATE
        .replace("__GENERATED_AT__", datetime.now().strftime("%Y-%m-%d %H:%M"))
        .replace("__DEAL_COUNT__", str(len(deals)))
        .replace("__LISTING_COUNT__", str(len(listings)))
        .replace("__MEDIAN_PRICE__", f"{median_price:,.2f}")
        .replace("__THRESHOLD_PRICE__", f"{median_price * threshold:,.2f}")
        .replace("__DEALS_JSON__", deals_json)
    )

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def open_report(path):
    webbrowser.open("file://" + path.replace("\\", "/"))
