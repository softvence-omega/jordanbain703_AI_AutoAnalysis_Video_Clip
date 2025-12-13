import websocket
import json
import time
import requests
import threading
import sys

BASE_URL = "http://184.105.4.166:8000/ai"
WS_URL = "ws://184.105.4.166:8000/ai"

def test_websocket_connection(project_id):
    """Test WebSocket with ultra-robust connection handling"""
    ws_url = f"{WS_URL}/ws/connect/{project_id}"
    print(f"🔗 Connecting to: {ws_url}\n")
    
    messages_received = []
    start_time = time.time()
    connection_alive = True
    processing_complete = False
    last_message_time = time.time()
    
    def on_message(ws, message):
        nonlocal processing_complete, last_message_time
        last_message_time = time.time()
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
                processing_complete = True
                time.sleep(2)
                ws.close()
                
            elif msg_type == "error":
                print(f"   ❌ ERROR: {data.get('message')}")
                processing_complete = True
                ws.close()
                
            elif msg_type == "cancelled":
                print(f"   🛑 Task cancelled")
                processing_complete = True
                ws.close()
                
            elif msg_type == "keepalive":
                waiting = data.get('waiting_time', 0)
                print(f"   💓 Server keepalive - waiting {waiting}s")
                
            elif msg_type == "pong":
                print(f"   💓 Pong received")
                
        except json.JSONDecodeError:
            print(f"   Raw: {message}")
    
    def on_error(ws, error):
        # Ignore ping/pong timeout errors - they're not fatal
        error_str = str(error)
        if "ping/pong timed out" in error_str.lower():
            print(f"\n⚠️ Ping/pong timeout (connection still alive)")
        else:
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
        
        if processing_complete:
            if result_msgs:
                print(f"   ✅ Successfully received final result")
            else:
                print(f"   ⚠️ Processing ended without result")
        elif len(progress_msgs) > 0:
            last_msg_age = time.time() - last_message_time
            print(f"   ⚠️ Received {len(progress_msgs)} progress updates")
            print(f"   📡 Last message received {last_msg_age:.0f}s ago")
            if last_msg_age > 60:
                print(f"   💡 Connection likely timed out - webhook may still be processing")
            else:
                print(f"   💡 Connection closed unexpectedly")
        else:
            print(f"   ⚠️ Connection closed before webhook arrived")
        
        print(f"{'=' * 60}")
    
    def on_open(ws):
        print("✅ WebSocket CONNECTED!")
        print("⏳ Waiting for Vizard webhook (typically 1-5 minutes)...")
        print("💡 You'll see keepalive messages while waiting\n")
        
        def keep_alive():
            """Send application-level ping every 20 seconds"""
            ping_count = 0
            while connection_alive and not processing_complete:
                time.sleep(20)
                if not connection_alive or processing_complete:
                    break
                    
                try:
                    if ws.sock and ws.sock.connected:
                        ping_count += 1
                        ws.send(json.dumps({
                            "type": "ping",
                            "count": ping_count,
                            "timestamp": time.time()
                        }))
                        elapsed = time.time() - start_time
                        print(f"[{elapsed:.1f}s] 💓 Ping #{ping_count} sent")
                except Exception as e:
                    print(f"⚠️ Ping failed: {e}")
                    break
        
        ping_thread = threading.Thread(target=keep_alive, daemon=True)
        ping_thread.start()
    
    # Create WebSocket with NO automatic ping/pong
    print("⏳ Establishing WebSocket connection...")
    
    # Disable trace for cleaner output
    # websocket.enableTrace(True)
    
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Run WITHOUT automatic ping/pong to avoid timeout issues
    try:
        ws.run_forever(
            # Completely disable WebSocket protocol-level ping/pong
            # We use application-level ping/pong instead (more reliable)
            suppress_origin=True,
            skip_utf8_validation=False
        )
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        ws.close()
    except Exception as e:
        print(f"\n❌ Connection error: {e}")
        import traceback
        traceback.print_exc()


def test_complete_flow():
    """Start new video processing and monitor via WebSocket"""
    print("=" * 60)
    print("🧪 COMPLETE FLOW TEST")
    print("=" * 60)
    
    print("\n📤 Step 1: Starting video processing...")
    
    payload = {
        "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJjbWlwbTduejIwMDAwZ3gxcWk5djBrZGw2IiwiZW1haWwiOiJzb2hhZ2lzbGFtZGV2ZWxvcGVyQGdtYWlsLmNvbSIsInJvbGUiOiJVU0VSIiwiaWF0IjoxNzY1NjExMDg1LCJleHAiOjE3NjU2MjkwODV9.HLD07_7ZPSjCtsdDRYIXiSkUA9-9euYNehXk1CyWao4",
        "url": "https://youtu.be/thpF81-wrMs?si=fcb30TSUBOEXgKuK",
        "videoType": 2,
        "langCode": "en",
        "clipLength": 1,
        "maxClipNumber": 2,
        "templateId": "33",
        "prompt": "i need some specific funny parts"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/generate", json=payload, timeout=120)
        
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
        print(f"💡 Note: Vizard webhook typically takes 1-5 minutes")
        print(f"💡 Keep this window open - you'll see progress updates!\n")
        
        time.sleep(1)  # Brief delay
        test_websocket_connection(project_id)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Test with existing project_id
        project_id = sys.argv[1]
        print(f"🧪 Testing existing project: {project_id}\n")
        test_websocket_connection(project_id)
    else:
        # Run complete flow
        test_complete_flow()