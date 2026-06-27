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


def format_time(t):
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return t


def clean(line: str) -> str:
    line = re.sub(r"<[^>]+>", "", line)
    line = re.sub(r"@\w+", "", line)
    line = re.sub(r"\(\s*\)", "", line)
    line = re.sub(r"（\s*）", "", line)
    line = re.sub(r"^(\d+\.|-|\*)\s*", "", line)
    line = re.sub(r"\s{2,}", " ", line).strip()
    return line


def extract(body):
    if not body:
        return "No release notes"

    out = []
    for l in body.splitlines():
        l = clean(l)
        if len(l) < 2:
            continue
        out.append(f"- {l}")
        if len(out) >= 8:
            break

    return "\n".join(out) if out else "No release notes"


def load_state():
    if Path(STATE_FILE).exists():
        return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    return {}


def save_state(s):
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    json.dump(s, open(STATE_FILE, "w", encoding="utf-8"), indent=2)


def get_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases?per_page=1"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return None
    data = r.json()
    return data[0] if data else None


def main():

    state = load_state()

    repos = [x.strip() for x in open(WATCHLIST) if x.strip()]

    for repo in repos:

        r = get_release(repo)
        if not r:
            continue

        tag = r.get("tag_name", "")
        published_raw = r.get("published_at", "")
        published = format_time(published_raw)
        url = r.get("html_url", "")
        body = r.get("body", "")

        # ⭐ FIX: stable key
        release_key = f"{tag}@{published_raw}"

        old = state.get(repo)

        # debug（关键）
        print(f"[DEBUG] {repo} old={old} new={release_key}")

        if old == release_key:
            continue

        state[repo] = release_key

        notes = extract(body)

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
