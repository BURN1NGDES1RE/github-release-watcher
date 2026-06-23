
import json
import os
from pathlib import Path

import requests

WATCHLIST = "watchlist.txt"
STATE_FILE = "release_state.json"

TG_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


def telegram_send(text):
    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )


def load_state():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_latest_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases"

    r = requests.get(url, timeout=30)

    if r.status_code != 200:
        return None

    releases = r.json()

    if not releases:
        return None

    return releases[0]


state = load_state()

first_run = len(state) == 0

with open(WATCHLIST, "r") as f:
    repos = [line.strip() for line in f if line.strip()]

for repo in repos:

    release = get_latest_release(repo)

    if not release:
        continue

    release_id = str(release["id"])

    if repo not in state:
        state[repo] = release_id
        continue

    if state[repo] == release_id:
        continue

    state[repo] = release_id

    if not first_run:

        name = release.get("name") or "Untitled"

        tag = release.get("tag_name", "")

        published = release.get("published_at", "")

        url = release.get("html_url", "")

        msg = (
            f"🚀 New Release\n\n"
            f"Repo: {repo}\n"
            f"Title: {name}\n"
            f"Version: {tag}\n"
            f"Published: {published}\n\n"
            f"{url}"
        )

        telegram_send(msg)

save_state(state)
