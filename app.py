from flask import Flask, request, jsonify
from flask_cors import CORS
from astral import LocationInfo
from astral.sun import sun
from datetime import datetime, timedelta
import pytz
import json
import traceback
import os

app = Flask(__name__)
CORS(app)

# Load countries.json once at startup
with open("countries.json", "r", encoding="utf-8") as f:
    country_data = json.load(f)

# Planet ruling each hour of the day
dayHours = {
    "Sunday":    ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn"],
    "Monday":    ["Moon", "Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars", "Sun"],
    "Tuesday":   ["Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"],
    "Wednesday": ["Mercury", "Moon", "Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"],
    "Thursday":  ["Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury"],
    "Friday":    ["Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter"],
    "Saturday":  ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars", "Sun", "Venus"]
}

# Night hours rotate forward (e.g. Thursday night = Sunday day hours)
nightHours = {
    "Sunday":    dayHours["Wednesday"],
    "Monday":    dayHours["Thursday"],
    "Tuesday":   dayHours["Friday"],
    "Wednesday": dayHours["Saturday"],
    "Thursday":  dayHours["Sunday"],
    "Friday":    dayHours["Monday"],
    "Saturday":  dayHours["Tuesday"]
}

@app.route('/sun-times', methods=['POST'])
def get_sun_times():
    data = request.json
    requested_country = data.get("country")
    requested_state = data.get("state")

    country = next((c for c in country_data if c["country"].lower() == requested_country.lower()), None)
    if not country:
        return jsonify({"error": f"Country '{requested_country}' not found"}), 400

    match = next((loc for loc in country["locations"] if loc["state"].lower() == requested_state.lower()), None)
    if not match:
        return jsonify({"error": f"State/City '{requested_state}' not found in {requested_country}"}), 404

    try:
        tz = pytz.timezone(match["timezone"])
        now = datetime.now(tz)

        loc = LocationInfo(match["state"], requested_country, match["timezone"], match["latitude"], match["longitude"])

        all_blocks = []
        current_hour_index = None
        current_period_id = None

        for offset in range(-3, 8):  # from 3 days back to 7 days ahead
            day = now.date() + timedelta(days=offset)
            s = sun(loc.observer, date=day, tzinfo=tz)
            sunrise = s["sunrise"]
            sunset = s["sunset"]

            # DAY block
            weekday = sunrise.strftime("%A")
            start = sunrise
            end = sunset
            planet_table = dayHours
            planets = planet_table[weekday]
            for i in range(12):
                hour_start = start + timedelta(seconds=i * ((end - start).total_seconds() / 12))
                hour_end = start + timedelta(seconds=(i + 1) * ((end - start).total_seconds() / 12))
                is_now = hour_start <= now < hour_end
                block = {
                    "hour": i + 1,
                    "start": hour_start.strftime("%H:%M"),
                    "end": hour_end.strftime("%H:%M"),
                    "planet": planets[i],
                    "period": "Day",
                    "weekday": weekday
                }
                if is_now:
                    current_hour_index = len(all_blocks)
                all_blocks.append(block)

            # NIGHT block (sunset → next day's sunrise)
            next_day = day + timedelta(days=1)
            s_next = sun(loc.observer, date=next_day, tzinfo=tz)
            next_sunrise = s_next["sunrise"]
            next_weekday = next_sunrise.strftime("%A")
            start = sunset
            end = next_sunrise
            planet_table = nightHours
            planets = planet_table[next_weekday]
            for i in range(12):
                hour_start = start + timedelta(seconds=i * ((end - start).total_seconds() / 12))
                hour_end = start + timedelta(seconds=(i + 1) * ((end - start).total_seconds() / 12))
                is_now = hour_start <= now < hour_end
                block = {
                    "hour": i + 1,
                    "start": hour_start.strftime("%H:%M"),
                    "end": hour_end.strftime("%H:%M"),
                    "planet": planets[i],
                    "period": "Night",
                    "weekday": next_weekday
                }
                if is_now:
                    current_hour_index = len(all_blocks)
                all_blocks.append(block)

        return jsonify({
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "sunrise": sunrise.strftime("%H:%M:%S"),
            "sunset": sunset.strftime("%H:%M:%S"),
            "day_of_week": now.strftime('%A'),
            "period": "Day" if s["sunrise"] <= now < s["sunset"] else "Night",
            "islamic_hour": (current_hour_index % 12 + 1) if current_hour_index is not None else None,
            "start": all_blocks[current_hour_index]["start"] if current_hour_index is not None else None,
            "end": all_blocks[current_hour_index]["end"] if current_hour_index is not None else None,
            "timezone": match["timezone"],
            "hour_blocks": all_blocks
        })

    except Exception as e:
        print("ERROR:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
