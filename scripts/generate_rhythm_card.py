"""Generate assets/rhythm.svg: when I code, by weekday and hour of day.

Reads the author timestamps of my commits over the last 12 months in every
repository, converts them to Irish time and draws two bar charts plus a
one-line "coding persona".

Usage: python scripts/generate_rhythm_card.py [--from-json FILE]
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from common import ACCENT, BG, FONT, TEXT, TITLE, USER, get_or_none, has_private_access, own_repos, write_asset

LOCAL_TZ = ZoneInfo("Europe/Dublin")
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def commit_times():
    since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    times = []
    for repo in own_repos():
        page = 1
        while True:
            batch = get_or_none(f"/repos/{repo['full_name']}/commits?author={USER}"
                                f"&since={since}&per_page=100&page={page}") or []
            for c in batch:
                stamp = c["commit"]["author"]["date"].replace("Z", "+00:00")
                times.append(datetime.fromisoformat(stamp).astimezone(LOCAL_TZ))
            if len(batch) < 100:
                break
            page += 1
    print(f"Collected {len(times)} commits")
    return times


def persona(by_hour):
    buckets = {
        "Night owl 🦉": list(range(21, 24)) + list(range(0, 5)),
        "Early bird 🐦": range(5, 9),
        "Daytime builder ☀️": range(9, 17),
        "Evening coder 🌆": range(17, 21),
    }
    return max(buckets, key=lambda name: sum(by_hour[h] for h in buckets[name]))


def bars(values, x0, y0, width, height, labels, every=1):
    peak = max(values) or 1
    step = width / len(values)
    out = []
    for i, v in enumerate(values):
        h = max(2, height * v / peak) if v else 2
        fill = TITLE if v == peak else "#8f2a5f"
        out.append(f'<rect x="{x0 + i * step + 1:.1f}" y="{y0 + height - h:.1f}" width="{step - 2:.1f}" '
                   f'height="{h:.1f}" rx="2" fill="{fill}"><title>{labels[i]}: {v}</title></rect>')
        if i % every == 0:
            out.append(f'<text x="{x0 + i * step + step / 2:.1f}" y="{y0 + height + 14}" '
                       f'class="a" text-anchor="middle">{labels[i]}</text>')
    return out


def render(times, private):
    by_day, by_hour = [0] * 7, [0] * 24
    for t in times:
        by_day[t.weekday()] += 1
        by_hour[t.hour] += 1
    best_day = DAYS[by_day.index(max(by_day))]
    best_hour = by_hour.index(max(by_hour))
    weekend = 100 * (by_day[5] + by_day[6]) / max(len(times), 1)
    updated = datetime.now(timezone.utc).strftime("%d %b %Y")
    scope = "public &amp; private" if private else "public"

    width, height, pad = 495, 250, 25
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="When I code">',
        f'<style>.t{{font:600 18px {FONT};fill:{TITLE}}}.s{{font:400 12px {FONT};fill:{TEXT};opacity:.75}}'
        f'.p{{font:700 16px {FONT};fill:{ACCENT}}}.k{{font:400 12px {FONT};fill:{TEXT}}}'
        f'.a{{font:400 10px {FONT};fill:{TEXT};opacity:.7}}</style>',
        f'<rect width="{width}" height="{height}" rx="6" fill="{BG}"/>',
        f'<text x="{pad}" y="35" class="t">When I code</text>',
        f'<text x="{pad}" y="55" class="s">{len(times):,} commits · last 12 months · {scope} · '
        f'Irish time · updated {updated}</text>',
        f'<text x="{pad}" y="84" class="p">{persona(by_hour)}</text>',
        f'<text x="{pad}" y="103" class="k">Most productive on {best_day}s around '
        f'{best_hour:02d}:00 · {weekend:.0f}% of commits on weekends</text>',
    ]
    out += bars(by_day, pad, 125, 140, 80, [d[:2] for d in DAYS])
    out += bars(by_hour, pad + 165, 125, width - 2 * pad - 165, 80,
                [f"{h:02d}" for h in range(24)], every=3)
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--from-json":
        times = [datetime.fromisoformat(t) for t in json.load(open(sys.argv[2]))]
        private = True
    else:
        times, private = commit_times(), has_private_access()
    if not times:
        sys.exit("No commits found; leaving the existing card untouched.")
    write_asset("rhythm.svg", render(times, private))


if __name__ == "__main__":
    main()
