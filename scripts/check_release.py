import json
import os
import time
from pathlib import Path
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
# GitHub API v5 (核心升级)
# =========================
def get_latest_release(repo):

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "release-watcher-v5"
    }

    # -------------------------
    # 1. latest API（最快）
    # -------------------------
    try:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json()
    except:
        pass

    # -------------------------
    # 2. full releases（最可靠）
    # -------------------------
    try:
        url = f"https://api.github.com/repos/{repo}/releases"
        r = requests.get(url, headers=headers, timeout=30)

        if r.status_code == 200:
            data = r.json()

            if not data:
                return None

            # 排除 draft，排序保证最新
            data = [x for x in data if not x.get("draft")]
            data.sort(key=lambda x: x.get("published_at") or "", reverse=True)

            if data:
                return data[0]
    except:
        pass

    # -------------------------
    # 3. tags fallback（兜底）
    # -------------------------
    try:
        url = f"https://api.github.com/repos/{repo}/tags"
        r = requests.get(url, headers=headers, timeout=30)

        if r.status_code == 200:
            tags = r.json()
            if tags:
                return {
                    "tag_name": tags[0]["name"],
                    "name": tags[0]["name"],
                    "html_url": f"https://github.com/{repo}/releases",
                    "published_at": "",
                    "id": tags[0]["name"]
                }
    except:
        pass

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

        tag = release.get("tag_name", "")
        name = release.get("name") or tag
        url = release.get("html_url", "")
        published = release.get("published_at", "")

        # =========================
        # v5：唯一稳定 key
        # =========================
        release_key = release.get("id") or f"{repo}@{tag}"

        old_key = state.get(repo)

        # 已处理
        if old_key == release_key:
            continue

        is_first_seen = old_key is None

        state[repo] = release_key

        # 首次只记录不通知
        if is_first_seen:
            continue

        msg = (
            "New Release\n\n"
            f"Repo: {repo}\n"
            f"Version: {tag}\n"
            f"Title: {name}\n"
            f"Published: {published}\n\n"
            f"{url}"
        )

        telegram_send(msg)

    save_state(state)


if __name__ == "__main__":
    main()
