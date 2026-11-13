import os
import re
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
            transition: background 0.2s;
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
            min-height: 60px;
            max-height: 145px;
            overflow-y: auto;
            text-align: center;
            font-size: 14.5px;
            font-weight: 300;
            line-height: 1.55;
            color: rgba(255, 255, 255, 0.88);
            padding: 0 10px;
            margin-bottom: 10px;
            z-index: 5;
        }

        .action-bar {
            display: flex;
            gap: 10px;
            justify-content: center;
            align-items: center;
            margin-top: 8px;
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
            width: 46px;
            height: 46px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.75);
            font-size: 18px;
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
            background: rgba(0, 0, 0, 0.94);
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
            <span id="stateLabel">NEO • STANDBY</span>
        </div>
        <div class="mode-tag" id="modeBtn" onclick="toggleMode()">ARBEIT</div>
    </div>

    <div class="hologram-center" onclick="toggleDirectRecord()">
        <canvas id="particleCanvas" width="620" height="620"></canvas>
    </div>

    <div class="caption-area" id="captionArea"></div>

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
        /* --- 3D Particle Sphere --- */
        const canvas = document.getElementById('particleCanvas');
        const ctx = canvas.getContext('2d');
        const particles = [];
        const NUM_PARTICLES = 600;
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

            let speed = 0.005;
            let waveAmp = 4;

            if (currentState === 'listening') {
                speed = 0.016;
                currentColor = { r: 0, g: 255, b: 145 };
                waveAmp = 6 + audioEnergy * 0.7;
            } else if (currentState === 'thinking') {
                speed = 0.036;
                currentColor = { r: 245, g: 165, b: 20 };
                waveAmp = 12;
            } else if (currentState === 'speaking') {
                speed = 0.014;
                currentColor = { r: 45, g: 212, b: 255 };
                waveAmp = 10 + Math.abs(Math.sin(t * 5.5)) * 18;
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

        function playTone(freq1, freq2) {
            try {
                const ac = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ac.createOscillator();
                const gain = ac.createGain();
                osc.connect(gain);
                gain.connect(ac.destination);
                osc.type = 'sine';
                osc.frequency.setValueAtTime(freq1, ac.currentTime);
                osc.frequency.exponentialRampToValueAtTime(freq2, ac.currentTime + 0.12);
                gain.gain.setValueAtTime(0.12, ac.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.15);
                osc.start();
                osc.stop(ac.currentTime + 0.16);
            } catch (e) {}
        }

        /* --- Core Audio & State Management (Zero Audio Interruption!) --- */
        const captionArea = document.getElementById('captionArea');
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
        let inConversation = false;
        let isSpeaking = false;
        let workMode = localStorage.getItem('neo_mode') || 'ARBEIT';

        let userMemory = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        let userMaterials = JSON.parse(localStorage.getItem('neo_materials') || '[]');
        let userTasks = JSON.parse(localStorage.getItem('neo_tasks') || '[]');
        let chatHistory = JSON.parse(localStorage.getItem('neo_history') || '[]');

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
        updateBadges();

        function toggleMode() {
            workMode = (workMode === 'ARBEIT') ? 'PRIVAT' : 'ARBEIT';
            updateBadges();
            stateLabel.innerText = "NEO • " + workMode;
        }

        function setState(state) {
            currentState = state || 'idle';
            document.body.classList.remove('listening', 'thinking', 'speaking');
            if (state === 'listening') { document.body.classList.add('listening'); stateLabel.innerText = "NEO • HÖRT ZU"; }
            else if (state === 'thinking') { document.body.classList.add('thinking'); stateLabel.innerText = "NEO • ANALYSIERT"; }
            else if (state === 'speaking') { document.body.classList.add('speaking'); stateLabel.innerText = "NEO • SPRICHT"; }
            else { stateLabel.innerText = wakeEnabled ? "NEO • STANDBY" : "NEO • PAUSIERT"; }
        }

        function stopWakeListener() {
            if (wakeRec) {
                try { wakeRec.onend = null; wakeRec.abort(); } catch(e){}
                wakeRec = null;
            }
        }

        function toggleWakeWord() {
            wakeEnabled = !wakeEnabled;
            document.getElementById('wakeBtn').classList.toggle('active', wakeEnabled);
            if (wakeEnabled) {
                setState(null);
                startWakeListener();
            } else {
                inConversation = false;
                stopWakeListener();
                setState(null);
            }
        }

        function startWakeListener() {
            // Niemals Mikrofon starten während NEO spricht oder bereits aufnimmt!
            if (!wakeEnabled || isRecording || inConversation || isSpeaking || currentState !== 'idle') return;
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) return;
            stopWakeListener();

            wakeRec = new SpeechRecognition();
            wakeRec.lang = 'de-DE';
            wakeRec.continuous = true;
            wakeRec.interimResults = true;

            wakeRec.onresult = (event) => {
                if (isSpeaking || isRecording) return;
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const txt = event.results[i][0].transcript.toLowerCase();
                    if (txt.includes('neo') || txt.includes('nio') || txt.includes('heineo')) {
                        stopWakeListener();
                        inConversation = true;
                        playTone(540, 960);
                        setTimeout(() => startDirectAudio(), 180);
                        return;
                    }
                }
            };

            wakeRec.onend = () => {
                wakeRec = null;
                if (wakeEnabled && !isRecording && !inConversation && !isSpeaking && currentState === 'idle') {
                    setTimeout(() => startWakeListener(), 400);
                }
            };

            try { wakeRec.start(); } catch(e) { wakeRec = null; }
        }

        function stopDirectAudio() {
            if (!isRecording) return;
            isRecording = false;
            audioEnergy = 0;
            if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
            if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
            if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
            if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
        }

        function toggleDirectRecord() {
            if (isSpeaking) {
                player.pause();
                player.currentTime = 0;
                isSpeaking = false;
                setState(null);
            }
            if (isRecording) {
                inConversation = false;
                stopDirectAudio();
                return;
            }
            stopWakeListener();
            inConversation = true;
            playTone(540, 960);
            startDirectAudio();
        }

        async function startDirectAudio() {
            if (isRecording || isSpeaking) return;
            stopWakeListener();
            try {
                activeStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                audioChunks = [];
                let options = { audioBitsPerSecond: 16000 };
                if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) options.mimeType = 'audio/webm;codecs=opus';
                else if (MediaRecorder.isTypeSupported('audio/webm')) options.mimeType = 'audio/webm';
                else if (MediaRecorder.isTypeSupported('audio/mp4')) options.mimeType = 'audio/mp4';

                mediaRecorder = new MediaRecorder(activeStream, options);
                mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) audioChunks.push(e.data); };

                mediaRecorder.onstop = async () => {
                    activeStream.getTracks().forEach(t => t.stop());
                    const mimeType = (mediaRecorder.mimeType || 'audio/webm').split(';')[0];
                    const blob = new Blob(audioChunks, { type: mimeType });

                    if (blob.size < 900) {
                        inConversation = false;
                        setState(null);
                        if (wakeEnabled) setTimeout(() => startWakeListener(), 600);
                        return;
                    }
                    playTone(760, 440);
                    setState('thinking');
                    const reader = new FileReader();
                    reader.readAsDataURL(blob);
                    reader.onloadend = () => {
                        sendToNeo({ audio: reader.result.split(',')[1], mime_type: mimeType });
                    };
                };

                mediaRecorder.start();
                isRecording = true;
                setState('listening');

                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const source = audioCtx.createMediaStreamSource(activeStream);
                const analyser = audioCtx.createAnalyser();
                analyser.fftSize = 256;
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
                        silenceTimer = setTimeout(() => stopDirectAudio(), 1150);
                    } else if (!hasSpoken && (Date.now() - startTime > 6000)) {
                        inConversation = false;
                        stopDirectAudio();
                    }
                    animFrame = requestAnimationFrame(monitorVolume);
                }
                monitorVolume();
            } catch (err) {
                inConversation = false;
                setState(null);
            }
        }

        // Volle Audio-Wiedergabe garantieren ohne Unterbrechung!
        player.onplay = () => {
            isSpeaking = true;
            stopWakeListener();
            setState('speaking');
        };

        player.onended = () => {
            isSpeaking = false;
            setState(null);
            if (inConversation) {
                setTimeout(() => startDirectAudio(), 650);
            } else if (wakeEnabled) {
                setTimeout(() => startWakeListener(), 850);
            }
        };

        player.onerror = () => {
            isSpeaking = false;
            setState(null);
            if (wakeEnabled) setTimeout(() => startWakeListener(), 850);
        };

        /* --- Drawer & Tools --- */
        let activeTab = 'tools';
        function openDrawer() { document.getElementById('drawer').classList.add('open'); switchTab(activeTab); }
        function closeDrawer() { document.getElementById('drawer').classList.remove('open'); }
        function switchTab(tab) {
            activeTab = tab;
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            const body = document.getElementById('drawerBody');

            if (tab === 'tools') {
                body.innerHTML = `
                    <div class="quick-grid">
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Erkläre mir ausführlich meine Termine im Kalender für heute und morgen.')">📅 Kalender erklären</div>
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Gib mir meinen Statusbericht für heute mit Kalender und Aufgaben.')">📋 Statusbericht</div>
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Wie wird das Wetter heute in Hamburg?')">🌤️ Wetter Hamburg</div>
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Lies meine ungelesenen E-Mails vor.')">📧 E-Mails</div>
                        <div class="q-btn" onclick="closeDrawer();saveParking()">🅿️ Parkplatz merken</div>
                        <div class="q-btn" onclick="closeDrawer();findParking()">🚗 Auto finden</div>
                    </div>`;
                return;
            }
            let list = tab === 'materials' ? userMaterials : (tab === 'tasks' ? userTasks : userMemory);
            body.innerHTML = list.length === 0
                ? `<div style="color:#94A3B8; text-align:center; margin-top:30px;">Leer, Sir.</div>`
                : list.map((item, idx) => `<div class="list-item"><span>${idx + 1}. ${item}</span><button class="check-btn" onclick="deleteItem('${tab}', ${idx})">✓</button></div>`).join('');
        }

        function deleteItem(type, idx) {
            if (type === 'memory') userMemory.splice(idx, 1);
            if (type === 'materials') userMaterials.splice(idx, 1);
            if (type === 'tasks') userTasks.splice(idx, 1);
            updateBadges();
            switchTab(type);
        }

        function saveParking() {
            if (!navigator.geolocation) return;
            navigator.geolocation.getCurrentPosition(pos => {
                const time = new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
                localStorage.setItem('neo_parking', JSON.stringify({lat: pos.coords.latitude, lng: pos.coords.longitude, time}));
                captionArea.innerText = `Parkplatz um ${time} Uhr gespeichert, Sir.`;
            });
        }

        function findParking() {
            const p = JSON.parse(localStorage.getItem('neo_parking') || 'null');
            if (!p) { captionArea.innerText = "Kein Parkplatz gespeichert, Sir."; return; }
            window.location.href = `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lng}&travelmode=walking`;
        }

        function handleImage(event) {
            const file = event.target.files[0];
            if (!file) return;
            setState('thinking');
            const note = document.getElementById('msg').value.trim();
            document.getElementById('msg').value = '';
            const reader = new FileReader();
            reader.onload = function(e) {
                const img = new Image();
                img.onload = function() {
                    const canvas = document.createElement('canvas');
                    const scale = Math.min(1, 800 / img.width);
                    canvas.width = img.width * scale;
                    canvas.height = img.height * scale;
                    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
                    sendToNeo({
                        image: canvas.toDataURL('image/jpeg', 0.7).split(',')[1],
                        message: note || "Analysiere dieses Bild und erkläre es kurz."
                    });
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
            event.target.value = '';
        }

        function quickCmd(cmd) { setState('thinking'); sendToNeo({ message: cmd }); }
        function sendText() {
            const input = document.getElementById('msg');
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            setState('thinking');
            sendToNeo({ message: text });
        }

        async function sendToNeo(payload) {
            stopWakeListener();
            captionArea.innerHTML = "";
            payload.mode = workMode;
            payload.memory = userMemory;
            payload.materials = userMaterials;
            payload.tasks = userTasks;
            payload.history = chatHistory.slice(-6);
            payload.local_time_str = new Date().toLocaleString('de-DE');

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (data.error) {
                    inConversation = false;
                    setState(null);
                    stateLabel.innerText = "FEHLER";
                    captionArea.innerText = data.error;
                    if (wakeEnabled) setTimeout(() => startWakeListener(), 1000);
                    return;
                }

                if (data.end_conversation) inConversation = false;
                if (data.new_memory) userMemory.push(data.new_memory.trim());
                if (data.delete_memory) userMemory = userMemory.filter(x => !x.toLowerCase().includes(data.delete_memory.toLowerCase()));
                if (data.new_material) userMaterials.push(data.new_material.trim());
                if (data.delete_material) userMaterials = userMaterials.filter(x => !x.toLowerCase().includes(data.delete_material.toLowerCase()));
                if (data.new_task) userTasks.push(data.new_task.trim());
                if (data.delete_task) userTasks = userTasks.filter(x => !x.toLowerCase().includes(data.delete_task.toLowerCase()));
                updateBadges();

                chatHistory.push({ role: "neo", text: data.reply });
                localStorage.setItem('neo_history', JSON.stringify(chatHistory.slice(-10)));

                // Zeige Antworttext sauber an
                const textDiv = document.createElement('div');
                textDiv.innerText = data.reply;
                captionArea.appendChild(textDiv);

                const btnRow = document.createElement('div');
                btnRow.className = "action-bar";

                if (data.copy_text && data.copy_text.trim() !== "") {
                    const cBtn = document.createElement('button');
                    cBtn.className = "action-pill";
                    cBtn.innerText = "📋 Kopieren";
                    cBtn.onclick = () => { navigator.clipboard.writeText(data.copy_text); cBtn.innerText = "✓ Kopiert"; };
                    btnRow.appendChild(cBtn);
                }

                if (data.action_url) {
                    inConversation = false;
                    const aBtn = document.createElement('a');
                    aBtn.href = data.action_url;
                    aBtn.className = "action-pill";
                    aBtn.innerText = data.action_label || "Öffnen";
                    if (data.copy_text) aBtn.onclick = () => navigator.clipboard.writeText(data.copy_text).catch(()=>{});
                    btnRow.appendChild(aBtn);
                    if (!data.copy_text) setTimeout(() => { window.location.href = data.action_url; }, 600);
                }

                if (btnRow.children.length > 0) captionArea.appendChild(btnRow);

                if (data.audio) {
                    isSpeaking = true;
                    setState('speaking');
                    player.src = "data:audio/mp3;base64," + data.audio;
                    const playPromise = player.play();
                    if (playPromise !== undefined) {
                        playPromise.catch(() => {
                            isSpeaking = false;
                            setState(null);
                            if (wakeEnabled) setTimeout(() => startWakeListener(), 800);
                        });
                    }
                } else {
                    setState(null);
                    if (inConversation) setTimeout(() => startDirectAudio(), 650);
                    else if (wakeEnabled) setTimeout(() => startWakeListener(), 800);
                }
            } catch (err) {
                inConversation = false;
                isSpeaking = false;
                setState(null);
                captionArea.innerText = "Verbindungsfehler, Sir.";
                if (wakeEnabled) setTimeout(() => startWakeListener(), 1000);
            }
        }

        window.addEventListener('load', () => {
            const params = new URLSearchParams(window.location.search);
            if (params.get('listen') === '1') {
                inConversation = true;
                // Begrüßung beim Öffnen der App vollständig abspielen und danach direkt zuhören!
                sendToNeo({ message: "Begrüße Sir kurz beim Öffnen der App und frage, wie du helfen kannst." });
            } else {
                startWakeListener();
            }
        });
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
        with urllib.request.urlopen(req, timeout=6) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status": "error", "message": str(e)}

SYSTEM_PROMPT = """Du bist NEO, der hochintelligente, ruhige KI-Assistent von Sir (Kundenbetreuer in einer Gebäudereinigung in Hamburg).
Aktueller Modus: {mode} | Aktuelle Zeit: {local_time}
Antworte IMMER auf perfektem Deutsch, höflich, ohne Sternchen/Markdown, und nenne den Nutzer 'Sir'.

WICHTIGE REGELN FÜR KALENDER & ERKLÄRUNGEN:
1. KALENDER & TERMINE (SEHR WICHTIG):
   - Wenn Sir nach seinem Kalender, Terminen, Objektbesichtigungen oder seinem Tagesplan fragt: Nutze die bereitgestellten 'Kalender-Daten' und ERKLÄRE ihm die Termine klar, vollständig und strukturiert in 3 bis 5 Sätzen (nenne Uhrzeit, Titel des Termins, Ort/Objekt und worum es geht). Kürze Kalender-Erklärungen NICHT zu stark ab!
   - Wenn im Kalender keine Termine stehen oder die Google-Bridge noch nicht verbunden ist, erkläre Sir das freundlich und nenne stattdessen seine offenen Aufgaben (Tasks) und Notizen.
2. ALLGEMEINE ANTWORTEN:
   - Bei normalen Befehlen antworte präzise in 1-2 Sätzen.
3. WHATSAPP (ANDROID NATIVE INTENT — NIEMALS web.whatsapp.com!):
   - Nummer bekannt: "https://wa.me/49176...?text=URL_ENCODED"
   - Nummer NICHT bekannt:
     * Modus ARBEIT: "intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp.w4b;end"
     * Modus PRIVAT: "intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp;end"
4. MAPS & APPS:
   - Maps: "https://www.google.com/maps/search/?api=1&query=URL_ENCODED"
   - Social Media Post: Text in 'copy_text', action_url auf Instagram/TikTok/LinkedIn/Facebook.
5. LISTEN:
   - 'new_memory' / 'delete_memory': Objekt-Codes, Notizen, Nummern
   - 'new_material' / 'delete_material': Material/Einkauf
   - 'new_task' / 'delete_task': Aufgaben
6. GESPRÄCH ENDE:
   - Bei "Danke", "Stopp", "Fertig", "Das war's": setze "end_conversation": true.

Antworte AUSSCHLIESSLICH als gültiges JSON-Objekt (ohne Markdown-Codeblöcke):
{{
  "reply": "Deine vollständige gesprochene Antwort an Sir",
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

def extract_json(raw_text):
    clean = raw_text.strip()
    match = re.search(r'\{.*\}', clean, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return {"reply": clean}

async def make_voice(text):
    clean_text = text.replace("*", "").replace("#", "").replace("...", ".").strip()
    communicate = edge_tts.Communicate(clean_text, "de-DE-FlorianMultilingualNeural", rate="+6%")
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
        msg = data.get("message", "")
        local_time_str = data.get("local_time_str", datetime.now().strftime("%d.%m.%Y %H:%M"))

        # Kalender & E-Mails abrufen (bei Audio immer vorsorglich mitladen, falls Sir nach Terminen fragt!)
        google_data = {}
        lower_msg = msg.lower()
        if "audio" in data or any(w in lower_msg for w in ["kalender", "termin", "heute", "morgen", "woche", "statusbericht", "plan", "besichtigung"]):
            google_data["calendar"] = call_google_bridge({"action": "get_calendar"})
        if "audio" in data or any(w in lower_msg for w in ["mail", "e-mail", "posteingang", "statusbericht"]):
            google_data["emails"] = call_google_bridge({"action": "get_emails"})

        client = genai.Client(api_key=api_key)
        contents = []

        if "image" in data:
            contents.append(types.Part.from_bytes(data=base64.b64decode(data["image"]), mime_type="image/jpeg"))
            contents.append(msg or "Analysiere dieses Bild und erkläre es kurz.")
        elif "audio" in data:
            contents.append(types.Part.from_bytes(data=base64.b64decode(data["audio"]), mime_type=data.get("mime_type", "audio/webm")))
            contents.append("Höre zu und antworte direkt auf Deutsch. Wenn Sir nach dem Kalender oder Terminen fragt, erkläre sie ausführlich.")
        else:
            contents.append(msg)

        context_str = (
            f"Kalender- und E-Mail-Daten: {json.dumps(google_data, ensure_ascii=False)} | "
            f"Notizen: {json.dumps(data.get('memory', []), ensure_ascii=False)} | "
            f"Material: {json.dumps(data.get('materials', []), ensure_ascii=False)} | "
            f"Tasks: {json.dumps(data.get('tasks', []), ensure_ascii=False)} | "
            f"Verlauf: {json.dumps(data.get('history', []), ensure_ascii=False)}"
        )
        contents.append(context_str)

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT.format(mode=mode, local_time=local_time_str),
                tools=[{"google_search": {}}]
            )
        )

        result = extract_json(response.text)
        reply = result.get("reply", "Zu Befehl, Sir.")
        audio_b64 = asyncio.run(make_voice(reply))

        return jsonify({
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
