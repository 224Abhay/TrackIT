import scheduler
import time
import socketio
import threading
import logging

# Configure logging
logging.basicConfig(
    filename="C:/ProgramData/TrackIt/client.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

MAIN_DIR = "C:/ProgramData/TrackIt"

sio = socketio.Client()

def connect_to_server():
    try:
        logging.info("Attempting to connect to server...")
        sio.connect("http://localhost:5000")
        logging.info("Connected to server successfully.")
        sio.wait()
    except Exception as e:
        logging.error(f"Failed to connect: {e}")

def log_event(event_name, data):
    logging.info(f"Received event: {event_name} | Data: {data}")

@sio.on("create_schedule")
def create_schedule(data):
    log_event("create_schedule", data)
    
    schedule_id = data.get("schedule_id")
    interval = data.get("interval")
    details_required = data.get("details_required")
    
    if all([schedule_id, interval, details_required]):
        scheduler.create_schedule(schedule_id, interval, details_required)
        logging.info(f"Schedule created: ID={schedule_id}, Interval={interval}, Details={details_required}")
    else:
        logging.warning("Invalid schedule data received")

@sio.on("custom_data")
def custom_event(data):
    log_event("custom_data", data)
    
    details_required = data.get("details_required")
    from get_info import get_info
    
    try:
        processed_result = get_info(*details_required)
        sio.emit("processed_data", processed_result)
        logging.info(f"Processed and sent data: {processed_result}")
    except Exception as e:
        logging.error(f"Error processing data: {e}")

if __name__ == "__main__":
    logging.info("Starting client...")
    thread = threading.Thread(target=connect_to_server, daemon=True)
    thread.start()
    time.sleep(5)

    while True:
        try:
            scheduler.run_scheduler(sio.connected)
            logging.info("Scheduler ran successfully.")
        except Exception as e:
            logging.error(f"Scheduler error: {e}")
        time.sleep(5)
