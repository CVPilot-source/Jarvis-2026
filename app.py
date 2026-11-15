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
  <rect width="512" height="512" rx="115" fill="#030712"/>
  <circle cx="256" cy="256" r="155" fill="none" stroke="#00E5FF" stroke-width="8" stroke-dasharray="16 10"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#FF9900" stroke-width="5"/>
  <circle cx="256" cy="256" r="24" fill="#FF9900"/>
</svg>"""

HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#030712">
    <link rel="manifest" href="/manifest.json">
    <title>N.E.O. // HOLOGRAPHIC VOICE CORE</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

        :root {
            --cyan: #00E5FF;
            --orange: #FF9900;
            --bg: #030712;
            --panel: rgba(8, 15, 30, 0.85);
            --border: rgba(0, 229, 255, 0.25);
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
                radial-gradient(circle at 50% 45%, rgba(0, 229, 255, 0.08) 0%, transparent 70%),
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
            font-size: 32px;
            font-weight: 700;
            letter-spacing: 10px;
            color: var(--text);
            text-shadow: 0 0 20px rgba(0, 229, 255, 0.5);
            margin: 0;
        }
        .status-badge {
            display: flex;
            align-items: center;
            gap: 6px;
            background: var(--panel);
            border: 1px solid var(--border);
            padding: 4px 14px;
            border-radius: 999px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
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

        /* CENTER HOLOGRAPHIC STAGE */
        .hologram-stage {
            position: relative;
            width: 300px;
            height: 300px;
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
            background: radial-gradient(circle, rgba(255,153,0,0.2) 0%, rgba(0,229,255,0.1) 50%, transparent 75%);
            animation: pulseGlow 4s ease-in-out infinite alternate;
        }
        @keyframes pulseGlow {
            0% { transform: scale(0.9); opacity: 0.6; }
            100% { transform: scale(1.15); opacity: 1; }
        }
        .holo-svg {
            width: 100%;
            height: 100%;
            filter: drop-shadow(0 0 15px rgba(0, 229, 255, 0.5));
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
        }
        .wake-text {
            font-size: 20px;
            font-weight: 600;
            letter-spacing: 2px;
            color: var(--text);
            margin: 0 0 4px 0;
            text-shadow: 0 0 12px rgba(0,229,255,0.4);
        }
        .listening-subtext {
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            letter-spacing: 1.5px;
            color: var(--muted);
            text-transform: uppercase;
        }

        /* BOTTOM DOCK */
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
            background: linear-gradient(135deg, rgba(0,229,255,0.2), rgba(255,153,0,0.2));
            border: 1.5px solid var(--cyan);
            color: var(--text);
            font-size: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 0 25px rgba(0, 229, 255, 0.3);
            transition: transform 0.2s, border-color 0.2s;
        }
        .mic-btn:active { transform: scale(0.92); }
    </style>
</head>
<body>
    <!-- TOP HEADER -->
    <div class="header">
        <h1 class="title">N E O</h1>
        <div class="status-badge">
            <span class="status-dot"></span>
            <span id="statusText">AKTIV 24/7</span>
        </div>
    </div>

    <!-- CENTER HOLOGRAPHIC BUST -->
    <div class="hologram-stage" onclick="toggleListening()" title="Tippen zum Sprechen">
        <div class="holo-glow"></div>
        <svg class="holo-svg" viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
            <circle cx="150" cy="150" r="130" fill="none" stroke="rgba(0,229,255,0.1)" stroke-width="1" stroke-dasharray="8 8"/>
            <circle cx="150" cy="150" r="105" fill="none" stroke="rgba(255,153,0,0.15)" stroke-width="1"/>
            <circle cx="150" cy="135" r="35" fill="url(#orangeGlow)" opacity="0.8"/>
            <defs>
                <radialGradient id="orangeGlow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stop-color="#FF9900" stop-opacity="0.9"/>
                    <stop offset="60%" stop-color="#FF5500" stop-opacity="0.4"/>
                    <stop offset="100%" stop-color="#030712" stop-opacity="0"/>
                </radialGradient>
            </defs>
            <g stroke="rgba(0,229,255,0.7)" stroke-width="1.5" fill="none" stroke-linecap="round">
                <path d="M60,250 Q100,210 150,210 Q200,210 240,250" opacity="0.9"/>
                <path d="M80,265 Q150,230 220,265" stroke="rgba(255,153,0,0.8)" stroke-width="1"/>
                <path d="M130,210 L130,165" />
                <path d="M170,210 L170,165" />
                <path d="M120,165 Q110,120 125,85 Q135,60 150,55 Q165,60 175,85 Q190,120 180,165" />
                <path d="M125,125 Q150,135 175,125" stroke="rgba(255,153,0,0.7)" />
                <path d="M130,145 Q150,155 170,145" stroke="rgba(0,229,255,0.9)" />
            </g>
            <g fill="#00E5FF">
                <circle cx="150" cy="55" r="3" fill="#FF9900"/>
                <circle cx="125" cy="90" r="2" />
                <circle cx="175" cy="90" r="2" />
                <circle cx="150" cy="135" r="3.5" fill="#FF9900" />
                <circle cx="110" cy="180" r="2" />
                <circle cx="190" cy="180" r="2" />
                <circle cx="150" cy="210" r="3" fill="#FF9900" />
            </g>
        </svg>
    </div>

    <!-- PROMPT TEXT -->
    <div class="prompt-container">
        <p class="wake-text" id="wakePrompt">Sage: „Hey Neo“</p>
        <span class="listening-subtext" id="subStatus">Lauscht im Hintergrund…</span>
    </div>

    <!-- BOTTOM MIC ICON -->
    <div class="mic-dock">
        <div class="mic-btn" onclick="toggleListening()">🎙️</div>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        let isRec = false, isSpk = false, inConv = false;
        let rec = null, stream = null, wakeRec = null;
        const player = document.getElementById('player');
        const subStatus = document.getElementById('subStatus');
        const wakePrompt = document.getElementById('wakePrompt');

        function setVisualState(state) {
            document.body.className = state || '';
            if (state === 'listening') {
                subStatus.innerText = "Ich höre zu...";
                wakePrompt.innerText = "Sprich jetzt...";
            } else if (state === 'thinking') {
                subStatus.innerText = "Analysiere...";
                wakePrompt.innerText = "Denkt nach...";
            } else if (state === 'speaking') {
                subStatus.innerText = "NEO spricht...";
                wakePrompt.innerText = "Antwortet...";
            } else {
                subStatus.innerText = "Lauscht im Hintergrund…";
                wakePrompt.innerText = "Sage: „Hey Neo“";
            }
        }

        function startWakeWord() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) return;
            try {
                wakeRec = new SpeechRecognition();
                wakeRec.lang = 'de-DE';
                wakeRec.continuous = true;
                wakeRec.interimResults = true;

                wakeRec.onresult = (e) => {
                    for (let i = e.resultIndex; i < e.results.length; i++) {
                        const t = e.results[i][0].transcript.toLowerCase();
                        if (t.includes('hey neo') || t.includes('hallo neo') || t.includes('neo')) {
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
                let chunks = [];
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

SYSTEM_PROMPT = """Du bist NEO, der hochintelligente KI-Assistent von Margil (Kundenbetreuer Gebäudereinigung Hamburg) und Social-Media-Direktor. Antworte IMMER strikt auf Deutsch.
Modus: {mode} | Zeit: {local_time}. Antworte souverän, ruhig, präzise und kurz auf Deutsch. Keine Sternchen oder Markdown.
Antworte NUR as JSON:
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
    for model_name in ["gemini-3.8-flash", "gemini-2.5-flash"]:
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
        "name": "NEO",
        "short_name": "NEO",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#030712",
        "theme_color": "#030712",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]
    })

@app.route("/icon.svg")
def icon():
    return Response(ICON_SVG, mimetype="image/svg+xml")

# --- TELEGRAM WEBHOOK PËR TË KAPUR KLIKIMET E BUTONAVE ---
@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.json or {}
        if "callback_query" in data:
            cq = data["callback_query"]
            callback_data = cq.get("data")
            callback_id = cq["id"]
            chat_id = cq["message"]["chat"]["id"]
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

            # Përgjigju Telegramit që butoni u procesua (që të hiqet animacioni i ngarkimit tek butoni)
            ans_text = "✅ Autorizimi u pranua!" if callback_data == "ok" else "❌ Autorizimi u refuzua!"
            if token:
                ans_payload = json.dumps({"callback_query_id": callback_id, "text": ans_text, "show_alert": True}).encode("utf-8")
                urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{token}/answerCallbackQuery", data=ans_payload, headers={"Content-Type": "application/json"}))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/telegram_notify", methods=["POST"])
def tg_notify():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        return jsonify({"ok": False, "error": "TELEGRAM_BOT_TOKEN fehlt in Render"})
    if not chat_id:
        try:
            u = json.loads(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=5).read().decode())
            if u.get("result"):
                chat_id = str(u["result"][-1]["message"]["chat"]["id"])
        except Exception:
            pass
    if not chat_id:
        return jsonify({"ok": False, "error": "Bitte sende zuerst 'Hallo' an deinen Bot in Telegram"})
    
    payload = json.dumps({
        "chat_id": chat_id,
        "text": (request.json or {}).get("text", "🔔 NEO Autorisierung anfrage"),
        "reply_markup": {"inline_keyboard": [[{"text": "✅ Autorisieren", "callback_data": "ok"}, {"text": "❌ Ablehnen", "callback_data": "no"}]]}
    }).encode("utf-8")
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=5)
    return jsonify({"ok": True})

@app.route("/chat", methods=["POST"])
def chat():
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        data = request.json or {}
        client = genai.Client(api_key=api_key)
        events = parse_upcoming_events()
        cal_txt = "\n".join([f"- {e['time']}: {e['title']}" for e in events]) or "Keine Termine."

        parts = [data.get("message", "Bereit."), f"Kalender:\n{cal_txt}\nNotizen: {json.dumps(data.get('memory', []), ensure_ascii=False)}"]
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT.format(mode=data.get("mode", "ARBEIT"), local_time=data.get("local_time_str", "")),
            temperature=0.3
        )
        resp = generate_with_fallback(client, parts, cfg)

        m = re.search(r'\{.*\}', resp.text.strip(), re.DOTALL)
        res = json.loads(m.group(0)) if m else {"reply": resp.text.strip()}
        reply = res.get("reply", "Zu Befehl, Margil.")
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
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run("0.0.0.0", port=int(os.environ.get("PORT", 5000)))
