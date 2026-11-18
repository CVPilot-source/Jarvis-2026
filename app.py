import os
import re
import time
import json
import base64
import asyncio
import urllib.request
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, Response
from google import genai
from google.genai import types
import edge_tts

app = Flask(__name__)
ICAL_CACHE = {"ts": 0, "events": []}

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="115" fill="#090A0F"/>
  <circle cx="256" cy="256" r="155" fill="none" stroke="#38BDF8" stroke-width="8" stroke-dasharray="16 10"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#F59E0B" stroke-width="5"/>
  <circle cx="256" cy="256" r="24" fill="#F59E0B"/>
</svg>"""

HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#090A0F">
    <link rel="manifest" href="/manifest.json">
    <title>NEO // Enterprise Intelligence OS</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --accent: #38BDF8;
            --accent-glow: rgba(56, 189, 248, 0.15);
            --orange: #F59E0B;
            --bg: #090A0F;
            --card-bg: #12141C;
            --card-border: rgba(255, 255, 255, 0.08);
            --card-hover: #181B26;
            --text: #F8FAFC;
            --muted: #94A3B8;
            --success: #10B981;
            --whatsapp: #25D366;
        }

        body.listening { --accent: #10B981; --accent-glow: rgba(16, 185, 129, 0.2); }
        body.thinking  { --accent: #38BDF8; --accent-glow: rgba(56, 189, 248, 0.2); }
        body.speaking  { --accent: #8B5CF6; --accent-glow: rgba(139, 92, 246, 0.2); }

        * { box-sizing: border-box; user-select: none; -webkit-tap-highlight-color: transparent; }

        html, body {
            margin: 0; padding: 0; width: 100vw; height: 100vh; overflow-x: hidden;
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Inter', sans-serif;
        }

        .app-header {
            display: flex; justify-content: space-between; align-items: center;
            min-height: 56px; padding: 8px 16px; background: var(--card-bg);
            border-bottom: 1px solid var(--card-border); flex-wrap: wrap; gap: 8px;
        }
        .brand { display: flex; align-items: center; gap: 8px; }
        .brand-logo { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 10px var(--accent); }
        .brand-name { font-weight: 700; font-size: 13px; letter-spacing: 0.5px; color: #fff; }
        
        .header-info { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .weather-badge, .live-clock {
            font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--accent);
            background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.2);
            padding: 4px 8px; border-radius: 6px; display: flex; align-items: center; gap: 4px;
        }
        .status-pill {
            display: flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.03);
            border: 1px solid var(--card-border); padding: 4px 10px; border-radius: 16px;
            font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--muted);
        }
        .status-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--success); }

        .app-container {
            display: grid;
            grid-template-columns: 280px 1fr 280px;
            gap: 14px;
            padding: 14px;
            height: calc(100vh - 56px);
            max-width: 1600px;
            margin: 0 auto;
            overflow-y: auto;
        }

        @media(max-width: 1024px) {
            .app-container { grid-template-columns: 1fr; height: auto; padding: 10px; }
            html, body { height: auto; overflow-y: auto; }
        }

        .panel {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .section-title {
            font-family: 'JetBrains Mono', monospace; font-size: 10.5px; font-weight: 500;
            text-transform: uppercase; letter-spacing: 1px; color: var(--muted);
            border-bottom: 1px solid var(--card-border); padding-bottom: 6px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .nav-card {
            background: rgba(255,255,255,0.015);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 10px 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex; flex-direction: column; gap: 3px;
        }
        .nav-card:hover {
            background: var(--card-hover);
            border-color: rgba(255,255,255,0.15);
        }
        .nav-card-title { font-weight: 600; font-size: 13px; color: #fff; display: flex; justify-content: space-between; align-items: center; }
        .nav-card-desc { font-size: 11.5px; color: var(--muted); line-height: 1.3; }

        .core-display {
            background: linear-gradient(180deg, #12141C 0%, #0D0F17 100%);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
            text-align: center;
            position: relative;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }

        .neural-orb-container {
            width: 140px; height: 140px;
            display: flex; align-items: center; justify-content: center;
            cursor: pointer; position: relative; margin: 10px 0;
        }
        .orb-ring {
            position: absolute; inset: 0; border-radius: 50%;
            border: 1px solid var(--accent); opacity: 0.3;
            animation: pulseOrb 3s infinite ease-in-out;
        }
        .orb-ring:nth-child(2) { inset: -12px; opacity: 0.15; animation-delay: 1s; }
        .orb-core {
            width: 70px; height: 70px; border-radius: 50%;
            background: radial-gradient(circle, var(--accent) 0%, rgba(56,189,248,0.2) 60%, transparent 100%);
            box-shadow: 0 0 30px var(--accent-glow);
            transition: all 0.3s ease;
        }
        @keyframes pulseOrb {
            0% { transform: scale(0.95); opacity: 0.2; }
            50% { transform: scale(1.08); opacity: 0.5; }
            100% { transform: scale(0.95); opacity: 0.2; }
        }

        .core-prompt { font-size: 16px; font-weight: 600; color: #fff; margin-bottom: 4px; }
        .core-sub { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--muted); margin-bottom: 14px; }
        
        .primary-btn {
            background: #fff; color: #090A0F; border: none;
            padding: 8px 20px; border-radius: 6px; font-weight: 600; font-size: 12.5px;
            cursor: pointer; transition: all 0.2s; font-family: 'Inter', sans-serif;
        }
        .primary-btn:hover { background: #E2E8F0; }

        .activity-log {
            width: 100%; background: rgba(0,0,0,0.3); border: 1px solid var(--card-border);
            border-radius: 6px; padding: 8px 12px; font-family: 'JetBrains Mono', monospace;
            font-size: 11px; color: var(--accent); text-align: left; margin-top: 14px;
        }

        .modal-backdrop {
            position: fixed; inset: 0; background: rgba(9, 10, 15, 0.85);
            backdrop-filter: blur(6px); z-index: 100; display: none;
            align-items: center; justify-content: center; padding: 16px;
        }
        .modal-backdrop.open { display: flex; }
        .modal-box {
            background: var(--card-bg); border: 1px solid var(--card-border);
            border-radius: 12px; width: 100%; max-width: 400px; padding: 20px;
            display: flex; flex-direction: column; gap: 12px;
            box-shadow: 0 16px 32px rgba(0,0,0,0.6);
        }
        .modal-header {
            display: flex; justify-content: space-between; align-items: center;
            font-weight: 600; font-size: 13.5px; color: #fff;
            border-bottom: 1px solid var(--card-border); padding-bottom: 8px;
        }
        .modal-content { max-height: 260px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
        .modal-row { background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); padding: 8px 10px; border-radius: 6px; }
        
        input, select, textarea {
            background: #090A0F; border: 1px solid var(--card-border); color: #fff;
            padding: 8px 10px; border-radius: 6px; font-family: 'Inter', sans-serif; font-size: 13px; outline: none; width: 100%;
        }
        input:focus, select:focus, textarea:focus { border-color: var(--accent); }
    </style>
</head>
<body>
    <header class="app-header">
        <div class="brand">
            <div class="brand-logo"></div>
            <span class="brand-name">NEO // ENTERPRISE OS</span>
        </div>
        <div class="header-info">
            <div class="weather-badge" id="weatherDisplay">🌡️ Hamburg: Lade...</div>
            <div class="live-clock" id="liveClockDisplay">--:--:--</div>
            <div class="status-pill">
                <div class="status-dot"></div>
                <span>ACTIVE</span>
            </div>
        </div>
    </header>

    <div class="app-container">
        <!-- LEFT PANEL -->
        <div class="panel">
            <div class="section-title"><span>Operations</span> <span id="eventCountBadge" style="color:var(--accent);">0 Termine</span></div>
            
            <div class="nav-card" onclick="quickCmd('Gib mir mein Morning Briefing mit Terminen heute.')">
                <div class="nav-card-title"><span>☀️ Morning Brief</span> <span style="font-size:9.5px; color:var(--accent);">API</span></div>
                <div class="nav-card-desc">Tagesübersicht und Einsätze in Hamburg.</div>
            </div>

            <div class="nav-card" onclick="openModal('calendar')">
                <div class="nav-card-title"><span>📅 Kalender Sync</span> <span style="font-size:9.5px; color:var(--success);">LIVE</span></div>
                <div class="nav-card-desc">Einsätze und Objektstandorte verwalten.</div>
            </div>

            <div class="nav-card" onclick="openModal('codes')">
                <div class="nav-card-title"><span>🔐 Objekt-Codes</span> <span id="codeCountBadge" style="font-size:9.5px; color:var(--orange);">0 Codes</span></div>
                <div class="nav-card-desc">Sichere Notizen und Zugangscodes.</div>
            </div>
        </div>

        <!-- CENTER CORE -->
        <div class="core-display">
            <div style="font-family:'JetBrains Mono'; font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:1px;">Neural Voice Interface</div>
            
            <div class="neural-orb-container" onclick="toggleListening()">
                <div class="orb-ring"></div>
                <div class="orb-ring"></div>
                <div class="orb-core"></div>
            </div>

            <div class="core-prompt" id="corePrompt">Sage: „Hey Neo“</div>
            <div class="core-sub" id="coreSub">Lauscht im Hintergrund</div>
            
            <button class="primary-btn" onclick="toggleListening()">Sprachbefehl starten</button>

            <div class="activity-log" id="activityLog">
                > System initialisiert. Bereit für Befehle...
            </div>
        </div>

        <!-- RIGHT PANEL -->
        <div class="panel">
            <div class="section-title"><span>Business Tools</span> <span style="color:var(--success);">31.50 €/h</span></div>

            <div class="nav-card" onclick="openModal('calc')">
                <div class="nav-card-title"><span>📐 Angebots-Rechner</span> <span style="font-size:9.5px; color:var(--accent);">PRO</span></div>
                <div class="nav-card-desc">Kalkulation für Kunden in Hamburg.</div>
            </div>

            <div class="nav-card" onclick="openModal('whatsapp')">
                <div class="nav-card-title"><span>💬 WhatsApp Business</span> <span style="font-size:9.5px; color:var(--whatsapp);">DIREKT</span></div>
                <div class="nav-card-desc">Nachricht direkt an Kunden öffnen.</div>
            </div>

            <div class="nav-card" onclick="sendTelegramAuth()">
                <div class="nav-card-title"><span>✈️ Telegram Auth</span> <span style="font-size:9.5px; color:var(--orange);">SECURE</span></div>
                <div class="nav-card-desc">Echtzeit-Freigabe über Telegram Bot.</div>
            </div>
        </div>
    </div>

    <!-- MODAL -->
    <div class="modal-backdrop" id="appModal">
        <div class="modal-box">
            <div class="modal-header">
                <span id="modalTitle">DATEN</span>
                <button onclick="closeModal()" style="background:none; border:none; color:var(--muted); cursor:pointer; font-size:16px;">✕</button>
            </div>
            <div class="modal-content" id="modalBody"></div>
        </div>
    </div>

    <input type="file" id="cam" accept="image/*" style="display:none" onchange="handleImage(event)">
    <audio id="audioPlayer" playsinline></audio>

    <script>
        function updateClock() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('de-DE');
            const dateStr = now.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' });
            document.getElementById('liveClockDisplay').innerText = `${dateStr}, ${timeStr}`;
        }
        setInterval(updateClock, 1000);
        updateClock();

        fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true')
            .then(r => r.json())
            .then(data => {
                if (data && data.current_weather) {
                    const temp = data.current_weather.temperature;
                    document.getElementById('weatherDisplay').innerText = `🌡️ Hamburg: ${temp}°C`;
                }
            }).catch(() => {
                document.getElementById('weatherDisplay').innerText = `🌡️ Hamburg: Aktiv`;
            });

        let isRecording = false, isSpeaking = false, inConversation = false;
        let mediaRecorder = null, audioStream = null, wakeRecognition = null;
        let eventsCache = [];
        const audioPlayer = document.getElementById('audioPlayer');
        const corePrompt = document.getElementById('corePrompt');
        const coreSub = document.getElementById('coreSub');
        const activityLog = document.getElementById('activityLog');

        fetch('/calendar_preview').then(r => r.json()).then(d => { 
            eventsCache = d.events || []; 
            document.getElementById('eventCountBadge').innerText = eventsCache.length + " Termine";
        }).catch(()=>{});

        let localMemory = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        document.getElementById('codeCountBadge').innerText = localMemory.length + " Codes";

        function logActivity(text) {
            activityLog.innerText = "> " + text;
        }

        function openModal(type) {
            const modal = document.getElementById('appModal');
            const title = document.getElementById('modalTitle');
            const body = document.getElementById('modalBody');
            modal.classList.add('open');

            if (type === 'calendar') {
                title.innerText = 'KALENDER TERMINE';
                body.innerHTML = eventsCache.length
                    ? eventsCache.map(e => `<div class="modal-row"><div style="color:var(--orange); font-size:11px; font-family:'JetBrains Mono';">${e.time}</div><div style="font-weight:600; margin-top:2px;">${e.title}</div><div style="color:var(--muted); font-size:11px; margin-top:2px;">${e.loc||''}</div></div>`).join('')
                    : '<div style="color:var(--muted);">Keine Termine gefunden.</div>';
            } else if (type === 'codes') {
                title.innerText = `OBJEKT-CODES (${localMemory.length})`;
                let list = localMemory.length ? localMemory.map((x, i) => `<div class="modal-row" style="display:flex; justify-content:space-between; align-items:center;"><span>${x}</span><button onclick="localMemory.splice(${i},1);localStorage.setItem('neo_memory',JSON.stringify(localMemory));document.getElementById('codeCountBadge').innerText = localMemory.length + ' Codes';openModal('codes');" style="background:none;border:none;color:var(--muted);cursor:pointer;">✕</button></div>`).join('') : '<div style="color:var(--muted);">Keine Codes gespeichert.</div>';
                body.innerHTML = `<div style="display:flex; gap:8px; margin-bottom:4px;"><input id="inputCode" type="text" placeholder="Neuer Code..." style="flex:1;"><button class="primary-btn" onclick="if(document.getElementById('inputCode').value.trim()){localMemory.push(document.getElementById('inputCode').value.trim());localStorage.setItem('neo_memory',JSON.stringify(localMemory));document.getElementById('codeCountBadge').innerText = localMemory.length + ' Codes';openModal('codes');}">Speichern</button></div>` + list;
            } else if (type === 'calc') {
                title.innerText = 'ANGEBOTS-KALKULATOR';
                body.innerHTML = `<div style="display:flex; flex-direction:column; gap:10px;">
                    <label>Fläche in m²:</label>
                    <input id="calcQm" type="number" value="600" oninput="calculatePreview()">
                    <label>Stundensatz (€/h):</label>
                    <input id="calcRate" type="number" step="0.5" value="31.50" oninput="calculatePreview()">
                    <select id="calcFreq">
                        <option value="1x pro Woche">1x pro Woche</option>
                        <option value="2x pro Woche" selected>2x pro Woche</option>
                        <option value="3x pro Woche">3x pro Woche</option>
                        <option value="5x pro Woche">5x pro Woche</option>
                    </select>
                    <div id="calcPreview" style="color:var(--orange); font-family:'JetBrains Mono'; font-weight:bold; font-size:12px;"></div>
                    <button class="primary-btn" onclick="closeModal(); quickCmd('Kalkuliere ein Reinigungsangebot für '+document.getElementById('calcQm').value+' m², '+document.getElementById('calcFreq').value+', Stundensatz '+document.getElementById('calcRate').value+' Euro, und erstelle den Angebotstext.');">Angebot erstellen</button>
                </div>`;
                calculatePreview();
            } else if (type === 'whatsapp') {
                title.innerText = 'WHATSAPP DIREKT VERSAND';
                body.innerHTML = `<div style="display:flex; flex-direction:column; gap:10px;">
                    <input id="waPhone" type="text" placeholder="Nummer mit Ländercode (z.B. 4917...)">
                    <textarea id="waText" rows="4" placeholder="Nachricht an den Kunden..."></textarea>
                    <button class="primary-btn" onclick="openWhatsAppDirect()">WhatsApp öffnen & Senden</button>
                </div>`;
            }
        }
        
        function calculatePreview() {
            const qm = parseFloat(document.getElementById('calcQm').value) || 0;
            const rate = parseFloat(document.getElementById('calcRate').value) || 31.50;
            const hours = (qm / 350) * 8.66; // approx monthly
            const total = hours * rate;
            const el = document.getElementById('calcPreview');
            if(el) el.innerText = `Monatlich ca. ${total.toLocaleString('de-DE', {minimumFractionDigits: 2, maximumFractionDigits: 2})} € netto`;
        }

        function closeModal() { document.getElementById('appModal').classList.remove('open'); }

        function openWhatsAppDirect() {
            const phone = document.getElementById('waPhone').value.trim().replace(/[^0-9]/g, '');
            const text = document.getElementById('waText').value.trim();
            if(!phone || !text) return;
            closeModal();
            logActivity("Öffne WhatsApp Business...");
            const url = `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
            window.open(url, '_blank');
        }

        async function sendTelegramAuth() {
            logActivity("Sende Telegram Authentifizierung...");
            try {
                const res = await fetch('/telegram_notify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:"📞 NEO Autorisierung angefordert!"}) });
                const data = await res.json();
                logActivity(data.ok ? "Telegram Freigabe gesendet." : "Fehler: " + (data.error || "Unbekannt"));
            } catch(e) { logActivity("Verbindungsfehler zu Telegram."); }
        }

        function handleImage(e) {
            const file = e.target.files[0]; if(!file) return;
            logActivity("Lade Mängel-Foto hoch...");
            const reader = new FileReader();
            reader.onload = evt => sendBackend({ image: evt.target.result.split(',')[1], message: "Erstelle einen professionellen Mängelbericht." });
            reader.readAsDataURL(file);
        }

        function startWakeWord() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) return;
            try {
                wakeRecognition = new SpeechRecognition();
                wakeRecognition.lang = 'de-DE'; wakeRecognition.continuous = true; wakeRecognition.interimResults = true;
                wakeRecognition.onresult = (e) => {
                    for (let i = e
