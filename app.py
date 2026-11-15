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
  <rect width="512" height="512" rx="115" fill="#030508"/>
  <circle cx="256" cy="256" r="155" fill="none" stroke="#00f3ff" stroke-width="8" stroke-dasharray="16 10"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#ff9900" stroke-width="5"/>
  <circle cx="256" cy="256" r="24" fill="#ff9900"/>
</svg>"""

HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#030508">
    <link rel="manifest" href="/manifest.json">
    <title>NEO // ENTERPRISE OS - COMMAND CENTER</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Courier+New:wght@400;700&family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --bg-deep: #030508;
            --hud-panel: rgba(4, 14, 28, 0.9);
            --neon-cyan: #00f3ff;
            --neon-purple: #b000ff;
            --neon-orange: #ff9900;
            --text-main: #e0fbfc;
            --text-dim: #7986ab;
            --border-glow: rgba(0, 243, 255, 0.45);
        }

        * { box-sizing: border-box; user-select: none; -webkit-tap-highlight-color: transparent; }

        html, body {
            margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden;
            background-color: var(--bg-deep);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            background-image: 
                radial-gradient(circle at 50% 50%, rgba(0, 243, 255, 0.08) 0%, transparent 90%),
                linear-gradient(rgba(0,243,255,0.025) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0,243,255,0.025) 1px, transparent 1px);
            background-size: 100% 100%, 30px 30px, 30px 30px;
        }

        .desktop-view { display: none; width: 100vw; height: 100vh; }
        .mobile-view { display: block; width: 100vw; height: 100vh; overflow-y: auto; }

        @media (min-width: 1024px) {
            .desktop-view { display: flex; flex-direction: column; justify-content: space-between; padding: 15px; }
            .mobile-view { display: none; }
        }

        /* ================= MOBILE VIEW ================= */
        .mobile-container {
            max-width: 480px; margin: 0 auto; padding: 15px; min-height: 100vh;
            display: flex; flex-direction: column; justify-content: space-between;
        }
        .mobile-header {
            background: var(--hud-panel); border: 1px solid var(--border-glow);
            border-radius: 12px; padding: 12px 15px; display: flex; justify-content: space-between; align-items: center;
            backdrop-filter: blur(12px); box-shadow: 0 0 20px rgba(0, 243, 255, 0.15);
        }
        .mobile-core-box { text-align: center; margin: 15px 0; position: relative; }
        .core-pulse {
            width: 95px; height: 95px;
            background: radial-gradient(circle, var(--neon-cyan) 0%, rgba(176,0,255,0.4) 70%, transparent 100%);
            border-radius: 50%; margin: 0 auto 10px auto;
            box-shadow: 0 0 35px var(--neon-cyan); animation: pulseCore 3s infinite alternate;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
            border: 2px solid var(--neon-cyan);
        }
        .core-pulse::after {
            content: ''; width: 55px; height: 55px; border: 2px dashed var(--text-main);
            border-radius: 50%; animation: spin 12s linear infinite;
        }
        @keyframes pulseCore {
            0% { transform: scale(0.95); box-shadow: 0 0 20px var(--neon-cyan); }
            100% { transform: scale(1.06); box-shadow: 0 0 45px var(--neon-cyan); }
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .voice-bar {
            background: var(--hud-panel); border: 1px solid var(--border-glow);
            border-radius: 20px; padding: 8px 15px; font-size: 11px; color: var(--neon-cyan);
            display: inline-block; box-shadow: 0 0 10px rgba(0,243,255,0.15);
        }
        .mobile-cards { display: flex; flex-direction: column; gap: 10px; margin-bottom: 15px; }
        .m-card {
            background: var(--hud-panel); border: 1px solid rgba(0, 243, 255, 0.25);
            border-radius: 12px; padding: 12px 14px; backdrop-filter: blur(10px); cursor: pointer;
        }
        .m-card h3 { font-size: 11px; color: var(--neon-orange); margin-bottom: 4px; display: flex; justify-content: space-between; }
        .m-card p { font-size: 11px; color: var(--text-dim); }
        .calc-box input {
            width: 100%; background: rgba(0,0,0,0.6); border: 1px solid var(--border-glow);
            color: var(--text-main); padding: 6px 8px; border-radius: 6px; margin-top: 4px; font-size: 12px;
        }
        .calc-result { margin-top: 6px; font-size: 12px; color: var(--neon-orange); font-weight: bold; }
        .action-btn {
            display: block; width: 100%; background: linear-gradient(135deg, var(--neon-orange), #ff5500);
            color: #000; border: none; padding: 8px; border-radius: 6px; font-weight: bold;
            margin-top: 8px; cursor: pointer; text-align: center; text-decoration: none; font-size: 11px;
        }

        /* ================= DESKTOP VIEW (ADVANCED SCI-FI HUD) ================= */
        .hud-header {
            display: flex; justify-content: space-between; align-items: center;
            background: var(--hud-panel); border: 1px solid var(--border-glow);
            padding: 12px 25px; border-radius: 6px; backdrop-filter: blur(15px);
            box-shadow: 0 0 30px rgba(0, 243, 255, 0.2);
            position: relative;
        }
        .hud-header::before, .hud-header::after {
            content: ''; position: absolute; width: 10px; height: 10px; border-color: var(--neon-cyan); border-style: solid;
        }
        .hud-header::before { top: -2px; left: -2px; border-width: 2px 0 0 2px; }
        .hud-header::after { bottom: -2px; right: -2px; border-width: 0 2px 2px 0; }
        .hud-header h1 { font-size: 14px; color: var(--neon-cyan); letter-spacing: 3px; margin: 0; }

        .hud-main-grid {
            display: grid;
            grid-template-columns: 320px 1fr 320px;
            gap: 15px; flex: 1; margin: 12px 0; align-items: stretch;
        }

        .hud-box {
            background: var(--hud-panel); border: 1px solid var(--border-glow);
            border-radius: 8px; padding: 15px; backdrop-filter: blur(15px);
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.05), 0 0 25px rgba(0, 243, 255, 0.08);
            display: flex; flex-direction: column; gap: 10px; position: relative;
        }
        .hud-box h3 {
            font-size: 11px; color: var(--neon-orange); margin: 0 0 4px 0;
            letter-spacing: 2px; border-bottom: 1px dashed rgba(255,153,0,0.4); padding-bottom: 4px;
            text-transform: uppercase;
        }

        /* Central Holographic Stage with Node Network Background */
        .hud-center-stage {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            position: relative; background: radial-gradient(circle, rgba(0,243,255,0.08) 0%, rgba(176,0,255,0.03) 60%, transparent 90%);
            border: 1px solid rgba(0, 243, 255, 0.25); border-radius: 8px; padding: 20px; overflow: hidden;
        }

        /* SVG Node Network Lines */
        .node-svg-overlay {
            position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; opacity: 0.6;
        }

        .hud-core-ring {
            width: 150px; height: 150px;
            background: radial-gradient(circle, var(--neon-cyan) 0%, rgba(176,0,255,0.4) 65%, transparent 100%);
            border-radius: 50%; box-shadow: 0 0 50px var(--neon-cyan);
            display: flex; align-items: center; justify-content: center;
            animation: pulseCore 4s infinite alternate; cursor: pointer; z-index: 3;
            border: 3px solid var(--neon-cyan); position: relative;
        }
        .hud-core-ring span { font-weight: bold; color: #030508; font-size: 13px; letter-spacing: 2px; }

        .hologram-orbit {
            display: flex; gap: 10px; margin-top: 20px; z-index: 3; flex-wrap: wrap; justify-content: center;
        }
        .orbit-node {
            background: rgba(4, 14, 28, 0.85); border: 1px solid var(--neon-cyan);
            padding: 8px 14px; border-radius: 6px; font-size: 10.5px; color: var(--neon-cyan);
            cursor: pointer; transition: 0.3s; backdrop-filter: blur(8px);
            letter-spacing: 1px; box-shadow: 0 0 10px rgba(0,243,255,0.2);
        }
        .orbit-node:hover {
            background: var(--neon-cyan); color: #030508; box-shadow: 0 0 20px var(--neon-cyan);
        }

        /* Telemetry Visualizers */
        .telemetry-bar {
            width: 100%; background: rgba(0,0,0,0.5); border: 1px solid rgba(0,243,255,0.2);
            height: 6px; border-radius: 3px; overflow: hidden; margin-top: 2px;
        }
        .telemetry-fill {
            height: 100%; background: linear-gradient(90deg, var(--neon-cyan), var(--neon-orange)); width: 78%;
            box-shadow: 0 0 8px var(--neon-cyan);
        }

        .hud-footer {
            background: var(--hud-panel); border: 1px solid var(--border-glow);
            padding: 10px 25px; border-radius: 6px; display: flex; justify-content: space-between;
            align-items: center; font-size: 10.5px; color: var(--text-dim); backdrop-filter: blur(10px);
        }

        /* MODAL */
        .modal {
            display: none; position: fixed; inset: 0; background: rgba(3,5,8,0.88);
            backdrop-filter: blur(10px); z-index: 100; align-items: center; justify-content: center; padding: 15px;
        }
        .modal-content {
            background: var(--hud-panel); border: 1px solid var(--neon-cyan);
            padding: 22px; border-radius: 10px; width: 100%; max-width: 440px;
            box-shadow: 0 0 50px rgba(0,243,255,0.35);
        }
        .close-modal { float: right; color: var(--neon-orange); cursor: pointer; font-weight: bold; font-size: 16px; }
    </style>
</head>
<body>

    <!-- ================= MOBILE INTERFACE ================= -->
    <div class="mobile-view">
        <div class="mobile-container">
            <header class="mobile-header">
                <div>
                    <h1 style="font-size: 13px; color: var(--neon-cyan); margin: 0;">NEO // ENTERPRISE OS</h1>
                    <p style="font-size: 10px; color: var(--text-dim); margin: 2px 0 0 0;">MARGIL MOLLAJ // WISAG HH</p>
                </div>
                <div style="text-align: right;">
                    <span id="m-date" style="font-size: 10px; color: var(--text-dim);">--.--.----</span><br>
                    <span style="font-size: 11px; color: var(--neon-cyan);" id="m-weather">🌡️ Hamburg 14°C</span>
                </div>
            </header>

            <div class="mobile-core-box">
                <div class="core-pulse" onclick="toggleListening()"></div>
                <div class="voice-bar" id="m-status-text">🎙️ „Hey Neo“ - Bereit in Hamburg</div>
            </div>

            <div class="mobile-cards">
                <div class="m-card" onclick="openModal('Morning Briefing', 'Objekte in Hamburg-Nord & Altona. Fokus auf Tiefenreinigung HafenCity. Alle Termine synchronisiert.')">
                    <h3><span>📅 MORNING BRIEFING</span> <span style="color:var(--neon-cyan);">Hamburg-Nord</span></h3>
                    <p>5 Objekte zur Kontrolle. Tippen für Details & Routen.</p>
                </div>

                <div class="m-card" onclick="event.stopPropagation();">
                    <h3><span>💰 ANGEBOTS-RECHNER</span> <span style="color:var(--neon-orange);">31.50 €/h</span></h3>
                    <p>Fläche (m²):</p>
                    <input type="number" id="m-area" value="300" oninput="calculateMobile()">
                    <div class="calc-result" id="m-total">Gesamt: 9,450.00 € netto</div>
                    <a href="#" id="m-whatsapp-btn" class="action-btn" onclick="sendWhatsAppMobile()">Angebot via WhatsApp senden</a>
                </div>

                <div class="m-card" onclick="openModal('Objekt Codes', 'Objekt 1045 (Westhafen): Torcode 2379\\nObjekt 882 (Altona): Schlüsselkasten #4')">
                    <h3><span>🔑 OBJEKT-CODES & SCHLÜSSEL</span> <span>WISAG HH</span></h3>
                    <p>Torcodes für HafenCity & Altona verwalten.</p>
                </div>

                <div class="m-card" onclick="openModal('Field Inspector', 'Foto hochladen -> NEO generiert professionellen Mängelbericht auf Deutsch für Hausverwaltung.')">
                    <h3><span>📷 FIELD INSPECTOR</span> <span>Mängelbericht</span></h3>
                    <p>Schäden dokumentieren & Bericht erstellen.</p>
                </div>
            </div>

            <footer style="text-align: center; font-size: 9.5px; color: var(--text-dim); padding: 4px;">
                SECURE ENTERPRISE LINK // WESER-EMS SECTOR ACTIVE
            </footer>
        </div>
    </div>


    <!-- ================= DESKTOP VIEW (ADVANCED HUD COMMAND CENTER) ================= -->
    <div class="desktop-view">
        <header class="hud-header">
            <h1>NEO // ENTERPRISE OS - COMMAND CENTER</h1>
            <div style="font-size: 11px; color: var(--text-dim); font-family: 'Courier New', monospace;">
                OPERATOR: <span style="color: var(--neon-cyan);">MARGIL MOLLAJ (WISAG HAMBURG)</span> | DATE: <span id="pc-date">--.--.----</span> | WEATHER: <span style="color: var(--neon-cyan);" id="pc-weather">Hamburg 14°C</span>
            </div>
        </header>

        <div class="hud-main-grid">
            <!-- Left Panel -->
            <div class="hud-box">
                <h3>Operations & Field Data</h3>
                <p style="font-size: 10.5px; color: var(--text-dim); line-height: 1.4;">Aktive Routen & Inspektionen im Sektor Hamburg-Nord / Altona.</p>
                
                <div style="background: rgba(0,0,0,0.5); padding: 10px; border-radius: 4px; border-left: 2px solid var(--neon-cyan); margin-top: 2px;">
                    <strong style="font-size: 11px; color: var(--neon-cyan);">HafenCity & Weser-Ems</strong>
                    <p style="font-size: 10px; color: var(--text-dim); margin-top: 3px;">5 Objekte zugewiesen. Sicherheitsprotokolle aktiv.</p>
                </div>

                <h3 style="margin-top: 10px;">Secure Vault</h3>
                <p style="font-size: 10px; color: var(--text-dim);">Torcodes & Schließzylinder Schnellzugriff.</p>
                
                <div style="margin-top: auto;">
                    <span style="font-size: 10px; color: var(--text-dim);">SYSTEM EFFICIENCY</span>
                    <div class="telemetry-bar"><div class="telemetry-fill" style="width: 94%;"></div></div>
                </div>
            </div>

            <!-- Central Holographic Stage with Node Network -->
            <div class="hud-center-stage">
                <!-- SVG Network Connecting Lines -->
                <svg class="node-svg-overlay" viewBox="0 0 600 400" preserveAspectRatio="none">
                    <line x1="300" y1="200" x2="100" y2="100" stroke="#00f3ff" stroke-width="1" stroke-dasharray="4 4" opacity="0.5"/>
                    <line x1="300" y1="200" x2="500" y2="100" stroke="#00f3ff" stroke-width="1" stroke-dasharray="4 4" opacity="0.5"/>
                    <line x1="300" y1="200" x2="120" y2="320" stroke="#ff9900" stroke-width="1" stroke-dasharray="4 4" opacity="0.5"/>
                    <line x1="300" y1="200" x2="480" y2="320" stroke="#ff9900" stroke-width="1" stroke-dasharray="4 4" opacity="0.5"/>
                    <circle cx="100" cy="100" r="4" fill="#00f3ff"/><circle cx="500" cy="100" r="4" fill="#00f3ff"/>
                    <circle cx="120" cy="320" r="4" fill="#ff9900"/><circle cx="480" cy="320" r="4" fill="#ff9900"/>
                </svg>

                <div style="position: absolute; top: 10px; font-size: 10px; color: var(--text-dim); letter-spacing: 2px;">NEURAL NODE CONSTELLATION // ACTIVE</div>
                
                <div class="hud-core-ring" onclick="toggleListening()">
                    <span>NEO CORE</span>
                </div>

                <div class="hologram-orbit">
                    <div class="orbit-node" onclick="openModal('Angebots-Rechner', 'Tarif: 31.50 €/h aktiv. Berechnungen in Echtzeit für Hamburg.')">Angebots-Rechner</div>
                    <div class="orbit-node" onclick="openModal('WhatsApp Direct', 'Direktverbindung zu Hausverwaltung & Kunden aktiv.')">WhatsApp Direct</div>
                    <div class="orbit-node" onclick="openModal('Field Inspector', 'Mängelberichte & Sonderreinigung Dokumentation.')">Field Inspector</div>
                    <div class="orbit-node" onclick="openModal('Outlook Sync', 'Verbindung mit margil.mollaj@wisag.de gesichert.')">Outlook Sync</div>
                </div>
            </div>

            <!-- Right Panel -->
            <div class="hud-box">
                <h3>Sales & Bidding Engine</h3>
                <p style="font-size: 10.5px; color: var(--text-dim);">Standard Tarif WISAG Gebäudereinigung:</p>
                <div style="font-size: 17px; color: var(--neon-orange); font-weight: bold; margin: 4px 0;">31.50 € / Stunde</div>
                <p style="font-size: 10px; color: var(--text-dim);">Sofortkalkulation für Hausverwaltung in Hamburg.</p>
                
                <h3 style="margin-top: 15px;">System Telemetry</h3>
                <div style="font-size: 10px; color: var(--text-dim); line-height: 1.5; background: rgba(0,0,0,0.4); padding: 8px; border-radius: 4px;">
                    Uptime: 99.9% // Sektor Hamburg<br>
                    Latency: 0.04ms (Render Edge)<br>
                    Encryption: AES-256 Link
                </div>

                <div style="margin-top: auto;">
                    <span style="font-size: 10px; color: var(--text-dim);">NEURAL LOAD</span>
                    <div class="telemetry-bar"><div class="telemetry-fill" style="width: 82%;"></div></div>
                </div>
            </div>
        </div>

        <footer class="hud-footer">
            <span>STATUS: ONLINE // WESER-EMS SECTOR</span>
            <span>„Hey Neo“ Voice Assistant Ready</span>
            <span>RENDER CLOUD HOSTED</span>
        </footer>
    </div>

    <!-- Generic Modal -->
    <div id="genericModal" class="modal">
        <div class="modal-content">
            <span class="close-modal" onclick="closeModal()">&times;</span>
            <h3 id="modal-title" style="color: var(--neon-cyan); margin-bottom: 10px; font-size: 13px;"></h3>
            <p id="modal-text" style="font-size: 11.5px; color: var(--text-dim); line-height: 1.5; white-space: pre-line;"></p>
        </div>
    </div>

    <audio id="audioPlayer" playsinline></audio>

    <script>
        const today = new Date().toLocaleDateString('de-DE');
        document.getElementById('m-date').innerText = today;
        document.getElementById('pc-date').innerText = today;

        fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true')
            .then(r => r.json())
            .then(data => {
                if (data && data.current_weather) {
                    const temp = data.current_weather.temperature;
                    document.getElementById('m-weather').innerText = `🌡️ Hamburg ${temp}°C`;
                    document.getElementById('pc-weather').innerText = `Hamburg ${temp}°C`;
                }
            }).catch(() => {});

        function calculateMobile() {
            const area = document.getElementById('m-area').value;
            const total = area * 31.50;
            document.getElementById('m-total').innerText = `Gesamt: ${total.toLocaleString('de-DE', {minimumFractionDigits: 2})} € netto`;
        }

        function sendWhatsAppMobile() {
            const area = document.getElementById('m-area').value;
            const total = document.getElementById('m-total').innerText;
            const text = encodeURIComponent(`Guten Tag, hier ist das Angebot der WISAG für Ihre Fläche (${area} m²): ${total} (Basis 31.50 €/h). Mit freundlichen Grüßen, Margil Mollaj`);
            window.open(`https://wa.me/?text=${text}`, '_blank');
        }

        function openModal(title, text) {
            document.getElementById('modal-title').innerText = title;
            document.getElementById('modal-text').innerText = text;
            document.getElementById('genericModal').style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('genericModal').style.display = 'none';
        }

        let isListening = false;
        const audioPlayer = document.getElementById('audioPlayer');

        function toggleListening() {
            isListening = !isListening;
            if (isListening) {
                document.getElementById('m-status-text').innerText = "🎙️ HÖRE ZU...";
                startVoiceRecording();
            } else {
                document.getElementById('m-status-text').innerText = "🎙️ „Hey Neo“ - Bereit";
            }
        }

        async function startVoiceRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const mediaRecorder = new MediaRecorder(stream);
                let chunks = [];
                mediaRecorder.ondataavailable = e => chunks.push(e.data);
                mediaRecorder.onstop = async () => {
                    stream.getTracks().forEach(t => t.stop());
                    const blob = new Blob(chunks, { type: 'audio/webm' });
                    const reader = new FileReader();
                    reader.readAsDataURL(blob);
                    reader.onloadend = async () => {
                        const base64Audio = reader.result.split(',')[1];
                        document.getElementById('m-status-text').innerText = "🧠 ANALYSIERE...";
                        try {
                            const res = await fetch('/chat', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ audio: base64Audio, mode: "ARBEIT" })
                            });
                            const data = await res.json();
                            document.getElementById('m-status-text').innerText = "🎙️ " + (data.reply || "Fertig.");
                            if (data.audio) {
                                audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                                audioPlayer.play();
                            }
                        } catch(err) {
                            document.getElementById('m-status-text').innerText = "❌ Verbindungsfehler";
                        }
                        isListening = false;
                    };
                };
                mediaRecorder.start();
                setTimeout(() => { if (mediaRecorder.state === 'recording') mediaRecorder.stop(); }, 5000);
            } catch(e) {
                isListening = false;
                document.getElementById('m-status-text').innerText = "❌ Mikrofon-Zugriff verweigert";
            }
        }
    </script>
</body>
</html>
"""

def parse_upcoming_events():
    now_ts = time.time()
    if ICAL_CACHE["events"] and (now_ts - ICAL_CACHE["ts"] < 120):
        return ICAL_CACHE["events"]
    ical_url = os.environ.get("ICAL_URL", "").strip()
    if not ical_url:
        return []
    try:
        raw = urllib.request.urlopen(ical_url, timeout=3).read().decode("utf-8", errors="ignore")
        raw = re.sub(r"\r?\n[ \t]", "", raw)
        now = datetime.now() - timedelta(hours=12)
        out = []
        for block in raw.split("BEGIN:VEVENT")[1:]:
            tm = re.search(r"SUMMARY:(.*)", block)
            dm = re.search(r"DTSTART[^:]*:(\d{8}(?:T\d{6}Z?)?)", block)
            lm = re.search(r"LOCATION:(.*)", block)
            if tm and dm:
                clean = dm.group(1).strip().replace("Z", "")
                dt = datetime.strptime(clean[:15], "%Y%m%dT%H%M%S") if "T" in clean else datetime.strptime(clean[:8], "%Y%m%d")
                if dm.group(1).endswith("Z"):
                    dt += timedelta(hours=1)
                if dt >= now:
                    out.append((dt, {
                        "time": dt.strftime("%d.%m. %H:%M") if "T" in clean else dt.strftime("%d.%m."),
                        "title": tm.group(1).strip().replace("\\n", " ").replace("\\,", ","),
                        "loc": lm.group(1).strip().replace("\\n", " ") if lm else ""
                    }))
        out.sort(key=lambda x: x[0])
        ICAL_CACHE["ts"] = now_ts
        ICAL_CACHE["events"] = [x[1] for x in out[:10]]
        return ICAL_CACHE["events"]
    except Exception:
        return ICAL_CACHE["events"]

SYSTEM_PROMPT = """Du bist NEO, der hochintelligente KI-Assistent von Margil Mollaj (Kundenbetreuer Gebäudereinigung WISAG Hamburg). Antworte IMMER strikt auf Deutsch.
Modus: {mode} | Zeit: {local_time}. Antworte souverän, ruhig, präzise und kurz auf Deutsch. Keine Sternchen oder Markdown.
Antworte NUR als JSON:
{{"reply":"","voice_lang":"de","copy_text":"","new_memory":"","action_url":"","action_label":"","end_conversation":false}}"""

async def make_voice(text, lang="de"):
    clean = text.replace("*", "").replace("#", "").strip()
    voice = "de-DE-FlorianMultilingualNeural"
    comm = edge_tts.Communicate(clean, voice, rate="+10%")
    buf = b""
    async for c in comm.stream():
        if c["type"] == "audio":
            buf += c["data"]
    return base64.b64encode(buf).decode("utf-8")

def generate_with_fallback(client, parts, config):
    for model_name in ["gemini-2.5-flash", "gemini-3.8-flash"]:
        try:
            return client.models.generate_content(model=model_name, contents=parts, config=config)
        except Exception as e:
            last_err = e
            continue
    raise last_err

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/calendar_preview")
def cal_prev():
    return jsonify({"events": parse_upcoming_events()})

@app.route("/manifest.json")
def manifest():
    return jsonify({
        "name": "NEO Enterprise OS",
        "short_name": "NEO",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#030508",
        "theme_color": "#030508",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]
    })

@app.route("/icon.svg")
def icon():
    return Response(ICON_SVG, mimetype="image/svg+xml")

@app.route("/chat", methods=["POST"])
def chat():
    text_content = ""
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        data = request.json or {}
        client = genai.Client(api_key=api_key)
        events = parse_upcoming_events()
        cal_txt = "\n".join([f"- {e['time']}: {e['title']}" for e in events]) or "Keine Termine."

        parts = [data.get("message", "Bereit."), f"Kalender:\n{cal_txt}"]
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT.format(mode=data.get("mode", "ARBEIT"), local_time=datetime.now().strftime("%d.%m.%Y %H:%M")),
            temperature=0.3
        )
        resp = generate_with_fallback(client, parts, cfg)
        text_content = resp.text.strip()

        m = re.search(r'\{.*\}', text_content, re.DOTALL)
        res = json.loads(m.group(0)) if m else {"reply": text_content}
        reply = res.get("reply", text_content)
        audio = asyncio.run(make_voice(reply, "de"))
        return jsonify({
            "reply": reply,
            "copy_text": res.get("copy_text", ""),
            "new_memory": res.get("new_memory", ""),
            "action_url": res.get("action_url", ""),
            "action_label": res.get("action_label", ""),
            "end_conversation": res.get("end_conversation", False),
            "audio": audio
        })
    except Exception as e:
        try:
            fallback_reply = "Zu Befehl, Margil."
            audio = asyncio.run(make_voice(fallback_reply, "de"))
            return jsonify({
                "reply": fallback_reply,
                "copy_text": "",
                "new_memory": "",
                "action_url": "",
                "action_label": "",
                "end_conversation": False,
                "audio": audio
            })
        except Exception:
            return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run("0.0.0.0", port=int(os.environ.get("PORT", 5000)))
