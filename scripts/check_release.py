import json
import os
import re
import time
from pathlib import Path
from datetime import datetime
import requests

WATCHLIST = "watchlist.txt"
STATE_FILE = "data/release_state.json"

TG_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


# =========================
# Telegram sender
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
# Time format
# =========================
def format_time(utc_time):
    try:
        dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return utc_time


# =========================
# Clean line (v6.9.2 핵心)
# =========================
def clean_line(line: str) -> str:

    # remove HTML tags
    line = re.sub(r"<[^>]+>", "", line)

    # remove @username
    line = re.sub(r"@\w+", "", line)

    # remove empty parentheses (normal + Chinese)
    line = re.sub(r"\(\s*\)", "", line)
    line = re.sub(r"（\s*）", "", line)

    # remove leading list markers
    line = re.sub(r"^(\d+\.|-|\*)\s*", "", line)

    # collapse spaces
    line = re.sub(r"\s{2,}", " ", line).strip()

    return line


# =========================
# Release notes parser
# =========================
def extract_release_notes(body, max_items=8):

    if not body:
        return "No release notes"

    output = []
    count = 0

    for raw in body.splitlines():

        line = clean_line(raw)

        if not line:
            continue

        low = line.lower()

        # skip noise sections
        if any(x in low for x in [
            "contributors",
            "sponsors",
            "github actions",
        ]):
            continue

        if len(line) < 2:
            continue

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
        return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    return {}


def save_state(state):
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=2, sort_keys=True)


# =========================
# GitHub API
# =========================
def get_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    r = requests.get(url, timeout=30)
    return r.json() if r.status_code == 200 else None


# =========================
# Main
# =========================
def main():

    state = load_state()

    repos = [x.strip() for x in open(WATCHLIST) if x.strip()]

    for repo in repos:

        release = get_release(repo)
        if not release:
            continue

        tag = release.get("tag_name", "")
        body = release.get("body", "")
        url = release.get("html_url", "")
        published = format_time(release.get("published_at", ""))

        release_key = f"{tag}@{release.get('id')}"

        old = state.get(repo)

        if old == release_key:
            continue

        state[repo] = release_key

        notes = extract_release_notes(body)

        msg = (
            f"{repo}\n\n"
            f"Version: {tag}\n"
            f"Published: {published}\n\n"
            f"Release Notes\n{notes}\n\n"
            f"Release Page\n{url}"
        )

        telegram_send(msg)

    save_state(state)


if __name__ == "__main__":
    main()
