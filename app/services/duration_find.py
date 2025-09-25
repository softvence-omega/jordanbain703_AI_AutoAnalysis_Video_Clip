import yt_dlp
import requests
import gdown
import subprocess
import os
import re

SUPPORTED_EXTENSIONS = {"mp4", "3gp", "avi", "mov"}

#Find out Duration from youtube
import json
import sys

def get_youtube_duration(url):
    try:
        # Step 0: Update yt-dlp to latest version
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], check=True)
        
        # Step 1: Extract info using yt-dlp with Android client
        result = subprocess.run(
            [
                "yt-dlp",
                "--extractor-args", "youtube:player_client=android",
                "-J",          # JSON output
                "--skip-download",
                url
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("yt-dlp error:", result.stderr)
            return None

        # Step 2: Parse JSON
        info = json.loads(result.stdout)
        duration = info.get("duration")

        if duration is None:
            print("⚠️ Duration not available (SABR-only / restricted video)")
            return None

        return duration  # in seconds

    except subprocess.CalledProcessError as e:
        print("Subprocess error:", e)
        return None
    except json.JSONDecodeError as e:
        print("JSON decode error:", e)
        return None
    except Exception as e:
        print("Unexpected error:", e)
        return None

# Example usage
# url = "https://www.youtube.com/watch?v=v4t0E3S1N1k"
# duration_seconds = get_youtube_duration(url)
# print("Video Duration (seconds):", duration_seconds)

#Find out Duration from google Drive
def extract_drive_file_id(url):
    pattern = r"/file/d/([a-zA-Z0-9_-]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Invalid Google Drive URL")

def download_drive_video(url, save_dir="./downloads"):
    os.makedirs(save_dir, exist_ok=True)
    file_id = extract_drive_file_id(url)
    download_url = f"https://drive.google.com/uc?id={file_id}"
    local_path = os.path.join(save_dir, f"{file_id}.mp4")

    output = gdown.download(download_url, local_path, quiet=False)
    if output is None:
        raise Exception(f"Cannot access or download the file: {url}")
    return local_path

def get_video_duration_ffmpeg(video_path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of",
         "default=noprint_wrappers=1:nokey=1", video_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    return float(result.stdout)

def get_drive_duration(url, save_dir="./downloads"):
    local_path = download_drive_video(url, save_dir)

    try:
        duration_seconds = get_video_duration_ffmpeg(local_path)
        print("Duration (seconds):", duration_seconds)
        return duration_seconds
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

# --------------------
# Example usage
# url = "https://drive.google.com/file/d/18Nbc8pNYVk7pzILnspqzzC9UL879-l7l/view?usp=sharing"
# url = "https://drive.google.com/file/d/18Nbc8pNYVk7pzILnspqzzC9UL879-l7l/view?usp=sharing"
# duration_sec = get_drive_duration(url)
# print("Duration (seconds):", duration_sec)

#Find out Duration from Cloudinary

import os
from urllib.parse import urlparse

def get_extension_from_url(url: str) -> str:
    ext = os.path.splitext(url.split("?")[0])[1].lower().replace(".", "")
    if ext not in SUPPORTED_EXTENSIONS:
        raise Exception(f"Unsupported video extension: {ext}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}")
    return ext

def get_cloudinary_video_duration(url, temp_dir="./downloads"):
    os.makedirs(temp_dir, exist_ok=True)
    local_path = os.path.join(temp_dir, "temp_video.mp4")
    
    # Download video
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise Exception("Cannot access Cloudinary video URL")
    with open(local_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    
    # Get duration using ffprobe
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of",
         "default=noprint_wrappers=1:nokey=1", local_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    try:
        duration_sec = float(result.stdout)
    except ValueError:
        raise Exception("Unable to determine video duration")
    
    # Cleanup
    os.remove(local_path)

    # Validate extension
    ext = get_extension_from_url(url)
    
    return duration_sec, ext

# url = "https://res.cloudinary.com/dbnf4vmma/video/upload/v1756114583/reels/ftkgfhryump8re3nvkci.mp4"
# res, ext = get_cloudinary_video_duration(url)
# print("Duration (seconds):", res)
# print("File extension:", ext)