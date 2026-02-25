from flask import Flask, request, jsonify, render_template
import requests
import os
from geopy.geocoders import Nominatim # <--- WICHTIG: Das hier hat gefehlt

app = Flask(__name__, static_folder='../static', template_folder='../templates')

# --- CONFIG ---
TANKERKOENIG_API_KEY = os.environ.get("TK_API_KEY")  
HEADERS = {"User-Agent": "FuelCalcPro/PWA"}

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
    
    # FALLBACK: Wenn keine Koordinaten, aber Text da ist -> Geocoding
    if (lat == 0 or lon == 0) and address_text:
        try:
            geolocator = Nominatim(user_agent="fuel_app_v2")
            location = geolocator.geocode(address_text, timeout=5)
            if location:
                lat = location.latitude
                lon = location.longitude
            else:
                return jsonify({"error": "Ort nicht gefunden"}), 404
        except:
            return jsonify({"error": "Geocoding Service Fehler"}), 500

    # Wenn immer noch keine Koordinaten -> Abbruch
    if lat == 0 or lon == 0:
        return jsonify({"error": "Keine Koordinaten"}), 400

    # Tankerkönig API Logic
    tk_type = "e5" if fuel_type == "super" else fuel_type
    url = "https://creativecommons.tankerkoenig.de/json/list.php"
    params = {
        "lat": lat, "lng": lon, "rad": 10,
        "sort": "price", "type": tk_type, "apikey": TANKERKOENIG_API_KEY
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
                "dist": st['dist']
            })
        return jsonify(cleaned)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')