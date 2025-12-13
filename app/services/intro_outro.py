import os
import subprocess
from app.services.download_file import Download_File
from app.config import DATA_DIR, MERGE_DIR
from app.services.add_logo import AddLogo
import cloudinary.uploader
from dotenv import load_dotenv
import cloudinary
from app.services.duration_find import get_video_duration_ffmpeg

load_dotenv(override=True)
print("API_KEY:", os.getenv("API_KEY"))

cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET")
)

# Global GPU flag
GPU_AVAILABLE = None

def verify_audio_stream_simple(file_path):
    """Simple audio verification"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'a:0',
             '-show_entries', 'stream=codec_name',
             '-of', 'default=noprint_wrappers=1:nokey=1',
             file_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            print(f"  🔊 Audio: {result.stdout.strip()}")
            return True
        else:
            print(f"  ⚠️ NO AUDIO!")
            return False
    except Exception as e:
        print(f"  ⚠️ Audio check failed: {e}")
        return False

def check_gpu_availability():
    """Check if NVIDIA GPU and CUDA are available"""
    global GPU_AVAILABLE
    
    if GPU_AVAILABLE is not None:
        return GPU_AVAILABLE
    
    try:
        result = subprocess.run(
            ['ffmpeg', '-encoders'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if 'h264_nvenc' in result.stdout:
            print("✅ GPU encoding available (NVENC)")
            GPU_AVAILABLE = True
            return True
        else:
            print("⚠️ NVENC not found, using CPU encoding")
            GPU_AVAILABLE = False
            return False
            
    except Exception as e:
        print(f"⚠️ GPU check failed: {e}, using CPU")
        GPU_AVAILABLE = False
        return False


def verify_video_file(file_path):
    """Verify that video file is valid and playable"""
    if not os.path.exists(file_path):
        return False, "File does not exist"
    
    if os.path.getsize(file_path) < 1000:
        return False, "File too small (possibly corrupted)"
    
    try:
        # Quick validation using ffprobe
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 
             'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
             file_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return True, "Valid"
        else:
            return False, f"Invalid format: {result.stderr[:100]}"
            
    except Exception as e:
        return False, f"Validation error: {e}"


def convert_to_same_format(input_path, output_path, target_width, target_height, target_fps=30):
    """
    Convert video to standard format with GPU/CPU fallback
    """
    # Verify input file first
    is_valid, msg = verify_video_file(input_path)
    if not is_valid:
        raise Exception(f"Invalid input video: {msg}")
    
    vf_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
    
    use_gpu = check_gpu_availability()
    
    if use_gpu:
        cmd = [
            "ffmpeg", "-y",
            "-hwaccel", "cuda",
            "-i", input_path,
            "-c:v", "h264_nvenc",
            "-preset", "fast",
            "-b:v", "5M",
            "-r", str(target_fps),
            "-vf", vf_filter,
            "-c:a", "aac",
            "-ar", "44100",
            "-ac", "2",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-r", str(target_fps),
            "-vf", vf_filter,
            "-c:a", "aac",
            "-ar", "44100",
            "-ac", "2",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]
    
    try:
        result = subprocess.run(
            cmd, 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=300
        )
        
        # Verify output file
        is_valid, msg = verify_video_file(output_path)
        if not is_valid:
            raise Exception(f"Output validation failed: {msg}")
        
        encoder = "GPU (NVENC)" if use_gpu else "CPU (libx264)"
        print(f"✅ Converted ({encoder}): {os.path.basename(input_path)} → {target_width}x{target_height}@{target_fps}fps")
        
    except subprocess.CalledProcessError as e:
        if use_gpu and ("cuda" in e.stderr.lower() or "nvenc" in e.stderr.lower()):
            print(f"⚠️ GPU encoding failed, retrying with CPU...")
            
            global GPU_AVAILABLE
            GPU_AVAILABLE = False
            
            cpu_cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-r", str(target_fps),
                "-vf", vf_filter,
                "-c:a", "aac",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_path
            ]
            subprocess.run(cpu_cmd, check=True, capture_output=True, text=True, timeout=300)
            print(f"✅ Converted (CPU fallback): {os.path.basename(input_path)}")
        else:
            raise

def add_silent_audio_if_missing(input_path, output_path):
    """
    Check if video has audio, if not add silent audio track
    This allows proper merging with videos that have audio
    """
    # Check if audio exists
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'a:0',
             '-show_entries', 'stream=codec_name',
             '-of', 'default=noprint_wrappers=1:nokey=1',
             input_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        has_audio = result.returncode == 0 and result.stdout.strip()
        
        if has_audio:
            print(f"  ✅ Audio exists, copying file...")
            # Just copy the file
            import shutil
            shutil.copy2(input_path, output_path)
            return
        
        print(f"  ⚠️ No audio found, adding silent audio...")
        
    except Exception as e:
        print(f"  ⚠️ Audio check failed, adding silent audio anyway...")
    
    # Add silent audio track
    use_gpu = check_gpu_availability()
    
    if use_gpu:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "copy",              # Copy video (no re-encode)
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            "-shortest",                  # Match video duration
            output_path
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            "-shortest",
            output_path
        ]
    
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        print(f"  ✅ Silent audio added: {os.path.basename(output_path)}")
        
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Failed to add silent audio: {e.stderr[:200]}")
        raise


def prepare_intro_outro_with_audio(intro_path, outro_path, output_dir):
    """
    Prepare intro and outro videos by ensuring they have audio tracks
    Returns paths to the prepared videos
    """
    print(f"\n{'='*70}")
    print("Preparing Intro/Outro with Audio Tracks")
    print('='*70)
    
    # Prepare intro
    intro_with_audio = os.path.join(output_dir, "intro_with_audio.mp4")
    print(f"\n📹 Processing Intro:")
    add_silent_audio_if_missing(intro_path, intro_with_audio)
    verify_audio_stream_simple(intro_with_audio)
    
    # Prepare outro
    outro_with_audio = os.path.join(output_dir, "outro_with_audio.mp4")
    print(f"\n📹 Processing Outro:")
    add_silent_audio_if_missing(outro_path, outro_with_audio)
    verify_audio_stream_simple(outro_with_audio)
    
    print(f"\n✅ Intro/Outro prepared with audio tracks")
    print('='*70)
    
    return intro_with_audio, outro_with_audio

def merge_videos_concat(list_file, output_path):
    """
    Simple concat merge - works when all videos have audio streams
    """
    use_gpu = check_gpu_availability()
    
    if use_gpu:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c:v", "h264_nvenc",
            "-preset", "fast",
            "-b:v", "5M",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            output_path
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            output_path
        ]
    
    try:
        result = subprocess.run(
            cmd, 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=300
        )
        
        encoder = "GPU" if use_gpu else "CPU"
        print(f"✅ Merged videos ({encoder}): {os.path.basename(output_path)}")
        
    except subprocess.CalledProcessError as e:
        if use_gpu and ("cuda" in e.stderr.lower() or "nvenc" in e.stderr.lower()):
            print(f"⚠️ GPU merge failed, retrying with CPU...")
            
            global GPU_AVAILABLE
            GPU_AVAILABLE = False
            
            cpu_cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "44100",
                "-ac", "2",
                output_path
            ]
            subprocess.run(cpu_cmd, check=True, capture_output=True, text=True, timeout=300)
            print(f"✅ Merged videos (CPU fallback): {os.path.basename(output_path)}")
        else:
            print(f"❌ Merge error: {e.stderr}")
            raise


def Add_intro_outro_logo(clips_info, intro_conv, outro_conv, target_width, target_height, logo_path):
    """Process clips with intro, outro, and logo"""
    
    # ✨ NEW: Prepare intro/outro with silent audio if needed
    intro_with_audio, outro_with_audio = prepare_intro_outro_with_audio(
        intro_conv, 
        outro_conv, 
        MERGE_DIR
    )
    
    i = 1
    successful_clips = 0
    
    for clip in clips_info:
        print(f"\n{'='*70}")
        print(f"Processing clip {i}/{len(clips_info)}")
        print('='*70)
        
        main_path = main_conv = list_file = final_output = output_with_logo = None
        
        try:
            # 1️⃣ Download main clip
            print(f"📥 Downloading clip {i}...")
            main_path = Download_File(clip['videoUrl'], DATA_DIR)
            
            is_valid, msg = verify_video_file(main_path)
            if not is_valid:
                raise Exception(f"Downloaded file invalid: {msg}")
            
            print(f"✅ Downloaded: {os.path.basename(main_path)}")
            print("🔍 Checking downloaded file audio...")
            verify_audio_stream_simple(main_path)

            # 2️⃣ Convert main video
            main_conv = os.path.join(MERGE_DIR, f"main_conv_{i}.mp4")
            print("🔄 Converting main video...")
            convert_to_same_format(main_path, main_conv, target_width, target_height)
            
            print("🔍 Checking converted file audio...")
            verify_audio_stream_simple(main_conv)

            # 3️⃣ Prepare concat list (using videos with audio)
            list_file = os.path.join(MERGE_DIR, f"videos_{i}.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                f.write(f"file '{os.path.abspath(intro_with_audio)}'\n")
                f.write(f"file '{os.path.abspath(main_conv)}'\n")
                f.write(f"file '{os.path.abspath(outro_with_audio)}'\n")
            print(f"📝 Created concat list")

            # 4️⃣ Merge videos
            final_output = os.path.join(MERGE_DIR, f"final_video_clip_{i}.mp4")
            print("🎬 Merging intro + main + outro...")
            merge_videos_concat(list_file, final_output)
            
            print("🔍 Checking merged file audio...")
            verify_audio_stream_simple(final_output)

            # 5️⃣ Add logo
            output_with_logo = os.path.join(MERGE_DIR, f"final_clip_with_logo_{i}.mp4")
            print("🎨 Adding logo overlay...")
            AddLogo(final_output, logo_path, output_path=output_with_logo)
            
            print("🔍 Checking final file audio...")
            if not verify_audio_stream_simple(output_with_logo):
                print("❌❌❌ FINAL VIDEO HAS NO AUDIO! ❌❌❌")
            
            is_valid, msg = verify_video_file(output_with_logo)
            if not is_valid:
                raise Exception(f"Final video validation failed: {msg}")

            # 6️⃣ Get duration
            try:
                duration = get_video_duration_ffmpeg(output_with_logo)
                clip['duration'] = duration
                print(f"⏱️ Duration: {duration}s")
            except Exception as e:
                print(f"⚠️ Could not get duration: {e}, using default")
                clip['duration'] = 0

            # 7️⃣ Upload to Cloudinary
            try:
                print("☁️ Uploading to Cloudinary...")
                response = cloudinary.uploader.upload(
                    output_with_logo,
                    resource_type="video",
                    folder="reels",
                    timeout=300
                )
                cloud_url = response['secure_url']
                print(f"✅ Uploaded: {cloud_url[:50]}...")
                clip['videoUrl'] = cloud_url
                successful_clips += 1
                
            except Exception as e:
                print(f"❌ Cloudinary upload failed: {e}")
                clip['videoUrl'] = None

        except Exception as e:
            print(f"❌ Error processing clip {i}: {e}")
            import traceback
            traceback.print_exc()
            clip['videoUrl'] = None

        finally:
            # Cleanup (keep intro_with_audio and outro_with_audio for next clips)
            print("🧹 Cleaning up...")
            for file in [main_path, main_conv, final_output, output_with_logo, list_file]:
                if file and os.path.exists(file):
                    try:
                        os.remove(file)
                        print(f"  🗑️ Deleted: {os.path.basename(file)}")
                    except Exception as e:
                        print(f"  ⚠️ Delete failed: {e}")

        i += 1
    
    # Final cleanup - delete intro/outro with audio
    print("\n🧹 Final cleanup...")
    for file in [intro_with_audio, outro_with_audio]:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"  🗑️ Deleted: {os.path.basename(file)}")
            except:
                pass
    
    print(f"\n{'='*70}")
    print(f"✅ Processing complete: {successful_clips}/{len(clips_info)} clips successful")
    print('='*70)
    
    return clips_info
