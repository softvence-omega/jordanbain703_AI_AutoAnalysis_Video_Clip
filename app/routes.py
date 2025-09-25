from urllib import response
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from app.services.filter_clips import filter_clips
from app.services.upload_video import upload_video
from app.services.clipper import run_clip_generation
from app.services.get_lang import get_language_code
from app.services.add_template import Add_Template
from app.services.duration_find import get_youtube_duration, get_drive_duration, get_cloudinary_video_duration
from app.schema import paramRequest, CancelResponse
from app.services.store_response import store_in_db
from app.config import BACKEND_URL
import asyncio
import requests
import os
import time
from dotenv import load_dotenv
load_dotenv(override=True)  # <-- this must come before accessing os.getenv()


# Keep track of pending project_id to future response
pending_clips = {}
cancelled_tasks = set()

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

@router.post("/generate", tags=["Video Processing"])
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
    print("Video Duration (seconds):------------", duration_seconds)

    # if round(duration_seconds) < 180:
    #     return {"error": "Video duration must be at least 180 seconds"}
    if round(duration_seconds) > 3600:
        return {"error": "Video duration must be less then 3600 seconds"}
    

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
        print("Project ID:--------", project_id)
        print("Waiting for clip generation...")

        # Create cancellable future
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        pending_clips[project_id] = {
            'future': future,
            'request': request,
            'template_info': template_info if request.templateId else None
        }

        try:
            # Wait for webhook with cancellation support
            clip_res = await asyncio.wait_for(future, timeout=500.0)

            # Check if task was cancelled during processing
            if project_id in cancelled_tasks:
                print(f"Task {project_id} was cancelled, terminating...")
                cancelled_tasks.discard(project_id)
                if project_id in pending_clips:
                    del pending_clips[project_id]
                return {"status": "cancelled", "message": "Task was cancelled by user"}

            # Process clips only if not cancelled
            if request.templateId and project_id not in cancelled_tasks:
                clips = Add_Template(clip_res['videos'], template_info['aspectRatio'], intro_url, outro_url, logo_url)
                clip_res['videos'] = clips
            
            print('-'*60)
            print(clip_res['videos'])    
            
            # Filter clips based on prompt - check cancellation again
            if (request.prompt and request.prompt.strip() != "" and 
                request.prompt.lower() != "string" and project_id not in cancelled_tasks):
                videos = clip_res['videos']
                if videos and "transcript" in videos[0] and videos[0]["transcript"]:
                    clip_res['videos'] = filter_clips(videos, request.prompt)

            # Final cancellation check before storing
            if project_id in cancelled_tasks:
                print(f"Task {project_id} was cancelled before storing, terminating...")
                cancelled_tasks.discard(project_id)
                if project_id in pending_clips:
                    del pending_clips[project_id]
                return {"status": "cancelled", "message": "Task was cancelled by user"}

            # Calculate credits
            total_duration = sum(clip['duration'] for clip in clip_res['videos'])
            total_credits = total_duration // 60
            print(f"Total Duration: {total_duration} seconds")
            print(f"Total Credits: {total_credits}")
            
            # Store in database
            clips_stored_id = store_in_db(request, clip_res["videos"], total_credits, main_video_duration=round(duration_seconds))
            if not clips_stored_id:
                if project_id in pending_clips:
                    del pending_clips[project_id]
                return {"status": "error", "message": "Failed to store clips in database."}

            # Success - cleanup
            if project_id in pending_clips:
                del pending_clips[project_id]

            return {
                "status": "done", 
                "clip_number": len(clip_res['videos']), 
                "credit_usage": total_credits,
                "clip_stored_id": clips_stored_id, 
                "clips": clip_res['videos']
            }
            
        except asyncio.TimeoutError:
            if project_id in pending_clips:
                del pending_clips[project_id]
            return {"status": "timeout", "message": "Webhook response took too long."}
        
        except asyncio.CancelledError:
            print(f"Task {project_id} was cancelled via asyncio")
            if project_id in pending_clips:
                del pending_clips[project_id]
            cancelled_tasks.discard(project_id)
            return {"status": "cancelled", "message": "Task was cancelled by user"}
        
        except Exception as e:
            if project_id in pending_clips:
                del pending_clips[project_id]
            return {"status": "failed", "error": str(e)}
    else:
        return {"status": "failed", "reason": response.get("message", "Upload failed"), "details": response}
    #     project_id = response['projectId']

    #     # Create a future and wait for webhook
    #     loop = asyncio.get_event_loop()
    #     future = loop.create_future()
    #     pending_clips[project_id] = future

    #     try:
    #         clip_res = await asyncio.wait_for(future, timeout=500.0)

    #         if request.templateId: 
    #             clips = Add_Template(clip_res['videos'], template_info['aspectRatio'], intro_url, outro_url, logo_url)
    #             clip_res['videos'] = clips
    #         print('-'*60)
    #         print(clip_res['videos'])    
    #         # filter clips based on prompt
    #         if request.prompt and request.prompt.strip() != "" and request.prompt.lower() != "string":
    #             videos = clip_res['videos']
    #             # Skip filter_clips if the first clip is missing 'transcript'
    #             if videos and "transcript" in videos[0] and videos[0]["transcript"]:
    #                 clip_res['videos'] = filter_clips(videos, request.prompt)

    #         # credit calculate , 1min = 1 credit
    #         total_duration = sum(clip['duration'] for clip in clip_res['videos'])
    #         total_credits = total_duration // 60
    #         print(f"Total Duration: {total_duration} seconds")
    #         print(f"Total Credits: {total_credits}")
            
    #         # store in database
    #         clips_stored_id = store_in_db(request, clip_res["videos"], total_credits, main_video_duration=round(duration_seconds))
    #         if not clips_stored_id:
    #             return {"status": "error", "message": "Failed to store clips in database."}

    #         return {"status": "done", "clip_number":len(clip_res['videos']), "credit_usage": total_credits,"clip_stored_id": clips_stored_id, "clips": clip_res['videos']}
    #     except asyncio.TimeoutError:
    #         del pending_clips[project_id]
    #         return {"status": "timeout", "message": "Webhook response took too long."}
    # else:
    #     return {"status": "failed", "reason": response.get("message", "Upload failed"), "details": response}

# cancel endpoint
@router.post("/cancel/{project_id}", response_model=CancelResponse, tags=["Video Processing"])
async def cancel_task(project_id: int):
    """
    Cancel a running video processing task by project ID
    
    - **project_id**: The project ID returned from generate endpoint
    - **Returns**: Cancellation status and message
    
    Example usage:
    ```
    POST /cancel/12345
    ```
    """
    print("Pending tasks:", pending_clips)
    if project_id not in pending_clips:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
    
    print(f"Cancelling task: {project_id}")

    # Add to cancelled set
    cancelled_tasks.add(project_id)
    
    # Cancel the future immediately
    task_data = pending_clips[project_id]
    future = task_data['future']
    
    if not future.done():
        future.cancel()
    
    # Remove from pending
    del pending_clips[project_id]
    
    return CancelResponse(
        status="cancelled", 
        message=f"Task {project_id} has been cancelled successfully"
    )

# webhook router for realtime
@router.post("/webhook/vizard", tags=["Webhooks"])
async def receive_vizard_webhook(request: Request):
    """
    Receive webhook from Vizard API when video processing is complete
    
    - **Internal endpoint**: Used by Vizard service only
    - **Returns**: Processing status
    """
    try:
        data = await request.json()
        print("📩 Vizard Webhook Received:---------", data)

        project_id = data.get("projectId")
        code = data.get("code")
        print(f"{code} and project id {project_id}")
        
        if code == 2000 and project_id:
            # Check if task was cancelled
            if project_id in cancelled_tasks:
                print(f"Webhook received for cancelled task {project_id}, ignoring...")
                return {"status": "task_was_cancelled"}
            
            # Process webhook if task is still pending
            if project_id in pending_clips:
                print("success-----------")
                future = pending_clips[project_id]['future']
                if not future.done():
                    future.set_result(data)  # webhook data direct pass
                return {"status": "clip generation ready"}
            else:
                print(f"Project {project_id} not found in pending clips")
                return {"status": "project_not_found"}

        return {"status": "ignored", "reason": "Invalid code or missing projectId"}
    except Exception as e:
        print("❌ Webhook error:", e)
        return {"status": "failed", "error": str(e)}
    
# @router.post("/webhook/vizard")
# async def receive_vizard_webhook(request: Request):
#     try:
#         data = await request.json()
#         print("📩 Vizard Webhook Received:---------", data)

#         project_id = data.get("projectId")
#         code = data.get("code")
#         print(f"{code} and project id {project_id}")
#         if code == 2000 and project_id:
#             print("success-----------")
#             # Resolve the future if it's waiting
#             future = pending_clips.get(project_id)
#             if future and not future.done():
#                 future.set_result(data)  # webhook data direct pass
#                 del pending_clips[project_id]

#             return {"status": "clip generation ready"}

#         return {"status": "ignored", "reason": "Invalid code or missing projectId"}
#     except Exception as e:
#         print("❌ Webhook error:", e)
#         return {"status": "failed", "error": str(e)}
    
@router.get("/supported-language")
def get_lang():
    return FileResponse("language.json", media_type="application/json")

@router.get("/supported-param")
def get_param():
    return FileResponse("supported_param.json", media_type="application/json")

