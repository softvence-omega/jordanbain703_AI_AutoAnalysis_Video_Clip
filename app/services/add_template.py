import os
import requests
from app.config import DATA_DIR, MERGE_DIR
from app.services.intro_outro import Add_intro_outro_logo, convert_to_same_format
from app.services.download_file import Download_File

# def download_file(url, save_path):
#     """Download a file from a URL and save it locally."""
#     response = requests.get(url, stream=True)
#     response.raise_for_status()
#     with open(save_path, "wb") as f:
#         for chunk in response.iter_content(chunk_size=8192):
#             f.write(chunk)
#     return save_path

def safe_remove(path):
    """Safely remove a file if it exists."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"Could not delete {path}: {e}")

def Add_Template(clips_info, ratio, intro_url, outro_url, logo_url):
    # Ensure directories exist
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MERGE_DIR, exist_ok=True)

    intro_path = None
    outro_path = None
    logo_path = None
    intro_conv = None
    outro_conv = None

    try:

        # Download files from URLs
        print("Downloading intro video...")
        intro_path = Download_File(intro_url, DATA_DIR)
        print("Downloading outro video...")
        outro_path = Download_File(outro_url, DATA_DIR)
        print("Downloading logo image...")
        logo_path = Download_File(logo_url, DATA_DIR)

        # Parse user-specified ratio
        ratio_parts = ratio.split(":")
        width_ratio = int(ratio_parts[0])
        height_ratio = int(ratio_parts[1])

        # Determine target resolution
        if ratio == "9:16":
            target_width, target_height = 1080, 1920
        elif ratio == "16:9":
            target_width, target_height = 1920, 1080
        elif ratio == "1:1":
            target_width, target_height = 1080, 1080
        elif ratio == "4:3":
            target_width, target_height = 1024, 768
        else:
            target_width = 1080
            target_height = int(target_width * height_ratio / width_ratio)

        print(f"Target resolution: {target_width}x{target_height} ({ratio})")

        # Convert intro and outro to target format
        intro_conv = os.path.join(MERGE_DIR, "intro_conv.mp4")
        outro_conv = os.path.join(MERGE_DIR, "outro_conv.mp4")

        print("Converting intro...")
        convert_to_same_format(intro_path, intro_conv, target_width, target_height)

        print("Converting outro...")
        convert_to_same_format(outro_path, outro_conv, target_width, target_height)

        # Merge intro, outro, and clips
        clips = Add_intro_outro_logo(clips_info, intro_conv, outro_conv, target_width, target_height, logo_path)
        # os.remove(intro_path)
        # os.remove(outro_path)
        # os.remove(logo_path)
        return clips

    except Exception as e:
        print(f"❌ Error occurred: {e}")
        raise e  # still raise error for API to show
    
    finally:
        print("🧹 Cleaning up downloaded & temp files...")

        safe_remove(intro_path)
        safe_remove(outro_path)
        safe_remove(logo_path)
        safe_remove(intro_conv)
        safe_remove(outro_conv)

        print("Cleanup complete.")