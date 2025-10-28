import websocket
import json
import time
import requests
import threading
import sys

BASE_URL = "http://localhost:8080/ai"
WS_URL = "ws://localhost:8080/ai"

def test_websocket_connection(project_id):
    """Test WebSocket with better connection stability"""
    ws_url = f"{WS_URL}/ws/{project_id}"
    print(f"🔗 Connecting to: {ws_url}\n")
    
    messages_received = []
    start_time = time.time()
    connection_alive = True
    
    def on_message(ws, message):
        elapsed = time.time() - start_time
        print(f"\n[{elapsed:.1f}s] 📩 MESSAGE RECEIVED:")
        try:
            data = json.loads(message)
            print(json.dumps(data, indent=2))
            messages_received.append(data)
            
            msg_type = data.get("type", "unknown")
            
            if msg_type == "connected":
                print(f"   ✅ Connection confirmed - waiting for webhook...")
                
            elif msg_type == "progress":
                progress = data.get('progress', 0)
                message_text = data.get('message', '')
                print(f"   📊 Progress: {progress}% - {message_text}")
                
                bar_length = 40
                filled = int(bar_length * progress / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"   [{bar}] {progress}%")
                
            elif msg_type == "result":
                print(f"   🎉 FINAL RESULT!")
                result = data.get('result', {})
                print(f"   Clips: {result.get('clip_count', 0)}")
                print(f"   Credits: {result.get('credit_usage', 0)}")
                print(f"\n✅ Processing complete! Closing in 2 seconds...")
                time.sleep(2)
                ws.close()
                
            elif msg_type == "error":
                print(f"   ❌ ERROR: {data.get('message')}")
                ws.close()
                
            elif msg_type == "cancelled":
                print(f"   🛑 Task cancelled")
                ws.close()
                
            elif msg_type == "keepalive":
                print(f"   💓 Keepalive")
                
        except json.JSONDecodeError:
            print(f"   Raw: {message}")
    
    def on_error(ws, error):
        print(f"\n❌ WebSocket Error: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        nonlocal connection_alive
        connection_alive = False
        elapsed = time.time() - start_time
        
        print(f"\n{'=' * 60}")
        print(f"🔌 Connection CLOSED after {elapsed:.1f}s")
        print(f"   Status: {close_status_code}")
        print(f"   Message: {close_msg}")
        print(f"\n📊 Total messages: {len(messages_received)}")
        
        progress_msgs = [m for m in messages_received if m.get('type') == 'progress']
        result_msgs = [m for m in messages_received if m.get('type') == 'result']
        
        if result_msgs:
            print(f"   ✅ Successfully received final result")
        elif len(progress_msgs) > 0:
            print(f"   ⚠️ Received {len(progress_msgs)} progress updates but no final result")
        else:
            print(f"   ⚠️ Connection closed before webhook arrived")
            print(f"   💡 Make sure server is running and webhook is configured")
        
        print(f"{'=' * 60}")
    
    def on_open(ws):
        print("✅ WebSocket CONNECTED and stable!")
        print("⏳ Waiting for Vizard webhook (may take 1-5 minutes)...\n")
        
        def keep_alive():
            """Send ping every 20 seconds to keep connection alive"""
            while connection_alive:
                time.sleep(20)
                try:
                    if ws.sock and ws.sock.connected:
                        ws.send(json.dumps({"type": "ping"}))
                        print(f"[{time.time() - start_time:.1f}s] 💓 Ping sent")
                except Exception as e:
                    print(f"⚠️ Ping failed: {e}")
                    break
        
        ping_thread = threading.Thread(target=keep_alive, daemon=True)
        ping_thread.start()
    
    # Create WebSocket with better error handling
    print("⏳ Establishing WebSocket connection...")
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Run with reconnection support
    try:
        # Enable trace for debugging
        # websocket.enableTrace(True)
        
        ws.run_forever(
            ping_interval=20,  # Send ping every 20 seconds
            ping_timeout=10    # Timeout if no pong in 10 seconds
        )
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        ws.close()
    except Exception as e:
        print(f"\n❌ Connection error: {e}")


def test_complete_flow():
    """Start new video processing and monitor via WebSocket"""
    print("=" * 60)
    print("🧪 COMPLETE FLOW TEST")
    print("=" * 60)
    
    print("\n📤 Step 1: Starting video processing...")
    
    payload = {
    "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJjbWYweXo0OHQwMDA1dW01czJ0eDJwc2RzIiwiZW1haWwiOiJtb2hlYnVsbGFvZmZpY2VAZ21haWwuY29tIiwicm9sZSI6IlVTRVIiLCJpYXQiOjE3NjE2MjA1MjEsImV4cCI6MTc2MTYzODUyMX0.lG0bjA_4TWShSXAPqb7u6Jf_44J2ofuFEd1-KpXA30w",
    "url": "https://youtu.be/thpF81-wrMs?si=fcb30TSUBOEXgKuK",
    "videoType": 2,
    "langCode": "en",
    "clipLength": 1,
    "maxClipNumber": 2,
    "templateId": "22",
    "prompt": "i need some specific funny parts"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/generate", json=payload, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return
        
        data = response.json()
        print(f"✅ Response: {json.dumps(data, indent=2)}")
        
        if "project_id" not in data:
            print("❌ No project_id in response")
            return
        
        project_id = data["project_id"]
        print(f"\n✅ Got project_id: {project_id}")
        print(f"\n🔌 Step 2: Connecting WebSocket...")
        
        test_websocket_connection(project_id)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # test_websocket_connection("25116050")
    if len(sys.argv) > 1:
        # Test with existing project_id
        project_id = sys.argv[1]
        print(f"🧪 Testing existing project: {project_id}\n")
        test_websocket_connection(project_id)
    else:
        # Run complete flow
        test_complete_flow()