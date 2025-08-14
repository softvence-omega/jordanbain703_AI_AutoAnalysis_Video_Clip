from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import FileResponse
from app.services.upload_video import upload_youtube_video
from app.services.clipper import run_clip_generation
from app.services.get_lang import get_language_code
from app.services.add_template import Add_Template
from app.schema import paramRequest
import asyncio
import os


# Keep track of pending project_id to future response
pending_clips = {}

router = APIRouter()

@router.post("/generate")
async def handle_generate_clip(
    request: paramRequest, 
    intro: UploadFile=File('upload intro file'), 
    outro: UploadFile=File('upload intro file'),
    logo: UploadFile=File('upload a logo')
    ):
    
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

    clip_urls=['https://cdn-video.vizard.ai/vizard/video/export/20250813/18252567-4fdc6f9649aa44949d66d59a8f507028.mp4?Expires=1755681880&Signature=ro7ZLfXWkthxjfV~Tek0gcnzKvgbzPp~sPpG4e1Ac-uFhuXEXaFuK6rxtMeBAQgg4Kt~7Q-P1rPWa2iZBD3RVyWTwYPSApanEXsIUzokDHc9WCqlkX6lKlMcn9g8khZZckaOCCZGB7ZKX-Ozx-WyjsW9msejph8T6JvytRdAdeQBTzWG02er658j1l~3MdMcC~r0fB6Ure69PTDNnBLZ5qcDBvtCAilpy3KExLapzDgKT6P-c9QsEamwkYEeJaeqjLw2vAViYWe7n9~ObapjXjlAehg6o2qsBHMRkoaqQfkZioJJSHF~dtgnT0s0DJCxefoZJP0sQNgIbtFjriNj0Q__&Key-Pair-Id=K1STSG6HQYFY8F',
              'https://cdn-video.vizard.ai/vizard/video/export/20250813/18252570-ac3c4ae6248a4cd783b3584d006b1490.mp4?Expires=1755681880&Signature=BkPBeMSAwDO7Wbzzxf4Cakp~9YyLQ1f73XDzIS68iQvcjNOJA2ub2QrgRa6bnfZdSusSZ3LojYIvEvsj8gyNfa~sZ9hm57Zfa2NkRafiztjyh92GgGv2Y1lX834fcnxyUkb60IEDvWrcw3JM2Im0AKZpJtGPfyHN1ncQ95WlhDoas76FRT8up9DWk6iZSZaLsRUExUHxU-uokb~h-MjLHgzc3Tf-noUEp-9tGoq0qVCLG6-Tlejd-HpmzepsvwzLFW6XcU6QurwxbZYudc7BdASY~wfnwqYBYBbMFtbnzDbTdnp24LERei4pJtLWXIZhcCerzTQ~QG8bKMfxx3JqYg__&Key-Pair-Id=K1STSG6HQYFY8F',
              'https://cdn-video.vizard.ai/vizard/video/export/20250813/18252569-5c5bcb5982c9428184388e7dd6b5ea62.mp4?Expires=1755681880&Signature=fFGIOaU45U0WXxapBCMd1yKdHLePkjhuwaneyOUPNpYD8SndEzKxY~MCzSIVKp13IkKefFMQgH-CUWWA7-3S9oxsfMW993LCncJARVi1kIAyabW51L736n~LH5GjE5id7Q1Al6MqW42zLIpmkHF3~~FxC4tb-b0cxBfDr6RldMGsdK-UIqXitWLwNZqWgsWAWVFK5ZGURPUpxhcJ7IRiK~X38Tpi1efmDIAUr7~tIxKDTJYgUXnfBpJEAu9pv-chjqkK6UaV4qLvDzDfRO9YVrRGKSJeYtjhFLvrgctI0hxaIJDE2mV4V-15cQUG5L9phEiTls7REr-nptlyjNYrQA__&Key-Pair-Id=K1STSG6HQYFY8F'
    ]
    
    Add_Template(clip_urls, request.aspectRatio, intro, outro, logo)
    


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

