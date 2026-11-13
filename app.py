import os
import json
import base64
import asyncio
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
                radial-gradient(circle at 50% 32%, rgba(0, 240, 255, 0.12) 0%, transparent 55%),
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
            padding: 18px 16px 20px;
            overflow: hidden;
        }

        /* HUD Header */
        .hud-top {
            width: 100%;
            max-width: 480px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            letter-spacing: 2px;
            text-transform: uppercase;
            opacity: 0.8;
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

        /* Holographic Arc Reactor Core */
        .core-wrapper {
            position: relative;
            width: 240px;
            height: 240px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
            margin-top: 10px;
        }
        .ring-outer {
            position: absolute;
            width: 235px;
            height: 235px;
            border-radius: 50%;
            border: 2px dashed rgba(0, 240, 255, 0.45);
            animation: spinRight 24s linear infinite;
            transition: border-color 0.3s;
        }
        .ring-mid {
            position: absolute;
            width: 205px;
            height: 205px;
            border-radius: 50%;
            border: 4px solid transparent;
            border-top-color: var(--primary);
            border-bottom-color: var(--primary);
            box-shadow: 0 0 25px var(--glow);
            animation: spinLeft 10s linear infinite;
            transition: all 0.3s;
        }
        .ring-inner {
            position: absolute;
            width: 175px;
            height: 175px;
            border-radius: 50%;
            border: 2px dotted rgba(0, 240, 255, 0.75);
            animation: spinRight 16s linear infinite;
            transition: border-color 0.3s;
        }
        .core-center {
            position: relative;
            width: 146px;
            height: 146px;
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
            font-size: 23px;
            font-weight: 800;
            letter-spacing: 4px;
            text-shadow: 0 0 12px var(--primary);
        }
        .core-center span {
            font-size: 8.5px;
            letter-spacing: 2.5px;
            opacity: 0.85;
            margin-top: 4px;
        }

        /* States: Listening (Green) & Thinking (Orange) & Speaking (Cyan Pulse) */
        body.listening { --primary: #00FF88; --glow: rgba(0, 255, 136, 0.55); }
        body.listening .ring-mid { animation-duration: 3s; }
        body.thinking { --primary: #FF9500; --glow: rgba(255, 149, 0, 0.55); }
        body.thinking .ring-mid { animation-duration: 1.5s; }
        body.thinking .ring-inner { animation-duration: 2s; }
        body.speaking .core-center { animation: pulseSpeak 0.9s ease-in-out infinite alternate; }

        @keyframes spinRight { 100% { transform: rotate(360deg); } }
        @keyframes spinLeft { 100% { transform: rotate(-360deg); } }
        @keyframes pulseSpeak {
            0% { transform: scale(1); box-shadow: 0 0 25px var(--glow); }
            100% { transform: scale(1.07); box-shadow: 0 0 50px var(--glow); }
        }

        /* Sound Equalizer Bars */
        .visualizer {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
            height: 24px;
            margin-top: 8px;
        }
        .bar {
            width: 3.5px;
            height: 6px;
            background: var(--primary);
            border-radius: 3px;
            box-shadow: 0 0 8px var(--primary);
            transition: height 0.08s ease;
        }

        .hint {
            font-size: 11px;
            letter-spacing: 1px;
            opacity: 0.7;
            margin-top: 4px;
            text-align: center;
        }

        /* HUD Response Panel */
        .hud-panel {
            flex: 1;
            width: 100%;
            max-width: 460px;
            margin: 14px 0;
            padding: 16px;
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
            font-size: 16px;
            line-height: 1.55;
            color: #E0F7FA;
            box-shadow: inset 0 0 20px rgba(0, 240, 255, 0.06);
        }

        .action-btn {
            margin-top: 14px;
            padding: 12px 24px;
            border-radius: 25px;
            background: #00FF88;
            color: #030712;
            font-weight: 800;
            text-decoration: none;
            font-size: 14px;
            letter-spacing: 0.5px;
            display: inline-block;
            box-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
        }

        /* Input Area */
        .input-box {
            display: flex;
            gap: 8px;
            width: 100%;
            max-width: 460px;
        }
        input {
            flex: 1;
            padding: 14px 18px;
            border-radius: 25px;
            border: 1px solid rgba(0, 240, 255, 0.45);
            background: rgba(11, 19, 36, 0.85);
            color: white;
            font-size: 16px;
            outline: none;
        }
        input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 12px var(--glow);
        }
        button {
            padding: 14px 22px;
            border-radius: 25px;
            border: none;
            background: var(--primary);
            color: #030712;
            font-weight: 800;
            font-size: 14px;
            letter-spacing: 1px;
            cursor: pointer;
            box-shadow: 0 0 15px var(--glow);
        }
    </style>
</head>
<body>
    <div class="hud-top">
        <div><span class="status-dot"></span>SYSTEM ONLINE</div>
        <div id="modeLabel">STANDBY</div>
    </div>

    <div style="display:flex; flex-direction:column; align-items:center;">
        <div class="core-wrapper" id="coreWrapper" onclick="toggleRecord()">
            <div class="ring-outer"></div>
            <div class="ring-mid"></div>
            <div class="ring-inner"></div>
            <div class="core-center" id="coreCenter">
                <h1>JARVIS</h1>
                <span>MARK IX HUD</span>
            </div>
        </div>

        <div class="visualizer" id="visualizer">
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        </div>
        <div class="hint" id="hint">Tippen & sprechen • Sendet automatisch</div>
    </div>

    <div class="hud-panel" id="status">Bereit für Ihre Befehle, Sir.</div>

    <div class="input-box">
        <input type="text" id="msg" placeholder="Befehl eingeben..." onkeypress="if(event.key==='Enter') sendText()">
        <button onclick="sendText()">SEND</button>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        const statusEl = document.getElementById('status');
        const hintEl = document.getElementById('hint');
        const modeLabel = document.getElementById('modeLabel');
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

        function setBars(level) {
            bars.forEach((bar, i) => {
                const factor = Math.sin((i + 1) * 0.7) * 0.5 + 0.7;
                const h = Math.max(5, Math.min(24, level * factor));
                bar.style.height = h + 'px';
            });
        }

        function setState(state, label) {
            document.body.classList.remove('listening', 'thinking', 'speaking');
            coreCenter.style.transform = '';
            setBars(6);
            if (state) document.body.classList.add(state);
            if (label) modeLabel.innerText = label;
        }

        function unlockAudio() {
            player.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";
            player.play().catch(() => {});
        }

        player.onplay = () => setState('speaking', 'VOICE OUTPUT');
        player.onended = () => setState(null, 'STANDBY');

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

            if (isRecording) {
                stopRecording();
                return;
            }

            try {
                activeStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                audioChunks = [];

                let options = {};
                if (MediaRecorder.isTypeSupported('audio/webm')) {
                    options = { mimeType: 'audio/webm' };
                } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
                    options = { mimeType: 'audio/mp4' };
                }

                mediaRecorder = new MediaRecorder(activeStream, options);

                mediaRecorder.ondataavailable = (e) => {
                    if (e.data && e.data.size > 0) audioChunks.push(e.data);
                };

                mediaRecorder.onstop = async () => {
                    activeStream.getTracks().forEach(t => t.stop());
                    const mimeType = mediaRecorder.mimeType || 'audio/webm';
                    const blob = new Blob(audioChunks, { type: mimeType });
                    if (blob.size < 1000) {
                        setState(null, 'STANDBY');
                        statusEl.innerText = "Nichts gehört, Sir. Bitte erneut tippen.";
                        hintEl.innerText = "Tippen & sprechen • Sendet automatisch";
                        return;
                    }
                    await sendAudio(blob, mimeType);
                };

                mediaRecorder.start();
                isRecording = true;
                setState('listening', 'LISTENING');
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
                    setBars(6 + avg * 0.6);

                    if (avg > 14) {
                        hasSpoken = true;
                        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
                    } else if (hasSpoken && !silenceTimer) {
                        silenceTimer = setTimeout(() => {
                            stopRecording();
                        }, 1500);
                    } else if (!hasSpoken && (Date.now() - startTime > 7000)) {
                        stopRecording();
                    }
                    animFrame = requestAnimationFrame(monitorVolume);
                }
                monitorVolume();

            } catch (err) {
                setState(null, 'ERROR');
                statusEl.innerText = "Mikrofon-Zugriff erforderlich. Bitte in den Browser-Einstellungen erlauben, Sir.";
            }
        }

        async function sendAudio(blob, mimeType) {
            setState('thinking', 'PROCESSING');
            statusEl.innerText = "Analysiere Sprache, Sir...";
            hintEl.innerText = "KI-Analyse läuft...";

            const reader = new FileReader();
            reader.readAsDataURL(blob);
            reader.onloadend = async () => {
                const base64Audio = reader.result.split(',')[1];
                await callBackend({ audio: base64Audio, mime_type: mimeType });
            };
        }

        async function sendText() {
            unlockAudio();
            const input = document.getElementById('msg');
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            setState('thinking', 'PROCESSING');
            statusEl.innerText = "Verarbeite Befehl, Sir...";
            await callBackend({ message: text });
        }

        async function callBackend(payload) {
            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                setState(null, 'STANDBY');
                hintEl.innerText = "Tippen & sprechen • Sendet automatisch";

                if (data.error) {
                    statusEl.innerText = data.error;
                    return;
                }

                statusEl.innerHTML = "";
                const textDiv = document.createElement('div');
                textDiv.innerText = data.reply;
                statusEl.appendChild(textDiv);

                if (data.action_url) {
                    const btn = document.createElement('a');
                    btn.href = data.action_url;
                    btn.target = "_blank";
                    btn.className = "action-btn";
                    btn.innerText = data.action_label || "App öffnen";
                    statusEl.appendChild(btn);
                    setTimeout(() => { window.location.href = data.action_url; }, 600);
                }

                if (data.audio) {
                    player.src = "data:audio/mp3;base64," + data.audio;
                    player.play().catch(() => {});
                }
            } catch (err) {
                setState(null, 'OFFLINE');
                statusEl.innerText = "Verbindungsfehler, Sir.";
            }
        }
    </script>
</body>
</html>
"""

SYSTEM_PROMPT = """Du bist J.A.R.V.I.S., der persönliche KI-Assistent des Nutzers.
Du verstehst perfektes Hochdeutsch sowie umgangssprachliches Deutsch zu 100%.
Antworte IMMER auf Deutsch, höflich, präzise (maximal 2-3 Sätze, ohne Sternchen oder Markdown) und nenne den Nutzer 'Sir'.

Du hast direkten Zugriff auf Smartphone-Apps über URL-Aktionen. Wenn der Nutzer eine App öffnen, jemanden anrufen, eine Nachricht senden, navigieren oder etwas suchen möchte, gib zusätzlich eine passende 'action_url' und ein kurzes 'action_label' zurück:
- Telefonanruf: "tel:+49..." (oder "tel:" wenn keine Nummer genannt wurde)
- WhatsApp Nachricht: "https://wa.me/?text=..." (URL-kodierter Text) oder "https://wa.me/49..."
- SMS: "sms:?body=..."
- Navigation / Google Maps: "https://www.google.com/maps/search/?api=1&query=..."
- YouTube Suche/Öffnen: "https://www.youtube.com/results?search_query=..."
- Google Suche: "https://www.google.com/search?q=..."
- E-Mail schreiben: "mailto:?subject=...&body=..."
- Spotify Suche: "https://open.spotify.com/search/..."

Wenn keine App geöffnet werden soll, lasse 'action_url' und 'action_label' leer ("").
Antworte ausschließlich im folgenden JSON-Format:
{"reply": "Deine gesprochene Antwort an Sir", "action_url": "", "action_label": ""}
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
        client = genai.Client(api_key=api_key)

        if "audio" in data:
            audio_bytes = base64.b64decode(data["audio"])
            mime_type = data.get("mime_type", "audio/webm").split(";")[0]
            contents = [
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Höre dir diese Sprachnachricht auf Deutsch genau an und führe den Befehl aus."
            ]
        else:
            contents = data.get("message", "")

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )

        result = json.loads(response.text)
        reply = result.get("reply", "Zu Befehl, Sir.")
        action_url = result.get("action_url", "")
        action_label = result.get("action_label", "")

        audio_b64 = asyncio.run(make_voice(reply))
        return jsonify({
            "reply": reply,
            "action_url": action_url,
            "action_label": action_label,
            "audio": audio_b64
        })
    except Exception as e:
        return jsonify({"error": f"Fehler: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
