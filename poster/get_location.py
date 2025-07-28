import json
import math
import time
import requests
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from tqdm import tqdm

# === CONFIG ===
GOOGLE_API_KEY = "SECRET"  # ← INSERISCI QUI LA TUA CHIAVE
INPUT_PATH = Path("data/clinics_ivg_2023.geojson")
OUTPUT_PATH = INPUT_PATH.with_name("clinics_ivg_2023_google_decode.geojson")

# === FUNZIONE: chiamata API Google ===
def geocode_google(address):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": f"{address}, Italia", "key": GOOGLE_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        results = r.json().get("results")
        if results:
            loc = results[0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    except Exception as e:
        print(f"❌ Errore con '{address}': {e}")
    return None, None

# === FUNZIONE: verifica se coordinate sono valide ===
def is_invalid(coords):
    if not coords or len(coords) != 2:
        return True
    x, y = coords
    return any([
        x is None, y is None,
        isinstance(x, float) and math.isnan(x),
        isinstance(y, float) and math.isnan(y),
    ])

# === CARICAMENTO DATI ===
data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
features = data.get("features", [])

updated = 0
for f in tqdm(features, desc="🔁 Geocoding con Google"):
    coords = f.get("geometry", {}).get("coordinates")
    if is_invalid(coords):
        addr = f["properties"].get("address", "")
        lat, lon = geocode_google(addr)
        if lat is not None and lon is not None:
            f["geometry"] = {"type": "Point", "coordinates": [lon, lat]}
            updated += 1
        time.sleep(0.25)  # rispetto soft rate limit

# === SALVATAGGIO ===
OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
print(f"✅ Completato: {updated} coordinate aggiornate")
print(f"📄 Salvato: {OUTPUT_PATH}")