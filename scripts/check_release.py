import json
import os
import time
from pathlib import Path

import requests

WATCHLIST = "watchlist.txt"
STATE_FILE = "release_state.json"

TG_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

SKIP_SECTIONS = {
    "contributors",
    "distribution notes",
    "chore",
    "ci",
    "build",
    "misc",
    "other"
}


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
# GitHub API (stable)
# =========================
def get_latest_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"

    try:
        r = requests.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "release-watcher-v4"
            },
            timeout=30,
        )

        if r.status_code == 200:
            return r.json()

        # fallback
        url2 = f"https://api.github.com/repos/{repo}/releases"
        r = requests.get(url2, timeout=30)

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

        release_id = str(release.get("id"))
        html_url = release.get("html_url", "")
        tag = release.get("tag_name", "")
        name = release.get("name") or "Untitled"
        published = release.get("published_at", "")

        # ⭐ v4 核心 key
        release_key = release_id

        old_key = state.get(repo)

        # 已处理
        if old_key == release_key:
            continue

        is_first_seen = old_key is None

        # 先写 state（防重复触发）
        state[repo] = release_key

        # 新 repo 不通知
        if is_first_seen:
            continue

        msg = (
            "🚀 New Release\n\n"
            f"Repo: {repo}\n"
            f"Title: {name}\n"
            f"Version: {tag}\n"
            f"Published: {published}\n\n"
            f"{html_url}"
        )

        telegram_send(msg)

    save_state(state)


if __name__ == "__main__":
    main()
