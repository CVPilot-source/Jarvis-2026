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
    <title>N.E.O. // CYBERNETIC OS</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

        :root {
            --cyan: #00E5FF;
            --orange: #FF9900;
            --bg: #030712;
            --panel: rgba(6, 12, 24, 0.85);
            --panel-hover: rgba(10, 20, 38, 0.95);
            --border: rgba(0, 229, 255, 0.25);
            --border-glow: rgba(0, 229, 255, 0.6);
            --text: #F8FAFC;
            --muted: #64748B;
            --green: #10B981;
        }

        body.listening { --cyan: #10B981; --border-glow: rgba(16, 185, 129, 0.8); }
        body.thinking  { --cyan: #00E5FF; --border-glow: rgba(0, 229, 255, 0.8); }
        body.speaking  { --cyan: #A855F7; --border-glow: rgba(168, 85, 247, 0.8); }

        * { box-sizing: border-box; user-select: none; -webkit-tap-highlight-color: transparent; }

        html, body {
            margin: 0; padding: 0; width: 100vw; height: 100vh; overflow-x: hidden;
            background-color: var(--bg);
            background-image: 
                radial-gradient(circle at 50% 50%, rgba(0, 229, 255, 0.05) 0%, transparent 80%),
                linear-gradient(rgba(0, 229, 255, 0.015) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 229, 255, 0.015) 1px, transparent 1px);
            background-size: 100% 100%, 40px 40px, 40px 40px;
            color: var(--text);
            font-family: 'Rajdhani', sans-serif;
        }

        /* TOP CYBER BAR */
        .top-bar {
            display: flex; justify-content: space-between; align-items: center;
            padding: 14px 24px; background: var(--panel); backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border); font-family: 'JetBrains Mono', monospace; font-size: 11.5px;
        }
        .top-title { color: var(--cyan); font-weight: 700; letter-spacing: 3px; font-size: 16px; text-shadow: 0 0 10px rgba(0,229,255,0.4); }
        .metrics { display: flex; gap: 20px; color: var(--muted); }
        .metrics span b { color: var(--text); }

        /* DASHBOARD GRID */
        .dashboard-grid {
            display: grid;
            grid-template-columns: 300px 1fr 310px;
            gap: 16px;
            padding: 20px;
            max-width: 1450px;
            margin: 0 auto;
        }

        @media(max-width: 1024px) {
            .dashboard-grid { grid-template-columns: 1fr; }
        }

        /* MODERN GLASS CARDS */
        .card {
            background: var(--panel);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            cursor: pointer;
            transition: all 0.25s ease;
            position: relative;
            overflow: hidden;
        }
        .card::before {
            content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%;
            background: var(--orange); opacity: 0.7;
        }
        .card:hover {
            background: var(--panel-hover);
            border-color: var(--border-glow);
            box-shadow: 0 0 25px rgba(0, 229, 255, 0.2);
            transform: translateY(-2px);
        }
        .card-header {
            display: flex; justify-content: space-between; align-items: center;
            font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 700;
            color: var(--orange); border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 6px;
        }
        .card-title { font-size: 16px; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 8px; }
        .card-desc { font-size: 13px; color: var(--muted); line-height: 1.4; }
        
        .badge-enabled {
            background: rgba(16, 185, 129, 0.15); color: var(--green);
            padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        /* CENTER CORE PANEL */
        .center-core-panel {
            background: rgba(4, 9, 18, 0.9);
            backdrop-filter: blur(15px);
            border: 1px solid var(--border-glow);
            border-radius: 16px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            position: relative;
            box-shadow: 0 0 40px rgba(0,229,255,0.15);
        }
        .hologram-stage {
            width: 240px; height: 240px;
            display: flex; align-items: center; justify-content: center;
            cursor: pointer; position: relative; margin: 10px 0;
        }
        .holo-svg { width: 100%; height: 100%; filter: drop-shadow(0 0 20px rgba(0,229,255,0.6)); }

        .action-btn {
            background: linear-gradient(135deg, rgba(0,229,255,0.25), rgba(255,153,0,0.25));
            border: 1px solid var(--cyan); color: var(--text);
            padding: 10px 22px; border-radius: 99px; font-weight: 700; font-size: 13px;
            cursor: pointer; transition: 0.25s; font-family: 'JetBrains Mono', monospace;
            box-shadow: 0 0 15px rgba(0,229,255,0.2);
        }
        .action-btn:hover { background: var(--cyan); color: #030712; box-shadow: 0 0 25px var(--cyan); transform: scale(1.05); }

        /* LIVE TERMINAL FEED */
        .terminal-box {
            width: 100%; background: rgba(2, 5, 10, 0.9);
            border: 1px solid rgba(0,229,255,0.15); border-radius: 8px;
            padding: 10px 14px; font-family: 'JetBrains Mono', monospace;
            font-size: 11px; color: var(--cyan); text-align: left;
            margin-top: 14px; min-height: 45px; max-height: 60px; overflow: hidden;
        }

        /* MODAL */
        .holo-modal {
            position: fixed; inset: 0; background: rgba(3, 7, 18, 0.88);
            backdrop-filter: blur(12px); z-index: 50; display: none;
            align-items: center; justify-content: center; padding: 16px;
        }
        .holo-modal.open { display: flex; }
        .holo-box {
            background: var(--panel); border: 1px solid var(--cyan);
            border-radius: 14px; width: 100%; max-width: 460px;
            padding: 24px; display: flex; flex-direction: column; gap: 14px;
            box-shadow: 0 0 50px rgba(0,229,255,0.3);
        }
        .holo-head {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--border); padding-bottom: 10px;
            font-size: 14px; font-weight: 700; color: var(--cyan);
        }
        .holo-content { max-height: 280px; overflow-y: auto; font-size: 13.5px; display: flex; flex-direction: column; gap: 8px; }
        .holo-row { padding: 10px; background: rgba(0,229,255,0.06); border-left: 3px solid var(--orange); border-radius: 6px; }
        input, select { background: #030712; border: 1px solid var(--border); color: #fff; padding: 10px; border-radius: 8px; font-family: 'Rajdhani'; font-size: 14px; }
    </style>
</head>
<body>
    <!-- TOP STATS BAR -->
    <div class="top-bar">
        <div class="top-title">N.E.O. // CYBERNETIC OS</div>
        <div class="metrics">
            <span>MODUS: <b>ARBEIT</b></span>
            <span>STATUS: <b style="color:var(--green);">SECURE STREAM</b></span>
        </div>
    </div>

    <!-- DASHBOARD GRID -->
    <div class="dashboard-grid">
        <!-- LEFT COLUMN -->
        <div style="display:flex; flex-direction:column; gap:16px;">
            <div class="card" onclick="quickCmd('Gib mir mein Morning Briefing mit Terminen heute.')">
                <div class="card-header"><span>$/brief-mode</span><span class="badge-enabled">ACTIVE</span></div>
                <div class="card-title">☀️ Morning Brief</div>
                <div class="card-desc">Liest heutige Termine & Objekt-Codes in Hamburg aus.</div>
            </div>

            <div class="card" onclick="openHolo('calendar')">
                <div class="card-header"><span>📅 /calendar</span><span class="badge-enabled">SYNCED</span></div>
                <div class="card-title">Kalender Termine</div>
                <div class="card-desc">Einsätze und Objektstandorte live synchronisiert.</div>
            </div>

            <div class="card" onclick="openHolo('codes')">
                <div class="card-header"><span>🔐 /memory</span><span class="badge-enabled">SECURE</span></div>
                <div class="card-title">Objekt-Codes</div>
                <div class="card-desc">Sichere Notizen und Zugangscodes verwalten.</div>
            </div>
        </div>

        <!-- CENTER COLUMN -->
        <div class="center-core-panel">
            <div class="card-header" style="width:100%; justify-content:center; border:none; color:var(--cyan); letter-spacing: 2px;">NEURAL CORE // ACTIVE VOICE INTERFACE</div>
            
            <div class="hologram-stage" onclick="toggleListening()">
                <svg class="holo-svg" viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="150" cy="150" r="125" fill="none" stroke="rgba(0,229,255,0.15)" stroke-width="1.5" stroke-dasharray="10 6"/>
                    <circle cx="150" cy="150" r="100" fill="none" stroke="rgba(255,153,0,0.2)" stroke-width="1"/>
                    <circle cx="150" cy="135" r="38" fill="url(#orangeGlow)" opacity="0.9"/>
                    <defs>
                        <radialGradient id="orangeGlow" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stop-color="#FF9900" stop-opacity="1"/>
                            <stop offset="60%" stop-color="#FF5500" stop-opacity="0.5"/>
                            <stop offset="100%" stop-color="#030712" stop-opacity="0"/>
                        </radialGradient>
                    </defs>
                    <g stroke="rgba(0,229,255,0.85)" stroke-width="1.8" fill="none" stroke-linecap="round">
                        <path d="M60,250 Q100,210 150,210 Q200,210 240,250" opacity="0.95"/>
                        <path d="M80,265 Q150,230 220,265" stroke="rgba(255,153,0,0.9)" stroke-width="1.2"/>
                        <path d="M130,210 L130,165" />
                        <path d="M170,210 L170,165" />
                        <path d="M120,165 Q110,120 125,85 Q135,60 150,55 Q165,60 175,85 Q190,120 180,165" />
                        <path d="M125,125 Q150,135 175,125" stroke="rgba(255,153,0,0.8)" />
                        <path d="M130,145 Q150,155 170,145" stroke="rgba(0,229,255,1)" />
                    </g>
                    <g fill="#00E5FF">
                        <circle cx="150" cy="55" r="3.5" fill="#FF9900"/>
                        <circle cx="125" cy="90" r="2.2" />
                        <circle cx="175" cy="90" r="2.2" />
                        <circle cx="150" cy="135" r="4" fill="#FF9900" />
                        <circle cx="110" cy="180" r="2.2" />
                        <circle cx="190" cy="180" r="2.2" />
                        <circle cx="150" cy="210" r="3.5" fill="#FF9900" />
                    </g>
                </svg>
            </div>

            <div id="wakePrompt" style="font-size:18px; font-weight:700; margin-bottom: 10px; color:var(--text); letter-spacing: 1px;">Sage: „Hey Neo“</div>
            <button class="action-btn" onclick="toggleListening()">🎙️ Sprachbefehl starten</button>
            
            <div class="terminal-box" id="terminalLog">
                > System bereit. Lauscht im Hintergrund...
            </div>
        </div>

        <!-- RIGHT COLUMN -->
        <div style="display:flex; flex-direction:column; gap:16px;">
            <div class="card" onclick="openHolo('calc')">
                <div class="card-header"><span>📐 /calculator</span><span class="badge-enabled">READY</span></div>
                <div class="card-title">Angebots-Rechner</div>
                <div class="card-desc">Kalkuliert Reinigungen exakt mit 31,50 €/Std.</div>
            </div>

            <div class="card" onclick="document.getElementById('cam').click()">
                <div class="card-header"><span>📸 /vision</span><span class="badge-enabled">ONLINE</span></div>
                <div class="card-title">Mängel-Foto</div>
                <div class="card-desc">Objekt-Mängel fotografieren und per KI analysieren.</div>
            </div>

            <div class="card" onclick="sendTg()">
                <div class="card-header"><span>✈️ /auth</span><span class="badge-enabled">SECURE</span></div>
                <div class="card-title">Telegram Auth</div>
                <div class="card-desc">Sichert Freigaben direkt in Echtzeit ab.</div>
            </div>
        </div>
    </div>

    <!-- HOLOGRAPHIC MODAL -->
    <div class="holo-modal" id="holoModal">
        <div class="holo-box">
            <div class="holo-head">
                <span id="holoTitle">DATEN</span>
                <button class="action-btn" style="padding:4px 10px;" onclick="closeHolo()">✕</button>
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
        const terminalLog = document.getElementById('terminalLog');

        function logTerm(txt) {
            terminalLog.innerText = "> " + txt;
        }

        fetch('/calendar_preview').then(r => r.json()).then(d => { cachedEvents = d.events || []; }).catch(()=>{});
        let mem = JSON.parse(localStorage.getItem('neo_memory') || '[]');

        function setVisualState(state) {
            document.body.className = state || '';
            if (state === 'listening') { wakePrompt.innerText = "Ich höre zu..."; logTerm("Sprachstrom aktiv. Empfange Audio..."); }
            else if (state === 'thinking') { wakePrompt.innerText = "Analysiere..."; logTerm("Verarbeite Anfrage über Gemini AI..."); }
            else if (state === 'speaking') { wakePrompt.innerText = "NEO spricht..."; logTerm("Generiere Edge-TTS Audioausgabe..."); }
            else { wakePrompt.innerText = "Sage: „Hey Neo“"; logTerm("System bereit. Lauscht im Hintergrund..."); }
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
                let list = mem.length ? mem.map((x, i) => `<div class="holo-row" style="display:flex;justify-content:space-between;align-items:center;"><span>${x}</span><button class="action-btn" style="padding:2px 8px;" onclick="mem.splice(${i},1);localStorage.setItem('neo_memory',JSON.stringify(mem));openHolo('codes');">✕</button></div>`).join('') : '<div style="color:var(--muted);">Keine Codes gespeichert.</div>';
                body.innerHTML = `<div style="display:flex;gap:8px;margin-bottom:8px;"><input id="newCode" type="text" placeholder="Neuer Code..." style="flex:1;"><button class="action-btn" onclick="if(document.getElementById('newCode').value.trim()){mem.push(document.getElementById('newCode').value.trim());localStorage.setItem('neo_memory',JSON.stringify(mem));openHolo('codes');}">Speichern</button></div>` + list;
            } else if (type === 'calc') {
                title.innerText = 'ANGEBOTS-KALKULATOR (31,50 €/Std)';
                body.innerHTML = `<div style="display:flex;flex-direction:column;gap:12px;">
                    <input id="cQm" type="number" placeholder="Fläche in m² (z.B. 600)" value="600">
                    <select id="cFreq">
                        <option value="1x pro Woche">1x pro Woche</option>
                        <option value="2x pro Woche" selected>2x pro Woche</option>
                        <option value="3x pro Woche">3x pro Woche</option>
                        <option value="5x pro Woche">5x pro Woche</option>
                    </select>
                    <button class="action-btn" onclick="closeHolo();quickCmd('Kalkuliere ein Reinigungsangebot für '+document.getElementById('cQm').value+' m², '+document.getElementById('cFreq').value+', und erstelle den Angebotstext.');">ANGEBOT ERSTELLEN</button>
                </div>`;
            }
        }
        function closeHolo() { document.getElementById('holoModal').classList.remove('open'); }

        async function sendTg() {
            logTerm("Sende Telegram Autorisierungsanfrage...");
            try {
                const r = await fetch('/telegram_notify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:"📞 NEO Autorisierung angefordert!"}) });
                const d = await r.json();
                logTerm(d.ok ? "Telegram Anfrage erfolgreich gesendet." : "Telegram Fehler: " + (d.error || "Unbekannt"));
            } catch(e) { logTerm("Telegram Verbindungsfehler."); }
        }

        function handleImg(ev) {
            const f = ev.target.files[0]; if(!f) return;
            setVisualState('thinking');
            logTerm("Lade Mängel-Foto für KI-Analyse hoch...");
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

        function quickCmd(t) { inConv = true; setVisualState('thinking'); logTerm("Führe Schnellbefehl aus..."); sendToNeoBackend({ message: t }); }

        async function sendToNeoBackend(payload) {
            payload.mode = "ARBEIT"; payload.memory = mem; payload.local_time_str = new Date().toLocaleString('de-DE');
            try {
                const res = await fetch('/chat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                const d = await res.json();
                if (d.error) { inConv = false; setVisualState(null); logTerm("Fehler: " + d.error); startWakeWord(); return; }
                if (d.end_conversation) inConv = false;
                if (d.new_memory) { mem.push(d.new_memory); localStorage.setItem('neo_memory', JSON.stringify(mem)); }
                logTerm(d.reply || "Aktion abgeschlossen.");
                if (d.audio) {
                    player.src = "data:audio/mp3;base64," + d.audio;
                    player.play().catch(() => { isSpk = false; setVisualState(null); startWakeWord(); });
                } else { setVisualState(null); startWakeWord(); }
            } catch(e) { inConv = false; setVisualState(null); logTerm("Server-Verbindungsfehler."); startWakeWord(); }
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
