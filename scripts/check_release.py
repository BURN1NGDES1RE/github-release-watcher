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
        except:
            pass
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
# Release Notes Parser
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

        if line.startswith(("![", "<img")):
            continue

        if line.startswith("###"):
            continue

        # 支持 - / * / + / 1. 2. 3.
        is_item = (
            line.startswith(("-", "*", "+")) or
            re.match(r"^\d+\.\s+", line)
        )

        if not is_item:
            continue

        # 清洗内容
        line = re.sub(r"^\d+\.\s*", "", line)
        line = re.sub(r"\s*By\s+@\w+", "", line)
        line = re.sub(r"\(#\d+\)", "", line)
        line = re.sub(r"\b[0-9a-f]{7,40}\b", "", line)
        line = re.sub(r"\s+", " ", line).strip()

        if not line:
            continue

        lines.append(line)
        count += 1

        if count >= max_items:
            break

    return "\n".join(lines) if lines else "No structured changes detected"


# =========================
# GitHub API
# =========================
def get_latest_release(repo):

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "release-watcher-v6.3"
    }

    # latest
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()
    except:
        pass

    # releases fallback
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/releases",
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            data = [x for x in data if not x.get("draft")]
            data.sort(key=lambda x: x.get("published_at") or "", reverse=True)
            if data:
                return data[0]
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
# Version normalize (你要求的核心修复)
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

        release = get_latest_release(repo)
        if not release:
            continue

        key = build_key(repo, release)
        old = state.get(repo)

        if old == key:
            continue

        is_first = old is None

        state[repo] = key

        if is_first:
            continue

        version = get_version(release)
        published = format_time(release.get("published_at", ""))
        url = release.get("html_url", "")
        body = release.get("body", "")

        notes = extract_release_notes(body)

        msg = (
            f"{repo} New Release\n"
            f"Version: {version}\n"
            f"Published: {published}\n\n"
            f"Release Notes\n"
            f"{notes}\n\n"
            f"Release URL\n"
            f"{url}"
        )

        msg = re.sub(r"\n{3,}", "\n\n", msg).strip()

        telegram_send(msg)

    save_state(state)


if __name__ == "__main__":
    main()
