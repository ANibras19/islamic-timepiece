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
        s_today = sun(loc.observer, date=now.date(), tzinfo=tz)
        sunrise = s_today["sunrise"]
        sunset = s_today["sunset"]

        # Determine Islamic period and hour block
        if sunrise <= now < sunset:
            period = "Day"
            start = sunrise
            end = sunset
            weekday = now.strftime('%A')  # Day is today
        else:
            period = "Night"
            if now >= sunset:
                tomorrow = now + timedelta(days=1)
                s_tomorrow = sun(loc.observer, date=tomorrow.date(), tzinfo=tz)
                start = sunset
                end = s_tomorrow["sunrise"]
                weekday = tomorrow.strftime('%A')  # Night belongs to next day
            else:
                yesterday = now - timedelta(days=1)
                s_yesterday = sun(loc.observer, date=yesterday.date(), tzinfo=tz)
                start = s_yesterday["sunset"]
                end = sunrise
                weekday = now.strftime('%A')  # Already past midnight, still night of today

        # Calculate Islamic hour number (1–12)
        total_seconds = (end - start).total_seconds()
        elapsed_seconds = (now - start).total_seconds()
        hour_length = total_seconds / 12
        islamic_hour = int(elapsed_seconds // hour_length) + 1
        islamic_hour = max(1, min(12, islamic_hour))

        # Generate Islamic hour blocks with start, end, and ruling planet
        hour_blocks = []
        planet_table = dayHours if period == "Day" else nightHours
        planets = planet_table[weekday]

        for i in range(12):
            hour_start = start + timedelta(seconds=i * hour_length)
            hour_end = start + timedelta(seconds=(i + 1) * hour_length)
            hour_blocks.append({
                "hour": i + 1,
                "start": hour_start.strftime("%H:%M"),
                "end": hour_end.strftime("%H:%M"),
                "planet": planets[i]
            })

        return jsonify({
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "sunrise": sunrise.strftime("%H:%M:%S"),
            "sunset": sunset.strftime("%H:%M:%S"),
            "day_of_week": weekday,
            "period": period,
            "islamic_hour": islamic_hour,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timezone": match["timezone"], 
            "hour_blocks": hour_blocks
        })

    except Exception as e:
        print("ERROR:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
