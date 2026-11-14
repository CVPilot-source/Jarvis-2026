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
  <circle cx="256" cy="256" r="155" fill="none" stroke="#F59E0B" stroke-width="8" stroke-dasharray="16 10"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#38BDF8" stroke-width="5"/>
  <circle cx="256" cy="256" r="24" fill="#F59E0B"/>
</svg>"""

HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#030712">
    <link rel="manifest" href="/manifest.json">
    <title>NEO // NEURAL COMMAND OS</title>
    <style>
        :root {
            --gold: #F59E0B;
            --gold-glow: rgba(245, 158, 11, 0.45);
            --cyan: #38BDF8;
            --cyan-dim: rgba(56, 189, 248, 0.16);
            --bg: #030712;
            --panel: rgba(8, 14, 28, 0.86);
            --border: rgba(56, 189, 248, 0.25);
            --text: #F8FAFC;
            --muted: #94A3B8;
        }
        body.listening { --gold: #10B981; --gold-glow: rgba(16, 185, 129, 0.5); }
        body.thinking  { --gold: #38BDF8; --gold-glow: rgba(56, 189, 248, 0.55); }
        body.speaking  { --gold: #F59E0B; --gold-glow: rgba(245, 158, 11, 0.65); }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        html, body {
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100dvh;
            overflow: hidden;
            background-color: var(--bg);
            background-image:
                radial-gradient(circle at 50% 48%, rgba(14, 30, 62, 0.85) 0%, rgba(3, 7, 18, 0.98) 70%),
                linear-gradient(rgba(56, 189, 248, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(56, 189, 248, 0.05) 1px, transparent 1px),
                linear-gradient(rgba(56, 189, 248, 0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(56, 189, 248, 0.02) 1px, transparent 1px);
            background-size: 100% 100%, 80px 80px, 80px 80px, 20px 20px, 20px 20px;
            color: var(--text);
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, monospace, sans-serif;
        }

        /* FULLSCREEN NEURAL CANVAS (LINES + PULSING DATA PACKETS + CORE RINGS) */
        #neuralCanvas {
            position: fixed;
            inset: 0;
            width: 100vw;
            height: 100dvh;
            z-index: 1;
            pointer-events: none;
        }

        /* TOP LEFT SYSTEM TELEMETRY (LIKE VIDEO) */
        .hud-tl {
            position: fixed;
            top: 16px;
            left: 20px;
            z-index: 10;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .sys-title {
            font-size: 20px;
            font-weight: 900;
            letter-spacing: 5px;
            color: var(--cyan);
            text-shadow: 0 0 14px rgba(56, 189, 248, 0.5);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .sys-sub {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.5px;
            color: var(--muted);
            text-transform: uppercase;
        }
        .hud-controls {
            display: flex;
            gap: 8px;
            margin-top: 6px;
        }
        .hud-btn {
            background: var(--panel);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 5px 11px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.8px;
            cursor: pointer;
            backdrop-filter: blur(8px);
        }
        .hud-btn:hover { border-color: var(--cyan); }

        /* TOP RIGHT LIVE TRANSCRIPT / TELEMETRY PANEL (LIKE VIDEO) */
        .hud-tr {
            position: fixed;
            top: 16px;
            right: 20px;
            width: 310px;
            max-width: 42vw;
            background: var(--panel);
            border: 1px solid var(--border);
            border-top: 2px solid var(--cyan);
            border-radius: 10px;
            padding: 10px 13px;
            z-index: 10;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6);
        }
        .tr-head {
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1.2px;
            color: var(--cyan);
            margin-bottom: 5px;
            text-transform: uppercase;
        }
        .tr-body {
            font-size: 12.5px;
            line-height: 1.42;
            color: #E2E8F0;
            max-height: 110px;
            overflow-y: auto;
        }

        /* CENTER CLICKABLE CORE HITBOX */
        .core-trigger {
            position: fixed;
            top: 48%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 170px;
            height: 170px;
            border-radius: 50%;
            z-index: 8;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        }
        .core-label {
            font-size: 18px;
            font-weight: 900;
            letter-spacing: 4px;
            color: #FFFFFF;
            text-shadow: 0 0 12px var(--gold);
        }
        .core-sub {
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1.8px;
            color: var(--gold);
            margin-top: 4px;
            text-transform: uppercase;
        }

        /* FLOATING NEURAL NODES DISTRIBUTED ACROSS FULL SCREEN */
        .node-item {
            position: fixed;
            transform: translate(-50%, -50%);
            z-index: 7;
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(8, 14, 28, 0.82);
            border: 1px solid rgba(56, 189, 248, 0.28);
            padding: 6px 12px;
            border-radius: 999px;
            cursor: pointer;
            backdrop-filter: blur(6px);
            transition: transform 0.15s, border-color 0.2s, box-shadow 0.2s;
            white-space: nowrap;
        }
        .node-item:hover, .node-item.active-node {
            border-color: var(--gold);
            box-shadow: 0 0 18px var(--gold-glow);
            transform: translate(-50%, -50%) scale(1.06);
        }
        .node-dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: var(--cyan);
            box-shadow: 0 0 8px var(--cyan);
            flex-shrink: 0;
        }
        .node-item.active-node .node-dot {
            background: var(--gold);
            box-shadow: 0 0 10px var(--gold);
        }
        .node-title {
            font-size: 11.5px;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: #F1F5F9;
        }

        /* HOLOGRAPHIC POPUP WINDOW (APPEARS ON COMMAND LIKE VIDEO) */
        .holo-modal {
            position: fixed;
            top: 48%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 440px;
            max-width: 92vw;
            background: rgba(7, 13, 27, 0.94);
            border: 1px solid var(--cyan);
            box-shadow: 0 0 40px rgba(56, 189, 248, 0.25);
            border-radius: 12px;
            padding: 16px;
            z-index: 20;
            display: none;
            flex-direction: column;
            gap: 10px;
            backdrop-filter: blur(16px);
        }
        .holo-modal.open { display: flex; }
        .holo-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 1.5px;
            color: var(--cyan);
            text-transform: uppercase;
        }
        .holo-content {
            max-height: 240px;
            overflow-y: auto;
            font-size: 13px;
            line-height: 1.45;
        }
        .holo-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 7px 10px;
            background: rgba(56, 189, 248, 0.06);
            border-left: 2px solid var(--gold);
            border-radius: 6px;
            margin-bottom: 6px;
        }

        /* BOTTOM COMMAND DOCK */
        .bottom-dock {
            position: fixed;
            bottom: 16px;
            left: 50%;
            transform: translateX(-50%);
            width: 540px;
            max-width: 94vw;
            z-index: 12;
            display: flex;
            flex-direction: column;
            gap: 8px;
            align-items: center;
        }
        .act-strip {
            display: flex;
            gap: 8px;
            justify-content: center;
        }
        .gold-pill {
            background: var(--gold);
            color: #030712;
            border: none;
            border-radius: 999px;
            padding: 6px 16px;
            font-size: 12px;
            font-weight: 800;
            text-decoration: none;
            cursor: pointer;
            box-shadow: 0 0 16px var(--gold-glow);
        }
        .cmd-bar {
            width: 100%;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 6px 8px 6px 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            backdrop-filter: blur(12px);
        }
        .cmd-bar input {
            flex: 1;
            background: transparent;
            border: none;
            color: #FFF;
            font-size: 13.5px;
            outline: none;
        }
        .mic-round {
            width: 34px;
            height: 34px;
            border-radius: 50%;
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid var(--gold);
            color: #FFF;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .exec-btn {
            background: var(--cyan);
            color: #030712;
            border: none;
            border-radius: 999px;
            padding: 7px 16px;
            font-size: 12px;
            font-weight: 800;
            cursor: pointer;
        }

        @media (max-width: 768px) {
            .hud-tr { display: none; }
            .node-item { padding: 5px 9px; }
            .node-title { font-size: 10.5px; }
        }
    </style>
</head>
<body>
    <!-- FULLSCREEN ANIMATED NEURAL NETWORK & REACTOR CORE -->
    <canvas id="neuralCanvas"></canvas>

    <!-- TOP LEFT TELEMETRY -->
    <div class="hud-tl">
        <div class="sys-title">NEO <span style="font-size:11px; color:var(--gold); letter-spacing:2px;">CORE OS</span></div>
        <div class="sys-sub" id="sysMeta">HAMBURG • --:-- • SYNCHRONISIERT</div>
        <div class="hud-controls">
            <button type="button" class="hud-btn" id="wBtn" onclick="toggleWake()">VOICE: AN</button>
            <button type="button" class="hud-btn" id="mBtn" onclick="toggleMode()">MODUS: ARBEIT</button>
            <button type="button" class="hud-btn" onclick="openHolo('calendar')">KALENDER</button>
        </div>
    </div>

    <!-- TOP RIGHT LIVE OUTPUT LOG (LIKE APEX) -->
    <div class="hud-tr">
        <div class="tr-head">
            <span>NEURAL STREAM</span>
            <span id="streamStatus">STANDBY</span>
        </div>
        <div class="tr-body" id="replyBox">System online, Margil. Bereit für deine Befehle.</div>
    </div>

    <!-- CENTER REACTOR CORE HITBOX -->
    <div class="core-trigger" onclick="toggleRec()">
        <div class="core-label">NEO</div>
        <div class="core-sub" id="coreState">ONLINE</div>
    </div>

    <!-- FLOATING NODES CONTAINER (POSITIONED DYNAMICALLY TO MATCH CANVAS LINES) -->
    <div id="nodesLayer"></div>

    <!-- HOLOGRAPHIC POPUP PANEL (OPENED BY NODES OR VOICE) -->
    <div class="holo-modal" id="holoModal">
        <div class="holo-head">
            <span id="holoTitle">SYSTEM DATEN</span>
            <button type="button" class="hud-btn" onclick="closeHolo()">✕</button>
        </div>
        <div class="holo-content" id="holoBody"></div>
    </div>

    <!-- BOTTOM DOCK -->
    <div class="bottom-dock">
        <div class="act-strip" id="actBar"></div>
        <div class="cmd-bar">
            <button type="button" class="mic-round" onclick="toggleRec()">🎙️</button>
            <input type="text" id="msg" placeholder="Befehl an NEO (z.B. Morning Brief, Angebot, Übersetzung DE/SQ)..." onkeypress="if(event.key==='Enter')sendTxt()">
            <button type="button" class="exec-btn" onclick="sendTxt()">EXEC</button>
        </div>
    </div>

    <input type="file" id="cam" accept="image/*" capture="environment" style="display:none" onchange="handleImg(event)">
    <audio id="player" playsinline></audio>

    <script>
        // --- 1. NEURAL NODE DEFINITIONS (DISTRIBUTED ACROSS WIDESCREEN LIKE VIDEO) ---
        const NODES = [
            { id: 'brief',    label: 'Morning Brief',  rx: 0.24, ry: 0.24, action: () => quickCmd('Gib mir mein komplettes Morning Briefing mit Terminen, Wetter und wichtigen Objekt-Codes.') },
            { id: 'calendar', label: 'Calendar Sync',  rx: 0.16, ry: 0.44, action: () => openHolo('calendar') },
            { id: 'navi',     label: 'Auto-Briefing',  rx: 0.22, ry: 0.66, action: () => quickCmd('Ich fahre los zum nächsten Termin. Gib mir das Briefing mit Codes und starte Navigation.') },
            { id: 'codes',    label: 'Objekt-Codes',   rx: 0.34, ry: 0.78, action: () => openHolo('codes') },
            { id: 'offer',    label: 'Angebot Rechner',rx: 0.76, ry: 0.24, action: () => quickCmd('Kalkuliere ein Reinigungsangebot für 600 Quadratmeter Büro, zweimal pro Woche, mit WhatsApp-Nachricht.') },
            { id: 'camera',   label: 'Mängel-Vision',  rx: 0.84, ry: 0.44, action: () => document.getElementById('cam').click() },
            { id: 'trans',    label: 'Dolmetscher DE/SQ',rx: 0.78, ry: 0.66, action: () => { document.getElementById('msg').focus(); document.getElementById('msg').placeholder = 'Text auf Deutsch oder Albanisch eingeben...'; } },
            { id: 'telegram', label: 'Telegram Link',  rx: 0.66, ry: 0.78, action: () => sendTg() }
        ];

        const nodesLayer = document.getElementById('nodesLayer');
        NODES.forEach(n => {
            const el = document.createElement('div');
            el.className = 'node-item';
            el.id = 'node-' + n.id;
            el.style.left = (n.rx * 100) + '%';
            el.style.top = (n.ry * 100) + '%';
            el.innerHTML = `<span class="node-dot"></span><span class="node-title">${n.label}</span>`;
            el.onclick = () => {
                highlightNode(n.id);
                n.action();
            };
            nodesLayer.appendChild(el);
        });

        function highlightNode(id) {
            document.querySelectorAll('.node-item').forEach(e => e.classList.remove('active-node'));
            const target = document.getElementById('node-' + id);
            if (target) target.classList.add('active-node');
        }

        // --- 2. FULLSCREEN HOLOGRAPHIC CANVAS (REACTOR RINGS + CURVED NEURAL TRACES + DATA PULSES) ---
        const canvas = document.getElementById('neuralCanvas');
        const ctx = canvas.getContext('2d');
        let W = window.innerWidth, H = window.innerHeight;
        function resizeCanvas() {
            W = canvas.width = window.innerWidth;
            H = canvas.height = window.innerHeight;
        }
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        let coreStateMode = 'idle';
        let angle1 = 0, angle2 = 0, pulseT = 0;

        // Data packets traveling along neural lines
        const packets = NODES.map((_, idx) => ({
            nodeIdx: idx,
            progress: (idx * 0.17) % 1,
            speed: 0.004 + (idx % 3) * 0.0015
        }));

        function drawNeuralNetwork() {
            ctx.clearRect(0, 0, W, H);
            const cx = W * 0.5;
            const cy = H * 0.48;

            let mainColor = '245, 158, 11'; // Amber Gold
            let secColor = '56, 189, 248';  // Cyan
            let rotSpeed = 0.006;
            let pulseBoost = 1;

            if (coreStateMode === 'listening') {
                mainColor = '16, 185, 129'; // Emerald
                rotSpeed = 0.015;
                pulseBoost = 2.2;
            } else if (coreStateMode === 'thinking') {
                mainColor = '56, 189, 248'; // Electric Cyan
                rotSpeed = 0.025;
                pulseBoost = 3.2;
            } else if (coreStateMode === 'speaking') {
                mainColor = '245, 158, 11'; // Intense Gold
                rotSpeed = 0.018;
                pulseBoost = 2.8;
            }

            angle1 += rotSpeed;
            angle2 -= rotSpeed * 0.7;
            pulseT += 0.06 * pulseBoost;

            // A. Curved Neural Traces from Center Core to Each Node
            NODES.forEach((n, idx) => {
                const nx = W * n.rx;
                const ny = H * n.ry;
                const midX = (cx + nx) * 0.5;
                const midY = (cy + ny) * 0.5 + (idx % 2 === 0 ? -28 : 28);

                ctx.beginPath();
                ctx.moveTo(cx, cy);
                ctx.quadraticCurveTo(midX, midY, nx, ny);
                ctx.strokeStyle = `rgba(${secColor}, ${coreStateMode === 'idle' ? 0.22 : 0.42})`;
                ctx.lineWidth = 1.4;
                ctx.stroke();

                // Traveling energy packet along the quadratic curve
                const p = packets[idx];
                p.progress += p.speed * pulseBoost;
                if (p.progress > 1) p.progress = 0;
                const t = p.progress;
                const px = (1 - t) * (1 - t) * cx + 2 * (1 - t) * t * midX + t * t * nx;
                const py = (1 - t) * (1 - t) * cy + 2 * (1 - t) * t * midY + t * t * ny;

                ctx.beginPath();
                ctx.arc(px, py, 2.8, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(${mainColor}, 0.9)`;
                ctx.fill();
            });

            // B. Multi-Ring Holographic Core (Like APEX Center Orb)
            const baseR = 76 + (coreStateMode === 'speaking' ? Math.sin(pulseT * 2.2) * 7 : Math.sin(pulseT) * 2);

            // Soft Ambient Radial Glow
            const glow = ctx.createRadialGradient(cx, cy, 15, cx, cy, baseR + 65);
            glow.addColorStop(0, `rgba(${mainColor}, 0.28)`);
            glow.addColorStop(0.6, `rgba(${secColor}, 0.08)`);
            glow.addColorStop(1, 'rgba(3, 7, 18, 0)');
            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(cx, cy, baseR + 65, 0, Math.PI * 2);
            ctx.fill();

            // Outer Segmented Cyan Ring
            ctx.save();
            ctx.translate(cx, cy);
            ctx.rotate(angle1);
            ctx.strokeStyle = `rgba(${secColor}, 0.55)`;
            ctx.lineWidth = 2;
            ctx.setLineDash([28, 14, 6, 14]);
            ctx.beginPath();
            ctx.arc(0, 0, baseR + 24, 0, Math.PI * 2);
            ctx.stroke();
            ctx.restore();

            // Middle Dashed Gold Ring
            ctx.save();
            ctx.translate(cx, cy);
            ctx.rotate(angle2);
            ctx.strokeStyle = `rgba(${mainColor}, 0.85)`;
            ctx.lineWidth = 3;
            ctx.setLineDash([18, 10]);
            ctx.beginPath();
            ctx.arc(0, 0, baseR + 8, 0, Math.PI * 2);
            ctx.stroke();
            ctx.restore();

            // Solid Inner Core Ring
            ctx.beginPath();
            ctx.arc(cx, cy, baseR - 6, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(5, 10, 22, 0.88)';
            ctx.fill();
            ctx.strokeStyle = `rgba(${mainColor}, 0.95)`;
            ctx.lineWidth = 2.5;
            ctx.stroke();

            requestAnimationFrame(drawNeuralNetwork);
        }
        drawNeuralNetwork();

        // --- 3. TELEMETRY, CALENDAR & HOLOGRAPHIC WINDOWS ---
        let cachedEvents = [];
        let weatherStr = "HAMBURG";
        function updateTelemetry() {
            const now = new Date();
            const t = now.toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
            const d = now.toLocaleDateString('de-DE', {weekday:'short', day:'2-digit', month:'2-digit'});
            document.getElementById('sysMeta').innerText = `${weatherStr} • ${d.toUpperCase()} • ${t} UHR`;
        }
        updateTelemetry();
        setInterval(updateTelemetry, 15000);

        fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true')
            .then(r => r.json()).then(d => {
                if (d.current_weather) { weatherStr = `HAMBURG ${Math.round(d.current_weather.temperature)}°C`; updateTelemetry(); }
            }).catch(()=>{});

        fetch('/calendar_preview').then(r => r.json()).then(d => {
            cachedEvents = d.events || [];
        }).catch(()=>{});

        let mem = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        let mode = localStorage.getItem('neo_mode') || 'ARBEIT';
        let wakeOn = true, isRec = false, isSpk = false, inConv = false;
        let rec = null, stream = null, chunks = [], wakeRec = null;
        const player = document.getElementById('player');

        function saveState() {
            localStorage.setItem('neo_memory', JSON.stringify(mem));
            localStorage.setItem('neo_mode', mode);
            document.getElementById('mBtn').innerText = 'MODUS: ' + mode;
        }
        saveState();

        function toggleMode() { mode = mode === 'ARBEIT' ? 'PRIVAT' : 'ARBEIT'; saveState(); }

        function openHolo(type) {
            const modal = document.getElementById('holoModal');
            const title = document.getElementById('holoTitle');
            const body = document.getElementById('holoBody');
            modal.classList.add('open');

            if (type === 'calendar') {
                title.innerText = 'KALENDER SYNCHRONISATION';
                body.innerHTML = cachedEvents.length
                    ? cachedEvents.map(e => `<div class="holo-row"><div><div style="color:var(--gold);font-size:11px;font-weight:800;">${e.time}</div><div>${e.title}</div><div style="color:var(--muted);font-size:11px;">${e.loc || ''}</div></div></div>`).join('')
                    : '<div style="color:var(--muted);">Keine anstehenden Termine gefunden.</div>';
            } else if (type === 'codes') {
                title.innerText = `OBJEKT-CODES & NOTIZEN (${mem.length})`;
                body.innerHTML = mem.length
                    ? mem.map((x, i) => `<div class="holo-row"><span>${x}</span><button type="button" class="gold-pill" style="padding:3px 10px;" onclick="mem.splice(${i},1);saveState();openHolo('codes');">✓</button></div>`).join('')
                    : '<div style="color:var(--muted);">Noch keine Objekt-Codes gespeichert.</div>';
            }
        }
        function closeHolo() { document.getElementById('holoModal').classList.remove('open'); }

        function setSt(s) {
            coreStateMode = s || 'idle';
            document.body.className = s || '';
            const cSt = document.getElementById('coreState');
            const sSt = document.getElementById('streamStatus');
            if (s === 'listening') { cSt.innerText = 'LISTENING'; sSt.innerText = 'HÖRT ZU'; }
            else if (s === 'thinking') { cSt.innerText = 'PROCESSING'; sSt.innerText = 'ANALYSE'; }
            else if (s === 'speaking') { cSt.innerText = 'ACTIVE'; sSt.innerText = 'SPRICHT'; }
            else { cSt.innerText = 'ONLINE'; sSt.innerText = 'STANDBY'; }
        }

        function stopWake() { if (wakeRec) { try { wakeRec.onend = null; wakeRec.abort(); } catch(e){} wakeRec = null; } }
        function toggleWake() {
            wakeOn = !wakeOn;
            document.getElementById('wBtn').innerText = wakeOn ? 'VOICE: AN' : 'VOICE: AUS';
            if (wakeOn) startWake(); else stopWake();
        }
        function startWake() {
            if (!wakeOn || isRec || isSpk || inConv) return;
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SR) return;
            stopWake();
            wakeRec = new SR();
            wakeRec.lang = 'de-DE';
            wakeRec.continuous = true;
            wakeRec.onresult = (e) => {
                for (let i = e.resultIndex; i < e.results.length; i++) {
                    const t = e.results[i][0].transcript.toLowerCase();
                    if (t.includes('hey neo') || t.includes('neo')) { stopWake(); inConv = true; startRec(); return; }
                }
            };
            wakeRec.onend = () => { wakeRec = null; if (wakeOn && !isRec && !isSpk && !inConv) setTimeout(startWake, 600); };
            try { wakeRec.start(); } catch(e){}
        }

        function toggleRec() {
            if (isSpk) { player.pause(); isSpk = false; setSt(null); }
            if (isRec) { isRec = false; if (rec && rec.state !== 'inactive') rec.stop(); return; }
            inConv = true; startRec();
        }

        async function startRec() {
            if (isRec || isSpk) return;
            stopWake();
            try {
                stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
                chunks = [];
                rec = new MediaRecorder(stream, { audioBitsPerSecond: 12000 });
                rec.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
                rec.onstop = () => {
                    stream.getTracks().forEach(t => t.stop());
                    const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
                    if (blob.size < 800) { inConv = false; setSt(null); startWake(); return; }
                    setSt('thinking');
                    const r = new FileReader();
                    r.readAsDataURL(blob);
                    r.onloadend = () => sendNeo({ audio: r.result.split(',')[1], mime_type: (rec.mimeType || 'audio/webm').split(';')[0] });
                };
                rec.start();
                isRec = true;
                setSt('listening');
                setTimeout(() => { if (isRec) { isRec = false; rec.stop(); } }, 5000);
            } catch(e) { inConv = false; setSt(null); }
        }

        player.onplay = () => { isSpk = true; setSt('speaking'); };
        player.onended = () => { isSpk = false; setSt(null); if (inConv) setTimeout(startRec, 400); else startWake(); };

        async function sendTg() {
            document.getElementById('replyBox').innerText = "Sende Autorisierungsanfrage an Telegram...";
            try {
                const r = await fetch('/telegram_notify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:"📞 NEO Autorisierung angefordert!"}) });
                const d = await r.json();
                document.getElementById('replyBox').innerText = d.ok ? "Telegram-Benachrichtigung erfolgreich gesendet." : (d.error || "Telegram Fehler");
            } catch(e) { document.getElementById('replyBox').innerText = "Verbindungsfehler zu Telegram."; }
        }

        function handleImg(ev) {
            const f = ev.target.files[0]; if (!f) return;
            highlightNode('camera');
            setSt('thinking');
            const r = new FileReader();
            r.onload = e => sendNeo({ image: e.target.result.split(',')[1], message: "Erstelle einen kurzen Objekt-Mängelbericht für WhatsApp." });
            r.readAsDataURL(f);
        }

        function quickCmd(t) { setSt('thinking'); sendNeo({ message: t }); }
        function sendTxt() {
            const inp = document.getElementById('msg');
            if (!inp.value.trim()) return;
            const v = inp.value.trim(); inp.value = '';
            setSt('thinking'); sendNeo({ message: v });
        }

        async function sendNeo(payload) {
            stopWake();
            document.getElementById('actBar').innerHTML = '';
            payload.mode = mode; payload.memory = mem; payload.local_time_str = new Date().toLocaleString('de-DE');
            try {
                const res = await fetch('/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
                const d = await res.json();
                if (d.error) { inConv = false; setSt(null); document.getElementById('replyBox').innerText = d.error; return; }
                if (d.end_conversation) inConv = false;
                if (d.new_memory) { mem.push(d.new_memory); saveState(); }
                document.getElementById('replyBox').innerText = d.reply;

                if (d.copy_text) {
                    const b = document.createElement('button'); b.type = 'button'; b.className = 'gold-pill'; b.innerText = 'Text kopieren';
                    b.onclick = () => { navigator.clipboard.writeText(d.copy_text); b.innerText = '✓ Kopiert'; };
                    document.getElementById('actBar').appendChild(b);
                }
                if (d.action_url) {
                    inConv = false;
                    const a = document.createElement('a'); a.href = d.action_url; a.className = 'gold-pill'; a.innerText = d.action_label || 'Öffnen';
                    document.getElementById('actBar').appendChild(a);
                }
                if (d.audio) {
                    player.src = "data:audio/mp3;base64," + d.audio;
                    player.play().catch(() => { isSpk = false; setSt(null); });
                } else { setSt(null); }
            } catch(e) { inConv = false; setSt(null); }
        }
        window.onload = startWake;
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

SYSTEM_PROMPT = """Du bist NEO, der hochintelligente KI-Assistent von Margil (Kundenbetreuer Gebäudereinigung Hamburg).
Modus: {mode} | Zeit: {local_time}. Antworte souverän, ruhig, kurz und ohne Markdown/Sternchen.
- Morning Brief / Auto-Briefing: Nächste Termine + Codes aus Notizen + Google Maps URL in `action_url` (`action_label`: "Navigation starten").
- Dolmetscher DE <-> SQ: Bei Übersetzung ins Albanische `voice_lang`: "sq" und Übersetzung in `copy_text`, sonst "de".
- Kalkulator: Büro ~220 m²/Std, 31,50 €/Std netto (4,33 Wochen/Monat). Fertiges Angebot in `copy_text` + WhatsApp Intent (`intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp.w4b;end`, `action_label`: "WhatsApp öffnen").
- Gespräch Ende ("Danke", "Stopp"): `end_conversation`: true.
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

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

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

@app.route("/telegram_notify", methods=["POST"])
def tg_notify():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        return jsonify({"ok": False, "error": "Token fehlt"})
    if not chat_id:
        try:
            u = json.loads(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=5).read().decode())
            if u.get("result"):
                chat_id = str(u["result"][-1]["message"]["chat"]["id"])
        except Exception:
            pass
    if not chat_id:
        return jsonify({"ok": False, "error": "Erst 'Hallo' im Bot senden"})
    payload = json.dumps({
        "chat_id": chat_id,
        "text": (request.json or {}).get("text", "🔔 NEO Autorisierung"),
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
        cal_txt = "\n".join([f"- {e['time']}: {e['title']} ({e['loc']})" for e in events]) or "Keine Termine."

        parts = []
        if "image" in data:
            parts.append(types.Part.from_bytes(data=base64.b64decode(data["image"]), mime_type="image/jpeg"))
            parts.append(data.get("message", "Mängelbericht erstellen."))
        elif "audio" in data:
            parts.append(types.Part.from_bytes(data=base64.b64decode(data["audio"]), mime_type=data.get("mime_type", "audio/webm")))
        else:
            parts.append(data.get("message", ""))

        parts.append(f"Kalender:\n{cal_txt}\nNotizen: {json.dumps(data.get('memory', []), ensure_ascii=False)}")

        resp = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=parts,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT.format(mode=data.get("mode", "ARBEIT"), local_time=data.get("local_time_str", "")),
                temperature=0.3
            )
        )
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
