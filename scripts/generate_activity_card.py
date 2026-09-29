"""Generate assets/activity.svg from the GitHub GraphQL contributions calendar.

Shows contributions over the last 12 months, the current and longest
streak, and commit / pull request / code review totals. (GitHub already
shows the contribution heatmap on the profile, so it is not repeated.) With STATS_TOKEN (a token belonging to
the profile owner) private contributions are included; otherwise only
public ones are counted, using GH_TOKEN.

Usage: python scripts/generate_activity_card.py [--from-json FILE]
"""

import json
import os
import sys
import urllib.request
from datetime import date, datetime, timezone

USER = os.environ.get("GITHUB_USER", "flaviu-vanca")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "activity.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

def fetch(token):
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
    coll = data["data"]["user"]["contributionsCollection"]
    weeks = coll["contributionCalendar"]["weeks"]
    days = [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]]
    totals = {
        "commits": coll["totalCommitContributions"],
        "pull requests": coll["totalPullRequestContributions"],
        "code reviews": coll["totalPullRequestReviewContributions"],
    }
    return days, totals


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


def render(days, totals, private=True):
    total = sum(c for _, c in days)
    current, longest = streaks(days)
    updated = datetime.now(timezone.utc).strftime("%d %b %Y")
    scope = "public &amp; private" if private else "public only"

    width, pad = 495, 25
    height = 175
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="GitHub activity">',
        '<style>.t{font:600 18px "Segoe UI",Ubuntu,sans-serif;fill:#fe428e}'
        '.s{font:400 12px "Segoe UI",Ubuntu,sans-serif;fill:#a9fef7;opacity:.75}'
        '.n{font:700 22px "Segoe UI",Ubuntu,sans-serif;fill:#f8d847}'
        '.k{font:400 12px "Segoe UI",Ubuntu,sans-serif;fill:#a9fef7}</style>',
        f'<rect width="{width}" height="{height}" rx="6" fill="#141321"/>',
        f'<text x="{pad}" y="35" class="t">GitHub activity</text>',
        f'<text x="{pad}" y="55" class="s">Last 12 months, {scope} · updated {updated}</text>',
    ]
    rows = [
        [(f"{total:,}", "contributions"), (f"{current}", "day current streak"),
         (f"{longest}", "day longest streak")],
        [(f"{n:,}", label) for label, n in totals.items()],
    ]
    col = (width - 2 * pad) / 3
    for r, row in enumerate(rows):
        for i, (num, label) in enumerate(row):
            x, y = pad + i * col, 90 + r * 55
            out.append(f'<text x="{x:.0f}" y="{y}" class="n">{num}</text>'
                       f'<text x="{x:.0f}" y="{y + 17}" class="k">{label}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--from-json":
        data = json.load(open(sys.argv[2]))
        days, totals = [tuple(d) for d in data["days"]], data["totals"]
        private = True
    else:
        private = bool(os.environ.get("STATS_TOKEN"))
        days, totals = fetch(os.environ.get("STATS_TOKEN") or os.environ.get("GH_TOKEN", ""))
    if not days:
        sys.exit("No contribution data returned; leaving the existing card untouched.")
    with open(OUT, "w") as f:
        f.write(render(days, totals, private))
    print(f"Rendered {len(days)} days, {sum(c for _, c in days)} contributions")


if __name__ == "__main__":
    main()
