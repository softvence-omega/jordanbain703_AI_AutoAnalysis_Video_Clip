from fastapi import APIRouter, Request
from app.services.upload_video import upload_youtube_video
from app.services.clipper import run_clip_generation
import asyncio

# Keep track of pending project_id to future response
pending_clips = {}

router = APIRouter()

@router.post("/generate")
async def handle_generate_clip(url: str):
    response = await upload_youtube_video(url)
    print("upload_video response", response)

    if response['code'] == 2000:
        project_id = response['projectId']

        # Create a future and wait for webhook
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        pending_clips[project_id] = future

        try:
            await asyncio.wait_for(future, timeout=120.0)  # Wait for webhook notify
            # Now actually call run_clip_generation
            clip_res = await run_clip_generation(project_id)
            print("clip response--------", clip_res)
            return {"status": "done", "clips": clip_res['videos']}
        
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
                future.set_result(True)  # Just notify it's ready
                print(f"📤 Project {project_id} marked ready.")
                del pending_clips[project_id]

            return {"status": "clip generation ready"}

        return {"status": "ignored", "reason": "Invalid code or missing projectId"}
    except Exception as e:
        print("❌ Webhook error:", e)
        return {"status": "failed", "error": str(e)}
