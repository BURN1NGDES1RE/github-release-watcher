import json
import os
import re
import html
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
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return utc_time


def extract_release_notes(body, max_items=5):
    if not body:
        return "No release notes provided."

    output = []
    change_count = 0

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

        if line.startswith("### "):
            output.append(line)
            continue

        if line.startswith(("- ", "* ")):
            item = line[2:].strip()

            # 删除 PR 编号
            item = re.sub(
                r"\s*\(#\d+\)",
                "",
                item
            )

            # 删除 commit hash
            item = re.sub(
                r"\s*\([a-f0-9]{7,40}\)$",
                "",
                item
            )

            output.append(f"- {item}")

            change_count += 1

            if change_count >= max_items:
                output.append("")
                output.append(
                    "... (more changes in release page)"
                )
                break

    if not output:
        return "No release notes provided."

    return "\n".join(output)


def load_state():
    if Path(STATE_FILE).exists():
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    return {}


def save_state(state):
    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
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
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-release-watcher",
        },
        timeout=30,
    )

    if r.status_code != 200:
        return None

    releases = r.json()

    if not releases:
        return None

    return releases[0]


state = load_state()

first_run = len(state) == 0

with open(
    WATCHLIST,
    "r",
    encoding="utf-8"
) as f:
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

        notes = html.escape(
            extract_release_notes(
                release.get(
                    "body",
                    ""
                )
            )
        )

        repo_display = html.escape(repo)
        tag_display = html.escape(tag)
        url_display = html.escape(url)

        published_local = format_time(
            release.get(
                "published_at",
                ""
            )
        )

        msg = (
            f"<b>New Release</b>\n\n"
            f"<code>{repo_display}</code>\n\n"
            f"<b>Version</b>\n"
            f"{tag_display}\n\n"
            f"<b>Published</b>\n"
            f"{published_local}\n\n"
            f"<b>Release Notes</b>\n\n"
            f"{notes}\n\n"
            f"<b>Release URL</b>\n"
            f"{url_display}"
        )

        telegram_send(msg)

save_state(state)
