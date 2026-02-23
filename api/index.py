from flask import Flask, request, jsonify, render_template_string
import requests
import re
import json
import math
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim

app = Flask(__name__)

# --- CONFIG ---
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36"}
FUEL_MAP = {"diesel": "diesel", "e5": "super-e5", "e10": "super-e10", "super": "super-e5"}

# --- HTML TEMPLATE (Direkt integriert für Stabilität) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fuel Calc Pro</title>
    <style>
        :root { --bg: #F9FAFB; --card: #FFFFFF; --text: #1F2937; --border: #E5E7EB; --primary: #000000; --accent: #10B981; }
        body { background-color: var(--bg); color: var(--text); font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 40px 20px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 700px; }
        h1 { font-weight: 800; text-align: center; margin-bottom: 30px; }
        .card { background: var(--card); border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); padding: 25px; margin-bottom: 20px; border: 1px solid var(--border); }
        label { display: block; font-size: 12px; font-weight: 700; text-transform: uppercase; color: #6B7280; margin-bottom: 6px; }
        input, select { width: 100%; padding: 12px; font-size: 16px; border: 1px solid var(--border); border-radius: 8px; box-sizing: border-box; outline: none; margin-bottom: 15px; }
        input:focus { border-color: var(--primary); }
        .row { display: flex; gap: 15px; } .col { flex: 1; }
        button { width: 100%; background: var(--primary); color: white; font-weight: 700; padding: 14px; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; }
        button:hover { opacity: 0.9; }
        .suggestions { position: absolute; background: white; border: 1px solid var(--border); border-radius: 8px; width: 100%; max-width: 650px; z-index: 100; display: none; margin-top: -10px; box-shadow: 0 10px 15px rgba(0,0,0,0.1); }
        .suggestion-item { padding: 12px; cursor: pointer; border-bottom: 1px solid #eee; }
        .suggestion-item:hover { background: #f9f9f9; }
        .result-item { background: white; border: 1px solid var(--border); border-radius: 10px; padding: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .result-item.best { border: 2px solid var(--accent); background: #ECFDF5; }
        .res-total { font-size: 20px; font-weight: 800; }
        .res-liter { color: var(--accent); font-weight: 700; }
        .loader { text-align: center; display: none; padding: 20px; color: #666; }
        @media(max-width: 600px) { .row { flex-direction: column; gap: 0; } }
    </style>
</head>
<body>
<div class="container">
    <div class="card">
        <label>Startadresse</label>
        <div style="position:relative">
            <input type="text" id="address" placeholder="Adresse eingeben (z.B. Berlin)" autocomplete="off">
            <div class="suggestions" id="suggestions"></div>
        </div>
        <input type="hidden" id="lat" value="0"><input type="hidden" id="lon" value="0"><input type="hidden" id="plz" value="">
        <div class="row">
            <div class="col"><label>Sorte</label><select id="fuel"><option value="e10">E10</option><option value="e5">E5</option><option value="diesel">Diesel</option></select></div>
            <div class="col"><label>Menge (L)</label><input type="number" id="liters" value="50"></div>
            <div class="col"><label>Verbrauch</label><input type="number" id="cons" value="7.5" step="0.1"></div>
        </div>
        <button onclick="search()">Preise vergleichen</button>
    </div>
    <div id="loader">Lade Daten...</div>
    <div id="results"></div>
</div>
<script>
    const addrIn = document.getElementById('address');
    const suggBox = document.getElementById('suggestions');
    let timer;
    addrIn.addEventListener('input', () => {
        clearTimeout(timer);
        document.getElementById('lat').value = "0";
        if(addrIn.value.length < 3) { suggBox.style.display='none'; return; }
        timer = setTimeout(async () => {
            const res = await fetch(`/api/autocomplete?q=${encodeURIComponent(addrIn.value)}`);
            const data = await res.json();
            suggBox.innerHTML = '';
            if(data.length) {
                suggBox.style.display='block';
                data.forEach(i => {
                    const div = document.createElement('div');
                    div.className = 'suggestion-item';
                    let txt = [i.properties.name, i.properties.street, i.properties.postcode, i.properties.city].filter(Boolean).join(', ');
                    div.innerText = txt;
                    div.onclick = () => {
                        addrIn.value = txt;
                        document.getElementById('lat').value = i.geometry.coordinates[1];
                        document.getElementById('lon').value = i.geometry.coordinates[0];
                        if(i.properties.postcode) document.getElementById('plz').value = i.properties.postcode;
                        suggBox.style.display='none';
                    };
                    suggBox.appendChild(div);
                });
            }
        }, 300);
    });
    document.onclick = (e) => { if(e.target !== addrIn) suggBox.style.display='none'; };
    async function search() {
        document.getElementById('loader').style.display='block';
        document.getElementById('results').innerHTML = '';
        try {
            const res = await fetch('/api/search', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({
                    address_text: addrIn.value, lat: document.getElementById('lat').value,
                    lon: document.getElementById('lon').value, plz_hint: document.getElementById('plz').value,
                    fuel: document.getElementById('fuel').value, liters: document.getElementById('liters').value,
                    cons: document.getElementById('cons').value
                })
            });
            const data = await res.json();
            document.getElementById('loader').style.display='none';
            if(data.error) return alert(data.error);
            let html = '';
            data.forEach((item, idx) => {
                const best = idx===0 ? 'best' : '';
                html += `<div class="result-item ${best}">
                    <div><div style="font-weight:bold">${item.name}</div><div style="font-size:13px;color:#666">${item.addr}</div><div style="font-size:12px;margin-top:4px">🚗 ${item.dist_total.toFixed(1)} km (Total)</div></div>
                    <div style="text-align:right"><div class="res-total">${item.total_cost.toFixed(2)}€</div><div style="font-size:12px;color:#999">Gesamt</div><div class="res-liter">${item.price.toFixed(3)}€ / L</div></div>
                </div>`;
            });
            document.getElementById('results').innerHTML = html;
        } catch(e) { alert("Fehler"); document.getElementById('loader').style.display='none'; }
    }
</script>
</body>
</html>
"""

# --- BACKEND LOGIC ---
def get_coordinates_backend(address):
    try:
        geolocator = Nominatim(user_agent="fuel_v3_vercel")
        location = geolocator.geocode(address, timeout=5)
        if location:
            plz = None
            if 'address' in location.raw:
                plz = location.raw['address'].get('postcode')
            return location.latitude, location.longitude, plz
        return None, None, None
    except: return None, None, None

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

# --- ROUTES ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/autocomplete')
def autocomplete():
    query = request.args.get('q', '')
    if not query: return jsonify([])
    try:
        r = requests.get(f"https://photon.komoot.io/api/?q={query}&lang=de&limit=5&bbox=5.8,47.2,15.1,55.1", timeout=3)
        return jsonify(r.json().get('features', []))
    except: return jsonify([])

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.json
    lat_start = float(data.get('lat') or 0)
    lon_start = float(data.get('lon') or 0)
    address_text = data.get('address_text', '')
    plz_hint = data.get('plz_hint')

    if lat_start == 0 or lon_start == 0:
        lat_start, lon_start, found_plz = get_coordinates_backend(address_text)
        if found_plz and not plz_hint: plz_hint = found_plz
    
    if not lat_start: return jsonify({"error": "Adresse nicht gefunden."})

    final_plz = plz_hint
    if not final_plz:
        match = re.search(r'\b\d{5}\b', address_text)
        if match: final_plz = match.group(0)
    
    if not final_plz: return jsonify({"error": "Keine PLZ gefunden."})

    slug = find_region_slug(final_plz)
    if not slug: return jsonify({"error": "Region nicht gefunden."})

    fuel = data.get('fuel')
    liters = float(data.get('liters'))
    cons = float(data.get('cons'))
    
    try:
        clean_fuel = FUEL_MAP.get(fuel, "super-e5")
        resp = requests.get(f"https://ich-tanke.de/tankstellen/{clean_fuel}/umkreis/{slug}/", headers=HEADERS, timeout=8)
        match = re.search(r'var tankstellen\s*=\s*(\[.*?\]);', resp.text, re.DOTALL)
        if not match: return jsonify({"error": "Keine Live-Daten."})

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

                dist_km = calculate_distance(lat_start, lon_start, st_lat, st_lon) * 1.5 * 2
                travel_cost = dist_km * (cons/100) * price_eur
                total = (liters * price_eur) + travel_cost
                
                p = soup.find("p")
                addr = list(p.stripped_strings)[1] if p and len(list(p.stripped_strings))>1 else ""
                results.append({"name": name, "addr": addr, "price": price_eur, "dist_total": dist_km, "total_cost": total})
            except: continue

        results.sort(key=lambda x: x["total_cost"])
        return jsonify(results[:20])
    except Exception as e: return jsonify({"error": str(e)})