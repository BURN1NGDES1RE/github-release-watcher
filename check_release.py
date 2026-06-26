import json
import os
import time
from pathlib import Path
from datetime import datetime

import requests

WATCHLIST = "watchlist.txt"
STATE_FILE = "release_state.json"

TG_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# =========================
# Telegram Sender (safe + retry)
# =========================
def telegram_send(text, retries=3):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    for i in range(retries):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                return True
        except Exception:
            pass

        time.sleep(2)

    return False


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
        published = release.get("published_at", "")
        url = release.get("html_url", "")
        name = release.get("name") or "Untitled"

        # ⭐ 稳定唯一 key（核心）
        release_key = f"{tag}@{published}"

        old_key = state.get(repo)

        # 已处理过
        if old_key == release_key:
            continue

        # =========================
        # 只有真正新 release 才通知
        # =========================
        if old_key is not None:

            msg = (
                "New Release\n\n"
                f"Repo: {repo}\n"
                f"Title: {name}\n"
                f"Version: {tag}\n"
                f"Published: {published}\n\n"
                f"{url}"
            )

            telegram_send(msg)

        # =========================
        # 最后再写 state（关键）
        # =========================
        state[repo] = release_key

    save_state(state)


if __name__ == "__main__":
    main()
