from urllib import response
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from app.services.filter_clips import filter_clips
from app.services.upload_video import upload_video
from app.services.clipper import run_clip_generation
from app.services.get_lang import get_language_code
from app.services.add_template import Add_Template
from app.services.duration_find import get_extension_from_url
from app.schema import paramRequest, CancelResponse
from app.services.store_response import store_in_db
from app.config import BACKEND_URL
from app.websocket_manager import manager
import asyncio
import requests
import json
import httpx
import time
from dotenv import load_dotenv
load_dotenv(override=True)  # <-- this must come before accessing os.getenv()


# Keep track of pending project_id to future response
pending_clips = {}
cancelled_tasks = set()

router = APIRouter()

def find_project_in_pending(project_id):
    """Find project in pending_clips, handling both string and int keys"""
    # Try as string first
    if project_id in pending_clips:
        return project_id
    # Try as int
    try:
        int_id = int(project_id)
        if int_id in pending_clips:
            return int_id
    except (ValueError, TypeError):
        pass
    # Try string version of int keys
    str_id = str(project_id)
    if str_id in pending_clips:
        return str_id
    return None

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
            get_extension_from_url, url
        )
        return ext
    return None  # Other video types don't need extension check


def validate_extension(ext: str) -> bool:
    """Validate video file extension"""
    if not ext:
        return True
    supported_exts = ["mp4", "3gp", "avi", "mov"]
    return ext.lower() in supported_exts





# routes.py - Key Updates

@router.post("/generate", tags=["Video Processing"])
async def handle_generate_clip(request: paramRequest):
    """
    Start video processing and return project_id
    Client should connect to /ws/{project_id} for progress updates
    """
    try:
        print("📝 Generate request received:", request.prompt)
        
        # Send initial progress even if WebSocket not connected yet
        # (will be stored and sent when client connects)
        
        # Validate parameters
        clip_length_list = [request.clipLength]
        if not (0 <= request.maxClipNumber <= 100):
            return {"error": "clipNumber must be between 0 and 100"}
        
        template_info = None
        aspect_ratio = 1
        
        if request.templateId:
            headers = {"Authorization": f"Bearer {request.auth_token}"}
            try:
                template_response = requests.get(
                    f"{BACKEND_URL}/templates/{request.templateId}", 
                    headers=headers
                )
                template_response.raise_for_status()
                template_info = template_response.json()['data']
                aspect_ratio = convert_aspect_ratio(template_info['aspectRatio'])
            except Exception as e:
                return {"error": f"Failed to fetch template info: {str(e)}"}
        
        # Find video duration
        ext = None
        try:
            if request.videoType == 1:
                ext = get_extension_from_url(request.url)
            # elif request.videoType == 2:
            #     duration_seconds = get_youtube_duration(request.url)
            # elif request.videoType == 3:
            #     duration_seconds = get_drive_duration(request.url)
        except Exception as e:
            return {"error": f"Failed to get video extension: {str(e)}"}

        # if round(duration_seconds) > 3600:
        #     return {"error": "Video duration must be less than 3600 seconds"}
        
        # Validate extension
        supported_exts = ["mp4", "3gp", "avi", "mov"]
        if ext and ext.lower() not in supported_exts:
            return {"error": f"Unsupported video extension: {ext}"}

        # Upload Video to Vizard
        print("📤 Uploading video to Vizard...")
        response = upload_video(
            request.url, 
            video_type=request.videoType, 
            lang=request.langCode, 
            prefer_length=clip_length_list, 
            clip_number=request.maxClipNumber, 
            aspect_ratio=aspect_ratio, 
            ext=ext
        )

        if response['code'] == 2000:
            project_id = response['projectId']
            print(f"✅ Project created: {project_id}")
            print("project id type:-----", type(project_id))
            
            # Store task metadata
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            pending_clips[project_id] = {
                'future': future,
                'request': request,
                'template_info': template_info,
                'created_at': time.time()
            }
            
            # Send initial progress (will be queued if WebSocket not connected yet)
            await manager.send_progress(
                project_id, 
                20, 
                "Video uploaded successfully, processing started..."
            )
            
            # Return project_id for client to connect WebSocket
            return {
                "status": "processing",
                "project_id": project_id,
                "message": "Connect to /ws/{project_id} for real-time progress",
                "websocket_url": f"/ws/{project_id}"
            }
        else:
            return {
                "status": "failed", 
                "reason": response.get("message", "Upload failed"), 
                "details": response
            }
            
    except Exception as e:
        print(f"❌ Generate error: {e}")
        return {"error": str(e)}


@router.websocket("/ws/connect/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """
    WebSocket endpoint with message queue processing
    """
    print(f"🔌 WebSocket connection attempt for: {project_id}")
    
    try:
        await manager.connect(websocket, project_id)
        print(f"✅ Connection established for {project_id}")
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connected",
            "project_id": project_id,
            "message": "Connected - waiting for processing",
            "timestamp": time.time()
        }))
        
        # Send initial progress if task exists
        actual_key = find_project_in_pending(project_id)
        print("actual key found----------------", actual_key)
        if actual_key is not None:
            print(f"⏳ Sending initial progress for {project_id}")
            await manager.send_progress(
                project_id, 
                25, 
                "Processing started - waiting for Vizard webhook..."
            )
        
        # Start message queue processor in background
        queue_task = asyncio.create_task(
            manager.process_message_queue(project_id, websocket)
        )
        
        # Keep connection alive and handle client messages
        last_keepalive = time.time()
        keepalive_interval = 45
        
        while True:
            try:
                # Wait for client messages
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=keepalive_interval
                )
                
                # Handle client messages
                try:
                    msg = json.loads(data)
                    msg_type = msg.get("type")
                    
                    if msg_type == "ping":
                        # Reply to ping
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": time.time()
                        }))
                        print(f"💓 Ping→Pong for {project_id}")
                        last_keepalive = time.time()
                        
                    elif msg_type == "status":
                        actual_key = find_project_in_pending(project_id)
                        status = "processing" if actual_key is not None else "unknown"
                        await websocket.send_text(json.dumps({
                            "type": "status_response",
                            "status": status,
                            "project_id": project_id,
                            "timestamp": time.time()
                        }))
                        
                except json.JSONDecodeError:
                    print(f"⚠️ Invalid JSON from {project_id}")
                    
            except asyncio.TimeoutError:
                # Send keepalive
                current_time = time.time()
                if current_time - last_keepalive >= keepalive_interval:
                    try:
                        await websocket.send_text(json.dumps({
                            "type": "keepalive",
                            "message": "Connection alive",
                            "project_id": project_id,
                            "timestamp": current_time
                        }))
                        print(f"💓 Keepalive → {project_id}")
                        last_keepalive = current_time
                    except Exception as e:
                        print(f"❌ Keepalive failed: {e}")
                        break
                        
            except WebSocketDisconnect:
                print(f"🔌 Client disconnected: {project_id}")
                break
            except Exception as e:
                print(f"❌ Error for {project_id}: {e}")
                break
        
        # Cancel queue processor
        queue_task.cancel()
        try:
            await queue_task
        except asyncio.CancelledError:
            pass
                
    except Exception as e:
        print(f"❌ WebSocket error for {project_id}: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        manager.disconnect(project_id)
        print(f"🔌 WebSocket cleanup complete for {project_id}")


# Debugging endpoint - check connection status
@router.get("/ws/status/{project_id}", tags=["Debug"])
async def check_websocket_status(project_id: str):
    """Check if WebSocket is connected for a project"""
    info = manager.get_connection_info(project_id)
    actual_key = find_project_in_pending(project_id)
    is_pending = actual_key is not None
    
    return {
        "project_id": project_id,
        "actual_key": actual_key,
        "websocket": info,
        "task_pending": is_pending,
        "task_data": {
            "exists": is_pending,
            "created_at": pending_clips[actual_key]['created_at'] if is_pending else None,
            "waiting_seconds": int(time.time() - pending_clips[actual_key]['created_at']) if is_pending else None
        } if is_pending else None
    }


@router.post("/webhook/vizard", tags=["Webhooks"])
async def receive_vizard_webhook(request: Request):
    """
    Receive webhook from Vizard when processing completes
    """
    try:
        data = await request.json()
        print("📩 Vizard webhook received:", data.get("projectId"))

        project_id = data.get("projectId")
        code = data.get("code")
        
        if code != 2000 or not project_id:
            return {"status": "ignored", "reason": "Invalid webhook data"}
        
        # Find actual key in pending_clips
        actual_key = find_project_in_pending(project_id)
        
        # Check if task was cancelled
        if project_id in cancelled_tasks or actual_key in cancelled_tasks:
            print(f"⚠️ Webhook for cancelled task: {project_id}")
            cancelled_tasks.discard(project_id)
            if actual_key: cancelled_tasks.discard(actual_key)
            if actual_key and actual_key in pending_clips:
                del pending_clips[actual_key]
            return {"status": "task_was_cancelled"}
        
        # Check if task exists
        if actual_key is None:
            print(f"⚠️ Unknown project: {project_id}")
            return {"status": "project_not_found"}
        
        task_data = pending_clips[actual_key]
        future = task_data['future']
        req = task_data['request']
        template_info = task_data['template_info']
        
        if future.done():
            return {"status": "already_processed"}
        
        try:
            print("checking for sending progress 50--------------")
            # Progress: 50% - Clips generated
            await manager.send_progress(
                project_id, 
                50, 
                "Video clips generated successfully",
                clips_count=len(data.get('videos', []))
            )
            
            clip_res = data
            
            # Check cancellation
            if project_id in cancelled_tasks or actual_key in cancelled_tasks:
                cancelled_tasks.discard(project_id)
                if actual_key: cancelled_tasks.discard(actual_key)
                del pending_clips[actual_key]
                await manager.send_cancelled(project_id)
                return {"status": "cancelled"}
            
            # Progress: 60% - Applying template
            print("checking for sending progress 60--------------", template_info)
            if req.templateId and template_info:
                await manager.send_progress(project_id, 60, "Applying custom template...")
                try:
                    # Check if template URLs are valid
                    intro_url = template_info.get('introVideo', '').strip()
                    outro_url = template_info.get('outroVideo', '').strip()
                    logo_url = template_info.get('overlayLogo', '').strip()
                    
                    print(f"🔍 Template URLs - intro: '{intro_url}', outro: '{outro_url}', logo: '{logo_url}'")
                    
                    # Apply template if at least one component is available
                    if intro_url or outro_url or logo_url:
                        clips = Add_Template(
                            clip_res['videos'], 
                            template_info['aspectRatio'], 
                            intro_url if intro_url else None,
                            outro_url if outro_url else None,
                            logo_url if logo_url else None
                        )
                        clip_res['videos'] = clips
                        components = []
                        if intro_url: components.append("intro")
                        if outro_url: components.append("outro")
                        if logo_url: components.append("logo")
                        await manager.send_progress(project_id, 70, f"Template applied: {', '.join(components)}")
                    else:
                        print(f"⚠️ No template components available")
                        await manager.send_progress(project_id, 70, "Template skipped - no components")
                except Exception as e:
                    print(f"⚠️ Template error: {e}")
                    await manager.send_progress(project_id, 70, "Template skipped, continuing...")
            
            # Check cancellation again
            if project_id in cancelled_tasks or actual_key in cancelled_tasks:
                cancelled_tasks.discard(project_id)
                if actual_key: cancelled_tasks.discard(actual_key)
                del pending_clips[actual_key]
                await manager.send_cancelled(project_id)
                return {"status": "cancelled"}
            
            # Progress: 75% - Filtering clips
            if (req.prompt and req.prompt.strip() and 
                req.prompt.lower() != "string"):
                await manager.send_progress(project_id, 75, "Filtering clips based on your prompt...")
                videos = clip_res['videos']
                if videos and len(videos) > 0 and videos[0].get("transcript"):
                    try:
                        filtered = filter_clips(videos, req.prompt)
                        clip_res['videos'] = filtered
                        await manager.send_progress(
                            project_id, 
                            85, 
                            f"Filtered to {len(filtered)} relevant clips"
                        )
                    except Exception as e:
                        print(f"⚠️ Filter error: {e}")
                        await manager.send_progress(project_id, 85, "Filter skipped")
            
            # Final cancellation check
            if project_id in cancelled_tasks or actual_key in cancelled_tasks:
                cancelled_tasks.discard(project_id)
                if actual_key: cancelled_tasks.discard(actual_key)
                del pending_clips[actual_key]
                await manager.send_cancelled(project_id)
                return {"status": "cancelled"}
            
            # Progress: 90% - Calculating credits
            await manager.send_progress(project_id, 90, "Calculating credits and saving...")
            
            total_duration = sum(clip.get('videoMsDuration', clip.get('duration', 0)) / 1000 for clip in clip_res['videos'])
            total_credits = int(total_duration // 60)
            
            # Store in database
            clips_stored_id = store_in_db(
                req, 
                clip_res["videos"], 
                total_credits, 
                main_video_duration=round(total_duration)
            )
            
            if not clips_stored_id:
                error_msg = "Failed to save clips to database"
                await manager.send_error(project_id, error_msg, "DB_SAVE_FAILED")
                if not future.done():
                    future.set_exception(Exception(error_msg))
                del pending_clips[actual_key]
                return {"status": "error", "message": error_msg}
            
            # Prepare final result
            result = {
                "status": "done",
                "project_id": project_id,
                "clip_count": len(clip_res['videos']),
                "credit_usage": total_credits,
                "clip_stored_id": clips_stored_id,
                "total_duration": total_duration,
                "clips": clip_res['videos']
            }
            
            # Progress: 100% - Send final result
            await manager.send_result(project_id, result)
            
            # Resolve future
            if not future.done():
                future.set_result(result)
            
            # Cleanup
            del pending_clips[actual_key]
            
            return {
                "status": "success", 
                "project_id": project_id,
                "clips_stored": clips_stored_id
            }
            
        except Exception as e:
            print(f"❌ Webhook processing error: {e}")
            error_msg = f"Processing failed: {str(e)}"
            await manager.send_error(project_id, error_msg, "PROCESSING_ERROR")
            
            if not future.done():
                future.set_exception(e)
            if actual_key and actual_key in pending_clips:
                del pending_clips[actual_key]
                
            return {"status": "failed", "error": str(e)}
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return {"status": "failed", "error": str(e)}


@router.post("/cancel/{project_id}", tags=["Video Processing"])
async def cancel_task(project_id: str):
    """Cancel a running task"""
    
    if project_id not in pending_clips:
        raise HTTPException(
            status_code=404, 
            detail="Task not found or already completed"
        )
    
    print(f"🛑 Cancelling task: {project_id}")
    
    # Mark as cancelled
    cancelled_tasks.add(project_id)
    
    # Cancel future
    task_data = pending_clips[project_id]
    future = task_data['future']
    if not future.done():
        future.cancel()
    
    # Notify via WebSocket
    await manager.send_cancelled(project_id)
    
    # Cleanup
    del pending_clips[project_id]
    manager.disconnect(project_id)
    
    return {
        "status": "cancelled",
        "message": f"Task {project_id} cancelled successfully",
        "project_id": project_id
    }
    
@router.get("/supported-language")
def get_lang():
    return FileResponse("language.json", media_type="application/json")

@router.get("/supported-param")
def get_param():
    return FileResponse("supported_param.json", media_type="application/json")

