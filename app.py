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

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="115" fill="#050811"/>
  <circle cx="256" cy="256" r="155" fill="none" stroke="#00f3ff" stroke-width="8" stroke-dasharray="16 10"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#ff9900" stroke-width="5"/>
  <circle cx="256" cy="256" r="24" fill="#ff9900"/>
</svg>"""

HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#050811">
    <link rel="manifest" href="/manifest.json">
    <title>NEO // ENTERPRISE OS - WISAG Hamburg</title>
    <style>
        :root {
            --bg-deep: #050811;
            --panel-bg: rgba(18, 20, 28, 0.95);
            --neon-cyan: #00f3ff;
            --neon-orange: #ff9900;
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
            --border-glow: rgba(0, 243, 255, 0.3);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif, monospace; }

        body {
            background-color: var(--bg-deep);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 20px;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            width: 100%;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        header {
            background: var(--panel-bg);
            border: 1px solid var(--border-glow);
            border-radius: 12px;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            backdrop-filter: blur(10px);
        }

        h1 { font-size: 16px; color: var(--neon-cyan); letter-spacing: 1px; }
        .meta { font-size: 12px; color: var(--text-dim); text-align: right; }

        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        @media(max-width: 768px) {
            .dashboard-grid { grid-template-columns: 1fr; }
            body { padding: 10px; }
        }

        .card {
            background: var(--panel-bg);
            border: 1px solid var(--border-glow);
            border-radius: 12px;
            padding: 18px;
            backdrop-filter: blur(10px);
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .card h3 {
            font-size: 13px;
            color: var(--neon-orange);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .card p, .card div, .card label {
            font-size: 12px;
            color: var(--text-dim);
        }

        input, select, textarea {
            width: 100%;
            background: #030408;
            border: 1px solid var(--border-glow);
            color: var(--text-main);
            padding: 8px 10px;
            border-radius: 6px;
            font-size: 13px;
            margin-top: 4px;
            outline: none;
        }
        input:focus, select:focus { border-color: var(--neon-cyan); }

        .btn {
            background: linear-gradient(135deg, var(--neon-orange), #ff5500);
            color: #000;
            border: none;
            padding: 10px;
            border-radius: 6px;
            font-weight: bold;
            cursor: pointer;
            text-align: center;
            text-decoration: none;
            font-size: 12px;
            margin-top: 8px;
            display: block;
        }

        .core-section {
            background: var(--panel-bg);
            border: 1px solid var(--border-glow);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }

        .core-btn {
            width: 80px;
            height: 80px;
            background: radial-gradient(circle, var(--neon-cyan) 0%, rgba(0,243,255,0.2) 70%, transparent 100%);
            border-radius: 50%;
            margin: 0 auto 10px auto;
            box-shadow: 0 0 25px var(--neon-cyan);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid var(--neon-cyan);
        }

        footer {
            text-align: center;
            font-size: 11px;
            color: var(--text-dim);
            padding: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>NEO // ENTERPRISE OS</h1>
                <p style="font-size: 11px; color: var(--text-dim);">Margil Mollaj // WISAG Hamburg</p>
            </div>
            <div class="meta">
                <span id="dateDisplay">--.--.----</span><br>
                <span id="weatherDisplay" style="color: var(--neon-cyan);">Hamburg Lade...</span>
            </div>
        </header>

        <div class="core-section">
            <div class="core-btn" onclick="toggleListening()">🎙️</div>
            <p id="statusText" style="color: var(--neon-cyan); font-weight: bold; font-size: 13px;">„Hey Neo“ - Sprachassistent Bereit</p>
        </div>

        <div class="dashboard-grid">
            <div class="card">
                <h3><span>📅 MORNING BRIEFING</span> <span style="color:var(--neon-cyan);">Hamburg-Nord</span></h3>
                <p>5 Objekte zur Kontrolle heute in Hamburg.</p>
                <button class="btn" style="background:var(--neon-cyan); color:#000;" onclick="alert('Morning Briefing: 5 Objekte in Hamburg-Nord & Altona aktiv.')">Details aufrufen</button>
            </div>

            <div class="card">
                <h3><span>💰 ANGEBOTS-RECHNER</span> <span style="color:var(--neon-orange);">Eigener Preis</span></h3>
                <label>Fläche in m²:</label>
                <input type="number" id="calcArea" value="300" oninput="calculate()">
                
                <label>Stundensatz (€/h):</label>
                <input type="number" step="0.5" id="calcRate" value="31.50" oninput="calculate()">
                
                <label>Frequenz pro Woche:</label>
                <select id="calcFreq" onchange="calculate()">
                    <option value="1">1x pro Woche</option>
                    <option value="2">2x pro Woche</option>
                    <option value="3">3x pro Woche</option>
                    <option value="4" selected>4x pro Woche</option>
                    <option value="5">5x pro Woche</option>
                </select>

                <div id="calcTotal" style="font-size: 13px; color: var(--neon-orange); font-weight: bold; margin-top: 5px;">Monatlich: 0.00 € netto</div>
                <button class="btn" onclick="sendWhatsApp()">Angebot via WhatsApp senden</button>
            </div>

            <div class="card">
                <h3><span>🔑 OBJEKT-CODES & SCHLÜSSEL</span> <span>WISAG HH</span></h3>
                <p>Objekt 1045 (Westhafen): Torcode 2379<br>Objekt 882 (Altona): Schlüsselkasten #4</p>
            </div>

            <div class="card">
                <h3><span>💬 QUICK TOOLS</span> <span style="color:var(--neon-cyan);">DIREKT</span></h3>
                <button class="btn" style="background:#10b981; color:#fff; margin-top:0;" onclick="window.open('https://wa.me/?text=Guten Tag, hier ist Margil Mollaj von der WISAG.', '_blank')">WhatsApp Business öffnen</button>
            </div>
        </div>
    </div>

    <footer>
        SECURE ENTERPRISE LINK // WESER-EMS SECTOR ACTIVE
    </footer>

    <audio id="audioPlayer" playsinline></audio>

    <script>
        document.getElementById('dateDisplay').innerText = new Date().toLocaleDateString('de-DE');

        fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true')
            .then(r => r.json())
            .then(data => {
                if (data && data.current_weather) {
                    document.getElementById('weatherDisplay').innerText = `Hamburg ${data.current_weather.temperature}°C`;
                }
            }).catch(() => {
                document.getElementById('weatherDisplay').innerText = `Hamburg Aktiv`;
            });

        function calculate() {
            const area = parseFloat(document.getElementById('calcArea').value) || 0;
            const rate = parseFloat(document.getElementById('calcRate').value) || 0;
            const freq = parseInt(document.getElementById('calcFreq').value) || 1;
            
            const monthlyHours = (area / 350) * freq * 4.33;
            const total = monthlyHours * rate;
            document.getElementById('calcTotal').innerText = `Monatlich: ${total.toLocaleString('de-DE', {minimumFractionDigits: 2, maximumFractionDigits: 2})} € netto`;
        }

        window.onload = calculate;

        function sendWhatsApp() {
            const area = document.getElementById('calcArea').value;
            const rate = document.getElementById('calcRate').value;
            const freqText = document.getElementById('calcFreq').options[document.getElementById('calcFreq').selectedIndex].text;
            const total = document.getElementById('calcTotal').innerText;
            const text = encodeURIComponent(`Guten Tag, hier ist das Angebot der WISAG für Ihre Fläche (${area} m² bei ${freqText}, Stundensatz: ${rate} €/h): ${total}. Mit freundlichen Grüßen, Margil Mollaj`);
            window.open(`https://wa.me/?text=${text}`, '_blank');
        }

        let isListening = false;
        const audioPlayer = document.getElementById('audioPlayer');

        function toggleListening() {
            isListening = !isListening;
            const statusEl = document.getElementById('statusText');
            if (isListening) {
                statusEl.innerText = "🎙️ Höre zu...";
                startVoiceRecording();
            } else {
                statusEl.innerText = "🎙️ „Hey Neo“ - Bereit";
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
                        try {
                            const res = await fetch('/chat', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ audio: base64Audio, mode: "ARBEIT" })
                            });
                            const data = await res.json();
                            if (data.reply) statusEl.innerText = "🎙️ " + data.reply;
                            if (data.audio) {
                                audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                                audioPlayer.play();
                            }
                        } catch(err) {
                            statusEl.innerText = "❌ Fehler bei Verbindung";
                        }
                        isListening = false;
                    };
                };
                mediaRecorder.start();
                setTimeout(() => { if (mediaRecorder.state === 'recording') mediaRecorder.stop(); }, 5000);
            } catch(e) {
                isListening = false;
                statusEl.innerText = "❌ Mikrofon gesperrt";
            }
        }
    </script>
</body>
</html>
"""

SYSTEM_PROMPT = """Du bist NEO, der KI-Assistent von Margil Mollaj (Kundenbetreuer WISAG Hamburg). Antworte auf Deutsch."""

async def make_voice(text, lang="de"):
    clean = text.replace("*", "").replace("#", "").strip()
    voice = "de-DE-FlorianMultilingualNeural"
    comm = edge_tts.Communicate(clean, voice, rate="+10%")
    buf = b""
    async for c in comm.stream():
        if c["type"] == "audio":
            buf += c["data"]
    return base64.b64encode(buf).decode("utf-8")

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/manifest.json")
def manifest():
    return jsonify({
        "name": "NEO Enterprise OS",
        "short_name": "NEO",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#050811",
        "theme_color": "#050811",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]
    })

@app.route("/icon.svg")
def icon():
    return Response(ICON_SVG, mimetype="image/svg+xml")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        data = request.json or {}
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=data.get("message", "Statusbericht für Hamburg."),
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
        )
        reply = resp.text.strip()
        audio = asyncio.run(make_voice(reply, "de"))
        return jsonify({"reply": reply, "audio": audio})
    except Exception as e:
        reply = "Zu Befehl, Margil."
        audio = asyncio.run(make_voice(reply, "de"))
        return jsonify({"reply": reply, "audio": audio})

if __name__ == "__main__":
    app.run("0.0.0.0", port=int(os.environ.get("PORT", 5000)))
