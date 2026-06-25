import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

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
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )


def format_time(utc_time):
    try:
        dt = datetime.fromisoformat(
            utc_time.replace("Z", "+00:00")
        )
        dt = dt.astimezone(
            timezone(timedelta(hours=8))
        )
        return dt.strftime("%Y-%m-%d %H:%M (UTC+8)")
    except Exception:
        return utc_time


def extract_release_notes(body, max_lines=8):
    if not body:
        return "No release notes provided."

    lines = []

    for line in body.splitlines():
        line = line.strip()

        if not line:
            continue

        if line.startswith("!["):
            continue

        if line.startswith("<img"):
            continue

        if line.lower().startswith("full changelog"):
            continue

        if len(line) > 300:
            continue

        lines.append(line)

        if len(lines) >= max_lines:
            break

    if not lines:
        return "No release notes provided."

    return "\n".join(lines)


def load_state():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)

    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(
            state,
            f,
            indent=2,
            sort_keys=True
        )


def get_latest_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases"

    r = requests.get(
        url,
        timeout=30
    )

    if r.status_code != 200:
        return None

    releases = r.json()

    if not releases:
        return None

    return releases[0]


state = load_state()

first_run = len(state) == 0

with open(WATCHLIST, "r") as f:
    repos = [
        line.strip()
        for line in f
        if line.strip()
    ]

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

        tag = release.get(
            "tag_name",
            ""
        )

        url = release.get(
            "html_url",
            ""
        )

        notes = extract_release_notes(
            release.get(
                "body",
                ""
            )
        )

        published_local = format_time(
            release.get(
                "published_at",
                ""
            )
        )

        msg = (
            f"<b>New Release</b>\n\n"
            f"<code>{repo}</code>\n\n"
            f"<b>Version</b>\n"
            f"{tag}\n\n"
            f"<b>Published</b>\n"
            f"{published_local}\n\n"
            f"<b>Release Notes</b>\n\n"
            f"{notes}\n\n"
            f"<b>Release URL</b>\n"
            f"{url}"
        )

        telegram_send(msg)

save_state(state)
