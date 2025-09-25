import os
import subprocess
from app.services.download_file import Download_File
from app.config import DATA_DIR, MERGE_DIR
from app.services.add_logo import AddLogo
import cloudinary.uploader
from dotenv import load_dotenv
import cloudinary
from app.services.duration_find import get_video_duration_ffmpeg

load_dotenv(override=True)  # <-- this must come before accessing os.getenv()
print("API_KEY:", os.getenv("API_KEY"))

cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET")
)

def convert_to_same_format(input_path, output_path, target_width, target_height, target_fps=30):
    """
    সব ভিডিওকে same resolution, frame rate এবং audio format এ convert করে।
    Audio sync issue দূর করার জন্য proper audio handling।
    """
    vf_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
    
    # cmd = [
    #     "ffmpeg",
    #     "-y",
    #     "-i", input_path,
    #     "-c:v", "libx264",
    #     "-preset", "fast",
    #     "-crf", "23",
    #     "-r", str(target_fps),        # Force frame rate
    #     "-vf", vf_filter,
    #     "-c:a", "aac",                # Audio codec
    #     "-ar", "44100",               # Sample rate
    #     "-ac", "2",                   # Stereo channels
    #     "-b:a", "128k",               # Audio bitrate
    #     "-movflags", "+faststart",    # Better playback
    #     output_path
    # ]
    cmd = [
        "ffmpeg",
        "-y",
        "-hwaccel", "cuda",         # GPU acceleration enable
        "-i", input_path,
        "-c:v", "h264_nvenc",       # NVIDIA GPU encoder (instead of libx264)
        "-preset", "fast",
        "-b:v", "5M",               # bitrate (তুমি চাইলে crf বাদ দিতে পারো)
        "-r", str(target_fps),
        "-vf", vf_filter,
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ]
    subprocess.run(cmd, check=True)
    print(f"Converted: {os.path.basename(input_path)} → {target_width}x{target_height}@{target_fps}fps")

def Add_intro_outro_logo(clips_info, intro_conv, outro_conv, target_width, target_height, logo_path):
    i = 1
    for clip in clips_info:
        print(f"Processing clip {i}")
        print("-"*70)
        main_path = main_conv = list_file = final_output = output_with_logo = None
        try:
            # 1️⃣ Download main clip
            main_path = Download_File(clip['videoUrl'], DATA_DIR)
            print(f"Downloaded main video: {main_path}")

            # 2️⃣ Convert main video
            main_conv = os.path.join(MERGE_DIR, f"main_conv_{i}.mp4")
            print("Converting main video...")
            convert_to_same_format(main_path, main_conv, target_width, target_height)

            # 3️⃣ Prepare list file for concat
            list_file = os.path.join(MERGE_DIR, f"videos_{i}.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                f.write(f"file '{os.path.abspath(intro_conv)}'\n")
                f.write(f"file '{os.path.abspath(main_conv)}'\n")
                f.write(f"file '{os.path.abspath(outro_conv)}'\n")

            # 4️⃣ Merge videos
            final_output = os.path.join(MERGE_DIR, f"final_video_clip_{i}.mp4")
            # cmd = [
            #     "ffmpeg",
            #     "-y",
            #     "-f", "concat",
            #     "-safe", "0",
            #     "-i", list_file,
            #     "-c:v", "libx264",
            #     "-preset", "fast",
            #     "-crf", "23",
            #     "-c:a", "aac",
            #     "-b:a", "128k",
            #     "-ar", "44100",
            #     "-ac", "2",
            #     final_output
            # ]
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c:v", "h264_nvenc",      # GPU encoder
                "-preset", "fast",
                "-cq", "23",               # Quality similar to CRF
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-ac", "2",
                final_output
            ]

            subprocess.run(cmd, check=True)
            print(f"Final video created: {final_output}")

            # 5️⃣ Add logo
            output_with_logo = os.path.join(MERGE_DIR, f"final_clip_with_logo_{i}.mp4")
            AddLogo(final_output, logo_path, output_path=output_with_logo)

            # Find duration
            duration = get_video_duration_ffmpeg(output_with_logo)
            clip['duration'] = duration

            # Upload to Cloudinary
            try:
                response = cloudinary.uploader.upload(
                    output_with_logo,
                    resource_type="video",
                    folder="reels",
                )
                cloud_url = response['secure_url']
                print(f"Uploaded to Cloudinary: {cloud_url}")
                clip['videoUrl'] = cloud_url
            except Exception as e:
                print(f"Cloudinary upload failed for clip {i}: {e}")
                clip['videoUrl'] = None

        except Exception as e:
            print(f"Error processing clip {i}: {e}")
            clip['videoUrl'] = None

        finally:
            # Clean up temporary files safely
            for file in [main_path, main_conv, final_output, output_with_logo, list_file]: 
                if file and os.path.exists(file):
                    try:
                        os.remove(file)
                    except Exception as e:
                        print(f"Failed to delete {file}: {e}")

        i += 1

    # Remove intro/outro after processing all clips
    for file in [intro_conv, outro_conv]:
        if file and os.path.exists(file):
            try:
                os.remove(file)
            except Exception as e:
                print(f"Failed to delete {file}: {e}")

    return clips_info