"""Generate assets/languages.svg from the GitHub languages API.

Aggregates the byte counts GitHub reports for every non-fork repository
owned by the user. With a token that can read private repositories
(STATS_TOKEN) private repositories are included too; otherwise only
public repositories are counted, using GH_TOKEN for rate limits.

Usage: python scripts/generate_languages_card.py [--from-json FILE]
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("GITHUB_USER", "flaviu-vanca")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "languages.svg")
API = "https://api.github.com"

COLORS = {
    "Java": "#b07219", "HTML": "#e34c26", "TypeScript": "#3178c6",
    "CSS": "#2dd4bf", "PowerShell": "#5391fe", "JavaScript": "#f1e05a",
    "HCL": "#844fba", "SQL": "#e38c00", "PLpgSQL": "#e38c00",
    "SCSS": "#c6538c", "Shell": "#89e051", "Python": "#3572a5",
    "Kotlin": "#a97bff", "PHP": "#4f5d95", "Dockerfile": "#384d54",
    "Makefile": "#427819", "Other": "#8b949e",
}
FALLBACK = ["#f97316", "#22c55e", "#ec4899", "#14b8a6", "#eab308", "#6366f1"]


def request(path, token):
    req = urllib.request.Request(API + path, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": USER + "-profile-card",
        **({"Authorization": "Bearer " + token} if token else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp), resp.headers


def get(path, token):
    return request(path, token)[0]


def describe_token(token):
    # Logs who the token belongs to and what it can do, never the token itself.
    user, headers = request("/user", token)
    scopes = headers.get("X-OAuth-Scopes")
    kind = f"classic token, scopes: [{scopes}]" if scopes is not None else "fine-grained token"
    print(f"STATS_TOKEN belongs to {user['login']} ({kind}); "
          f"owned private repos visible: {user.get('owned_private_repos', 'n/a')}")


def list_repos(token, private):
    # /user/repos needs a personal token and then includes private repos.
    path = ("/user/repos?affiliation=owner&visibility=all" if private
            else f"/users/{USER}/repos?type=owner")
    repos, page = [], 1
    while True:
        batch = get(f"{path}&per_page=100&page={page}", token)
        repos += batch
        if len(batch) < 100:
            return repos
        page += 1


def collect(token, private):
    totals, count, private_count = {}, 0, 0
    if private:
        describe_token(token)
    for repo in list_repos(token, private):
        if repo["fork"] or repo["archived"] or repo["owner"]["login"].lower() != USER.lower():
            continue
        count += 1
        private_count += repo["private"]
        for lang, size in get(f"/repos/{repo['full_name']}/languages", token).items():
            totals[lang] = totals.get(lang, 0) + size
    print(f"Counted {count} repositories ({private_count} private)"
          + ("" if private else "; set STATS_TOKEN to include private ones"))
    return totals, count


def render(totals, repo_count):
    total = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    top = [(name, size * 100 / total) for name, size in ranked[:9]]
    other = sum(size for _, size in ranked[9:]) * 100 / total
    if other >= 0.05:
        top.append(("Other", other))

    fallback = iter(FALLBACK * 3)
    colors = {name: COLORS.get(name) or next(fallback) for name, _ in top}
    updated = datetime.now(timezone.utc).strftime("%d %b %Y")

    width, pad = 495, 25
    bar = width - 2 * pad
    height = 110 + ((len(top) + 1) // 2) * 26
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Languages across my projects">',
        '<style>.t{font:600 18px "Segoe UI",Ubuntu,sans-serif;fill:#fe428e}'
        '.s{font:400 12px "Segoe UI",Ubuntu,sans-serif;fill:#a9fef7;opacity:.75}'
        '.l{font:400 13px "Segoe UI",Ubuntu,sans-serif;fill:#a9fef7}</style>',
        f'<rect width="{width}" height="{height}" rx="6" fill="#141321"/>',
        f'<text x="{pad}" y="35" class="t">Languages across my projects</text>',
        f'<text x="{pad}" y="55" class="s">{repo_count} repositories · updated {updated}</text>',
        f'<clipPath id="c"><rect x="{pad}" y="72" width="{bar}" height="10" rx="5"/></clipPath>',
        '<g clip-path="url(#c)">',
    ]
    x = pad
    for name, pct in top:
        w = bar * pct / 100
        out.append(f'<rect x="{x:.2f}" y="72" width="{w + 0.5:.2f}" height="10" fill="{colors[name]}"/>')
        x += w
    out.append("</g>")
    for i, (name, pct) in enumerate(top):
        cx = pad + (i % 2) * (bar / 2)
        cy = 112 + (i // 2) * 26
        out.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{colors[name]}"/>'
                   f'<text x="{cx + 16}" y="{cy}" class="l">{name} {pct:.1f}%</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--from-json":
        data = json.load(open(sys.argv[2]))
        totals, count = data["languages"], data["repos"]
    else:
        stats_token = os.environ.get("STATS_TOKEN", "")
        token = stats_token or os.environ.get("GH_TOKEN", "")
        totals, count = collect(token, private=bool(stats_token))
    if not totals:
        sys.exit("No language data returned; leaving the existing card untouched.")
    with open(OUT, "w") as f:
        f.write(render(totals, count))


if __name__ == "__main__":
    main()
