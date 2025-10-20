from urllib import response
from fastapi import APIRouter, Request, UploadFile, File, WebSocket, WebSocketDisconnect
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
import httpx
import os
import json
from dotenv import load_dotenv
load_dotenv(override=True)

# Track active WebSocket connections by project_id
# Structure: {project_id: websocket}
active_connections = {}
pending_clips = {}

router = APIRouter()

def convert_aspect_ratio(aspect_ratio_label: str) -> float:
    """Convert aspect ratio label to numeric value"""
    aspect_ratio_map = {
        "9:16": 1,
        "1:1": 2,
        "4:5": 3,
        "16:9": 4
    }
    return aspect_ratio_map.get(aspect_ratio_label, 1)


async def fetch_template_info(template_id: str, auth_token: str) -> dict:
    """Async function to fetch template information"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{BACKEND_URL}/templates/{template_id}", 
                headers=headers
            )
            response.raise_for_status()
            return response.json()['data']
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to fetch template info: {str(e)}")


async def get_video_extension(url: str, video_type: int):
    """Async wrapper for getting video extension from Cloudinary"""
    if video_type == 1:  # Cloudinary only
        _, ext = await asyncio.to_thread(
            get_cloudinary_video_duration, url
        )
        return ext
    return None


def validate_extension(ext: str) -> bool:
    """Validate video file extension"""
    if not ext:
        return True
    supported_exts = ["mp4", "3gp", "avi", "mov"]
    return ext.lower() in supported_exts


async def send_message_to_client(project_id: str, message: dict):
    """Send message to connected WebSocket client"""
    if project_id in active_connections:
        websocket = active_connections[project_id]
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Failed to send message to {project_id}: {str(e)}")
            # Remove disconnected client
            active_connections.pop(project_id, None)


async def process_clip_generation_in_background(
    project_id: str, 
    future, 
    request: paramRequest, 
    template_info,
    intro_url,
    outro_url,
    logo_url
):
    """
    Background task to process clip generation
    Runs independently without blocking the REST API response
    """
    try:
        # Wait for webhook response with timeout
        clip_res = await asyncio.wait_for(future, timeout=500.0)
        
        # Send processing update
        await send_message_to_client(project_id, {
            "status": "processing",
            "message": "Applying template and filtering clips..."
        })
        
        # Apply template if exists
        if request.templateId and template_info:
            clips = await asyncio.to_thread(
                Add_Template,
                clip_res['videos'],
                template_info['aspectRatio'],
                intro_url,
                outro_url,
                logo_url
            )
            clip_res['videos'] = clips
        
        # Filter clips based on prompt
        if request.prompt and request.prompt.strip() and request.prompt.lower() != "string":
            videos = clip_res['videos']
            if videos and "transcript" in videos[0] and videos[0]["transcript"]:
                clip_res['videos'] = await asyncio.to_thread(
                    filter_clips,
                    videos,
                    request.prompt
                )
        
        # Calculate credits (1min = 1 credit)
        total_duration = sum(clip['duration'] for clip in clip_res['videos'])
        total_credits = total_duration // 60
        print(f"Total Duration: {total_duration} seconds")
        print(f"Total Credits: {total_credits}")
        
        # Send database storage update
        await send_message_to_client(project_id, {
            "status": "processing",
            "message": "Saving clips to database..."
        })
        
        # Store in database
        clips_stored_id = await asyncio.to_thread(
            store_in_db,
            request,
            clip_res["videos"],
            total_credits,
            main_video_duration=0
        )
        
        if not clips_stored_id:
            await send_message_to_client(project_id, {
                "status": "error",
                "message": "Failed to store clips in database."
            })
            return
        
        # Send final success message
        await send_message_to_client(project_id, {
            "status": "done",
            "message": "Clip generation completed successfully!",
            "clip_number": len(clip_res['videos']),
            "credit_usage": total_credits,
            "clip_stored_id": clips_stored_id,
            "clips": clip_res['videos']
        })
        
    except asyncio.TimeoutError:
        pending_clips.pop(project_id, None)
        await send_message_to_client(project_id, {
            "status": "timeout",
            "message": "Webhook response took too long."
        })
    except Exception as e:
        print(f"❌ Error in background processing: {str(e)}")
        await send_message_to_client(project_id, {
            "status": "error",
            "message": f"Processing error: {str(e)}"
        })
    finally:
        # Cleanup
        pending_clips.pop(project_id, None)


@router.websocket("/ws/clip-generation/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """
    WebSocket endpoint for real-time clip generation updates
    """
    await websocket.accept()
    active_connections[project_id] = websocket
    print(f"✅ WebSocket connected for project_id: {project_id}")
    
    try:
        # Send connection confirmation
        await websocket.send_json({
            "status": "connected",
            "message": "Connected to clip generation stream"
        })
        
        # Keep connection alive and wait for messages
        while True:
            # This will block until a message is received or connection is closed
            data = await websocket.receive_text()
            
    except WebSocketDisconnect:
        print(f"❌ WebSocket disconnected for project_id: {project_id}")
        active_connections.pop(project_id, None)
    except Exception as e:
        print(f"❌ WebSocket error for {project_id}: {str(e)}")
        active_connections.pop(project_id, None)


@router.post("/generate", response_model=dict)
async def handle_generate_clip(request: paramRequest):
    """
    Main endpoint for generating video clips with WebSocket support
    """
    print("prompt-----------", request.prompt)
    
    # Validate parameters
    clip_length_list = [request.clipLength]
    if not (0 <= request.maxClipNumber <= 100):
        return {"error": "clipNumber must be between 0 and 100"}
    
    # Initialize default values
    aspect_ratio = 1
    logo_url = None
    intro_url = None
    outro_url = None
    template_info = None
    ext = None
    
    try:
        # Parallel execution: Fetch template info and extension check
        tasks = []
        
        if request.templateId:
            tasks.append(fetch_template_info(request.templateId, request.auth_token))
        else:
            tasks.append(asyncio.sleep(0))
        
        if request.videoType == 1:
            tasks.append(get_video_extension(request.url, request.videoType))
        else:
            tasks.append(asyncio.sleep(0))
        
        if request.templateId or request.videoType == 1:
            print("-----------Fetching template info and/or extension in parallel-------------------")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            if request.templateId:
                if isinstance(results[0], Exception):
                    return {"error": f"Failed to fetch template info: {str(results[0])}"}
                
                template_info = results[0]
                print("Template Info:", "-"*50, template_info)
                
                aspect_ratio = convert_aspect_ratio(template_info['aspectRatio'])
                logo_url = template_info.get('overlayLogo')
                intro_url = template_info.get('introVideo')
                outro_url = template_info.get('outroVideo')
            
            if request.videoType == 1:
                if isinstance(results[1], Exception):
                    return {"error": f"Failed to get video extension: {str(results[1])}"}
                ext = results[1]
        
        if ext and not validate_extension(ext):
            supported_exts = ["mp4", "3gp", "avi", "mov"]
            return {"error": f"Unsupported video file extension: {ext}. Supported: {', '.join(supported_exts)}"}
        
        print('extension-----------', ext)
        
        # Upload Video to Vizard
        print("----------------uploading video-------------")
        response = await asyncio.to_thread(
            upload_video,
            request.url,
            video_type=request.videoType,
            lang=request.langCode,
            prefer_length=clip_length_list,
            clip_number=request.maxClipNumber,
            aspect_ratio=aspect_ratio,
            ext=ext
        )
        
        if response['code'] != 2000:
            return {
                "status": "failed", 
                "reason": response.get("message", "Upload failed"), 
                "details": response
            }
        
        project_id = response['projectId']
        
        # Send initial processing message via WebSocket
        await send_message_to_client(project_id, {
            "status": "processing",
            "message": "Video uploaded to Vizard. Processing started...",
            "project_id": project_id
        })
        
        # Return project_id immediately to frontend
        # This prevents timeout on REST API call
        response_data = {
            "status": "processing",
            "message": "Processing started. Updates will be sent via WebSocket.",
            "projectId": project_id,
            "project_id": project_id
        }
        
        # Create a future and wait for webhook (in background)
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        pending_clips[project_id] = future
        
        # Start background task for processing
        # This runs independently without blocking the REST response
        asyncio.create_task(
            process_clip_generation_in_background(
                project_id, future, request, template_info,
                intro_url, outro_url, logo_url
            )
        )
        
        # Return immediately with project_id
        return response_data

        
    except Exception as e:
        print(f"❌ Error in handle_generate_clip: {str(e)}")
        return {
            "status": "error",
            "message": f"An unexpected error occurred: {str(e)}"
        }


@router.post("/webhook/vizard")
async def receive_vizard_webhook(request: Request):
    """
    Webhook endpoint to receive Vizard processing results
    """
    try:
        data = await request.json()
        print("📩 Vizard Webhook Received:---------", data)
        
        project_id = data.get("projectId")
        code = data.get("code")
        print(f"Code: {code}, Project ID: {project_id}")
        
        if code == 2000 and project_id:
            print("success-----------")
            
            # Send webhook received notification
            await send_message_to_client(project_id, {
                "status": "processing",
                "message": "Vizard completed processing. Finalizing..."
            })
            
            # Resolve the future if it's waiting
            future = pending_clips.get(project_id)
            if future and not future.done():
                future.set_result(data)
                pending_clips.pop(project_id, None)
            
            return {"status": "clip generation ready"}
        
        return {
            "status": "ignored",
            "reason": "Invalid code or missing projectId"
        }
        
    except Exception as e:
        print("❌ Webhook error:", e)
        return {
            "status": "failed",
            "error": str(e)
        }


@router.get("/supported-language")
async def get_lang():
    """Get supported languages"""
    return FileResponse("language.json", media_type="application/json")


@router.get("/supported-param")
async def get_param():
    """Get supported parameters"""
    return FileResponse("supported_param.json", media_type="application/json")