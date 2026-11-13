import os
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JARVIS MARK IX</title>
    <style>
        body { margin: 0; background: #060B14; color: #00F0FF; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
        .ring { width: 200px; height: 200px; border-radius: 50%; border: 4px solid #00F0FF; box-shadow: 0 0 30px #00F0FF, inset 0 0 20px #00F0FF; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; transition: 0.3s; user-select: none; }
        .ring.active { transform: scale(1.1); border-color: #FF8C00; box-shadow: 0 0 50px #FF8C00; }
        h1 { margin: 0; font-size: 28px; letter-spacing: 4px; }
        p { font-size: 10px; letter-spacing: 2px; opacity: 0.8; }
        #status { margin-top: 30px; font-size: 15px; text-align: center; padding: 0 20px; min-height: 40px; max-width: 90%; }
        .input-box { position: fixed; bottom: 25px; display: flex; gap: 8px; width: 90%; max-width: 400px; }
        input { flex: 1; padding: 12px; border-radius: 20px; border: 1px solid #00F0FF; background: #0B1324; color: white; outline: none; }
        button { padding: 12px 18px; border-radius: 20px; border: none; background: #00F0FF; color: #060B14; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="ring" id="ring" onclick="startVoice()">
        <h1>JARVIS</h1>
        <p>MARK IX HYBRID</p>
    </div>
    <div id="status">Tippe auf den Kreis oder schreibe unten, Sir.</div>
    <div class="input-box">
        <input type="text" id="msg" placeholder="Nachricht an JARVIS..." onkeypress="if(event.key==='Enter') sendMsg()">
        <button onclick="sendMsg()">Senden</button>
    </div>
    <script>
        const statusEl = document.getElementById('status');
        const ring = document.getElementById('ring');

        async function startVoice() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                statusEl.innerText = "Sprache wird in diesem Browser nicht unterstützt. Bitte Chrome oder Safari nutzen.";
                return;
            }
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                stream.getTracks().forEach(track => track.stop());
            } catch (err) {
                statusEl.innerText = "Mikrofon-Zugriff blockiert (" + err.name + "). Bitte oben in der Adressleiste erlauben.";
                return;
            }

            const recog = new SpeechRecognition();
            recog.lang = 'de-DE';
            recog.interimResults = false;
            ring.classList.add('active');
            statusEl.innerText = "Höre zu, Sir...";

            recog.onresult = (e) => {
                const text = e.results[0][0].transcript;
                document.getElementById('msg').value = text;
                sendMsg();
            };
            recog.onerror = (e) => {
                ring.classList.remove('active');
                statusEl.innerText = "Mikrofon-Fehler: " + e.error;
            };
            recog.onend = () => {
                if (statusEl.innerText === "Höre zu, Sir...") {
                    ring.classList.remove('active');
                    statusEl.innerText = "Nichts gehört. Bitte erneut tippen, Sir.";
                }
            };
            recog.start();
        }

        async function sendMsg() {
            const input = document.getElementById('msg');
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            ring.classList.add('active');
            statusEl.innerText = "Denke nach...";
            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text})
                });
                const data = await res.json();
                ring.classList.remove('active');
                statusEl.innerText = data.reply || data.error;
                if (data.audio) {
                    const audio = new Audio("data:audio/mp3;base64," + data.audio);
                    audio.play();
                }
            } catch (err) {
                ring.classList.remove('active');
                statusEl.innerText = "Verbindungsfehler.";
            }
        }
    </script>
</body>
</html>
"""

async def make_voice(text):
    communicate = edge_tts.Communicate(text, "de-DE-KillianNeural")
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
        user_msg = request.json.get("message", "")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction="Du bist J.A.R.V.I.S., ein hochintelligenter, höflicher KI-Assistent. Antworte immer kurz, präzise auf Deutsch und nenne den Nutzer 'Sir'."
            )
        )
        reply = response.text
        audio_b64 = asyncio.run(make_voice(reply))
        return jsonify({"reply": reply, "audio": audio_b64})
    except Exception as e:
        return jsonify({"error": f"Fehler: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
