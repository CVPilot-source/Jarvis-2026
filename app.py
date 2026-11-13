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
    "name": "JARVIS MARK IX ULTIMATE",
    "short_name": "JARVIS",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#030712",
    "theme_color": "#030712",
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
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#00F0FF" stop-opacity="0.5"/>
      <stop offset="70%" stop-color="#0284C7" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="#030712" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" rx="115" fill="#030712"/>
  <circle cx="256" cy="256" r="220" fill="url(#glow)"/>
  <circle cx="256" cy="256" r="188" fill="none" stroke="#00F0FF" stroke-width="6" stroke-opacity="0.35"/>
  <circle cx="256" cy="256" r="160" fill="none" stroke="#00F0FF" stroke-width="14" stroke-dasharray="65 25 15 25"/>
  <circle cx="256" cy="256" r="120" fill="none" stroke="#38BDF8" stroke-width="6" stroke-dasharray="12 12"/>
  <circle cx="256" cy="256" r="82" fill="#061626" stroke="#00F0FF" stroke-width="5"/>
  <text x="256" y="276" font-family="sans-serif" font-size="64" font-weight="800" fill="#00F0FF" text-anchor="middle">J</text>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#030712">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/svg+xml" href="/icon.svg">
    <title>JARVIS MARK IX</title>
    <style>
        :root {
            --primary: #00F0FF;
            --glow: rgba(0, 240, 255, 0.45);
            --bg: #030712;
        }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body {
            margin: 0;
            background-color: var(--bg);
            background-image: 
                radial-gradient(circle at 50% 25%, rgba(0, 240, 255, 0.13) 0%, transparent 55%),
                linear-gradient(rgba(0, 240, 255, 0.04) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 240, 255, 0.04) 1px, transparent 1px);
            background-size: 100% 100%, 32px 32px, 32px 32px;
            color: var(--primary);
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
            height: 100dvh;
            padding: 12px 14px 16px;
            overflow: hidden;
        }
        .hud-top {
            width: 100%;
            max-width: 480px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 10px;
            letter-spacing: 1px;
            text-transform: uppercase;
            border-bottom: 1px solid rgba(0, 240, 255, 0.22);
            padding-bottom: 8px;
            gap: 4px;
        }
        .top-actions { display: flex; gap: 5px; flex-wrap: wrap; justify-content: flex-end; }
        .badge-btn {
            font-size: 9.5px;
            padding: 4px 8px;
            border: 1px solid rgba(0, 240, 255, 0.45);
            background: rgba(0, 240, 255, 0.08);
            border-radius: 12px;
            cursor: pointer;
            color: var(--primary);
            font-weight: 600;
        }
        .badge-btn.active {
            background: #00FF88;
            color: #030712;
            border-color: #00FF88;
            box-shadow: 0 0 10px rgba(0, 255, 136, 0.4);
        }
        .badge-btn.work {
            background: rgba(255, 165, 0, 0.2);
            border-color: #FFA500;
            color: #FFD280;
        }
        .core-wrapper {
            position: relative;
            width: 185px;
            height: 185px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
            margin-top: 2px;
        }
        .ring-outer {
            position: absolute;
            width: 182px;
            height: 182px;
            border-radius: 50%;
            border: 2px dashed rgba(0, 240, 255, 0.45);
            animation: spinRight 24s linear infinite;
        }
        .ring-mid {
            position: absolute;
            width: 158px;
            height: 158px;
            border-radius: 50%;
            border: 4px solid transparent;
            border-top-color: var(--primary);
            border-bottom-color: var(--primary);
            box-shadow: 0 0 22px var(--glow);
            animation: spinLeft 10s linear infinite;
        }
        .ring-inner {
            position: absolute;
            width: 134px;
            height: 134px;
            border-radius: 50%;
            border: 2px dotted rgba(0, 240, 255, 0.75);
            animation: spinRight 16s linear infinite;
        }
        .core-center {
            position: relative;
            width: 112px;
            height: 112px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(0, 240, 255, 0.24) 0%, rgba(3, 7, 18, 0.94) 75%);
            border: 2px solid var(--primary);
            box-shadow: 0 0 28px var(--glow), inset 0 0 20px var(--glow);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 2;
            transition: all 0.2s;
        }
        .core-center h1 {
            margin: 0;
            font-size: 18px;
            font-weight: 800;
            letter-spacing: 3px;
            text-shadow: 0 0 12px var(--primary);
        }
        .core-center span {
            font-size: 7px;
            letter-spacing: 1.8px;
            opacity: 0.85;
            margin-top: 3px;
        }
        body.listening { --primary: #00FF88; --glow: rgba(0, 255, 136, 0.55); }
        body.listening .ring-mid { animation-duration: 3s; }
        body.thinking { --primary: #FF9500; --glow: rgba(255, 149, 0, 0.55); }
        body.thinking .ring-mid { animation-duration: 1.4s; }
        body.speaking .core-center { animation: pulseSpeak 0.85s ease-in-out infinite alternate; }

        @keyframes spinRight { 100% { transform: rotate(360deg); } }
        @keyframes spinLeft { 100% { transform: rotate(-360deg); } }
        @keyframes pulseSpeak {
            0% { transform: scale(1); box-shadow: 0 0 25px var(--glow); }
            100% { transform: scale(1.07); box-shadow: 0 0 48px var(--glow); }
        }
        .visualizer {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
            height: 18px;
            margin-top: 4px;
        }
        .bar {
            width: 3.5px;
            height: 5px;
            background: var(--primary);
            border-radius: 3px;
            box-shadow: 0 0 8px var(--primary);
            transition: height 0.08s ease;
        }
        .hint {
            font-size: 10.5px;
            opacity: 0.72;
            margin-top: 2px;
            text-align: center;
        }
        .hud-panel {
            flex: 1;
            width: 100%;
            max-width: 460px;
            margin: 8px 0;
            padding: 14px;
            background: rgba(11, 19, 36, 0.72);
            border: 1px solid rgba(0, 240, 255, 0.25);
            border-left: 3px solid var(--primary);
            border-right: 3px solid var(--primary);
            border-radius: 14px;
            backdrop-filter: blur(8px);
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: 14.5px;
            line-height: 1.5;
            color: #E0F7FA;
        }
        .list-item {
            width: 100%;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(0, 240, 255, 0.08);
            padding: 7px 10px;
            border-radius: 8px;
            margin-bottom: 6px;
            font-size: 13px;
            text-align: left;
        }
        .del-btn {
            background: #FF4D4D;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 11px;
            cursor: pointer;
            margin-left: 8px;
        }
        .btn-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            justify-content: center;
            margin-top: 10px;
        }
        .action-btn {
            padding: 10px 18px;
            border-radius: 25px;
            background: #00FF88;
            color: #030712;
            font-weight: 800;
            text-decoration: none;
            font-size: 13px;
            display: inline-block;
            border: none;
            cursor: pointer;
            box-shadow: 0 0 18px rgba(0, 255, 136, 0.45);
        }
        .copy-btn {
            padding: 10px 16px;
            border-radius: 25px;
            background: #38BDF8;
            color: #030712;
            font-weight: 800;
            font-size: 13px;
            border: none;
            cursor: pointer;
        }
        .quick-apps {
            display: flex;
            gap: 6px;
            width: 100%;
            max-width: 460px;
            overflow-x: auto;
            padding-bottom: 7px;
            scrollbar-width: none;
        }
        .quick-apps::-webkit-scrollbar { display: none; }
        .chip {
            white-space: nowrap;
            padding: 6px 11px;
            border-radius: 16px;
            border: 1px solid rgba(0, 240, 255, 0.35);
            background: rgba(11, 19, 36, 0.85);
            color: #00F0FF;
            font-size: 11.5px;
            cursor: pointer;
        }
        .input-box {
            display: flex;
            gap: 6px;
            width: 100%;
            max-width: 460px;
            align-items: center;
        }
        .cam-btn {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            border: 1px solid rgba(0, 240, 255, 0.45);
            background: rgba(11, 19, 36, 0.9);
            color: #00F0FF;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            flex-shrink: 0;
        }
        input[type="text"] {
            flex: 1;
            padding: 12px 14px;
            border-radius: 25px;
            border: 1px solid rgba(0, 240, 255, 0.45);
            background: rgba(11, 19, 36, 0.88);
            color: white;
            font-size: 15px;
            outline: none;
            min-width: 0;
        }
        button.send-btn {
            padding: 12px 16px;
            border-radius: 25px;
            border: none;
            background: var(--primary);
            color: #030712;
            font-weight: 800;
            font-size: 13px;
            cursor: pointer;
            box-shadow: 0 0 14px var(--glow);
            flex-shrink: 0;
        }
    </style>
</head>
<body>
    <div class="hud-top">
        <div class="badge-btn work" id="modeBtn" onclick="toggleMode()">🏢 ARBEIT</div>
        <div class="top-actions">
            <div class="badge-btn" id="loopBtn" onclick="toggleLoop()">AUTO: AUS</div>
            <div class="badge-btn" onclick="showList('memory')" id="memCount">NOTIZEN: 0</div>
            <div class="badge-btn" onclick="showList('materials')" id="matCount">MATERIAL: 0</div>
            <div class="badge-btn" onclick="showList('tasks')" id="taskCount">TASKS: 0</div>
        </div>
    </div>

    <div style="display:flex; flex-direction:column; align-items:center;">
        <div class="core-wrapper" onclick="toggleRecord()">
            <div class="ring-outer"></div>
            <div class="ring-mid"></div>
            <div class="ring-inner"></div>
            <div class="core-center" id="coreCenter">
                <h1>JARVIS</h1>
                <span>MARK IX PRO</span>
            </div>
        </div>

        <div class="visualizer">
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
            <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        </div>
        <div class="hint" id="hint">Tippen & sprechen • Kamera für Objekte/Briefe</div>
    </div>

    <div class="hud-panel" id="status">Bereit, Sir. Objekt-Codes, Materialbestellungen, Termine, Kamera und WhatsApp sind aktiv.</div>

    <div class="quick-apps">
        <div class="chip" onclick="quickCmd('Gib mir mein Tagesbriefing mit Terminen, E-Mails, Aufgaben und Materialliste.')">📋 Briefing</div>
        <div class="chip" onclick="saveParking()">🅿️ Parkplatz merken</div>
        <div class="chip" onclick="findParking()">🚗 Auto finden</div>
        <div class="chip" onclick="quickCmd('Welche Termine habe ich heute und morgen?')">📅 Termine</div>
        <div class="chip" onclick="quickCmd('Lies meine ungelesenen E-Mails vor.')">📧 E-Mails</div>
        <div class="chip" onclick="quickCmd('Öffne Google Maps')">🗺️ Maps</div>
    </div>

    <div class="input-box">
        <button class="cam-btn" onclick="document.getElementById('camInput').click()" title="Kamera / Foto">📷</button>
        <input type="file" id="camInput" accept="image/*" capture="environment" style="display:none" onchange="handleImage(event)">
        <input type="text" id="msg" placeholder="Befehl, Objekt-Code oder Notiz..." onkeypress="if(event.key==='Enter') sendText()">
        <button class="send-btn" onclick="sendText()">SEND</button>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        const statusEl = document.getElementById('status');
        const hintEl = document.getElementById('hint');
        const coreCenter = document.getElementById('coreCenter');
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
        let userMemory = JSON.parse(localStorage.getItem('jarvis_memory') || '[]');
        let userMaterials = JSON.parse(localStorage.getItem('jarvis_materials') || '[]');
        let userTasks = JSON.parse(localStorage.getItem('jarvis_tasks') || '[]');
        let chatHistory = JSON.parse(localStorage.getItem('jarvis_history') || '[]');

        function updateBadges() {
            localStorage.setItem('jarvis_memory', JSON.stringify(userMemory));
            localStorage.setItem('jarvis_materials', JSON.stringify(userMaterials));
            localStorage.setItem('jarvis_tasks', JSON.stringify(userTasks));
            localStorage.setItem('jarvis_mode', workMode);

            document.getElementById('memCount').innerText = "NOTIZEN: " + userMemory.length;
            document.getElementById('matCount').innerText = "MATERIAL: " + userMaterials.length;
            document.getElementById('taskCount').innerText = "TASKS: " + userTasks.length;

            const modeBtn = document.getElementById('modeBtn');
            if (workMode === 'ARBEIT') {
                modeBtn.innerText = "🏢 ARBEIT";
                modeBtn.classList.add('work');
            } else {
                modeBtn.innerText = "🏠 PRIVAT";
                modeBtn.classList.remove('work');
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
            btn.innerText = autoLoop ? "AUTO: AN" : "AUTO: AUS";
            btn.classList.toggle('active', autoLoop);
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
            statusEl.innerHTML = `<div style='width:100%;'><div style='margin-bottom:8px;font-weight:bold;color:#00F0FF;'>${title}:</div>` +
                list.map((m, i) => `<div class="list-item"><span>${i+1}. ${m}</span><button class="del-btn" onclick="deleteItem('${type}', ${i})">✓</button></div>`).join("") +
                "</div>";
        }

        function saveParking() {
            if (!navigator.geolocation) {
                statusEl.innerText = "GPS wird auf diesem Gerät nicht unterstützt, Sir.";
                return;
            }
            statusEl.innerText = "Ermittle GPS-Position des Fahrzeugs...";
            navigator.geolocation.getCurrentPosition(pos => {
                const lat = pos.coords.latitude;
                const lng = pos.coords.longitude;
                const time = new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
                localStorage.setItem('jarvis_parking', JSON.stringify({lat, lng, time}));
                statusEl.innerText = `Parkplatz um ${time} Uhr gespeichert, Sir!`;
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
            statusEl.innerHTML = `<div>Ihr Fahrzeug wurde um ${p.time} Uhr hier geparkt, Sir.</div><div class="btn-row"><a href="${url}" class="action-btn">Route zum Auto starten</a></div>`;
            setTimeout(() => { window.location.href = url; }, 700);
        }

        function setBars(level) {
            bars.forEach((bar, i) => {
                const factor = Math.sin((i + 1) * 0.7) * 0.5 + 0.7;
                const h = Math.max(5, Math.min(18, level * factor));
                bar.style.height = h + 'px';
            });
        }

        function setState(state) {
            document.body.classList.remove('listening', 'thinking', 'speaking');
            coreCenter.style.transform = '';
            setBars(5);
            if (state) document.body.classList.add(state);
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
                    coreCenter.style.transform = `scale(${scale.toFixed(2)})`;
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
                hintEl.innerText = "Tippen & sprechen • Kamera für Objekte/Briefe";

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
                    cBtn.className = "copy-btn";
                    cBtn.innerText = "📋 Text kopieren";
                    cBtn.onclick = () => {
                        navigator.clipboard.writeText(data.copy_text);
                        cBtn.innerText = "✓ Kopiert!";
                    };
                    btnRow.appendChild(cBtn);
                }

                if (data.action_url) {
                    const aBtn = document.createElement('a');
                    aBtn.href = data.action_url;
                    aBtn.className = "action-btn";
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
