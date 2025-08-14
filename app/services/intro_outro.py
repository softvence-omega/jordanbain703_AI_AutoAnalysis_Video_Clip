import os
import subprocess
from app.services.download_file import Download_File
from app.config import DATA_DIR, MERGE_DIR
from app.services.add_logo import AddLogo

def convert_to_same_format(input_path, output_path, target_width, target_height, target_fps=30):
    """
    সব ভিডিওকে same resolution, frame rate এবং audio format এ convert করে।
    Audio sync issue দূর করার জন্য proper audio handling।
    """
    vf_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-r", str(target_fps),        # Force frame rate
        "-vf", vf_filter,
        "-c:a", "aac",                # Audio codec
        "-ar", "44100",               # Sample rate
        "-ac", "2",                   # Stereo channels
        "-b:a", "128k",               # Audio bitrate
        "-movflags", "+faststart",    # Better playback
        output_path
    ]
    subprocess.run(cmd, check=True)
    print(f"Converted: {os.path.basename(input_path)} → {target_width}x{target_height}@{target_fps}fps")

def Add_intro_outro_logo(urls, intro_conv, outro_conv, target_width, target_height, logo_path):

    i=1
    for url in urls:
        # 1️⃣ Download main clip
        main_path = Download_File(url, DATA_DIR)
        print(f"Downloaded main video: {main_path}")

        main_conv = os.path.join(MERGE_DIR, "main_conv.mp4")
        print("Converting main video...")
        convert_to_same_format(main_path, main_conv, target_width, target_height)

        # 5️⃣ Create list file
        list_file = os.path.join(MERGE_DIR, "videos.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            f.write(f"file '{os.path.abspath(intro_conv)}'\n")
            f.write(f"file '{os.path.abspath(main_conv)}'\n")
            f.write(f"file '{os.path.abspath(outro_conv)}'\n")

        # 6️⃣ Merge with re-encoding (safe audio-video sync)
        final_output = os.path.join(MERGE_DIR, f"final_video{i}.mp4")
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-ac", "2",
            final_output
        ]
        subprocess.run(cmd, check=True)
        print(f"Final video created: {final_output}")
        # logo add
        AddLogo(final_output, logo_path, output_path=os.path.join(MERGE_DIR, f"final clip{i}.mp4"))

        os.remove(main_conv)
        os.remove(main_path)
        os.remove(final_output)
        i+=1

        # add cloudinary

    # remove unused file
    os.remove(intro_conv)
    os.remove(outro_conv)
    

    return "successfully added template" # return video urls

