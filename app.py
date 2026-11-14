import os
import re
import time
import json
import base64
import asyncio
import threading
import urllib.request
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, Response, send_file
from google import genai
from google.genai import types
import edge_tts

app = Flask(__name__)
ICAL_CACHE = {"ts": 0, "events": []}

PROACTIVE_STATE = {
    "chat_id": os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
    "last_update_id": 0,
    "notified_events": set(),
    "pending_action": None,
    "voice_alerts": []
}

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#020408"/>
  <circle cx="256" cy="256" r="180" fill="none" stroke="#00E5FF" stroke-width="4" stroke-dasharray="40 15 10 15"/>
  <circle cx="256" cy="256" r="130" fill="none" stroke="#FF9900" stroke-width="6" stroke-dasharray="20 10"/>
  <circle cx="256" cy="256" r="16" fill="#FF9900"/>
</svg>"""

HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#020408">
    <link rel="manifest" href="/manifest.json">
    <title>N.E.O. // TACTICAL CORE</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;800&family=Rajdhani:wght@500;600;700&display=swap');

        :root {
            --amber: #FF9900;
            --cyan: #00E5FF;
            --bg: #020408;
            --hud-bg: rgba(4, 10, 20, 0.78);
            --line: rgba(0, 229, 255, 0.22);
            --text: #E2F1FF;
            --dim: #4A6B82;
        }
        body.listening { --amber: #00FF88; }
        body.thinking  { --amber: #00E5FF; }
        body.speaking  { --amber: #FF9900; }

        * { box-sizing: border-box; user-select: none; -webkit-tap-highlight-color: transparent; }

        html, body {
            margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden;
            background: radial-gradient(circle at 50% 50%, #061326 0%, #020408 78%);
            color: var(--text);
            font-family: 'Rajdhani', sans-serif;
        }

        /* TECHNICAL BLUEPRINT GRID OVERLAY */
        .grid-overlay {
            position: fixed; inset: 0; pointer-events: none; z-index: 0;
            background-image:
                linear-gradient(rgba(0, 229, 255, 0.035) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 229, 255, 0.035) 1px, transparent 1px),
                linear-gradient(rgba(0, 229, 255, 0.015) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 229, 255, 0.015) 1px, transparent 1px);
            background-size: 100px 100px, 100px 100px, 20px 20px, 20px 20px;
        }

        #hudCanvas {
            position: fixed; inset: 0; width: 100vw; height: 100vh;
            z-index: 1; pointer-events: none;
        }

        /* TOP LEFT SYSTEM ARCHITECTURE HEADER */
        .hud-top-left {
            position: fixed; top: 22px; left: 26px; z-index: 10;
            border-left: 2px solid var(--amber);
            padding-left: 12px;
        }
        .sys-code {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px; letter-spacing: 3px; color: var(--cyan);
        }
        .sys-main {
            font-size: 26px; font-weight: 700; letter-spacing: 6px;
            color: #FFFFFF; line-height: 1.1; margin: 2px 0;
        }
        .sys-bar {
            display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap;
        }
        .tac-btn {
            background: var(--hud-bg);
            border: 1px solid var(--line);
            color: var(--cyan);
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px; letter-spacing: 1.5px;
            padding: 5px 10px; cursor: pointer;
            clip-path: polygon(6px 0, 100% 0, 100% calc(100% - 6px), calc(100% - 6px) 100%, 0 100%, 0 6px);
            transition: 0.15s;
        }
        .tac-btn:hover, .tac-btn.on {
            border-color: var(--amber);
            color: var(--amber);
            background: rgba(255, 153, 0, 0.08);
        }

        /* TOP RIGHT TELEMETRY & STREAM TERMINAL */
        .hud-top-right {
            position: fixed; top: 22px; right: 26px; width: 380px; max-width: 44vw;
            background: var(--hud-bg);
            border: 1px solid var(--line);
            border-right: 2px solid var(--amber);
            padding: 12px 16px; z-index: 10;
            clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 14px 100%, 0 calc(100% - 14px));
            backdrop-filter: blur(8px);
        }
        .term-header {
            display: flex; justify-content: space-between;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px; letter-spacing: 2px; color: var(--amber);
            border-bottom: 1px solid rgba(0, 229, 255, 0.15);
            padding-bottom: 5px; margin-bottom: 8px;
        }
        .term-output {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px; line-height: 1.55; color: var(--text);
            max-height: 140px; overflow-y: auto; user-select: text;
        }

        /* CENTER CORE INTERACTION ZONE */
        .core-zone {
            position: fixed; top: 47%; left: 50%; transform: translate(-50%, -50%);
            width: 190px; height: 190px; border-radius: 50%; z-index: 8;
            cursor: pointer; display: flex; flex-direction: column;
            align-items: center; justify-content: center; text-align: center;
        }
        .core-id {
            font-family: 'JetBrains Mono', monospace;
            font-size: 18px; font-weight: 800; letter-spacing: 6px;
            color: #FFF; text-shadow: 0 0 12px var(--amber);
        }
        .core-status {
            font-family: 'JetBrains Mono', monospace;
            font-size: 9px; letter-spacing: 2.5px; color: var(--amber);
            margin-top: 5px;
        }

        /* SCI-FI ARCHITECTURAL NODES (NO EMOJIS, PURE TECH HUD) */
        .sci-node {
            position: fixed; transform: translate(-50%, -50%); z-index: 7;
            background: rgba(3, 9, 18, 0.85);
            border: 1px solid rgba(0, 229, 255, 0.32);
            border-left: 2px solid var(--cyan);
            padding: 6px 14px;
            cursor: pointer;
            clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%);
            transition: 0.18s;
        }
        .sci-node:hover, .sci-node.active {
            border-color: var(--amber);
            border-left: 3px solid var(--amber);
            box-shadow: 0 0 20px rgba(255, 153, 0, 0.25);
            transform: translate(-50%, -50%) scale(1.06);
        }
        .node-code {
            font-family: 'JetBrains Mono', monospace;
            font-size: 8.5px; letter-spacing: 2px; color: var(--dim);
            display: block;
        }
        .sci-node:hover .node-code, .sci-node.active .node-code { color: var(--amber); }
        .node-name {
            font-size: 13px; font-weight: 700; letter-spacing: 2px;
            color: #FFFFFF; text-transform: uppercase;
        }

        /* FLOATING HOLOGRAM DATA WINDOW */
        .holo-win {
            position: fixed; top: 47%; left: 50%; transform: translate(-50%, -50%);
            width: 500px; max-width: 92vw;
            background: rgba(3, 8, 17, 0.96);
            border: 1px solid var(--cyan);
            border-top: 2px solid var(--amber);
            padding: 18px; z-index: 30;
            display: none; flex-direction: column; gap: 12px;
            clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 16px 100%, 0 calc(100% - 16px));
            box-shadow: 0 0 60px rgba(0, 0, 0, 0.9);
        }
        .holo-win.open { display: flex; }
        .holo-bar {
            display: flex; justify-content: space-between; align-items: center;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px; letter-spacing: 2px; color: var(--amber);
            border-bottom: 1px solid var(--line); padding-bottom: 8px;
        }
        .holo-list { max-height: 280px; overflow-y: auto; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
        .holo-item {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 10px; border-left: 2px solid var(--cyan);
            background: rgba(0, 229, 255, 0.04); margin-bottom: 6px;
        }

        /* BOTTOM COMMAND TERMINAL */
        .bottom-console {
            position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
            width: 620px; max-width: 94vw; z-index: 12;
            display: flex; flex-direction: column; gap: 8px; align-items: center;
        }
        .act-links { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
        .amber-link {
            background: rgba(255, 153, 0, 0.15); border: 1px solid var(--amber);
            color: var(--amber); font-family: 'JetBrains Mono', monospace;
            font-size: 11px; letter-spacing: 1.5px; padding: 6px 14px;
            text-decoration: none; cursor: pointer; text-transform: uppercase;
        }
        .cmd-frame {
            width: 100%; background: var(--hud-bg);
            border: 1px solid var(--line); border-left: 3px solid var(--amber);
            padding: 6px 10px; display: flex; align-items: center; gap: 10px;
            clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 0 100%);
        }
        .cmd-prefix {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px; color: var(--amber); font-weight: 700;
        }
        .cmd-frame input {
            flex: 1; background: transparent; border: none; color: #FFF;
            font-family: 'JetBrains Mono', monospace; font-size: 12.5px;
            outline: none; user-select: text;
        }

        @media (max-width: 768px) {
            .hud-top-right { top: auto; bottom: 78px; right: 12px; left: 12px; width: auto; max-width: none; }
            .sci-node { padding: 4px 9px; }
            .node-name { font-size: 11px; }
        }
    </style>
</head>
<body>
    <div class="grid-overlay"></div>
    <canvas id="hudCanvas"></canvas>

    <!-- TOP LEFT ARCHITECTURE -->
    <div class="hud-top-left">
        <div class="sys-code">SYS.NODE // 040-HAMBURG</div>
        <div class="sys-main">N.E.O. CORE</div>
        <div class="sys-code" id="telemetryClock">SYNCING TELEMETRY...</div>
        <div class="sys-bar">
            <button type="button" class="tac-btn on" id="wBtn" onclick="toggleWake()">[VOICE_LOOP: ON]</button>
            <button type="button" class="tac-btn" id="mBtn" onclick="toggleMode()">[MODE: ARBEIT]</button>
            <button type="button" class="tac-btn" onclick="openHolo('calendar')">[SCHEDULE]</button>
            <button type="button" class="tac-btn" onclick="openHolo('codes')">[VAULT: <span id="nCount">0</span>]</button>
        </div>
    </div>

    <!-- TOP RIGHT STREAM -->
    <div class="hud-top-right">
        <div class="term-header">
            <span>// NEURAL_STREAM_LOG</span>
            <span id="streamStatus">ONLINE</span>
        </div>
        <div class="term-output" id="replyBox">STANDING ORDERS ACTIVE. AWAITING VOICE INPUT ("HEY NEO") OR NODE EXECUTION.</div>
    </div>

    <!-- CENTER REACTOR -->
    <div class="core-zone" onclick="manualListenTrigger()">
        <div class="core-id">N.E.O.</div>
        <div class="core-status" id="coreState">LISTENING_LOOP</div>
    </div>

    <!-- NODES LAYER -->
    <div id="nodesLayer"></div>

    <!-- HOLO WINDOW -->
    <div class="holo-win" id="holoModal">
        <div class="holo-bar">
            <span id="holoTitle">// DATA_MODULE</span>
            <button type="button" class="tac-btn" onclick="closeHolo()">[CLOSE_X]</button>
        </div>
        <div class="holo-list" id="holoBody"></div>
    </div>

    <!-- BOTTOM TERMINAL -->
    <div class="bottom-console">
        <div class="act-links" id="actBar"></div>
        <div class="cmd-frame">
            <span class="cmd-prefix">NEO&gt;</span>
            <input type="text" id="msg" placeholder="EXECUTE DIRECTIVE OR TRANSLATION..." onkeydown="if(event.key==='Enter')sendTxt()">
            <button type="button" class="tac-btn on" onclick="manualListenTrigger()">[MIC]</button>
            <button type="button" class="tac-btn" onclick="sendTxt()">[EXEC]</button>
        </div>
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
                osc.frequency.exponentialRampToValueAtTime(f2, ac.currentTime + 0.10);
                g.gain.setValueAtTime(0.10, ac.currentTime);
                g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.12);
                osc.start(); osc.stop(ac.currentTime + 0.13);
            } catch(e){}
        }

        // --- 1. ARCHITECTURAL NODES (PURE SCI-FI LABELS) ---
        const NODES = [
            { id: 'brief',    code: 'MOD.01 // BRIEFING', label: 'MORNING BRIEF',   rx: 0.21, ry: 0.24, action: () => quickCmd('Gib mir mein komplettes Morning Briefing mit Terminen heute und wichtigen Objekt-Codes.') },
            { id: 'calendar', code: 'MOD.02 // TIMELINE', label: 'CALENDAR SYNC',   rx: 0.14, ry: 0.46, action: () => openHolo('calendar') },
            { id: 'navi',     code: 'MOD.03 // ROUTING',  label: 'AUTO DISPATCH',   rx: 0.20, ry: 0.68, action: () => quickCmd('Ich fahre los zum nächsten Termin. Gib mir das Briefing mit Codes und starte Navigation.') },
            { id: 'codes',    code: 'MOD.04 // SECURITY', label: 'OBJECT VAULT',    rx: 0.33, ry: 0.80, action: () => openHolo('codes') },
            { id: 'offer',    code: 'MOD.05 // FINANCE',  label: 'QUOTE ENGINE',    rx: 0.79, ry: 0.24, action: () => openHolo('calc') },
            { id: 'camera',   code: 'MOD.06 // OPTICS',   label: 'DEFECT VISION',   rx: 0.86, ry: 0.46, action: () => document.getElementById('cam').click() },
            { id: 'trans',    code: 'MOD.07 // LINGUIST', label: 'TRANSLATOR DE/SQ',rx: 0.80, ry: 0.68, action: () => { const i = document.getElementById('msg'); i.focus(); i.value = 'Übersetze ins Albanische: '; } },
            { id: 'telegram', code: 'MOD.08 // REMOTE',   label: 'TELEGRAM AUTH',   rx: 0.67, ry: 0.80, action: () => sendTg() }
        ];

        const nodesLayer = document.getElementById('nodesLayer');
        NODES.forEach(n => {
            const el = document.createElement('div');
            el.className = 'sci-node';
            el.id = 'node-' + n.id;
            el.style.left = (n.rx * 100) + '%';
            el.style.top = (n.ry * 100) + '%';
            el.innerHTML = `<span class="node-code">${n.code}</span><span class="node-name">${n.label}</span>`;
            el.onclick = () => {
                document.querySelectorAll('.sci-node').forEach(e => e.classList.remove('active'));
                el.classList.add('active');
                n.action();
            };
            nodesLayer.appendChild(el);
        });

        // --- 2. HIGH-END SCI-FI CANVAS (CONSTELLATION MESH + FREQUENCY EQUALIZER CORE) ---
        const canvas = document.getElementById('hudCanvas');
        const ctx = canvas.getContext('2d');
        let W = window.innerWidth, H = window.innerHeight;
        function resizeCanvas() { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; }
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        // Ambient floating neural particles in background
        const bgDots = Array.from({length: 48}, () => ({
            x: Math.random() * W,
            y: Math.random() * H,
            vx: (Math.random() - 0.5) * 0.35,
            vy: (Math.random() - 0.5) * 0.35
        }));

        let coreStateMode = 'idle', tTick = 0;
        const packets = NODES.map((_, i) => ({ p: (i * 0.14) % 1, s: 0.0045 + (i % 3) * 0.001 }));

        function renderHUD() {
            ctx.clearRect(0, 0, W, H);
            const cx = W * 0.5, cy = H * 0.47;

            let priRGB = '255, 153, 0'; // Amber
            let secRGB = '0, 229, 255'; // Cyan
            let energy = 1;

            if (coreStateMode === 'listening') { priRGB = '0, 255, 136'; energy = 2.4; }
            else if (coreStateMode === 'thinking') { priRGB = '0, 229, 255'; energy = 3.5; }
            else if (coreStateMode === 'speaking') { priRGB = '255, 153, 0'; energy = 3.0; }

            tTick += 0.02 * energy;

            // A. Ambient Constellation Mesh
            for (let i = 0; i < bgDots.length; i++) {
                const d = bgDots[i];
                d.x += d.vx; d.y += d.vy;
                if (d.x < 0 || d.x > W) d.vx *= -1;
                if (d.y < 0 || d.y > H) d.vy *= -1;

                ctx.fillStyle = `rgba(${secRGB}, 0.35)`;
                ctx.fillRect(d.x - 1, d.y - 1, 2, 2);

                for (let j = i + 1; j < bgDots.length; j++) {
                    const d2 = bgDots[j];
                    const dist = Math.hypot(d.x - d2.x, d.y - d2.y);
                    if (dist < 130) {
                        ctx.strokeStyle = `rgba(${secRGB}, ${(1 - dist / 130) * 0.12})`;
                        ctx.lineWidth = 0.8;
                        ctx.beginPath(); ctx.moveTo(d.x, d.y); ctx.lineTo(d2.x, d2.y); ctx.stroke();
                    }
                }
            }

            // B. Angled Circuit Traces from Core to Primary Nodes + Sub-nodes
            NODES.forEach((n, idx) => {
                const nx = W * n.rx, ny = H * n.ry;
                // Orthogonal / 45-degree sci-fi circuit bend
                const bendX = cx + (nx - cx) * 0.55;
                const bendY = cy + (ny - cy) * 0.25;

                ctx.beginPath();
                ctx.moveTo(cx, cy);
                ctx.lineTo(bendX, bendY);
                ctx.lineTo(nx, ny);
                ctx.strokeStyle = `rgba(${secRGB}, 0.28)`;
                ctx.lineWidth = 1.2;
                ctx.stroke();

                // Corner junction micro-node
                ctx.fillStyle = `rgba(${secRGB}, 0.7)`;
                ctx.fillRect(bendX - 2, bendY - 2, 4, 4);

                // Data pulse traveling along the circuit path
                const pk = packets[idx];
                pk.p += pk.s * energy;
                if (pk.p > 1) pk.p = 0;
                let px, py;
                if (pk.p < 0.5) {
                    const lt = pk.p * 2;
                    px = cx + (bendX - cx) * lt;
                    py = cy + (bendY - cy) * lt;
                } else {
                    const lt = (pk.p - 0.5) * 2;
                    px = bendX + (nx - bendX) * lt;
                    py = bendY + (ny - bendY) * lt;
                }
                ctx.beginPath();
                ctx.arc(px, py, 2.6, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(${priRGB}, 0.95)`;
                ctx.fill();
            });

            // C. Central APEX-Style Multi-Ring Frequency Core
            const baseR = 84;

            // Core Radial Glow
            const g = ctx.createRadialGradient(cx, cy, 10, cx, cy, baseR + 90);
            g.addColorStop(0, `rgba(${priRGB}, 0.24)`);
            g.addColorStop(0.5, `rgba(${secRGB}, 0.06)`);
            g.addColorStop(1, 'rgba(2, 4, 8, 0)');
            ctx.fillStyle = g;
            ctx.beginPath(); ctx.arc(cx, cy, baseR + 90, 0, Math.PI * 2); ctx.fill();

            // Outer Telemetry Degree Ring
            ctx.save();
            ctx.translate(cx, cy);
            ctx.rotate(tTick * 0.2);
            ctx.strokeStyle = `rgba(${secRGB}, 0.35)`;
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 8, 22, 8]);
            ctx.beginPath(); ctx.arc(0, 0, baseR + 38, 0, Math.PI * 2); ctx.stroke();
            ctx.restore();

            // Radial Audio Frequency Bars (64 bars around the core)
            const numBars = 64;
            ctx.save();
            ctx.translate(cx, cy);
            for (let i = 0; i < numBars; i++) {
                const ang = (i / numBars) * Math.PI * 2 + tTick * 0.15;
                const wave = coreStateMode === 'idle'
                    ? 4 + Math.sin(i * 0.5 + tTick * 2) * 3
                    : 6 + Math.abs(Math.sin(i * 0.7 + tTick * 5)) * 22;
                const r1 = baseR + 4;
                const r2 = r1 + wave;
                ctx.strokeStyle = i % 2 === 0 ? `rgba(${priRGB}, 0.85)` : `rgba(${secRGB}, 0.65)`;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(Math.cos(ang) * r1, Math.sin(ang) * r1);
                ctx.lineTo(Math.cos(ang) * r2, Math.sin(ang) * r2);
                ctx.stroke();
            }
            ctx.restore();

            // Counter-Rotating Heavy Segmented Amber Ring
            ctx.save();
            ctx.translate(cx, cy);
            ctx.rotate(-tTick * 0.45);
            ctx.strokeStyle = `rgba(${priRGB}, 0.9)`;
            ctx.lineWidth = 3.5;
            ctx.setLineDash([32, 14, 8, 14]);
            ctx.beginPath(); ctx.arc(0, 0, baseR - 6, 0, Math.PI * 2); ctx.stroke();
            ctx.restore();

            // Inner Dark Core Shield
            ctx.beginPath();
            ctx.arc(cx, cy, baseR - 16, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(2, 6, 14, 0.92)';
            ctx.fill();
            ctx.strokeStyle = `rgba(${secRGB}, 0.5)`;
            ctx.lineWidth = 1.5;
            ctx.stroke();

            requestAnimationFrame(renderHUD);
        }
        renderHUD();

        // --- 3. TELEMETRY & DATA WINDOWS ---
        let cachedEvents = [], weatherStr = "HAMBURG";
        function updateTelemetry() {
            const now = new Date();
            document.getElementById('telemetryClock').innerText = `${weatherStr} // ${now.toLocaleTimeString('de-DE')} CET`;
        }
        updateTelemetry(); setInterval(updateTelemetry, 1000);

        fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true')
            .then(r => r.json()).then(d => { if (d.current_weather) weatherStr = `HH ${Math.round(d.current_weather.temperature)}°C`; }).catch(()=>{});

        fetch('/calendar_preview').then(r => r.json()).then(d => { cachedEvents = d.events || []; }).catch(()=>{});

        let mem = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        let mode = localStorage.getItem('neo_mode') || 'ARBEIT';
        const player = document.getElementById('player');

        function saveState() {
            localStorage.setItem('neo_memory', JSON.stringify(mem));
            localStorage.setItem('neo_mode', mode);
            document.getElementById('mBtn').innerText = `[MODE: ${mode}]`;
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
                title.innerText = '// SCHEDULE_MATRIX (ICAL)';
                body.innerHTML = cachedEvents.length
                    ? cachedEvents.map(e => `<div class="holo-item"><div><div style="color:var(--amber);font-size:10px;">${e.time}</div><div style="font-weight:700;">${e.title}</div><div style="color:var(--dim);font-size:10px;">${e.loc || ''}</div></div></div>`).join('')
                    : '<div style="color:var(--dim);">NO UPCOMING EVENTS DETECTED.</div>';
            } else if (type === 'codes') {
                title.innerText = `// OBJECT_VAULT (${mem.length})`;
                const listHtml = mem.length
                    ? mem.map((x, i) => `<div class="holo-item"><span>${x}</span><button type="button" class="tac-btn on" onclick="mem.splice(${i},1);saveState();openHolo('codes');">[DEL]</button></div>`).join('')
                    : '<div style="color:var(--dim);margin-bottom:10px;">VAULT EMPTY.</div>';
                body.innerHTML = `
                    <div style="display:flex;gap:6px;margin-bottom:12px;">
                        <input id="newCodeInp" type="text" placeholder="ENTER OBJECT CODE / KEY INFO..." style="flex:1;background:#020408;border:1px solid var(--line);color:#fff;padding:8px;font-family:'JetBrains Mono',monospace;font-size:11px;">
                        <button type="button" class="tac-btn on" onclick="const v=document.getElementById('newCodeInp').value.trim();if(v){mem.push(v);saveState();openHolo('codes');}">[+STORE]</button>
                    </div>` + listHtml;
            } else if (type === 'calc') {
                title.innerText = '// QUOTE_CALCULATOR (31.50 EUR/H)';
                body.innerHTML = `
                    <div style="display:flex;flex-direction:column;gap:10px;">
                        <input id="cQm" type="number" placeholder="AREA IN SQM (600)" value="600" style="background:#020408;border:1px solid var(--line);color:#fff;padding:9px;font-family:'JetBrains Mono',monospace;">
                        <select id="cFreq" style="background:#020408;border:1px solid var(--line);color:#fff;padding:9px;font-family:'JetBrains Mono',monospace;">
                            <option value="1x pro Woche">1x / WEEK</option>
                            <option value="2x pro Woche" selected>2x / WEEK</option>
                            <option value="3x pro Woche">3x / WEEK</option>
                            <option value="5x pro Woche">5x / WEEK</option>
                        </select>
                        <button type="button" class="tac-btn on" style="padding:10px;" onclick="const q=document.getElementById('cQm').value||600;const f=document.getElementById('cFreq').value;closeHolo();quickCmd('Kalkuliere ein Reinigungsangebot für '+q+' Quadratmeter Büro, '+f+', und sende mir das Angebot zur Autorisierung auf Telegram.');">[COMPUTE & REQUEST AUTH]</button>
                    </div>`;
            }
        }
        function closeHolo() { document.getElementById('holoModal').classList.remove('open'); }

        function setSt(s) {
            coreStateMode = s || 'idle';
            document.body.className = s || '';
            const cSt = document.getElementById('coreState');
            const sSt = document.getElementById('streamStatus');
            if (s === 'listening') { cSt.innerText = 'VOICE_CAPTURE'; sSt.innerText = 'RECEIVING AUDIO'; }
            else if (s === 'thinking') { cSt.innerText = 'COMPUTING'; sSt.innerText = 'PROCESSING'; }
            else if (s === 'speaking') { cSt.innerText = 'VOICE_OUTPUT'; sSt.innerText = 'TRANSMITTING'; }
            else { cSt.innerText = activeSession ? 'DIALOG_OPEN' : 'LISTENING_LOOP'; sSt.innerText = 'ONLINE'; }
        }

        // --- 4. HANDS-FREE VOICE + PROACTIVE POLLING ---
        let wakeOn = true, activeSession = false, isBusy = false, srInstance = null;

        function toggleWake() {
            wakeOn = !wakeOn;
            const b = document.getElementById('wBtn');
            if (wakeOn) {
                b.innerText = '[VOICE_LOOP: ON]'; b.classList.add('on');
                startAlwaysListening();
            } else {
                b.innerText = '[VOICE_LOOP: OFF]'; b.classList.remove('on');
                activeSession = false;
                if (srInstance) { try { srInstance.onend = null; srInstance.abort(); } catch(e){} srInstance = null; }
                setSt(null);
            }
        }

        function manualListenTrigger() {
            if (isBusy) { player.pause(); isBusy = false; }
            activeSession = true;
            beep(560, 960);
            setSt('listening');
            document.getElementById('replyBox').innerText = ">> DIRECT AUDIO CHANNEL OPEN. SPEAK NOW, MARGIL...";
            if (!srInstance) startAlwaysListening();
        }

        function startAlwaysListening() {
            if (!wakeOn || isBusy) return;
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SR) return;
            if (srInstance) { try { srInstance.onend = null; srInstance.abort(); } catch(e){} srInstance = null; }

            srInstance = new SR();
            srInstance.lang = 'de-DE';
            srInstance.continuous = true;
            srInstance.interimResults = true;

            srInstance.onresult = (event) => {
                if (isBusy) return;
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const raw = event.results[i][0].transcript.trim();
                    const low = raw.toLowerCase();

                    if (!event.results[i].isFinal) {
                        if (activeSession || low.includes('neo') || low.includes('nio')) {
                            setSt('listening');
                            document.getElementById('replyBox').innerText = ">> INPUT: " + raw.toUpperCase() + " ...";
                        }
                        continue;
                    }

                    const wakeMatch = low.match(/\b(hey neo|hey nio|hallo neo|ok neo|neo)\b/);
                    if (wakeMatch) {
                        const idx = low.indexOf(wakeMatch[0]) + wakeMatch[0].length;
                        const cmd = raw.slice(idx).replace(/^[,.\s]+/, '').trim();
                        activeSession = true;
                        beep(660, 920);
                        if (cmd.length > 2) {
                            processVoiceText(cmd);
                        } else {
                            setSt('listening');
                            document.getElementById('replyBox').innerText = ">> STANDING BY, MARGIL. STATE YOUR DIRECTIVE.";
                        }
                        return;
                    } else if (activeSession && raw.length > 1) {
                        beep(660, 920);
                        processVoiceText(raw);
                        return;
                    }
                }
            };

            srInstance.onend = () => { srInstance = null; if (wakeOn && !isBusy) setTimeout(startAlwaysListening, 250); };
            srInstance.onerror = () => { srInstance = null; if (wakeOn && !isBusy) setTimeout(startAlwaysListening, 600); };
            try { srInstance.start(); } catch(e) { srInstance = null; }
        }

        function processVoiceText(spokenText) {
            isBusy = true;
            if (srInstance) { try { srInstance.onend = null; srInstance.abort(); } catch(e){} srInstance = null; }
            setSt('thinking');
            sendNeo({ message: spokenText });
        }

        async function checkProactiveAlerts() {
            if (isBusy) return;
            try {
                const res = await fetch('/proactive_poll');
                const data = await res.json();
                if (data.alert && data.alert.text) {
                    isBusy = true;
                    if (srInstance) { try { srInstance.onend = null; srInstance.abort(); } catch(e){} srInstance = null; }
                    beep(740, 1120);
                    document.getElementById('replyBox').innerText = "// PROACTIVE_ALERT: " + data.alert.text;

                    if (data.alert.action_url) {
                        document.getElementById('actBar').innerHTML = '';
                        const a = document.createElement('a');
                        a.href = data.alert.action_url; a.target = '_blank'; a.className = 'amber-link';
                        a.innerText = `[${data.alert.action_label || 'EXECUTE'}]`;
                        document.getElementById('actBar').appendChild(a);
                    }

                    if (data.alert.audio) {
                        player.src = "data:audio/mp3;base64," + data.alert.audio;
                        player.play().catch(() => { isBusy = false; setSt(null); if (wakeOn) startAlwaysListening(); });
                    } else {
                        isBusy = false; if (wakeOn) startAlwaysListening();
                    }
                }
            } catch (e) {}
        }
        setInterval(checkProactiveAlerts, 12000);

        player.onplay = () => { isBusy = true; setSt('speaking'); };
        player.onended = () => { isBusy = false; setSt(activeSession ? 'listening' : null); if (wakeOn) setTimeout(startAlwaysListening, 250); };
        player.onerror = () => { isBusy = false; setSt(null); if (wakeOn) setTimeout(startAlwaysListening, 350); };

        async function sendTg() {
            document.getElementById('replyBox').innerText = ">> TRANSMITTING AUTHORIZATION REQUEST TO TELEGRAM...";
            try {
                const r = await fetch('/telegram_notify', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({text:"🔔 N.E.O. AUTHORIZATION REQUIRED:\nMargil, bitte bestätige die Freigabe für das nächste Objekt-Briefing."})
                });
                const d = await r.json();
                document.getElementById('replyBox').innerText = d.ok ? ">> TELEGRAM PACKET DISPATCHED. AWAITING REMOTE APPROVAL." : (">> ERROR: " + (d.error || "TELEGRAM LINK FAILED"));
            } catch(e) { document.getElementById('replyBox').innerText = ">> TELEGRAM CONNECTION ERROR."; }
        }

        function handleImg(ev) {
            const f = ev.target.files[0]; if (!f) return;
            isBusy = true; setSt('thinking');
            const r = new FileReader();
            r.onload = e => sendNeo({ image: e.target.result.split(',')[1], message: "Erstelle einen professionellen Objekt-Mängelbericht und frage nach meiner Autorisierung für den Versand." });
            r.readAsDataURL(f);
        }

        function quickCmd(t) { isBusy = true; setSt('thinking'); sendNeo({ message: t }); }
        function sendTxt() {
            const inp = document.getElementById('msg');
            if (!inp.value.trim()) return;
            const v = inp.value.trim(); inp.value = '';
            isBusy = true; setSt('thinking'); sendNeo({ message: v });
        }

        async function sendNeo(payload) {
            document.getElementById('actBar').innerHTML = '';
            document.getElementById('replyBox').innerText = ">> PROCESSING DIRECTIVE: " + (payload.message || "DATA_PACKET").toUpperCase();
            payload.mode = mode; payload.memory = mem; payload.local_time_str = new Date().toLocaleString('de-DE');

            try {
                const res = await fetch('/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
                const d = await res.json();
                if (d.error) {
                    isBusy = false; setSt(null);
                    document.getElementById('replyBox').innerText = ">> SYS_ERR: " + d.error;
                    if (wakeOn) startAlwaysListening();
                    return;
                }
                if (d.end_conversation) activeSession = false;
                if (d.new_memory) { mem.push(d.new_memory); saveState(); }
                document.getElementById('replyBox').innerText = d.reply;

                if (d.copy_text) {
                    const b = document.createElement('button'); b.type = 'button'; b.className = 'amber-link'; b.innerText = '[COPY_PAYLOAD]';
                    b.onclick = () => { navigator.clipboard.writeText(d.copy_text); b.innerText = '[COPIED_OK]'; };
                    document.getElementById('actBar').appendChild(b);
                }
                if (d.action_url) {
                    let finalUrl = d.action_url;
                    if (!isMobile && finalUrl.startsWith('intent://')) {
                        const m = finalUrl.match(/text=([^#&]+)/);
                        finalUrl = 'https://wa.me/?text=' + (m ? m[1] : '');
                    }
                    const a = document.createElement('a'); a.href = finalUrl; a.target = '_blank'; a.className = 'amber-link'; a.innerText = `[${d.action_label || 'OPEN_LINK'}]`;
                    document.getElementById('actBar').appendChild(a);
                }
                if (d.audio) {
                    player.src = "data:audio/mp3;base64," + d.audio;
                    player.play().catch(() => { isBusy = false; setSt(null); if (wakeOn) startAlwaysListening(); });
                } else {
                    isBusy = false; setSt(null); if (wakeOn) startAlwaysListening();
                }
            } catch(e) {
                isBusy = false; setSt(null);
                document.getElementById('replyBox').innerText = ">> NETWORK FAILURE.";
                if (wakeOn) startAlwaysListening();
            }
        }

        window.addEventListener('load', startAlwaysListening);
    </script>
</body>
</html>"""

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
                        "dt_iso": dt.isoformat(),
                        "time": dt.strftime("%d.%m. %H:%M") if "T" in clean else dt.strftime("%d.%m."),
                        "title": tm.group(1).strip().replace("\\n", " ").replace("\\,", ","),
                        "loc": lm.group(1).strip().replace("\\n", " ") if lm else ""
                    }))
        out.sort(key=lambda x: x[0])
        ICAL_CACHE["ts"] = now_ts
        ICAL_CACHE["events"] = [x[1] for x in out[:12]]
        return ICAL_CACHE["events"]
    except Exception:
        return ICAL_CACHE["events"]

SYSTEM_PROMPT = """Du bist NEO, der autonome taktische KI-Assistent von Margil (Kundenbetreuer Gebäudereinigung Hamburg).
Modus: {mode} | Zeit: {local_time}. Antworte präzise, souverän, ohne Markdown/Sternchen.
- WICHTIG (AUTORISIERUNG): Wenn es um ein Angebot, einen Mängelbericht oder eine Freigabe geht, fülle `telegram_auth_request` mit einer Zusammenfassung für Telegram aus.
- Morning Brief / Auto-Briefing: Nächste Termine + Codes aus Notizen + Google Maps URL in `action_url` (`action_label`: "ROUTE STARTEN").
- Dolmetscher DE <-> SQ: Bei Übersetzung ins Albanische `voice_lang`: "sq" und Übersetzung in `copy_text`, sonst "de".
- Kalkulator: Büro ~220 m²/Std, 31,50 €/Std netto (4,33 Wochen/Monat). Fertiges Angebot in `copy_text` + WhatsApp URL (`https://wa.me/?text=URL_ENCODED`, `action_label`: "WHATSAPP SENDEN").
- Gespräch Ende ("Danke", "Stopp", "Pause"): `end_conversation`: true.
Antworte NUR als JSON:
{{"reply":"","voice_lang":"de","copy_text":"","telegram_auth_request":"","new_memory":"","action_url":"","action_label":"","end_conversation":false}}"""

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

def tg_call(method, payload=None):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        if payload:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

def send_tg_authorization(text, action_meta=None):
    cid = PROACTIVE_STATE.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not cid:
        u = tg_call("getUpdates")
        if u and u.get("result"):
            for item in reversed(u["result"]):
                if "message" in item:
                    cid = str(item["message"]["chat"]["id"])
                    PROACTIVE_STATE["chat_id"] = cid
                    break
    if not cid:
        return False
    if action_meta:
        PROACTIVE_STATE["pending_action"] = action_meta
    res = tg_call("sendMessage", {
        "chat_id": cid,
        "text": text,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ Autorisieren", "callback_data": "auth_approve"},
                {"text": "❌ Ablehnen", "callback_data": "auth_reject"}
            ]]
        }
    })
    return bool(res and res.get("ok"))

def queue_voice_alert(text, action_url="", action_label=""):
    try:
        audio_b64 = asyncio.run(make_voice(text, "de"))
    except Exception:
        audio_b64 = ""
    PROACTIVE_STATE["voice_alerts"].append({
        "text": text,
        "audio": audio_b64,
        "action_url": action_url,
        "action_label": action_label
    })

def autonomous_guardian_loop():
    while True:
        time.sleep(15)
        try:
            updates = tg_call("getUpdates", {"offset": PROACTIVE_STATE["last_update_id"] + 1, "timeout": 2})
            if updates and updates.get("ok"):
                for upd in updates.get("result", []):
                    PROACTIVE_STATE["last_update_id"] = upd["update_id"]
                    if "callback_query" in upd:
                        cb = upd["callback_query"]
                        cid = str(cb["message"]["chat"]["id"])
                        PROACTIVE_STATE["chat_id"] = cid
                        data_cb = cb.get("data", "")
                        tg_call("answerCallbackQuery", {"callback_query_id": cb["id"]})
                        pending = PROACTIVE_STATE.get("pending_action") or {}
                        if data_cb == "auth_approve":
                            tg_call("sendMessage", {"chat_id": cid, "text": "✅ Autorisierung bestätigt, Margil."})
                            spoken = pending.get("approve_speech", "Margil, deine Autorisierung über Telegram ist eingegangen. Ich habe die Aktion freigegeben.")
                            queue_voice_alert(spoken, pending.get("action_url", ""), pending.get("action_label", "OPEN"))
                            PROACTIVE_STATE["pending_action"] = None
                        elif data_cb == "auth_reject":
                            tg_call("sendMessage", {"chat_id": cid, "text": "❌ Vorgang abgelehnt."})
                            queue_voice_alert("Margil, du hast den Vorgang über Telegram abgelehnt.")
                            PROACTIVE_STATE["pending_action"] = None
                    elif "message" in upd:
                        msg = upd["message"]
                        cid = str(msg["chat"]["id"])
                        PROACTIVE_STATE["chat_id"] = cid
                        txt = msg.get("text", "").strip()
                        if txt.lower() in ["/start", "hallo", "hi"]:
                            tg_call("sendMessage", {"chat_id": cid, "text": f"N.E.O. Tactical Link aktiv. Chat-ID: {cid}"})
                        elif txt:
                            tg_call("sendMessage", {"chat_id": cid, "text": f"Befehl übertragen: {txt}"})
                            queue_voice_alert(f"Margil, neue Nachricht über Telegram: {txt}")

            events = parse_upcoming_events()
            now_dt = datetime.now()
            for ev in events:
                dt_iso = ev.get("dt_iso", "")
                if not dt_iso or dt_iso in PROACTIVE_STATE["notified_events"]:
                    continue
                ev_dt = datetime.fromisoformat(dt_iso)
                diff_min = (ev_dt - now_dt).total_seconds() / 60.0
                if 0 < diff_min <= 35:
                    PROACTIVE_STATE["notified_events"].add(dt_iso)
                    loc = ev.get("loc", "")
                    maps_url = f"https://www.google.com/maps/dir/?api=1&destination={urllib.parse.quote(loc)}&travelmode=driving" if loc else ""
                    speech_alert = f"Margil, in {int(diff_min)} Minuten steht dein Termin {ev['title']} an. Ich habe dir die Anfrage zur Autorisierung auf Telegram geschickt."
                    queue_voice_alert(speech_alert, maps_url, "ROUTE STARTEN")
                    send_tg_authorization(
                        f"🔔 TERMIN-ALARM:\n{ev['time']} – {ev['title']}\nOrt: {loc or 'N/A'}\n\nRoute & Briefing freigeben?",
                        action_meta={
                            "approve_speech": f"Autorisierung erhalten, Margil. Route für {ev['title']} ist bereit.",
                            "action_url": maps_url,
                            "action_label": "ROUTE STARTEN"
                        }
                    )
        except Exception:
            pass

threading.Thread(target=autonomous_guardian_loop, daemon=True).start()

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/proactive_poll")
def proactive_poll():
    if PROACTIVE_STATE["voice_alerts"]:
        return jsonify({"alert": PROACTIVE_STATE["voice_alerts"].pop(0)})
    return jsonify({"alert": None})

@app.route("/avatar")
def avatar():
    base = os.path.dirname(os.path.abspath(__file__))
    for f in os.listdir(base):
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return send_file(os.path.join(base, f))
    return Response(ICON_SVG, mimetype="image/svg+xml")

@app.route("/calendar_preview")
def cal_prev():
    return jsonify({"events": parse_upcoming_events()})

@app.route("/manifest.json")
def manifest():
    return jsonify({
        "name": "N.E.O.",
        "short_name": "NEO",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#020408",
        "theme_color": "#020408",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]
    })

@app.route("/icon.svg")
def icon():
    return Response(ICON_SVG, mimetype="image/svg+xml")

@app.route("/telegram_notify", methods=["POST"])
def tg_notify():
    text = (request.json or {}).get("text", "🔔 N.E.O. Autorisierung angefordert")
    ok = send_tg_authorization(
        text,
        action_meta={
            "approve_speech": "Vielen Dank, Margil. Du hast die Anfrage über Telegram autorisiert.",
            "action_url": "",
            "action_label": ""
        }
    )
    if not ok:
        return jsonify({"ok": False, "error": "Bitte sende einmal 'Hallo' an deinen Bot in Telegram!"})
    return jsonify({"ok": True})

@app.route("/chat", methods=["POST"])
def chat():
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY fehlt"}), 500
        data = request.json or {}
        client = genai.Client(api_key=api_key)
        events = parse_upcoming_events()
        cal_txt = "\n".join([f"- {e['time']}: {e['title']} ({e['loc']})" for e in events]) or "Keine Termine."

        parts = []
        if "image" in data:
            parts.append(types.Part.from_bytes(data=base64.b64decode(data["image"]), mime_type="image/jpeg"))
            parts.append(data.get("message", "Mängelbericht erstellen."))
        else:
            parts.append(data.get("message", ""))

        parts.append(f"Kalender:\n{cal_txt}\nNotizen: {json.dumps(data.get('memory', []), ensure_ascii=False)}")

        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT.format(mode=data.get("mode", "ARBEIT"), local_time=data.get("local_time_str", "")),
            temperature=0.3
        )
        resp = generate_with_fallback(client, parts, cfg)

        m = re.search(r'\{.*\}', resp.text.strip(), re.DOTALL)
        res = json.loads(m.group(0)) if m else {"reply": resp.text.strip()}
        reply = res.get("reply", "Zu Befehl, Margil.")

        if res.get("telegram_auth_request"):
            send_tg_authorization(
                f"🔔 AUTORISIERUNG ERFORDERLICH:\n\n{res['telegram_auth_request']}",
                action_meta={
                    "approve_speech": "Margil, deine Freigabe über Telegram wurde bestätigt.",
                    "action_url": res.get("action_url", ""),
                    "action_label": res.get("action_label", "OPEN")
                }
            )

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
