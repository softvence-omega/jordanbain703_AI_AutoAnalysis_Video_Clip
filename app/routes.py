from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import FileResponse
from app.services.upload_video import upload_youtube_video
from app.services.clipper import run_clip_generation
from app.services.get_lang import get_language_code
from app.services.add_template import Add_intro_outro
from app.schema import paramRequest
import asyncio
import os
import shutil
from app.config import DATA_DIR

# Keep track of pending project_id to future response
pending_clips = {}

router = APIRouter()

@router.post("/generate")
async def handle_generate_clip(
    # request: paramRequest, 
    intro: UploadFile=File('upload intro file'), 
    outro: UploadFile=File('upload intro file')
    ):
    # Save uploaded files locally
    intro_path = os.path.join(DATA_DIR, intro.filename)
    outro_path = os.path.join(DATA_DIR, outro.filename)

    with open(intro_path, "wb") as f:
        shutil.copyfileobj(intro.file, f)

    with open(outro_path, "wb") as f:
        shutil.copyfileobj(outro.file, f)
        
    clip_url='https://cdn-video.vizard.ai/vizard/video/export/20250813/18252567-4fdc6f9649aa44949d66d59a8f507028.mp4?Expires=1755681880&Signature=ro7ZLfXWkthxjfV~Tek0gcnzKvgbzPp~sPpG4e1Ac-uFhuXEXaFuK6rxtMeBAQgg4Kt~7Q-P1rPWa2iZBD3RVyWTwYPSApanEXsIUzokDHc9WCqlkX6lKlMcn9g8khZZckaOCCZGB7ZKX-Ozx-WyjsW9msejph8T6JvytRdAdeQBTzWG02er658j1l~3MdMcC~r0fB6Ure69PTDNnBLZ5qcDBvtCAilpy3KExLapzDgKT6P-c9QsEamwkYEeJaeqjLw2vAViYWe7n9~ObapjXjlAehg6o2qsBHMRkoaqQfkZioJJSHF~dtgnT0s0DJCxefoZJP0sQNgIbtFjriNj0Q__&Key-Pair-Id=K1STSG6HQYFY8F'
    Add_intro_outro(clip_url, intro_path, outro_path)
    
    # clip_length_list = [request.clipLength]
    # if not (0 <= request.maxClipNumber <= 100):
    #     return {"error": "clipNumber must be between 0 and 100"}

    # response = await upload_youtube_video(request.url, request.lang_code, clip_length_list, request.maxClipNumber, request.aspectRatio)
    # print("upload_video response", response)

    # if response['code'] == 2000:
    #     project_id = response['projectId']

    #     # Create a future and wait for webhook
    #     loop = asyncio.get_event_loop()
    #     future = loop.create_future()
    #     pending_clips[project_id] = future

    #     try:
    #         clip_res = await asyncio.wait_for(future, timeout=300.0)
    #         return {"status": "done", "clip_number":len(clip_res['videos']), "clips": clip_res['videos']}
    #     except asyncio.TimeoutError:
    #         del pending_clips[project_id]
    #         return {"status": "timeout", "message": "Webhook response took too long."}
    # else:
    #     return {"status": "failed", "reason": response.get("message", "Upload failed")}
    


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

