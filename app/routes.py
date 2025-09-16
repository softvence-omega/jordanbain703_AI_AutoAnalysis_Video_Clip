from urllib import response
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import FileResponse
from app.services.filter_clips import filter_clips
from app.services.upload_video import upload_video
from app.services.clipper import run_clip_generation
from app.services.get_lang import get_language_code
from app.services.add_template import Add_Template
from app.services.duration_find import get_youtube_duration, get_drive_duration, get_cloudinary_video_duration
from app.schema import paramRequest
from app.services.store_response import store_in_db
from app.config import BACKEND_URL
import asyncio
import requests
import os
from dotenv import load_dotenv
load_dotenv(override=True)  # <-- this must come before accessing os.getenv()


# Keep track of pending project_id to future response
pending_clips = {}

router = APIRouter()

def convert_aspect_ratio(aspect_ratio_label: str) -> float:
    if aspect_ratio_label == "9:16":
        return 1
    elif aspect_ratio_label == "1:1":
        return 2
    elif aspect_ratio_label == "4:5":
        return 3
    elif aspect_ratio_label == "16:9":
        return 4
    else:
        return 1

@router.post("/generate")
async def handle_generate_clip(
    request: paramRequest
    ):
    print("prompt-----------", request.prompt)
    # Validate parameters
    clip_length_list = [request.clipLength]
    if not (0 <= request.maxClipNumber <= 100):
        return {"error": "clipNumber must be between 0 and 100"}
    if request.templateId:
        # By template_id, fetch aspect_ration, intro, outro, logo, music from database
        headers = {
            "Authorization": f"Bearer {request.auth_token}"
        }
        try:
            template_info = requests.get(f"{BACKEND_URL}/templates/{request.templateId}", headers=headers)
            template_info.raise_for_status()
            template_info = template_info.json()['data']
            print("Template Info:","-"*50, template_info)
        except Exception as e:
            return {"error": f"Failed to fetch template info: {str(e)}"}
        
        aspect_ratio = convert_aspect_ratio(template_info['aspectRatio'])
        logo_url = template_info['overlayLogo']
        intro_url = template_info['introVideo']
        outro_url = template_info['outroVideo']

        # print("Aspect Ratio:", aspect_ratio)
        # print("Intro URL:", intro_url)
        # print("Outro URL:", outro_url)
        # print("Logo URL:", logo_url)
    else:
        aspect_ratio=1
    
    # find out video duration
    print("-----------finding Duration-------------------")
    ext = None
    if request.videoType==1:
        duration_seconds, ext = get_cloudinary_video_duration(request.url)
    elif request.videoType==2:
        duration_seconds = get_youtube_duration(request.url)
    elif request.videoType==3:
        duration_seconds = get_drive_duration(request.url)
    if round(duration_seconds) < 180:
        return {"error": "Video duration must be at least 180 seconds"}
    if round(duration_seconds) > 3600:
        return {"error": "Video duration must be less then 3600 seconds"}
    print("main video duration-----------", round(duration_seconds))

    # Validate supported extension
    supported_exts = ["mp4", "3gp", "avi", "mov"]
    if ext and ext.lower() not in supported_exts:
        raise ValueError(f"Unsupported video file extension: {ext}. Supported: {', '.join(supported_exts)}")
    print('extension-----------', ext)

    # Upload Video to Vizard
    print("----------------uploading video-------------")
    response = upload_video(request.url, video_type=request.videoType, lang=request.langCode, prefer_length=clip_length_list, clip_number=request.maxClipNumber, aspect_ratio=aspect_ratio, ext=ext)

    if response['code'] == 2000:
        project_id = response['projectId']

        # Create a future and wait for webhook
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        pending_clips[project_id] = future

        try:
            clip_res = await asyncio.wait_for(future, timeout=500.0)

            if request.templateId: 
                clips = Add_Template(clip_res['videos'], template_info['aspectRatio'], intro_url, outro_url, logo_url)
                clip_res['videos'] = clips
            print('-'*60)
            print(clip_res['videos'])    
            # filter clips based on prompt
            if request.prompt and request.prompt.strip() != "" and request.prompt.lower() != "string":
                videos = clip_res['videos']
                # Skip filter_clips if the first clip is missing 'transcript'
                if videos and "transcript" in videos[0] and videos[0]["transcript"]:
                    clip_res['videos'] = filter_clips(videos, request.prompt)

            # credit calculate , 1min = 1 credit
            total_duration = sum(clip['duration'] for clip in clip_res['videos'])
            total_credits = total_duration // 60
            print(f"Total Duration: {total_duration} seconds")
            print(f"Total Credits: {total_credits}")
            
            # store in database
            clips_stored_id = store_in_db(request, clip_res["videos"], total_credits, main_video_duration=round(duration_seconds))
            if not clips_stored_id:
                return {"status": "error", "message": "Failed to store clips in database."}

            return {"status": "done", "clip_number":len(clip_res['videos']), "credit_usage": total_credits,"clip_stored_id": clips_stored_id, "clips": clip_res['videos']}
        except asyncio.TimeoutError:
            del pending_clips[project_id]
            return {"status": "timeout", "message": "Webhook response took too long."}
    else:
        return {"status": "failed", "reason": response.get("message", "Upload failed"), "details": response}



# webhook router for realtime
@router.post("/webhook/vizard")
async def receive_vizard_webhook(request: Request):
    try:
        data = await request.json()
        print("📩 Vizard Webhook Received:---------", data)

        project_id = data.get("projectId")
        code = data.get("code")
        print(f"{code} and project id {project_id}")
        if code == 2000 and project_id:
            print("success-----------")
            # Resolve the future if it's waiting
            future = pending_clips.get(project_id)
            if future and not future.done():
                future.set_result(data)  # webhook data direct pass
                del pending_clips[project_id]

            return {"status": "clip generation ready"}

        return {"status": "ignored", "reason": "Invalid code or missing projectId"}
    except Exception as e:
        print("❌ Webhook error:", e)
        return {"status": "failed", "error": str(e)}
    
@router.get("/supported-language")
def get_lang():
    return FileResponse("language.json", media_type="application/json")

@router.get("/supported-param")
def get_param():
    return FileResponse("supported_param.json", media_type="application/json")

