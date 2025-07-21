from flask import Flask, request, jsonify
from flask_cors import CORS
from astral import LocationInfo
from astral.sun import sun
from datetime import datetime
import pytz
import json
import os

app = Flask(__name__)
CORS(app)  # ✅ Allow requests from frontend

# Load countries.json once at startup
with open("countries.json", "r", encoding="utf-8") as f:
    country_data = json.load(f)

@app.route('/sun-times', methods=['POST'])
def get_sun_times():
    data = request.json
    requested_state = data.get("state")

    india = next((c for c in country_data if c["country"] == "India"), None)
    if not india:
        return jsonify({"error": "India not found in data"}), 400

    match = next((loc for loc in india["locations"] if loc["state"].lower() == requested_state.lower()), None)
    if not match:
        return jsonify({"error": f"State '{requested_state}' not found"}), 404

    try:
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(tz)

        loc = LocationInfo(match["state"], "India", match["timezone"], match["latitude"], match["longitude"])
        s = sun(loc.observer, date=now.date(), tzinfo=tz)

        sunrise = s["sunrise"]
        sunset = s["sunset"]

        # Determine if it's day or night
        if sunrise <= now < sunset:
            period = "Day"
            start = sunrise
            end = sunset
        else:
            period = "Night"
            if now >= sunset:
                tomorrow = now.date().replace(day=now.day + 1)
                s_tomorrow = sun(loc.observer, date=tomorrow, tzinfo=tz)
                start = sunset
                end = s_tomorrow["sunrise"]
            else:
                yesterday = now.date().replace(day=now.day - 1)
                s_yesterday = sun(loc.observer, date=yesterday, tzinfo=tz)
                start = s_yesterday["sunset"]
                end = sunrise

        total_seconds = (end - start).total_seconds()
        elapsed_seconds = (now - start).total_seconds()
        hour_length = total_seconds / 12
        islamic_hour = int(elapsed_seconds // hour_length) + 1
        if islamic_hour > 12:
            islamic_hour = 12

        # Planet of the Day (fixed per weekday)
        weekday = now.strftime('%A')
        day_ruler = {
            "Sunday": "Sun",
            "Monday": "Moon",
            "Tuesday": "Mars",
            "Wednesday": "Mercury",
            "Thursday": "Jupiter",
            "Friday": "Venus",
            "Saturday": "Saturn"
        }[weekday]

        # Chaldean order
        chaldean_order = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

        # Build the 24-hour planetary cycle starting from day ruler
        start_index = chaldean_order.index(day_ruler)
        planetary_cycle = [chaldean_order[(start_index + i) % 7] for i in range(24)]
        hour_index = islamic_hour - 1
        if period == "Night":
            hour_index += 12

        planet_of_hour = planetary_cycle[hour_index % 24]

        return jsonify({
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "sunrise": sunrise.strftime("%H:%M:%S"),
            "sunset": sunset.strftime("%H:%M:%S"),
            "day_of_week": weekday,
            "period": period,
            "islamic_hour": islamic_hour,
            "planet_of_day": day_ruler,
            "planet_of_hour": planet_of_hour
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
