import os
import subprocess
import json
from app.config import MERGE_DIR, DATA_DIR
from app.services.download_file import Download_File

def convert_to_same_format(input_path, output_path, target_width, target_height):
    """
    সব ভিডিওকে same resolution এবং audio format এ convert করে।
    Audio sync issue দূর করার জন্য proper audio handling।
    """
    # Padding with black bars to maintain aspect ratio
    vf_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-vf", vf_filter,
        "-c:a", "aac",          # Force audio codec
        "-ar", "44100",         # Sample rate
        "-ac", "2",             # Stereo channels
        "-b:a", "128k",         # Audio bitrate
        "-avoid_negative_ts", "make_zero",  # Audio sync fix
        "-fflags", "+genpts",   # Generate timestamps
        output_path
    ]
    subprocess.run(cmd, check=True)
    print(f"Converted: {os.path.basename(input_path)} → {target_width}x{target_height}")

def Add_intro_outro(clip_url, intro_path, outro_path, ratio='9:16'):
    os.makedirs(MERGE_DIR, exist_ok=True)

    # 1️⃣ Download main clip
    main_path = Download_File(clip_url, DATA_DIR)
    print(f"Downloaded main video: {main_path}")

    # 2️⃣ Parse user specified ratio
    ratio_parts = ratio.split(":")
    width_ratio = int(ratio_parts[0])
    height_ratio = int(ratio_parts[1])
    
    # 3️⃣ Calculate target resolution
    if ratio == "9:16":
        target_width, target_height = 1080, 1920
    elif ratio == "16:9":
        target_width, target_height = 1920, 1080
    elif ratio == "1:1":
        target_width, target_height = 1080, 1080
    elif ratio == "4:3":
        target_width, target_height = 1024, 768
    else:
        # Custom ratio calculation
        target_width = 1080
        target_height = int(target_width * height_ratio / width_ratio)

    print(f"Target resolution: {target_width}x{target_height} ({ratio})")

    # 4️⃣ Convert ALL videos (including main) to same format for proper merging
    intro_conv = os.path.join(MERGE_DIR, "intro_conv.mp4")
    main_conv = os.path.join(MERGE_DIR, "main_conv.mp4")
    outro_conv = os.path.join(MERGE_DIR, "outro_conv.mp4")

    print("Converting intro...")
    convert_to_same_format(intro_path, intro_conv, target_width, target_height)
    
    print("Converting main video...")
    convert_to_same_format(main_path, main_conv, target_width, target_height)
    
    print("Converting outro...")
    convert_to_same_format(outro_path, outro_conv, target_width, target_height)

    # 5️⃣ Create list file
    list_file = os.path.join(MERGE_DIR, "videos.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        f.write(f"file '{os.path.abspath(intro_conv)}'\n")
        f.write(f"file '{os.path.abspath(main_conv)}'\n")
        f.write(f"file '{os.path.abspath(outro_conv)}'\n")

    # 6️⃣ Merge with copy (since all videos now have same format)
    final_output = os.path.join(MERGE_DIR, "final_video.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",  # Now safe to use copy since all formats are same
        final_output
    ]
    subprocess.run(cmd, check=True)
    print(f"Final video created: {final_output}")

    return final_output

if __name__ == "__main__":
    intro_path = os.path.join(DATA_DIR, 'intro.mp4')
    outro_path = os.path.join(DATA_DIR, 'outro.mp4')
    clip_url = "https://cdn-video.vizard.ai/vizard/video/export/20250813/18252571-d423d2bfd3f84898a5e34551343f4762.mp4?Expires=1755681880&Signature=LrMlpm8kH~6k4REIrLnoRwo95gHjviyXIgY6ZF4E7OCpKW9Sa3mjasA5EIjK~GuFpz-Vh8l1Amp9OQtEzX2RHiv6JHCRV1I0pc1UQg8~lL8C3shFsE0dE7VKGywxpLu0hZ~ImT1p2dPZYhTeMMsSi2oaizx6anHFdVuRufRg4dvoYqaKij0nDgtxQQ7V2Sx0m5pw3oOIzYPnfG7Cr-H3sJ1cj2MSdbkLskscfEfMrfQWzTqIqyc6SPDm15~IpWZzleyQHT8ods~BUj8FDnvHqVlpUNUHvNKR-5kXIHgMZSYQGPw-DcdHy3vkhlE-eClnDTa-dTsKYtldznHjRqzUNA__&Key-Pair-Id=K1STSG6HQYFY8F"
    
    try:
        final_video = Add_intro_outro(clip_url, intro_path, outro_path, ratio='9:16')
        print(f"Success! Final video: {final_video}")
        
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e}")
    except Exception as e:
        print(f"Error: {e}")