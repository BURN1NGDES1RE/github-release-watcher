import json
import os
import time
import re
from pathlib import Path
from datetime import datetime

import requests

WATCHLIST = "watchlist.txt"
STATE_FILE = "data/release_state.json"

TG_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


# =========================
# Telegram
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


# =========================
# Time format (UTC -> CN)
# =========================
def format_time(utc_time):
    try:
        dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return utc_time


# =========================
# Release Notes Parser v6.6
# =========================
def extract_release_notes(body, max_items=6):
    if not body or not body.strip():
        return "No release notes"

    output = []
    count = 0

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower = line.lower()

        # skip noise
        if any(x in lower for x in [
            "contributors",
            "chore:",
            "ci:",
            "merged pull request",
        ]):
            continue

        # skip images
        if line.startswith("![") or "<img" in line:
            continue

        # detect list
        is_list = (
            line.startswith("- ")
            or line.startswith("* ")
            or re.match(r"^\d+\.\s", line)
        )

        if is_list:
            clean = re.sub(r"^(\d+\.|-|\*)\s*", "", line)
            output.append(f"- {clean}")
            count += 1
        else:
            # keep normal text (关键修复点)
            if len(line) > 4:
                output.append(f"- {line}")
                count += 1

        if count >= max_items:
            output.append("... more changes in release page")
            break

    return "\n".join(output) if output else "No release notes"


# =========================
# State
# =========================
def load_state():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


# =========================
# GitHub API
# =========================
def get_latest_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"

    try:
        r = requests.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "release-watcher-v6.6"
            },
            timeout=30,
        )

        if r.status_code != 200:
            return None

        return r.json()

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
        name = release.get("name") or tag
        published = format_time(release.get("published_at", ""))
        url = release.get("html_url", "")
        body = release.get("body", "")

        release_key = f"{tag}@{release.get('id')}"

        old_key = state.get(repo)

        if old_key == release_key:
            continue

        is_first = old_key is None
        state[repo] = release_key

        if is_first:
            continue

        notes = extract_release_notes(body)

        msg = (
            f"{repo} New Release\n\n"
            f"Version: {tag}\n"
            f"Published: {published}\n\n"
            f"Release Notes\n{notes}\n\n"
            f"Release URL\n{url}"
        )

        telegram_send(msg)

    save_state(state)


if __name__ == "__main__":
    main()
