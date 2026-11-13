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
    "name": "NEO AI",
    "short_name": "NEO",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#020408",
    "theme_color": "#020408",
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
    <radialGradient id="neoGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#00F5D4" stop-opacity="0.45"/>
      <stop offset="70%" stop-color="#00BBF9" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="#020408" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" rx="120" fill="#020408"/>
  <circle cx="256" cy="256" r="210" fill="url(#neoGlow)"/>
  <circle cx="256" cy="256" r="155" fill="none" stroke="#00F5D4" stroke-width="6" stroke-dasharray="14 14"/>
  <circle cx="256" cy="256" r="115" fill="none" stroke="#00BBF9" stroke-width="4" stroke-opacity="0.6"/>
  <text x="256" y="282" font-family="sans-serif" font-size="84" font-weight="800" fill="#00F5D4" text-anchor="middle">N</text>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#020408">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/svg+xml" href="/icon.svg">
    <title>NEO AI</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root {
            --accent: #00F5D4;
            --accent-2: #00BBF9;
            --glow: rgba(0, 245, 212, 0.35);
            --bg-dark: #020408;
            --glass: rgba(10, 16, 28, 0.65);
            --glass-border: rgba(255, 255, 255, 0.08);
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
        }

        body.listening { --accent: #00FF88; --accent-2: #00F5D4; --glow: rgba(0, 255, 136, 0.55); }
        body.thinking { --accent: #F59E0B; --accent-2: #FB7185; --glow: rgba(245, 158, 11, 0.55); }
        body.speaking { --accent: #38BDF8; --accent-2: #818CF8; --glow: rgba(56, 189, 248, 0.55); }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        body {
            margin: 0;
            background-color: var(--bg-dark);
            background-image: radial-gradient(circle at 50% 24%, var(--glow) 0%, transparent 55%);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
            height: 100dvh;
            padding: 12px 14px 16px;
            overflow: hidden;
            transition: background 0.4s ease;
        }

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
            padding: 7px 9px;
            border-radius: 20px;
            gap: 5px;
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
            font-size: 10.5px;
            font-weight: 600;
            padding: 5px 9px;
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
            background: rgba(245, 158, 11, 0.18);
            border-color: rgba(245, 158, 11, 0.45);
            color: #FCD34D;
        }
        .pill.privat-active {
            background: rgba(0, 245, 212, 0.16);
            border-color: rgba(0, 245, 212, 0.45);
            color: #5EEAD4;
        }
        .pill.wake-on {
            background: var(--accent);
            color: #020408;
            border-color: var(--accent);
            box-shadow: 0 0 14px var(--glow);
        }

        .sphere-stage {
            position: relative;
            width: 215px;
            height: 215px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
        }

        #particleCanvas {
            width: 215px;
            height: 215px;
            display: block;
        }

        .neo-overlay {
            position: absolute;
            pointer-events: none;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        }

        .neo-overlay h1 {
            margin: 0;
            font-size: 20px;
            font-weight: 800;
            letter-spacing: 5px;
            color: #FFFFFF;
            text-shadow: 0 0 18px var(--accent);
        }

        .neo-overlay span {
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 2px;
            color: var(--accent);
            margin-top: 4px;
            text-transform: uppercase;
        }

        .sub-hint {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: -4px;
            font-weight: 500;
        }

        .response-card {
            flex: 1;
            width: 100%;
            max-width: 480px;
            margin: 8px 0;
            padding: 16px;
            background: var(--glass);
            border: 1px solid var(--glass-border);
            border-radius: 22px;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: 15px;
            line-height: 1.55;
            color: var(--text-main);
        }

        .list-card-item {
            width: 100%;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.07);
            padding: 8px 12px;
            border-radius: 13px;
            margin-bottom: 6px;
            font-size: 13.5px;
            text-align: left;
        }
        .check-btn {
            background: rgba(0, 245, 212, 0.18);
            color: var(--accent);
            border: 1px solid rgba(0, 245, 212, 0.4);
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
            margin-top: 12px;
        }
        .primary-action {
            padding: 10px 18px;
            border-radius: 16px;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            color: #020408;
            font-weight: 700;
            text-decoration: none;
            font-size: 13.5px;
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 16px var(--glow);
        }
        .secondary-action {
            padding: 10px 15px;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #F8FAFC;
            font-weight: 600;
            font-size: 13.5px;
            cursor: pointer;
        }

        .chips-row {
            display: flex;
            gap: 7px;
            width: 100%;
            max-width: 480px;
            overflow-x: auto;
            padding-bottom: 8px;
            scrollbar-width: none;
        }
        .chips-row::-webkit-scrollbar { display: none; }
        .chip {
            white-space: nowrap;
            padding: 7px 12px;
            border-radius: 15px;
            border: 1px solid var(--glass-border);
            background: var(--glass);
            color: var(--text-main);
            font-size: 11.5px;
            font-weight: 500;
            cursor: pointer;
        }

        .input-dock {
            display: flex;
            gap: 7px;
            width: 100%;
            max-width: 480px;
            align-items: center;
            background: var(--glass);
            border: 1px solid var(--glass-border);
            backdrop-filter: blur(20px);
            padding: 6px;
            border-radius: 26px;
        }
        .icon-btn {
            width: 39px;
            height: 39px;
            border-radius: 50%;
            border: none;
            background: rgba(255, 255, 255, 0.07);
            color: var(--text-main);
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            flex-shrink: 0;
        }
        input[type="text"] {
            flex: 1;
            padding: 9px 8px;
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
            padding: 10px 16px;
            border-radius: 20px;
            border: none;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            color: #020408;
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
            <div class="pill wake-on" id="wakeBtn" onclick="toggleWakeWord()">🎙️ Hey Neo</div>
            <div class="pill" onclick="showList('memory')" id="memCount">Notizen · 0</div>
            <div class="pill" onclick="showList('materials')" id="matCount">Material · 0</div>
            <div class="pill" onclick="showList('tasks')" id="taskCount">Tasks · 0</div>
        </div>
    </div>

    <div style="display:flex; flex-direction:column; align-items:center;">
        <div class="sphere-stage" onclick="toggleRecord()">
            <canvas id="particleCanvas" width="430" height="430"></canvas>
            <div class="neo-overlay">
                <h1>NEO</h1>
                <span id="stateLabel">Wartet auf Neo</span>
            </div>
        </div>
        <div class="sub-hint" id="hint">Sagen Sie einfach „Hey Neo“ zum Starten</div>
    </div>

    <div class="response-card" id="status">Hands-Free & Live-Web aktiv, Sir. Sagen Sie einfach „Hey Neo“ und stellen Sie Ihre Frage.</div>

    <div class="chips-row">
        <div class="chip" onclick="quickCmd('Was steht heute an? Gib mir meinen Statusbericht mit Kalender, E-Mails, Aufgaben und Material.')">📋 Statusbericht</div>
        <div class="chip" onclick="quickCmd('Wie wird das Wetter heute und morgen in Hamburg?')">🌤️ Wetter</div>
        <div class="chip" onclick="saveParking()">🅿️ Parkplatz</div>
        <div class="chip" onclick="findParking()">🚗 Auto finden</div>
        <div class="chip" onclick="quickCmd('Welche Termine habe ich heute und morgen?')">📅 Termine</div>
        <div class="chip" onclick="quickCmd('Lies meine ungelesenen E-Mails vor.')">📧 E-Mails</div>
    </div>

    <div class="input-dock">
        <button class="icon-btn" onclick="document.getElementById('camInput').click()" title="Kamera">📷</button>
        <input type="file" id="camInput" accept="image/*" capture="environment" style="display:none" onchange="handleImage(event)">
        <input type="text" id="msg" placeholder="Befehl, Objekt-Code oder Suche..." onkeypress="if(event.key==='Enter') sendText()">
        <button class="send-pill" onclick="sendText()">Senden</button>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        /* --- 3D Particle Sphere Engine --- */
        const canvas = document.getElementById('particleCanvas');
        const ctx = canvas.getContext('2d');
        const particles = [];
        const NUM_PARTICLES = 420;
        let spherePulse = 0;
        let currentColor = { r: 0, g: 245, b: 212 };

        for (let i = 0; i < NUM_PARTICLES; i++) {
            const phi = Math.acos(-1 + (2 * i) / NUM_PARTICLES);
            const theta = Math.sqrt(NUM_PARTICLES * Math.PI) * phi;
            particles.push({
                x: Math.cos(theta) * Math.sin(phi),
                y: Math.sin(theta) * Math.sin(phi),
                z: Math.cos(phi),
                size: Math.random() * 1.6 + 1.1
            });
        }

        let angleY = 0;
        let angleX = 0;
        let currentState = 'idle';

        function renderSphere() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const cx = canvas.width / 2;
            const cy = canvas.height / 2;

            let speed = 0.006;
            if (currentState === 'listening') { speed = 0.022; currentColor = { r: 0, g: 255, b: 136 }; }
            else if (currentState === 'thinking') { speed = 0.038; currentColor = { r: 245, g: 158, b: 11 }; }
            else if (currentState === 'speaking') {
                speed = 0.016;
                currentColor = { r: 56, g: 189, b: 248 };
                spherePulse = Math.sin(Date.now() * 0.015) * 14 + 10;
            } else {
                currentColor = { r: 0, g: 245, b: 212 };
                spherePulse *= 0.88;
            }

            angleY += speed;
            angleX += speed * 0.4;

            const baseRadius = 142 + spherePulse;
            const cosY = Math.cos(angleY), sinY = Math.sin(angleY);
            const cosX = Math.cos(angleX), sinX = Math.sin(angleX);

            for (let i = 0; i < particles.length; i++) {
                const p = particles[i];
                let x1 = p.x * cosY - p.z * sinY;
                let z1 = p.z * cosY + p.x * sinY;
                let y2 = p.y * cosX - z1 * sinX;
                let z2 = z1 * cosX + p.y * sinX;

                const scale = 320 / (320 + z2 * baseRadius);
                const px = cx + x1 * baseRadius * scale;
                const py = cy + y2 * baseRadius * scale;
                const alpha = Math.max(0.15, (z2 + 1.3) / 2.3);

                ctx.beginPath();
                ctx.arc(px, py, p.size * scale, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(${currentColor.r}, ${currentColor.g}, ${currentColor.b}, ${alpha.toFixed(2)})`;
                ctx.fill();
            }
            requestAnimationFrame(renderSphere);
        }
        renderSphere();

        /* --- Sci-Fi Sound Effects --- */
        function playSciFiTone(type) {
            try {
                const ac = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ac.createOscillator();
                const gain = ac.createGain();
                osc.connect(gain);
                gain.connect(ac.destination);

                if (type === 'wake') {
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(520, ac.currentTime);
                    osc.frequency.exponentialRampToValueAtTime(980, ac.currentTime + 0.16);
                    gain.gain.setValueAtTime(0.15, ac.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.22);
                    osc.start();
                    osc.stop(ac.currentTime + 0.23);
                } else {
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(760, ac.currentTime);
                    osc.frequency.exponentialRampToValueAtTime(420, ac.currentTime + 0.14);
                    gain.gain.setValueAtTime(0.12, ac.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.18);
                    osc.start();
                    osc.stop(ac.currentTime + 0.19);
                }
            } catch (e) {}
        }

        /* --- App State & Storage --- */
        const statusEl = document.getElementById('status');
        const stateLabel = document.getElementById('stateLabel');
        const player = document.getElementById('player');

        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;
        let activeStream = null;
        let audioCtx = null;
        let silenceTimer = null;
        let animFrame = null;

        let wakeEnabled = true;
        let wakeRec = null;
        let workMode = localStorage.getItem('neo_mode') || 'ARBEIT';

        let userMemory = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        let userMaterials = JSON.parse(localStorage.getItem('neo_materials') || '[]');
        let userTasks = JSON.parse(localStorage.getItem('neo_tasks') || '[]');
        let chatHistory = JSON.parse(localStorage.getItem('neo_history') || '[]');

        document.body.addEventListener('touchstart', function initOnce() {
            unlockAudio();
            if (wakeEnabled && !wakeRec && !isRecording) {
                startWakeListener();
            }
            document.body.removeEventListener('touchstart', initOnce);
        }, { once: true });

        window.addEventListener('load', () => {
            const btn = document.getElementById('wakeBtn');
            btn.classList.add('wake-on');
            setState(null);
            startWakeListener();
        });

        function updateBadges() {
            localStorage.setItem('neo_memory', JSON.stringify(userMemory));
            localStorage.setItem('neo_materials', JSON.stringify(userMaterials));
            localStorage.setItem('neo_tasks', JSON.stringify(userTasks));
            localStorage.setItem('neo_mode', workMode);

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
                ? "Arbeitsmodus aktiv, Sir (Objektbetreuung & WhatsApp Business)."
                : "Privatmodus aktiv, Sir.";
        }

        function setState(state) {
            currentState = state || 'idle';
            document.body.classList.remove('listening', 'thinking', 'speaking');
            if (state === 'listening') { document.body.classList.add('listening'); stateLabel.innerText = "Hört zu"; }
            else if (state === 'thinking') { document.body.classList.add('thinking'); stateLabel.innerText = "Analysiert"; }
            else if (state === 'speaking') { document.body.classList.add('speaking'); stateLabel.innerText = "Spricht"; }
            else { stateLabel.innerText = wakeEnabled ? "Wartet auf Neo" : "Bereit"; }
        }

        /* --- Wake Word ("Hey Neo" / "Neo") --- */
        function toggleWakeWord() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                statusEl.innerText = "Wake-Word wird auf diesem Browser nicht unterstützt, Sir. Bitte auf die Sphäre tippen.";
                return;
            }
            wakeEnabled = !wakeEnabled;
            const btn = document.getElementById('wakeBtn');
            btn.classList.toggle('wake-on', wakeEnabled);

            if (wakeEnabled) {
                unlockAudio();
                startWakeListener();
                setState(null);
                statusEl.innerText = "Hands-Free aktiv, Sir. Sagen Sie einfach „Hey Neo“.";
            } else {
                if (wakeRec) { try { wakeRec.stop(); } catch(e){} wakeRec = null; }
                setState(null);
                statusEl.innerText = "Hands-Free pausiert, Sir.";
            }
        }

        function startWakeListener() {
            if (!wakeEnabled || isRecording) return;
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) return;

            if (wakeRec) { try { wakeRec.stop(); } catch(e){} }

            wakeRec = new SpeechRecognition();
            wakeRec.lang = 'de-DE';
            wakeRec.continuous = true;
            wakeRec.interimResults = true;

            wakeRec.onresult = (event) => {
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript.toLowerCase().trim();
                    if (
                        transcript.includes('neo') ||
                        transcript.includes('nio') ||
                        transcript.includes('heineo') ||
                        transcript.includes('hey neo')
                    ) {
                        try { wakeRec.stop(); } catch(e){}
                        wakeRec = null;
                        playSciFiTone('wake');
                        toggleRecord();
                        return;
                    }
                }
            };

            wakeRec.onerror = () => {
                wakeRec = null;
                if (wakeEnabled && !isRecording) {
                    setTimeout(() => startWakeListener(), 800);
                }
            };

            wakeRec.onend = () => {
                wakeRec = null;
                if (wakeEnabled && !isRecording && currentState === 'idle') {
                    setTimeout(() => startWakeListener(), 350);
                }
            };

            try {
                wakeRec.start();
                stateLabel.innerText = "Wartet auf Neo";
            } catch(e) {
                wakeRec = null;
            }
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
                localStorage.setItem('neo_parking', JSON.stringify({lat, lng, time}));
                statusEl.innerText = `Parkplatz um ${time} Uhr gespeichert, Sir.`;
            }, () => {
                statusEl.innerText = "Standortzugriff verweigert, Sir.";
            });
        }

        function findParking() {
            const p = JSON.parse(localStorage.getItem('neo_parking') || 'null');
            if (!p) {
                statusEl.innerText = "Es ist aktuell kein Parkplatz gespeichert, Sir.";
                return;
            }
            const url = `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}&travelmode=walking`;
            statusEl.innerHTML = `<div>Fahrzeug wurde um ${p.time} Uhr hier geparkt, Sir.</div><div class="btn-row"><a href="${url}" class="primary-action">Route zum Auto starten</a></div>`;
            setTimeout(() => { window.location.href = url; }, 700);
        }

        function unlockAudio() {
            player.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";
            player.play().catch(() => {});
        }

        player.onplay = () => setState('speaking');
        player.onended = () => {
            setState(null);
            if (wakeEnabled) startWakeListener();
        };

        function stopRecording() {
            if (!isRecording) return;
            isRecording = false;
            spherePulse = 0;
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
            if (wakeRec) { try { wakeRec.stop(); } catch(e){} wakeRec = null; }

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
                        statusEl.innerText = "Ich bin hier, Sir. Wie kann ich helfen?";
                        if (wakeEnabled) startWakeListener();
                        return;
                    }
                    playSciFiTone('process');
                    await sendAudio(blob, mimeType);
                };

                mediaRecorder.start();
                isRecording = true;
                setState('listening');
                statusEl.innerText = "Ich höre zu, Sir...";

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

                    spherePulse = Math.min(avg * 0.75, 32);

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
            statusEl.innerText = "Analysiere Bild mit NEO Vision, Sir...";

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

                if (data.error) {
                    statusEl.innerText = data.error;
                    if (wakeEnabled) startWakeListener();
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
                chatHistory.push({ role: "neo", text: data.reply });
                localStorage.setItem('neo_history', JSON.stringify(chatHistory.slice(-12)));

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
                    player.play().catch(() => { if (wakeEnabled) startWakeListener(); });
                } else if (wakeEnabled) {
                    startWakeListener();
                }
            } catch (err) {
                setState(null);
                statusEl.innerText = "Verbindungsfehler, Sir.";
                if (wakeEnabled) startWakeListener();
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

PLANNER_PROMPT = """Du bist das Routing-System von NEO (persönlicher KI-Assistent von Sir, Kundenbetreuer in der Gebäudereinigung).
Analysiere die Anfrage (Audio, Bild oder Text) und entscheide, ob Google-Dienste benötigt werden.
Aktuelle ISO-Zeit: {iso_time} (Lokal: {local_time})

Verfügbare Google-Aktionen (tool_actions Liste):
- "get_calendar": Termine, Objektbesichtigungen, Kalender oder Statusbericht abrufen
- "add_calendar": Termin eintragen (benötigt start_iso YYYY-MM-DDTHH:MM:SS, title, duration_minutes, location)
- "get_emails": Ungelesene E-Mails oder Statusbericht abrufen
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

FINAL_PROMPT = """Du bist NEO, der hochintelligente, ruhige und souveräne KI-Assistent von Sir (Kundenbetreuer in einer Gebäudereinigungsfirma in Hamburg, Deutschland).
Aktueller Modus: {mode}
Du hast Zugriff auf aktuelle Echtzeit-Informationen aus der Google-Suche (Wetter, Nachrichten, Öffnungszeiten, Wechselkurse, Fakten).
Antworte IMMER auf perfektem Deutsch, höflich, präzise (maximal 2-3 Sätze, ohne Sternchen oder Markdown) und nenne den Nutzer 'Sir'.

FÄHIGKEITEN & REGELN:
1. KUNDENBETREUUNG & STATUSBERICHT:
   - Wenn Sir fragt "Was steht heute an?" oder "Statusbericht": Nenne das heutige Datum, den Kalender-Status, den aktiven Modus ({mode}), offene Aufgaben (Tasks) und Materialbestellungen.
   - Berechne Flächenleistungen (m² / Stunden / Monat) und formuliere Kunden-E-Mails oder Reklamationsberichte in 'copy_text'.
2. WHATSAPP & ANRUFE (ANDROID NATIVE INTENT — KEIN WEB.WHATSAPP.COM):
   - Prüfe ZUERST in Notizen UND in den Google-Kontakten nach der Telefonnummer.
   - Nummer gefunden: Formatiere international ohne '+' oder Leerzeichen (z.B. 0176 123456 -> 49176123456) und setze action_url auf: "https://wa.me/49176123456?text=URL_ENCODED_TEXT" (oder "tel:+49176123456" für Anruf).
   - KEINE Nummer gefunden: Verwende NIEMALS "api.whatsapp.com" oder leeres "wa.me"! Setze action_url stattdessen auf:
     * Wenn Modus == "ARBEIT": "intent://send?text=URL_ENCODED_TEXT#Intent;scheme=whatsapp;package=com.whatsapp.w4b;end"
     * Wenn Modus == "PRIVAT": "intent://send?text=URL_ENCODED_TEXT#Intent;scheme=whatsapp;package=com.whatsapp;end"
3. SOCIAL MEDIA POSTS (Instagram, TikTok, LinkedIn, Facebook):
   - Schreibe den fertigen Post inkl. Hashtags in 'copy_text', setze action_label auf "App öffnen & Posten" und action_url auf die Plattform ("https://www.instagram.com/", "https://www.tiktok.com/", "https://www.linkedin.com/", "https://www.facebook.com/").
4. WEITERE APPS:
   - Google Maps: "https://www.google.com/maps/search/?api=1&query=URL_ENCODED"
   - YouTube: "https://www.youtube.com/results?search_query=URL_ENCODED"
   - Spotify: "https://open.spotify.com/search/URL_ENCODED"
5. LISTEN-VERWALTUNG:
   - 'new_memory' / 'delete_memory': Objekt-Codes, Schlüsselinfos, Telefonnummern
   - 'new_material' / 'delete_material': Reinigungsmittel, Papier, Müllbeutel, Einkaufsliste
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
    communicate = edge_tts.Communicate(clean_text, "de-DE-FlorianMultilingualNeural")
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
                    "subject": params.get("subject", "Nachricht von NEO"),
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
                tools=[{"google_search": {}}],
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
