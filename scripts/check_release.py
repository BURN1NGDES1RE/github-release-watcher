import json
import os
import time
from pathlib import Path

import requests

WATCHLIST = "watchlist.txt"
STATE_FILE = "data/release_state.json"

SKIP_SECTIONS = {
    "contributors",
    "distribution notes",
    "chore",
    "ci",
    "build",
    "misc",
    "other"
}

TG_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# =========================
# Telegram Sender
# =========================
def telegram_send(text, retries=3):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    for _ in range(retries):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)

    return False
    
def format_time(utc_time):
    try:
        dt = datetime.fromisoformat(
            utc_time.replace("Z", "+00:00")
        )
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return utc_time

# =========================
# Release Notes Cleaner
# =========================
def extract_release_notes(body, max_items=5):

    if not body:
        return "- No structured release notes"

    output = []
    change_count = 0
    skip_mode = False

    for line in body.splitlines():

        line = line.strip()
        if not line:
            continue

        if line.startswith("### "):
            section = line.replace("###", "").strip().lower()
            skip_mode = section in SKIP_SECTIONS
            if skip_mode:
                continue
            output.append(line)
            continue

        if skip_mode:
            continue

        if line.startswith(("![", "<img")):
            continue

        if line.lower().startswith("chore:"):
            continue

        if line.lower().startswith("ci:"):
            continue

        if line.startswith(("- ", "* ")):
            output.append(line)
            change_count += 1

            if change_count >= max_items:
                output.append("")
                output.append("... (more changes in release page)")
                break

    if not output:
        return "- No structured release notes"

    return "\n".join(output)


# =========================
# State
# =========================
def load_state():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


# =========================
# GitHub API
# =========================
def get_latest_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases"

    try:
        r = requests.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "release-watcher-v2"
            },
            timeout=30,
        )

        if r.status_code != 200:
            return None

        data = r.json()
        if not data:
            return None

        return data[0]

    except Exception:
        return None


# =========================
# Main
# =========================
def main():

    state = load_state()

    with open(WATCHLIST, "r", encoding="utf-8") as f:
        repos = [x.strip() for x in f if x.strip()]

    for repo in repos:

        release = get_latest_release(repo)
        if not release:
            continue

        tag = release.get("tag_name", "")
        published = format_time(
            release.get("published_at", "")
        )
        url = release.get("html_url", "")
        notes = extract_release_notes(
            release.get("body", "")
        )

        release_key = f"{tag}@{published}"
        old_key = state.get(repo)

        is_new_repo = old_key is None

        if old_key == release_key:
            continue

        if is_new_repo:
            state[repo] = release_key
            continue

        msg = (
            "New Release\n\n"
            f"Repo: {repo}\n"
            f"Title: {name}\n"
            f"Version: {tag}\n"
            f"Published: {published}\n\n"
            f"{url}"
        )

        telegram_send(msg)

        state[repo] = release_key

    save_state(state)


if __name__ == "__main__":
    main()
