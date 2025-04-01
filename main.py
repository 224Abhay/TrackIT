import asyncio
import json
import scheduler
import time
import socketio


sio = socketio.Client()

async def connect_to_server():
    try:
        sio.connect("http://localhost:5000")
        print("Connected to WebSocket server. Listening for schedule requests...")
        sio.wait()
    except Exception as e:
        print(f"Failed to connect: {e}")

async def listen_for_schedule():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket server. Listening for schedule requests...")
        while True:
            try:
                message = await websocket.recv()
                print(f"Received message: {message}")
                
                data = json.loads(message)
                schedule_id = data.get("schedule_id")
                interval = data.get("interval")
                details_required = data.get("details_required")
                
                if all([schedule_id, interval, details_required]):
                    scheduler.create_schedule(schedule_id, interval, details_required)
                else:
                    print("Invalid schedule data received")
                    
            except Exception as e:
                print(f"Error processing message: {e}")

@sio.on("create_schedule")
def create_schedule(data):
    schedule_id = data.get("schedule_id")
    interval = data.get("interval")
    details_required = data.get("details_required")
    
    if all([schedule_id, interval, details_required]):
        scheduler.create_schedule(schedule_id, interval, details_required)
    else:
        print("Invalid schedule data received")

@sio.on("custom_data")
def custom_event(data):
    details_required = data.get("details_required")
    from get_info import get_info
    processed_result = get_info(*details_required)
    sio.emit("processed_data", processed_result)

if __name__ == "__main__":
    asyncio.run(connect_to_server())

    while True:
        # scheduler.run_scheduler()
        time.sleep(1)