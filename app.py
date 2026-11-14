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
  <rect width="512" height="512" rx="120" fill="#09090B"/>
  <circle cx="256" cy="256" r="155" fill="none" stroke="#F59E0B" stroke-width="10"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#22D3EE" stroke-width="5" stroke-dasharray="20 12"/>
  <circle cx="256" cy="256" r="24" fill="#F59E0B"/>
</svg>"""

HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#09090B">
    <link rel="manifest" href="/manifest.json">
    <title>NEO Executive</title>
    <style>
        :root {
            --gold: #F59E0B;
            --cyan: #22D3EE;
            --active: #F59E0B;
            --bg: #09090B;
            --surface: #141417;
            --surface-2: #1E1E24;
            --border: rgba(255, 255, 255, 0.08);
            --text: #FAFAFA;
            --muted: #A1A1AA;
        }
        body.listening { --active: #10B981; }
        body.thinking  { --active: #22D3EE; }
        body.speaking  { --active: #A855F7; }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        body {
            margin: 0 auto;
            max-width: 500px;
            height: 100dvh;
            background: radial-gradient(circle at 50% 18%, #1C1917 0%, #09090B 62%);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 12px 14px;
            gap: 9px;
        }

        /* HEADER */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .pill-tag {
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 11.5px;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--active);
            box-shadow: 0 0 8px var(--active);
        }
        .brand {
            font-size: 13px;
            font-weight: 900;
            letter-spacing: 4px;
            color: var(--gold);
        }

        /* CENTER ORB / AVATAR */
        .core-stage {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 4px 0;
        }
        .orb-wrap {
            width: 112px;
            height: 112px;
            border-radius: 50%;
            padding: 3px;
            background: linear-gradient(135deg, var(--active), var(--cyan));
            box-shadow: 0 0 26px rgba(245, 158, 11, 0.25);
            cursor: pointer;
            transition: transform 0.15s;
        }
        .orb-wrap:active { transform: scale(0.95); }
        .orb-img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            overflow: hidden;
            background: #09090B;
        }
        .orb-img img {
            width: 100%;
            height: 114%;
            object-fit: cover;
            object-position: center 12%;
            display: block;
        }
        .core-title {
            font-size: 16px;
            font-weight: 800;
            margin-top: 8px;
        }
        .core-sub {
            font-size: 12px;
            font-weight: 600;
            color: var(--active);
            margin-top: 2px;
        }
        .meta-strip {
            display: flex;
            gap: 6px;
            margin-top: 6px;
        }
        .meta-chip {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 7px;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 600;
            color: var(--muted);
            cursor: pointer;
        }

        /* CARDS */
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 10px 12px;
        }
        .card-head {
            font-size: 10px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--gold);
            margin-bottom: 3px;
        }
        .card-body {
            font-size: 13px;
            line-height: 1.4;
            color: #F4F4F5;
        }

        /* 4 COMPACT BUTTONS */
        .tools-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 7px;
        }
        .tool-btn {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 13px;
            padding: 10px 4px;
            text-align: center;
            cursor: pointer;
        }
        .tool-btn:active { border-color: var(--gold); background: var(--surface-2); }
        .tool-ico { font-size: 17px; display: block; margin-bottom: 3px; }
        .tool-lbl { font-size: 10.5px; font-weight: 700; color: var(--text); }

        /* ACTION BAR */
        .act-bar {
            display: flex;
            gap: 8px;
            justify-content: center;
            min-height: 28px;
        }
        .gold-pill {
            background: var(--gold);
            color: #09090B;
            border: none;
            border-radius: 999px;
            padding: 6px 15px;
            font-size: 12px;
            font-weight: 800;
            text-decoration: none;
            cursor: pointer;
        }

        /* BOTTOM CONSOLE */
        .console {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 8px;
            display: flex;
            gap: 7px;
            align-items: center;
        }
        .mic-btn {
            width: 42px;
            height: 42px;
            border-radius: 12px;
            background: var(--surface-2);
            border: 1px solid var(--active);
            color: #FFF;
            font-size: 18px;
            cursor: pointer;
            flex-shrink: 0;
        }
        .console input {
            flex: 1;
            background: #09090B;
            border: 1px solid var(--border);
            border-radius: 10px;
            color: #FFF;
            padding: 9px 10px;
            font-size: 13.5px;
            outline: none;
        }
        .send-btn {
            background: var(--gold);
            color: #09090B;
            border: none;
            border-radius: 10px;
            padding: 9px 13px;
            font-size: 12px;
            font-weight: 800;
            cursor: pointer;
        }

        /* NOTES MODAL */
        .modal {
            position: fixed;
            inset: 0;
            background: #09090B;
            z-index: 50;
            display: none;
            flex-direction: column;
            padding: 16px;
        }
        .modal.open { display: flex; }
        .note-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--surface);
            border: 1px solid var(--border);
            padding: 10px 12px;
            border-radius: 10px;
            margin-bottom: 8px;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="header">
        <button type="button" class="pill-tag" onclick="toggleWake()">
            <span class="indicator"></span>
            <span id="wBtn">Voice AN</span>
        </button>
        <div class="brand">NEO</div>
        <button type="button" class="pill-tag" id="mBtn" onclick="toggleMode()">Arbeit</button>
    </div>

    <div class="core-stage">
        <div class="orb-wrap" onclick="toggleRec()">
            <div class="orb-img"><img src="/avatar" alt="NEO" onerror="this.src='/icon.svg'"></div>
        </div>
        <div class="core-title">Hallo, Margil</div>
        <div class="core-sub" id="stTxt" onclick="toggleRec()">Tippen oder „Hey Neo“ sagen</div>
        <div class="meta-strip">
            <span class="meta-chip" id="clock">--:--</span>
            <span class="meta-chip" id="weather">Hamburg</span>
            <span class="meta-chip" onclick="openList()">Codes: <span id="nCount">0</span></span>
        </div>
    </div>

    <div class="card" onclick="quickCmd('Erkläre mir kurz meine nächsten Termine im Kalender.')" style="cursor:pointer;">
        <div class="card-head">Nächster Termin • Kalender</div>
        <div class="card-body" id="nextEv" style="font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Wird synchronisiert...</div>
    </div>

    <div class="card" style="flex:1; display:flex; flex-direction:column; justify-content:center;">
        <div class="card-head">NEO Antwort</div>
        <div class="card-body" id="replyBox">System bereit, Margil.</div>
    </div>

    <div class="tools-row">
        <div class="tool-btn" onclick="quickCmd('Ich fahre los zum nächsten Termin. Gib mir das Briefing mit Codes und starte Navigation.')">
            <span class="tool-ico">🧭</span>
            <span class="tool-lbl">Briefing</span>
        </div>
        <div class="tool-btn" onclick="quickCmd('Kalkuliere 600 qm Büro, 2x pro Woche, mit WhatsApp-Angebot.')">
            <span class="tool-ico">📐</span>
            <span class="tool-lbl">Angebot</span>
        </div>
        <div class="tool-btn" onclick="document.getElementById('cam').click()">
            <span class="tool-ico">📸</span>
            <span class="tool-lbl">Mängel</span>
        </div>
        <div class="tool-btn" onclick="sendTg()">
            <span class="tool-ico">✈️</span>
            <span class="tool-lbl">Telegram</span>
        </div>
    </div>

    <div class="act-bar" id="actBar"></div>

    <div class="console">
        <button type="button" class="mic-btn" onclick="toggleRec()">🎙️</button>
        <input type="text" id="msg" placeholder="Befehl oder Übersetzung..." onkeypress="if(event.key==='Enter')sendTxt()">
        <button type="button" class="send-btn" onclick="sendTxt()">Go</button>
    </div>

    <input type="file" id="cam" accept="image/*" capture="environment" style="display:none" onchange="handleImg(event)">

    <div class="modal" id="modal">
        <div class="header" style="margin-bottom:12px;">
            <strong style="color:var(--gold);">Objekt-Codes & Notizen</strong>
            <button type="button" class="pill-tag" onclick="closeList()">✕ Schließen</button>
        </div>
        <div id="listBody" style="flex:1; overflow-y:auto;"></div>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        function updClock() {
            document.getElementById('clock').innerText = new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'}) + " Uhr";
        }
        updClock(); setInterval(updClock, 15000);

        fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true')
            .then(r => r.json()).then(d => {
                if (d.current_weather) document.getElementById('weather').innerText = "HH " + Math.round(d.current_weather.temperature) + "°C";
            }).catch(()=>{});

        fetch('/calendar_preview').then(r => r.json()).then(d => {
            document.getElementById('nextEv').innerText = (d.events && d.events.length) ? (d.events[0].time + " – " + d.events[0].title) : "Keine Termine eingetragen";
        }).catch(()=>{});

        let mem = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        let mode = localStorage.getItem('neo_mode') || 'ARBEIT';
        let wakeOn = true, isRec = false, isSpk = false, inConv = false;
        let rec = null, stream = null, chunks = [], wakeRec = null;
        const player = document.getElementById('player');
        const stTxt = document.getElementById('stTxt');

        function saveState() {
            localStorage.setItem('neo_memory', JSON.stringify(mem));
            localStorage.setItem('neo_mode', mode);
            document.getElementById('nCount').innerText = mem.length;
            document.getElementById('mBtn').innerText = mode === 'ARBEIT' ? 'Arbeit' : 'Privat';
        }
        saveState();

        function toggleMode() { mode = mode === 'ARBEIT' ? 'PRIVAT' : 'ARBEIT'; saveState(); }
        function setSt(s) {
            document.body.className = s || '';
            stTxt.innerText = s === 'listening' ? 'Hört zu, Margil...' : (s === 'thinking' ? 'NEO analysiert...' : (s === 'speaking' ? 'NEO spricht...' : 'Tippen oder „Hey Neo“ sagen'));
        }

        function stopWake() { if (wakeRec) { try { wakeRec.onend = null; wakeRec.abort(); } catch(e){} wakeRec = null; } }
        function toggleWake() {
            wakeOn = !wakeOn;
            document.getElementById('wBtn').innerText = wakeOn ? 'Voice AN' : 'Voice AUS';
            if (wakeOn) startWake(); else stopWake();
        }
        function startWake() {
            if (!wakeOn || isRec || isSpk || inConv) return;
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SR) return;
            stopWake();
            wakeRec = new SR();
            wakeRec.lang = 'de-DE';
            wakeRec.continuous = true;
            wakeRec.onresult = (e) => {
                for (let i = e.resultIndex; i < e.results.length; i++) {
                    const t = e.results[i][0].transcript.toLowerCase();
                    if (t.includes('hey neo') || t.includes('neo')) { stopWake(); inConv = true; startRec(); return; }
                }
            };
            wakeRec.onend = () => { wakeRec = null; if (wakeOn && !isRec && !isSpk && !inConv) setTimeout(startWake, 600); };
            try { wakeRec.start(); } catch(e){}
        }

        function toggleRec() {
            if (isSpk) { player.pause(); isSpk = false; setSt(null); }
            if (isRec) { isRec = false; if (rec && rec.state !== 'inactive') rec.stop(); return; }
            inConv = true; startRec();
        }

        async function startRec() {
            if (isRec || isSpk) return;
            stopWake();
            try {
                stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
                chunks = [];
                rec = new MediaRecorder(stream, { audioBitsPerSecond: 12000 });
                rec.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
                rec.onstop = () => {
                    stream.getTracks().forEach(t => t.stop());
                    const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
                    if (blob.size < 800) { inConv = false; setSt(null); startWake(); return; }
                    setSt('thinking');
                    const r = new FileReader();
                    r.readAsDataURL(blob);
                    r.onloadend = () => sendNeo({ audio: r.result.split(',')[1], mime_type: (rec.mimeType || 'audio/webm').split(';')[0] });
                };
                rec.start();
                isRec = true;
                setSt('listening');
                setTimeout(() => { if (isRec) { isRec = false; rec.stop(); } }, 5000);
            } catch(e) { inConv = false; setSt(null); }
        }

        player.onplay = () => { isSpk = true; setSt('speaking'); };
        player.onended = () => { isSpk = false; setSt(null); if (inConv) setTimeout(startRec, 400); else startWake(); };

        function openList() {
            document.getElementById('modal').classList.add('open');
            document.getElementById('listBody').innerHTML = mem.length ? mem.map((x,i) => `<div class="note-item"><span>${x}</span><button type="button" class="gold-pill" onclick="mem.splice(${i},1);saveState();openList();">✓</button></div>`).join('') : '<p style="color:#A1A1AA">Keine Notizen gespeichert.</p>';
        }
        function closeList() { document.getElementById('modal').classList.remove('open'); }

        async function sendTg() {
            stTxt.innerText = "Sende Telegram...";
            try {
                const r = await fetch('/telegram_notify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:"📞 NEO Autorisierung angefordert!"}) });
                const d = await r.json();
                stTxt.innerText = d.ok ? "Telegram gesendet!" : (d.error || "Fehler");
            } catch(e) { stTxt.innerText = "Telegram Fehler"; }
        }

        function handleImg(ev) {
            const f = ev.target.files[0]; if (!f) return;
            setSt('thinking');
            const r = new FileReader();
            r.onload = e => sendNeo({ image: e.target.result.split(',')[1], message: "Erstelle einen kurzen Objekt-Mängelbericht für WhatsApp." });
            r.readAsDataURL(f);
        }

        function quickCmd(t) { setSt('thinking'); sendNeo({ message: t }); }
        function sendTxt() {
            const inp = document.getElementById('msg');
            if (!inp.value.trim()) return;
            const v = inp.value.trim(); inp.value = '';
            setSt('thinking'); sendNeo({ message: v });
        }

        async function sendNeo(payload) {
            stopWake();
            document.getElementById('actBar').innerHTML = '';
            payload.mode = mode; payload.memory = mem; payload.local_time_str = new Date().toLocaleString('de-DE');
            try {
                const res = await fetch('/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
                const d = await res.json();
                if (d.error) { inConv = false; setSt(null); document.getElementById('replyBox').innerText = d.error; return; }
                if (d.end_conversation) inConv = false;
                if (d.new_memory) { mem.push(d.new_memory); saveState(); }
                document.getElementById('replyBox').innerText = d.reply;
                if (d.copy_text) {
                    const b = document.createElement('button'); b.type = 'button'; b.className = 'gold-pill'; b.innerText = 'Text kopieren';
                    b.onclick = () => { navigator.clipboard.writeText(d.copy_text); b.innerText = '✓ Kopiert'; };
                    document.getElementById('actBar').appendChild(b);
                }
                if (d.action_url) {
                    inConv = false;
                    const a = document.createElement('a'); a.href = d.action_url; a.className = 'gold-pill'; a.innerText = d.action_label || 'Öffnen';
                    document.getElementById('actBar').appendChild(a);
                }
                if (d.audio) {
                    player.src = "data:audio/mp3;base64," + d.audio;
                    player.play().catch(() => { isSpk = false; setSt(null); });
                } else { setSt(null); }
            } catch(e) { inConv = false; setSt(null); }
        }
        window.onload = startWake;
    </script>
</body>
</html>"""

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

SYSTEM_PROMPT = """Du bist NEO, der schnelle KI-Assistent von Margil (Kundenbetreuer Gebäudereinigung Hamburg).
Modus: {mode} | Zeit: {local_time}. Antworte kurz, höflich, ohne Markdown/Sternchen.
- Auto-Briefing ("Ich fahre los"): Nächster Termin + Codes aus Notizen + Google Maps URL in `action_url` (`action_label`: "Navigation starten").
- Dolmetscher DE <-> SQ: Bei Übersetzung ins Albanische `voice_lang`: "sq" und Übersetzung in `copy_text`, sonst "de".
- Kalkulator: Büro ~220 m²/Std, 31,50 €/Std netto (4,33 Wochen/Monat). Fertiges Angebot in `copy_text` + WhatsApp Intent (`intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp.w4b;end`, `action_label`: "WhatsApp öffnen").
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
        "background_color": "#09090B",
        "theme_color": "#09090B",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]
    })

@app.route("/icon.svg")
def icon():
    return Response(ICON_SVG, mimetype="image/svg+xml")

@app.route("/telegram_notify", methods=["POST"])
def tg_notify():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        return jsonify({"ok": False, "error": "Token fehlt"})
    if not chat_id:
        try:
            u = json.loads(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=5).read().decode())
            if u.get("result"):
                chat_id = str(u["result"][-1]["message"]["chat"]["id"])
        except Exception:
            pass
    if not chat_id:
        return jsonify({"ok": False, "error": "Erst 'Hallo' im Bot senden"})
    payload = json.dumps({
        "chat_id": chat_id,
        "text": (request.json or {}).get("text", "🔔 NEO Autorisierung"),
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
        cal_txt = "\n".join([f"- {e['time']}: {e['title']} ({e['loc']})" for e in events]) or "Keine Termine."

        parts = []
        if "image" in data:
            parts.append(types.Part.from_bytes(data=base64.b64decode(data["image"]), mime_type="image/jpeg"))
            parts.append(data.get("message", "Mängelbericht erstellen."))
        elif "audio" in data:
            parts.append(types.Part.from_bytes(data=base64.b64decode(data["audio"]), mime_type=data.get("mime_type", "audio/webm")))
        else:
            parts.append(data.get("message", ""))

        parts.append(f"Kalender:\n{cal_txt}\nNotizen: {json.dumps(data.get('memory', []), ensure_ascii=False)}")

        resp = client.models.generate_content(
            model="gemini-3.8-flash",
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
