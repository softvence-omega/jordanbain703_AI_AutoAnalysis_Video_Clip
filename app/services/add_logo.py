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
    ভিডিওতে logo বসায়।
    position: top-right, top-left, bottom-right, bottom-left
    """
    positions = {
        "top-right": "overlay=W-w-10:10",
        "top-left": "overlay=10:10",
        "bottom-right": "overlay=W-w-10:H-h-10",
        "bottom-left": "overlay=10:H-h-10"
    }
    overlay_pos = positions.get(position, "overlay=W-w-10:10")

    # চেক করব PNG কিনা
    logo_ext = os.path.splitext(logo_path)[1].lower()
    if logo_ext != ".png":
        png_logo = os.path.join(DATA_DIR, "logo.png")
        convert_to_png(logo_path, png_logo)
    else:
        png_logo = logo_path  # আগে থেকেই PNG হলে কনভার্সন লাগবে না

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-i", png_logo,
        "-filter_complex",
        f"[1:v]scale={logo_width}:-1[logo];[0:v][logo]{overlay_pos}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "copy",
        output_path
    ]
    subprocess.run(cmd, check=True)
    print(f"Logo added to video: {output_path}")

if __name__=="__main__":
    input_path = os.path.join(MERGE_DIR, 'final_video1.mp4')
    output_path = os.path.join(MERGE_DIR, 'final_with_logo.mp4')
    logo_path = os.path.join(DATA_DIR, 'logo.png')

    AddLogo(input_path, logo_path, output_path, logo_width=150)
