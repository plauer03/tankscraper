let currentLat = 0;
let currentLon = 0;
let currentStationData = null;

document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    // Keine automatische Suche beim Start, um die UI clean zu lassen (oder optional aktivieren)
});

// --- UI HELPERS ---
function handleEnter(e) {
    if(e.key === 'Enter') triggerSearch();
}

function switchTab(tabId, el) {
    if(el) {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        el.classList.add('active');
    }
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById('view-' + tabId).classList.add('active');
}

// --- SETTINGS ---
function loadSettings() {
    const settings = JSON.parse(localStorage.getItem('fuelApp_settings')) || { name: 'Mein Auto', cons: 7.5, tank: 50 };
    document.getElementById('car-name').value = settings.name;
    document.getElementById('car-cons').value = settings.cons;
    document.getElementById('car-tank').value = settings.tank;
    document.getElementById('header-car-name').innerText = settings.name;
}

function saveSettings() {
    const settings = {
        name: document.getElementById('car-name').value || 'Mein Auto',
        cons: parseFloat(document.getElementById('car-cons').value) || 7.5,
        tank: parseFloat(document.getElementById('car-tank').value) || 50
    };
    localStorage.setItem('fuelApp_settings', JSON.stringify(settings));
    loadSettings();
    switchTab('search');
}

// --- SUCHE ---
function locateMe() {
    const btn = document.querySelector('.geo-btn');
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<i class="ph-bold ph-spinner ph-spin"></i>';
    
    if(!navigator.geolocation) {
        alert("GPS nicht verfügbar");
        btn.innerHTML = originalContent;
        return;
    }
    
    navigator.geolocation.getCurrentPosition(pos => {
        currentLat = pos.coords.latitude;
        currentLon = pos.coords.longitude;
        btn.innerHTML = '<i class="ph-fill ph-navigation-arrow"></i>';
        document.getElementById('address-input').value = "Mein Standort";
        triggerSearch(); // Startet Suche mit Koordinaten
    }, err => {
        btn.innerHTML = originalContent;
        alert("Standortzugriff nicht erlaubt.");
    });
}

async function triggerSearch() {
    const inputVal = document.getElementById('address-input').value;
    const list = document.getElementById('results-list');
    const fuel = document.getElementById('fuel-type').value;
    const radius = document.getElementById('radius-select').value;
    const sort = document.getElementById('sort-select').value;

    // Modus entscheiden: Textsuche oder Koordinaten?
    // Wenn "Mein Standort" im Feld steht UND wir Koordinaten haben -> nimm Koordinaten
    // Sonst -> nimm Textadresse (Backend muss geocoding machen)
    
    let payload = { 
        fuel: fuel,
        radius : radius,
        sort : sort
    };
    
    if (inputVal === "Mein Standort" && currentLat !== 0) {
        payload.lat = currentLat;
        payload.lon = currentLon;
    } else if (inputVal.length > 2) {
        payload.address_text = inputVal; // Das Backend muss das nun verarbeiten!
        // Reset Coordinates to force backend geocoding
        payload.lat = 0; 
        payload.lon = 0;
    } else {
        return; // Nichts zu suchen
    }

    list.innerHTML = '<div class="empty-state"><i class="ph-bold ph-spinner ph-spin"></i></div>';

    try {
        const res = await fetch('/api/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        if(data.error) {
             list.innerHTML = `<div class="empty-state"><p>${data.error}</p></div>`;
             return;
        }
        
        renderList(data);
    } catch(e) {
        list.innerHTML = '<div class="empty-state"><p>Verbindungsfehler.</p></div>';
    }
}

function renderList(data) {
    const list = document.getElementById('results-list');
    list.innerHTML = '';
    
    if(!data || data.length === 0) {
        list.innerHTML = '<div class="empty-state"><p>Keine Ergebnisse.</p></div>';
        return;
    }

    data.forEach(item => {
        // CLEAN PRICE FORMATTING (Kein sup tag mehr)
        const pStr = item.price.toFixed(3);
        const mainP = pStr.substring(0, 4); // "1.68"
        const smallP = pStr.substring(4);   // "9"
        
        // Brand Avatar Color (Pseudo-Random basierend auf Name)
        const brandChar = (item.brand || "T").charAt(0).toUpperCase();
        
        const div = document.createElement('div');
        div.className = 'card-item';
        div.onclick = () => openDetail(item);
        
        div.innerHTML = `
            <div class="card-left">
                <div class="brand-avatar">${brandChar}</div>
                <div class="info-col">
                    <div class="station-name">${item.name}</div>
                    <div class="dist-pill">${item.dist.toFixed(1)} km</div>
                </div>
            </div>
            <div class="price-box">
                <span class="price-clean">${mainP}<span class="price-suffix">${smallP}</span></span>
            </div>
        `;
        list.appendChild(div);
    });
}

// --- DETAIL OVERLAY ---
function openDetail(item) {
    currentStationData = item;
    const settings = JSON.parse(localStorage.getItem('fuelApp_settings')) || {cons: 7.5, tank: 50};
    
    // Rechenlogik
    const distTotal = item.dist * 2 * 1.3; 
    const driveCost = (distTotal / 100) * settings.cons * item.price;
    const fillCost = settings.tank * item.price;
    const totalCost = fillCost + driveCost;
    const realPrice = totalCost / settings.tank;

    // Texte setzen
    document.getElementById('det-name').innerText = item.name;
    document.getElementById('det-address').innerText = item.street + ", " + item.place;
    document.getElementById('det-brand-pill').innerText = item.brand || "Tankstelle";

    // Preis schön
    const pStr = item.price.toFixed(3);
    document.getElementById('det-price').innerHTML = `${pStr.substring(0,4)}<small>${pStr.substring(4)}</small>`;
    
    // Stats
    document.getElementById('det-total').innerText = totalCost.toFixed(2) + '€';
    document.getElementById('det-real').innerText = realPrice.toFixed(2) + '€';
    document.getElementById('det-dist').innerText = (item.dist * 1.3).toFixed(1) + ' km';

    const overlay = document.getElementById('detail-overlay');
    overlay.style.display = 'flex';
    setTimeout(() => overlay.classList.add('open'), 10);
}

function closeDetail() {
    const overlay = document.getElementById('detail-overlay');
    overlay.classList.remove('open');
    setTimeout(() => overlay.style.display = 'none', 300);
}

function navigateExternal() {
    if(!currentStationData) return;
    const query = `${currentStationData.street}, ${currentStationData.place}`;
    // iOS nutzt maps: schema, Android geo: oder https
    const url = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
    window.open(url, '_blank');
}

// --- ROUTENPLANUNG ---

function swapRoute() {
    const start = document.getElementById('route-start');
    const end = document.getElementById('route-end');
    const temp = start.value;
    start.value = end.value;
    end.value = temp;
}

async function planRoute() {
    const start = document.getElementById('route-start').value;
    const end = document.getElementById('route-end').value;
    const fuel = document.getElementById('fuel-type').value; // Wir nutzen den globalen Filter
    const list = document.getElementById('route-results-list');
    
    if(!start || !end) return alert("Bitte Start und Ziel eingeben.");
    
    list.innerHTML = '<div class="empty-state"><i class="ph-bold ph-spinner ph-spin"></i><p>Berechne Route & lade Preise...</p></div>';
    
    try {
        const res = await fetch('/api/route', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ start: start, end: end, fuel: fuel })
        });
        
        const data = await res.json();
        
        if(data.error) {
             list.innerHTML = `<div class="empty-state"><p>${data.error}</p></div>`;
             return;
        }
        
        renderRouteList(data);
    } catch(e) {
        list.innerHTML = '<div class="empty-state"><p>Fehler bei der Routenberechnung.</p></div>';
    }
}

// Wir nutzen eine abgewandelte Liste für Routen, um den Text anzupassen
function renderRouteList(data) {
    const list = document.getElementById('route-results-list');
    list.innerHTML = '';
    
    if(!data || data.length === 0) {
        list.innerHTML = '<div class="empty-state"><p>Keine Tankstellen auf dieser Route gefunden.</p></div>';
        return;
    }

    data.forEach(item => {
        const pStr = item.price.toFixed(3);
        const mainP = pStr.substring(0, 4);
        const smallP = pStr.substring(4);
        const brandChar = (item.brand || "T").charAt(0).toUpperCase();
        
        const div = document.createElement('div');
        div.className = 'card-item';
        div.onclick = () => openDetail(item); // Das Overlay funktioniert auch hier!
        
        div.innerHTML = `
            <div class="card-left">
                <div class="brand-avatar">${brandChar}</div>
                <div class="info-col">
                    <div class="station-name">${item.name}</div>
                    <div class="dist-pill">Entlang der Route</div>
                </div>
            </div>
            <div class="price-box">
                <span class="price-clean">${mainP}<span class="price-suffix">${smallP}</span></span>
            </div>
        `;
        list.appendChild(div);
    });
}