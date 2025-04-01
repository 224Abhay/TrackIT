import datetime
import os
import json
import time
from get_info import get_info

DATA_DIR = r"C:/ProgramData/TrackIt"
SCHEDULES_DIR = os.path.join(DATA_DIR, "schedules")
LAST_SENT_FILE = os.path.join(DATA_DIR, "last_sent.json")

os.makedirs(SCHEDULES_DIR, exist_ok=True)

if os.path.exists(LAST_SENT_FILE):
    with open(LAST_SENT_FILE, "r") as f:
        last_sent = json.load(f)
else:
    last_sent = {}

def run_scheduler():
    for schedule_file_name in os.listdir(SCHEDULES_FOLDER):
        if schedule_file_name.endswith(".json"):
            if schedule_file_name not in last_sent:

                with open(os.path.join(SCHEDULES_FOLDER, schedule_file_name), "r") as f:
                    schedule = json.load(f)

                data = get_info(*schedule["details_required"])
                print(data)

                last_sent[schedule_file_name] = {"last_sent": time.time(), "interval": schedule["interval"]}

            else:
                if time.time() - last_sent[schedule_file_name]["last_sent"] > last_sent[schedule_file_name]["interval"]:
                    with open(os.path.join(SCHEDULES_FOLDER, schedule_file_name), "r") as f:
                        schedule = json.load(f)

                    data = get_info(*schedule["details_required"])
                    print(data)

                    last_sent[schedule_file_name]["last_sent"] = time.time()


    with open(LAST_SENT_FILE, "w") as f:
        json.dump(last_sent, f)

def create_schedule(schedule_id, interval, details_required):
    schedule = {
        "interval": interval,
        "details_required": details_required
    }

    filename = f"{schedule_id}.json"
    filepath = os.path.join(SCHEDULES_DIR, filename)
    
    with open(filepath, "w") as f:
        json.dump(schedule, f, indent=4)
    
    print(f"Schedule created and saved to {filepath}")
    return schedule
