from app.websocket_manager import manager
from app.routes import pending_clips

# Add this to your existing webhook handler
async def handle_webhook_with_progress(project_id: str, data: dict):
    if project_id in pending_clips:
        await manager.send_progress(project_id, 60, "Clips ready, processing...")
        
        # Your existing webhook logic here
        pending_clips[project_id]['future'].set_result(data)