from collections import defaultdict
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import requests

def load_env_file(filepath='/opt/data/.env'):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"\'')

def scan_and_schedule_day_combos():
    url = 'https://external-api.kalshi.com/trade-api/v2/markets'
    params = {'status': 'open', 'series_ticker': 'KXSPORTS', 'limit': 200}

    response = requests.get(url, params=params)
    if response.status_code != 200:
        return 'Error fetching schedule.'

    markets = response.json().get('markets', [])
    time_groups = defaultdict(list)
    
    for m in markets:
        time_groups[m['close_time']].append({
            'ticker': m['ticker'],
            'title': m['title'],
        })

    overlapping_schedules = {
        close_time: games for close_time, games in time_groups.items() 
        if len(games) >= 2
    }

    for close_iso, tickers in overlapping_schedules.items():
        schedule_targeted_check(close_iso, tickers)

    return overlapping_schedules

def schedule_targeted_check(close_iso, tickers):
    close_dt = datetime.fromisoformat(close_iso.replace('Z', '+00:00'))
    at_time = close_dt.strftime('%H:%M')
    
    tickers_json = json.dumps(tickers).replace('"', '\\"')
    cmd = (
        f'echo "/opt/data/venv/bin/python /opt/data/kalshi_skimmer.py '
        f'--check-tickers \\"{tickers_json}\\"" | at {at_time}'
    )
    subprocess.run(cmd, shell=True)

def check_specific_tickers(ticker_list):
    high_prob_matches = []

    for item in ticker_list:
        ticker = item['ticker']
        url = f'https://external-api.kalshi.com/trade-api/v2/markets/{ticker}'
        response = requests.get(url)

        if response.status_code == 200:
            m = response.json().get('market', {})
            prob = max(m.get('yes_bid', 0), m.get('last_price', 0)) / 100.0
            if prob >= 0.95:
                high_prob_matches.append({
                    'title': m.get('title', item['title']),
                    'prob': prob,
                    'ticker': ticker,
                })

    return high_prob_matches if len(high_prob_matches) >= 2 else None

def send_to_discord(content):
    load_env_file()
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url: return

    payload = {
        'content': f'📊 **Kalshi 95%+ Combo Alert**\n```json\n{json.dumps(content, indent=2)}\n```'
    }
    requests.post(webhook_url, json=payload)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--check-tickers':
        target_tickers = json.loads(sys.argv[2])
        combos = check_specific_tickers(target_tickers)
        if combos:
            send_to_discord(combos)
    else:
        scan_and_schedule_day_combos()