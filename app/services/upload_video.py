import requests
from app.config import VIZARD_API_KEY

def upload_video(video_url, video_type, lang, prefer_length, clip_number, aspect_ratio, ext=None):
    """
    Upload video to Vizard API from multiple sources
    
    Args:
        video_url (str): URL or path to the video
        video_type (int): Type of video source
            1 - Remote video files (direct URL to video file)
            2 - YouTube 
            3 - Google Drive
            4 - Vimeo
            5 - StreamYard
        lang (str): Language code (default: "en")
        prefer_length (list): Preferred length settings (default: [0])
    
    Returns:
        dict: API response
    """
    
    # Validate video type
    if video_type not in [1, 2, 3, 4, 5]:
        raise ValueError("video_type must be 1 (Remote), 2 (YouTube), 3 (Google Drive), 4 (Vimeo), or 5 (StreamYard)")
    
    headers = {
        "Content-Type": "application/json",
        "VIZARDAI_API_KEY": VIZARD_API_KEY
    }
    
    data = {
        "lang": lang,
        "preferLength": prefer_length,
        "ratioOfClip": aspect_ratio,
        "maxClipNumber": clip_number,
        "videoUrl": video_url,
        "videoType": video_type,
        "includeTranscript": True,
        "contentAnalysis": True,
        "ext": ext
    }
    print("data-----------", data)
    try:
        response = requests.post(
            "https://elb-api.vizard.ai/hvizard-server-front/open-api/v1/project/create",
            headers=headers,
            json=data
        )
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"Error uploading video: {e}")
        return {
            "code": 5000,
            "message": "Upload failed",
            "details": str(e)
        }

# Example usage functions for each video type

def upload_remote_video(video_url, lang="en"):
    """Upload from remote video file URL"""
    return upload_video(video_url, video_type=1, lang=lang)

async def upload_youtube_video(youtube_url, lang, clipLength, clipNumber, aspectRatio):
    """Upload from YouTube URL"""
    return upload_video(youtube_url, video_type=2, lang=lang, prefer_length=clipLength, clip_number=clipNumber, aspect_ratio=aspectRatio)

def upload_google_drive_video(drive_url, lang="en"):
    """Upload from Google Drive URL"""
    return upload_video(drive_url, video_type=3, lang=lang)

def upload_vimeo_video(vimeo_url, lang="en"):
    """Upload from Vimeo URL"""
    return upload_video(vimeo_url, video_type=4, lang=lang)

def upload_streamyard_video(streamyard_url, lang="en"):
    """Upload from StreamYard URL"""
    return upload_video(streamyard_url, video_type=5, lang=lang)

# Example usage:
if __name__ == "__main__":
    # YouTube example
    result = upload_youtube_video("https://www.youtube.com/watch?v=OqLfw-TzzfI")
    print("YouTube upload result:", result) # return project ID
    
    # Google Drive example
    # result = upload_google_drive_video("https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/view")
    # print("Google Drive upload result:", result)
    