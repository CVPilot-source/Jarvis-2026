import os
import re
import time
import json
import base64
import asyncio
import urllib.request
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, Response, send_file
from google import genai
from google.genai import types
import edge_tts

app = Flask(__name__)
ICAL_CACHE = {"ts": 0, "events": []}

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="115" fill="#020617"/>
  <circle cx="256" cy="256" r="155" fill="none" stroke="#00E5FF" stroke-width="6" stroke-dasharray="30 15"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#FF9900" stroke-width="4" stroke-dasharray="15 10"/>
  <circle cx="256" cy="256" r="20" fill="#FF9900"/>
</svg>"""

HTML_PAGE = """<!DOCTYPE html>
<html lang="sq">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#020617">
    <link rel="manifest" href="/manifest.json">
    <title>NEO // HOLOGRAPHIC VOICE CORE</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

        :root {
            --cyan: #00E5FF;
            --orange: #FF9900;
            --bg: #020617;
            --panel: rgba(3, 10, 26, 0.75);
            --text: #F8FAFC;
            --muted: #64748B;
        }

        body.listening { --cyan: #10B981; }
        body.thinking  { --cyan: #00E5FF; }
        body.speaking  { --cyan: #A855F7; }

        * { box-sizing: border-box; user-select: none; -webkit-tap-highlight-color: transparent; }

        html, body {
            margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden;
            background-color: var(--bg);
            background-image:
                radial-gradient(circle at 50% 45%, rgba(0, 229, 255, 0.08) 0%, transparent 65%),
                linear-gradient(rgba(0, 229, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 229, 255, 0.03) 1px, transparent 1px);
            background-size: 100% 100%, 32px 32px, 32px 32px;
            color: var(--text);
            font-family: 'Rajdhani', sans-serif;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: center;
            padding: 24px 16px;
        }

        /* TOP HEADER */
        .header {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            z-index: 10;
        }
        .title {
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 8px;
            color: var(--text);
            text-shadow: 0 0 16px rgba(0, 229, 255, 0.4);
            margin: 0;
        }
        .status-badge {
            display: flex;
            align-items: center;
            gap: 6px;
            background: var(--panel);
            border: 1px solid rgba(0, 229, 255, 0.25);
            padding: 3px 12px;
            border-radius: 999px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            letter-spacing: 2px;
            color: var(--cyan);
            text-transform: uppercase;
        }
        .status-dot {
            width: 6px; height: 6px;
            border-radius: 50%;
            background: var(--cyan);
            box-shadow: 0 0 8px var(--cyan);
            animation: pulseDot 2s infinite;
        }
        @keyframes pulseDot {
            0% { opacity: 0.4; }
            50% { opacity: 1; transform: scale(1.2); }
            100% { opacity: 0.4; }
        }

        /* CENTER HOLOGRAPHIC BUST CONTAINER */
        .hologram-stage {
            position: relative;
            width: 280px;
            height: 280px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            z-index: 5;
        }
        .holo-glow {
            position: absolute;
            inset: 0;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(0,229,255,0.15) 0%, rgba(255,153,0,0.05) 50%, transparent 75%);
            animation: pulseGlow 4s ease-in-out infinite alternate;
        }
        @keyframes pulseGlow {
            0% { transform: scale(0.9); opacity: 0.6; }
            100% { transform: scale(1.15); opacity: 1; }
        }
        .holo-svg {
            width: 100%;
            height: 100%;
            filter: drop-shadow(0 0 12px rgba(0, 229, 255, 0.4));
            animation: floatHolo 5s ease-in-out infinite;
        }
        @keyframes floatHolo {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-8px); }
        }

        /* PROMPT & SUBTEXT */
        .prompt-container {
            text-align: center;
            z-index: 10;
            margin-bottom: 12px;
        }
        .wake-text {
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 2px;
            color: var(--text);
            margin: 0 0 4px 0;
            text-shadow: 0 0 10px rgba(0,229,255,0.3);
        }
        .listening-subtext {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            letter-spacing: 1.5px;
            color: var(--muted);
            text-transform: uppercase;
        }

        /* BOTTOM MIC INDICATOR */
        .mic-dock {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            z-index: 10;
            margin-bottom: 10px;
        }
        .mic-btn {
            width: 64px; height: 64px;
            border-radius: 50%;
            background: linear-gradient(135deg, rgba(0,229,255,0.15), rgba(255,153,0,0.15));
            border: 1.5px solid var(--cyan);
            color: var(--text);
            font-size: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.25);
            transition: transform 0.2s, border-color 0.2s;
        }
        .mic-btn:active { transform: scale(0.92); }
        body.listening .mic-btn {
            border-color: #10B981;
            box-shadow: 0 0 30px rgba(16, 185, 129, 0.5);
            animation: micPulse 1s infinite;
        }
        @keyframes micPulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.06); }
            100% { transform: scale(1); }
        }
    </style>
</head>
<body>
    <!-- TOP HEADER -->
    <div class="header">
        <h1 class="title">N E O</h1>
        <div class="status-badge">
            <span class="status-dot"></span>
            <span id="statusText">AKTIV</span>
        </div>
    </div>

    <!-- CENTER HOLOGRAPHIC BUST (SVG) -->
    <div class="hologram-stage" onclick="toggleListening()" title="Kliko për të folur">
        <div class="holo-glow"></div>
        <svg class="holo-svg" viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
            <!-- Rrjetë rrethore sfondi -->
            <circle cx="150" cy="150" r="120" fill="none" stroke="rgba(0,229,255,0.12)" stroke-width="1" stroke-dasharray="6 6"/>
            <circle cx="150" cy="150" r="95" fill="none" stroke="rgba(255,153,0,0.15)" stroke-width="1"/>
            
            <!-- Silueta e bustit holografik pa fytyrë (Linja dhe pika cyan & portokalli) -->
            <g stroke="rgba(0,229,255,0.6)" stroke-width="1.5" fill="none" stroke-linecap="round">
                <!-- Vala e supeve dhe gjoksit -->
                <path d="M70,240 Q110,210 150,210 Q190,210 230,240" opacity="0.8"/>
                <path d="M90,255 Q150,225 210,255" stroke="rgba(255,153,0,0.7)" stroke-width="1"/>
                
                <!-- Qafa -->
                <path d="M130,210 L130,170" />
                <path d="M170,210 L170,170" />
                
                <!-- Konturi i kokës (faceless bust) -->
                <path d="M120,170 Q115,130 125,95 Q135,70 150,65 Q165,70 175,95 Q185,130 180,170" />
                
                <!-- Unaza e energjisë në kokë -->
                <ellipse cx="150" cy="80" rx="22" ry="7" stroke="rgba(255,153,0,0.8)" stroke-width="1.2"/>
            </g>

            <!-- Pikat e dritës neural (hologram nodes) -->
            <g fill="#00E5FF">
                <circle cx="150" cy="65" r="3" />
                <circle cx="125" cy="100" r="2" />
                <circle cx="175" cy="100" r="2" />
                <circle cx="150" cy="135" r="2.5" fill="#FF9900" />
                <circle cx="130" cy="170" r="2" />
                <circle cx="170" cy="170" r="2" />
                <circle cx="150" cy="210" r="3" fill="#FF9900" />
                <circle cx="110" cy="225" r="2" />
                <circle cx="190" cy="225" r="2" />
            </g>

            <!-- Lidhje shtesë fije drite -->
            <path d="M150,135 L125,100 M150,135 L175,100 M150,135 L150,65 M150,210 L130,170 M150,210 L170,170" stroke="rgba(0,229,255,0.25)" stroke-width="1"/>
        </svg>
    </div>

    <!-- PROMPT TEXT -->
    <div class="prompt-container">
        <p class="wake-text">Thuaj: „Hej Neo“</p>
        <span class="listening-subtext" id="subStatus">Po të dëgjoj…</span>
    </div>

    <!-- BOTTOM MIC ICON -->
    <div class="mic-dock">
        <div class="mic-btn" onclick="toggleListening()">🎙️</div>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        let isRec = false, isSpk = false, inConv = false;
        let rec = null, stream = null, chunks = [], wakeRec = null;
        const player = document.getElementById('player');
        const subStatus = document.getElementById('subStatus');

        function setVisualState(state) {
            document.body.className = state || '';
            if (state === 'listening') {
                subStatus.innerText = "Dëgjoj komandën tuaj...";
            } else if (state === 'thinking') {
                subStatus.innerText = "Duke analizuar...";
            } else if (state === 'speaking') {
                subStatus.innerText = "NEO po flet...";
            } else {
                subStatus.innerText = "Po të dëgjoj…";
            }
        }

        // --- WAKE WORD & CONTINUOUS LISTENING ---
        function startWakeWord() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) return;
            try {
                wakeRec = new SpeechRecognition();
                wakeRec.lang = 'sq-AL'; // Ose 'de-DE' sipas dëshirës
                wakeRec.continuous = true;
                wakeRec.interimResults = true;

                wakeRec.onresult = (e) => {
                    for (let i = e.resultIndex; i < e.results.length; i++) {
                        const t = e.results[i][0].transcript.toLowerCase();
                        if (t.includes('hej neo') || t.includes('hey neo') || t.includes('neo')) {
                            if (wakeRec) { try { wakeRec.abort(); } catch(err){} }
                            inConv = true;
                            startRecordingAudio();
                            return;
                        }
                    }
                };
                wakeRec.onend = () => {
                    if (!isRec && !isSpk && !inConv) {
                        setTimeout(startWakeWord, 800);
                    }
                };
                wakeRec.start();
            } catch(e) {}
        }

        function toggleListening() {
            if (isSpk) { player.pause(); isSpk = false; setVisualState(null); return; }
            if (isRec) { isRec = false; if (rec && rec.state !== 'inactive') rec.stop(); return; }
            inConv = true;
            startRecordingAudio();
        }

        async function startRecordingAudio() {
            if (isRec || isSpk) return;
            if (wakeRec) { try { wakeRec.abort(); } catch(e){} }
            try {
                stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
                chunks = [];
                rec = new MediaRecorder(stream, { audioBitsPerSecond: 16000 });
                rec.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
                rec.onstop = () => {
                    stream.getTracks().forEach(t => t.stop());
                    const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
                    if (blob.size < 600) { inConv = false; setVisualState(null); startWakeWord(); return; }
                    setVisualState('thinking');
                    const reader = new FileReader();
                    reader.readAsDataURL(blob);
                    reader.onloadend = () => {
                        sendToNeoBackend({ audio: reader.result.split(',')[1], mime_type: (rec.mimeType || 'audio/webm').split(';')[0] });
                    };
                };
                rec.start();
                isRec = true;
                setVisualState('listening');
                setTimeout(() => { if (isRec) { isRec = false; rec.stop(); } }, 6000);
            } catch(e) {
                inConv = false;
                setVisualState(null);
                startWakeWord();
            }
        }

        player.onplay = () => { isSpk = true; setVisualState('speaking'); };
        player.onended = () => {
            isSpk = false;
            setVisualState(null);
            if (inConv) setTimeout(startRecordingAudio, 400);
            else startWakeWord();
        };

        async function sendToNeoBackend(payload) {
            payload.mode = "ARBEIT";
            payload.memory = JSON.parse(localStorage.getItem('neo_memory') || '[]');
            payload.local_time_str = new Date().toLocaleString('de-DE');
            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const d = await res.json();
                if (d.error) { inConv = false; setVisualState(null); startWakeWord(); return; }
                if (d.end_conversation) inConv = false;
                if (d.new_memory) {
                    let mem = JSON.parse(localStorage.getItem('neo_memory') || '[]');
                    mem.push(d.new_memory);
                    localStorage.setItem('neo_memory', JSON.stringify(mem));
                }
                if (d.audio) {
                    player.src = "data:audio/mp3;base64," + d.audio;
                    player.play().catch(() => { isSpk = false; setVisualState(null); startWakeWord(); });
                } else {
                    setVisualState(null);
                    startWakeWord();
                }
            } catch(e) {
                inConv = false;
                setVisualState(null);
                startWakeWord();
            }
        }

        window.onload = startWakeWord;
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

SYSTEM_PROMPT = """Du bist NEO, der sprachgesteuerte KI-Assistent von Margil (Kundenbetreuer Gebäudereinigung Hamburg).
Modus: {mode} | Zeit: {local_time}. Antworte kurz, direkt, präzise und professionell auf Deutsch (oder Albanisch falls angesprochen). Keine Karten, kein Markdown, keine Sternchen.
- Gespräch Ende ("Danke", "Stopp"): `end_conversation`: true.
Antworte NUR als JSON:
{{"reply":"","voice_lang":"de","copy_text":"","new_memory":"","action_url":"","action_label":"","end_conversation":false}}"""

async def make_voice(text, lang="de"):
    clean = text.replace("*", "").replace("#", "").strip()
    voice = "sq-AL-IlirNeural" if lang == "sq" else "de-DE-FlorianMultilingualNeural"
    comm = edge_tts.Communicate(clean, voice, rate="+10%")
    buf = b""
    async for c in comm.stream():
        if c["type"] == "audio":
            buf += c["data"]
    return base64.b64encode(buf).decode("utf-8")

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/avatar")
def avatar():
    base = os.path.dirname(os.path.abspath(__file__))
    for f in os.listdir(base):
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return send_file(os.path.join(base, f))
    return Response(ICON_SVG, mimetype="image/svg+xml")

@app.route("/calendar_preview")
def cal_prev():
    return jsonify({"events": parse_upcoming_events()[:3]})

@app.route("/manifest.json")
def manifest():
    return jsonify({
        "name": "NEO",
        "short_name": "NEO",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#020617",
        "theme_color": "#020617",
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
        events = parse_upcoming_events()
        cal_txt = "\n".join([f"- {e['time']}: {e['title']}" for e in events]) or "Keine Termine."

        parts = []
        if "audio" in data:
            parts.append(types.Part.from_bytes(data=base64.b64decode(data["audio"]), mime_type=data.get("mime_type", "audio/webm")))
            parts.append("Höre dir diese Sprachnachricht von Margil an und antworte passend.")
        else:
            parts.append("Bereit.")

        parts.append(f"Kalender:\n{cal_txt}\nNotizen: {json.dumps(data.get('memory', []), ensure_ascii=False)}")

        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=parts,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT.format(mode=data.get("mode", "ARBEIT"), local_time=data.get("local_time_str", "")),
                temperature=0.3
            )
        )
        m = re.search(r'\{.*\}', resp.text.strip(), re.DOTALL)
        res = json.loads(m.group(0)) if m else {"reply": resp.text.strip()}
        reply = res.get("reply", "Zu Befehl.")
        audio = asyncio.run(make_voice(reply, res.get("voice_lang", "de")))
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
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(0.0.0.0", port=int(os.environ.get("PORT", 5000)))
