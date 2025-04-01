import scheduler
import time
import socketio
import threading


sio = socketio.Client()

def connect_to_server():
    try:
        sio.connect("http://localhost:5000")
        sio.wait()
    except Exception as e:
        print(f"Failed to connect: {e}")

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
    thread = threading.Thread(target=connect_to_server, daemon=True)
    thread.start()

    while True:
        scheduler.run_scheduler()
        time.sleep(1)