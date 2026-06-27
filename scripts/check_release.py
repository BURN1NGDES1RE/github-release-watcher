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


# =========================
# GitHub API (关键修复)
# =========================
def get_latest_release(repo):
    """
    使用 /releases/latest（最稳定）
    避免 /releases 排序问题
    """
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

        if r.status_code != 200:
            return None

        return r.json()

    except Exception:
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

        # ===== stable identity =====
        release_id = str(release.get("id"))
        tag = release.get("tag_name", "")
        published = release.get("published_at", "")
        url = release.get("html_url", "")
        name = release.get("name") or "Untitled"

        old_id = state.get(repo)

        # 已处理过
        if old_id == release_id:
            continue

        # 是否第一次见到该 repo
        is_first_seen = old_id is None

        # 先写 state（避免重复触发）
        state[repo] = release_id

        # 新 repo 不通知
        if is_first_seen:
            continue

        msg = (
            "🚀 New Release\n\n"
            f"Repo: {repo}\n"
            f"Title: {name}\n"
            f"Version: {tag}\n"
            f"Published: {published}\n\n"
            f"{url}"
        )

        telegram_send(msg)

    save_state(state)


if __name__ == "__main__":
    main()
