from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import os
import requests


def load_env_file(filepath='/opt/data/.env'):
  """Simple zero-dependency helper to read key-value pairs from .env."""
  if os.path.exists(filepath):
    with open(filepath, 'r') as f:
      for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
          key, value = line.split('=', 1)
          os.environ[key.strip()] = value.strip().strip('"\'')


def get_combo_skims():
  # Production API endpoint for Kalshi
  url = 'https://external-api.kalshi.com/trade-api/v2/markets'
  params = {'status': 'open', 'series_ticker': 'KXSPORTS', 'limit': 100}

  response = requests.get(url, params=params)
  if response.status_code != 200:
    return 'Error fetching data from Kalshi.'

  markets = response.json().get('markets', [])
  now = datetime.now(timezone.utc)

  #Games closing in the last 5 minutes or coming up soon
  filtered = []
  for m in markets:
    close_time = datetime.fromisoformat(m['close_time'].replace('Z', '+00:00'))

    time_diff = (close_time - now).total_seconds()
    if -300 <= time_diff <= 300:
      prob = max(m.get('yes_bid', 0), m.get('last_price', 0)) / 100.0
      if prob >= 0.95:
        filtered.append({
            'title': m['title'],
            'prob': prob,
            'close_time': close_time.strftime('%H:%M UTC'),
            'ticker': m['ticker'],
        })

 #Logic to combo games at the same time
  grouped = defaultdict(list)
  for game in filtered:
    grouped[game['close_time']].append(game)

  # Only return times with 2+ games 
  combos = {k: v for k, v in grouped.items() if len(v) >= 2}

  if not combos:
    return (
        'No high-probability (95%+) game combos found for the current time'
        ' window.'
    )

  return json.dumps(combos, indent=2)


def send_to_discord(content):
  load_env_file()  
  webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

  if not webhook_url:
    print('Warning: DISCORD_WEBHOOK_URL not set in environment or .env file.')
    return

  payload = {'content': f'📊 **Kalshi High-Probability Sports Combos**\n```json\n{content}\n```'}
  response = requests.post(webhook_url, json=payload)
  if response.status_code not in (200, 204):
    print(f'Failed to post to Discord. Status code: {response.status_code}')


if __name__ == '__main__':
  result = get_combo_skims()
  print(result)
  send_to_discord(result)