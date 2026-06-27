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
# Release Notes Cleaner (UI版)
# =========================
def extract_release_notes(body, max_items=6):

    if not body:
        return "No release notes available"

    output = []
    skip_mode = False
    count = 0

    skip_sections = {
        "contributors",
        "distribution notes",
        "chore",
        "ci",
        "build",
        "misc",
        "other"
    }

    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue

        # section header
        if line.startswith("### "):
            section = line.replace("###", "").strip().lower()
            skip_mode = section in skip_sections
            continue

        if skip_mode:
            continue

        # noise filter
        if line.startswith(("![", "<img")):
            continue

        if line.lower().startswith(("chore:", "ci:")):
            continue

        # keep list items only
        if line.startswith(("- ", "* ")):
            output.append(line)
            count += 1

            if count >= max_items:
                output.append("... more changes in release page")
                break

    return "\n".join(output) if output else "No significant changes listed"


# =========================
# GitHub API v5 (稳定版)
# =========================
def get_latest_release(repo):

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "release-watcher-v5.1"
    }

    # 1. latest
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

    # 2. full releases fallback
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/releases",
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                data = [x for x in data if not x.get("draft")]
                data.sort(key=lambda x: x.get("published_at") or "", reverse=True)
                return data[0]
    except:
        pass

    # 3. tags fallback
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/tags",
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            tags = r.json()
            if tags:
                t = tags[0]["name"]
                return {
                    "tag_name": t,
                    "name": t,
                    "html_url": f"https://github.com/{repo}/releases",
                    "published_at": "",
                    "id": t
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
        published = release.get("published_at", "")
        url = release.get("html_url", "")
        body = release.get("body", "")

        release_id = str(release.get("id") or f"{repo}@{tag}")
        old_id = state.get(repo)

        if old_id == release_id:
            continue

        is_first = old_id is None
        state[repo] = release_id

        if is_first:
            continue

        notes = extract_release_notes(body)

        # =========================
        # v5.1 UI（恢复你要的结构）
        # =========================
        msg = (
            "New Release\n\n"
            f"Repo: {repo}\n\n"
            f"Version\n{tag}\n\n"
            f"Published\n{published}\n\n"
            f"Release Notes\n\n{notes}\n\n"
            f"Release URL\n{url}"
        )

        telegram_send(msg)

    save_state(state)


if __name__ == "__main__":
    main()
