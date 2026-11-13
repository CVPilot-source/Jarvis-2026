import os
import json
import base64
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, Response
from google import genai
from google.genai import types
import edge_tts

app = Flask(__name__)

MANIFEST_JSON = {
    "name": "JARVIS MARK X",
    "short_name": "JARVIS",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#050811",
    "theme_color": "#050811",
    "icons": [
        {
            "src": "/icon.svg",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any maskable"
        }
    ]
}

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0B132B"/>
      <stop offset="100%" stop-color="#04070F"/>
    </linearGradient>
    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38BDF8"/>
      <stop offset="50%" stop-color="#818CF8"/>
      <stop offset="100%" stop-color="#2DD4BF"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="120" fill="url(#bgGrad)"/>
  <circle cx="256" cy="256" r="175" fill="none" stroke="url(#ringGrad)" stroke-width="16" stroke-opacity="0.3"/>
  <circle cx="256" cy="256" r="145" fill="none" stroke="url(#ringGrad)" stroke-width="10" stroke-dasharray="110 40"/>
  <circle cx="256" cy="256" r="95" fill="#091124" stroke="url(#ringGrad)" stroke-width="6"/>
  <text x="256" y="280" font-family="sans-serif" font-size="76" font-weight="800" fill="#F8FAFC" text-anchor="middle">J</text>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#050811">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/svg+xml" href="/icon.svg">
    <title>JARVIS MARK X</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root {
            --accent: #38BDF8;
            --accent-2: #818CF8;
            --glow: rgba(56, 189, 248, 0.35);
            --bg-dark: #050811;
            --glass: rgba(15, 23, 42, 0.58);
            --glass-border: rgba(255, 255, 255, 0.09);
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
        }

        body.theme-emerald {
            --accent: #10B981;
            --accent-2: #34D399;
            --glow: rgba(16, 185, 129, 0.35);
        }

        body.theme-gold {
            --accent: #F59E0B;
            --accent-2: #FBBF24;
            --glow: rgba(245, 158, 11, 0.35);
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        body {
            margin: 0;
            background-color: var(--bg-dark);
            background-image:
                radial-gradient(circle at 50% 18%, var(--glow) 0%, transparent 55%),
                radial-gradient(circle at 85% 85%, rgba(129, 140, 248, 0.12) 0%, transparent 45%);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
            height: 100dvh;
            padding: 14px 16px 18px;
            overflow: hidden;
            transition: background 0.5s ease;
        }

        /* Top Glass Navigation Bar */
        .top-bar {
            width: 100%;
            max-width: 480px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--glass);
            border: 1px solid var(--glass-border);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            padding: 8px 10px;
            border-radius: 20px;
            gap: 6px;
        }

        .pill-group {
            display: flex;
            gap: 5px;
            align-items: center;
            overflow-x: auto;
            scrollbar-width: none;
        }
        .pill-group::-webkit-scrollbar { display: none; }

        .pill {
            font-size: 11px;
            font-weight: 600;
            padding: 5px 10px;
            border-radius: 14px;
            border: 1px solid var(--glass-border);
            background: rgba(255, 255, 255, 0.04);
            color: var(--text-main);
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s ease;
        }
        .pill:active { transform: scale(0.95); }

        .pill.work-active {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(217, 119, 6, 0.15));
            border-color: rgba(245, 158, 11, 0.5);
            color: #FCD34D;
        }
        .pill.privat-active {
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.25), rgba(129, 140, 248, 0.15));
            border-color: rgba(56, 189, 248, 0.5);
            color: #7DD3FC;
        }
        .pill.auto-on {
            background: #10B981;
            color: #04070F;
            border-color: #10B981;
            box-shadow: 0 0 14px rgba(16, 185, 129, 0.45);
        }

        /* Modern 3D Liquid Orb Core */
        .orb-stage {
            position: relative;
            width: 196px;
            height: 196px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
            margin-top: 4px;
        }

        .aurora-ring {
            position: absolute;
            width: 186px;
            height: 186px;
            border-radius: 50%;
            background: conic-gradient(from 0deg, var(--accent), var(--accent-2), transparent, var(--accent));
            animation: spinSlow 8s linear infinite;
            opacity: 0.75;
            filter: blur(4px);
        }

        .glass-ring {
            position: absolute;
            width: 174px;
            height: 174px;
            border-radius: 50%;
            border: 1px solid rgba(255, 255, 255, 0.16);
            background: rgba(5, 8, 17, 0.65);
            backdrop-filter: blur(10px);
        }

        .orb-core {
            position: relative;
            width: 136px;
            height: 136px;
            border-radius: 50%;
            background: radial-gradient(circle at 35% 30%, rgba(255,255,255,0.18), rgba(15, 23, 42, 0.9) 65%, #03060D 100%);
            border: 1.5px solid rgba(255, 255, 255, 0.2);
            box-shadow:
                0 12px 35px rgba(0, 0, 0, 0.6),
                inset 0 0 28px var(--glow),
                0 0 30px var(--glow);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 2;
            transition: transform 0.18s ease, box-shadow 0.3s ease;
        }

        .orb-core h1 {
            margin: 0;
            font-size: 20px;
            font-weight: 800;
            letter-spacing: 3px;
            background: linear-gradient(135deg, #FFFFFF 20%, var(--accent) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .orb-core span {
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 2px;
            color: var(--text-muted);
            margin-top: 4px;
            text-transform: uppercase;
        }

        body.listening { --accent: #10B981; --accent-2: #34D399; --glow: rgba(16, 185, 129, 0.55); }
        body.listening .aurora-ring { animation-duration: 2.2s; opacity: 1; }
        body.thinking { --accent: #F59E0B; --accent-2: #F43F5E; --glow: rgba(245, 158, 11, 0.55); }
        body.thinking .aurora-ring { animation-duration: 1.2s; opacity: 1; }
        body.speaking .orb-core { animation: orbSpeak 0.85s ease-in-out infinite alternate; }

        @keyframes spinSlow { 100% { transform: rotate(360deg); } }
        @keyframes orbSpeak {
            0% { transform: scale(1); }
            100% { transform: scale(1.07); }
        }

        /* Smooth Waveform Visualizer */
        .wave-box {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            height: 22px;
            margin-top: 4px;
        }
        .bar {
            width: 4px;
            height: 5px;
            background: linear-gradient(to top, var(--accent), var(--accent-2));
            border-radius: 99px;
            transition: height 0.08s ease;
        }
        .sub-hint {
            font-size: 11.5px;
            color: var(--text-muted);
            margin-top: 3px;
            font-weight: 500;
        }

        /* Glass Response Card */
        .response-card {
            flex: 1;
            width: 100%;
            max-width: 480px;
            margin: 10px 0;
            padding: 18px;
            background: var(--glass);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: 15.5px;
            font-weight: 400;
            line-height: 1.6;
            color: var(--text-main);
        }

        .list-card-item {
            width: 100%;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.07);
            padding: 9px 12px;
            border-radius: 14px;
            margin-bottom: 7px;
            font-size: 13.5px;
            text-align: left;
        }
        .check-btn {
            background: rgba(16, 185, 129, 0.2);
            color: #34D399;
            border: 1px solid rgba(16, 185, 129, 0.4);
            border-radius: 10px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            margin-left: 10px;
        }

        .btn-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            justify-content: center;
            margin-top: 14px;
        }
        .primary-action {
            padding: 11px 20px;
            border-radius: 16px;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            color: #04070F;
            font-weight: 700;
            text-decoration: none;
            font-size: 13.5px;
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 18px var(--glow);
        }
        .secondary-action {
            padding: 11px 16px;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #F8FAFC;
            font-weight: 600;
            font-size: 13.5px;
            cursor: pointer;
        }

        /* Quick Action Chips */
        .chips-row {
            display: flex;
            gap: 7px;
            width: 100%;
            max-width: 480px;
            overflow-x: auto;
            padding-bottom: 9px;
            scrollbar-width: none;
        }
        .chips-row::-webkit-scrollbar { display: none; }
        .chip {
            white-space: nowrap;
            padding: 7px 13px;
            border-radius: 16px;
            border: 1px solid var(--glass-border);
            background: var(--glass);
            backdrop-filter: blur(12px);
            color: var(--text-main);
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        .chip:active { transform: scale(0.95); background: rgba(255,255,255,0.12); }

        /* Floating Input Dock */
        .input-dock {
            display: flex;
            gap: 8px;
            width: 100%;
            max-width: 480px;
            align-items: center;
            background: var(--glass);
            border: 1px solid var(--glass-border);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            padding: 6px;
            border-radius: 26px;
        }
        .icon-btn {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: none;
            background: rgba(255, 255, 255, 0.07);
            color: var(--text-main);
            font-size: 17px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            flex-shrink: 0;
        }
        input[type="text"] {
            flex: 1;
            padding: 10px 8px;
            border: none;
            background: transparent;
            color: var(--text-main);
            font-size: 15px;
            font-family: inherit;
            outline: none;
            min-width: 0;
        }
        input::placeholder { color: var(--text-muted); }
        .send-pill {
            padding: 10px 18px;
            border-radius: 20px;
            border: none;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            color: #04070F;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            flex-shrink: 0;
        }
    </style>
</head>
<body>
    <div class="top-bar">
        <div class="pill work-active" id="modeBtn" onclick="toggleMode()">🏢 Arbeit</div>
        <div class="pill-group">
            <div class="pill" id="loopBtn" onclick="toggleLoop()">Auto: Aus</div>
            <div class="pill" onclick="showList('memory')" id="memCount">Notizen · 0</div>
            <div class="pill" onclick="showList('materials')" id="matCount">Material · 0</div>
            <div class="pill" onclick="showList('tasks')" id="taskCount">Tasks · 0</div>
            <div class="pill" onclick="cycleTheme()" title="Farbe ändern">🎨</div>
        </div>
    </div>

    <div style="display:flex; flex-direction:column; align-items:center;">
        <div class="orb-stage" onclick="toggleRecord()">
            <div class="aurora-ring"></div>
            <div class="glass-ring"></div>
            <div class="orb-core" id="orbCore">
                <h1>JARVIS</h1>
                <span id="stateLabel">Bereit</span>
            </div>
        </div>

        <div class="wave-box">
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        </div>
        <div class="sub-hint" id="hint">Tippen zum Sprechen • Kamera für Objekte & Briefe</div>
    </div>

    <div class="response-card" id="status">Guten Abend, Sir. Alle Systeme, Objekt-Notizen, Kamera und Dienste sind einsatzbereit.</div>

    <div class="chips-row">
        <div class="chip" onclick="quickCmd('Gib mir mein Tagesbriefing mit Terminen, E-Mails, Aufgaben und Materialliste.')">📋 Briefing</div>
        <div class="chip" onclick="saveParking()">🅿️ Parkplatz</div>
        <div class="chip" onclick="findParking()">🚗 Auto finden</div>
        <div class="chip" onclick="quickCmd('Welche Termine habe ich heute und morgen?')">📅 Termine</div>
        <div class="chip" onclick="quickCmd('Lies meine ungelesenen E-Mails vor.')">📧 E-Mails</div>
        <div class="chip" onclick="quickCmd('Öffne Google Maps')">🗺️ Maps</div>
    </div>

    <div class="input-dock">
        <button class="icon-btn" onclick="document.getElementById('camInput').click()" title="Kamera">📷</button>
        <input type="file" id="camInput" accept="image/*" capture="environment" style="display:none" onchange="handleImage(event)">
        <input type="text" id="msg" placeholder="Befehl, Objekt-Code oder Notiz..." onkeypress="if(event.key==='Enter') sendText()">
        <button class="send-pill" onclick="sendText()">Senden</button>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        const statusEl = document.getElementById('status');
        const hintEl = document.getElementById('hint');
        const stateLabel = document.getElementById('stateLabel');
        const orbCore = document.getElementById('orbCore');
        const bars = document.querySelectorAll('.bar');
        const player = document.getElementById('player');

        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;
        let activeStream = null;
        let audioCtx = null;
        let silenceTimer = null;
        let animFrame = null;

        let autoLoop = false;
        let workMode = localStorage.getItem('jarvis_mode') || 'ARBEIT';
        let themeIdx = parseInt(localStorage.getItem('jarvis_theme') || '0');
        const themes = ['', 'theme-emerald', 'theme-gold'];

        let userMemory = JSON.parse(localStorage.getItem('jarvis_memory') || '[]');
        let userMaterials = JSON.parse(localStorage.getItem('jarvis_materials') || '[]');
        let userTasks = JSON.parse(localStorage.getItem('jarvis_tasks') || '[]');
        let chatHistory = JSON.parse(localStorage.getItem('jarvis_history') || '[]');

        function applyTheme() {
            document.body.classList.remove('theme-emerald', 'theme-gold');
            if (themes[themeIdx]) document.body.classList.add(themes[themeIdx]);
            localStorage.setItem('jarvis_theme', themeIdx);
        }
        applyTheme();

        function cycleTheme() {
            themeIdx = (themeIdx + 1) % themes.length;
            applyTheme();
        }

        function updateBadges() {
            localStorage.setItem('jarvis_memory', JSON.stringify(userMemory));
            localStorage.setItem('jarvis_materials', JSON.stringify(userMaterials));
            localStorage.setItem('jarvis_tasks', JSON.stringify(userTasks));
            localStorage.setItem('jarvis_mode', workMode);

            document.getElementById('memCount').innerText = "Notizen · " + userMemory.length;
            document.getElementById('matCount').innerText = "Material · " + userMaterials.length;
            document.getElementById('taskCount').innerText = "Tasks · " + userTasks.length;

            const modeBtn = document.getElementById('modeBtn');
            if (workMode === 'ARBEIT') {
                modeBtn.innerText = "🏢 Arbeit";
                modeBtn.className = "pill work-active";
            } else {
                modeBtn.innerText = "🏠 Privat";
                modeBtn.className = "pill privat-active";
            }
        }
        updateBadges();

        function toggleMode() {
            workMode = (workMode === 'ARBEIT') ? 'PRIVAT' : 'ARBEIT';
            updateBadges();
            statusEl.innerText = workMode === 'ARBEIT'
                ? "Arbeitsmodus aktiv, Sir (Objektbetreuung & Kundenservice)."
                : "Privatmodus aktiv, Sir.";
        }

        function toggleLoop() {
            autoLoop = !autoLoop;
            const btn = document.getElementById('loopBtn');
            btn.innerText = autoLoop ? "Auto: An" : "Auto: Aus";
            btn.classList.toggle('auto-on', autoLoop);
        }

        function deleteItem(type, idx) {
            if (type === 'memory') userMemory.splice(idx, 1);
            if (type === 'materials') userMaterials.splice(idx, 1);
            if (type === 'tasks') userTasks.splice(idx, 1);
            updateBadges();
            showList(type);
        }

        function showList(type) {
            let list = userMemory;
            let title = "Objekt-Codes & Notizen";
            if (type === 'materials') { list = userMaterials; title = "Material- & Einkaufsliste"; }
            if (type === 'tasks') { list = userTasks; title = "Aufgabenliste (Tasks)"; }

            if (list.length === 0) {
                statusEl.innerText = `Ihre Liste "${title}" ist aktuell leer, Sir.`;
                return;
            }
            statusEl.innerHTML = `<div style='width:100%;'><div style='margin-bottom:10px;font-weight:700;color:var(--accent);'>${title}</div>` +
                list.map((m, i) => `<div class="list-card-item"><span>${i+1}. ${m}</span><button class="check-btn" onclick="deleteItem('${type}', ${i})">✓</button></div>`).join("") +
                "</div>";
        }

        function saveParking() {
            if (!navigator.geolocation) {
                statusEl.innerText = "GPS wird auf diesem Gerät nicht unterstützt, Sir.";
                return;
            }
            statusEl.innerText = "Ermittle genaue GPS-Position des Fahrzeugs...";
            navigator.geolocation.getCurrentPosition(pos => {
                const lat = pos.coords.latitude;
                const lng = pos.coords.longitude;
                const time = new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
                localStorage.setItem('jarvis_parking', JSON.stringify({lat, lng, time}));
                statusEl.innerText = `Parkplatz um ${time} Uhr gespeichert, Sir.`;
            }, () => {
                statusEl.innerText = "Standortzugriff verweigert, Sir.";
            });
        }

        function findParking() {
            const p = JSON.parse(localStorage.getItem('jarvis_parking') || 'null');
            if (!p) {
                statusEl.innerText = "Es ist aktuell kein Parkplatz gespeichert, Sir.";
                return;
            }
            const url = `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}&travelmode=walking`;
            statusEl.innerHTML = `<div>Fahrzeug wurde um ${p.time} Uhr hier geparkt, Sir.</div><div class="btn-row"><a href="${url}" class="primary-action">Route zum Auto starten</a></div>`;
            setTimeout(() => { window.location.href = url; }, 700);
        }

        function setBars(level) {
            bars.forEach((bar, i) => {
                const factor = Math.sin((i + 1) * 0.7) * 0.5 + 0.7;
                const h = Math.max(5, Math.min(20, level * factor));
                bar.style.height = h + 'px';
            });
        }

        function setState(state) {
            document.body.classList.remove('listening', 'thinking', 'speaking');
            orbCore.style.transform = '';
            setBars(5);
            if (state === 'listening') { document.body.classList.add('listening'); stateLabel.innerText = "Hört zu"; }
            else if (state === 'thinking') { document.body.classList.add('thinking'); stateLabel.innerText = "Analysiert"; }
            else if (state === 'speaking') { document.body.classList.add('speaking'); stateLabel.innerText = "Spricht"; }
            else { stateLabel.innerText = "Bereit"; }
        }

        function unlockAudio() {
            player.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";
            player.play().catch(() => {});
        }

        player.onplay = () => setState('speaking');
        player.onended = () => {
            setState(null);
            if (autoLoop) {
                setTimeout(() => { if (!isRecording) toggleRecord(); }, 450);
            }
        };

        function stopRecording() {
            if (!isRecording) return;
            isRecording = false;
            if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
            if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
            if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
        }

        async function toggleRecord() {
            unlockAudio();
            if (isRecording) { stopRecording(); return; }

            try {
                activeStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                audioChunks = [];
                let options = {};
                if (MediaRecorder.isTypeSupported('audio/webm')) options = { mimeType: 'audio/webm' };
                else if (MediaRecorder.isTypeSupported('audio/mp4')) options = { mimeType: 'audio/mp4' };

                mediaRecorder = new MediaRecorder(activeStream, options);
                mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) audioChunks.push(e.data); };

                mediaRecorder.onstop = async () => {
                    activeStream.getTracks().forEach(t => t.stop());
                    const mimeType = mediaRecorder.mimeType || 'audio/webm';
                    const blob = new Blob(audioChunks, { type: mimeType });
                    if (blob.size < 1000) {
                        setState(null);
                        statusEl.innerText = "Nichts gehört, Sir.";
                        return;
                    }
                    await sendAudio(blob, mimeType);
                };

                mediaRecorder.start();
                isRecording = true;
                setState('listening');
                statusEl.innerText = "Ich höre zu, Sir...";
                hintEl.innerText = "Sprechen Sie jetzt...";

                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const source = audioCtx.createMediaStreamSource(activeStream);
                const analyser = audioCtx.createAnalyser();
                analyser.fftSize = 512;
                source.connect(analyser);
                const dataArray = new Uint8Array(analyser.frequencyBinCount);

                let hasSpoken = false;
                const startTime = Date.now();

                function monitorVolume() {
                    if (!isRecording) return;
                    analyser.getByteFrequencyData(dataArray);
                    let sum = 0;
                    for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
                    const avg = sum / dataArray.length;

                    const scale = 1 + Math.min(avg / 220, 0.14);
                    orbCore.style.transform = `scale(${scale.toFixed(2)})`;
                    setBars(5 + avg * 0.6);

                    if (avg > 14) {
                        hasSpoken = true;
                        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
                    } else if (hasSpoken && !silenceTimer) {
                        silenceTimer = setTimeout(() => stopRecording(), 1500);
                    } else if (!hasSpoken && (Date.now() - startTime > 6500)) {
                        stopRecording();
                    }
                    animFrame = requestAnimationFrame(monitorVolume);
                }
                monitorVolume();
            } catch (err) {
                setState(null);
                statusEl.innerText = "Mikrofon-Zugriff erforderlich, Sir.";
            }
        }

        async function sendAudio(blob, mimeType) {
            setState('thinking');
            statusEl.innerText = "Verarbeite Anfrage, Sir...";
            const reader = new FileReader();
            reader.readAsDataURL(blob);
            reader.onloadend = async () => {
                const base64Audio = reader.result.split(',')[1];
                await callBackend({ audio: base64Audio, mime_type: mimeType });
            };
        }

        function handleImage(event) {
            const file = event.target.files[0];
            if (!file) return;
            unlockAudio();
            setState('thinking');
            statusEl.innerText = "Analysiere Bild mit JARVIS Vision, Sir...";

            const note = document.getElementById('msg').value.trim();
            document.getElementById('msg').value = '';

            const reader = new FileReader();
            reader.onload = function(e) {
                const img = new Image();
                img.onload = async function() {
                    const canvas = document.createElement('canvas');
                    const maxW = 1024;
                    const scale = Math.min(1, maxW / img.width);
                    canvas.width = img.width * scale;
                    canvas.height = img.height * scale;
                    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
                    const b64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
                    await callBackend({
                        image: b64,
                        message: note || "Analysiere dieses Bild (Objektkontrolle, Rechnung, Brief oder Problem) und fasse es kurz zusammen."
                    });
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
            event.target.value = '';
        }

        function quickCmd(cmd) {
            unlockAudio();
            setState('thinking');
            statusEl.innerText = "Verarbeite Befehl, Sir...";
            callBackend({ message: cmd });
        }

        async function sendText() {
            unlockAudio();
            const input = document.getElementById('msg');
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            setState('thinking');
            statusEl.innerText = "Verarbeite Befehl, Sir...";
            await callBackend({ message: text });
        }

        async function callBackend(payload) {
            payload.mode = workMode;
            payload.memory = userMemory;
            payload.materials = userMaterials;
            payload.tasks = userTasks;
            payload.history = chatHistory.slice(-8);
            payload.local_time = new Date().toISOString();
            payload.local_time_str = new Date().toLocaleString('de-DE');

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                setState(null);
                hintEl.innerText = "Tippen zum Sprechen • Kamera für Objekte & Briefe";

                if (data.error) {
                    statusEl.innerText = data.error;
                    return;
                }

                if (data.new_memory) { userMemory.push(data.new_memory.trim()); }
                if (data.delete_memory) {
                    const t = data.delete_memory.toLowerCase();
                    userMemory = userMemory.filter(x => !x.toLowerCase().includes(t));
                }
                if (data.new_material) { userMaterials.push(data.new_material.trim()); }
                if (data.delete_material) {
                    const t = data.delete_material.toLowerCase();
                    userMaterials = userMaterials.filter(x => !x.toLowerCase().includes(t));
                }
                if (data.new_task) { userTasks.push(data.new_task.trim()); }
                if (data.delete_task) {
                    const t = data.delete_task.toLowerCase();
                    userTasks = userTasks.filter(x => !x.toLowerCase().includes(t));
                }
                updateBadges();

                if (data.user_said) chatHistory.push({ role: "user", text: data.user_said });
                chatHistory.push({ role: "jarvis", text: data.reply });
                localStorage.setItem('jarvis_history', JSON.stringify(chatHistory.slice(-12)));

                statusEl.innerHTML = "";
                const textDiv = document.createElement('div');
                textDiv.innerText = data.reply;
                statusEl.appendChild(textDiv);

                const btnRow = document.createElement('div');
                btnRow.className = "btn-row";

                if (data.copy_text && data.copy_text.trim() !== "") {
                    const cBtn = document.createElement('button');
                    cBtn.className = "secondary-action";
                    cBtn.innerText = "📋 Kopieren";
                    cBtn.onclick = () => {
                        navigator.clipboard.writeText(data.copy_text);
                        cBtn.innerText = "✓ Kopiert";
                    };
                    btnRow.appendChild(cBtn);
                }

                if (data.action_url) {
                    const aBtn = document.createElement('a');
                    aBtn.href = data.action_url;
                    aBtn.className = "primary-action";
                    aBtn.innerText = data.action_label || "Öffnen";
                    if (data.copy_text) {
                        aBtn.onclick = () => { navigator.clipboard.writeText(data.copy_text).catch(()=>{}); };
                    }
                    btnRow.appendChild(aBtn);
                    if (!data.copy_text) {
                        setTimeout(() => { window.location.href = data.action_url; }, 750);
                    }
                }

                if (btnRow.children.length > 0) statusEl.appendChild(btnRow);

                if (data.audio) {
                    player.src = "data:audio/mp3;base64," + data.audio;
                    player.play().catch(() => {});
                }
            } catch (err) {
                setState(null);
                statusEl.innerText = "Verbindungsfehler, Sir.";
            }
        }
    </script>
</body>
</html>
"""

def call_google_bridge(payload):
    bridge_url = os.environ.get("GOOGLE_BRIDGE_URL", "").strip()
    if not bridge_url:
        return {"status": "skipped"}
    try:
        req = urllib.request.Request(
            bridge_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status": "error", "message": str(e)}

PLANNER_PROMPT = """Du bist das Routing-System von J.A.R.V.I.S. (Kundenbetreuer Gebäudereinigung & Privat-Assistent).
Analysiere die Anfrage (Audio, Bild oder Text) und entscheide, ob Google-Dienste benötigt werden.
Aktuelle ISO-Zeit: {iso_time} (Lokal: {local_time})

Verfügbare Google-Aktionen (tool_actions Liste):
- "get_calendar": Termine, Objektbesichtigungen, Kalender oder Briefing abrufen
- "add_calendar": Termin eintragen (benötigt start_iso YYYY-MM-DDTHH:MM:SS, title, duration_minutes, location)
- "get_emails": Ungelesene E-Mails oder Briefing abrufen
- "send_email": E-Mail senden (benötigt to, subject, body)
- "find_contact": Kontakt nach Namen suchen (für WhatsApp, Anruf oder E-Mail)

Antworte NUR als JSON:
{{
  "user_said": "Kurze Zusammenfassung was Sir gesagt/gezeigt hat",
  "tool_actions": [],
  "params": {{
    "contact_name": "",
    "title": "",
    "start_iso": "",
    "duration_minutes": 60,
    "location": "",
    "to": "",
    "subject": "",
    "body": ""
  }}
}}
"""

FINAL_PROMPT = """Du bist J.A.R.V.I.S., der hochprofessionelle KI-Assistent von Sir (Kundenbetreuer in einer Gebäudereinigungsfirma in Deutschland).
Aktueller Modus: {mode}
Antworte IMMER auf perfektem, professionellem Deutsch, höflich, präzise (maximal 2-3 Sätze, ohne Sternchen oder Markdown) und nenne den Nutzer 'Sir'.

FÄHIGKEITEN & REGELN:
1. KUNDENBETREUUNG & OBJEKTE:
   - Berechne Flächenleistungen (m² / Stunden / Monat), formuliere professionelle Kunden-E-Mails oder Reklamationsberichte für Reinigungskräfte.
   - Wenn ein Bild gesendet wurde (z.B. Verschmutzung, Reklamation, Kassenbon, Behördenbrief): Analysiere es präzise. Bei Reklamationen formuliere einen fertigen Berichtstext in 'copy_text'.
2. WHATSAPP & ANRUFE (OHNE FEHLER):
   - Prüfe ZUERST im Gedächtnis (Notizen) UND in den Google-Kontakten nach der Telefonnummer.
   - Nummer gefunden: Formatiere international ohne '+' oder Leerzeichen (z.B. 0176 123456 -> 49176123456) und setze action_url auf: "https://wa.me/49176123456?text=URL_ENCODED_TEXT" (oder "tel:+49176123456" für Anruf).
   - KEINE Nummer gefunden: Öffne NIEMALS "https://wa.me/" leer! Setze action_url auf "https://api.whatsapp.com/send?text=URL_ENCODED_TEXT" (falls Text vorhanden) oder lasse action_url leer und frage Sir nach der Nummer zum Speichern.
3. SOCIAL MEDIA POSTS (Instagram, TikTok, LinkedIn, Facebook):
   - Wenn Sir einen Post erstellen möchte: Schreibe den fertigen Post inkl. Hashtags in 'copy_text', setze action_label auf "App öffnen & Posten" und action_url auf die passende Plattform ("https://www.instagram.com/", "https://www.tiktok.com/", "https://www.linkedin.com/", "https://www.facebook.com/").
4. WEITERE APPS:
   - Google Maps: "https://www.google.com/maps/search/?api=1&query=URL_ENCODED"
   - YouTube: "https://www.youtube.com/results?search_query=URL_ENCODED"
   - Spotify: "https://open.spotify.com/search/URL_ENCODED"
5. LISTEN-VERWALTUNG (nur ausfüllen wenn Sir etwas speichern oder löschen möchte):
   - 'new_memory' / 'delete_memory': Objekt-Codes, Schlüsselinfos, Telefonnummern, Kundeninfos
   - 'new_material' / 'delete_material': Reinigungsmittel, Papier, Müllbeutel oder Einkaufsliste
   - 'new_task' / 'delete_task': Aufgaben / To-Dos

Antworte ausschließlich als JSON:
{{
  "reply": "Deine gesprochene Antwort an Sir",
  "copy_text": "",
  "new_memory": "",
  "delete_memory": "",
  "new_material": "",
  "delete_material": "",
  "new_task": "",
  "delete_task": "",
  "action_url": "",
  "action_label": ""
}}
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

@app.route("/manifest.json")
def manifest():
    return jsonify(MANIFEST_JSON)

@app.route("/icon.svg")
def icon():
    return Response(ICON_SVG, mimetype="image/svg+xml")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY fehlt in Render!"}), 500

        data = request.json or {}
        mode = data.get("mode", "ARBEIT")
        memory = data.get("memory", [])
        materials = data.get("materials", [])
        tasks = data.get("tasks", [])
        history = data.get("history", [])
        iso_time = data.get("local_time", datetime.now().isoformat())
        local_time_str = data.get("local_time_str", datetime.now().strftime("%d.%m.%Y %H:%M"))

        client = genai.Client(api_key=api_key)

        planner_sys = PLANNER_PROMPT.format(iso_time=iso_time, local_time=local_time_str)
        step1_contents = []
        if "image" in data:
            img_bytes = base64.b64decode(data["image"])
            step1_contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
            step1_contents.append(data.get("message", "Analysiere dieses Bild."))
        elif "audio" in data:
            audio_bytes = base64.b64decode(data["audio"])
            mime_type = data.get("mime_type", "audio/webm").split(";")[0]
            step1_contents.append(types.Part.from_bytes(data=audio_bytes, mime_type=mime_type))
            step1_contents.append("Analysiere diese deutsche Sprachnachricht.")
        else:
            step1_contents.append(data.get("message", ""))

        step1_res = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=step1_contents,
            config=types.GenerateContentConfig(
                system_instruction=planner_sys,
                response_mime_type="application/json"
            )
        )
        plan = json.loads(step1_res.text)
        user_said = plan.get("user_said", data.get("message", ""))
        tool_actions = plan.get("tool_actions", [])
        params = plan.get("params", {})

        tool_results = {}
        for act in tool_actions:
            if act == "get_calendar":
                tool_results["calendar"] = call_google_bridge({"action": "get_calendar"})
            elif act == "add_calendar":
                tool_results["calendar_add"] = call_google_bridge({
                    "action": "add_calendar",
                    "title": params.get("title", "Termin"),
                    "start_iso": params.get("start_iso"),
                    "duration_minutes": params.get("duration_minutes", 60),
                    "location": params.get("location", "")
                })
            elif act == "get_emails":
                tool_results["emails"] = call_google_bridge({"action": "get_emails"})
            elif act == "send_email":
                tool_results["email_send"] = call_google_bridge({
                    "action": "send_email",
                    "to": params.get("to"),
                    "subject": params.get("subject", "Nachricht von JARVIS"),
                    "body": params.get("body", "")
                })
            elif act == "find_contact":
                tool_results["contacts"] = call_google_bridge({
                    "action": "find_contact",
                    "name": params.get("contact_name", "")
                })

        final_contents = []
        if "image" in data:
            final_contents.append(types.Part.from_bytes(data=base64.b64decode(data["image"]), mime_type="image/jpeg"))

        final_context = (
            f"Aktuelle Zeit: {local_time_str}\n"
            f"Nutzer-Anfrage: {user_said}\n"
            f"Objekt-Codes & Notizen: {json.dumps(memory, ensure_ascii=False)}\n"
            f"Material- & Einkaufsliste: {json.dumps(materials, ensure_ascii=False)}\n"
            f"Aufgabenliste (Tasks): {json.dumps(tasks, ensure_ascii=False)}\n"
            f"Gesprächsverlauf: {json.dumps(history, ensure_ascii=False)}\n"
            f"Google-Dienste Ergebnisse: {json.dumps(tool_results, ensure_ascii=False)}"
        )
        final_contents.append(final_context)

        step2_res = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=final_contents,
            config=types.GenerateContentConfig(
                system_instruction=FINAL_PROMPT.format(mode=mode),
                response_mime_type="application/json"
            )
        )

        result = json.loads(step2_res.text)
        reply = result.get("reply", "Zu Befehl, Sir.")
        audio_b64 = asyncio.run(make_voice(reply))

        return jsonify({
            "user_said": user_said,
            "reply": reply,
            "copy_text": result.get("copy_text", ""),
            "new_memory": result.get("new_memory", ""),
            "delete_memory": result.get("delete_memory", ""),
            "new_material": result.get("new_material", ""),
            "delete_material": result.get("delete_material", ""),
            "new_task": result.get("new_task", ""),
            "delete_task": result.get("delete_task", ""),
            "action_url": result.get("action_url", ""),
            "action_label": result.get("action_label", ""),
            "audio": audio_b64
        })
    except Exception as e:
        return jsonify({"error": f"Fehler: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
