# websocket_manager.py - FIXED VERSION
import json
from fastapi import WebSocket
from starlette.websockets import WebSocketState
from typing import Dict
import time
import asyncio


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_times: Dict[str, float] = {}
        self.last_activity: Dict[str, float] = {}
        self.message_queues: Dict[str, asyncio.Queue] = {}

    async def connect(self, websocket: WebSocket, project_id):
        """Accept and store WebSocket connection"""
        project_id = str(project_id)  # Always convert to string
        await websocket.accept()
        self.active_connections[project_id] = websocket
        self.connection_times[project_id] = time.time()
        self.last_activity[project_id] = time.time()
        self.message_queues[project_id] = asyncio.Queue()
        print(f"✅ WebSocket connected for project: {project_id}")
        print(f"📊 Active connections: {len(self.active_connections)}")

    def disconnect(self, project_id):
        """Remove WebSocket connection"""
        project_id = str(project_id)  # Always convert to string
        if project_id in self.active_connections:
            uptime = time.time() - self.connection_times.get(project_id, time.time())
            del self.active_connections[project_id]
            if project_id in self.connection_times:
                del self.connection_times[project_id]
            if project_id in self.last_activity:
                del self.last_activity[project_id]
            if project_id in self.message_queues:
                del self.message_queues[project_id]
            print(f"🔌 Disconnected: {project_id} (was connected for {uptime:.1f}s)")
            print(f"📊 Active connections: {len(self.active_connections)}")

    def is_connected(self, project_id) -> bool:
        """
        FIXED: Simple check - if in active_connections, it's connected
        The queue-based approach handles disconnections automatically
        """
        project_id = str(project_id)  # Always convert to string
        return project_id in self.active_connections

    async def send_message(self, project_id, message: dict) -> bool:
        """
        FIXED: Always queue message if connection exists
        Don't check is_connected() - just check if in active_connections
        """
        project_id = str(project_id)  # Always convert to string
        
        if project_id not in self.active_connections:
            print(f"⚠️ No active connection for project: {project_id}")
            print(f"📊 Active projects: {list(self.active_connections.keys())}")
            return False
        
        if project_id not in self.message_queues:
            print(f"⚠️ No message queue for: {project_id}")
            return False
        
        try:
            # Queue message
            await self.message_queues[project_id].put(message)
            
            msg_type = message.get('type', 'unknown')
            if msg_type in ['result', 'error', 'progress']:
                progress = message.get('progress', '')
                progress_str = f" ({progress}%)" if progress else ""
                print(f"📥 Queued {msg_type}{progress_str} for {project_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to queue message for {project_id}: {e}")
            # If queue fails, remove connection
            self.disconnect(project_id)
            return False
    
    async def process_message_queue(self, project_id, websocket: WebSocket):
        """Process queued messages - runs in background"""
        project_id = str(project_id)  # Always convert to string
        queue = self.message_queues.get(project_id)
        if not queue:
            print(f"⚠️ No queue for {project_id}")
            return
        
        print(f"🎬 Starting message processor for {project_id}")
        
        try:
            while project_id in self.active_connections:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(queue.get(), timeout=2.0)
                    
                    # Try to send
                    try:
                        await websocket.send_text(json.dumps(message))
                        self.last_activity[project_id] = time.time()
                        
                        msg_type = message.get('type', 'unknown')
                        if msg_type in ['result', 'error', 'progress']:
                            progress = message.get('progress', '')
                            progress_str = f" ({progress}%)" if progress else ""
                            print(f"✅ Sent {msg_type}{progress_str} to {project_id}")
                        
                        queue.task_done()
                        
                    except Exception as send_error:
                        print(f"❌ Failed to send to {project_id}: {send_error}")
                        # Connection broken, exit loop
                        break
                    
                except asyncio.TimeoutError:
                    # No message, continue
                    continue
                    
        except Exception as e:
            print(f"❌ Message processor error for {project_id}: {e}")
        finally:
            print(f"🛑 Message processor stopped for {project_id}")

    async def send_progress(self, project_id, progress: int, message: str, **extra_data):
        """Send progress update"""
        project_id = str(project_id)  # Always convert to string
        payload = {
            "type": "progress",
            "progress": progress,
            "message": message,
            "project_id": project_id,
            "timestamp": time.time(),
            **extra_data
        }
        return await self.send_message(project_id, payload)

    async def send_result(self, project_id, result: dict):
        """Send final result"""
        project_id = str(project_id)  # Always convert to string
        payload = {
            "type": "result",
            "result": result,
            "project_id": project_id,
            "timestamp": time.time()
        }
        return await self.send_message(project_id, payload)

    async def send_error(self, project_id, error_message: str, error_code: str = None):
        """Send error message"""
        project_id = str(project_id)  # Always convert to string
        payload = {
            "type": "error",
            "message": error_message,
            "error_code": error_code,
            "project_id": project_id,
            "timestamp": time.time()
        }
        return await self.send_message(project_id, payload)

    async def send_cancelled(self, project_id):
        """Send cancellation notice"""
        project_id = str(project_id)  # Always convert to string
        payload = {
            "type": "cancelled",
            "message": "Task was cancelled by user",
            "project_id": project_id,
            "timestamp": time.time()
        }
        return await self.send_message(project_id, payload)

    async def broadcast(self, message: dict):
        """Send message to all connected clients"""
        results = []
        for project_id in list(self.active_connections.keys()):
            success = await self.send_message(project_id, message)
            results.append(success)
        return sum(results)

    def get_connection_info(self, project_id) -> dict:
        """Get detailed connection information"""
        project_id = str(project_id)  # Always convert to string
        if project_id not in self.active_connections:
            return {"connected": False}
        
        websocket = self.active_connections[project_id]
        state = "UNKNOWN"
        
        try:
            if hasattr(websocket, 'client_state'):
                state = str(websocket.client_state)
        except:
            pass
        
        return {
            "connected": True,
            "uptime": time.time() - self.connection_times.get(project_id, time.time()),
            "last_activity": time.time() - self.last_activity.get(project_id, time.time()),
            "websocket_state": state,
            "queue_size": self.message_queues[project_id].qsize() if project_id in self.message_queues else 0
        }


# Global instance
manager = ConnectionManager()