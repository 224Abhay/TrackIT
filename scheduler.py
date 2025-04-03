import datetime
import os
import json
import time
from get_info import get_info
import socketio
import logging

# Configure logging
logging.basicConfig(
    filename="C:/ProgramData/TrackIt/scheduler.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

PARENT_DIR = r"C:/ProgramData/TrackIt"
SCHEDULES_DIR = os.path.join(PARENT_DIR, "schedules")
DATA_DIR = os.path.join(PARENT_DIR, "data")
LAST_SENT_FILE = os.path.join(PARENT_DIR, "last_sent.json")

os.makedirs(SCHEDULES_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def run_scheduler(connected_to_server=True):
    logging.info("Running scheduler...")
    
    if os.path.exists(LAST_SENT_FILE):
        with open(LAST_SENT_FILE, "r") as f:
            last_sent = json.load(f)
    else:
        last_sent = {}

    schedules = os.listdir(SCHEDULES_DIR)

    if not schedules:
        logging.info("No schedules found.")
        return

    for schedule_file_name in schedules:
        if schedule_file_name.endswith(".json"):
            if schedule_file_name not in last_sent:
                with open(os.path.join(SCHEDULES_DIR, schedule_file_name), "r") as f:
                    schedule = json.load(f)

                data = get_info(*schedule["details_required"])
                logging.info(f"Collected data for {schedule_file_name}: {data}")

                if connected_to_server:
                    socketio.emit("processed_data", {"data": data})
                    logging.info(f"Sent data to server for {schedule_file_name}")
                else:
                    with open(os.path.join(DATA_DIR, schedule_file_name), "w") as f:
                        json.dump(data, f, indent=4)
                    logging.info(f"Saved data locally for {schedule_file_name}")

                last_sent[schedule_file_name] = {"last_sent": time.time(), "interval": schedule["interval"]}
            else:
                if time.time() - last_sent[schedule_file_name]["last_sent"] > last_sent[schedule_file_name]["interval"]:
                    with open(os.path.join(SCHEDULES_DIR, schedule_file_name), "r") as f:
                        schedule = json.load(f)

                    data = get_info(*schedule["details_required"])
                    logging.info(f"Collected data for {schedule_file_name}: {data}")

                    if connected_to_server:
                        socketio.emit("processed_data", {"data": data})
                        logging.info(f"Sent data to server for {schedule_file_name}")
                    else:
                        with open(os.path.join(DATA_DIR, schedule_file_name), "w") as f:
                            json.dump(data, f, indent=4)
                        logging.info(f"Saved data locally for {schedule_file_name}")

                    last_sent[schedule_file_name]["last_sent"] = time.time()

    with open(LAST_SENT_FILE, "w") as f:
        json.dump(last_sent, f)
    logging.info("Scheduler execution completed.")

def create_schedule(schedule_id, interval, details_required):
    schedule = {
        "interval": interval,
        "details_required": details_required
    }

    filename = f"{schedule_id}.json"
    filepath = os.path.join(SCHEDULES_DIR, filename)
    
    with open(filepath, "w") as f:
        json.dump(schedule, f, indent=4)
    
    logging.info(f"Schedule created: ID={schedule_id}, Interval={interval}, Details={details_required}")
    print(f"Schedule created and saved to {filepath}")
    return schedule