import time
from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

devices = []

@app.route("/api/data", methods=["POST"])
def device_report():
    data = request.json
    if not data or "data" not in data or "schedule" not in data:
        return jsonify({"error": "Invalid data format"}), 400
    
    data["timestamp"] = datetime.now().isoformat()
    hardware_info = data["data"].get("hardware", {})
    serial_number = hardware_info.get("serial_number", "unknown")
    
    file_path = f"devices/{data['hardware']['serial_number']}.json"
    
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            existing_data = json.load(f)
    else:
        existing_data = []

    existing_data.append(data)

    with open(file_path, "w") as f:
        json.dump(existing_data, f, indent=4)
        
    return jsonify({"message": "Device data received", "status": "success"}), 200

@app.route("/api/schedule", methods=["POST"])
def send_schedule():
    data = request.json
    schedule_id = data.get("schedule_id")
    interval = data.get("interval")
    details_required = data.get("details_required")
    socketio.emit("create_schedule", {"schedule_id": schedule_id, "interval": interval, "details_required": details_required})

    return jsonify({"message": "Schedule sent", "status": "success"}), 200

@app.route("/api/custom", methods=["POST"])
def get_custom_data():
    data = request.json
    socketio.emit("custom_data", {"details_required": data['details_required']})

    return jsonify({"data": data}), 200

@socketio.on("processed_data")
def receive_processed_data(data):
    """Handles processed data from the client"""
    print(f"Received processed data: {data}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)