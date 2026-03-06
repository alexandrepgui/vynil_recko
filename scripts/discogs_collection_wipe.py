"""Back up and delete the authenticated user's entire Discogs collection.

Usage:
    python scripts/discogs_collection_wipe.py              # backup only
    python scripts/discogs_collection_wipe.py --delete      # backup + delete
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import requests

# Load .env from project root
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)

BASE_URL = "https://api.discogs.com"
USER_AGENT = "VynilRecko/1.0"


def _headers():
    token = os.getenv("DISCOGS_TOKEN")
    if not token:
        sys.exit("ERROR: DISCOGS_TOKEN not found in .env")
    return {
        "User-Agent": USER_AGENT,
        "Authorization": f"Discogs token={token}",
    }


def get_username():
    resp = requests.get(f"{BASE_URL}/oauth/identity", headers=_headers())
    resp.raise_for_status()
    return resp.json()["username"]


def fetch_collection(username: str) -> list[dict]:
    """Fetch all releases from the user's collection (all folders)."""
    items = []
    page = 1
    while True:
        resp = requests.get(
            f"{BASE_URL}/users/{username}/collection/folders/0/releases",
            headers=_headers(),
            params={"page": page, "per_page": 100},
        )
        resp.raise_for_status()
        data = resp.json()
        releases = data.get("releases", [])
        if not releases:
            break
        items.extend(releases)
        print(f"  Fetched page {page} ({len(items)} items so far)")
        if page >= data.get("pagination", {}).get("pages", 1):
            break
        page += 1
        time.sleep(1)  # respect rate limits
    return items


def save_backup(items: list[dict], username: str) -> Path:
    backup_dir = Path(__file__).resolve().parent.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = backup_dir / f"discogs_collection_{username}_{timestamp}.json"
    with open(path, "w") as f:
        json.dump(items, f, indent=2)
    return path


def delete_collection(username: str, items: list[dict]):
    """Delete every release from the collection."""
    total = len(items)
    for i, item in enumerate(items, 1):
        release_id = item["id"]
        instance_id = item["instance_id"]
        folder_id = item.get("folder_id", 0)
        resp = requests.delete(
            f"{BASE_URL}/users/{username}/collection/folders/{folder_id}/releases/{release_id}/instances/{instance_id}",
            headers=_headers(),
        )
        if resp.status_code == 204:
            print(f"  Deleted {i}/{total}: {item['basic_information']['title']}")
        else:
            print(f"  FAILED {i}/{total}: {item['basic_information']['title']} (HTTP {resp.status_code})")
        time.sleep(1)  # respect rate limits


def main():
    do_delete = "--delete" in sys.argv

    print("Fetching Discogs identity...")
    username = get_username()
    print(f"Username: {username}")

    print("Fetching collection...")
    items = fetch_collection(username)
    print(f"Total items: {len(items)}")

    if not items:
        print("Collection is empty. Nothing to do.")
        return

    backup_path = save_backup(items, username)
    print(f"Backup saved to: {backup_path}")

    if not do_delete:
        print("Backup complete. Re-run with --delete to delete the collection.")
        return

    confirm = input(f"DELETE all {len(items)} items from {username}'s collection? Type 'yes' to confirm: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        return

    print("Deleting collection...")
    delete_collection(username, items)
    print("Done.")


if __name__ == "__main__":
    main()
