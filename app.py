import os
import re
import time
import json
import base64
import asyncio
import urllib.request
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, Response
from google import genai
from google.genai import types
import edge_tts

app = Flask(__name__)
ICAL_CACHE = {"ts": 0, "events": []}

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="115" fill="#090A0F"/>
  <circle cx="256" cy="256" r="155" fill="none" stroke="#38BDF8" stroke-width="8" stroke-dasharray="16 10"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#F59E0B" stroke-width="5"/>
  <circle cx="256" cy="256" r="24" fill="#F59E0B"/>
</svg>"""

HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#090A0F">
    <link rel="manifest" href="/manifest.json">
    <title>NEO // Enterprise Intelligence OS</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --accent: #38BDF8;
            --accent-glow: rgba(56, 189, 248, 0.15);
            --orange: #F59E0B;
            --bg: #090A0F;
            --card-bg: #12141C;
            --card-border: rgba(255, 255, 255, 0.08);
            --card-hover: #181B26;
            --text: #F8FAFC;
            --muted: #94A3B8;
            --success: #10B981;
        }

        body.listening { --accent: #10B981; --accent-glow: rgba(16, 185, 129, 0.2); }
        body.thinking  { --accent: #38BDF8; --accent-glow: rgba(56, 189, 248, 0.2); }
        body.speaking  { --accent: #8B5CF6; --accent-glow: rgba(139, 92, 246, 0.2); }

        * { box-sizing: border-box; user-select: none; -webkit-tap-highlight-color: transparent; }

        html, body {
            margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden;
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Inter', sans-serif;
        }

        /* HEADER */
        .app-header {
            display: flex; justify-content: space-between; align-items: center;
            height: 64px; padding: 0 24px; background: var(--card-bg);
            border-bottom: 1px solid var(--card-border);
        }
        .brand { display: flex; align-items: center; gap: 12px; }
        .brand-logo { width: 10px; height: 10px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 12px var(--accent); }
        .brand-name { font-weight: 700; font-size: 15px; letter-spacing: 1px; color: #fff; }
        
        .header-info { display: flex; align-items: center; gap: 12px; }
        .weather-badge, .live-clock {
            font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent);
            background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.2);
            padding: 5px 12px; border-radius: 8px; display: flex; align-items: center; gap: 6px;
        }
        .status-pill {
            display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.03);
            border: 1px solid var(--card-border); padding: 6px 14px; border-radius: 20px;
            font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--muted);
        }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--success); }

        /* MAIN LAYOUT */
        .app-container {
            display: grid;
            grid-template-columns: 320px 1fr 320px;
            gap: 20px;
            padding: 24px;
            height: calc(100vh - 64px);
            max-width: 1600px;
            margin: 0 auto;
        }

        @media(max-width: 1100px) {
            .app-container { grid-template-columns: 1fr; height: auto; overflow-y: auto; }
        }

        /* CARDS / MODULES */
        .panel {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .section-title {
            font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 500;
            text-transform: uppercase; letter-spacing: 1.5px; color: var(--muted);
            border-bottom: 1px solid var(--card-border); padding-bottom: 8px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .nav-card {
            background: rgba(255,255,255,0.015);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 14px 16px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex; flex-direction: column; gap: 4px;
        }
            .nav-card:hover {
            background: var(--card-hover);
            border-color: rgba(255,255,255,0.15);
            transform: translateY(-1px);
        }
        .nav-card-title { font-weight: 600; font-size: 14px; color: #fff; display: flex; justify-content: space-between; align-items: center; }
        .nav-card-desc { font-size: 12.5px; color: var(--muted); line-height: 1.4; }

        /* CENTER CORE */
        .core-display {
            background: linear-gradient(180deg, #12141C 0%, #0D0F17 100%);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 30px;
            text-align: center;
            position: relative;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }

        /* MINIMALIST PULSING ORB */
        .neural-orb-container {
            width: 170px; height: 170px;
            display: flex; align-items: center; justify-content: center;
            cursor: pointer; position: relative; margin: 15px 0;
        }
        .orb-ring {
            position: absolute; inset: 0; border-radius: 50%;
            border: 1px solid var(--accent); opacity: 0.3;
            animation: pulseOrb 3s infinite ease-in-out;
        }
        .orb-ring:nth-child(2) { inset: -15px; opacity: 0.15; animation-delay: 1s; }
        .orb-core {
            width: 85px; height: 85px; border-radius: 50%;
            background: radial-gradient(circle, var(--accent) 0%, rgba(56,189,248,0.2) 60%, transparent 100%);
            box-shadow: 0 0 40px var(--accent-glow);
            transition: all 0.3s ease;
        }
        @keyframes pulseOrb {
            0% { transform: scale(0.95); opacity: 0.2; }
            50% { transform: scale(1.08); opacity: 0.5; }
            100% { transform: scale(0.95); opacity: 0.2; }
        }

        .core-prompt { font-size: 18px; font-weight: 600; color: #fff; margin-bottom: 6px; }
        .core-sub { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--muted); margin-bottom: 20px; }
        
        .primary-btn {
            background: #fff; color: #090A0F; border: none;
            padding: 10px 24px; border-radius: 8px; font-weight: 600; font-size: 13px;
            cursor: pointer; transition: all 0.2s; font-family: 'Inter', sans-serif;
        }
        .primary-btn:hover { background: #E2E8F0; transform: translateY(-1px); }

        /* ACTIVITY LOG */
        .activity-log {
            width: 100%; background: rgba(0,0,0,0.3); border: 1px solid var(--card-border);
            border-radius: 8px; padding: 12px 16px; font-family: 'JetBrains Mono', monospace;
            font-size: 11.5px; color: var(--accent); text-align: left; margin-top: 20px;
        }

        /* MODAL */
        .modal-backdrop {
            position: fixed; inset: 0; background: rgba(9, 10, 15, 0.8);
            backdrop-filter: blur(8px); z-index: 100; display: none;
            align-items: center; justify-content: center; padding: 20px;
        }
        .modal-backdrop.open { display: flex; }
        .modal-box {
            background: var(--card-bg); border: 1px solid var(--card-border);
            border-radius: 14px; width: 100%; max-width: 440px; padding: 24px;
            display: flex; flex-direction: column; gap: 16px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6);
        }
        .modal-header {
            display: flex; justify-content: space-between; align-items: center;
            font-weight: 600; font-size: 14px; color: #fff;
            border-bottom: 1px solid var(--card-border); padding-bottom: 10px;
        }
        .modal-content { max-height: 280px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; font-size: 13.5px; }
        .modal-row { background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); padding: 10px 12px; border-radius: 8px; }
        
        input, select {
            background: #090A0F; border: 1px solid var(--card-border); color: #fff;
            padding: 10px 12px; border-radius: 8px; font-family: 'Inter', sans-serif; font-size: 13.5px; outline: none;
        }
        input:focus, select:focus { border-color: var(--accent); }
    </style>
</head>
<body>
    <header class="app-header">
        <div class="brand">
            <div class="brand-logo"></div>
            <span class="brand-name">NEO // ENTERPRISE OS</span>
        </div>
        <div class="header-info">
            <div class="weather-badge" id="weatherDisplay">☁️ Hamburg: Lade...</div>
            <div class="live-clock" id="liveClockDisplay">--:--:--</div>
            <div class="status-pill">
                <div class="status-dot"></div>
                <span>HAMBURG ACTIVE</span>
            </div>
        </div>
    </header>

    <div class="app-container">
        <!-- LEFT PANEL -->
        <div class="panel">
            <div class="section-title"><span>Operations</span> <span id="eventCountBadge" style="color:var(--accent);">0 Termine</span></div>
            
            <div class="nav-card" onclick="quickCmd('Gib mir mein Morning Briefing mit Terminen heute.')">
                <div class="nav-card-title"><span>☀️ Morning Brief</span> <span style="font-size:10px; color:var(--accent);">API</span></div>
                <div class="nav-card-desc">Tagesübersicht und Einsätze in Hamburg.</div>
            </div>

            <div class="nav-card" onclick="openModal('calendar')">
                <div class="nav-card-title"><span>📅 Kalender Sync</span> <span style="font-size:10px; color:var(--success);">LIVE</span></div>
                <div class="nav-card-desc">Einsätze und Objektstandorte verwalten.</div>
            </div>

            <div class="nav-card" onclick="openModal('codes')">
                <div class="nav-card-title"><span>🔐 Objekt-Codes</span> <span id="codeCountBadge" style="font-size:10px; color:var(--orange);">0 Codes</span></div>
                <div class="nav-card-desc">Sichere Notizen und Zugangscodes.</div>
            </div>
        </div>

        <!-- CENTER CORE -->
        <div class="core-display">
            <div style="font-family:'JetBrains Mono'; font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:1.5px;">Neural Voice Interface</div>
            
            <div class="neural-orb-container" onclick="toggleListening()">
                <div class="orb-ring"></div>
                <div class="orb-ring"></div>
                <div class="orb-core"></div>
            </div>

            <div class="core-prompt" id="corePrompt">Sage: „Hey Neo“</div>
            <div class="core-sub" id="coreSub">Lauscht im Hintergrund</div>
            
            <button class="primary-btn" onclick="toggleListening()">Sprachbefehl starten</button>

            <div class="activity-log" id="activityLog">
                > System initialisiert. Bereit für Befehle...
            </div>
        </div>

        <!-- RIGHT PANEL -->
        <div class="panel">
            <div class="section-title"><span>Business Tools</span> <span style="color:var(--success);">31.50 €/h</span></div>

            <div class="nav-card" onclick="openModal('calc')">
                <div class="nav-card-title"><span>📐 Angebots-Rechner</span> <span style="font-size:10px; color:var(--accent);">PRO</span></div>
                <div class="nav-card-desc">Kalkulation für Kunden in Hamburg.</div>
            </div>

            <div class="nav-card" onclick="document.getElementById('cam').click()">
                <div class="nav-card-title"><span>📸 Mängel-Foto</span> <span style="font-size:10px; color:var(--success);">VISION</span></div>
                <div class="nav-card-desc">Objekt-Schäden fotografieren & analysieren.</div>
            </div>

            <div class="nav-card" onclick="sendTelegramAuth()">
                <div class="nav-card-title"><span>✈️ Telegram Auth</span> <span style="font-size:10px; color:var(--orange);">SECURE</span></div>
                <div class="nav-card-desc">Echtzeit-Freigabe über Telegram Bot.</div>
            </div>
        </div>
    </div>

    <!-- MODAL -->
    <div class="modal-backdrop" id="appModal">
        <div class="modal-box">
            <div class="modal-header">
                <span id="modalTitle">DATEN</span>
                <button onclick="closeModal()" style="background:none; border:none; color:var(--muted); cursor:pointer; font-size:16px;">✕</button>
            </div>
            <div class="modal-content" id="modalBody"></div>
        </div>
    </div>

    <input type="file" id="cam" accept="image/*" style="display:none" onchange="handleImage(event)">
    <audio id="audioPlayer" playsinline></audio>

    <script>
        // LIVE CLOCK & WEATHER SCRIPT
        function updateClock() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('de-DE');
            const dateStr = now.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' });
            document.getElementById('liveClockDisplay').innerText = `${dateStr}, ${timeStr}`;
        }
        setInterval(updateClock, 1000);
        updateClock();

        // FETCH LIVE WEATHER FOR HAMBURG
        fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true')
            .then(r => r.json())
            .then(data => {
                if (data && data.current_weather) {
                    const temp = data.current_weather.temperature;
                    document.getElementById('weatherDisplay').innerText = `🌡️ Hamburg: ${temp}°C`;
                }
            }).catch(() => {
                document.getElementById('weatherDisplay').innerText = `🌡️ Hamburg: Aktiv`;
            });

        let isRecording = false, isSpeaking = false, inConversation = false;
        let mediaRecorder = null, audioStream = null, wakeRecognition = null;
        let eventsCache = [];
        const audioPlayer = document.getElementById('audioPlayer');
        const corePrompt = document.getElementById('corePrompt');
        const coreSub = document.getElementById('coreSub');
        const activityLog = document.getElementById('activityLog');

        fetch('/calendar_preview').then(r => r.json()).then(d => { 
            eventsCache = d.events || []; 
            document.getElementById('eventCountBadge').innerText = eventsCache.length + " Termine";
        }).catch(()=>{});

        let localMemory = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        document.getElementById('codeCountBadge').innerText = localMemory.length + " Codes";

        function logActivity(text) {
            activityLog.innerText = "> " + text;
        }

        function openModal(type) {
            const modal = document.getElementById('appModal');
            const title = document.getElementById('modalTitle');
            const body = document.getElementById('modalBody');
            modal.classList.add('open');

            if (type === 'calendar') {
                title.innerText = 'KALENDER TERMINE';
                body.innerHTML = eventsCache.length
                    ? eventsCache.map(e => `<div class="modal-row"><div style="color:var(--orange); font-size:11px; font-family:'JetBrains Mono';">${e.time}</div><div style="font-weight:600; margin-top:2px;">${e.title}</div><div style="color:var(--muted); font-size:11px; margin-top:2px;">${e.loc||''}</div></div>`).join('')
                    : '<div style="color:var(--muted);">Keine Termine gefunden.</div>';
            } else if (type === 'codes') {
                title.innerText = `OBJEKT-CODES (${localMemory.length})`;
                let list = localMemory.length ? localMemory.map((x, i) => `<div class="modal-row" style="display:flex; justify-content:space-between; align-items:center;"><span>${x}</span><button onclick="localMemory.splice(${i},1);localStorage.setItem('neo_memory',JSON.stringify(localMemory));document.getElementById('codeCountBadge').innerText = localMemory.length + ' Codes';openModal('codes');" style="background:none;border:none;color:var(--muted);cursor:pointer;">✕</button></div>`).join('') : '<div style="color:var(--muted);">Keine Codes gespeichert.</div>';
                body.innerHTML = `<div style="display:flex; gap:8px; margin-bottom:4px;"><input id="inputCode" type="text" placeholder="Neuer Code..." style="flex:1;"><button class="primary-btn" onclick="if(document.getElementById('inputCode').value.trim()){localMemory.push(document.getElementById('inputCode').value.trim());localStorage.setItem('neo_memory',JSON.stringify(localMemory));document.getElementById('codeCountBadge').innerText = localMemory.length + ' Codes';openModal('codes');}">Speichern</button></div>` + list;
            } else if (type === 'calc') {
                title.innerText = 'ANGEBOTS-KALKULATOR (31,50 €/Std)';
                body.innerHTML = `<div style="display:flex; flex-direction:column; gap:12px;">
                    <input id="calcQm" type="number" placeholder="Fläche in m² (z.B. 600)" value="600">
                    <select id="calcFreq">
                        <option value="1x pro Woche">1x pro Woche</option>
                        <option value="2x pro Woche" selected>2x pro Woche</option>
                        <option value="3x pro Woche">3x pro Woche</option>
                        <option value="5x pro Woche">5x pro Woche</option>
                    </select>
                    <button class="primary-btn" onclick="closeModal(); quickCmd('Kalkuliere ein Reinigungsangebot für '+document.getElementById('calcQm').value+' m², '+document.getElementById('calcFreq').value+', und erstelle den Angebotstext.');">Angebot erstellen</button>
                </div>`;
            }
        }
        function closeModal() { document.getElementById('appModal').classList.remove('open'); }

        async function sendTelegramAuth() {
            logActivity("Sende Telegram Authentifizierung...");
            try {
                const res = await fetch('/telegram_notify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:"📞 NEO Autorisierung angefordert!"}) });
                const data = await res.json();
                logActivity(data.ok ? "Telegram Freigabe gesendet." : "Fehler: " + (data.error || "Unbekannt"));
            } catch(e) { logActivity("Verbindungsfehler zu Telegram."); }
        }

        function handleImage(e) {
            const file = e.target.files[0]; if(!file) return;
            logActivity("Lade Mängel-Foto hoch...");
            const reader = new FileReader();
            reader.onload = evt => sendBackend({ image: evt.target.result.split(',')[1], message: "Erstelle einen professionellen Mängelbericht." });
            reader.readAsDataURL(file);
        }

        function startWakeWord() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) return;
            try {
                wakeRecognition = new SpeechRecognition();
                wakeRecognition.lang = 'de-DE'; wakeRecognition.continuous = true; wakeRecognition.interimResults = true;
                wakeRecognition.onresult = (e) => {
                    for (let i = e.resultIndex; i < e.results.length; i++) {
                        const transcript = e.results[i][0].transcript.toLowerCase();
                        if (transcript.includes('hey neo') || transcript.includes('hallo neo') || transcript.includes('neo')) {
                            if (wakeRecognition) { try { wakeRecognition.abort(); } catch(err){} }
                            inConversation = true; startAudioRecording(); return;
                        }
                    }
                };
                wakeRecognition.onend = () => { if (!isRecording && !isSpeaking && !inConversation) setTimeout(startWakeWord, 800); };
                wakeRecognition.start();
            } catch(e) {}
        }

        function toggleListening() {
            if (isSpeaking) { audioPlayer.pause(); isSpeaking = false; resetState(); return; }
            if (isRecording) { isRecording = false; if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop(); return; }
            inConversation = true; startAudioRecording();
        }

        function resetState() {
            document.body.className = '';
            corePrompt.innerText = "Sage: „Hey Neo“";
            coreSub.innerText = "Lauscht im Hintergrund";
        }

        async function startAudioRecording() {
            if (isRecording || isSpeaking) return;
            if (wakeRecognition) { try { wakeRecognition.abort(); } catch(e){} }
            try {
                audioStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
                let chunks = [];
                mediaRecorder = new MediaRecorder(audioStream, { audioBitsPerSecond: 16000 });
                mediaRecorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
                mediaRecorder.onstop = () => {
                    audioStream.getTracks().forEach(t => t.stop());
                    const blob = new Blob(chunks, { type: mediaRecorder.mimeType || 'audio/webm' });
                    if (blob.size < 600) { inConversation = false; resetState(); startWakeWord(); return; }
                    document.body.className = 'thinking';
                    corePrompt.innerText = "Analysiere...";
                    coreSub.innerText = "Verarbeite Anfrage...";
                    logActivity("Verarbeite Audio über Gemini AI...");
                    const reader = new FileReader();
                    reader.readAsDataURL(blob);
                    reader.onloadend = () => {
                        sendBackend({ audio: reader.result.split(',')[1], mime_type: (mediaRecorder.mimeType || 'audio/webm').split(';')[0] });
                    };
                };
                mediaRecorder.start();
                isRecording = true;
                document.body.className = 'listening';
                corePrompt.innerText = "Ich höre zu...";
                coreSub.innerText = "Sprich jetzt...";
                logActivity("Sprachstrom aktiv...");
                setTimeout(() => { if (isRecording) { isRecording = false; mediaRecorder.stop(); } }, 6000);
            } catch(e) { inConversation = false; resetState(); startWakeWord(); }
        }

        audioPlayer.onplay = () => { isSpeaking = true; document.body.className = 'speaking'; corePrompt.innerText = "NEO spricht..."; coreSub.innerText = "Audioausgabe aktiv"; };
        audioPlayer.onended = () => { isSpeaking = false; resetState(); if (inConversation) setTimeout(startAudioRecording, 400); else startWakeWord(); };

        function quickCmd(text) {
            inConversation = true; document.body.className = 'thinking'; corePrompt.innerText = "Analysiere..."; logActivity("Führe Schnellbefehl aus..."); sendBackend({ message: text });
        }

        async function sendBackend(payload) {
            payload.mode = "ARBEIT"; payload.memory = localMemory; payload.local_time_str = new Date().toLocaleString('de-DE');
            try {
                const res = await fetch('/chat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                const data = await res.json();
                if (data.error) { inConversation = false; resetState(); logActivity("Fehler: " + data.error); startWakeWord(); return; }
                if (data.end_conversation) inConversation = false;
                if (data.new_memory) { 
                    localMemory.push(data.new_memory); 
                    localStorage.setItem('neo_memory', JSON.stringify(localMemory)); 
                    document.getElementById('codeCountBadge').innerText = localMemory.length + " Codes";
                }
                logActivity(data.reply || "Aktion erfolgreich abgeschlossen.");
                if (data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    audioPlayer.play().catch(() => { isSpeaking = false; resetState(); startWakeWord(); });
                } else { resetState(); startWakeWord(); }
            } catch(e) { inConversation = false; resetState(); logActivity("Server-Verbindungsfehler."); startWakeWord(); }
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
        "background_color": "#090A0F",
        "theme_color": "#090A0F",
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
    text_content = ""
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
        text_content = resp.text.strip()

        m = re.search(r'\{.*\}', text_content, re.DOTALL)
        res = json.loads(m.group(0)) if m else {"reply": text_content}
        reply = res.get("reply", text_content)
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
        try:
            fallback_reply = text_content if text_content else "Zu Befehl, Margil."
            audio = asyncio.run(make_voice(fallback_reply, "de"))
            return jsonify({
                "reply": fallback_reply,
                "copy_text": "",
                "new_memory": "",
                "action_url": "",
                "action_label": "",
                "end_conversation": False,
                "audio": audio
            })
        except Exception as inner_e:
            return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run("0.0.0.0", port=int(os.environ.get("PORT", 5000)))
