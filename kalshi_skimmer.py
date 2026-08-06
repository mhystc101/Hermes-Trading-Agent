import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import json

def get_combo_skims():
    # Production API endpoint for Kalshi
    url = "https://external-api.kalshi.com/trade-api/v2/markets"
    # Filter for sports series (KXSPORTS)
    params = {"status": "open", "series_ticker": "KXSPORTS", "limit": 100}
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return "Error fetching data from Kalshi."

    markets = response.json().get("markets", [])
    now = datetime.now(timezone.utc)
    
    # 1. Filter: Only games closing in the last 5 minutes or next 5 minutes
    # (Adjust window as needed for 'live' games)
    filtered = []
    for m in markets:
        close_time = datetime.fromisoformat(m['close_time'].replace('Z', '+00:00'))
        
        # Check: Is it in the last 5 mins (-5m) or coming up soon?
        time_diff = (close_time - now).total_seconds()
        if -300 <= time_diff <= 300: 
            prob = max(m.get("yes_bid", 0), m.get("last_price", 0)) / 100.0
            if prob >= 0.95:
                filtered.append({
                    "title": m["title"],
                    "prob": prob,
                    "close_time": close_time.strftime("%H:%M UTC"),
                    "ticker": m["ticker"]
                })

    # 2. Grouping: Logic to combo games at the same time
    grouped = defaultdict(list)
    for game in filtered:
        grouped[game["close_time"]].append(game)

    # 3. Format Output: Only return times with 2+ games (Combos)
    combos = {k: v for k, v in grouped.items() if len(v) >= 2}
    
    if not combos:
        return "No high-probability (-95%) game combos found for the current time window."
    
    return json.dumps(combos, indent=2)

if __name__ == "__main__":
    print(get_combo_skims())