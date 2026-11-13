import os
import json
import base64
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, Response
from google import genai
from google.genai import types
import edge_tts

app = Flask(__name__)

MANIFEST_JSON = {
    "name": "JARVIS MARK IX",
    "short_name": "JARVIS",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#030712",
    "theme_color": "#030712",
    "icons": [
        {
            "src": "/icon.svg",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any maskable"
        }
    ]
}

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#00F0FF" stop-opacity="0.45"/>
      <stop offset="70%" stop-color="#0284C7" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="#030712" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" rx="115" fill="#030712"/>
  <circle cx="256" cy="256" r="220" fill="url(#glow)"/>
  <circle cx="256" cy="256" r="185" fill="none" stroke="#00F0FF" stroke-width="6" stroke-opacity="0.35"/>
  <circle cx="256" cy="256" r="160" fill="none" stroke="#00F0FF" stroke-width="14" stroke-dasharray="65 25 15 25"/>
  <circle cx="256" cy="256" r="120" fill="none" stroke="#38BDF8" stroke-width="6" stroke-dasharray="12 12"/>
  <circle cx="256" cy="256" r="82" fill="#061626" stroke="#00F0FF" stroke-width="5"/>
  <text x="256" y="276" font-family="sans-serif" font-size="64" font-weight="800" fill="#00F0FF" text-anchor="middle">J</text>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#030712">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/svg+xml" href="/icon.svg">
    <title>JARVIS MARK IX</title>
    <style>
        :root {
            --primary: #00F0FF;
            --glow: rgba(0, 240, 255, 0.45);
            --bg: #030712;
        }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body {
            margin: 0;
            background-color: var(--bg);
            background-image: 
                radial-gradient(circle at 50% 30%, rgba(0, 240, 255, 0.12) 0%, transparent 55%),
                linear-gradient(rgba(0, 240, 255, 0.04) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 240, 255, 0.04) 1px, transparent 1px);
            background-size: 100% 100%, 32px 32px, 32px 32px;
            color: var(--primary);
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
            height: 100dvh;
            padding: 16px 16px 18px;
            overflow: hidden;
        }
        .hud-top {
            width: 100%;
            max-width: 480px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            letter-spacing: 2px;
            text-transform: uppercase;
            opacity: 0.85;
            border-bottom: 1px solid rgba(0, 240, 255, 0.2);
            padding-bottom: 8px;
        }
        .status-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--primary);
            box-shadow: 0 0 8px var(--primary);
            margin-right: 6px;
        }
        .mem-badge {
            font-size: 10px;
            padding: 2px 8px;
            border: 1px solid rgba(0, 240, 255, 0.4);
            border-radius: 10px;
            cursor: pointer;
        }
        .core-wrapper {
            position: relative;
            width: 215px;
            height: 215px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
            margin-top: 6px;
        }
        .ring-outer {
            position: absolute;
            width: 210px;
            height: 210px;
            border-radius: 50%;
            border: 2px dashed rgba(0, 240, 255, 0.45);
            animation: spinRight 24s linear infinite;
        }
        .ring-mid {
            position: absolute;
            width: 184px;
            height: 184px;
            border-radius: 50%;
            border: 4px solid transparent;
            border-top-color: var(--primary);
            border-bottom-color: var(--primary);
            box-shadow: 0 0 25px var(--glow);
            animation: spinLeft 10s linear infinite;
        }
        .ring-inner {
            position: absolute;
            width: 156px;
            height: 156px;
            border-radius: 50%;
            border: 2px dotted rgba(0, 240, 255, 0.75);
            animation: spinRight 16s linear infinite;
        }
        .core-center {
            position: relative;
            width: 130px;
            height: 130px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(0, 240, 255, 0.22) 0%, rgba(3, 7, 18, 0.92) 75%);
            border: 2px solid var(--primary);
            box-shadow: 0 0 30px var(--glow), inset 0 0 22px var(--glow);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 2;
            transition: all 0.25s;
        }
        .core-center h1 {
            margin: 0;
            font-size: 20px;
            font-weight: 800;
            letter-spacing: 4px;
            text-shadow: 0 0 12px var(--primary);
        }
        .core-center span {
            font-size: 8px;
            letter-spacing: 2px;
            opacity: 0.85;
            margin-top: 4px;
        }
        body.listening { --primary: #00FF88; --glow: rgba(0, 255, 136, 0.55); }
        body.listening .ring-mid { animation-duration: 3s; }
        body.thinking { --primary: #FF9500; --glow: rgba(255, 149, 0, 0.55); }
        body.thinking .ring-mid { animation-duration: 1.5s; }
        body.speaking .core-center { animation: pulseSpeak 0.9s ease-in-out infinite alternate; }

        @keyframes spinRight { 100% { transform: rotate(360deg); } }
        @keyframes spinLeft { 100% { transform: rotate(-360deg); } }
        @keyframes pulseSpeak {
            0% { transform: scale(1); box-shadow: 0 0 25px var(--glow); }
            100% { transform: scale(1.07); box-shadow: 0 0 50px var(--glow); }
        }
        .visualizer {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
            height: 22px;
            margin-top: 6px;
        }
        .bar {
            width: 3.5px;
            height: 5px;
            background: var(--primary);
            border-radius: 3px;
            box-shadow: 0 0 8px var(--primary);
            transition: height 0.08s ease;
        }
        .hint {
            font-size: 11px;
            opacity: 0.7;
            margin-top: 3px;
            text-align: center;
        }
        .hud-panel {
            flex: 1;
            width: 100%;
            max-width: 460px;
            margin: 12px 0;
            padding: 15px;
            background: rgba(11, 19, 36, 0.65);
            border: 1px solid rgba(0, 240, 255, 0.25);
            border-left: 3px solid var(--primary);
            border-right: 3px solid var(--primary);
            border-radius: 14px;
            backdrop-filter: blur(8px);
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: 15.5px;
            line-height: 1.55;
            color: #E0F7FA;
        }
        .action-btn {
            margin-top: 12px;
            padding: 11px 22px;
            border-radius: 25px;
            background: #00FF88;
            color: #030712;
            font-weight: 800;
            text-decoration: none;
            font-size: 14px;
            display: inline-block;
            box-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
        }
        .quick-apps {
            display: flex;
            gap: 8px;
            width: 100%;
            max-width: 460px;
            overflow-x: auto;
            padding-bottom: 8px;
            scrollbar-width: none;
        }
        .quick-apps::-webkit-scrollbar { display: none; }
        .chip {
            white-space: nowrap;
            padding: 6px 12px;
            border-radius: 16px;
            border: 1px solid rgba(0, 240, 255, 0.35);
            background: rgba(11, 19, 36, 0.8);
            color: #00F0FF;
            font-size: 12px;
            cursor: pointer;
        }
        .input-box {
            display: flex;
            gap: 8px;
            width: 100%;
            max-width: 460px;
        }
        input {
            flex: 1;
            padding: 13px 16px;
            border-radius: 25px;
            border: 1px solid rgba(0, 240, 255, 0.45);
            background: rgba(11, 19, 36, 0.85);
            color: white;
            font-size: 16px;
            outline: none;
        }
        button.send-btn {
            padding: 13px 20px;
            border-radius: 25px;
            border: none;
            background: var(--primary);
            color: #030712;
            font-weight: 800;
            font-size: 14px;
            cursor: pointer;
            box-shadow: 0 0 15px var(--glow);
        }
    </style>
</head>
<body>
    <div class="hud-top">
        <div><span class="status-dot"></span>JARVIS CONNECTED</div>
        <div class="mem-badge" onclick="showMemory()" id="memCount">GEDÄCHTNIS: 0</div>
    </div>

    <div style="display:flex; flex-direction:column; align-items:center;">
        <div class="core-wrapper" onclick="toggleRecord()">
            <div class="ring-outer"></div>
            <div class="ring-mid"></div>
            <div class="ring-inner"></div>
            <div class="core-center" id="coreCenter">
                <h1>JARVIS</h1>
                <span>MARK IX PRO</span>
            </div>
        </div>

        <div class="visualizer">
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        </div>
        <div class="hint" id="hint">Tippen & sprechen • Sendet automatisch</div>
    </div>

    <div class="hud-panel" id="status">Alle Systeme verbunden, Sir. Gmail, Kalender, Kontakte und Apps sind einsatzbereit.</div>

    <div class="quick-apps">
        <div class="chip" onclick="quickCmd('Wie sieht mein Kalender heute und morgen aus?')">📅 Termine</div>
        <div class="chip" onclick="quickCmd('Lies meine ungelesenen E-Mails vor.')">📧 E-Mails</div>
        <div class="chip" onclick="quickCmd('Gib mir mein komplettes Tagesbriefing.')">📋 Briefing</div>
        <div class="chip" onclick="quickCmd('Öffne WhatsApp')">💬 WhatsApp</div>
        <div class="chip" onclick="quickCmd('Öffne Google Maps')">🗺️ Maps</div>
    </div>

    <div class="input-box">
        <input type="text" id="msg" placeholder="Befehl an JARVIS..." onkeypress="if(event.key==='Enter') sendText()">
        <button class="send-btn" onclick="sendText()">SEND</button>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        const statusEl = document.getElementById('status');
        const hintEl = document.getElementById('hint');
        const memCountEl = document.getElementById('memCount');
        const coreCenter = document.getElementById('coreCenter');
        const bars = document.querySelectorAll('.bar');
        const player = document.getElementById('player');

        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;
        let activeStream = null;
        let audioCtx = null;
        let silenceTimer = null;
        let animFrame = null;

        let userMemory = JSON.parse(localStorage.getItem('jarvis_memory') || '[]');
        let chatHistory = JSON.parse(localStorage.getItem('jarvis_history') || '[]');

        function updateMemBadge() {
            memCountEl.innerText = "GEDÄCHTNIS: " + userMemory.length;
        }
        updateMemBadge();

        function showMemory() {
            if (userMemory.length === 0) {
                statusEl.innerText = "Ihr privates Gedächtnis ist noch leer, Sir.";
            } else {
                statusEl.innerHTML = "<strong>Gespeicherte Notizen:</strong><br><br>" + userMemory.map((m, i) => (i+1) + ". " + m).join("<br>");
            }
        }

        function setBars(level) {
            bars.forEach((bar, i) => {
                const factor = Math.sin((i + 1) * 0.7) * 0.5 + 0.7;
                const h = Math.max(5, Math.min(22, level * factor));
                bar.style.height = h + 'px';
            });
        }

        function setState(state) {
            document.body.classList.remove('listening', 'thinking', 'speaking');
            coreCenter.style.transform = '';
            setBars(5);
            if (state) document.body.classList.add(state);
        }

        function unlockAudio() {
            player.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";
            player.play().catch(() => {});
        }

        player.onplay = () => setState('speaking');
        player.onended = () => setState(null);

        function stopRecording() {
            if (!isRecording) return;
            isRecording = false;
            if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
            if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
            if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
        }

        async function toggleRecord() {
            unlockAudio();
            if (isRecording) { stopRecording(); return; }

            try {
                activeStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                audioChunks = [];
                let options = {};
                if (MediaRecorder.isTypeSupported('audio/webm')) options = { mimeType: 'audio/webm' };
                else if (MediaRecorder.isTypeSupported('audio/mp4')) options = { mimeType: 'audio/mp4' };

                mediaRecorder = new MediaRecorder(activeStream, options);
                mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) audioChunks.push(e.data); };

                mediaRecorder.onstop = async () => {
                    activeStream.getTracks().forEach(t => t.stop());
                    const mimeType = mediaRecorder.mimeType || 'audio/webm';
                    const blob = new Blob(audioChunks, { type: mimeType });
                    if (blob.size < 1000) {
                        setState(null);
                        statusEl.innerText = "Nichts gehört, Sir. Bitte erneut tippen.";
                        hintEl.innerText = "Tippen & sprechen • Sendet automatisch";
                        return;
                    }
                    await sendAudio(blob, mimeType);
                };

                mediaRecorder.start();
                isRecording = true;
                setState('listening');
                statusEl.innerText = "Ich höre zu, Sir...";
                hintEl.innerText = "Sprechen Sie jetzt — sendet nach kurzer Pause";

                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const source = audioCtx.createMediaStreamSource(activeStream);
                const analyser = audioCtx.createAnalyser();
                analyser.fftSize = 512;
                source.connect(analyser);
                const dataArray = new Uint8Array(analyser.frequencyBinCount);

                let hasSpoken = false;
                const startTime = Date.now();

                function monitorVolume() {
                    if (!isRecording) return;
                    analyser.getByteFrequencyData(dataArray);
                    let sum = 0;
                    for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
                    const avg = sum / dataArray.length;

                    const scale = 1 + Math.min(avg / 220, 0.14);
                    coreCenter.style.transform = `scale(${scale.toFixed(2)})`;
                    setBars(5 + avg * 0.6);

                    if (avg > 14) {
                        hasSpoken = true;
                        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
                    } else if (hasSpoken && !silenceTimer) {
                        silenceTimer = setTimeout(() => stopRecording(), 1500);
                    } else if (!hasSpoken && (Date.now() - startTime > 7000)) {
                        stopRecording();
                    }
                    animFrame = requestAnimationFrame(monitorVolume);
                }
                monitorVolume();
            } catch (err) {
                setState(null);
                statusEl.innerText = "Mikrofon-Zugriff erforderlich, Sir.";
            }
        }

        async function sendAudio(blob, mimeType) {
            setState('thinking');
            statusEl.innerText = "Verarbeite Anfrage, Sir...";
            hintEl.innerText = "Verbinde mit Diensten...";
            const reader = new FileReader();
            reader.readAsDataURL(blob);
            reader.onloadend = async () => {
                const base64Audio = reader.result.split(',')[1];
                await callBackend({ audio: base64Audio, mime_type: mimeType });
            };
        }

        function quickCmd(cmd) {
            unlockAudio();
            setState('thinking');
            statusEl.innerText = "Verarbeite Befehl, Sir...";
            callBackend({ message: cmd });
        }

        async function sendText() {
            unlockAudio();
            const input = document.getElementById('msg');
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            setState('thinking');
            statusEl.innerText = "Verarbeite Befehl, Sir...";
            await callBackend({ message: text });
        }

        async function callBackend(payload) {
            payload.memory = userMemory;
            payload.history = chatHistory.slice(-6);
            payload.local_time = new Date().toISOString();
            payload.local_time_str = new Date().toLocaleString('de-DE');

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                setState(null);
                hintEl.innerText = "Tippen & sprechen • Sendet automatisch";

                if (data.error) {
                    statusEl.innerText = data.error;
                    return;
                }

                if (data.new_memory && data.new_memory.trim() !== "") {
                    userMemory.push(data.new_memory.trim());
                    localStorage.setItem('jarvis_memory', JSON.stringify(userMemory));
                    updateMemBadge();
                }

                if (data.user_said) {
                    chatHistory.push({ role: "user", text: data.user_said });
                }
                chatHistory.push({ role: "jarvis", text: data.reply });
                localStorage.setItem('jarvis_history', JSON.stringify(chatHistory.slice(-10)));

                statusEl.innerHTML = "";
                const textDiv = document.createElement('div');
                textDiv.innerText = data.reply;
                statusEl.appendChild(textDiv);

                if (data.action_url) {
                    const btn = document.createElement('a');
                    btn.href = data.action_url;
                    btn.className = "action-btn";
                    btn.innerText = data.action_label || "App öffnen";
                    statusEl.appendChild(btn);
                    setTimeout(() => { window.location.href = data.action_url; }, 700);
                }

                if (data.audio) {
                    player.src = "data:audio/mp3;base64," + data.audio;
                    player.play().catch(() => {});
                }
            } catch (err) {
                setState(null);
                statusEl.innerText = "Verbindungsfehler, Sir.";
            }
        }
    </script>
</body>
</html>
"""

def call_google_bridge(payload):
    bridge_url = os.environ.get("GOOGLE_BRIDGE_URL", "").strip()
    if not bridge_url:
        return {"status": "error", "message": "GOOGLE_BRIDGE_URL fehlt in Render"}
    try:
        req = urllib.request.Request(
            bridge_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status": "error", "message": str(e)}

PLANNER_PROMPT = """Du bist das Routing-System von J.A.R.V.I.S.
Analysiere die Anfrage des Nutzers (Audio oder Text) und entscheide, ob Daten aus Google (Kalender, Gmail, Kontakte) benötigt werden oder eine Aktion ausgeführt werden soll.
Aktuelle ISO-Zeit des Nutzers: {iso_time} (Lokal: {local_time})

Verfügbare Google-Aktionen (tool_action):
- "none": Keine Google-Daten nötig (normale Frage, App öffnen ohne Kontakt-Suche, Notiz merken)
- "get_calendar": Nutzer fragt nach Terminen, Kalender, Tagesplan oder Briefing
- "add_calendar": Nutzer möchte einen Termin in den Kalender eintragen (benötigt start_iso im Format YYYY-MM-DDTHH:MM:SS, title, duration_minutes)
- "get_emails": Nutzer fragt nach E-Mails, Posteingang oder Briefing
- "send_email": Nutzer möchte eine E-Mail senden (benötigt to, subject, body)
- "find_contact": Nutzer möchte jemanden anrufen, eine WhatsApp-Nachricht an eine Person senden oder deren Nummer/E-Mail wissen (benötigt contact_name)

Antworte NUR als JSON:
{{
  "user_said": "Was der Nutzer auf Deutsch gesagt hat",
  "tool_action": "none | get_calendar | add_calendar | get_emails | send_email | find_contact",
  "params": {{
    "contact_name": "",
    "title": "",
    "start_iso": "",
    "duration_minutes": 60,
    "location": "",
    "to": "",
    "subject": "",
    "body": ""
  }}
}}
"""

FINAL_PROMPT = """Du bist J.A.R.V.I.S., der hochintelligente, persönliche KI-Assistent von Sir.
Antworte IMMER auf perfektem Deutsch, höflich, präzise (maximal 2-3 Sätze, ohne Sternchen oder Markdown) und nenne den Nutzer 'Sir'.

Nutze die übergebenen Google-Ergebnisse (Kalender, E-Mails, gefundene Kontakte) und das private Gedächtnis.
Wenn ein Kontakt gefunden wurde und Sir eine WhatsApp senden oder anrufen wollte:
- Formatiere die Telefonnummer international ohne Leerzeichen oder '+' für WhatsApp (z.B. aus 0176 123456 mache 49176123456) und setze action_url auf: "https://wa.me/49176123456?text=..."
- Oder für Anruf: "tel:+49176123456"

Weitere App-Aktionen (action_url):
- WhatsApp allgemein: "https://wa.me/?text=..."
- Google Maps: "https://www.google.com/maps/search/?api=1&query=..."
- YouTube: "https://www.youtube.com/results?search_query=..."
- Google Suche: "https://www.google.com/search?q=..."
- Spotify: "https://open.spotify.com/search/..."

Wenn Sir sagt "Merke dir...", schreibe die Info kurz in 'new_memory'.

Antworte ausschließlich als JSON:
{{
  "reply": "Deine gesprochene Antwort an Sir",
  "new_memory": "",
  "action_url": "",
  "action_label": ""
}}
"""

async def make_voice(text):
    clean_text = text.replace("*", "").replace("#", "")
    communicate = edge_tts.Communicate(clean_text, "de-DE-KillianNeural")
    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return base64.b64encode(audio_bytes).decode("utf-8")

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/manifest.json")
def manifest():
    return jsonify(MANIFEST_JSON)

@app.route("/icon.svg")
def icon():
    return Response(ICON_SVG, mimetype="image/svg+xml")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY fehlt in Render!"}), 500

        data = request.json or {}
        memory = data.get("memory", [])
        history = data.get("history", [])
        iso_time = data.get("local_time", datetime.now().isoformat())
        local_time_str = data.get("local_time_str", datetime.now().strftime("%d.%m.%Y %H:%M"))

        client = genai.Client(api_key=api_key)

        # Hapi 1: Kupto komandën dhe vendos nëse duhen të dhëna nga Google
        planner_sys = PLANNER_PROMPT.format(iso_time=iso_time, local_time=local_time_str)
        if "audio" in data:
            audio_bytes = base64.b64decode(data["audio"])
            mime_type = data.get("mime_type", "audio/webm").split(";")[0]
            step1_contents = [
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Analysiere diese deutsche Sprachnachricht."
            ]
        else:
            step1_contents = [data.get("message", "")]

        step1_res = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=step1_contents,
            config=types.GenerateContentConfig(
                system_instruction=planner_sys,
                response_mime_type="application/json"
            )
        )
        plan = json.loads(step1_res.text)
        user_said = plan.get("user_said", data.get("message", ""))
        tool_action = plan.get("tool_action", "none")
        params = plan.get("params", {})

        # Hapi 2: Ekzekuto lidhjen me Google Bridge nëse kërkohet
        tool_result = {}
        if tool_action == "get_calendar":
            tool_result = call_google_bridge({"action": "get_calendar"})
        elif tool_action == "add_calendar":
            tool_result = call_google_bridge({
                "action": "add_calendar",
                "title": params.get("title", "Termin"),
                "start_iso": params.get("start_iso"),
                "duration_minutes": params.get("duration_minutes", 60),
                "location": params.get("location", "")
            })
        elif tool_action == "get_emails":
            tool_result = call_google_bridge({"action": "get_emails"})
        elif tool_action == "send_email":
            tool_result = call_google_bridge({
                "action": "send_email",
                "to": params.get("to"),
                "subject": params.get("subject", "Nachricht von JARVIS"),
                "body": params.get("body", "")
            })
        elif tool_action == "find_contact":
            tool_result = call_google_bridge({
                "action": "find_contact",
                "name": params.get("contact_name", "")
            })

        # Hapi 3: Gjenero përgjigjen përfundimtare të JARVIS
        final_context = (
            f"Aktuelle Zeit: {local_time_str}\n"
            f"Nutzer-Anfrage: {user_said}\n"
            f"Privates Gedächtnis: {json.dumps(memory, ensure_ascii=False)}\n"
            f"Gesprächsverlauf: {json.dumps(history, ensure_ascii=False)}\n"
            f"Google-Daten-Ergebnis ({tool_action}): {json.dumps(tool_result, ensure_ascii=False)}"
        )

        step2_res = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=final_context,
            config=types.GenerateContentConfig(
                system_instruction=FINAL_PROMPT,
                response_mime_type="application/json"
            )
        )

        result = json.loads(step2_res.text)
        reply = result.get("reply", "Zu Befehl, Sir.")
        new_memory = result.get("new_memory", "")
        action_url = result.get("action_url", "")
        action_label = result.get("action_label", "")

        audio_b64 = asyncio.run(make_voice(reply))
        return jsonify({
            "user_said": user_said,
            "reply": reply,
            "new_memory": new_memory,
            "action_url": action_url,
            "action_label": action_label,
            "audio": audio_b64
        })
    except Exception as e:
        return jsonify({"error": f"Fehler: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
