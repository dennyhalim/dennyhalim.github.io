"""Monitor a Facebook profile/page videos tab, download new videos once via yt-dlp
(auto-adapting based on FFmpeg availability), and cross-post to YouTube and Telegram.
"""

import json
import os
import re
import shutil
import subprocess
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from playwright.sync_api import sync_playwright

# --- Configuration ---
TARGET_USERNAME = "100008547796685"
COOKIES_FILE = "cookies.txt"
STATE_FILE = "seen_ids.json"
DOWNLOAD_DIR = Path("downloads")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Resolution settings
YOUTUBE_MAX_HEIGHT = 1080
TELEGRAM_MAX_BYTES = 490 * 1024 * 1024  # 49 MB safety threshold below 50 MB Bot API cap

# YouTube API settings
YOUTUBE_CLIENT_SECRETS = "client_secrets.json"
YOUTUBE_TOKEN_FILE = "youtube_token.json"
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_PRIVACY_STATUS = "private"  # "private", "unlisted", or "public"

# Telegram Bot settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "@your_channel_or_chat_id")


def has_ffmpeg() -> bool:
    """Return True if ffmpeg is available in the system PATH."""
    return shutil.which("ffmpeg") is not None


def load_state(state_path: str) -> dict:
    """Load persisted video upload state from JSON."""
    if Path(state_path).exists():
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state_path: str, state: dict) -> None:
    """Atomically write upload state to JSON."""
    tmp_path = f"{state_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_path, state_path)


def load_netscape_cookies(cookies_txt_path: str) -> list[dict]:
    """Parse a Netscape-format cookies.txt file into Playwright cookie dicts."""
    jar = MozillaCookieJar(cookies_txt_path)
    jar.load(ignore_discard=True, ignore_expires=True)
    playwright_cookies = []
    for c in jar:
        cookie_dict = {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "secure": bool(c.secure),
            "sameSite": "Lax",
        }
        if c.expires:
            cookie_dict["expires"] = int(c.expires)
        playwright_cookies.append(cookie_dict)
    return playwright_cookies


def get_latest_video_id(username: str, cookies_txt: str) -> str | None:
    """Render the Facebook videos tab in Playwright and extract the first video/reel ID."""
    target_url = f"https://www.facebook.com/{username}/videos"
    cookies = load_netscape_cookies(cookies_txt)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        context.add_cookies(cookies)

        page = context.new_page()
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(
            'a[href*="/videos/"], a[href*="/reel/"], a[href*="/watch/"]',
            timeout=20000,
        )

        hrefs = page.eval_on_selector_all(
            'a[href*="/videos/"], a[href*="/reel/"], a[href*="/watch/"]',
            "els => els.map(e => e.href)",
        )
        browser.close()

    for link in hrefs:
        match = re.search(r"(?:/videos/|/reel/|[?&]v=)(\d+)", link)
        if match:
            return match.group(1)
    return None


def download_video(
    video_id: str, cookies_txt: str, max_height: int = 1080, ffmpeg_available: bool = True
) -> tuple[Path, dict]:
    """Download a Facebook video using DASH muxing if FFmpeg exists, else single-file MP4."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    video_url = f"https://www.facebook.com/watch/?v={video_id}"

    if ffmpeg_available:
        output_file = DOWNLOAD_DIR / f"{video_id}_{max_height}p.mp4"
        info_json_path = DOWNLOAD_DIR / f"{video_id}_{max_height}p.info.json"
        format_selector = (
            f"bv*[height<={max_height}][ext=mp4]+ba[ext=m4a]"
            f"/b[height<={max_height}][ext=mp4]/b"
        )
    else:
        print("[Info] FFmpeg not found in PATH; falling back to single-file progressive MP4.")
        output_file = DOWNLOAD_DIR / f"{video_id}_progressive.mp4"
        info_json_path = DOWNLOAD_DIR / f"{video_id}_progressive.info.json"
        format_selector = f"b[height<={max_height}][ext=mp4]/b[ext=mp4]/b"

    cmd = [
        "yt-dlp",
        "--cookies", cookies_txt,
        "--user-agent", USER_AGENT,
        "--concurrent-fragments", "1",
        "--sleep-requests", "2",
        "--socket-timeout", "60",
        "--retries", "5",
        "--fragment-retries", "5",
        "-f", format_selector,
        "--write-info-json",
        "-o", str(output_file),
    ]
    if ffmpeg_available:
        cmd.extend(["--merge-output-format", "mp4"])
    cmd.append(video_url)

    subprocess.run(cmd, check=True)

    metadata = {"title": f"Facebook Video {video_id}", "description": video_url}
    if info_json_path.exists():
        with open(info_json_path, "r", encoding="utf-8") as f:
            raw_info = json.load(f)
        raw_title = (raw_info.get("title") or "").strip()
        raw_desc = (raw_info.get("description") or "").strip()
        metadata["title"] = (raw_title or f"Facebook Video {video_id}")[:100]
        metadata["description"] = f"{raw_desc}\n\nSource: {video_url}".strip()

    return output_file, metadata


def prepare_telegram_video(
    source_path: Path, video_id: str, ffmpeg_available: bool = True
) -> Path:
    """Return source_path if under 49 MB or if FFmpeg is missing; otherwise scale down locally."""
    file_size = source_path.stat().st_size
    if file_size <= TELEGRAM_MAX_BYTES:
        return source_path

    if not ffmpeg_available:
        print(
            f"[Warning] {source_path.name} is {file_size / 1024 / 1024:.1f} MB "
            "and FFmpeg is missing—skipping compression."
        )
        return source_path

    tg_output = DOWNLOAD_DIR / f"{video_id}_tg.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(source_path),
        "-vf", "scale=-2:720",
        "-c:v", "libx264", "-crf", "26", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(tg_output),
    ]
    subprocess.run(cmd, check=True)
    return tg_output


def get_youtube_service():
    """Authenticate with YouTube Data API v3 via OAuth 2.0 and cache refresh token."""
    creds = None
    if Path(YOUTUBE_TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(
            YOUTUBE_TOKEN_FILE, YOUTUBE_SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                YOUTUBE_CLIENT_SECRETS, YOUTUBE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(YOUTUBE_TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(video_path: Path, title: str, description: str) -> str:
    """Upload a video file to YouTube and return the resulting YouTube video ID."""
    youtube = get_youtube_service()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": YOUTUBE_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=4 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    yt_id = response["id"]
    print(f"[YouTube] Uploaded successfully: https://youtu.be/{yt_id}")
    return yt_id


def upload_to_telegram(video_path: Path, caption: str) -> None:
    """Upload an MP4 file to a Telegram channel/chat via Bot API sendVideo."""
    file_size = video_path.stat().st_size
    if file_size > TELEGRAM_MAX_BYTES:
        raise ValueError(
            f"File {video_path.name} ({file_size / 1024 / 1024:.1f} MB) exceeds "
            "standard Telegram Bot API 50 MB limit (install FFmpeg to auto-compress)."
        )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    safe_caption = caption[:1024]

    with open(video_path, "rb") as video_file:
        resp = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": safe_caption,
                "supports_streaming": True,
            },
            files={"video": (video_path.name, video_file, "video/mp4")},
            timeout=300,
        )
    resp.raise_for_status()
    print(f"[Telegram] Sent {video_path.name} to {TELEGRAM_CHAT_ID}")


def cleanup_downloads(video_id: str) -> None:
    """Remove temporary video and info.json files for a completed video ID."""
    for item in DOWNLOAD_DIR.glob(f"{video_id}_*"):
        item.unlink(missing_ok=True)


def run_pipeline() -> None:
    """Check for a new Facebook video, download once, and upload to YouTube & Telegram."""
    ffmpeg_available = has_ffmpeg()
    state = load_state(STATE_FILE)

    vid = get_latest_video_id(TARGET_USERNAME, COOKIES_FILE)
    if not vid:
        print("No video ID found—verify cookies.txt is valid and logged in.")
        return

    entry = state.setdefault(vid, {"youtube": False, "telegram": False, "youtube_id": None})
    if entry["youtube"] and entry["telegram"]:
        print(f"Video {vid} already processed on both YouTube and Telegram.")
        return

    print(f"Processing video ID: {vid} (FFmpeg installed: {ffmpeg_available})")
    source_file, metadata = download_video(
        vid,
        COOKIES_FILE,
        max_height=YOUTUBE_MAX_HEIGHT,
        ffmpeg_available=ffmpeg_available,
    )

    # 1. YouTube Upload
    if not entry["youtube"]:
        yt_id = upload_to_youtube(source_file, metadata["title"], metadata["description"])
        entry["youtube"] = True
        entry["youtube_id"] = yt_id
        save_state(STATE_FILE, state)

    # 2. Telegram Upload
    if not entry["telegram"]:
        tg_file = prepare_telegram_video(source_file, vid, ffmpeg_available=ffmpeg_available)
        caption = f"{metadata['title']}\n\n{metadata['description']}"
        if entry.get("youtube_id"):
            caption += f"\nYouTube: https://youtu.be/{entry['youtube_id']}"
        upload_to_telegram(tg_file, caption)
        entry["telegram"] = True
        save_state(STATE_FILE, state)

    # 3. Clean up local files once both destinations succeed
    if entry["youtube"] and entry["telegram"]:
        cleanup_downloads(vid)
        print(f"Completed and cleaned up temporary files for {vid}.")


if __name__ == "__main__":
    run_pipeline()
