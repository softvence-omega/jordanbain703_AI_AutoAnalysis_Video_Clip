
import subprocess
import os
from PIL import Image
from app.config import MERGE_DIR, DATA_DIR

def convert_to_png(input_logo, output_logo):
    """Convert any image to PNG RGBA format for safe overlay compatibility"""
    img = Image.open(input_logo).convert("RGBA")
    img.save(output_logo)
    print(f"Converted logo to PNG RGBA: {output_logo}")

def add_logo_gpu_safe(input_video, logo_path, output_video, logo_width=150, position="top-right"):
    """
    Add logo to a video using CPU overlay + GPU encode.
    - overlay filters run on CPU for compatibility
    - encoding runs on GPU (h264_nvenc) for speed
    """
    # Ensure logo is PNG RGBA
    logo_ext = os.path.splitext(logo_path)[1].lower()
    if logo_ext != ".png":
        png_logo = os.path.join(DATA_DIR, "temp_logo.png")
        convert_to_png(logo_path, png_logo)
    else:
        png_logo = logo_path

    # Overlay position mapping
    positions = {
        "top-right": "overlay=W-w-10:10",
        "top-left": "overlay=10:10",
        "bottom-right": "overlay=W-w-10:H-h-10",
        "bottom-left": "overlay=10:H-h-10"
    }
    overlay_pos = positions.get(position, "overlay=W-w-10:10")

    # FFmpeg command: CPU overlay, GPU encode
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_video,
        "-i", png_logo,
        "-filter_complex",
        f"[1:v]scale={logo_width}:-1[logo];[0:v][logo]{overlay_pos}",
        "-c:v", "h264_nvenc",      # GPU encoder
        "-preset", "fast",
        "-cq", "23",
        "-c:a", "copy",
        output_video
    ]

    print("Running FFmpeg safe GPU encode with CPU overlay...")
    try:
        subprocess.run(cmd, check=True)
        print(f"Logo added successfully: {output_video}")
    except subprocess.CalledProcessError as e:
        print(f"Error adding logo: {e}")

    # Remove temporary PNG if created
    if logo_ext != ".png" and os.path.exists(png_logo):
        os.remove(png_logo)

if __name__ == "__main__":
    input_video = os.path.join("video.mp4")
    output_video = os.path.join("video_with_logo.mp4")
    logo_path = os.path.join("logo.png")  # Supports jpg or png

    add_logo_gpu_safe(input_video, logo_path, output_video, logo_width=150, position="top-right")
