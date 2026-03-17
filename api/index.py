from flask import Flask, request, jsonify, render_template
import requests
import os
from geopy.geocoders import Nominatim

app = Flask(__name__, static_folder='../static', template_folder='../templates')

# --- CONFIG ---
TANKERKOENIG_API_KEY = os.environ.get("TK_API_KEY")

# --- brand mapping
BRAND_DOMAIN_MAP = {
    # 🇩🇪 
    "aral": "aral.de",
    "shell": "shell.com",
    "bp": "bp.com",
    "esso": "esso.de",
    "total": "totalenergies.com",
    "totalenergies": "totalenergies.com",
    "jet": "jet-tankstellen.de",
    "star": "star.de",
    "avia": "avia.de",
    "hem": "hem-tankstelle.de",
    "bft": "bft.de",
    "q1": "q1.eu",
    "markant": "markant-tankstellen.de",
    "ratio": "ratio-tankstellen.de",
    "globus": "globus.de",
    "edeka": "edeka.de",
    "rewe": "rewe.de",

    # international
    "eni": "eni.com",
    "agip": "eni.com",
    "agpi eni": "eni.com",
    "omv": "omv.com",
    "orlen": "orlen.pl",
    "circle k": "circlek.com",
    "texaco": "texaco.com",
    "gulf": "gulf.com",

    # 🇫🇷 / 🇪🇸 / 🇮🇹 etc.
    "cepsa": "cepsa.com",
    "repsol": "repsol.com",

    # 🇳🇱 / 🇧🇪
    "tango": "tango.nl",

    # fallback keys
    "": None,
    None: None
}

def get_logo_url(brand):
    if not brand:
        return None
    
    domain = BRAND_DOMAIN_MAP.get(brand.lower())
    if not domain:
        return None
    
    return f"https://img.logo.dev/{domain}?token=pk_JxklmdOOSI6pJKAAMx3TQA"
# -----------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search():
    data = request.json
    lat = float(data.get('lat') or 0)
    lon = float(data.get('lon') or 0)
    address_text = data.get('address_text')
    
    fuel_type = data.get('fuel', 'e5')
    radius = data.get('radius', 10)
    sort_by = data.get('sort', 'price')
    
    if (lat == 0 or lon == 0) and address_text:
        try:
            geolocator = Nominatim(user_agent="fuel_app_v3")
            location = geolocator.geocode(address_text, timeout=5)
            if location:
                lat = location.latitude
                lon = location.longitude
            else:
                return jsonify({"error": "Ort nicht gefunden"}), 404
        except:
            return jsonify({"error": "Geocoding Fehler"}), 500

    if lat == 0 or lon == 0:
        return jsonify({"error": "Keine Koordinaten"}), 400

    tk_type = "e5" if fuel_type == "super" else fuel_type
    url = "https://creativecommons.tankerkoenig.de/json/list.php"
    
    params = {
        "lat": lat, "lng": lon, "rad": radius,
        "sort": sort_by, "type": tk_type, "apikey": TANKERKOENIG_API_KEY
    }
    
    try:
        r = requests.get(url, params=params, timeout=5)
        api_data = r.json()
        if not api_data.get('ok'): 
            return jsonify({"error": api_data.get('message', 'API Error')}), 500
        
        cleaned = []
        for st in api_data.get('stations', []):
            if not st['isOpen']: continue
            cleaned.append({
                "name": st['name'],
                "brand": st['brand'],
                "street": st['street'],
                "place": st['place'],
                "price": st['price'],
                "dist": st['dist'],
                "logo": get_logo_url(st['brand'])
            })
        return jsonify(cleaned)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/route', methods=['POST'])
def route_search():
    data = request.json
    start_text = data.get('start')
    end_text = data.get('end')
    fuel_type = data.get('fuel', 'e10')
    tk_type = "e5" if fuel_type == "super" else fuel_type

    if not start_text or not end_text:
        return jsonify({"error": "Start und Ziel erforderlich."}), 400

    try:
        geolocator = Nominatim(user_agent="fuel_app_route")
        start_loc = geolocator.geocode(start_text, timeout=5)
        end_loc = geolocator.geocode(end_text, timeout=5)

        if not start_loc or not end_loc:
            return jsonify({"error": "Start oder Ziel nicht gefunden."}), 404

        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{start_loc.longitude},{start_loc.latitude};{end_loc.longitude},{end_loc.latitude}?overview=simplified&geometries=geojson"
        osrm_res = requests.get(osrm_url, timeout=8).json()

        if osrm_res.get('code') != 'Ok':
            return jsonify({"error": "Route konnte nicht berechnet werden."}), 500

        coordinates = osrm_res['routes'][0]['geometry']['coordinates']
        mid_index = len(coordinates) // 2
        
        points_to_check = [
            (start_loc.latitude, start_loc.longitude),
            (coordinates[mid_index][1], coordinates[mid_index][0]),
            (end_loc.latitude, end_loc.longitude)
        ]

        all_stations = {}
        for lat, lon in points_to_check:
            tk_url = "https://creativecommons.tankerkoenig.de/json/list.php"
            params = {
                "lat": lat, "lng": lon, "rad": 10,
                "sort": "price", "type": tk_type, "apikey": TANKERKOENIG_API_KEY
            }
            
            r = requests.get(tk_url, params=params, timeout=5)
            tk_data = r.json()
            
            if tk_data.get('ok'):
                for st in tk_data.get('stations', []):
                    if st['isOpen']:
                        all_stations[st['id']] = {
                            "name": st['name'], "brand": st['brand'],
                            "street": st['street'], "place": st['place'],
                            "price": st['price'], "dist": st['dist']
                        }

        results = list(all_stations.values())
        results.sort(key=lambda x: x['price'])
        return jsonify(results[:20])

    except Exception as e:
        return jsonify({"error": f"Server Fehler: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')