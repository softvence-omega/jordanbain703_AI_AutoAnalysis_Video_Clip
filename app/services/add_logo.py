import subprocess
from app.config import MERGE_DIR, DATA_DIR
import os
from PIL import Image

def convert_to_png(input_path, output_path):
    img = Image.open(input_path).convert("RGBA")
    img.save(output_path, format="PNG")
    print(f"Converted to PNG: {output_path}")

def AddLogo(input_path, logo_path, output_path, position="top-right", logo_width=150):
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
        "-i", input_path,
        "-i", png_logo,
        "-filter_complex",
        f"[1:v]scale={logo_width}:-1[logo];[0:v][logo]{overlay_pos}",
        "-c:v", "h264_nvenc",      # GPU encoder
        "-preset", "fast",
        "-cq", "23",
        "-c:a", "copy",
        output_path
    ]

    print("Running FFmpeg safe GPU encode with CPU overlay...")
    try:
        subprocess.run(cmd, check=True)
        print(f"Logo added successfully: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error adding logo: {e}")

    # Remove temporary PNG if created
    if logo_ext != ".png" and os.path.exists(png_logo):
        os.remove(png_logo)

    # """
    # Add logo on video
    # position: top-right, top-left, bottom-right, bottom-left
    # """
    # positions = {
    #     "top-right": "overlay=W-w-10:10",
    #     "top-left": "overlay=10:10",
    #     "bottom-right": "overlay=W-w-10:H-h-10",
    #     "bottom-left": "overlay=10:H-h-10"
    # }
    # overlay_pos = positions.get(position, "overlay=W-w-10:10")

    # # check file is PNG or NOt
    # logo_ext = os.path.splitext(logo_path)[1].lower()
    # if logo_ext != ".png":
    #     png_logo = os.path.join(DATA_DIR, "logo.png")
    #     convert_to_png(logo_path, png_logo)
    # else:
    #     png_logo = logo_path 
    # cmd = [
    #     "ffmpeg",
    #     "-y",
    #     "-i", input_path,
    #     "-i", png_logo,
    #     "-filter_complex",
    #     f"[1:v]scale={logo_width}:-1[logo];[0:v][logo]{overlay_pos}",
    #     "-c:v", "libx264",
    #     "-preset", "fast",
    #     "-crf", "23",
    #     "-c:a", "copy",
    #     output_path
    # ]
    # subprocess.run(cmd, check=True)
    # print(f"Logo added to video: {output_path}")
    # os.remove(png_logo)  # remove temporary png logo file

if __name__ == "__main__":
    input_video = os.path.join("video.mp4")
    output_video = os.path.join("video_with_logo.mp4")
    logo_path = os.path.join("logo.png")  # Supports jpg or png

    add_logo_gpu_safe(input_video, logo_path, output_video, logo_width=150, position="top-right")
