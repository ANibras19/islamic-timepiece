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

        all_periods = []

        # Start from -3 days/nights to +7 days/nights (total 22 periods)
        for offset in range(-3, 8):
            base_date = (now + timedelta(days=offset)).date()
            s = sun(loc.observer, date=base_date, tzinfo=tz)
            prev_s = sun(loc.observer, date=base_date - timedelta(days=1), tzinfo=tz)
            next_s = sun(loc.observer, date=base_date + timedelta(days=1), tzinfo=tz)

            # Night (belongs to next Islamic day)
            night_start = s["sunset"]
            night_end = next_s["sunrise"]
            night_weekday = (night_start + timedelta(minutes=1)).strftime('%A')  # belongs to next day
            night_planets = nightHours[night_weekday]
            night_blocks = []
            night_hour_length = (night_end - night_start).total_seconds() / 12

            for i in range(12):
                hs = night_start + timedelta(seconds=i * night_hour_length)
                he = night_start + timedelta(seconds=(i + 1) * night_hour_length)
                night_blocks.append({
                    "hour": i + 1,
                    "start": hs.strftime("%H:%M"),
                    "end": he.strftime("%H:%M"),
                    "planet": night_planets[i],
                    "period": "Night",
                    "weekday": night_weekday,
                    "islamic_hour": (
                        i + 1 if night_start <= now < night_end else None
                    )
                })

            all_periods.append(night_blocks)

            # Day (belongs to the same date)
            day_start = s["sunrise"]
            day_end = s["sunset"]
            day_weekday = base_date.strftime('%A')
            day_planets = dayHours[day_weekday]
            day_blocks = []
            day_hour_length = (day_end - day_start).total_seconds() / 12

            for i in range(12):
                hs = day_start + timedelta(seconds=i * day_hour_length)
                he = day_start + timedelta(seconds=(i + 1) * day_hour_length)
                day_blocks.append({
                    "hour": i + 1,
                    "start": hs.strftime("%H:%M"),
                    "end": he.strftime("%H:%M"),
                    "planet": day_planets[i],
                    "period": "Day",
                    "weekday": day_weekday,
                    "islamic_hour": (
                        i + 1 if day_start <= now < day_end else None
                    )
                })

            all_periods.append(day_blocks)

        # Flatten the list and find current hour block
        flat_blocks = [b for period in all_periods for b in period]
        current_block = next((b for b in flat_blocks if b["islamic_hour"]), None)

        return jsonify({
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timezone": match["timezone"],
            "hour_blocks": flat_blocks,
            "period": current_block["period"] if current_block else None,
            "day_of_week": current_block["weekday"] if current_block else None,
            "islamic_hour": current_block["islamic_hour"] if current_block else None,
            "start": None,
            "end": None
        })

    except Exception as e:
        print("ERROR:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
