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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#030712">
    <link rel="manifest" href="/manifest.json">
    <title>N.E.O. // LIGHTNING FAST CORE</title>
    <style>
        :root {
            --cyan: #00E5FF;
            --orange: #FF9900;
            --bg: #030712;
            --panel: rgba(8, 15, 30, 0.9);
            --border: rgba(0, 229, 255, 0.25);
            --text: #F8FAFC;
            --muted: #94A3B8;
        }
        body.listening { --cyan: #10B981; }
        body.thinking  { --cyan: #00E5FF; }
        body.speaking  { --cyan: #A855F7; }

        * { box-sizing: border-box; user-select: none; -webkit-tap-highlight-color: transparent; }

        html, body {
            margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden;
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Segoe UI', -apple-system, sans-serif;
        }

        #neuralCanvas {
            position: fixed; inset: 0; width: 100vw; height: 100vh;
            z-index: 1; pointer-events: none;
        }

        /* TOP LEFT HUD */
        .hud-tl {
            position: fixed; top: 16px; left: 20px; z-index: 10;
            display: flex; flex-direction: column; gap: 4px;
        }
        .sys-title {
            font-size: 24px; font-weight: 900; letter-spacing: 6px; color: var(--cyan);
            text-shadow: 0 0 10px rgba(0,229,255,0.4);
        }
        .sys-sub { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: var(--muted); }
        .hud-controls { display: flex; gap: 6px; margin-top: 4px; flex-wrap: wrap; }
        .hud-btn {
            background: var(--panel); border: 1px solid var(--border); color: var(--text);
            padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 700;
            cursor: pointer; transition: 0.1s;
        }
        .hud-btn:hover { border-color: var(--cyan); color: var(--cyan); }

        /* TOP RIGHT STREAM PANEL */
        .hud-tr {
            position: fixed; top: 16px; right: 20px; width: 360px; max-width: 42vw;
            background: var(--panel); border: 1px solid var(--border); border-top: 2px solid var(--orange);
            border-radius: 10px; padding: 10px 14px; z-index: 10;
        }
        .tr-head {
            display: flex; justify-content: space-between; font-size: 10px;
            font-weight: 800; letter-spacing: 1px; color: var(--orange); margin-bottom: 4px;
        }
        .tr-body {
            font-size: 13px; line-height: 1.4; color: #F1F5F9;
            max-height: 120px; overflow-y: auto; user-select: text;
        }

        /* CENTER STAGE */
        .core-trigger {
            position: fixed; top: 48%; left: 50%; transform: translate(-50%, -50%);
            width: 300px; height: 320px; border-radius: 50%; z-index: 8;
            cursor: pointer; display: flex; flex-direction: column;
            align-items: center; justify-content: flex-end; text-align: center;
            padding-bottom: 5px;
        }
        .core-sub {
            font-size: 11px; font-weight: 800; letter-spacing: 2px;
            color: #FFF; background: rgba(3, 7, 18, 0.9); padding: 4px 14px; border-radius: 99px;
            border: 1px solid var(--border);
        }

        /* NODES */
        .node-item {
            position: fixed; transform: translate(-50%, -50%); z-index: 7;
            display: flex; align-items: center; gap: 8px;
            background: var(--panel); border: 1px solid var(--border);
            padding: 6px 12px; border-radius: 999px; cursor: pointer;
            white-space: nowrap; transition: transform 0.1s;
        }
        .node-item:hover { border-color: var(--cyan); transform: translate(-50%, -50%) scale(1.05); }
        .node-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--orange); }
        .node-title { font-size: 12px; font-weight: 700; color: #F8FAFC; }

        /* POPUP WINDOW */
        .holo-modal {
            position: fixed; top: 48%; left: 50%; transform: translate(-50%, -50%);
            width: 460px; max-width: 90vw; background: rgba(7, 13, 27, 0.98);
            border: 1px solid var(--cyan); border-radius: 12px; padding: 16px; z-index: 30;
            display: none; flex-direction: column; gap: 10px;
        }
        .holo-modal.open { display: flex; }
        .holo-head {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--border); padding-bottom: 6px;
            font-size: 12px; font-weight: 800; color: var(--cyan);
        }
        .holo-content { max-height: 260px; overflow-y: auto; font-size: 13px; }
        .holo-row {
            display: flex; justify-content: space-between; align-items: center;
            padding: 6px 10px; background: rgba(0, 229, 255, 0.05);
            border-left: 3px solid var(--orange); border-radius: 6px; margin-bottom: 6px;
        }

        .gold-pill {
            background: var(--orange); color: #030712; border: none; border-radius: 999px;
            padding: 6px 16px; font-size: 11px; font-weight: 800; cursor: pointer;
        }

        @media (max-width: 768px) {
            .hud-tr { top: auto; bottom: 16px; right: 10px; left: 10px; width: auto; max-width: none; }
            .node-item { padding: 5px 9px; }
            .node-title { font-size: 10.5px; }
        }
    </style>
</head>
<body>
    <canvas id="neuralCanvas"></canvas>

    <!-- TOP LEFT -->
    <div class="hud-tl">
        <div class="sys-title">N E O</div>
        <div class="sys-sub" id="sysMeta">HAMBURG • FAST OS</div>
        <div class="hud-controls">
            <button type="button" class="hud-btn" id="wBtn" onclick="toggleWake()" style="border-color:#10B981; color:#10B981;">● HEY NEO</button>
            <button type="button" class="hud-btn" id="mBtn" onclick="toggleMode()">ARBEIT</button>
            <button type="button" class="hud-btn" onclick="openHolo('calendar')">KALENDER</button>
            <button type="button" class="hud-btn" onclick="openHolo('codes')">CODES (<span id="nCount">0</span>)</button>
        </div>
    </div>

    <!-- TOP RIGHT OUTPUT -->
    <div class="hud-tr">
        <div class="tr-head">
            <span>VOICE STREAM</span>
            <span id="streamStatus">BEREIT</span>
        </div>
        <div class="tr-body" id="replyBox">Sage „Hey Neo“ oder tippe auf das Core in der Mitte.</div>
    </div>

    <!-- CENTER STAGE -->
    <div class="core-trigger" onclick="manualListenTrigger()">
        <div class="core-sub" id="coreState">SAY "HEY NEO"</div>
    </div>

    <!-- NODES -->
    <div id="nodesLayer"></div>

    <!-- HOLOGRAPHIC MODAL -->
    <div class="holo-modal" id="holoModal">
        <div class="holo-head">
            <span id="holoTitle">DATEN</span>
            <button type="button" class="hud-btn" onclick="closeHolo()">✕</button>
        </div>
        <div class="holo-content" id="holoBody"></div>
    </div>

    <input type="file" id="cam" accept="image/*" style="display:none" onchange="handleImg(event)">
    <audio id="player" playsinline></audio>

    <script>
        const isMobile = /Android|iPhone|iPad/i.test(navigator.userAgent);

        function beep(f1, f2) {
            try {
                const ac = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ac.createOscillator();
                const g = ac.createGain();
                osc.connect(g); g.connect(ac.destination);
                osc.frequency.setValueAtTime(f1, ac.currentTime);
                osc.frequency.exponentialRampToValueAtTime(f2, ac.currentTime + 0.1);
                g.gain.setValueAtTime(0.1, ac.currentTime);
                g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.1);
                osc.start(); osc.stop(ac.currentTime + 0.1);
            } catch(e){}
        }

        // --- 1. NODES ---
        const NODES = [
            { id: 'brief',    label: '☀️ Morning Brief',   rx: 0.21, ry: 0.24, action: () => quickCmd('Gib mir mein komplettes Morning Briefing mit Terminen heute und wichtigen Objekt-Codes.') },
            { id: 'calendar', label: '📅 Kalender Sync',   rx: 0.14, ry: 0.43, action: () => openHolo('calendar') },
            { id: 'navi',     label: '🧭 Auto-Briefing',   rx: 0.20, ry: 0.63, action: () => quickCmd('Ich fahre los zum nächsten Termin. Gib mir das Briefing mit Codes und starte Navigation.') },
            { id: 'codes',    label: '🔐 Objekt-Codes',    rx: 0.31, ry: 0.75, action: () => openHolo('codes') },
            { id: 'offer',    label: '📐 Angebot Rechner', rx: 0.79, ry: 0.24, action: () => openHolo('calc') },
            { id: 'camera',   label: '📸 Mängel-Foto',     rx: 0.86, ry: 0.43, action: () => document.getElementById('cam').click() },
            { id: 'telegram', label: '✈️ Autorisierung',   rx: 0.69, ry: 0.75, action: () => sendTg() }
        ];

        const nodesLayer = document.getElementById('nodesLayer');
        NODES.forEach(n => {
            const el = document.createElement('div');
            el.className = 'node-item';
            el.style.left = (n.rx * 100) + '%';
            el.style.top = (n.ry * 100) + '%';
            el.innerHTML = `<span class="node-dot"></span><span class="node-title">${n.label}</span>`;
            el.onclick = () => n.action();
            nodesLayer.appendChild(el);
        });

        // --- 2. OPTIMIZED ULTRA-FAST CANVAS ENGINE ---
        const canvas = document.getElementById('neuralCanvas');
        const ctx = canvas.getContext('2d', { alpha: false });
        let W = window.innerWidth, H = window.innerHeight;
        function resizeCanvas() { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; }
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        let coreStateMode = 'idle', angle = 0;

        function drawFastCore() {
            ctx.fillStyle = '#030712';
            ctx.fillRect(0, 0, W, H);

            const cx = W * 0.5, cy = H * 0.48;
            angle += 0.04;

            // Simple, lightning-fast vector rings
            ctx.strokeStyle = 'rgba(0, 229, 255, 0.7)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(cx, cy, 80, 0, Math.PI * 2);
            ctx.stroke();

            ctx.strokeStyle = 'rgba(255, 153, 0, 0.8)';
            ctx.lineWidth = 2;
            ctx.save();
            ctx.translate(cx, cy);
            ctx.rotate(angle);
            ctx.beginPath();
            ctx.arc(0, 0, 65, 0, Math.PI * 1.5);
            ctx.stroke();
            ctx.restore();

            // Center core
            ctx.fillStyle = coreStateMode === 'listening' ? '#10B981' : (coreStateMode === 'speaking' ? '#A855F7' : '#FF9900');
            ctx.beginPath();
            ctx.arc(cx, cy, 22, 0, Math.PI * 2);
            ctx.fill();

            requestAnimationFrame(drawFastCore);
        }
        drawFastCore();

        // --- 3. STATE & POPUPS ---
        let cachedEvents = [];
        fetch('/calendar_preview').then(r => r.json()).then(d => { cachedEvents = d.events || []; }).catch(()=>{});

        let mem = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        let mode = localStorage.getItem('neo_mode') || 'ARBEIT';
        const player = document.getElementById('player');

        function saveState() {
            localStorage.setItem('neo_memory', JSON.stringify(mem));
            localStorage.setItem('neo_mode', mode);
            document.getElementById('mBtn').innerText = mode;
            document.getElementById('nCount').innerText = mem.length;
        }
        saveState();

        function toggleMode() { mode = mode === 'ARBEIT' ? 'PRIVAT' : 'ARBEIT'; saveState(); }

        function openHolo(type) {
            const modal = document.getElementById('holoModal');
            const title = document.getElementById('holoTitle');
            const body = document.getElementById('holoBody');
            modal.classList.add('open');

            if (type === 'calendar') {
                title.innerText = 'KALENDER';
                body.innerHTML = cachedEvents.length
                    ? cachedEvents.map(e => `<div class="holo-row"><div><div style="color:var(--orange);font-size:11px;">${e.time}</div><div style="font-weight:700;">${e.title}</div></div></div>`).join('')
                    : '<div style="color:var(--muted);">Keine Termine.</div>';
            } else if (type === 'codes') {
                title.innerText = `CODES (${mem.length})`;
                body.innerHTML = `<div style="display:flex;gap:6px;margin-bottom:10px;"><input id="cInp" type="text" placeholder="Neuer Code..." style="flex:1;background:#030712;border:1px solid var(--border);color:#fff;padding:6px;border-radius:4px;"><button class="gold-pill" onclick="mem.push(document.getElementById('cInp').value);saveState();openHolo('codes');">+</button></div>` +
                    (mem.length ? mem.map((x, i) => `<div class="holo-row"><span>${x}</span><button class="gold-pill" onclick="mem.splice(${i},1);saveState();openHolo('codes');">✕</button></div>`).join('') : '');
            }
        }
        function closeHolo() { document.getElementById('holoModal').classList.remove('open'); }

        function setSt(s) {
            coreStateMode = s || 'idle';
            document.getElementById('coreState').innerText = s === 'listening' ? 'HÖRE ZU...' : (s === 'thinking' ? 'DENKT NACH...' : (s === 'speaking' ? 'SPRICHT' : 'SAY "HEY NEO"'));
        }

        // --- 4. FAST SPEECH ENGINE ---
        let wakeOn = true, activeSession = false, isBusy = false, srInstance = null;

        function toggleWake() {
            wakeOn = !wakeOn;
            document.getElementById('wBtn').innerText = wakeOn ? '● HEY NEO' : '○ PAUSIERT';
            if (!wakeOn && srInstance) srInstance.abort();
            else startAlwaysListening();
        }

        function manualListenTrigger() {
            if (isBusy) { player.pause(); isBusy = false; }
            activeSession = true;
            beep(520, 920);
            setSt('listening');
        }

        function startAlwaysListening() {
            if (!wakeOn || isBusy) return;
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SR) return;
            if (srInstance) { try { srInstance.abort(); } catch(e){} }

            srInstance = new SR();
            srInstance.lang = 'de-DE';
            srInstance.continuous = true;
            srInstance.interimResults = true;

            srInstance.onresult = (e) => {
                if (isBusy) return;
                for (let i = e.resultIndex; i < e.results.length; i++) {
                    const raw = e.results[i][0].transcript.trim();
                    const low = raw.toLowerCase();
                    if (low.includes('neo') || activeSession) {
                        if (e.results[i].isFinal) {
                            beep(640, 880);
                            processVoiceText(raw);
                            return;
                        }
                    }
                }
            };
            srInstance.onend = () => { if (wakeOn && !isBusy) setTimeout(startAlwaysListening, 300); };
            try { srInstance.start(); } catch(e) {}
        }

        function processVoiceText(txt) {
            isBusy = true;
            if (srInstance) { try { srInstance.abort(); } catch(e){} }
            setSt('thinking');
            sendNeo({ message: txt });
        }

        player.onplay = () => { isBusy = true; setSt('speaking'); };
        player.onended = () => { isBusy = false; setSt(null); if (wakeOn) startAlwaysListening(); };

        function quickCmd(t) { isBusy = true; setSt('thinking'); sendNeo({ message: t }); }
        function sendTg() { quickCmd('Sende Telegram Autorisierung.'); }
        function handleImg(ev) { if(ev.target.files[0]) quickCmd('Analysiere Mängel-Foto.'); }

        async function sendNeo(payload) {
            payload.mode = mode; payload.memory = mem; payload.local_time_str = new Date().toLocaleString('de-DE');
            try {
                const res = await fetch('/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
                const d = await res.json();
                document.getElementById('replyBox').innerText = d.reply || "Erledigt.";
                if (d.audio) {
                    player.src = "data:audio/mp3;base64," + d.audio;
                    player.play().catch(() => { isBusy = false; setSt(null); if (wakeOn) startAlwaysListening(); });
                } else { isBusy = false; setSt(null); if (wakeOn) startAlwaysListening(); }
            } catch(e) { isBusy = false; setSt(null); if (wakeOn) startAlwaysListening(); }
        }

        window.onload = startAlwaysListening;
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

SYSTEM_PROMPT = """Du bist NEO, der KI-Assistent von Margil (Gebäudereinigung Hamburg).
Modus: {mode} | Zeit: {local_time}. Antworte kurz, direkt auf Deutsch.
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
    return jsonify({"name": "NEO", "short_name": "NEO", "start_url": "/", "display": "standalone", "background_color": "#030712", "theme_color": "#030712"})

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
    app.run("0.0.0.0", port=int(os.environ.get("PORT", 5000)))
