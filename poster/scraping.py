"""build_clinics_dataset.py – v1.8
------------------------------------------------
Robust geocoding:
 • timeout aumentato (default 10 s, env NOMINATIM_TIMEOUT)
 • fino a 3 retry con back‑off esponenziale (2 s, 5 s, 10 s)
 • se fallisce ancora → coord nulle ma lo script continua
 • opzione rapida per saltare la geocodifica: esporta ADDR_ONLY=1

Il resto del parsing è identico alla v1.7.
"""
from __future__ import annotations
import json, os, re, sys, time
from io import StringIO
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin

import pandas as pd, requests, urllib3
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut
from tqdm import tqdm

# ──────────────────── Compatibilità richieste ────────────────────
if tuple(map(int, urllib3.__version__.split('.'))) >= (2, 2):
    sys.exit('⚠️ urllib3≥2.2 incompatibile – esegui: pip install "urllib3<2.2"')

BASE   = 'https://www.epicentro.iss.it'
INDEX  = f'{BASE}/ivg/progetto-ccm-2022-mappa-punti-ivg'
HEADERS= {'User-Agent':'IVG-Scraper/1.8 (+https://github.com/tuo-user)'}
CACHE_DIR = Path('data/cache'); CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT = Path('data/clinics_ivg_2023.geojson')

NOMINATIM_DELAY   = float(os.getenv('NOMINATIM_DELAY'  , '1.1'))  # sec
NOMINATIM_TIMEOUT = float(os.getenv('NOMINATIM_TIMEOUT', '10'))   # sec
MAX_RETRIES       = 3
ADDR_ONLY         = os.getenv('ADDR_ONLY','0') == '1'  # salta geocoding

REGEX_NUM = re.compile(r'^(?:\s*)((?:\d[\d.\s]*)?)\s+((?:\d[\d.\s]*)?)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)')

# ──────────────────── Utility HTTP cache ────────────────────

def cached_get(url:str)->Path:
    name = re.sub(r'\W+','_',url.lower().split('//')[-1])[:120] or 'index'
    path = CACHE_DIR / f"{name}.html"
    if path.exists():
        return path
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    path.write_text(r.text, 'utf-8')
    return path

# ──────────────────── Helper numeri ────────────────────

def _num(s:str)->float:
    s = re.sub(r'[.\s]','', s)
    return float(s.replace(',','.')) if s else 0.0

# ──────────────────── Parsing pagina regionale ────────────────────

def parse_regional_page(html_path:Path, region:str)->pd.DataFrame:
    soup = BeautifulSoup(html_path.read_text('utf-8'), 'html.parser')
    table = soup.find('table')
    if table:
        df = pd.read_html(StringIO(str(table)))[0]
        df.columns = [c.strip().lower() for c in df.columns]
        qmap = {}
        for c in df.columns:
            cl=c.lower()
            if 'totale' in cl: qmap[c]='totalIVG'
            elif 'farmacologic' in cl and '%' in cl: qmap[c]='pct_pharm'
            elif 'farmacologic' in cl: qmap[c]='IVG_pharm'
            elif '9-10' in cl: qmap[c]='pct_9-10w'
            elif '11-12' in cl: qmap[c]='pct_11-12w'
            elif '8' in cl: qmap[c]='pct_<=8w'
            elif 'cert' in cl: qmap[c]='pct_cert_consultorio'
        df = df.rename(columns=qmap)
        names, addrs = [], []
        for tr in table.find_all('tr'):
            tds = tr.find_all('td')
            if not tds: continue
            cell = tds[0]
            lines = list(cell.stripped_strings)
            if not lines: continue
            names.append(lines[0])
            addrs.append(' '.join(lines[1:]).strip().rstrip(','))
        df['name']    = names[:len(df)]
        df['address'] = addrs[:len(df)]
        df['region']  = region
        return df
    # fallback regex
    lines = [re.sub(r'\s+',' ', l).strip() for l in soup.get_text('\n').split('\n') if l.strip()]
    recs: List[dict] = []
    for i, line in enumerate(lines):
        m = REGEX_NUM.match(line)
        if not m: continue
        addr = lines[i-1] if i>=1 else ''
        name = lines[i-2] if i>=2 else ''
        tot, ph, pct_ph, p8, p9, p11, pct_c = m.groups()
        recs.append({'name':name,'address':addr,'totalIVG':int(re.sub(r'\D','',tot)),
                     'IVG_pharm':int(re.sub(r'\D','',ph)),'pct_pharm':_num(pct_ph),
                     'pct_<=8w':_num(p8),'pct_9-10w':_num(p9),'pct_11-12w':_num(p11),
                     'pct_cert_consultorio':_num(pct_c),'region':region})
    return pd.DataFrame.from_records(recs)

# ──────────────────── Geocoding robusto ────────────────────

def safe_geocode(geolocator:Nominatim, query:str)->Optional[tuple[float,float]]:
    for attempt in range(1, MAX_RETRIES+1):
        try:
            loc = geolocator.geocode(query, timeout=NOMINATIM_TIMEOUT)
            if loc: return loc.latitude, loc.longitude
            return None
        except (GeocoderTimedOut, GeocoderUnavailable, requests.ConnectionError):
            if attempt == MAX_RETRIES:
                return None
            wait = [2,5,10][attempt-1] if attempt-1 < 3 else 10
            time.sleep(wait)
    return None


def geocode_df(df:pd.DataFrame)->pd.DataFrame:
    if ADDR_ONLY or 'address' not in df.columns:
        print('ℹ️  Geocodifica saltata (ADDR_ONLY=1 o address mancante).')
        df['lat'] = df['lon'] = None
        return df
    geo = Nominatim(user_agent='ivg_geocoder')
    lats, lons = [], []
    for addr in tqdm(df['address'], desc='Geocoding', unit='addr'):
        key = re.sub(r'[^a-zA-Z0-9]','_', addr)[:80]
        cache = CACHE_DIR / f'geo_{key}.json'
        if cache.exists():
            c = json.loads(cache.read_text()); lats.append(c['lat']); lons.append(c['lon']); continue
        time.sleep(NOMINATIM_DELAY)
        coords = safe_geocode(geo, addr + ', Italia')
        if coords is None:
            lats.append(None); lons.append(None)
        else:
            lat, lon = coords; lats.append(lat); lons.append(lon)
            cache.write_text(json.dumps({'lat':lat,'lon':lon}))
    df['lat'], df['lon'] = lats, lons
    return df

# ──────────────────── Pipeline principale ────────────────────

def main():
    print('📥  Scarico indice…')
    idx = cached_get(INDEX)
    soup = BeautifulSoup(idx.read_text('utf-8'), 'html.parser')
    links = soup.select("a[href*='progetto-ccm-2022-']")
    region_links = {}
    for a in links:
        href=a.get('href','')
        if any(x in href for x in ('divulgazione','grafici','mappa-punti-ivg')): continue
        name=a.get_text(strip=True)
        region_links[name]=href if href.startswith('http') else urljoin(INDEX, href)
    print(f'🔗  Link regioni: {len(region_links)}')

    frames: List[pd.DataFrame] = []
    for region, url in region_links.items():
        print(f'→ {region:15} {url}')
        frames.append(parse_regional_page(cached_get(url), region))

    df_all = pd.concat(frames, ignore_index=True)
    df_all = geocode_df(df_all)

    feats=[]
    for _, r in df_all.iterrows():
        if r.get('lon') is None: continue
        feats.append({'type':'Feature','geometry':{'type':'Point','coordinates':[r.lon,r.lat]},
                      'properties':{k:v for k,v in r.items() if k not in ('lat','lon')}})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump({'type':'FeatureCollection','features':feats}, open(OUTPUT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅  Creato {OUTPUT} – strutture con coordinate: {len(feats)}')

if __name__=='__main__':
    main()
