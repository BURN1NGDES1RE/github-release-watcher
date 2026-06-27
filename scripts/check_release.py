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


def format_time(utc_time):
    try:
        dt = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return utc_time


# =========================
# Smart parser v6.7
# =========================
def extract_release_notes(body, max_items=8):
    if not body:
        return "No release notes"

    sections = {
        "feat": [],
        "fix": [],
        "opt": [],
        "other": []
    }

    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue

        line = re.sub(r"@\w+", "", line)  # remove @author

        low = line.lower()

        if any(k in low for k in ["chore:", "ci:", "merged pull request"]):
            continue

        item = re.sub(r"^(\d+\.|-|\*)\s*", "", line)

        if any(k in low for k in ["新增", "feat", "add"]):
            sections["feat"].append(item)
        elif any(k in low for k in ["修复", "fix"]):
            sections["fix"].append(item)
        elif any(k in low for k in ["优化", "optimize", "improve"]):
            sections["opt"].append(item)
        else:
            sections["other"].append(item)

    output = []

    for title, items in sections.items():
        for i in items:
            output.append(f"- {i}")
            if len(output) >= max_items:
                output.append("... more changes in release page")
                return "\n".join(output)

    return "\n".join(output) if output else "No release notes"


def load_state():
    if Path(STATE_FILE).exists():
        return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    return {}


def save_state(state):
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=2)


def get_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    r = requests.get(url, timeout=30)
    return r.json() if r.status_code == 200 else None


def main():
    state = load_state()

    repos = [x.strip() for x in open(WATCHLIST) if x.strip()]

    for repo in repos:
        r = get_release(repo)
        if not r:
            continue

        tag = r.get("tag_name", "")
        rid = str(r.get("id"))
        body = r.get("body", "")
        published = format_time(r.get("published_at", ""))
        url = r.get("html_url", "")

        key = f"{tag}@{rid}"

        if state.get(repo) == key:
            continue

        state[repo] = key

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
