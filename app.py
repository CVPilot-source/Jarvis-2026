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

MANIFEST_JSON = {
    "name": "NEO",
    "short_name": "NEO",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#060913",
    "theme_color": "#060913",
    "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]
}

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="120" fill="#060913"/>
  <circle cx="256" cy="256" r="150" fill="none" stroke="#38BDF8" stroke-width="12"/>
  <circle cx="256" cy="256" r="28" fill="#38BDF8"/>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#060913">
    <link rel="manifest" href="/manifest.json">
    <title>NEO</title>
    <style>
        :root {
            --accent: #38BDF8;
            --bg: #060913;
            --card: #111827;
            --border: rgba(255,255,255,0.1);
            --text: #F8FAFC;
            --muted: #94A3B8;
        }
        body.listening { --accent: #10B981; }
        body.thinking  { --accent: #F59E0B; }
        body.speaking  { --accent: #A855F7; }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; touch-action: manipulation; }

        body {
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            height: 100dvh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 12px 14px;
            max-width: 520px;
            margin-left: auto;
            margin-right: auto;
            gap: 10px;
        }

        .top { display: flex; justify-content: space-between; align-items: center; }
        .chip {
            background: var(--card); border: 1px solid var(--border); color: var(--text);
            padding: 6px 12px; border-radius: 999px; font-size: 12px; font-weight: 700;
            display: flex; align-items: center; gap: 6px; cursor: pointer;
        }
        .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }

        .hero {
            background: var(--card); border: 1px solid var(--border); border-radius: 18px;
            padding: 12px; display: flex; align-items: center; gap: 12px;
        }
        .avatar {
            width: 68px; height: 76px; border-radius: 14px; overflow: hidden;
            border: 2px solid var(--accent); flex-shrink: 0; cursor: pointer;
        }
        .avatar img { width: 100%; height: 114%; object-fit: cover; object-position: center 12%; display: block; }
        .title { font-size: 18px; font-weight: 800; }
        .tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
        .tag {
            background: rgba(56,189,248,0.12); color: var(--accent); border-radius: 6px;
            padding: 3px 8px; font-size: 11px; font-weight: 700;
        }

        .cal-box {
            background: var(--card); border: 1px solid var(--border); border-left: 3px solid var(--accent);
            border-radius: 14px; padding: 10px 12px; cursor: pointer;
        }
        .cal-lbl { font-size: 10px; font-weight: 800; color: var(--accent); text-transform: uppercase; }
        .cal-val { font-size: 13.5px; font-weight: 700; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; flex: 1; }
        .tile {
            background: var(--card); border: 1px solid var(--border); border-radius: 16px;
            padding: 12px; display: flex; flex-direction: column; justify-content: center;
            cursor: pointer;
        }
        .tile:active { border-color: var(--accent); }
        .tile-t { font-size: 14px; font-weight: 700; }
        .tile-s { font-size: 11px; color: var(--muted); margin-top: 2px; }

        .action-bar { display: flex; gap: 8px; justify-content: center; min-height: 30px; }
        .pill {
            background: var(--accent); color: #060913; border: none; border-radius: 999px;
            padding: 6px 14px; font-size: 12px; font-weight: 800; text-decoration: none; cursor: pointer;
        }

        .dock {
            background: var(--card); border: 1px solid var(--border); border-radius: 18px;
            padding: 10px; display: flex; flex-direction: column; gap: 8px;
        }
        .dock-top { display: flex; align-items: center; gap: 10px; }
        .mic {
            width: 50px; height: 50px; border-radius: 50%; background: #0B1324;
            border: 2px solid var(--accent); color: #FFF; font-size: 20px;
            display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0;
        }
        .status-txt { flex: 1; font-size: 13px; font-weight: 700; color: var(--accent); cursor: pointer; }
        .input-row { display: flex; gap: 6px; }
        .input-row input {
            flex: 1; background: #060913; border: 1px solid var(--border); border-radius: 10px;
            color: #FFF; padding: 9px 10px; font-size: 13.5px; outline: none;
        }
        .input-row button {
            background: var(--accent); color: #060913; border: none; border-radius: 10px;
            padding: 0 14px; font-weight: 800; font-size: 12.5px; cursor: pointer;
        }

        .modal {
            position: fixed; inset: 0; background: #060913; z-index: 40;
            display: none; flex-direction: column; padding: 16px;
        }
        .modal.open { display: flex; }
        .row {
            display: flex; justify-content: space-between; align-items: center;
            background: var(--card); padding: 10px 12px; border-radius: 10px; margin-bottom: 8px; font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="top">
        <button type="button" class="chip" onclick="toggleWake()"><span class="dot"></span><span id="wLabel">Voice Aktiv</span></button>
        <span style="font-weight:800; letter-spacing:2px; font-size:12px; color:var(--accent);">NEO</span>
        <button type="button" class="chip" id="mBtn" onclick="toggleMode()">Arbeit</button>
    </div>

    <div class="hero">
        <div class="avatar" onclick="toggleRec()"><img src="/avatar" alt="NEO" onerror="this.src='/icon.svg'"></div>
        <div>
            <div class="title">Hallo, Margil</div>
            <div class="tags">
                <span class="tag" id="clock">--:--</span>
                <span class="tag" id="weather">Hamburg</span>
                <span class="tag" onclick="openList()" style="cursor:pointer;">Notizen: <span id="nCount">0</span></span>
            </div>
        </div>
    </div>

    <div class="cal-box" onclick="quickCmd('Erkläre mir kurz meine nächsten Termine im Kalender.')">
        <div class="cal-lbl">Nächster Termin</div>
        <div class="cal-val" id="nextEv">Wird geladen...</div>
    </div>

    <div class="grid">
        <div class="tile" onclick="quickCmd('Ich fahre los zum nächsten Termin. Gib mir das Briefing mit Codes und starte Navigation.')">
            <div class="tile-t">Auto-Briefing</div>
            <div class="tile-s">Codes & Route</div>
        </div>
        <div class="tile" onclick="quickCmd('Kalkuliere 600 qm Büro, 2x pro Woche, mit WhatsApp-Angebot.')">
            <div class="tile-t">Angebot Rechner</div>
            <div class="tile-s">m² & Preis</div>
        </div>
        <div class="tile" onclick="document.getElementById('cam').click()">
            <div class="tile-t">Mängel-Foto</div>
            <div class="tile-s">Kamera Bericht</div>
        </div>
        <div class="tile" onclick="sendTg()">
            <div class="tile-t">Telegram Alert</div>
            <div class="tile-s">Autorisierung</div>
        </div>
    </div>

    <div class="action-bar" id="actBar"></div>

    <div class="dock">
        <div class="dock-top">
            <button type="button" class="mic" onclick="toggleRec()">🎙️</button>
            <div class="status-txt" id="stTxt" onclick="toggleRec()">Tippen oder „Hey Neo“ sagen</div>
            <button type="button" class="chip" onclick="openList()">Listen</button>
        </div>
        <div class="input-row">
            <input type="text" id="msg" placeholder="Befehl oder Übersetzung..." onkeypress="if(event.key==='Enter')sendTxt()">
            <button type="button" onclick="sendTxt()">Senden</button>
        </div>
    </div>

    <input type="file" id="cam" accept="image/*" capture="environment" style="display:none" onchange="handleImg(event)">

    <div class="modal" id="modal">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <b>Notizen & Codes</b>
            <button type="button" class="chip" onclick="closeList()">✕ Schließen</button>
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
                if (d.current_weather) document.getElementById('weather').innerText = "Hamburg " + Math.round(d.current_weather.temperature) + "°C";
            }).catch(()=>{});

        fetch('/calendar_preview').then(r => r.json()).then(d => {
            document.getElementById('nextEv').innerText = (d.events && d.events.length) ? (d.events[0].time + " – " + d.events[0].title) : "Keine Termine";
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
            stTxt.innerText = s === 'listening' ? 'Hört zu...' : (s === 'thinking' ? 'Antwort kommt...' : (s === 'speaking' ? 'NEO spricht...' : 'Tippen oder „Hey Neo“ sagen'));
        }

        function stopWake() { if (wakeRec) { try { wakeRec.onend = null; wakeRec.abort(); } catch(e){} wakeRec = null; } }
        function toggleWake() {
            wakeOn = !wakeOn;
            document.getElementById('wLabel').innerText = wakeOn ? 'Voice Aktiv' : 'Stumm';
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
            wakeRec.onend = () => { wakeRec = null; if (wakeOn && !isRec && !isSpk && !inConv) setTimeout(startWake, 500); };
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
            document.getElementById('listBody').innerHTML = mem.length ? mem.map((x,i) => `<div class="row"><span>${x}</span><button class="pill" onclick="mem.splice(${i},1);saveState();openList();">✓</button></div>`).join('') : '<p style="color:#94A3B8">Keine Notizen.</p>';
        }
        function closeList() { document.getElementById('modal').classList.remove('open'); }

        async function sendTg() {
            stTxt.innerText = "Sende Telegram...";
            const r = await fetch('/telegram_notify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:"📞 NEO Autorisierung angefordert!"}) });
            const d = await r.json();
            stTxt.innerText = d.ok ? "Telegram gesendet!" : (d.error || "Fehler");
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
                if (d.error) { inConv = false; setSt(null); stTxt.innerText = d.error; return; }
                if (d.end_conversation) inConv = false;
                if (d.new_memory) { mem.push(d.new_memory); saveState(); }
                if (d.copy_text) {
                    const b = document.createElement('button'); b.className = 'pill'; b.innerText = 'Text kopieren';
                    b.onclick = () => { navigator.clipboard.writeText(d.copy_text); b.innerText = '✓ Kopiert'; };
                    document.getElementById('actBar').appendChild(b);
                }
                if (d.action_url) {
                    inConv = false;
                    const a = document.createElement('a'); a.href = d.action_url; a.className = 'pill'; a.innerText = d.action_label || 'Öffnen';
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

SYSTEM_PROMPT = """Du bist NEO, der schnelle KI-Assistent von Margil (Kundenbetreuer Gebäudereinigung Hamburg).
Modus: {mode} | Zeit: {local_time}. Antworte kurz, höflich, ohne Markdown/Sternchen.
- Auto-Briefing ("Ich fahre los"): Nächster Termin + Codes aus Notizen + Google Maps URL in `action_url`.
- Dolmetscher DE <-> SQ: Bei Übersetzung ins Albanische `voice_lang`: "sq", sonst "de".
- Kalkulator: Büro ~220 m²/Std, 31,50 €/Std netto. Fertiger Text in `copy_text` + WhatsApp Intent (`intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp.w4b;end`).
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
    return jsonify(MANIFEST_JSON)

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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
