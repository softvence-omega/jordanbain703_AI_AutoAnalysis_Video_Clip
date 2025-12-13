import subprocess
from app.config import MERGE_DIR, DATA_DIR
import os
from PIL import Image

# Global GPU availability cache
_GPU_AVAILABLE = None

def check_gpu_available():
    """Check if GPU encoding is available"""
    global _GPU_AVAILABLE
    
    if _GPU_AVAILABLE is not None:
        return _GPU_AVAILABLE
    
    try:
        result = subprocess.run(
            ['ffmpeg', '-encoders'],
            capture_output=True,
            text=True,
            timeout=5
        )
        _GPU_AVAILABLE = 'h264_nvenc' in result.stdout
        return _GPU_AVAILABLE
    except:
        _GPU_AVAILABLE = False
        return False


def convert_to_png(input_path, output_path):
    """Convert image to PNG format"""
    img = Image.open(input_path).convert("RGBA")
    img.save(output_path, format="PNG")
    print(f"✅ Converted to PNG: {os.path.basename(output_path)}")


def AddLogo(input_path, logo_path, output_path, position="top-right", logo_width=150):
    """
    Add logo to video with automatic GPU/CPU fallback
    - Tries GPU (h264_nvenc) first
    - Falls back to CPU (libx264) if GPU fails
    """
    
    # Ensure logo is PNG RGBA
    logo_ext = os.path.splitext(logo_path)[1].lower()
    png_logo = None
    
    if logo_ext != ".png":
        png_logo = os.path.join(DATA_DIR, "temp_logo.png")
        convert_to_png(logo_path, png_logo)
        logo_to_use = png_logo
    else:
        logo_to_use = logo_path

    # Overlay position mapping
    positions = {
        "top-right": "overlay=W-w-10:10",
        "top-left": "overlay=10:10",
        "bottom-right": "overlay=W-w-10:H-h-10",
        "bottom-left": "overlay=10:H-h-10"
    }
    overlay_pos = positions.get(position, "overlay=W-w-10:10")

    # Check GPU availability
    use_gpu = check_gpu_available()
    
    if use_gpu:
        # Try GPU encoding first
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-i", logo_to_use,
            "-filter_complex",
            f"[1:v]scale={logo_width}:-1[logo];[0:v][logo]{overlay_pos}",
            "-c:v", "h264_nvenc",
            "-preset", "fast",
            "-cq", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            output_path
        ]
    else:
        # CPU encoding
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-i", logo_to_use,
            "-filter_complex",
            f"[1:v]scale={logo_width}:-1[logo];[0:v][logo]{overlay_pos}",
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
        print(f"🎨 Adding logo using {'GPU (NVENC)' if use_gpu else 'CPU (libx264)'}...")
        result = subprocess.run(
            cmd, 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=300
        )
        print(f"✅ Logo added successfully: {os.path.basename(output_path)}")
        
    except subprocess.CalledProcessError as e:
        # If GPU failed, try CPU fallback
        if use_gpu and ("cuda" in e.stderr.lower() or "nvenc" in e.stderr.lower()):
            print(f"⚠️ GPU logo overlay failed, retrying with CPU...")
            print(f"GPU Error: {e.stderr[:150]}")
            
            # Mark GPU as unavailable
            global _GPU_AVAILABLE
            _GPU_AVAILABLE = False
            
            # Retry with CPU
            cpu_cmd = [
                "ffmpeg",
                "-y",
                "-i", input_path,
                "-i", logo_to_use,
                "-filter_complex",
                f"[1:v]scale={logo_width}:-1[logo];[0:v][logo]{overlay_pos}",
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
                subprocess.run(
                    cpu_cmd, 
                    check=True, 
                    capture_output=True, 
                    text=True,
                    timeout=300
                )
                print(f"✅ Logo added with CPU fallback: {os.path.basename(output_path)}")
            except subprocess.CalledProcessError as cpu_error:
                print(f"❌ CPU logo overlay also failed!")
                print(f"Error: {cpu_error.stderr}")
                raise Exception(f"Logo overlay failed: {cpu_error.stderr}")
        else:
            print(f"❌ Logo overlay failed: {e.stderr}")
            raise Exception(f"Error adding logo: {e}")
    
    except subprocess.TimeoutExpired:
        raise Exception("Logo overlay timed out (>5 minutes)")
    
    finally:
        # Cleanup temporary PNG
        if png_logo and os.path.exists(png_logo):
            try:
                os.remove(png_logo)
                print(f"🗑️ Removed temporary logo: {os.path.basename(png_logo)}")
            except Exception as e:
                print(f"⚠️ Failed to remove temp logo: {e}")


if __name__ == "__main__":
    # Test code
    input_video = "video.mp4"
    output_video = "video_with_logo.mp4"
    logo_path = "logo.png"
    
    AddLogo(input_video, logo_path, output_video, logo_width=150, position="top-right")
