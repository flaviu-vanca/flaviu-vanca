"""Shared helpers for the profile card generators."""

import json
import os
import urllib.error
import urllib.request

USER = os.environ.get("GITHUB_USER", "flaviu-vanca")
API = "https://api.github.com"
ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")

# Radical theme, matching the other cards.
BG, TITLE, TEXT, ACCENT = "#141321", "#fe428e", "#a9fef7", "#f8d847"
FONT = '"Segoe UI",Ubuntu,sans-serif'


def token():
    """Personal token (includes private repos) or the workflow token."""
    return os.environ.get("STATS_TOKEN") or os.environ.get("GH_TOKEN", "")


def has_private_access():
    return bool(os.environ.get("STATS_TOKEN"))


def get(path, raw=False):
    tok = token()
    req = urllib.request.Request(API + path, headers={
        "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
        "User-Agent": USER + "-profile-card",
        **({"Authorization": "Bearer " + tok} if tok else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
    return body.decode("utf-8", "replace") if raw else json.loads(body)


def get_or_none(path, raw=False):
    """Like get(), but None for empty repositories and missing resources."""
    try:
        return get(path, raw)
    except urllib.error.HTTPError as err:
        if err.code in (404, 409):
            return None
        raise


def own_repos():
    """Non-fork, non-archived repositories owned by USER."""
    path = ("/user/repos?visibility=all" if has_private_access()
            else f"/users/{USER}/repos?type=owner")
    repos, page = [], 1
    while True:
        batch = get(f"{path}&per_page=100&page={page}")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    return [r for r in repos if not r["fork"] and not r["archived"]
            and r["owner"]["login"].lower() == USER.lower()]


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_asset(name, svg):
    with open(os.path.join(ASSETS, name), "w") as f:
        f.write(svg)
