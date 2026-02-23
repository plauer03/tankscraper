from flask import Flask, request, jsonify
import requests
import re
import json
import math
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim

app = Flask(__name__)

# --- KONFIGURATION ---
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36"}
FUEL_MAP = {"diesel": "diesel", "e5": "super-e5", "e10": "super-e10", "super": "super-e5"}

# --- BERECHNUNGEN ---
def get_coordinates_backend(address):
    try:
        geolocator = Nominatim(user_agent="fuel_finder_v3_serverless")
        location = geolocator.geocode(address, timeout=5)
        if location:
            plz = None
            if 'address' in location.raw:
                plz = location.raw['address'].get('postcode')
            return location.latitude, location.longitude, plz
        return None, None, None
    except:
        return None, None, None

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def find_region_slug(plz):
    try:
        r = requests.get("https://ich-tanke.de/suche/", params={'q': plz}, headers=HEADERS, timeout=4)
        m_direct = re.search(rf"/umkreis/({plz}-[a-zA-Z0-9-]+)/", r.url)
        if m_direct: return m_direct.group(1)

        soup = BeautifulSoup(r.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            m = re.search(rf"/umkreis/({plz}-[a-zA-Z0-9-]+)/", link['href'])
            if m: return m.group(1)
    except: return None
    return None

# --- ROUTEN ---

@app.route('/api/autocomplete')
def autocomplete():
    query = request.args.get('q', '')
    if not query: return jsonify([])
    # Photon API (OpenStreetMap)
    url = f"https://photon.komoot.io/api/?q={query}&lang=de&limit=5&bbox=5.8,47.2,15.1,55.1"
    try:
        r = requests.get(url, timeout=3)
        return jsonify(r.json().get('features', []))
    except:
        return jsonify([])

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.json
    
    # DATEN ABFRAGEN
    lat_start = float(data.get('lat') or 0)
    lon_start = float(data.get('lon') or 0)
    address_text = data.get('address_text', '')
    plz_hint = data.get('plz_hint')

    # FALLBACK: Backend Geocoding
    if lat_start == 0 or lon_start == 0:
        lat_start, lon_start, found_plz = get_coordinates_backend(address_text)
        if found_plz and not plz_hint:
            plz_hint = found_plz
    
    if not lat_start:
        return jsonify({"error": "Adresse nicht gefunden. Bitte prüfen."})

    # PLZ EXTRACTOR
    final_plz = plz_hint
    if not final_plz:
        match = re.search(r'\b\d{5}\b', address_text)
        if match: final_plz = match.group(0)
    
    if not final_plz:
        return jsonify({"error": "Keine PLZ in der Adresse gefunden."})

    fuel_type = data.get('fuel')
    liters_fill = float(data.get('liters'))
    consumption = float(data.get('cons'))

    # REGION FINDEN
    slug = find_region_slug(final_plz)
    if not slug: return jsonify({"error": f"Keine Daten für PLZ {final_plz}."})

    # DATEN LADEN
    clean_fuel = FUEL_MAP.get(fuel_type, "super-e5")
    url = f"https://ich-tanke.de/tankstellen/{clean_fuel}/umkreis/{slug}/"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        match = re.search(r'var tankstellen\s*=\s*(\[.*?\]);', resp.text, re.DOTALL)
        if not match: return jsonify({"error": "Keine Live-Daten verfügbar."})

        stations = json.loads(match.group(1))
        results = []

        for item in stations:
            try:
                st_lon, st_lat = float(item[0]), float(item[1])
                name, html = item[2], item[3]
                
                soup = BeautifulSoup(html, 'html.parser')
                price_span = soup.find("span", class_="zahl")
                if not price_span: continue
                price_eur = float(price_span.get_text(strip=True).replace(",", ".").replace("9", "9", 1))

                # Distanz & Kosten
                air_km = calculate_distance(lat_start, lon_start, st_lat, st_lon)
                dist_km = air_km * 1.5 * 2 # Hin- und Rückweg
                
                travel_cost = dist_km * (consumption/100) * price_eur
                total_cost = (liters_fill * price_eur) + travel_cost

                p = soup.find("p")
                addr = list(p.stripped_strings)[1] if p and len(list(p.stripped_strings))>1 else ""

                results.append({
                    "name": name, "addr": addr, "price": price_eur,
                    "dist_total": dist_km, "total_cost": total_cost
                })
            except: continue

        results.sort(key=lambda x: x["total_cost"])
        return jsonify(results[:20])

    except Exception as e:
        return jsonify({"error": str(e)})

# Vercel benötigt dies nicht, aber gut für lokales Testen
if __name__ == '__main__':
    app.run(debug=True)