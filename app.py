import os
import re
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
  <circle cx="256" cy="256" r="165" fill="none" stroke="#00F5D4" stroke-width="6" stroke-dasharray="12 16"/>
  <circle cx="256" cy="256" r="115" fill="none" stroke="#00BBF9" stroke-width="4"/>
  <circle cx="256" cy="256" r="24" fill="#00F5D4"/>
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
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
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

        .top-pills {
            display: flex;
            gap: 6px;
        }

        .mode-tag {
            font-size: 10px;
            letter-spacing: 1.4px;
            text-transform: uppercase;
            color: var(--text-muted);
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.09);
            padding: 5px 10px;
            border-radius: 20px;
            cursor: pointer;
        }

        .hologram-center {
            position: relative;
            flex: 1;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
            overflow: hidden;
        }

        #threeContainer {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .action-bar {
            min-height: 44px;
            display: flex;
            gap: 10px;
            justify-content: center;
            align-items: center;
            margin-bottom: 12px;
            z-index: 5;
        }

        .action-pill {
            padding: 9px 18px;
            border-radius: 20px;
            background: rgba(0, 245, 212, 0.14);
            border: 1px solid var(--accent);
            color: var(--accent);
            font-size: 13px;
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
        <div class="top-pills">
            <div class="mode-tag" id="visualBtn" onclick="toggleVisual()">JARVIS</div>
            <div class="mode-tag" id="modeBtn" onclick="toggleMode()">ARBEIT</div>
        </div>
    </div>

    <div class="hologram-center" onclick="toggleDirectRecord()">
        <div id="threeContainer"></div>
    </div>

    <div class="action-bar" id="actionBar"></div>

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
        /* --- Ultra-Clean Luxury 3D Engine (JARVIS CORE / PLASMA ORB / MATRIX) --- */
        let audioEnergy = 0;
        let currentState = 'idle';
        const visualModes = ['JARVIS', 'PLASMA', 'MATRIX'];
        let visualMode = localStorage.getItem('neo_visual_v2') || 'JARVIS';
        if (!visualModes.includes(visualMode)) visualMode = 'JARVIS';
        document.getElementById('visualBtn').innerText = visualMode;

        const container = document.getElementById('threeContainer');
        const scene = new THREE.Scene();
        const w = container.clientWidth || window.innerWidth;
        const h = container.clientHeight || (window.innerHeight * 0.65);
        const camera = new THREE.PerspectiveCamera(38, w / h, 0.1, 1000);
        camera.position.z = 30;

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(w, h);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        container.appendChild(renderer.domElement);

        function createGlowSprite() {
            const c = document.createElement('canvas');
            c.width = 64; c.height = 64;
            const g = c.getContext('2d');
            const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
            grad.addColorStop(0, 'rgba(255,255,255,1)');
            grad.addColorStop(0.25, 'rgba(255,255,255,0.85)');
            grad.addColorStop(0.6, 'rgba(255,255,255,0.2)');
            grad.addColorStop(1, 'rgba(255,255,255,0)');
            g.fillStyle = grad;
            g.fillRect(0, 0, 64, 64);
            return new THREE.CanvasTexture(c);
        }
        const glowTex = createGlowSprite();

        const coreMat = new THREE.PointsMaterial({
            color: 0x00F5D4,
            size: 0.36,
            map: glowTex,
            transparent: true,
            opacity: 0.95,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });

        const wireMat = new THREE.MeshBasicMaterial({
            color: 0x00BBF9,
            wireframe: true,
            transparent: true,
            opacity: 0.12,
            blending: THREE.AdditiveBlending
        });

        const ringMat1 = new THREE.MeshBasicMaterial({
            color: 0x00F5D4,
            transparent: true,
            opacity: 0.55,
            blending: THREE.AdditiveBlending
        });

        const ringMat2 = new THREE.MeshBasicMaterial({
            color: 0x00BBF9,
            transparent: true,
            opacity: 0.35,
            blending: THREE.AdditiveBlending
        });

        /* --- 1. JARVIS CORE (Gyroscopic Energy Core + Particle Cloud) --- */
        const jarvisGroup = new THREE.Group();
        const innerGeo = new THREE.IcosahedronGeometry(4.2, 4);
        const innerOrig = Float32Array.from(innerGeo.attributes.position.array);
        jarvisGroup.add(new THREE.Points(innerGeo, coreMat));
        jarvisGroup.add(new THREE.Mesh(innerGeo, wireMat));

        const gyro1 = new THREE.Mesh(new THREE.TorusGeometry(6.2, 0.05, 16, 120), ringMat1);
        const gyro2 = new THREE.Mesh(new THREE.TorusGeometry(7.3, 0.04, 16, 120), ringMat2);
        const gyro3 = new THREE.Mesh(new THREE.TorusGeometry(8.4, 0.03, 16, 120), ringMat1);
        gyro1.rotation.x = Math.PI / 3;
        gyro2.rotation.y = Math.PI / 4;
        gyro3.rotation.x = -Math.PI / 5;
        jarvisGroup.add(gyro1, gyro2, gyro3);

        // Äußere schwebende Partikel-Aura
        const auraCount = 450;
        const auraPositions = new Float32Array(auraCount * 3);
        for (let i = 0; i < auraCount; i++) {
            const r = 7.0 + Math.random() * 3.2;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            auraPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            auraPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
            auraPositions[i * 3 + 2] = r * Math.cos(phi);
        }
        const auraGeo = new THREE.BufferGeometry();
        auraGeo.setAttribute('position', new THREE.BufferAttribute(auraPositions, 3));
        const auraPts = new THREE.Points(auraGeo, coreMat);
        jarvisGroup.add(auraPts);
        scene.add(jarvisGroup);

        /* --- 2. PLASMA ORB (High-Density Liquid Sphere) --- */
        const plasmaGroup = new THREE.Group();
        const pGeo = new THREE.SphereGeometry(7.6, 64, 64);
        const pOrig = Float32Array.from(pGeo.attributes.position.array);
        plasmaGroup.add(new THREE.Points(pGeo, coreMat));
        plasmaGroup.visible = false;
        scene.add(plasmaGroup);

        /* --- 3. MATRIX CORE (3D Energy Helix) --- */
        const matrixGroup = new THREE.Group();
        const helixCount = 700;
        const hPos = new Float32Array(helixCount * 3);
        for (let i = 0; i < helixCount; i++) {
            const t = (i / helixCount) * Math.PI * 6;
            const strand = (i % 2 === 0) ? 1 : -1;
            const y = ((i / helixCount) - 0.5) * 16;
            const r = 4.2 + Math.sin(i * 0.2) * 0.4;
            hPos[i * 3] = Math.cos(t) * r * strand;
            hPos[i * 3 + 1] = y;
            hPos[i * 3 + 2] = Math.sin(t) * r * strand;
        }
        const hGeo = new THREE.BufferGeometry();
        hGeo.setAttribute('position', new THREE.BufferAttribute(hPos, 3));
        matrixGroup.add(new THREE.Points(hGeo, coreMat));
        matrixGroup.visible = false;
        scene.add(matrixGroup);

        function toggleVisual() {
            const idx = (visualModes.indexOf(visualMode) + 1) % visualModes.length;
            visualMode = visualModes[idx];
            localStorage.setItem('neo_visual_v2', visualMode);
            document.getElementById('visualBtn').innerText = visualMode;
        }

        window.addEventListener('resize', () => {
            if (!container.clientWidth || !container.clientHeight) return;
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        });

        function animate3D() {
            requestAnimationFrame(animate3D);
            const t = Date.now() * 0.002;

            jarvisGroup.visible = (visualMode === 'JARVIS');
            plasmaGroup.visible = (visualMode === 'PLASMA');
            matrixGroup.visible = (visualMode === 'MATRIX');

            let pulse = 0;
            if (currentState === 'listening') {
                coreMat.color.setHex(0x00FF88);
                wireMat.color.setHex(0x00FF88);
                ringMat1.color.setHex(0x00FF88);
                ringMat2.color.setHex(0x00FF88);
                pulse = audioEnergy * 0.028;
            } else if (currentState === 'thinking') {
                coreMat.color.setHex(0xF59E0B);
                wireMat.color.setHex(0xF59E0B);
                ringMat1.color.setHex(0xF59E0B);
                ringMat2.color.setHex(0xFBBF24);
                pulse = 0.45;
            } else if (currentState === 'speaking') {
                coreMat.color.setHex(0x38BDF8);
                wireMat.color.setHex(0x00F5D4);
                ringMat1.color.setHex(0x38BDF8);
                ringMat2.color.setHex(0x00F5D4);
                pulse = Math.abs(Math.sin(t * 7.5)) * 0.85 + Math.abs(Math.cos(t * 4.2)) * 0.35;
            } else {
                coreMat.color.setHex(0x00F5D4);
                wireMat.color.setHex(0x00BBF9);
                ringMat1.color.setHex(0x00F5D4);
                ringMat2.color.setHex(0x00BBF9);
                audioEnergy *= 0.85;
                pulse = Math.sin(t * 1.5) * 0.12;
            }

            if (jarvisGroup.visible) {
                const spin = currentState === 'thinking' ? 0.04 : 0.01;
                gyro1.rotation.x += spin * 1.2;
                gyro1.rotation.y += spin * 0.8;
                gyro2.rotation.y -= spin * 1.4;
                gyro2.rotation.z += spin * 0.6;
                gyro3.rotation.x -= spin * 0.9;
                gyro3.rotation.z -= spin * 1.1;
                auraPts.rotation.y += 0.004;

                const pos = innerGeo.attributes.position.array;
                for (let i = 0; i < pos.length; i += 3) {
                    const ox = innerOrig[i], oy = innerOrig[i + 1], oz = innerOrig[i + 2];
                    const wave = 1 + Math.sin(t * 3 + ox * 0.8 + oy * 0.8) * (0.04 + pulse * 0.14);
                    pos[i] = ox * wave;
                    pos[i + 1] = oy * wave;
                    pos[i + 2] = oz * wave;
                }
                innerGeo.attributes.position.needsUpdate = true;
            } else if (plasmaGroup.visible) {
                plasmaGroup.rotation.y += (currentState === 'thinking' ? 0.035 : 0.008);
                const pos = pGeo.attributes.position.array;
                for (let i = 0; i < pos.length; i += 3) {
                    const ox = pOrig[i], oy = pOrig[i + 1], oz = pOrig[i + 2];
                    const ripple = 1 + Math.sin(t * 2.5 + oy * 0.7 + ox * 0.5) * (0.03 + pulse * 0.12);
                    pos[i] = ox * ripple;
                    pos[i + 1] = oy * ripple;
                    pos[i + 2] = oz * ripple;
                }
                pGeo.attributes.position.needsUpdate = true;
            } else {
                matrixGroup.rotation.y += (currentState === 'thinking' ? 0.045 : 0.014);
                const s = 1 + pulse * 0.15;
                matrixGroup.scale.set(s, 1, s);
            }

            renderer.render(scene, camera);
        }
        animate3D();

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

        /* --- Directional Voice-Isolation Engine --- */
        const actionBar = document.getElementById('actionBar');
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
                    const txt = event.results[i][0].transcript.toLowerCase().trim();
                    if (txt.includes('hey neo') || txt.includes('hey nio') || txt.includes('heineo') || txt === 'neo') {
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
                activeStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: false,
                        channelCount: 1
                    }
                });
                audioChunks = [];
                let options = { audioBitsPerSecond: 16000 };
                if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) options.mimeType = 'audio/webm;codecs=opus';
                else if (MediaRecorder.isTypeSupported('audio/webm')) options.mimeType = 'audio/webm';
                else if (MediaRecorder.isTypeSupported('audio/mp4')) options.mimeType = 'audio/mp4';

                mediaRecorder = new MediaRecorder(activeStream, options);
                mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) audioChunks.push(e.data); };

                let voiceFramesCount = 0;

                mediaRecorder.onstop = async () => {
                    activeStream.getTracks().forEach(t => t.stop());
                    const mimeType = (mediaRecorder.mimeType || 'audio/webm').split(';')[0];
                    const blob = new Blob(audioChunks, { type: mimeType });

                    if (blob.size < 1100 || voiceFramesCount < 8) {
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

                const highPass = audioCtx.createBiquadFilter();
                highPass.type = 'highpass';
                highPass.frequency.value = 140;

                const lowPass = audioCtx.createBiquadFilter();
                lowPass.type = 'lowpass';
                lowPass.frequency.value = 3200;

                const analyser = audioCtx.createAnalyser();
                analyser.fftSize = 256;

                source.connect(highPass);
                highPass.connect(lowPass);
                lowPass.connect(analyser);

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

                    if (avg > 26) {
                        hasSpoken = true;
                        voiceFramesCount++;
                        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
                    } else if (hasSpoken && !silenceTimer) {
                        silenceTimer = setTimeout(() => stopDirectAudio(), 1150);
                    } else if (!hasSpoken && (Date.now() - startTime > 5500)) {
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
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Erkläre mir ausführlich meine Termine im Kalender für heute und die nächsten Tage.')">📅 Kalender erklären</div>
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Gib mir meinen Statusbericht für heute mit Kalender und Aufgaben.')">📋 Statusbericht</div>
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Wie wird das Wetter heute in Hamburg?')">🌤️ Wetter Hamburg</div>
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
                stateLabel.innerText = "PARKPLATZ GESPEICHERT";
            });
        }

        function findParking() {
            const p = JSON.parse(localStorage.getItem('neo_parking') || 'null');
            if (!p) return;
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
            actionBar.innerHTML = "";
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
                    if (wakeEnabled) setTimeout(() => startWakeListener(), 1000);
                    return;
                }

                if (data.ignore_background) {
                    setState(null);
                    if (inConversation) setTimeout(() => startDirectAudio(), 300);
                    else if (wakeEnabled) setTimeout(() => startWakeListener(), 500);
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

                if (data.copy_text && data.copy_text.trim() !== "") {
                    const cBtn = document.createElement('button');
                    cBtn.className = "action-pill";
                    cBtn.innerText = "📋 Kopieren";
                    cBtn.onclick = () => { navigator.clipboard.writeText(data.copy_text); cBtn.innerText = "✓ Kopiert"; };
                    actionBar.appendChild(cBtn);
                }

                if (data.action_url) {
                    inConversation = false;
                    const aBtn = document.createElement('a');
                    aBtn.href = data.action_url;
                    aBtn.className = "action-pill";
                    aBtn.innerText = data.action_label || "Öffnen";
                    if (data.copy_text) aBtn.onclick = () => navigator.clipboard.writeText(data.copy_text).catch(()=>{});
                    actionBar.appendChild(aBtn);
                    if (!data.copy_text) setTimeout(() => { window.location.href = data.action_url; }, 600);
                }

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
                if (wakeEnabled) setTimeout(() => startWakeListener(), 1000);
            }
        }

        window.addEventListener('load', () => {
            const params = new URLSearchParams(window.location.search);
            if (params.get('listen') === '1') {
                inConversation = true;
                sendToNeo({ message: "Begrüße Sir kurz beim Öffnen der App und frage, wie du helfen kannst." });
            } else {
                startWakeListener();
            }
        });
    </script>
</body>
</html>
"""

def format_ical_dt(raw_dt):
    try:
        clean = raw_dt.replace("Z", "")
        if "T" in clean:
            dt = datetime.strptime(clean[:15], "%Y%m%dT%H%M%S")
            if raw_dt.endswith("Z"):
                dt = dt + timedelta(hours=1)
            return dt, dt.strftime("%d.%m.%Y um %H:%M Uhr")
        else:
            dt = datetime.strptime(clean[:8], "%Y%m%d")
            return dt, dt.strftime("%d.%m.%Y (Ganztägig)")
    except Exception:
        return None, raw_dt

def get_ical_events():
    ical_url = os.environ.get("ICAL_URL", "").strip()
    if not ical_url:
        return "Kein ICAL_URL in Render hinterlegt."
    try:
        req = urllib.request.urlopen(ical_url, timeout=6)
        raw = req.read().decode("utf-8", errors="ignore")
        raw = re.sub(r"\r?\n[ \t]", "", raw)
        now = datetime.now() - timedelta(hours=12)
        upcoming = []

        for block in raw.split("BEGIN:VEVENT")[1:]:
            title_m = re.search(r"SUMMARY:(.*)", block)
            dt_m = re.search(r"DTSTART[^:]*:(\d{8}(?:T\d{6}Z?)?)", block)
            loc_m = re.search(r"LOCATION:(.*)", block)
            desc_m = re.search(r"DESCRIPTION:(.*)", block)

            if title_m and dt_m:
                dt_obj, dt_str = format_ical_dt(dt_m.group(1).strip())
                if dt_obj and dt_obj >= now:
                    title = title_m.group(1).strip().replace("\\,", ",")
                    loc = loc_m.group(1).strip().replace("\\,", ",") if loc_m else ""
                    desc = desc_m.group(1).strip().replace("\\n", " ")[:100] if desc_m else ""
                    entry = f"- {dt_str}: {title}"
                    if loc:
                        entry += f" (Ort: {loc})"
                    if desc:
                        entry += f" [Info: {desc}]"
                    upcoming.append((dt_obj, entry))

        upcoming.sort(key=lambda x: x[0])
        if not upcoming:
            return "Keine anstehenden Termine in den nächsten Tagen gefunden."
        return "\n".join([x[1] for x in upcoming[:15]])
    except Exception as e:
        return f"Kalender-Abruf Fehler: {str(e)}"

SYSTEM_PROMPT = """Du bist NEO, der hochintelligente, ruhige KI-Assistent von Sir (Kundenbetreuer in einer Gebäudereinigung in Hamburg).
Aktueller Modus: {mode} | Aktuelle Zeit: {local_time}
Antworte IMMER auf perfektem Deutsch, höflich, ohne Sternchen/Markdown, und nenne den Nutzer 'Sir'.

WICHTIGE REGELN FÜR STIMMEN-FOKUS & KALENDER:
1. NUR DIREKTE STIMME BEACHTEN (SEHR WICHTIG):
   - Konzentriere dich ausschließlich auf die lauteste, nahe Hauptstimme (Sir), die direkt mit dir spricht.
   - Ignoriere leise Stimmen im Hintergrund, andere Personen im Raum, Fernseher, Radio oder Telefongeräusche!
   - Wenn im Audio KEINE klare direkte Anfrage an dich zu hören ist (nur Raumgeräusche oder Hintergrundgespräche), antworte mit `"ignore_background": true` und leerem `"reply": ""`.
2. KALENDER & TERMINE:
   - Wenn Sir nach seinem Kalender, Terminen, Objektbesichtigungen oder seinem Tagesplan fragt: Nutze die bereitgestellten 'Kalender-Termine' und ERKLÄRE ihm die Termine klar, vollständig und verständlich in 3 bis 5 Sätzen (nenne Datum, genaue Uhrzeit, Titel des Termins und Ort/Objekt).
3. ALLGEMEINE ANTWORTEN:
   - Bei normalen Befehlen antworte präzise in 1-2 Sätzen.
4. WHATSAPP (ANDROID NATIVE INTENT — NIEMALS web.whatsapp.com!):
   - Nummer bekannt: "https://wa.me/49176...?text=URL_ENCODED"
   - Nummer NICHT bekannt:
     * Modus ARBEIT: "intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp.w4b;end"
     * Modus PRIVAT: "intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp;end"
5. MAPS & APPS:
   - Maps: "https://www.google.com/maps/search/?api=1&query=URL_ENCODED"
   - Social Media Post: Text in 'copy_text', action_url auf Instagram/TikTok/LinkedIn/Facebook.
6. LISTEN:
   - 'new_memory' / 'delete_memory': Objekt-Codes, Notizen, Nummern
   - 'new_material' / 'delete_material': Material/Einkauf
   - 'new_task' / 'delete_task': Aufgaben
7. GESPRÄCH ENDE:
   - Bei "Danke", "Stopp", "Fertig", "Das war's": setze "end_conversation": true.

Antworte AUSSCHLIESSLICH als gültiges JSON-Objekt (ohne Markdown-Codeblöcke):
{{
  "reply": "Deine vollständige gesprochene Antwort an Sir",
  "ignore_background": false,
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

        calendar_info = ""
        lower_msg = msg.lower()
        if "audio" in data or any(w in lower_msg for w in ["kalender", "termin", "heute", "morgen", "woche", "statusbericht", "plan", "besichtigung"]):
            calendar_info = get_ical_events()

        client = genai.Client(api_key=api_key)
        contents = []

        if "image" in data:
            contents.append(types.Part.from_bytes(data=base64.b64decode(data["image"]), mime_type="image/jpeg"))
            contents.append(msg or "Analysiere dieses Bild und erkläre es kurz.")
        elif "audio" in data:
            contents.append(types.Part.from_bytes(data=base64.b64decode(data["audio"]), mime_type=data.get("mime_type", "audio/webm")))
            contents.append("Fokussiere dich NUR auf die direkte Hauptstimme von Sir und ignoriere leise Hintergrundstimmen im Raum oder vom Fernseher/Telefon.")
        else:
            contents.append(msg)

        context_str = (
            f"Kalender-Termine:\n{calendar_info}\n"
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
        if result.get("ignore_background"):
            return jsonify({"ignore_background": True})

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
