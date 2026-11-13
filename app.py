import os
import json
import base64
import asyncio
from flask import Flask, request, jsonify, render_template_string
from google import genai
from google.genai import types
import edge_tts

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#060B14">
    <title>JARVIS MARK IX</title>
    <style>
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { margin: 0; background: #060B14; color: #00F0FF; font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: space-between; height: 100dvh; padding: 25px 15px 20px; overflow: hidden; }
        .ring { width: 175px; height: 175px; min-height: 175px; border-radius: 50%; border: 4px solid #00F0FF; box-shadow: 0 0 30px #00F0FF, inset 0 0 20px #00F0FF; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; transition: 0.25s; user-select: none; margin-top: 10px; }
        .ring.listening { transform: scale(1.1); border-color: #00FF88; box-shadow: 0 0 50px #00FF88, inset 0 0 25px #00FF88; color: #00FF88; }
        .ring.thinking { transform: scale(1.05); border-color: #FF8C00; box-shadow: 0 0 50px #FF8C00, inset 0 0 25px #FF8C00; color: #FF8C00; }
        h1 { margin: 0; font-size: 24px; letter-spacing: 4px; }
        p { font-size: 9px; letter-spacing: 2px; opacity: 0.85; margin: 4px 0 0; }
        .hint { font-size: 11px; opacity: 0.65; margin-top: 8px; }
        #status { flex: 1; width: 100%; max-width: 460px; overflow-y: auto; margin: 18px 0; font-size: 16px; line-height: 1.5; text-align: center; padding: 10px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #E0F7FA; }
        .action-btn { margin-top: 14px; padding: 12px 22px; border-radius: 25px; background: #00FF88; color: #060B14; font-weight: bold; text-decoration: none; font-size: 15px; display: inline-block; box-shadow: 0 0 15px rgba(0,255,136,0.4); }
        .input-box { display: flex; gap: 8px; width: 100%; max-width: 460px; }
        input { flex: 1; padding: 14px 16px; border-radius: 25px; border: 1px solid #00F0FF; background: #0B1324; color: white; font-size: 16px; outline: none; }
        button { padding: 14px 20px; border-radius: 25px; border: none; background: #00F0FF; color: #060B14; font-weight: bold; font-size: 15px; cursor: pointer; }
    </style>
</head>
<body>
    <div style="text-align:center;">
        <div class="ring" id="ring" onclick="toggleRecord()">
            <h1>JARVIS</h1>
            <p>MARK IX HYBRID</p>
        </div>
        <div class="hint" id="hint">Tippen zum Sprechen • Nochmal tippen zum Senden</div>
    </div>

    <div id="status">Bereit für Ihre Befehle, Sir.</div>

    <div class="input-box">
        <input type="text" id="msg" placeholder="Befehl an JARVIS..." onkeypress="if(event.key==='Enter') sendText()">
        <button onclick="sendText()">Senden</button>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        const statusEl = document.getElementById('status');
        const hintEl = document.getElementById('hint');
        const ring = document.getElementById('ring');
        const player = document.getElementById('player');

        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;
        let activeStream = null;

        function unlockAudio() {
            player.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";
            player.play().catch(() => {});
        }

        function setRing(state) {
            ring.classList.remove('listening', 'thinking');
            if (state) ring.classList.add(state);
        }

        async function toggleRecord() {
            unlockAudio();

            if (isRecording && mediaRecorder) {
                mediaRecorder.stop();
                isRecording = false;
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
                    await sendAudio(blob, mimeType);
                };

                mediaRecorder.start();
                isRecording = true;
                setRing('listening');
                statusEl.innerText = "Ich höre zu, Sir... (Tippen zum Beenden)";
                hintEl.innerText = "Aufnahme läuft...";
            } catch (err) {
                setRing(null);
                statusEl.innerText = "Mikrofon-Zugriff erforderlich. Bitte in den Browser-Einstellungen erlauben, Sir.";
            }
        }

        async function sendAudio(blob, mimeType) {
            setRing('thinking');
            statusEl.innerText = "Analysiere Sprache, Sir...";
            hintEl.innerText = "Verarbeite...";

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
            setRing('thinking');
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
                setRing(null);
                hintEl.innerText = "Tippen zum Sprechen • Nochmal tippen zum Senden";

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
                setRing(null);
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
