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
# Telegram sender
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
# Clean release notes (核心优化)
# =========================
def extract_release_notes(body, max_items=6):

    if not body:
        return "No release notes available"

    output = []
    skip_mode = False
    count = 0

    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue

        # section filter
        if line.startswith("### "):
            section = line.replace("###", "").strip().lower()
            skip_mode = section in SKIP_SECTIONS
            continue

        if skip_mode:
            continue

        # noise filter
        if line.startswith(("![", "<img")):
            continue

        if line.lower().startswith(("chore:", "ci:")):
            continue

        # only keep list items
        if line.startswith(("- ", "* ")):
            output.append(line)
            count += 1

            if count >= max_items:
                output.append("... more changes in release page")
                break

    return "\n".join(output) if output else "No significant changes listed"


# =========================
# GitHub API
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

        release_id = str(release.get("id"))
        tag = release.get("tag_name", "")
        name = release.get("name") or "Untitled"
        published = release.get("published_at", "")
        url = release.get("html_url", "")
        body = release.get("body", "")

        old_id = state.get(repo)

        if old_id == release_id:
            continue

        is_first_seen = old_id is None

        state[repo] = release_id

        if is_first_seen:
            continue

        notes = extract_release_notes(body)

        msg = (
            f"New Release\n\n"
            f"Repo: {repo}\n"
            f"Version: {tag}\n"
            f"Title: {name}\n"
            f"Published: {published}\n\n"
            f"Release Notes\n"
            f"{notes}\n\n"
            f"Release URL\n"
            f"{url}"
        )

        telegram_send(msg)

    save_state(state)


if __name__ == "__main__":
    main()
