import os
import time
import json
import requests
import traceback
from datetime import datetime, timezone, timedelta
from entsoe import EntsoePandasClient
import pandas as pd
from dotenv import load_dotenv

load_dotenv(override=True)

ORACLE_ENDPOINT = "http://127.0.0.1:8000/city"
ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
COUNTRY_CODE = "BE"

def get_real_entsoe_price():
    """Haalt de actuele day-ahead uurprijs voor België op via de officiële ENTSO-E API."""
    # Veiligheidscontrole: check of de key correct is ingeladen uit .env
    if not ENTSOE_API_KEY:
        print("[ENTSO-E Error] ENTSOE_API_KEY niet gevonden in .env bestand! Schakelt over op nood-fallback.")
        return round(0.1450, 4)

    try:
        client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
        now = pd.Timestamp.now(tz='Europe/Brussels')
        start = now.floor('D')
        end = start + timedelta(days=1)
        
        # Query day-ahead prijzen
        ts_prices = client.query_day_ahead_prices(COUNTRY_CODE, start=start, end=end)
        
        # Bepaal huidige uur-timestamp afgerond naar beneden
        current_hour = now.floor('h')
        
        # Prijs in EUR/MWh omrekenen naar EUR/kWh
        price_kwh = ts_prices.loc[current_hour] / 1000
        print(f"Live market price loaded from ENTSO-E: {price_kwh:.4f} EUR/kWh")
        return round(price_kwh, 4)
        
    except Exception as e:
        print(f"[ENTSO-E Error] Probleem bij ophalen prijs ({e}). Schakelt over op nood-fallback.")
        traceback.print_exc()
        return round(0.1450, 4)

def get_real_production_weather():
    """Haalt het actuele weer in Brussel op via de officiële Open-Meteo API."""
    try:
        # Exacte URL op basis van Open-Meteo Docs (Brussels coördinaten)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 50.8503,
            "longitude": 4.3517,
            "current_weather": True
        }
        res = requests.get(url, params=params, timeout=5).json()
        
        current_data = res.get("current_weather", {})
        code = current_data.get("weathercode", current_data.get("weather_code", 0))
        temp = current_data.get("temperature", 15.0)
        
        is_day = current_data.get("is_day", 1)
        
        # WMO Code mapping conform open-meteo docs naar uw simulator enums
        if code in [95, 96, 99]: 
            return "storm"
        elif code in [71, 73, 75, 77, 85, 86]: 
            return "snow"
        elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: 
            return "rain"
        elif temp > 30: 
            return "extreme_heat"
        elif temp < 0: 
            return "winter"
        return "sunny" if is_day == 1 else "clear_night"
    
    except Exception as e:
        print(f"[Open-Meteo Error] Fallback naar sunny: {e}")
        return "sunny"

def calculate_baseline_demand():
    current_hour = datetime.now().hour
    if 7 <= current_hour <= 9 or 17 <= current_hour <= 20:
        return 250.0
    if 10 <= current_hour <= 16:
        return 150.0
    return 90.0

def send_production_data():
    current_price = get_real_entsoe_price()
    baseline_demand = calculate_baseline_demand()
    live_weather = get_real_production_weather()
    
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "city_status": {
            "kale_stroomprijs_eur_kwh": current_price,
            "geschatte_basis_vraag_kw": baseline_demand,
            "actieve_laders_basis": 10,
            "net_congestie_risico": "HOOG" if baseline_demand > 200 and current_price > 0.18 else "LAAG"
        },
        "weather": live_weather
    }
    
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(ORACLE_ENDPOINT, data=json.dumps(payload), headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"[POST 200] Markt: EUR {current_price}/kWh | Weer: {live_weather} -> Succesvol gesynchroniseerd!")
    except Exception as e:
        print(f"[FastAPI Connection Error] Verbindingsfout naar FastAPI: {e}")

if __name__ == "__main__":
    print("EV Production Simulator Data-Pusher Actief...")
    try:
        while True:
            send_production_data()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nSimulator gestopt.")