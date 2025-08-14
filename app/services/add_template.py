from app.services.intro_outro import Add_intro_outro
import os
import shutil
from app.config import DATA_DIR,MERGE_DIR
from app.services.intro_outro import Add_intro_outro_logo, convert_to_same_format

def Add_Template(urls, ratio, intro, outro, logo): # for testing, give intro/outro in param
    # from template id, fetch all param like intro , outro
     # Save uploaded files locally
    intro_path = os.path.join(DATA_DIR, intro.filename)
    outro_path = os.path.join(DATA_DIR, outro.filename)
    logo_path = os.path.join(DATA_DIR, logo.filename)

    with open(intro_path, "wb") as f:
        shutil.copyfileobj(intro.file, f)

    with open(outro_path, "wb") as f:
        shutil.copyfileobj(outro.file, f)
    
    with open(logo_path, "wb") as f:
        shutil.copyfileobj(logo.file, f)

    os.makedirs(MERGE_DIR, exist_ok=True)

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
        target_width = 1080
        target_height = int(target_width * height_ratio / width_ratio)

    print(f"Target resolution: {target_width}x{target_height} ({ratio})")

    # 4️⃣ Convert ALL videos
    intro_conv = os.path.join(MERGE_DIR, "intro_conv.mp4")
    outro_conv = os.path.join(MERGE_DIR, "outro_conv.mp4")

    print("Converting intro...")
    convert_to_same_format(intro_path, intro_conv, target_width, target_height)
    
    print("Converting outro...")
    convert_to_same_format(outro_path, outro_conv, target_width, target_height)
    
    Add_intro_outro_logo(urls, intro_conv, outro_conv, target_width, target_height, logo_path)

