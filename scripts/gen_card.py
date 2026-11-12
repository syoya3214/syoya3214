"""Generate an SVG card of the last year's GitHub contributions.

Uses only the workflow's built-in GITHUB_TOKEN. Private contributions are
included as counts when "Private contributions" is enabled on the profile.
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from collections import OrderedDict

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_days(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        data = json.load(res)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    return cal["totalContributions"], days


def streaks(days):
    longest = cur = 0
    for _, c in days:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)
    # current streak: allow today to be empty (the day is not over yet)
    current = 0
    rest = days[:-1] if days and days[-1][1] == 0 else days
    for _, c in reversed(rest):
        if c == 0:
            break
        current += 1
    return longest, current


def monthly(days):
    months = OrderedDict()
    for date, c in days:
        months[date[:7]] = months.get(date[:7], 0) + c
    items = list(months.items())
    return items[-12:]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(total, days):
    longest, current = streaks(days)
    active = sum(1 for _, c in days if c > 0)
    best_date, best = max(days, key=lambda x: x[1])
    months = monthly(days)
    peak = max([c for _, c in months] + [1])
    start, end = days[0][0], days[-1][0]

    W, H = 900, 305
    # bar chart area
    cx, cy, cw, ch = 330, 70, 540, 190
    n = len(months)
    slot = cw / n
    bw = slot * 0.62

    bars = []
    for i, (ym, c) in enumerate(months):
        h = max(2, ch * c / peak) if c else 2
        x = cx + i * slot + (slot - bw) / 2
        y = cy + ch - h
        label = f"{int(ym[5:])}月"
        delay = 0.08 * i
        bars.append(
            f'<g><rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" '
            f'style="animation-delay:{delay:.2f}s"/>'
            f'<text class="mlabel" x="{x + bw / 2:.1f}" y="{cy + ch + 20}">{label}</text>'
            + (f'<text class="val" x="{x + bw / 2:.1f}" y="{y - 6:.1f}" style="animation-delay:{delay + 0.5:.2f}s">{c}</text>' if c else "")
            + "</g>"
        )

    def stat(y, value, label):
        return (
            f'<text class="sval" x="40" y="{y}">{value}</text>'
            f'<text class="slabel" x="40" y="{y + 20}">{esc(label)}</text>'
        )

    bd = dt.date.fromisoformat(best_date)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{total} contributions in the last year">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0f2027"/><stop offset="0.5" stop-color="#203a43"/><stop offset="1" stop-color="#2c5364"/>
  </linearGradient>
  <linearGradient id="bar" x1="0" y1="1" x2="0" y2="0">
    <stop offset="0" stop-color="#1e88e5"/><stop offset="1" stop-color="#4fc3f7"/>
  </linearGradient>
</defs>
<style>
  text {{ font-family: "Segoe UI", "Hiragino Sans", "Noto Sans JP", Ubuntu, sans-serif; }}
  .title {{ fill: #e0f7fa; font-size: 15px; font-weight: 600; letter-spacing: .5px; }}
  .big {{ fill: #4fc3f7; font-size: 64px; font-weight: 700; }}
  .bigl {{ fill: #b0bec5; font-size: 14px; }}
  .sval {{ fill: #ffffff; font-size: 22px; font-weight: 700; }}
  .slabel {{ fill: #90a4ae; font-size: 12px; }}
  .mlabel {{ fill: #90a4ae; font-size: 12px; text-anchor: middle; }}
  .val {{ fill: #e0f7fa; font-size: 11px; text-anchor: middle; opacity: 0; animation: fade .4s ease forwards; }}
  .range {{ fill: #607d8b; font-size: 11px; text-anchor: end; }}
  .bar {{ fill: url(#bar); transform-box: fill-box; transform-origin: bottom; transform: scaleY(0); animation: grow .7s cubic-bezier(.2,.8,.2,1) forwards; }}
  @keyframes grow {{ to {{ transform: scaleY(1); }} }}
  @keyframes fade {{ to {{ opacity: 1; }} }}
</style>
<rect width="{W}" height="{H}" rx="14" fill="url(#bg)"/>
<text class="title" x="40" y="42">CONTRIBUTIONS · 過去1年</text>
<text class="range" x="{W - 30}" y="42">{start} 〜 {end}</text>
<text class="big" x="36" y="122">{total}</text>
<text class="bigl" x="40" y="146">コントリビューション</text>
{stat(196, f"{active}日", "活動した日数")}
{stat(256, f"{longest}日", "最長連続日数")}
<g transform="translate(150,0)">{stat(196, f"{best}件", f"1日の最多（{bd.month}/{bd.day}）")}{stat(256, f"{current}日", "現在の連続日数")}</g>
<line x1="{cx - 20}" y1="{cy}" x2="{cx - 20}" y2="{cy + ch + 24}" stroke="#ffffff" stroke-opacity=".08"/>
{''.join(bars)}
</svg>
"""


def main():
    login = os.environ.get("USERNAME") or sys.argv[1]
    out = os.environ.get("OUTPUT", "assets/contrib-card.svg")
    if len(sys.argv) > 2:  # local test: python gen_card.py <login> <days.json>
        days = [tuple(x) for x in json.load(open(sys.argv[2]))]
        total = sum(c for _, c in days)
    else:
        total, days = fetch_days(login, os.environ["GITHUB_TOKEN"])
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(total, days))
    print(f"wrote {out}: total={total}")


if __name__ == "__main__":
    main()
