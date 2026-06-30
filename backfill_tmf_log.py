#!/usr/bin/env python3
"""
One-time backfill: fetch all published TMF video titles from the YouTube API
and populate tmf_post_log.json so title_already_published() has full history.

Run via:  python3 backfill_tmf_log.py
Or via workflow_dispatch on tmf-backfill.yml
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
TOKEN_FILE = BASE_DIR / "youtube_token_tmf.json"
LOG_FILE   = BASE_DIR / "tmf_post_log.json"
CHANNEL_ID = "UC0O6KbbHKW4_a7d9epNo93A"
YT_SCOPES  = ["https://www.googleapis.com/auth/youtube",
               "https://www.googleapis.com/auth/youtube.upload"]


def get_credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    if not TOKEN_FILE.exists():
        sys.exit(f"Token file not found: {TOKEN_FILE}")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), YT_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
    if not creds.valid:
        sys.exit("Credentials invalid — re-run OAuth")
    return creds


def fetch_all_titles(youtube) -> list[dict]:
    """Return list of {title, video_id, published_at} for all uploads on the channel."""
    # Get the uploads playlist ID
    ch_resp = youtube.channels().list(
        part="contentDetails",
        id=CHANNEL_ID,
    ).execute()
    if not ch_resp.get("items"):
        sys.exit("Channel not found or token has wrong account")
    uploads_playlist = ch_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"Uploads playlist: {uploads_playlist}")

    videos = []
    page_token = None
    while True:
        kwargs = dict(
            part="snippet",
            playlistId=uploads_playlist,
            maxResults=50,
        )
        if page_token:
            kwargs["pageToken"] = page_token
        resp = youtube.playlistItems().list(**kwargs).execute()
        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            title = snippet.get("title", "").strip()
            vid_id = snippet.get("resourceId", {}).get("videoId", "")
            pub_at = snippet.get("publishedAt", "")[:19].replace("T", " ")
            if title and vid_id:
                videos.append({
                    "channel":   "tmf",
                    "topic":     title,   # best proxy we have
                    "title":     title,
                    "url":       f"https://youtu.be/{vid_id}",
                    "posted_at": pub_at,
                })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    print(f"Fetched {len(videos)} videos from YouTube API")
    return videos


def merge_into_log(new_entries: list[dict]) -> None:
    """Merge fetched entries into tmf_post_log.json without wiping recent entries."""
    existing: dict = {"tmf": [], "posts": []}
    if LOG_FILE.exists():
        try:
            existing = json.loads(LOG_FILE.read_text())
        except Exception:
            pass

    existing_urls = {p.get("url") for p in existing.get("posts", [])}
    added = 0
    for entry in new_entries:
        if entry["url"] not in existing_urls:
            existing.setdefault("posts", []).append(entry)
            existing_urls.add(entry["url"])
            # Also add topic to the tmf list for cycle dedup
            if entry["title"] not in existing.get("tmf", []):
                existing.setdefault("tmf", []).append(entry["title"])
            added += 1

    LOG_FILE.write_text(json.dumps(existing, indent=2))
    print(f"Added {added} new entries. Log now has {len(existing['posts'])} total posts.")


def main():
    print("=== TMF Log Backfill ===")
    from googleapiclient.discovery import build
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)
    entries = fetch_all_titles(youtube)
    merge_into_log(entries)
    print("Done. Commit tmf_post_log.json to persist.")


if __name__ == "__main__":
    main()
