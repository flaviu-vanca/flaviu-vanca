"""Generate assets/activity.svg from the GitHub GraphQL contributions calendar.

Shows contributions over the last 12 months, the current and longest
streak, and a contribution heatmap. With STATS_TOKEN (a token belonging to
the profile owner) private contributions are included; otherwise only
public ones are counted, using GH_TOKEN.

Usage: python scripts/generate_activity_card.py [--from-json FILE]
"""

import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

USER = os.environ.get("GITHUB_USER", "flaviu-vanca")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "activity.svg")

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

# Radical-theme heatmap shades, from no contributions to the most.
SHADES = ["#1e1c2e", "#5a1f47", "#8f2a5f", "#c93577", "#fe428e"]


def fetch_days(token):
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "User-Agent": USER + "-profile-card",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]]


def streaks(days):
    today = date.today().isoformat()
    counts = [c for d, c in days if d <= today]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    # Today without contributions yet does not break the current streak.
    if counts and counts[-1] == 0:
        counts = counts[:-1]
    current = 0
    for c in reversed(counts):
        if not c:
            break
        current += 1
    return current, longest


def shade(count, peak):
    if not count:
        return SHADES[0]
    return SHADES[min(4, 1 + int(3 * count / max(peak, 1)))]


def render(days, private=True):
    total = sum(c for _, c in days)
    current, longest = streaks(days)
    peak = max((c for _, c in days), default=0)
    updated = datetime.now(timezone.utc).strftime("%d %b %Y")
    scope = "public &amp; private" if private else "public only"

    width, pad = 495, 25
    step, cell = 8.4, 6.6
    grid_top = 118
    height = grid_top + 7 * step + 22

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height:.0f}" '
        f'viewBox="0 0 {width} {height:.0f}" role="img" aria-label="GitHub activity">',
        '<style>.t{font:600 18px "Segoe UI",Ubuntu,sans-serif;fill:#fe428e}'
        '.s{font:400 12px "Segoe UI",Ubuntu,sans-serif;fill:#a9fef7;opacity:.75}'
        '.n{font:700 22px "Segoe UI",Ubuntu,sans-serif;fill:#f8d847}'
        '.k{font:400 12px "Segoe UI",Ubuntu,sans-serif;fill:#a9fef7}</style>',
        f'<rect width="{width}" height="{height:.0f}" rx="6" fill="#141321"/>',
        f'<text x="{pad}" y="35" class="t">GitHub activity</text>',
        f'<text x="{pad}" y="55" class="s">Last 12 months, {scope} · updated {updated}</text>',
    ]
    stats = [(f"{total:,}", "contributions"), (f"{current}", "day current streak"),
             (f"{longest}", "day longest streak")]
    col = (width - 2 * pad) / 3
    for i, (num, label) in enumerate(stats):
        x = pad + i * col
        out.append(f'<text x="{x:.0f}" y="87" class="n">{num}</text>'
                   f'<text x="{x:.0f}" y="104" class="k">{label}</text>')

    # One column per week, Sunday at the top, like GitHub's own graph.
    first = date.fromisoformat(days[0][0])
    offset = (first.weekday() + 1) % 7
    for i, (d, c) in enumerate(days):
        slot = i + offset
        x = pad + (slot // 7) * step
        y = grid_top + (slot % 7) * step
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="1.5" '
                   f'fill="{shade(c, peak)}"><title>{d}: {c}</title></rect>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--from-json":
        days = [tuple(d) for d in json.load(open(sys.argv[2]))]
        private = True
    else:
        private = bool(os.environ.get("STATS_TOKEN"))
        days = fetch_days(os.environ.get("STATS_TOKEN") or os.environ.get("GH_TOKEN", ""))
    if not days:
        sys.exit("No contribution data returned; leaving the existing card untouched.")
    with open(OUT, "w") as f:
        f.write(render(days, private))
    print(f"Rendered {len(days)} days, {sum(c for _, c in days)} contributions")


if __name__ == "__main__":
    main()
