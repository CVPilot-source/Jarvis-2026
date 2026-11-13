import os
import json
import base64
import asyncio
import urllib.request
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, Response
from google import genai
from google.genai import types
import edge_tts

app = Flask(__name__)

MANIFEST_JSON = {
    "name": "NEO",
    "short_name": "NEO",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#000000",
    "theme_color": "#000000",
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
  <rect width="512" height="512" rx="120" fill="#000000"/>
  <circle cx="256" cy="256" r="160" fill="none" stroke="#00F5D4" stroke-width="6" stroke-dasharray="10 14"/>
  <circle cx="256" cy="256" r="120" fill="none" stroke="#00BBF9" stroke-width="3" stroke-opacity="0.7"/>
  <circle cx="256" cy="256" r="8" fill="#00F5D4"/>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#000000">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/svg+xml" href="/icon.svg">
    <title>NEO</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

        :root {
            --accent: #00F5D4;
            --text-main: #F8FAFC;
            --text-muted: rgba(248, 250, 252, 0.45);
        }

        body.listening { --accent: #00FF88; }
        body.thinking { --accent: #F59E0B; }
        body.speaking { --accent: #38BDF8; }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        body {
            margin: 0;
            background-color: #000000;
            color: var(--text-main);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
            height: 100dvh;
            padding: 20px 18px 24px;
            overflow: hidden;
        }

        .top-minimal {
            width: 100%;
            max-width: 440px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 5;
        }

        .status-dot-wrap {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 11px;
            letter-spacing: 2.5px;
            text-transform: uppercase;
            color: var(--text-muted);
            font-weight: 600;
        }

        .status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--accent);
            box-shadow: 0 0 10px var(--accent);
            transition: background 0.3s;
        }

        .mode-tag {
            font-size: 10.5px;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: var(--text-muted);
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 5px 11px;
            border-radius: 20px;
            cursor: pointer;
        }

        .hologram-center {
            position: relative;
            flex: 1;
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
        }

        #particleCanvas {
            width: 310px;
            height: 310px;
            max-width: 82vw;
            max-height: 82vw;
            display: block;
        }

        .caption-area {
            width: 100%;
            max-width: 420px;
            min-height: 76px;
            max-height: 150px;
            overflow-y: auto;
            text-align: center;
            font-size: 15px;
            font-weight: 300;
            line-height: 1.55;
            color: rgba(255, 255, 255, 0.88);
            padding: 0 10px;
            margin-bottom: 10px;
            z-index: 5;
        }

        .btn-row {
            display: flex;
            gap: 8px;
            justify-content: center;
            margin-top: 10px;
        }

        .action-pill {
            padding: 8px 16px;
            border-radius: 20px;
            background: rgba(0, 245, 212, 0.14);
            border: 1px solid var(--accent);
            color: var(--accent);
            font-size: 12.5px;
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
        }

        .bottom-controls {
            width: 100%;
            max-width: 440px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 5;
        }

        .circle-btn {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.75);
            font-size: 17px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
        }
        .circle-btn.active {
            border-color: var(--accent);
            color: var(--accent);
            box-shadow: 0 0 14px rgba(0, 245, 212, 0.25);
        }

        .drawer {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.88);
            backdrop-filter: blur(22px);
            -webkit-backdrop-filter: blur(22px);
            z-index: 20;
            display: none;
            flex-direction: column;
            justify-content: space-between;
            padding: 20px 18px 24px;
        }
        .drawer.open { display: flex; }

        .drawer-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .tabs {
            display: flex;
            gap: 8px;
            margin: 14px 0;
            overflow-x: auto;
        }
        .tab {
            padding: 7px 13px;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.06);
            color: #CBD5E1;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
        }
        .tab.active {
            background: var(--accent);
            color: #000000;
        }

        .drawer-body {
            flex: 1;
            overflow-y: auto;
            padding: 6px 0;
        }

        .list-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.05);
            padding: 11px 14px;
            border-radius: 14px;
            margin-bottom: 8px;
            font-size: 14px;
        }

        .check-btn {
            background: rgba(0, 245, 212, 0.18);
            color: var(--accent);
            border: none;
            border-radius: 10px;
            padding: 5px 10px;
            font-weight: 700;
            cursor: pointer;
        }

        .quick-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin-bottom: 14px;
        }
        .q-btn {
            padding: 11px;
            border-radius: 14px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: #F8FAFC;
            font-size: 12.5px;
            text-align: left;
            cursor: pointer;
        }

        .text-dock {
            display: flex;
            gap: 8px;
            background: rgba(255, 255, 255, 0.07);
            padding: 6px 8px;
            border-radius: 24px;
        }
        .text-dock input {
            flex: 1;
            background: transparent;
            border: none;
            color: white;
            font-size: 15px;
            padding: 8px;
            outline: none;
        }
        .text-dock button {
            background: var(--accent);
            color: #000000;
            border: none;
            border-radius: 18px;
            padding: 8px 16px;
            font-weight: 700;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="top-minimal">
        <div class="status-dot-wrap">
            <div class="status-dot"></div>
            <span id="stateLabel">NEO • BEREIT</span>
        </div>
        <div class="mode-tag" id="modeBtn" onclick="toggleMode()">ARBEIT</div>
    </div>

    <div class="hologram-center" onclick="toggleRecord()">
        <canvas id="particleCanvas" width="620" height="620"></canvas>
    </div>

    <div class="caption-area" id="status">Sagen Sie „Hey Neo“ oder berühren Sie die Sphäre.</div>

    <div class="bottom-controls">
        <button class="circle-btn active" id="wakeBtn" onclick="toggleWakeWord()" title="Hey Neo">🎙️</button>
        <button class="circle-btn" onclick="document.getElementById('camInput').click()" title="Kamera">📷</button>
        <button class="circle-btn" onclick="openDrawer()" title="Menü & Listen">☰</button>
        <input type="file" id="camInput" accept="image/*" capture="environment" style="display:none" onchange="handleImage(event)">
    </div>

    <div class="drawer" id="drawer">
        <div>
            <div class="drawer-header">
                <span style="font-weight:700; letter-spacing:2px; font-size:13px;">NEO SYSTEM</span>
                <button class="circle-btn" style="width:36px;height:36px;" onclick="closeDrawer()">✕</button>
            </div>
            <div class="tabs">
                <div class="tab active" id="tab-tools" onclick="switchTab('tools')">Aktionen</div>
                <div class="tab" id="tab-memory" onclick="switchTab('memory')">Notizen (<span id="c-mem">0</span>)</div>
                <div class="tab" id="tab-materials" onclick="switchTab('materials')">Material (<span id="c-mat">0</span>)</div>
                <div class="tab" id="tab-tasks" onclick="switchTab('tasks')">Tasks (<span id="c-task">0</span>)</div>
            </div>
        </div>

        <div class="drawer-body" id="drawerBody"></div>

        <div class="text-dock">
            <input type="text" id="msg" placeholder="Befehl oder Notiz schreiben..." onkeypress="if(event.key==='Enter'){closeDrawer();sendText();}">
            <button onclick="closeDrawer();sendText();">Send</button>
        </div>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        /* --- High-Density Organic 3D Particle Sphere --- */
        const canvas = document.getElementById('particleCanvas');
        const ctx = canvas.getContext('2d');
        const particles = [];
        const NUM_PARTICLES = 680;
        let audioEnergy = 0;
        let currentColor = { r: 0, g: 245, b: 212 };

        for (let i = 0; i < NUM_PARTICLES; i++) {
            const phi = Math.acos(-1 + (2 * i) / NUM_PARTICLES);
            const theta = Math.sqrt(NUM_PARTICLES * Math.PI) * phi;
            particles.push({
                bx: Math.cos(theta) * Math.sin(phi),
                by: Math.sin(theta) * Math.sin(phi),
                bz: Math.cos(phi),
                phase: Math.random() * Math.PI * 2,
                size: Math.random() * 1.5 + 0.9
            });
        }

        let rotY = 0;
        let rotX = 0;
        let currentState = 'idle';

        function renderSphere() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const cx = canvas.width / 2;
            const cy = canvas.height / 2;
            const t = Date.now() * 0.002;

            let speed = 0.0045;
            let waveAmp = 4;

            if (currentState === 'listening') {
                speed = 0.014;
                currentColor = { r: 0, g: 255, b: 145 };
                waveAmp = 6 + audioEnergy * 0.65;
            } else if (currentState === 'thinking') {
                speed = 0.032;
                currentColor = { r: 245, g: 165, b: 20 };
                waveAmp = 12;
            } else if (currentState === 'speaking') {
                speed = 0.012;
                currentColor = { r: 45, g: 212, b: 255 };
                waveAmp = 8 + Math.abs(Math.sin(t * 4.5)) * 18;
            } else {
                currentColor = { r: 0, g: 245, b: 212 };
                audioEnergy *= 0.85;
            }

            rotY += speed;
            rotX += speed * 0.35;

            const cosY = Math.cos(rotY), sinY = Math.sin(rotY);
            const cosX = Math.cos(rotX), sinX = Math.sin(rotX);
            const baseR = 195;

            for (let i = 0; i < particles.length; i++) {
                const p = particles[i];
                const ripple = Math.sin(t * 2 + p.phase + p.by * 3) * waveAmp;
                const r = baseR + ripple;

                let x1 = p.bx * cosY - p.bz * sinY;
                let z1 = p.bz * cosY + p.bx * sinY;
                let y2 = p.by * cosX - z1 * sinX;
                let z2 = z1 * cosX + p.by * sinX;

                const perspective = 460 / (460 + z2 * r);
                const px = cx + x1 * r * perspective;
                const py = cy + y2 * r * perspective;
                const alpha = Math.max(0.12, (z2 + 1.25) / 2.25);

                ctx.beginPath();
                ctx.arc(px, py, p.size * perspective, 0, Math.PI * 2);
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
        let keepConversationOpen = false;
        let workMode = localStorage.getItem('neo_mode') || 'ARBEIT';

        let userMemory = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        let userMaterials = JSON.parse(localStorage.getItem('neo_materials') || '[]');
        let userTasks = JSON.parse(localStorage.getItem('neo_tasks') || '[]');
        let chatHistory = JSON.parse(localStorage.getItem('neo_history') || '[]');

        document.body.addEventListener('touchstart', function initOnce() {
            unlockAudio();
            if (wakeEnabled && !wakeRec && !isRecording) startWakeListener();
            document.body.removeEventListener('touchstart', initOnce);
        }, { once: true });

        window.addEventListener('load', () => {
            updateBadges();
            const params = new URLSearchParams(window.location.search);
            if (params.get('listen') === '1') {
                keepConversationOpen = true;
                toggleRecord();
            } else {
                setState(null);
                startWakeListener();
            }
        });

        function updateBadges() {
            localStorage.setItem('neo_memory', JSON.stringify(userMemory));
            localStorage.setItem('neo_materials', JSON.stringify(userMaterials));
            localStorage.setItem('neo_tasks', JSON.stringify(userTasks));
            localStorage.setItem('neo_mode', workMode);

            document.getElementById('c-mem').innerText = userMemory.length;
            document.getElementById('c-mat').innerText = userMaterials.length;
            document.getElementById('c-task').innerText = userTasks.length;
            document.getElementById('modeBtn').innerText = workMode;
        }

        function toggleMode() {
            workMode = (workMode === 'ARBEIT') ? 'PRIVAT' : 'ARBEIT';
            updateBadges();
            statusEl.innerText = workMode === 'ARBEIT'
                ? "Arbeitsmodus aktiv, Sir."
                : "Privatmodus aktiv, Sir.";
        }

        function setState(state) {
            currentState = state || 'idle';
            document.body.classList.remove('listening', 'thinking', 'speaking');
            if (state === 'listening') { document.body.classList.add('listening'); stateLabel.innerText = "NEO • HÖRT ZU"; }
            else if (state === 'thinking') { document.body.classList.add('thinking'); stateLabel.innerText = "NEO • ANALYSIERT"; }
            else if (state === 'speaking') { document.body.classList.add('speaking'); stateLabel.innerText = "NEO • SPRICHT"; }
            else { stateLabel.innerText = wakeEnabled ? "NEO • BEREIT" : "NEO • PAUSIERT"; }
        }

        /* --- Drawer Menu --- */
        let activeTab = 'tools';
        function openDrawer() {
            document.getElementById('drawer').classList.add('open');
            switchTab(activeTab);
        }
        function closeDrawer() {
            document.getElementById('drawer').classList.remove('open');
        }
        function switchTab(tab) {
            activeTab = tab;
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            const body = document.getElementById('drawerBody');

            if (tab === 'tools') {
                body.innerHTML = `
                    <div class="quick-grid">
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Was steht heute an? Gib mir meinen Statusbericht mit Kalender, E-Mails, Aufgaben und Material.')">📋 Statusbericht</div>
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Wie wird das Wetter heute und morgen in Hamburg?')">🌤️ Wetter Hamburg</div>
                        <div class="q-btn" onclick="closeDrawer();saveParking()">🅿️ Parkplatz merken</div>
                        <div class="q-btn" onclick="closeDrawer();findParking()">🚗 Auto finden</div>
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Welche Termine habe ich heute und morgen?')">📅 Termine</div>
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Lies meine ungelesenen E-Mails vor.')">📧 E-Mails</div>
                    </div>`;
                return;
            }

            let list = userMemory;
            if (tab === 'materials') list = userMaterials;
            if (tab === 'tasks') list = userTasks;

            if (list.length === 0) {
                body.innerHTML = `<div style="color:#94A3B8; text-align:center; margin-top:30px;">Keine Einträge vorhanden, Sir.</div>`;
                return;
            }
            body.innerHTML = list.map((item, idx) =>
                `<div class="list-item"><span>${idx + 1}. ${item}</span><button class="check-btn" onclick="deleteItem('${tab}', ${idx})">✓</button></div>`
            ).join('');
        }

        function deleteItem(type, idx) {
            if (type === 'memory') userMemory.splice(idx, 1);
            if (type === 'materials') userMaterials.splice(idx, 1);
            if (type === 'tasks') userTasks.splice(idx, 1);
            updateBadges();
            switchTab(type);
        }

        /* --- Wake Word ("Hey Neo") --- */
        function toggleWakeWord() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                statusEl.innerText = "Bitte berühren Sie die Sphäre zum Sprechen, Sir.";
                return;
            }
            wakeEnabled = !wakeEnabled;
            document.getElementById('wakeBtn').classList.toggle('active', wakeEnabled);

            if (wakeEnabled) {
                unlockAudio();
                startWakeListener();
                setState(null);
                statusEl.innerText = "Sagen Sie einfach „Hey Neo“, Sir.";
            } else {
                keepConversationOpen = false;
                if (wakeRec) { try { wakeRec.stop(); } catch(e){} wakeRec = null; }
                setState(null);
                statusEl.innerText = "Sprachaktivierung pausiert.";
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
                    if (transcript.includes('neo') || transcript.includes('nio') || transcript.includes('heineo')) {
                        try { wakeRec.stop(); } catch(e){}
                        wakeRec = null;
                        keepConversationOpen = true;
                        playSciFiTone('wake');
                        toggleRecord();
                        return;
                    }
                }
            };

            wakeRec.onerror = () => {
                wakeRec = null;
                if (wakeEnabled && !isRecording) setTimeout(() => startWakeListener(), 800);
            };

            wakeRec.onend = () => {
                wakeRec = null;
                if (wakeEnabled && !isRecording && currentState === 'idle') setTimeout(() => startWakeListener(), 350);
            };

            try { wakeRec.start(); } catch(e) { wakeRec = null; }
        }

        function saveParking() {
            if (!navigator.geolocation) { statusEl.innerText = "GPS nicht verfügbar, Sir."; return; }
            statusEl.innerText = "Speichere GPS-Position...";
            navigator.geolocation.getCurrentPosition(pos => {
                const time = new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
                localStorage.setItem('neo_parking', JSON.stringify({lat: pos.coords.latitude, lng: pos.coords.longitude, time}));
                statusEl.innerText = `Parkplatz um ${time} Uhr gespeichert, Sir.`;
            }, () => { statusEl.innerText = "Standortzugriff verweigert, Sir."; });
        }

        function findParking() {
            const p = JSON.parse(localStorage.getItem('neo_parking') || 'null');
            if (!p) { statusEl.innerText = "Kein Parkplatz gespeichert, Sir."; return; }
            const url = `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}&travelmode=walking`;
            statusEl.innerHTML = `<div>Geparkt um ${p.time} Uhr, Sir.</div><div class="btn-row"><a href="${url}" class="action-pill">Route zum Auto</a></div>`;
            setTimeout(() => { window.location.href = url; }, 700);
        }

        function unlockAudio() {
            player.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";
            player.play().catch(() => {});
        }

        player.onplay = () => setState('speaking');
        player.onended = () => {
            setState(null);
            // Automatische Fortsetzung des Gesprächs nach der Antwort!
            if (keepConversationOpen) {
                setTimeout(() => {
                    if (!isRecording) toggleRecord();
                }, 700);
            } else if (wakeEnabled) {
                setTimeout(() => startWakeListener(), 1000);
            }
        };

        function stopRecording() {
            if (!isRecording) return;
            isRecording = false;
            audioEnergy = 0;
            if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
            if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
            if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
            if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
        }

        async function toggleRecord() {
            unlockAudio();
            if (isRecording) {
                keepConversationOpen = false;
                stopRecording();
                return;
            }
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
                        // Wenn Nutzer nichts mehr sagt, Gespräch sanft beenden und wieder auf "Hey Neo" warten
                        keepConversationOpen = false;
                        setState(null);
                        statusEl.innerText = "Sagen Sie „Hey Neo“, wenn Sie mich brauchen, Sir.";
                        if (wakeEnabled) setTimeout(() => startWakeListener(), 800);
                        return;
                    }
                    playSciFiTone('process');
                    await sendAudio(blob, mimeType);
                };

                mediaRecorder.start();
                isRecording = true;
                keepConversationOpen = true;
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
                    audioEnergy = avg;

                    if (avg > 14) {
                        hasSpoken = true;
                        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
                    } else if (hasSpoken && !silenceTimer) {
                        silenceTimer = setTimeout(() => stopRecording(), 1450);
                    } else if (!hasSpoken && (Date.now() - startTime > 6000)) {
                        // Nach 6 Sekunden Stille Gespräch automatisch schließen
                        keepConversationOpen = false;
                        stopRecording();
                    }
                    animFrame = requestAnimationFrame(monitorVolume);
                }
                monitorVolume();
            } catch (err) {
                keepConversationOpen = false;
                setState(null);
                statusEl.innerText = "Mikrofon-Zugriff erforderlich, Sir.";
            }
        }

        async function sendAudio(blob, mimeType) {
            setState('thinking');
            statusEl.innerText = "Verarbeite...";
            const reader = new FileReader();
            reader.readAsDataURL(blob);
            reader.onloadend = async () => {
                await callBackend({ audio: reader.result.split(',')[1], mime_type: mimeType });
            };
        }

        function handleImage(event) {
            const file = event.target.files[0];
            if (!file) return;
            unlockAudio();
            setState('thinking');
            statusEl.innerText = "Analysiere Bild...";
            const note = document.getElementById('msg').value.trim();
            document.getElementById('msg').value = '';

            const reader = new FileReader();
            reader.onload = function(e) {
                const img = new Image();
                img.onload = async function() {
                    const canvas = document.createElement('canvas');
                    const scale = Math.min(1, 1024 / img.width);
                    canvas.width = img.width * scale;
                    canvas.height = img.height * scale;
                    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
                    await callBackend({
                        image: canvas.toDataURL('image/jpeg', 0.8).split(',')[1],
                        message: note || "Analysiere dieses Bild und fasse es kurz zusammen."
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
            statusEl.innerText = "Verarbeite...";
            callBackend({ message: cmd });
        }

        async function sendText() {
            unlockAudio();
            const input = document.getElementById('msg');
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            setState('thinking');
            statusEl.innerText = "Verarbeite...";
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
                    keepConversationOpen = false;
                    statusEl.innerText = data.error;
                    if (wakeEnabled) setTimeout(() => startWakeListener(), 1000);
                    return;
                }

                // Wenn Nutzer das Gespräch beendet ("Danke", "Stopp", "Fertig"), Loop beenden
                const saidLower = (data.user_said || "").toLowerCase();
                if (
                    saidLower.includes("danke") ||
                    saidLower.includes("stopp") ||
                    saidLower.includes("fertig") ||
                    saidLower.includes("das war's") ||
                    saidLower.includes("das wars") ||
                    saidLower.includes("schluss") ||
                    data.end_conversation === true
                ) {
                    keepConversationOpen = false;
                }

                if (data.new_memory) userMemory.push(data.new_memory.trim());
                if (data.delete_memory) userMemory = userMemory.filter(x => !x.toLowerCase().includes(data.delete_memory.toLowerCase()));
                if (data.new_material) userMaterials.push(data.new_material.trim());
                if (data.delete_material) userMaterials = userMaterials.filter(x => !x.toLowerCase().includes(data.delete_material.toLowerCase()));
                if (data.new_task) userTasks.push(data.new_task.trim());
                if (data.delete_task) userTasks = userTasks.filter(x => !x.toLowerCase().includes(data.delete_task.toLowerCase()));
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
                    cBtn.className = "action-pill";
                    cBtn.innerText = "📋 Kopieren";
                    cBtn.onclick = () => {
                        navigator.clipboard.writeText(data.copy_text);
                        cBtn.innerText = "✓ Kopiert";
                    };
                    btnRow.appendChild(cBtn);
                }

                if (data.action_url) {
                    keepConversationOpen = false;
                    const aBtn = document.createElement('a');
                    aBtn.href = data.action_url;
                    aBtn.className = "action-pill";
                    aBtn.innerText = data.action_label || "Öffnen";
                    if (data.copy_text) aBtn.onclick = () => navigator.clipboard.writeText(data.copy_text).catch(()=>{});
                    btnRow.appendChild(aBtn);
                    if (!data.copy_text) setTimeout(() => { window.location.href = data.action_url; }, 750);
                }

                if (btnRow.children.length > 0) statusEl.appendChild(btnRow);

                if (data.audio) {
                    player.src = "data:audio/mp3;base64," + data.audio;
                    player.play().catch(() => {
                        if (wakeEnabled) setTimeout(() => startWakeListener(), 1000);
                    });
                } else if (keepConversationOpen) {
                    setTimeout(() => toggleRecord(), 700);
                } else if (wakeEnabled) {
                    setTimeout(() => startWakeListener(), 1000);
                }
            } catch (err) {
                keepConversationOpen = false;
                setState(null);
                statusEl.innerText = "Verbindungsfehler, Sir.";
                if (wakeEnabled) setTimeout(() => startWakeListener(), 1000);
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
6. GESPRÄCH BEENDEN:
   - Wenn Sir "Danke", "Stopp", "Fertig", "Das war's" oder "Gute Nacht" sagt, setze "end_conversation": true.

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
  "action_label": "",
  "end_conversation": false
}}
"""

async def make_voice(text):
    clean_text = text.replace("*", "").replace("#", "").replace("...", ".").strip()
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
            "end_conversation": result.get("end_conversation", False),
            "audio": audio_b64
        })
    except Exception as e:
        return jsonify({"error": f"Fehler: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
