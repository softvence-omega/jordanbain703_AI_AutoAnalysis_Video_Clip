from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import FileResponse
from app.services.upload_video import upload_youtube_video
from app.services.clipper import run_clip_generation
from app.services.get_lang import get_language_code
from app.services.add_template import Add_Template
from app.schema import paramRequest
import asyncio
import requests


# Keep track of pending project_id to future response
pending_clips = {}

router = APIRouter()

@router.post("/generate")
async def handle_generate_clip(
    request: paramRequest
    ):
    
    clip_length_list = [request.clipLength]
    if not (0 <= request.maxClipNumber <= 100):
        return {"error": "clipNumber must be between 0 and 100"}
    if request.templateId:
        # By template_id, fetch aspect_ration, intro, outro, logo, music from database
        template_info = requests.get("")
        aspect_ratio = template_info['aspectRatio']
        logo = template_info['logo_file']
        intro = template_info['intro_file']
        outro = template_info['outro_file']
    else:
        aspect_ratio=1
                
    response = await upload_youtube_video(request.url, request.langCode, clip_length_list, request.maxClipNumber, aspect_ratio)
    print("upload_video response", response)

    if response['code'] == 2000:
        project_id = response['projectId']

        # Create a future and wait for webhook
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        pending_clips[project_id] = future

        try:
            clip_res = await asyncio.wait_for(future, timeout=300.0)
            if request.templateId: 
                clips = Add_Template(clip_res['videos'], aspect_ratio, intro, outro, logo)
                clip_res['videos'] = clips
            return {"status": "done", "clip_number":len(clip_res['videos']), "clips": clip_res['videos']}
        except asyncio.TimeoutError:
            del pending_clips[project_id]
            return {"status": "timeout", "message": "Webhook response took too long."}
    else:
        return {"status": "failed", "reason": response.get("message", "Upload failed")}
    


# webhook router for realtime
@router.post("/webhook/vizard")
async def receive_vizard_webhook(request: Request):
    try:
        data = await request.json()
        print("📩 Vizard Webhook Received:", data)

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
    
@router.get("/supported language")
def get_lang():
    return FileResponse("language.json", media_type="application/json")

@router.get("/supported param")
def get_param():
    return FileResponse("supported_param.json", media_type="application/json")

