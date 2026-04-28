from flask import Flask, render_template, jsonify
import pyodbc
import requests
import json
from datetime import datetime
import os

app = Flask(__name__)

# ⚠️ REPLACE THESE
ENDPOINT_URL = "https://trafficml-workspace-sjfwk.francecentral.inference.ml.azure.com/score"
ENDPOINT_KEY = os.getenv("ENDPOINT_KEY")

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=trafficserver-elie.database.windows.net;"
    "DATABASE=TrafficDB;"
    "UID=trafficadmin;"
    "PWD=Eliemezher2005$;"
    "Encrypt=yes;"
)

def get_latest_zone_data():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            locationZone,
            AVG(speed) as avg_speed,
            COUNT(*) as vehicle_count,
            MAX(timestamp) as last_update
        FROM VehicleTelemetry
        WHERE timestamp >= DATEADD(MINUTE, -5, GETUTCDATE())
        GROUP BY locationZone
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def predict_congestion(avg_speed, vehicle_count, hour):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ENDPOINT_KEY}"
    }
    data = {
        "input_data": {
            "columns": ["avg_speed", "vehicle_count", "road_capacity", 
                       "congestion_ratio", "hour_of_day", "is_rush_hour"],
            "data": [[
                avg_speed,
                vehicle_count,
                100,
                vehicle_count / 100,
                hour,
                1 if (8 <= hour < 10) or (17 <= hour < 20) else 0
            ]]
        }
    }
    try:
        response = requests.post(ENDPOINT_URL, headers=headers, json=data)
        result = response.json()
        if isinstance(result, list):
            return int(result[0])
        return 0
    except:
        return 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/zones')
def get_zones():
    rows = get_latest_zone_data()
    hour = datetime.utcnow().hour
    zones = []

    # If no live data, use time-based simulation
    if not rows:
        zone_names = ["ZoneA", "ZoneB", "ZoneC", "ZoneD"]
        import random
        for zone in zone_names:
            if (8 <= hour < 10) or (17 <= hour < 20):
                avg_speed = random.randint(5, 25)
                vehicle_count = random.randint(70, 95)
            elif 0 <= hour < 6 or hour >= 22:
                avg_speed = random.randint(80, 120)
                vehicle_count = random.randint(0, 10)
            elif 12 <= hour < 14:
                avg_speed = random.randint(70, 110)
                vehicle_count = random.randint(8, 20)
            else:
                avg_speed = random.randint(30, 60)
                vehicle_count = random.randint(20, 50)

            prediction = predict_congestion(avg_speed, vehicle_count, hour)
            zones.append({
                "zone": zone,
                "avg_speed": round(avg_speed, 1),
                "vehicle_count": vehicle_count,
                "prediction": prediction,
                "status": "🔴 Congested" if prediction == 1 else "🟢 Normal",
                "last_update": datetime.utcnow().strftime("%H:%M:%S")
            })
        return jsonify(zones)

    for row in rows:
        zone, avg_speed, vehicle_count, last_update = row
        prediction = predict_congestion(avg_speed, vehicle_count, hour)
        zones.append({
            "zone": zone,
            "avg_speed": round(avg_speed, 1),
            "vehicle_count": vehicle_count,
            "prediction": prediction,
            "status": "🔴 Congested" if prediction == 1 else "🟢 Normal",
            "last_update": last_update.strftime("%H:%M:%S")
        })

    return jsonify(zones)

if __name__ == '__main__':
    app.run(debug=True)