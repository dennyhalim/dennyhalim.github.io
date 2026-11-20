#!/usr/bin/env python3
"""
FB -> Download -> Upload to YouTube -> Send to Telegram
Usage:
    python fb_to_yt.py nike --download --upload --telegram

    python fb_to_yt.py nike --download --upload --telegram \
        --telegram-token 123456:ABC --telegram-chat -1001234567890

    # Env vars work too (for GitHub Actions):
    export TELEGRAM_BOT_TOKEN=123456:ABC
    export TELEGRAM_CHAT_ID=-1001234567890

Requirements:
    pip install curl_cffi yt-dlp google-api-python-client google-auth-oauthlib requests
"""

import argparse
import http.cookiejar
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from curl_cffi import requests as cffi_requests
import requests as py_requests
import yt_dlp

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET = "client_secret.json"
TOKEN_FILE = "token.json"

# Jakarta time for date stamp - change to your tz
TZ = timezone(timedelta(hours=7))  # WIB

# ================= FACEBOOK =================

def load_cookies(cookies_file: str) -> dict:
    path = Path(cookies_file)
    if not path.exists():
        print(f"[!] {cookies_file} not found")
        sys.exit(1)
    cj = http.cookiejar.MozillaCookieJar(cookies_file)
    cj.load(ignore_discard=True, ignore_expires=True)
    cookies = {c.name: c.value for c in cj}
    #if "c_user" not in cookies:
    #    print("[!] No c_user - re-export cookies.txt")
    #    sys.exit(1)
    #print(f"[*] Loaded {len(cookies)} FB cookies")
    return cookies

def extract_ids(html: str) -> list[str]:
    patterns = [r'/videos/(\d{6,})', r'/reel/(\d{6,})', r'/watch/\?v=(\d{6,})', r'"video_id":"(\d{6,})"']
    ids = []
    for pat in patterns:
        ids.extend(re.findall(pat, html))
    seen, unique = set(), []
    for vid in ids:
        if vid not in seen:
            seen.add(vid)
            unique.append(vid)
    return unique

def get_video_ids(username: str, cookies: dict, impersonate: str) -> list[str]:
    session = cffi_requests.Session(impersonate=impersonate)
    session.headers.update({"Accept-Language": "en-US,en;q=0.9"})
    for url in [f"https://www.facebook.com/{username}/videos", f"https://mbasic.facebook.com/{username}/videos"]:
        try:
            print(f"[*] GET {url}")
            r = session.get(url, cookies=cookies, impersonate=impersonate, timeout=30)
            if r.status_code != 200 or "login" in r.url.lower():
                continue
            ids = extract_ids(r.text)
            if ids:
                print(f"[+] Found {len(ids)} videos")
                return ids
        except Exception as e:
            print(f"[!] {e}")
    return []

def download_progressive(video_id: str, username: str, cookies_file: str, impersonate: str, quality: int, out_dir: str):
    video_url = f"https://www.facebook.com/{username}/videos/{video_id}"
    watch_url = f"https://www.facebook.com/watch/?v={video_id}"
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        'format': f'b[height<={quality}][ext=mp4]/b[height<={quality}]/b/best',
        'outtmpl': str(out_path / '%(id)s_%(title)s.%(ext)s'),
        'cookiefile': cookies_file,
        #'impersonate': impersonate,
        'noplaylist': True,
        'quiet': False,
        'retries': 3,
    }
    print(f"\n[*] Downloading progressive max {quality}p...")
    for url in [video_url, watch_url]:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info
        except Exception as e:
            print(f"[!] Failed {url}: {e}")
    return None, {}

# ================= YOUTUBE =================

def get_youtube_service():
    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        Path(TOKEN_FILE).write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def upload_to_youtube(file_path: str, title: str, description: str, tags: list[str], privacy: str, category: str):
    youtube = get_youtube_service()
    body = {
        "snippet": {"title": title, "description": description, "tags": tags, "categoryId": category},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[*] YouTube upload {int(status.progress()*100)}%")
    vid = response.get("id")
    print(f"[+] Uploaded! https://youtu.be/{vid}")
    return vid

# ================= TELEGRAM =================

def send_telegram(token: str, chat_id: str, text: str, video_path: str | None = None, send_video: bool = False):
    """Send to group/channel. chat_id = -100xxx for group, @channelusername for channel"""
    if not token or not chat_id:
        print("[!] Telegram token/chat_id missing, skipping")
        return False

    base = f"https://api.telegram.org/bot{token}"

    # 1. Send video file itself (if under 50MB, good for channel)
    if send_video and video_path and Path(video_path).exists():
        size_mb = Path(video_path).stat().st_size / 1024 / 1024
        if size_mb <= 50:
            print(f"[*] Sending video to Telegram ({size_mb:.1f} MB)...")
            with open(video_path, "rb") as f:
                r = py_requests.post(
                    f"{base}/sendVideo",
                    data={"chat_id": chat_id, "caption": text, "parse_mode": "HTML", "supports_streaming": True},
                    files={"video": f},
                    timeout=120,
                )
            print(f"[*] Telegram sendVideo: {r.status_code} - {r.text[:200]}")
            return r.status_code == 200
        else:
            print(f"[*] Video {size_mb:.1f} MB > 50MB, sending link instead")

    # 2. Send text message with links (always works)
    print(f"[*] Sending Telegram message to {chat_id}...")
    r = py_requests.post(
        f"{base}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False},
        timeout=30,
    )
    print(f"[*] Telegram sendMessage: {r.status_code} - {r.text[:300]}")
    return r.status_code == 200

def make_date_stamp(fmt: str) -> str:
    """fmt examples: %Y-%m-%d, %d %b %Y, %Y/%m/%d"""
    return datetime.now(TZ).strftime(fmt)

# ================= MAIN =================

def main():
    p = argparse.ArgumentParser()
    p.add_argument("username", nargs="?", help="FB Page username")
    p.add_argument("--cookies", default="cookies.txt")
    p.add_argument("--impersonate", default="chrome")
    p.add_argument("--quality", type=int, default=720)
    p.add_argument("--out", default="downloads")
    p.add_argument("--download", action="store_true")
    p.add_argument("--upload", action="store_true")
    p.add_argument("--file", help="Upload this file directly, skip FB")
    p.add_argument("--title", help="Base title, date stamp added automatically")
    p.add_argument("--description", default="")
    p.add_argument("--tags", default="facebook,viral")
    p.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    p.add_argument("--category", default="22")

    # Date stamp
    p.add_argument("--no-date", action="store_true", help="Don't add date to title")
    p.add_argument("--date-format", default="%Y-%m-%d", help="strftime format, default %%Y-%%m-%%d")
    p.add_argument("--date-position", default="prefix", choices=["prefix", "suffix"], help="Where to put date")

    # Telegram
    p.add_argument("--telegram", action="store_true", help="Send to Telegram")
    p.add_argument("--telegram-token", default=os.getenv("TELEGRAM_BOT_TOKEN", ""), help="Bot token or env TELEGRAM_BOT_TOKEN")
    p.add_argument("--telegram-chat", default=os.getenv("TELEGRAM_CHAT_ID", ""), help="Chat ID or env TELEGRAM_CHAT_ID")
    p.add_argument("--telegram-send-video", action="store_true", help="Send video file, not just link. Max 50MB")
    p.add_argument("--auth-only", action="store_true")
    args = p.parse_args()

    if args.auth_only:
        get_youtube_service()
        print("[+] token.json created")
        return

    if not args.username and not args.file:
        p.print_help()
        sys.exit(1)

    # --- Build date stamp ---
    date_stamp = "" if args.no_date else make_date_stamp(args.date_format)
    print(f"[*] Date stamp: {date_stamp}")

    def apply_date(base: str) -> str:
        if not date_stamp:
            return base[:100]
        if args.date_position == "prefix":
            titled = f"[{date_stamp}] {base}"
        else:
            titled = f"{base} | {date_stamp}"
        return titled[:100]  # YouTube limit

    # --- Mode: local file ---
    if args.file:
        title = apply_date(args.title or Path(args.file).stem)
        yt_id = None
        if args.upload:
            yt_id = upload_to_youtube(args.file, title, args.description, [t.strip() for t in args.tags.split(",")], args.privacy, args.category)
        if args.telegram:
            msg = f"🎬 <b>{title}</b>\n\n"
            if yt_id:
                msg += f"▶️ YouTube: https://youtu.be/{yt_id}\n"
            msg += f"📅 {date_stamp}"
            send_telegram(args.telegram_token, args.telegram_chat, msg, args.file, args.telegram_send_video)
        return

    # --- Mode: FB -> YT -> Telegram ---
    cookies = load_cookies(args.cookies)
    ids = get_video_ids(args.username, cookies, args.impersonate)
    if not ids:
        print("[!] No videos found")
        sys.exit(1)

    latest = ids[0]
    fb_url = f"https://www.facebook.com/{args.username}/videos/{latest}"
    print(f"\n=== FB Latest ===\nID: {latest}\nURL: {fb_url}")
    Path("latest_id.txt").write_text(latest)

    if not args.download and not args.upload:
        print("[*] Use --download --upload --telegram")
        return

    filename, info = download_progressive(latest, args.username, args.cookies, args.impersonate, args.quality, args.out)
    if not filename:
        sys.exit(1)

    # Title with date stamp
    fb_title = info.get("title") or f"Video {latest}"
    base_title = args.title or fb_title
    yt_title = apply_date(base_title)
    yt_desc = args.description or f"Original: {fb_url}\n\n{info.get('description','')[:4000]}"

    yt_id = None
    if args.upload:
        yt_id = upload_to_youtube(filename, yt_title, yt_desc, [t.strip() for t in args.tags.split(",") if t.strip()], args.privacy, args.category)

    # Telegram - always send even if upload failed, so you know
    if args.telegram:
        msg = f"🎬 <b>{yt_title}</b>\n\n"
        if yt_id:
            msg += f"▶️ YouTube: https://youtu.be/{yt_id}\n"
        msg += f"📘 Facebook: {fb_url}\n"
        msg += f"📅 {date_stamp}\n"
        msg += f"🆔 FB ID: <code>{latest}</code>"
        send_telegram(args.telegram_token, args.telegram_chat, msg, filename, args.telegram_send_video)

    print(f"\n=== DONE ===\nTitle: {yt_title}\nFile: {filename}\nYT: https://youtu.be/{yt_id if yt_id else 'N/A'}")

if __name__ == "__main__":
    main()
