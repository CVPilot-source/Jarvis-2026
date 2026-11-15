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
    <title>N.E.O. // COMMAND OS</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

        :root {
            --cyan: #00E5FF;
            --orange: #FF9900;
            --bg: #030712;
            --panel: rgba(8, 15, 30, 0.9);
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
                radial-gradient(circle at 50% 42%, rgba(0, 229, 255, 0.08) 0%, transparent 65%),
                linear-gradient(rgba(0, 229, 255, 0.025) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 229, 255, 0.025) 1px, transparent 1px);
            background-size: 100% 100%, 32px 32px, 32px 32px;
            color: var(--text);
            font-family: 'Rajdhani', sans-serif;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: center;
            padding: 16px;
        }

        /* TOP HEADER */
        .header {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            z-index: 10;
        }
        .title {
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 8px;
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
            padding: 3px 12px;
            border-radius: 999px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10.5px;
            letter-spacing: 1.5px;
            color: var(--cyan);
            text-transform: uppercase;
        }
        .status-dot {
            width: 5px; height: 5px;
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
            width: 260px;
            height: 260px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            z-index: 5;
            margin: auto 0;
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
            50% { transform: translateY(-6px); }
        }

        /* COMMAND DOCK (ELEGANT BUTTONS) */
        .command-dock {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 8px;
            max-width: 600px;
            z-index: 10;
            margin-bottom: 8px;
        }
        .cmd-btn {
            background: var(--panel);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 7px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.5px;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .cmd-btn:hover {
            border-color: var(--cyan);
            color: var(--cyan);
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.3);
            transform: translateY(-2px);
        }

        /* BOTTOM MIC & STATUS */
        .bottom-bar {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            z-index: 10;
        }
        .wake-text {
            font-size: 16px;
            font-weight: 600;
            letter-spacing: 1.5px;
            color: var(--text);
            margin: 0;
            text-shadow: 0 0 10px rgba(0,229,255,0.4);
        }
        .mic-btn {
            width: 54px; height: 54px;
            border-radius: 50%;
            background: linear-gradient(135deg, rgba(0,229,255,0.2), rgba(255,153,0,0.2));
            border: 1.5px solid var(--cyan);
            color: var(--text);
            font-size: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.3);
            transition: transform 0.2s;
        }
        .mic-btn:active { transform: scale(0.92); }

        /* HOLOGRAPHIC MODAL */
        .holo-modal {
            position: fixed; inset: 0; background: rgba(3, 7, 18, 0.85);
            backdrop-filter: blur(8px); z-index: 50; display: none;
            align-items: center; justify-content: center; padding: 16px;
        }
        .holo-modal.open { display: flex; }
        .holo-box {
            background: var(--panel); border: 1px solid var(--cyan);
            box-shadow: 0 0 35px rgba(0, 229, 255, 0.25);
            border-radius: 14px; width: 100%; max-width: 440px;
            padding: 20px; display: flex; flex-direction: column; gap: 14px;
        }
        .holo-head {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--border); padding-bottom: 8px;
            font-size: 14px; font-weight: 700; color: var(--cyan); letter-spacing: 1px;
        }
        .holo-content { max-height: 260px; overflow-y: auto; font-size: 13.5px; display: flex; flex-direction: column; gap: 8px; }
        .holo-row {
            padding: 8px 12px; background: rgba(0, 229, 255, 0.05);
            border-left: 3px solid var(--orange); border-radius: 6px;
        }
        .gold-pill {
            background: var(--orange); color: #030712; border: none; border-radius: 999px;
            padding: 8px 16px; font-size: 12px; font-weight: 700; cursor: pointer; text-align: center;
        }
        input, select {
            background: #030712; border: 1px solid var(--border); color: #fff;
            padding: 9px 12px; border-radius: 6px; font-family: 'Rajdhani', sans-serif; font-size: 14px;
        }
    </style>
</head>
<body>
    <!-- TOP HEADER -->
    <div class="header">
        <h1 class="title">N E O</h1>
        <div class="status-badge">
            <span class="status-dot"></span>
            <span id="statusText">HAMBURG • AKTIV</span>
        </div>
    </div>

    <!-- CENTER HOLOGRAPHIC CORE -->
    <div class="hologram-stage" onclick="toggleListening()" title="Tippen zum Sprechen">
        <div class="holo-glow"></div>
        <svg class="holo-svg" viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
            <circle cx="150" cy="150" r="125" fill="none" stroke="rgba(0,229,255,0.12)" stroke-width="1" stroke-dasharray="8 8"/>
            <circle cx="150" cy="150" r="100" fill="none" stroke="rgba(255,153,0,0.15)" stroke-width="1"/>
            <circle cx="150" cy="135" r="35" fill="url(#orangeGlow)" opacity="0.85"/>
            <defs>
                <radialGradient id="orangeGlow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stop-color="#FF9900" stop-opacity="0.95"/>
                    <stop offset="60%" stop-color="#FF5500" stop-opacity="0.4"/>
                    <stop offset="100%" stop-color="#030712" stop-opacity="0"/>
                </radialGradient>
            </defs>
            <g stroke="rgba(0,229,255,0.75)" stroke-width="1.5" fill="none" stroke-linecap="round">
                <path d="M60,250 Q100,210 150,210 Q200,210 240,250" opacity="0.9"/>
                <path d="M80,265 Q150,230 220,265" stroke="rgba(255,153,0,0.85)" stroke-width="1"/>
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

    <!-- COMMAND DOCK (ELEGANT BUTTONS) -->
    <div class="command-dock">
        <button class="cmd-btn" onclick="quickCmd('Gib mir mein Morning Briefing mit Terminen heute.')">☀️ Morning Brief</button>
        <button class="cmd-btn" onclick="openHolo('calendar')">📅 Kalender</button>
        <button class="cmd-btn" onclick="openHolo('calc')">📐 Rechner</button>
        <button class="cmd-btn" onclick="openHolo('codes')">🔐 Objekt-Codes</button>
        <button class="cmd-btn" onclick="document.getElementById('cam').click()">📸 Mängel-Foto</button>
        <button class="cmd-btn" onclick="sendTg()">✈️ Telegram Auth</button>
    </div>

    <!-- BOTTOM WAKE & MIC -->
    <div class="bottom-bar">
        <p class="wake-text" id="wakePrompt">Sage: „Hey Neo“</p>
        <div class="mic-btn" onclick="toggleListening()">🎙️</div>
    </div>

    <!-- HOLOGRAPHIC MODAL -->
    <div class="holo-modal" id="holoModal">
        <div class="holo-box">
            <div class="holo-head">
                <span id="holoTitle">DATEN</span>
                <button class="cmd-btn" style="padding: 2px 8px;" onclick="closeHolo()">✕</button>
            </div>
            <div class="holo-content" id="holoBody"></div>
        </div>
    </div>

    <input type="file" id="cam" accept="image/*" style="display:none" onchange="handleImg(event)">
    <audio id="player" playsinline></audio>

    <script>
        let isRec = false, isSpk = false, inConv = false;
        let rec = null, stream = null, wakeRec = null;
        let cachedEvents = [];
        const player = document.getElementById('player');
        const wakePrompt = document.getElementById('wakePrompt');

        fetch('/calendar_preview').then(r => r.json()).then(d => { cachedEvents = d.events || []; }).catch(()=>{});
        let mem = JSON.parse(localStorage.getItem('neo_memory') || '[]');

        function setVisualState(state) {
            document.body.className = state || '';
            if (state === 'listening') wakePrompt.innerText = "Ich höre zu...";
            else if (state === 'thinking') wakePrompt.innerText = "Analysiere...";
            else if (state === 'speaking') wakePrompt.innerText = "NEO spricht...";
            else wakePrompt.innerText = "Sage: „Hey Neo“";
        }

        function openHolo(type) {
            const modal = document.getElementById('holoModal');
            const title = document.getElementById('holoTitle');
            const body = document.getElementById('holoBody');
            modal.classList.add('open');

            if (type === 'calendar') {
                title.innerText = 'KALENDER TERMINE';
                body.innerHTML = cachedEvents.length
                    ? cachedEvents.map(e => `<div class="holo-row"><div style="color:var(--orange);font-size:11px;">${e.time}</div><div style="font-weight:700;">${e.title}</div><div style="color:var(--muted);font-size:11px;">${e.loc||''}</div></div>`).join('')
                    : '<div style="color:var(--muted);">Keine Termine gefunden.</div>';
            } else if (type === 'codes') {
                title.innerText = `OBJEKT-CODES & NOTIZEN (${mem.length})`;
                let list = mem.length ? mem.map((x, i) => `<div class="holo-row" style="display:flex;justify-content:space-between;align-items:center;"><span>${x}</span><button class="gold-pill" style="padding:2px 8px;" onclick="mem.splice(${i},1);localStorage.setItem('neo_memory',JSON.stringify(mem));openHolo('codes');">✕</button></div>`).join('') : '<div style="color:var(--muted);">Keine Codes gespeichert.</div>';
                body.innerHTML = `<div style="display:flex;gap:6px;margin-bottom:8px;"><input id="newCode" type="text" placeholder="Neuer Code..." style="flex:1;"><button class="gold-pill" onclick="if(document.getElementById('newCode').value.trim()){mem.push(document.getElementById('newCode').value.trim());localStorage.setItem('neo_memory',JSON.stringify(mem));openHolo('codes');}">Speichern</button></div>` + list;
            } else if (type === 'calc') {
                title.innerText = 'ANGEBOTS-KALKULATOR (31,50 €/Std)';
                body.innerHTML = `<div style="display:flex;flex-direction:column;gap:10px;">
                    <input id="cQm" type="number" placeholder="Fläche in m² (z.B. 600)" value="600">
                    <select id="cFreq">
                        <option value="1x pro Woche">1x pro Woche</option>
                        <option value="2x pro Woche" selected>2x pro Woche</option>
                        <option value="3x pro Woche">3x pro Woche</option>
                        <option value="5x pro Woche">5x pro Woche</option>
                    </select>
                    <button class="gold-pill" onclick="closeHolo();quickCmd('Kalkuliere ein Reinigungsangebot für '+document.getElementById('cQm').value+' m², '+document.getElementById('cFreq').value+', und erstelle den Angebotstext.');">ANGEBOT ERSTELLEN</button>
                </div>`;
            }
        }
        function closeHolo() { document.getElementById('holoModal').classList.remove('open'); }

        async function sendTg() {
            wakePrompt.innerText = "Sende Telegram...";
            try {
                const r = await fetch('/telegram_notify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:"📞 NEO Autorisierung angefordert!"}) });
                const d = await r.json();
                wakePrompt.innerText = d.ok ? "Telegram gesendet!" : "Telegram Fehler";
                setTimeout(() => wakePrompt.innerText = "Sage: „Hey Neo“", 3000);
            } catch(e) { wakePrompt.innerText = "Verbindungsfehler"; }
        }

        function handleImg(ev) {
            const f = ev.target.files[0]; if(!f) return;
            setVisualState('thinking');
            const r = new FileReader();
            r.onload = e => sendToNeoBackend({ image: e.target.result.split(',')[1], message: "Erstelle einen professionellen Objekt-Mängelbericht." });
            r.readAsDataURL(f);
        }

        function startWakeWord() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) return;
            try {
                wakeRec = new SpeechRecognition();
                wakeRec.lang = 'de-DE'; wakeRec.continuous = true; wakeRec.interimResults = true;
                wakeRec.onresult = (e) => {
                    for (let i = e.resultIndex; i < e.results.length; i++) {
                        const t = e.results[i][0].transcript.toLowerCase();
                        if (t.includes('hey neo') || t.includes('hallo neo') || t.includes('neo')) {
                            if (wakeRec) { try { wakeRec.abort(); } catch(err){} }
                            inConv = true; startRecordingAudio(); return;
                        }
                    }
                };
                wakeRec.onend = () => { if (!isRec && !isSpk && !inConv) setTimeout(startWakeWord, 800); };
                wakeRec.start();
            } catch(e) {}
        }

        function toggleListening() {
            if (isSpk) { player.pause(); isSpk = false; setVisualState(null); return; }
            if (isRec) { isRec = false; if (rec && rec.state !== 'inactive') rec.stop(); return; }
            inConv = true; startRecordingAudio();
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
                rec.start(); isRec = true; setVisualState('listening');
                setTimeout(() => { if (isRec) { isRec = false; rec.stop(); } }, 6000);
            } catch(e) { inConv = false; setVisualState(null); startWakeWord(); }
        }

        player.onplay = () => { isSpk = true; setVisualState('speaking'); };
        player.onended = () => { isSpk = false; setVisualState(null); if (inConv) setTimeout(startRecordingAudio, 400); else startWakeWord(); };

        function quickCmd(t) { inConv = true; setVisualState('thinking'); sendToNeoBackend({ message: t }); }

        async function sendToNeoBackend(payload) {
            payload.mode = "ARBEIT"; payload.memory = mem; payload.local_time_str = new Date().toLocaleString('de-DE');
            try {
                const res = await fetch('/chat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                const d = await res.json();
                if (d.error) { inConv = false; setVisualState(null); startWakeWord(); return; }
                if (d.end_conversation) inConv = false;
                if (d.new_memory) { mem.push(d.new_memory); localStorage.setItem('neo_memory', JSON.stringify(mem)); }
                if (d.audio) {
                    player.src = "data:audio/mp3;base64," + d.audio;
                    player.play().catch(() => { isSpk = false; setVisualState(null); startWakeWord(); });
                } else { setVisualState(null); startWakeWord(); }
            } catch(e) { inConv = false; setVisualState(null); startWakeWord(); }
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

@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.json or {}
        if "callback_query" in data:
            cq = data["callback_query"]
            callback_data = cq.get("data")
            callback_id = cq["id"]
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
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
