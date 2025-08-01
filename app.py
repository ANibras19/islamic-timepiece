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
        current_period = None
        current_weekday = None
        current_islamic_hour = None

        for offset in range(-3, 8):
            day = now + timedelta(days=offset)

            # ----- NIGHT FIRST -----
            night_start_data = sun(loc.observer, date=day.date(), tzinfo=tz)
            night_end_data = sun(loc.observer, date=(day + timedelta(days=1)).date(), tzinfo=tz)
            night_start = night_start_data["sunset"]
            night_end = night_end_data["sunrise"]
            night_weekday = (day + timedelta(days=1)).strftime('%A')  # Night belongs to next day
            night_planets = nightHours[night_weekday]
            total_night_seconds = (night_end - night_start).total_seconds()
            hour_length_night = total_night_seconds / 12

            for i in range(12):
                hour_start = night_start + timedelta(seconds=i * hour_length_night)
                hour_end = night_start + timedelta(seconds=(i + 1) * hour_length_night)
                is_current = night_start <= now < night_end and hour_start <= now < hour_end

                all_blocks.append({
                    "hour": i + 1,
                    "start": hour_start.strftime("%H:%M"),
                    "end": hour_end.strftime("%H:%M"),
                    "planet": night_planets[i],
                    "period": "Night",
                    "date": (day + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "day_name": night_weekday,
                    "is_current": is_current
                })

                if is_current:
                    current_period = "Night"
                    current_weekday = night_weekday
                    current_islamic_hour = i + 1

            # ----- DAY NEXT -----
            sunrise = night_end
            sunset = night_end_data["sunset"]
            day_weekday = (day + timedelta(days=1)).strftime('%A')
            day_planets = dayHours[day_weekday]
            total_day_seconds = (sunset - sunrise).total_seconds()
            hour_length_day = total_day_seconds / 12

            for i in range(12):
                hour_start = sunrise + timedelta(seconds=i * hour_length_day)
                hour_end = sunrise + timedelta(seconds=(i + 1) * hour_length_day)
                is_current = sunrise <= now < sunset and hour_start <= now < hour_end

                all_blocks.append({
                    "hour": i + 1,
                    "start": hour_start.strftime("%H:%M"),
                    "end": hour_end.strftime("%H:%M"),
                    "planet": day_planets[i],
                    "period": "Day",
                    "date": (day + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "day_name": day_weekday,
                    "is_current": is_current
                })

                if is_current:
                    current_period = "Day"
                    current_weekday = day_weekday
                    current_islamic_hour = i + 1

        return jsonify({
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timezone": match["timezone"],
            "hour_blocks": all_blocks,
            "period": current_period,
            "day_of_week": current_weekday,
            "islamic_hour": current_islamic_hour
        })

    except Exception as e:
        print("ERROR:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
