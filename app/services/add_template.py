import requests
from app.config import MERGE_DIR, DATA_DIR
from app.services.download_file import Download_File
import subprocess
import os
import shutil
import tempfile
from fastapi import UploadFile

def Add_Template(clip_url, intro_path, outro_path):
    # 1️⃣ Download main clip
    video_path = Download_File(clip_url, DATA_DIR)

    # 3️⃣ Merge using FFmpeg
    final_output = os.path.join(MERGE_DIR, "final_video.mp4")
    cmd = [
        "ffmpeg",
        "-i", intro_path,
        "-i", video_path,
        "-i", outro_path,
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[a]",
        "-map", "1:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac",
        final_output
    ]
    subprocess.run(cmd, check=True)

    os.remove(video_path)
    # os.remove(intro_path)
    # os.remove(outro_path)

    return final_output




