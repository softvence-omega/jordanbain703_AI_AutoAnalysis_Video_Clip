import asyncio
import json
import time
from fastapi import WebSocket
from typing import Dict, List, Optional

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.message_queues: Dict[str, List[dict]] = {}
        self.connection_times: Dict[str, float] = {}
    
    async def connect(self, websocket: WebSocket, project_id: str):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections[project_id] = websocket
        self.connection_times[project_id] = time.time()
        
        # Initialize message queue if not exists
        if project_id not in self.message_queues:
            self.message_queues[project_id] = []
        
        print(f"✅ WebSocket connected for project: {project_id}")
        print(f"📊 Active connections: {len(self.active_connections)}")
    
    def disconnect(self, project_id: str):
        """Remove WebSocket connection"""
        if project_id in self.active_connections:
            connection_duration = time.time() - self.connection_times.get(project_id, time.time())
            del self.active_connections[project_id]
            print(f"🔌 Disconnected: {project_id} (was connected for {connection_duration:.1f}s)")
            print(f"📊 Active connections: {len(self.active_connections)}")
        
        # Clean up message queue
        if project_id in self.message_queues:
            del self.message_queues[project_id]
        
        if project_id in self.connection_times:
            del self.connection_times[project_id]
    
    def is_connected(self, project_id: str) -> bool:
        """Check if client is connected"""
        return project_id in self.active_connections
    
    async def send_message(self, project_id: str, message: dict):
        """
        Send message to client or queue it if not connected
        IMPORTANT: Check both string and int versions of project_id
        """
        # Try to find the actual key (could be string or int)
        actual_key = None
        
        # Check exact match first
        if project_id in self.active_connections:
            actual_key = project_id
        else:
            # Try converting types
            try:
                # Try as int
                int_id = int(project_id) if isinstance(project_id, str) else project_id
                if int_id in self.active_connections:
                    actual_key = int_id
                
                # Try as string
                str_id = str(project_id)
                if str_id in self.active_connections:
                    actual_key = str_id
            except (ValueError, TypeError):
                pass
        
        if actual_key is not None:
            try:
                websocket = self.active_connections[actual_key]
                await websocket.send_text(json.dumps(message))
                msg_type = message.get('type', 'message')
                progress = f" ({message.get('progress')}%)" if 'progress' in message else ''
                print(f"✅ Sent {msg_type}{progress} to {project_id}")
                return True
            except Exception as e:
                print(f"❌ Failed to send message to {project_id}: {e}")
                # Queue the message for retry
                if project_id not in self.message_queues:
                    self.message_queues[project_id] = []
                self.message_queues[project_id].append(message)
                print(f"📥 Queued message for later delivery")
                return False
        else:
            # Client not connected yet, queue the message
            if project_id not in self.message_queues:
                self.message_queues[project_id] = []
            self.message_queues[project_id].append(message)
            msg_type = message.get('type', 'message')
            progress = f" ({message.get('progress')}%)" if 'progress' in message else ''
            print(f"📥 Queued {msg_type}{progress} for {project_id} (connection not found)")
            print(f"🔍 Active connections: {list(self.active_connections.keys())}")
            return False
    
    async def process_message_queue(self, project_id: str, websocket: WebSocket):
        """
        Process queued messages for a connection
        CRITICAL: This must continuously check for new messages
        """
        print(f"🎬 Starting message processor for {project_id}")
        processed_count = 0
        
        try:
            while True:
                # Check if there are queued messages
                if project_id in self.message_queues and self.message_queues[project_id]:
                    # Get all pending messages
                    messages_to_send = self.message_queues[project_id].copy()
                    self.message_queues[project_id].clear()
                    
                    # Send each message
                    for message in messages_to_send:
                        try:
                            await websocket.send_text(json.dumps(message))
                            processed_count += 1
                            msg_type = message.get('type', 'unknown')
                            progress = message.get('progress', '')
                            print(f"✅ Sent queued {msg_type} {f'({progress}%)' if progress else ''} to {project_id}")
                        except Exception as e:
                            print(f"❌ Failed to send queued message: {e}")
                            # Re-queue failed message
                            if project_id in self.message_queues:
                                self.message_queues[project_id].append(message)
                            break
                
                # Small delay to avoid busy waiting
                # IMPORTANT: Must be small enough to catch new messages quickly
                await asyncio.sleep(0.1)  # Check every 100ms
                
        except asyncio.CancelledError:
            print(f"🛑 Message processor stopped for {project_id} (processed {processed_count} messages)")
            raise
        except Exception as e:
            print(f"❌ Message processor error for {project_id}: {e}")
            import traceback
            traceback.print_exc()
    
    async def send_progress(self, project_id: str, progress: int, message: str, **kwargs):
        """Send progress update"""
        payload = {
            "type": "progress",
            "progress": progress,
            "message": message,
            "project_id": project_id,
            "timestamp": time.time(),
            **kwargs
        }
        await self.send_message(project_id, payload)
    
    async def send_result(self, project_id: str, result: dict):
        """Send final result"""
        payload = {
            "type": "result",
            "result": result,
            "project_id": project_id,
            "timestamp": time.time()
        }
        await self.send_message(project_id, payload)
    
    async def send_error(self, project_id: str, error_message: str, error_code: str = "UNKNOWN"):
        """Send error message"""
        payload = {
            "type": "error",
            "message": error_message,
            "error_code": error_code,
            "project_id": project_id,
            "timestamp": time.time()
        }
        await self.send_message(project_id, payload)
    
    async def send_cancelled(self, project_id: str):
        """Send cancellation notification"""
        payload = {
            "type": "cancelled",
            "message": "Task was cancelled",
            "project_id": project_id,
            "timestamp": time.time()
        }
        await self.send_message(project_id, payload)
    
    def get_connection_info(self, project_id: str) -> dict:
        """Get connection information for debugging"""
        is_connected = project_id in self.active_connections
        queue_size = len(self.message_queues.get(project_id, []))
        connected_duration = None
        
        if is_connected and project_id in self.connection_times:
            connected_duration = time.time() - self.connection_times[project_id]
        
        return {
            "connected": is_connected,
            "queue_size": queue_size,
            "connected_duration_seconds": connected_duration,
            "queued_messages": self.message_queues.get(project_id, [])[:5] if queue_size > 0 else []
        }
    
    def get_stats(self) -> dict:
        """Get overall manager statistics"""
        return {
            "active_connections": len(self.active_connections),
            "projects_with_queues": len(self.message_queues),
            "total_queued_messages": sum(len(q) for q in self.message_queues.values()),
            "connections": list(self.active_connections.keys())
        }

# Global instance
manager = ConnectionManager()