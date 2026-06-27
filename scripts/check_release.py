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
# Telegram
# =========================
def telegram_send(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        r = requests.post(url, json=payload, timeout=30)
        print("[TG] status =", r.status_code, r.text[:100])
        return r.status_code == 200
    except Exception as e:
        print("[TG ERROR]", e)
        return False


# =========================
# Time
# =========================
def format_time(utc_time):
    try:
        dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
        dt = dt.astimezone(timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return utc_time


# =========================
# GitHub
# =========================
def get_latest_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"

    try:
        r = requests.get(url, timeout=30)
        print(f"[GITHUB] {repo} status={r.status_code}")

        if r.status_code == 200:
            return r.json()
        return None

    except Exception as e:
        print("[GITHUB ERROR]", repo, e)
        return None


# =========================
# State
# =========================
def load_state():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
            print("[STATE LOAD]", s)
            return s
    return {}


def save_state(state):
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    print("[STATE SAVE]", state)


# =========================
# Version
# =========================
def get_version(release):
    return release.get("name") or release.get("tag_name") or "unknown"


# =========================
# Key
# =========================
def build_key(repo, release):
    return f"{repo}|{release.get('tag_name','')}|{release.get('published_at','')}"


# =========================
# Main
# =========================
def main():

    print("========== START ==========")

    state = load_state()

    if not Path(WATCHLIST).exists():
        print("[ERROR] watchlist.txt NOT FOUND")
        return

    with open(WATCHLIST, "r", encoding="utf-8") as f:
        repos = [x.strip() for x in f if x.strip()]

    print("[WATCHLIST]", repos)

    if not repos:
        print("[ERROR] repos empty")
        return

    for repo in repos:

        print("\n--------------------------")
        print("[REPO]", repo)

        release = get_latest_release(repo)

        if not release:
            print("[SKIP] no release")
            continue

        version = get_version(release)
        published = format_time(release.get("published_at", ""))
        url = release.get("html_url", "")

        key = build_key(repo, release)
        old = state.get(repo)

        print("[KEY]", key)
        print("[OLD]", old)

        is_first = old is None

        if old == key:
            print("[SKIP] same release")
            continue

        state[repo] = key

        if is_first:
            print("[INIT] first run skip notify")
            continue

        msg = (
            f"<b>{repo}</b>\n\n"
            f"Version: {version}\n"
            f"Published: {published}\n\n"
            f"{url}"
        )

        print("[SEND MSG]\n", msg)

        ok = telegram_send(msg)

        print("[SEND RESULT]", ok)

    save_state(state)

    print("========== END ==========")


if __name__ == "__main__":
    main()
