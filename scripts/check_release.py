import json
import os
import time
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests

WATCHLIST = "watchlist.txt"
STATE_FILE = "data/release_state.json"

TG_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


# =========================
# Telegram Sender (stable)
# =========================
def telegram_send(text, retries=3):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    for i in range(retries):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                return True
            print(f"[Telegram] status={r.status_code} retry={i+1}")
        except Exception as e:
            print(f"[Telegram ERROR] {e}")
        time.sleep(2)

    return False


# =========================
# Time format (UTC → UTC+8)
# =========================
def format_time(utc_time):
    try:
        if not utc_time:
            return ""

        dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
        dt = dt.astimezone(timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return utc_time


# =========================
# Release Notes Parser (stable)
# =========================
def extract_release_notes(body, max_items=6):

    if not body:
        return "No structured changes detected"

    lines = []
    count = 0

    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue

        if line.startswith(("![", "<img", "###")):
            continue

        is_item = (
            line.startswith(("-", "*", "+")) or
            re.match(r"^\d+\.\s+", line)
        )

        if not is_item:
            continue

        # clean
        line = re.sub(r"^\d+\.\s*", "", line)
        line = re.sub(r"\s*By\s+@\w+", "", line)
        line = re.sub(r"\(#\d+\)", "", line)
        line = re.sub(r"\b[0-9a-f]{7,40}\b", "", line)
        line = re.sub(r"\s+", " ", line).strip()

        if not line:
            continue

        lines.append(f"- {line}")
        count += 1

        if count >= max_items:
            break

    return "\n".join(lines) if lines else "No structured changes detected"


# =========================
# GitHub API (stable + logs)
# =========================
def get_latest_release(repo):

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "release-watcher-v6.4-stable"
    }

    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[GitHub latest error] {repo}: {e}")

    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/releases",
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            data = [x for x in data if not x.get("draft")]

            data.sort(
                key=lambda x: x.get("published_at") or "",
                reverse=True
            )

            if data:
                return data[0]

    except Exception as e:
        print(f"[GitHub fallback error] {repo}: {e}")

    return None


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
# Version
# =========================
def get_version(release):
    return (
        release.get("name")
        or release.get("tag_name")
        or "unknown"
    )


# =========================
# Key
# =========================
def build_key(repo, release):
    return f"{repo}|{release.get('tag_name','')}|{release.get('published_at','')}"


# =========================
# Main
# =========================
def main():

    state = load_state()

    with open(WATCHLIST, "r", encoding="utf-8") as f:
        repos = [x.strip() for x in f if x.strip()]

    for repo in repos:

        print(f"[CHECK] {repo}")

        release = get_latest_release(repo)
        if not release:
            print(f"[SKIP] no release: {repo}")
            continue

        key = build_key(repo, release)
        old = state.get(repo)

        version = get_version(release)
        published = format_time(release.get("published_at", ""))
        url = release.get("html_url", "")
        body = release.get("body", "")

        is_first = old is None

        # update state FIRST (fix v6.4 bug)
        state[repo] = key

        if old == key:
            print(f"[SKIP] same release: {repo}")
            continue

        # first run only initialize, no notify
        if is_first:
            print(f"[INIT] {repo}")
            continue

        notes = extract_release_notes(body)

        msg = (
            f"<b>{repo}</b>\n\n"
            f"Version: {version}\n"
            f"Published: {published}\n\n"
            f"Release Notes\n"
            f"{notes}\n\n"
            f"Release URL\n"
            f"{url}"
        )

        msg = re.sub(r"\n{3,}", "\n\n", msg).strip()

        ok = telegram_send(msg)

        print(f"[SEND] {repo} success={ok}")

    save_state(state)


if __name__ == "__main__":
    main()
