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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#030712">
    <link rel="manifest" href="/manifest.json">
    <title>NEO // COMMAND OS</title>
    <style>
        :root {
            --gold: #F59E0B;
            --gold-glow: rgba(245, 158, 11, 0.45);
            --cyan: #38BDF8;
            --bg: #030712;
            --panel: rgba(8, 14, 28, 0.90);
            --border: rgba(56, 189, 248, 0.28);
            --text: #F8FAFC;
            --muted: #94A3B8;
        }
        body.listening { --gold: #10B981; --gold-glow: rgba(16, 185, 129, 0.65); }
        body.thinking  { --gold: #38BDF8; --gold-glow: rgba(56, 189, 248, 0.65); }
        body.speaking  { --gold: #A855F7; --gold-glow: rgba(168, 85, 247, 0.65); }

        * { box-sizing: border-box; user-select: none; -webkit-tap-highlight-color: transparent; }

        html, body {
            margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden;
            background-color: var(--bg);
            background-image:
                radial-gradient(circle at 50% 46%, rgba(14, 30, 62, 0.82) 0%, rgba(3, 7, 18, 0.98) 70%),
                linear-gradient(rgba(56, 189, 248, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(56, 189, 248, 0.05) 1px, transparent 1px);
            background-size: 100% 100%, 64px 64px, 64px 64px;
            color: var(--text);
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        }

        #neuralCanvas {
            position: fixed; inset: 0; width: 100vw; height: 100vh;
            z-index: 1; pointer-events: none;
        }

        /* TOP LEFT HUD */
        .hud-tl {
            position: fixed; top: 18px; left: 22px; z-index: 10;
            display: flex; flex-direction: column; gap: 6px;
        }
        .sys-title {
            font-size: 22px; font-weight: 900; letter-spacing: 4px; color: var(--cyan);
            display: flex; align-items: center; gap: 10px;
        }
        .sys-sub { font-size: 11.5px; font-weight: 700; letter-spacing: 1.2px; color: var(--muted); }
        .hud-controls { display: flex; gap: 8px; margin-top: 4px; flex-wrap: wrap; }
        .hud-btn {
            background: var(--panel); border: 1px solid var(--border); color: var(--text);
            padding: 6px 12px; border-radius: 7px; font-size: 11.5px; font-weight: 700;
            cursor: pointer; transition: 0.15s;
        }
        .hud-btn:hover { border-color: var(--gold); color: var(--gold); }

        /* TOP RIGHT STREAM PANEL */
        .hud-tr {
            position: fixed; top: 18px; right: 22px; width: 360px; max-width: 44vw;
            background: var(--panel); border: 1px solid var(--border); border-top: 2px solid var(--gold);
            border-radius: 12px; padding: 12px 15px; z-index: 10;
            box-shadow: 0 10px 30px rgba(0,0,0,0.65);
        }
        .tr-head {
            display: flex; justify-content: space-between; font-size: 10.5px;
            font-weight: 800; letter-spacing: 1.2px; color: var(--gold); margin-bottom: 6px;
        }
        .tr-body {
            font-size: 13.5px; line-height: 1.45; color: #F1F5F9;
            max-height: 140px; overflow-y: auto; user-select: text;
        }

        /* CENTER CORE */
        .core-trigger {
            position: fixed; top: 46%; left: 50%; transform: translate(-50%, -50%);
            width: 160px; height: 160px; border-radius: 50%; z-index: 8;
            cursor: pointer; display: flex; flex-direction: column;
            align-items: center; justify-content: center; text-align: center;
        }
        .core-label {
            font-size: 20px; font-weight: 900; letter-spacing: 4px; color: #FFF;
            text-shadow: 0 0 14px var(--gold);
        }
        .core-sub {
            font-size: 10px; font-weight: 800; letter-spacing: 1.5px;
            color: var(--gold); margin-top: 4px;
        }

        /* NODES */
        .node-item {
            position: fixed; transform: translate(-50%, -50%); z-index: 7;
            display: flex; align-items: center; gap: 9px;
            background: var(--panel); border: 1px solid var(--border);
            padding: 8px 15px; border-radius: 999px; cursor: pointer;
            transition: transform 0.15s, border-color 0.2s, box-shadow 0.2s;
            white-space: nowrap; box-shadow: 0 6px 18px rgba(0,0,0,0.5);
        }
        .node-item:hover, .node-item.active-node {
            border-color: var(--gold);
            box-shadow: 0 0 20px var(--gold-glow);
            transform: translate(-50%, -50%) scale(1.07);
        }
        .node-dot {
            width: 9px; height: 9px; border-radius: 50%;
            background: var(--cyan); box-shadow: 0 0 8px var(--cyan);
        }
        .node-item.active-node .node-dot { background: var(--gold); box-shadow: 0 0 10px var(--gold); }
        .node-title { font-size: 12.5px; font-weight: 700; color: #F8FAFC; }

        /* POPUP WINDOW */
        .holo-modal {
            position: fixed; top: 46%; left: 50%; transform: translate(-50%, -50%);
            width: 480px; max-width: 92vw; background: rgba(7, 13, 27, 0.97);
            border: 1px solid var(--cyan); box-shadow: 0 0 45px rgba(0, 0, 0, 0.85);
            border-radius: 14px; padding: 18px; z-index: 30;
            display: none; flex-direction: column; gap: 12px;
        }
        .holo-modal.open { display: flex; }
        .holo-head {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--border); padding-bottom: 8px;
            font-size: 12.5px; font-weight: 800; letter-spacing: 1.5px; color: var(--cyan);
        }
        .holo-content { max-height: 280px; overflow-y: auto; font-size: 13.5px; }
        .holo-row {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 11px; background: rgba(56, 189, 248, 0.07);
            border-left: 3px solid var(--gold); border-radius: 7px; margin-bottom: 7px;
        }

        /* BOTTOM CONSOLE */
        .bottom-dock {
            position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%);
            width: 600px; max-width: 94vw; z-index: 12;
            display: flex; flex-direction: column; gap: 8px; align-items: center;
        }
        .act-strip { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
        .gold-pill {
            background: var(--gold); color: #030712; border: none; border-radius: 999px;
            padding: 7px 16px; font-size: 12px; font-weight: 800; text-decoration: none;
            cursor: pointer; box-shadow: 0 0 14px var(--gold-glow);
        }
        .cmd-bar {
            width: 100%; background: var(--panel); border: 1px solid var(--border);
            border-radius: 999px; padding: 6px 8px 6px 14px;
            display: flex; align-items: center; gap: 8px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.6);
        }
        .cmd-bar input {
            flex: 1; background: transparent; border: none; color: #FFF;
            font-size: 14px; outline: none; user-select: text;
        }
        .mic-round {
            width: 36px; height: 36px; border-radius: 50%;
            background: rgba(245, 158, 11, 0.16); border: 1px solid var(--gold);
            color: #FFF; cursor: pointer; display: flex; align-items: center; justify-content: center;
        }
        .exec-btn {
            background: var(--cyan); color: #030712; border: none; border-radius: 999px;
            padding: 8px 18px; font-size: 12.5px; font-weight: 800; cursor: pointer;
        }

        @media (max-width: 768px) {
            .hud-tr { top: auto; bottom: 82px; right: 12px; left: 12px; width: auto; max-width: none; }
            .node-item { padding: 6px 10px; }
            .node-title { font-size: 11px; }
        }
    </style>
</head>
<body>
    <canvas id="neuralCanvas"></canvas>

    <!-- TOP LEFT -->
    <div class="hud-tl">
        <div class="sys-title">NEO <span style="font-size:11px; color:var(--gold); letter-spacing:2px;">ALWAYS-ON VOICE OS</span></div>
        <div class="sys-sub" id="sysMeta">HAMBURG • SYNCHRONISIERT</div>
        <div class="hud-controls">
            <button type="button" class="hud-btn" id="wBtn" onclick="toggleWake()" style="border-color:#10B981; color:#10B981;">● HEY NEO: IMMER AKTIV</button>
            <button type="button" class="hud-btn" id="mBtn" onclick="toggleMode()">MODUS: ARBEIT</button>
            <button type="button" class="hud-btn" onclick="openHolo('calendar')">KALENDER</button>
            <button type="button" class="hud-btn" onclick="openHolo('codes')">CODES (<span id="nCount">0</span>)</button>
        </div>
    </div>

    <!-- TOP RIGHT OUTPUT -->
    <div class="hud-tr">
        <div class="tr-head">
            <span>LIVE VOICE STREAM</span>
            <span id="streamStatus">WARTE AUF "HEY NEO"</span>
        </div>
        <div class="tr-body" id="replyBox">Sage einfach „Hey Neo“ (z.B. „Hey Neo, gib mir mein Morning Brief“). Ich höre dauerhaft zu!</div>
    </div>

    <!-- CENTER REACTOR -->
    <div class="core-trigger" onclick="manualListenTrigger()">
        <div class="core-label">NEO</div>
        <div class="core-sub" id="coreState">SAY "HEY NEO"</div>
    </div>

    <!-- NODES -->
    <div id="nodesLayer"></div>

    <!-- HOLOGRAPHIC MODAL -->
    <div class="holo-modal" id="holoModal">
        <div class="holo-head">
            <span id="holoTitle">DATEN</span>
            <button type="button" class="hud-btn" onclick="closeHolo()">✕ Schließen</button>
        </div>
        <div class="holo-content" id="holoBody"></div>
    </div>

    <!-- BOTTOM DOCK -->
    <div class="bottom-dock">
        <div class="act-strip" id="actBar"></div>
        <div class="cmd-bar">
            <button type="button" class="mic-round" onclick="manualListenTrigger()">🎙️</button>
            <input type="text" id="msg" placeholder="Oder hier schreiben & Enter drücken..." onkeydown="if(event.key==='Enter')sendTxt()">
            <button type="button" class="exec-btn" onclick="sendTxt()">SENDEN</button>
        </div>
    </div>

    <input type="file" id="cam" accept="image/*" style="display:none" onchange="handleImg(event)">
    <audio id="player" playsinline></audio>

    <script>
        const isMobile = /Android|iPhone|iPad/i.test(navigator.userAgent);

        // Kurzer Bestätigungston wenn "Hey Neo" erkannt wird
        function beep(f1, f2) {
            try {
                const ac = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ac.createOscillator();
                const g = ac.createGain();
                osc.connect(g); g.connect(ac.destination);
                osc.frequency.setValueAtTime(f1, ac.currentTime);
                osc.frequency.exponentialRampToValueAtTime(f2, ac.currentTime + 0.11);
                g.gain.setValueAtTime(0.12, ac.currentTime);
                g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.13);
                osc.start(); osc.stop(ac.currentTime + 0.14);
            } catch(e){}
        }

        // --- 1. NODES ---
        const NODES = [
            { id: 'brief',    label: '☀️ Morning Brief',   rx: 0.23, ry: 0.25, action: () => quickCmd('Gib mir mein komplettes Morning Briefing mit Terminen heute und wichtigen Objekt-Codes.') },
            { id: 'calendar', label: '📅 Kalender Sync',   rx: 0.16, ry: 0.45, action: () => openHolo('calendar') },
            { id: 'navi',     label: '🧭 Auto-Briefing',   rx: 0.22, ry: 0.65, action: () => quickCmd('Ich fahre los zum nächsten Termin. Gib mir das Briefing mit Codes und starte Navigation.') },
            { id: 'codes',    label: '🔐 Objekt-Codes',    rx: 0.34, ry: 0.77, action: () => openHolo('codes') },
            { id: 'offer',    label: '📐 Angebot Rechner', rx: 0.77, ry: 0.25, action: () => openHolo('calc') },
            { id: 'camera',   label: '📸 Mängel-Foto',     rx: 0.84, ry: 0.45, action: () => document.getElementById('cam').click() },
            { id: 'trans',    label: '🌐 Dolmetscher DE/SQ',rx: 0.78, ry: 0.65, action: () => { const i = document.getElementById('msg'); i.focus(); i.value = 'Übersetze ins Albanische: '; } },
            { id: 'telegram', label: '✈️ Telegram Alert',  rx: 0.66, ry: 0.77, action: () => sendTg() }
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
                document.querySelectorAll('.node-item').forEach(e => e.classList.remove('active-node'));
                el.classList.add('active-node');
                n.action();
            };
            nodesLayer.appendChild(el);
        });

        // --- 2. CANVAS ANIMATION ---
        const canvas = document.getElementById('neuralCanvas');
        const ctx = canvas.getContext('2d');
        let W = window.innerWidth, H = window.innerHeight;
        function resizeCanvas() { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; }
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        let coreStateMode = 'idle', angle1 = 0, angle2 = 0, pulseT = 0;
        const packets = NODES.map((_, idx) => ({ progress: (idx * 0.15) % 1, speed: 0.004 + (idx % 3) * 0.0012 }));

        function drawNeuralNetwork() {
            ctx.clearRect(0, 0, W, H);
            const cx = W * 0.5, cy = H * 0.46;

            let mainColor = '245, 158, 11', secColor = '56, 189, 248', rotSpeed = 0.005, pulseBoost = 1;
            if (coreStateMode === 'listening') { mainColor = '16, 185, 129'; rotSpeed = 0.016; pulseBoost = 2.4; }
            else if (coreStateMode === 'thinking') { mainColor = '56, 189, 248'; rotSpeed = 0.026; pulseBoost = 3.2; }
            else if (coreStateMode === 'speaking') { mainColor = '168, 85, 247'; rotSpeed = 0.018; pulseBoost = 2.6; }

            angle1 += rotSpeed; angle2 -= rotSpeed * 0.7; pulseT += 0.05 * pulseBoost;

            NODES.forEach((n, idx) => {
                const nx = W * n.rx, ny = H * n.ry;
                const midX = (cx + nx) * 0.5, midY = (cy + ny) * 0.5 + (idx % 2 === 0 ? -25 : 25);

                ctx.beginPath();
                ctx.moveTo(cx, cy);
                ctx.quadraticCurveTo(midX, midY, nx, ny);
                ctx.strokeStyle = `rgba(${secColor}, 0.25)`;
                ctx.lineWidth = 1.5;
                ctx.stroke();

                const p = packets[idx];
                p.progress += p.speed * pulseBoost;
                if (p.progress > 1) p.progress = 0;
                const t = p.progress;
                const px = (1 - t) * (1 - t) * cx + 2 * (1 - t) * t * midX + t * t * nx;
                const py = (1 - t) * (1 - t) * cy + 2 * (1 - t) * t * midY + t * t * ny;

                ctx.beginPath();
                ctx.arc(px, py, 3, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(${mainColor}, 0.95)`;
                ctx.fill();
            });

            const baseR = 72 + (coreStateMode === 'speaking' ? Math.sin(pulseT * 2) * 8 : Math.sin(pulseT) * 2);
            const glow = ctx.createRadialGradient(cx, cy, 10, cx, cy, baseR + 60);
            glow.addColorStop(0, `rgba(${mainColor}, 0.32)`);
            glow.addColorStop(1, 'rgba(3, 7, 18, 0)');
            ctx.fillStyle = glow;
            ctx.beginPath(); ctx.arc(cx, cy, baseR + 60, 0, Math.PI * 2); ctx.fill();

            ctx.save(); ctx.translate(cx, cy); ctx.rotate(angle1);
            ctx.strokeStyle = `rgba(${secColor}, 0.6)`; ctx.lineWidth = 2; ctx.setLineDash([24, 12, 6, 12]);
            ctx.beginPath(); ctx.arc(0, 0, baseR + 22, 0, Math.PI * 2); ctx.stroke(); ctx.restore();

            ctx.save(); ctx.translate(cx, cy); ctx.rotate(angle2);
            ctx.strokeStyle = `rgba(${mainColor}, 0.85)`; ctx.lineWidth = 3; ctx.setLineDash([16, 10]);
            ctx.beginPath(); ctx.arc(0, 0, baseR + 7, 0, Math.PI * 2); ctx.stroke(); ctx.restore();

            ctx.beginPath(); ctx.arc(cx, cy, baseR - 6, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(5, 10, 22, 0.92)'; ctx.fill();
            ctx.strokeStyle = `rgba(${mainColor}, 0.95)`; ctx.lineWidth = 2.5; ctx.stroke();

            requestAnimationFrame(drawNeuralNetwork);
        }
        drawNeuralNetwork();

        // --- 3. STATE & POPUPS ---
        let cachedEvents = [], weatherStr = "HAMBURG";
        function updateTelemetry() {
            const now = new Date();
            document.getElementById('sysMeta').innerText = `${weatherStr} • ${now.toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'})} UHR`;
        }
        updateTelemetry(); setInterval(updateTelemetry, 15000);

        fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true')
            .then(r => r.json()).then(d => { if (d.current_weather) { weatherStr = `HAMBURG ${Math.round(d.current_weather.temperature)}°C`; updateTelemetry(); } }).catch(()=>{});

        fetch('/calendar_preview').then(r => r.json()).then(d => { cachedEvents = d.events || []; }).catch(()=>{});

        let mem = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        let mode = localStorage.getItem('neo_mode') || 'ARBEIT';
        const player = document.getElementById('player');

        function saveState() {
            localStorage.setItem('neo_memory', JSON.stringify(mem));
            localStorage.setItem('neo_mode', mode);
            document.getElementById('mBtn').innerText = 'MODUS: ' + mode;
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
                title.innerText = 'KALENDER TERMINE';
                body.innerHTML = cachedEvents.length
                    ? cachedEvents.map(e => `<div class="holo-row"><div><div style="color:var(--gold);font-size:11px;font-weight:800;">${e.time}</div><div style="font-weight:700;">${e.title}</div><div style="color:var(--muted);font-size:11px;">${e.loc || ''}</div></div></div>`).join('')
                    : '<div style="color:var(--muted);">Keine anstehenden Termine gefunden.</div>';
            } else if (type === 'codes') {
                title.innerText = `OBJEKT-CODES & NOTIZEN (${mem.length})`;
                const listHtml = mem.length
                    ? mem.map((x, i) => `<div class="holo-row"><span>${x}</span><button type="button" class="gold-pill" style="padding:3px 10px;" onclick="mem.splice(${i},1);saveState();openHolo('codes');">✓</button></div>`).join('')
                    : '<div style="color:var(--muted);margin-bottom:10px;">Noch keine Objekt-Codes gespeichert.</div>';
                body.innerHTML = `
                    <div style="display:flex;gap:6px;margin-bottom:12px;">
                        <input id="newCodeInp" type="text" placeholder="Neuen Code/Notiz eingeben..." style="flex:1;background:#030712;border:1px solid var(--border);color:#fff;padding:8px;border-radius:6px;">
                        <button type="button" class="exec-btn" onclick="const v=document.getElementById('newCodeInp').value.trim();if(v){mem.push(v);saveState();openHolo('codes');}">+ Speichern</button>
                    </div>` + listHtml;
            } else if (type === 'calc') {
                title.innerText = 'ANGEBOTS-KALKULATOR (31,50 €/Std)';
                body.innerHTML = `
                    <div style="display:flex;flex-direction:column;gap:10px;">
                        <input id="cQm" type="number" placeholder="Fläche in m² (z.B. 600)" value="600" style="background:#030712;border:1px solid var(--border);color:#fff;padding:9px;border-radius:7px;">
                        <select id="cFreq" style="background:#030712;border:1px solid var(--border);color:#fff;padding:9px;border-radius:7px;">
                            <option value="1x pro Woche">1x pro Woche</option>
                            <option value="2x pro Woche" selected>2x pro Woche</option>
                            <option value="3x pro Woche">3x pro Woche</option>
                            <option value="5x pro Woche">5x pro Woche</option>
                        </select>
                        <button type="button" class="gold-pill" onclick="const q=document.getElementById('cQm').value||600;const f=document.getElementById('cFreq').value;closeHolo();quickCmd('Kalkuliere ein Reinigungsangebot für '+q+' Quadratmeter Büro, '+f+', und erstelle den Angebotstext.');">JETZT BERECHNEN</button>
                    </div>`;
            }
        }
        function closeHolo() { document.getElementById('holoModal').classList.remove('open'); }

        function setSt(s) {
            coreStateMode = s || 'idle';
            document.body.className = s || '';
            const cSt = document.getElementById('coreState');
            const sSt = document.getElementById('streamStatus');
            if (s === 'listening') { cSt.innerText = 'ICH HÖRE ZU...'; sSt.innerText = 'SPRICH JETZT'; }
            else if (s === 'thinking') { cSt.innerText = 'DENKT NACH...'; sSt.innerText = 'ANALYSE...'; }
            else if (s === 'speaking') { cSt.innerText = 'NEO SPRICHT'; sSt.innerText = 'AUDIO AKTIV'; }
            else { cSt.innerText = activeSession ? 'SPRICH WEITER...' : 'SAY "HEY NEO"'; sSt.innerText = activeSession ? 'DIALOG AKTIV' : 'LAUSCHT ("HEY NEO")'; }
        }

        // --- 4. 100% HANDS-FREE CONTINUOUS SPEECH ENGINE (KEIN KLICKEN NÖTIG!) ---
        let wakeOn = true;          // Immer aktiv!
        let activeSession = false;  // Wenn true, nimmt NEO jeden Satz direkt an (ohne "Hey Neo")
        let isBusy = false;         // True während NEO denkt oder spricht
        let srInstance = null;

        function toggleWake() {
            wakeOn = !wakeOn;
            const b = document.getElementById('wBtn');
            if (wakeOn) {
                b.innerText = '● HEY NEO: IMMER AKTIV';
                b.style.borderColor = '#10B981';
                b.style.color = '#10B981';
                startAlwaysListening();
            } else {
                b.innerText = '○ HEY NEO: PAUSIERT';
                b.style.borderColor = '';
                b.style.color = '';
                activeSession = false;
                if (srInstance) { try { srInstance.onend = null; srInstance.abort(); } catch(e){} srInstance = null; }
                setSt(null);
            }
        }

        function manualListenTrigger() {
            if (isBusy) {
                player.pause();
                isBusy = false;
            }
            activeSession = true;
            beep(520, 920);
            setSt('listening');
            document.getElementById('replyBox').innerText = "🎙️ Ich höre dir direkt zu, Margil...";
            if (!srInstance) startAlwaysListening();
        }

        function startAlwaysListening() {
            if (!wakeOn || isBusy) return;
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SR) {
                document.getElementById('replyBox').innerText = "Bitte Google Chrome oder Edge für Hands-Free 'Hey Neo' nutzen.";
                return;
            }
            if (srInstance) {
                try { srInstance.onend = null; srInstance.abort(); } catch(e){}
                srInstance = null;
            }

            srInstance = new SR();
            srInstance.lang = 'de-DE';
            srInstance.continuous = true;
            srInstance.interimResults = true;

            srInstance.onresult = (event) => {
                if (isBusy) return;
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const raw = event.results[i][0].transcript.trim();
                    const low = raw.toLowerCase();

                    // Live-Vorschau während Margil spricht
                    if (!event.results[i].isFinal) {
                        if (activeSession || low.includes('neo') || low.includes('nio')) {
                            setSt('listening');
                            document.getElementById('replyBox').innerText = "🎙️ " + raw + " ...";
                        }
                        continue;
                    }

                    // Finaler Satz erkannt!
                    const wakeMatch = low.match(/\b(hey neo|hey nio|hallo neo|ok neo|neo)\b/);
                    if (wakeMatch) {
                        const idx = low.indexOf(wakeMatch[0]) + wakeMatch[0].length;
                        const commandAfterWake = raw.slice(idx).replace(/^[,.\s]+/, '').trim();

                        if (commandAfterWake.length > 2) {
                            // Margil hat direkt gesagt: "Hey Neo, wie ist das Wetter?"
                            activeSession = true;
                            beep(640, 880);
                            processVoiceText(commandAfterWake);
                            return;
                        } else {
                            // Margil hat nur "Hey Neo" gesagt -> Dialog-Modus öffnen!
                            activeSession = true;
                            beep(520, 960);
                            setSt('listening');
                            document.getElementById('replyBox').innerText = "🎙️ Ja, Margil? Sprich einfach weiter...";
                            return;
                        }
                    } else if (activeSession && raw.length > 1) {
                        // Im aktiven Gespräch braucht Margil NICHT nochmal "Hey Neo" zu sagen
                        beep(640, 880);
                        processVoiceText(raw);
                        return;
                    }
                }
            };

            srInstance.onend = () => {
                srInstance = null;
                if (wakeOn && !isBusy) {
                    setTimeout(() => startAlwaysListening(), 250);
                }
            };

            srInstance.onerror = () => {
                srInstance = null;
                if (wakeOn && !isBusy) {
                    setTimeout(() => startAlwaysListening(), 600);
                }
            };

            try { srInstance.start(); } catch(e) { srInstance = null; }
        }

        function processVoiceText(spokenText) {
            isBusy = true;
            if (srInstance) { try { srInstance.onend = null; srInstance.abort(); } catch(e){} srInstance = null; }
            setSt('thinking');
            sendNeo({ message: spokenText });
        }

        player.onplay = () => {
            isBusy = true;
            setSt('speaking');
        };

        player.onended = () => {
            isBusy = false;
            setSt(activeSession ? 'listening' : null);
            if (wakeOn) setTimeout(() => startAlwaysListening(), 250);
        };

        player.onerror = () => {
            isBusy = false;
            setSt(null);
            if (wakeOn) setTimeout(() => startAlwaysListening(), 350);
        };

        async function sendTg() {
            document.getElementById('replyBox').innerText = "Sende Autorisierungsanfrage an Telegram...";
            try {
                const r = await fetch('/telegram_notify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:"📞 NEO Autorisierung angefordert!"}) });
                const d = await r.json();
                document.getElementById('replyBox').innerText = d.ok ? "✅ Telegram-Benachrichtigung erfolgreich gesendet!" : ("⚠️ " + (d.error || "Telegram Fehler"));
            } catch(e) { document.getElementById('replyBox').innerText = "Verbindungsfehler zu Telegram."; }
        }

        function handleImg(ev) {
            const f = ev.target.files[0]; if (!f) return;
            isBusy = true;
            setSt('thinking');
            const r = new FileReader();
            r.onload = e => sendNeo({ image: e.target.result.split(',')[1], message: "Erstelle einen professionellen Objekt-Mängelbericht." });
            r.readAsDataURL(f);
        }

        function quickCmd(t) { isBusy = true; setSt('thinking'); sendNeo({ message: t }); }
        function sendTxt() {
            const inp = document.getElementById('msg');
            if (!inp.value.trim()) return;
            const v = inp.value.trim(); inp.value = '';
            isBusy = true;
            setSt('thinking');
            sendNeo({ message: v });
        }

        async function sendNeo(payload) {
            document.getElementById('actBar').innerHTML = '';
            document.getElementById('replyBox').innerText = "NEO verarbeitet: „" + (payload.message || "Anfrage") + "“...";
            payload.mode = mode;
            payload.memory = mem;
            payload.local_time_str = new Date().toLocaleString('de-DE');

            try {
                const res = await fetch('/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
                const d = await res.json();
                if (d.error) {
                    isBusy = false; setSt(null);
                    document.getElementById('replyBox').innerText = "Fehler: " + d.error;
                    if (wakeOn) startAlwaysListening();
                    return;
                }
                if (d.end_conversation) activeSession = false;
                if (d.new_memory) { mem.push(d.new_memory); saveState(); }
                document.getElementById('replyBox').innerText = d.reply;

                if (d.copy_text) {
                    const b = document.createElement('button'); b.type = 'button'; b.className = 'gold-pill'; b.innerText = '📋 Text kopieren';
                    b.onclick = () => { navigator.clipboard.writeText(d.copy_text); b.innerText = '✓ Kopiert!'; };
                    document.getElementById('actBar').appendChild(b);
                }
                if (d.action_url) {
                    let finalUrl = d.action_url;
                    if (!isMobile && finalUrl.startsWith('intent://')) {
                        const m = finalUrl.match(/text=([^#&]+)/);
                        finalUrl = 'https://wa.me/?text=' + (m ? m[1] : '');
                    }
                    const a = document.createElement('a'); a.href = finalUrl; a.target = '_blank'; a.className = 'gold-pill'; a.innerText = d.action_label || 'Öffnen';
                    document.getElementById('actBar').appendChild(a);
                }
                if (d.audio) {
                    player.src = "data:audio/mp3;base64," + d.audio;
                    player.play().catch(() => {
                        isBusy = false; setSt(null);
                        if (wakeOn) startAlwaysListening();
                    });
                } else {
                    isBusy = false; setSt(null);
                    if (wakeOn) startAlwaysListening();
                }
            } catch(e) {
                isBusy = false; setSt(null);
                document.getElementById('replyBox').innerText = "Server-Verbindungsfehler.";
                if (wakeOn) startAlwaysListening();
            }
        }

        // Startet sofort beim Laden der Seite das permanente Lauschen auf "Hey Neo"!
        window.addEventListener('load', () => {
            startAlwaysListening();
        });
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
- Kalkulator: Büro ~220 m²/Std, 31,50 €/Std netto (4,33 Wochen/Monat). Fertiges Angebot in `copy_text` + WhatsApp URL (`https://wa.me/?text=URL_ENCODED`, `action_label`: "WhatsApp öffnen").
- Gespräch Ende ("Danke", "Stopp", "Pause"): `end_conversation`: true.
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
        "name": "NEO OS",
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
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY fehlt in Render"}), 500
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
