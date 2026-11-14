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
    "background_color": "#02060D",
    "theme_color": "#02060D",
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
  <rect width="512" height="512" rx="120" fill="#02060D"/>
  <circle cx="256" cy="256" r="165" fill="none" stroke="#00D4FF" stroke-width="8" stroke-dasharray="28 14"/>
  <circle cx="256" cy="256" r="115" fill="none" stroke="#00F5D4" stroke-width="4"/>
  <circle cx="256" cy="256" r="24" fill="#00D4FF"/>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#02060D">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/svg+xml" href="/icon.svg">
    <title>NEO HUD</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');

        :root {
            --hud-blue: #00D4FF;
            --hud-cyan: #00F5D4;
            --hud-bg: #02060D;
            --panel-bg: rgba(4, 18, 34, 0.65);
            --panel-border: rgba(0, 212, 255, 0.35);
            --text-main: #E0F7FF;
            --text-dim: rgba(160, 225, 255, 0.6);
        }

        body.listening { --hud-blue: #00FF88; --hud-cyan: #00FF88; --panel-border: rgba(0, 255, 136, 0.55); }
        body.thinking { --hud-blue: #F59E0B; --hud-cyan: #FBBF24; --panel-border: rgba(245, 158, 11, 0.55); }
        body.speaking { --hud-blue: #38BDF8; --hud-cyan: #00F5D4; --panel-border: rgba(56, 189, 248, 0.65); }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        body {
            margin: 0;
            background: radial-gradient(circle at 50% 45%, #07192E 0%, #02060D 72%, #000205 100%);
            color: var(--text-main);
            font-family: 'Rajdhani', sans-serif;
            height: 100dvh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 10px 12px 14px;
            position: relative;
        }

        body::before {
            content: "";
            position: fixed;
            inset: 0;
            background-image:
                linear-gradient(rgba(0, 212, 255, 0.04) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 212, 255, 0.04) 1px, transparent 1px);
            background-size: 36px 36px;
            pointer-events: none;
            z-index: 0;
        }

        .visor-frame {
            position: fixed;
            inset: 6px;
            border: 1px solid rgba(0, 212, 255, 0.22);
            border-radius: 22px;
            pointer-events: none;
            z-index: 1;
            box-shadow: inset 0 0 35px rgba(0, 212, 255, 0.08);
        }

        .hud-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            z-index: 5;
            position: relative;
        }

        .hud-chip {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            padding: 5px 10px;
            border-radius: 8px;
            font-size: 11px;
            letter-spacing: 1.2px;
            text-transform: uppercase;
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 0 12px rgba(0, 212, 255, 0.12);
            cursor: pointer;
        }

        .pulse-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--hud-blue);
            box-shadow: 0 0 8px var(--hud-blue);
        }

        .neo-header-center {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-top: -2px;
        }

        .neo-title-badge {
            font-family: 'Orbitron', sans-serif;
            font-weight: 900;
            font-size: 18px;
            letter-spacing: 6px;
            color: #FFFFFF;
            text-shadow: 0 0 14px var(--hud-blue), 0 0 28px var(--hud-blue);
            background: linear-gradient(180deg, rgba(0, 212, 255, 0.18), rgba(0, 212, 255, 0.04));
            border: 1px solid var(--panel-border);
            border-top: 2px solid var(--hud-blue);
            padding: 4px 26px 5px 32px;
            clip-path: polygon(10% 0%, 90% 0%, 100% 100%, 0% 100%);
        }

        .hud-clock-box {
            text-align: center;
            margin-top: 4px;
            background: rgba(2, 12, 24, 0.6);
            border: 1px solid rgba(0, 212, 255, 0.2);
            padding: 3px 14px;
            border-radius: 6px;
        }

        .hud-time {
            font-family: 'Orbitron', sans-serif;
            font-size: 17px;
            font-weight: 700;
            color: var(--text-main);
            letter-spacing: 1.5px;
        }

        .hud-date {
            font-size: 9.5px;
            letter-spacing: 1.5px;
            color: var(--text-dim);
            text-transform: uppercase;
        }

        .hud-stage {
            flex: 1;
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            align-items: center;
            gap: 8px;
            z-index: 4;
            position: relative;
            width: 100%;
            max-width: 960px;
            margin: 0 auto;
        }

        .hud-side-col {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .hud-card {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-left: 3px solid var(--hud-blue);
            border-radius: 8px;
            padding: 8px 10px;
            backdrop-filter: blur(8px);
            box-shadow: 0 0 18px rgba(0, 212, 255, 0.08);
        }

        .hud-card-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 9.5px;
            letter-spacing: 1.5px;
            color: var(--hud-blue);
            margin-bottom: 6px;
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid rgba(0, 212, 255, 0.18);
            padding-bottom: 3px;
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            margin: 4px 0;
            color: var(--text-dim);
        }

        .bar-track {
            width: 54%;
            height: 5px;
            background: rgba(0, 212, 255, 0.12);
            border-radius: 3px;
            overflow: hidden;
        }

        .bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--hud-blue), var(--hud-cyan));
            box-shadow: 0 0 8px var(--hud-blue);
            transition: width 0.5s ease;
        }

        .env-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 5px;
            font-size: 11px;
        }
        .env-item strong {
            color: #FFFFFF;
            font-size: 13px;
            display: block;
        }

        .reticle-wrap {
            position: relative;
            width: 240px;
            height: 240px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
        }

        .reticle-label {
            position: absolute;
            top: -12px;
            font-family: 'Orbitron', sans-serif;
            font-size: 9px;
            letter-spacing: 2px;
            color: var(--hud-blue);
            background: rgba(2, 12, 24, 0.8);
            padding: 2px 10px;
            border: 1px solid var(--panel-border);
            border-radius: 10px;
        }

        .ring {
            position: absolute;
            border-radius: 50%;
            pointer-events: none;
            transition: border-color 0.25s, box-shadow 0.25s;
        }

        .ring-outer {
            width: 228px;
            height: 228px;
            border: 2px dashed var(--hud-blue);
            opacity: 0.55;
            animation: spinCW 24s linear infinite;
        }

        .ring-mid {
            width: 178px;
            height: 178px;
            border: 3px solid transparent;
            border-top-color: var(--hud-blue);
            border-bottom-color: var(--hud-cyan);
            box-shadow: 0 0 20px rgba(0, 212, 255, 0.25);
            animation: spinCCW 10s linear infinite;
        }

        .ring-inner {
            width: 124px;
            height: 124px;
            border: 1.5px solid var(--hud-cyan);
            opacity: 0.8;
            animation: spinCW 6s linear infinite;
        }

        .core-eye {
            width: 68px;
            height: 68px;
            border-radius: 50%;
            background: radial-gradient(circle, var(--hud-cyan) 0%, rgba(0, 212, 255, 0.25) 55%, transparent 75%);
            border: 2px solid var(--hud-blue);
            box-shadow: 0 0 25px var(--hud-blue), inset 0 0 15px var(--hud-cyan);
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Orbitron', sans-serif;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.5px;
            color: #FFFFFF;
            transition: transform 0.12s ease;
        }

        body.listening .ring-mid { animation-duration: 3s; }
        body.thinking .ring-outer { animation-duration: 4s; }
        body.thinking .ring-mid { animation-duration: 1.8s; }
        body.speaking .core-eye { animation: corePulse 0.45s infinite alternate; }

        @keyframes spinCW { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes spinCCW { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
        @keyframes corePulse { from { transform: scale(0.95); } to { transform: scale(1.16); } }

        .action-bar {
            min-height: 36px;
            display: flex;
            gap: 8px;
            justify-content: center;
            align-items: center;
            z-index: 6;
        }

        .action-pill {
            padding: 6px 16px;
            border-radius: 16px;
            background: rgba(0, 212, 255, 0.18);
            border: 1px solid var(--hud-blue);
            color: #FFFFFF;
            font-size: 12.5px;
            font-weight: 600;
            letter-spacing: 1px;
            text-decoration: none;
            cursor: pointer;
            box-shadow: 0 0 14px rgba(0, 212, 255, 0.25);
        }

        .hud-bottom {
            width: 100%;
            max-width: 960px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 8px;
            z-index: 5;
        }

        .voice-wave-box {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 4px 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 36px;
        }

        .voice-tag {
            font-family: 'Orbitron', sans-serif;
            font-size: 9px;
            letter-spacing: 1.5px;
            color: var(--hud-blue);
            white-space: nowrap;
        }

        #waveCanvas {
            flex: 1;
            height: 26px;
            margin: 0 10px;
        }

        .hud-dock {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 6px;
            background: rgba(4, 18, 34, 0.85);
            border: 1px solid var(--panel-border);
            border-radius: 12px;
            padding: 6px;
        }

        .dock-btn {
            background: rgba(0, 212, 255, 0.06);
            border: 1px solid rgba(0, 212, 255, 0.22);
            border-radius: 8px;
            padding: 6px 2px;
            color: var(--text-main);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 2px;
            cursor: pointer;
            font-family: 'Orbitron', sans-serif;
            font-size: 8.5px;
            letter-spacing: 0.8px;
        }
        .dock-btn span.ico { font-size: 15px; }
        .dock-btn.active {
            border-color: var(--hud-cyan);
            background: rgba(0, 245, 212, 0.16);
            box-shadow: 0 0 10px rgba(0, 245, 212, 0.25);
        }

        @media (max-width: 680px) {
            .hud-stage {
                grid-template-columns: 1fr;
                grid-template-rows: auto 1fr auto;
            }
            .hud-side-col {
                flex-direction: row;
                justify-content: space-between;
            }
            .hud-card {
                flex: 1;
                padding: 6px 8px;
            }
            .reticle-wrap {
                width: 205px;
                height: 205px;
                margin: 0 auto;
            }
            .ring-outer { width: 196px; height: 196px; }
            .ring-mid { width: 152px; height: 152px; }
            .ring-inner { width: 106px; height: 106px; }
        }

        .drawer {
            position: fixed;
            inset: 0;
            background: rgba(2, 6, 13, 0.96);
            backdrop-filter: blur(20px);
            z-index: 30;
            display: none;
            flex-direction: column;
            justify-content: space-between;
            padding: 18px;
        }
        .drawer.open { display: flex; }

        .drawer-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--panel-border);
            font-family: 'Orbitron', sans-serif;
            letter-spacing: 2px;
        }

        .tabs {
            display: flex;
            gap: 8px;
            margin: 12px 0;
            overflow-x: auto;
        }
        .tab {
            padding: 7px 13px;
            border-radius: 8px;
            background: rgba(0, 212, 255, 0.08);
            border: 1px solid rgba(0, 212, 255, 0.25);
            color: var(--text-main);
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
        }
        .tab.active {
            background: var(--hud-blue);
            color: #02060D;
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
            background: rgba(0, 212, 255, 0.06);
            border: 1px solid rgba(0, 212, 255, 0.2);
            padding: 10px 14px;
            border-radius: 8px;
            margin-bottom: 8px;
            font-size: 14px;
        }

        .check-btn {
            background: rgba(0, 245, 212, 0.2);
            color: var(--hud-cyan);
            border: 1px solid var(--hud-cyan);
            border-radius: 6px;
            padding: 4px 10px;
            font-weight: 700;
            cursor: pointer;
        }

        .quick-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }
        .q-btn {
            padding: 11px;
            border-radius: 8px;
            background: rgba(0, 212, 255, 0.08);
            border: 1px solid var(--panel-border);
            color: var(--text-main);
            font-size: 13px;
            text-align: left;
            cursor: pointer;
        }

        .text-dock {
            display: flex;
            gap: 8px;
            background: rgba(0, 212, 255, 0.08);
            border: 1px solid var(--panel-border);
            padding: 6px 8px;
            border-radius: 10px;
        }
        .text-dock input {
            flex: 1;
            background: transparent;
            border: none;
            color: white;
            font-size: 15px;
            padding: 6px;
            outline: none;
        }
        .text-dock button {
            background: var(--hud-blue);
            color: #02060D;
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-family: 'Orbitron', sans-serif;
            font-weight: 700;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="visor-frame"></div>

    <div class="hud-top">
        <div class="hud-chip" onclick="toggleWakeWord()">
            <div class="pulse-dot"></div>
            <span id="stateLabel">VOICE ACTIVE</span>
        </div>

        <div class="neo-header-center">
            <div class="neo-title-badge">NEO</div>
            <div class="hud-clock-box">
                <div class="hud-time" id="hudClock">00:00</div>
                <div class="hud-date" id="hudDate">HAMBURG • SYSTEM ONLINE</div>
            </div>
        </div>

        <div class="hud-chip" id="modeBtn" onclick="toggleMode()">
            <span>ARBEIT</span>
            <span style="color:var(--hud-cyan);">100%</span>
        </div>
    </div>

    <div class="hud-stage">
        <div class="hud-side-col">
            <div class="hud-card">
                <div class="hud-card-title"><span>SYSTEM STATUS</span><span>ONLINE</span></div>
                <div class="stat-row"><span>GEMINI 3.8</span><div class="bar-track"><div class="bar-fill" style="width:96%"></div></div></div>
                <div class="stat-row"><span>VOICE GATE</span><div class="bar-track"><div class="bar-fill" style="width:92%"></div></div></div>
                <div class="stat-row"><span>MODULES</span><div class="bar-track"><div class="bar-fill" style="width:100%"></div></div></div>
            </div>

            <div class="hud-card">
                <div class="hud-card-title"><span>ENVIRONMENT</span><span>HAMBURG</span></div>
                <div class="env-grid">
                    <div class="env-item"><span>NOTIZEN</span><strong id="hud-mem">0</strong></div>
                    <div class="env-item"><span>MATERIAL</span><strong id="hud-mat">0</strong></div>
                </div>
            </div>
        </div>

        <div class="reticle-wrap" onclick="toggleDirectRecord()">
            <div class="reticle-label" id="reticleStatus">NEURAL CORE • READY</div>
            <div class="ring ring-outer"></div>
            <div class="ring ring-mid"></div>
            <div class="ring ring-inner"></div>
            <div class="core-eye" id="coreEye">NEO</div>
        </div>

        <div class="hud-side-col">
            <div class="hud-card" onclick="quickCmd('Ich fahre jetzt los zum nächsten Termin. Gib mir das Auto-Briefing mit Codes und starte die Navigation.')" style="cursor:pointer;">
                <div class="hud-card-title"><span>AUTO-BRIEFING</span><span>GO</span></div>
                <div style="font-size:11.5px; color:var(--text-main); line-height:1.35;">
                    • Nächster Termin + Codes<br>
                    • Direkt-Navi starten<br>
                    • Offene Tasks: <strong id="hud-task" style="color:var(--hud-cyan);">0</strong>
                </div>
            </div>

            <div class="hud-card" onclick="findParking()" style="cursor:pointer;">
                <div class="hud-card-title"><span>LOCATION</span><span>GPS</span></div>
                <div style="font-size:11.5px; color:var(--text-dim);">
                    HAMBURG, DE<br>
                    <span style="color:var(--hud-cyan);">Tippen für Auto-GPS</span>
                </div>
            </div>
        </div>
    </div>

    <div class="action-bar" id="actionBar"></div>

    <div class="hud-bottom">
        <div class="voice-wave-box">
            <span class="voice-tag" id="waveLabel">VOICE ASSISTANT</span>
            <canvas id="waveCanvas" width="420" height="40"></canvas>
            <span class="voice-tag" style="color:var(--hud-cyan);">DE / SQ</span>
        </div>

        <div class="hud-dock">
            <div class="dock-btn" onclick="quickCmd('Ich fahre los zum nächsten Termin im Kalender. Gib mir das Briefing und starte die Navigation.')">
                <span class="ico">🧭</span>
                <span>LOSFAHREN</span>
            </div>
            <div class="dock-btn" onclick="document.getElementById('camInput').click()">
                <span class="ico">📷</span>
                <span>MÄNGEL-CAM</span>
            </div>
            <div class="dock-btn" onclick="quickCmd('Erkläre mir ausführlich meine Termine im Kalender für heute und die nächsten Tage.')">
                <span class="ico">📅</span>
                <span>CALENDAR</span>
            </div>
            <div class="dock-btn active" id="wakeBtn" onclick="toggleWakeWord()">
                <span class="ico">🎙️</span>
                <span>VOICE</span>
            </div>
            <div class="dock-btn" onclick="openDrawer()">
                <span class="ico">⚙️</span>
                <span>SYSTEM</span>
            </div>
        </div>
    </div>

    <input type="file" id="camInput" accept="image/*" capture="environment" style="display:none" onchange="handleImage(event)">

    <div class="drawer" id="drawer">
        <div>
            <div class="drawer-header">
                <span>NEO COMMAND SYSTEM</span>
                <button class="hud-chip" onclick="closeDrawer()">✕ SCHLIESSEN</button>
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
            <input type="text" id="msg" placeholder="Befehl, Kalkulation oder Übersetzung..." onkeypress="if(event.key==='Enter'){closeDrawer();sendText();}">
            <button onclick="closeDrawer();sendText();">SEND</button>
        </div>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        function updateHudClock() {
            const now = new Date();
            document.getElementById('hudClock').innerText = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
            document.getElementById('hudDate').innerText = now.toLocaleDateString('de-DE', { weekday: 'long', day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase();
        }
        updateHudClock();
        setInterval(updateHudClock, 10000);

        const waveCanvas = document.getElementById('waveCanvas');
        const wCtx = waveCanvas.getContext('2d');
        let audioEnergy = 0;
        let currentState = 'idle';

        function drawWaveform() {
            wCtx.clearRect(0, 0, waveCanvas.width, waveCanvas.height);
            const midY = waveCanvas.height / 2;
            const t = Date.now() * 0.008;

            let amp = 2.5;
            let color = '#00D4FF';

            if (currentState === 'listening') {
                amp = 4 + audioEnergy * 0.42;
                color = '#00FF88';
            } else if (currentState === 'thinking') {
                amp = 8;
                color = '#F59E0B';
            } else if (currentState === 'speaking') {
                amp = 7 + Math.abs(Math.sin(t * 1.4)) * 10;
                color = '#38BDF8';
            } else {
                audioEnergy *= 0.85;
            }

            wCtx.beginPath();
            wCtx.strokeStyle = color;
            wCtx.lineWidth = 2;
            for (let x = 0; x < waveCanvas.width; x += 3) {
                const env = Math.sin((x / waveCanvas.width) * Math.PI);
                const y = midY + Math.sin(x * 0.06 + t) * amp * env;
                if (x === 0) wCtx.moveTo(x, y);
                else wCtx.lineTo(x, y);
            }
            wCtx.stroke();
            requestAnimationFrame(drawWaveform);
        }
        drawWaveform();

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

        const actionBar = document.getElementById('actionBar');
        const stateLabel = document.getElementById('stateLabel');
        const reticleStatus = document.getElementById('reticleStatus');
        const coreEye = document.getElementById('coreEye');
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
            document.getElementById('hud-mem').innerText = userMemory.length;
            document.getElementById('hud-mat').innerText = userMaterials.length;
            document.getElementById('hud-task').innerText = userTasks.length;
            document.getElementById('modeBtn').innerHTML = `<span>${workMode}</span><span style="color:var(--hud-cyan);">100%</span>`;
        }
        updateBadges();

        function toggleMode() {
            workMode = (workMode === 'ARBEIT') ? 'PRIVAT' : 'ARBEIT';
            updateBadges();
        }

        function setState(state) {
            currentState = state || 'idle';
            document.body.classList.remove('listening', 'thinking', 'speaking');
            if (state === 'listening') {
                document.body.classList.add('listening');
                stateLabel.innerText = "LISTENING...";
                reticleStatus.innerText = "AUDIO INPUT • ACTIVE";
            } else if (state === 'thinking') {
                document.body.classList.add('thinking');
                stateLabel.innerText = "PROCESSING...";
                reticleStatus.innerText = "TARGET ANALYSIS";
            } else if (state === 'speaking') {
                document.body.classList.add('speaking');
                stateLabel.innerText = "NEO SPEAKING";
                reticleStatus.innerText = "VOICE OUTPUT • LIVE";
            } else {
                stateLabel.innerText = wakeEnabled ? "VOICE ACTIVE" : "VOICE MUTED";
                reticleStatus.innerText = "NEURAL CORE • READY";
            }
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
            coreEye.style.transform = 'scale(1)';
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
                    coreEye.style.transform = `scale(${1 + Math.min(0.28, avg * 0.005)})`;

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
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Ich fahre los zum nächsten Termin im Kalender. Gib mir das Auto-Briefing mit Objekt-Codes und starte die Navigation.')">🚗 Auto-Briefing & Navi</div>
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Erkläre mir ausführlich meine Termine im Kalender für heute und die nächsten Tage.')">📅 Kalender erklären</div>
                        <div class="q-btn" onclick="closeDrawer();quickCmd('Kalkuliere ein Reinigungsangebot für 600 Quadratmeter Büro, zweimal pro Woche, und mach die WhatsApp-Nachricht fertig.')">💶 Angebots-Rechner</div>
                        <div class="q-btn" onclick="closeDrawer();document.getElementById('camInput').click()">📷 Mängelbericht Foto</div>
                        <div class="q-btn" onclick="closeDrawer();saveParking()">🅿️ Parkplatz merken</div>
                        <div class="q-btn" onclick="closeDrawer();findParking()">🧭 Auto finden (GPS)</div>
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
                reticleStatus.innerText = "GPS PARKPLATZ GESPEICHERT";
            });
        }

        function findParking() {
            const p = JSON.parse(localStorage.getItem('neo_parking') || 'null');
            if (!p) { saveParking(); return; }
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
                        message: note || "Erstelle anhand dieses Fotos einen professionellen Objekt-Mängelbericht mit Datum und Uhrzeit für den Kunden und mach ihn für WhatsApp fertig."
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
                    reticleStatus.innerText = "SYSTEM ERROR";
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
                    desc = desc_m.group(1).strip().replace("\\n", " ")[:120] if desc_m else ""
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
Antworte höflich, ohne Sternchen/Markdown, und nenne den Nutzer 'Sir'. Standard-Sprache ist Deutsch (außer bei Übersetzungen ins Albanische).

WICHTIGE REGELN & 4 SPEZIAL-MODULE:
1. NUR DIREKTE STIMME BEACHTEN (SEHR WICHTIG):
   - Konzentriere dich ausschließlich auf die lauteste, nahe Hauptstimme (Sir). Ignoriere Hintergrundstimmen im Raum, TV, Radio oder Telefon!
   - Wenn keine klare direkte Anfrage vorliegt, setze `"ignore_background": true` und `"reply": ""`.

2. MODUL A — AUTO-BRIEFING & NAVIGATION ("Ich fahre los", "Nächster Termin", "Losfahren"):
   - Lies den nächsten anstehenden Termin aus 'Kalender-Termine'.
   - Prüfe in 'Notizen' (memory), ob es Türcodes, Schlüssel-Infos oder Ansprechpartner zu diesem Objekt/Kunden gibt!
   - Fasse beides (Termin + Codes/Notizen) in 2-3 klaren Sätzen zusammen und setze `action_url` auf Google Maps Navigation: `"https://www.google.com/maps/dir/?api=1&destination=ADRESSE_URL_ENCODED&travelmode=driving"` mit `action_label`: `"Navigation starten"`.

3. MODUL B — ZWEISPRACHIGER DOLMETSCHER DEUTSCH <-> ALBANISCH ("Übersetze...", "Përktheje..."):
   - Wenn Sir sagt "Übersetze für das Team..." oder auf Deutsch spricht und Albanisch will: Übersetze den Satz in natürliches, freundliches Albanisch, setze `reply` auf die albanische Übersetzung (damit NEO es laut vorliest!), `voice_lang`: `"sq"` und schreibe die Übersetzung zusätzlich in `copy_text`.
   - Wenn Sir auf Albanisch spricht und die deutsche Übersetzung für einen Kunden braucht: Setze `reply` auf die höfliche deutsche Übersetzung, `voice_lang`: `"de"` und schreibe sie in `copy_text`.

4. MODUL C — ANGEBOTS- & STUNDEN-KALKULATOR ("Kalkuliere...", "Angebot berechnen..."):
   - Nutze realistische Richtwerte der Gebäudereinigung in Deutschland:
     * Büroreinigung: ca. 220 m²/Stunde | Unterhaltsreinigung / Praxis: ca. 160 m²/Stunde | Treppenhaus: ca. 180 m²/Stunde | Glasreinigung: ca. 45 m²/Stunde.
     * Verrechnungssatz: ca. 31,50 € netto/Stunde (4,33 Wochen pro Monat).
   - Nenne in `reply` die geschätzten Stunden pro Einsatz, die monatlichen Stunden und den monatlichen Netto-Preis in 2-3 Sätzen.
   - Erstelle ein fertiges, professionelles Angebots-Kurzschreiben in `copy_text` und bereite den WhatsApp-Business-Intent in `action_url` vor (`action_label`: `"Angebot per WhatsApp"`).

5. MODUL D — OBJEKT-MÄNGELBERICHT MIT KAMERA:
   - Wenn ein Bild gesendet wird: Beschreibe den Zustand/Mangel sachlich und professionell in 2 Sätzen für Sir.
   - Schreibe einen formellen Mängelbericht (inkl. Datum & Uhrzeit `{local_time}`, Befund und Maßnahme) in `copy_text` und setze `action_url` auf den WhatsApp-Intent (`action_label`: `"Bericht senden"`).

6. KALENDER & ALLGEMEINES:
   - Bei allgemeinen Kalenderfragen erkläre die Termine in 3-5 Sätzen mit Datum, Uhrzeit und Ort.
   - WHATSAPP (ANDROID NATIVE INTENT — NIEMALS web.whatsapp.com!):
     * Nummer bekannt: `"https://wa.me/49176...?text=URL_ENCODED"`
     * Nummer NICHT bekannt (ARBEIT): `"intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp.w4b;end"`
     * Nummer NICHT bekannt (PRIVAT): `"intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp;end"`
   - LISTEN: `new_memory`/`delete_memory` (Codes/Notizen), `new_material`/`delete_material` (Material), `new_task`/`delete_task` (Aufgaben).
   - GESPRÄCH ENDE: Bei "Danke", "Stopp", "Fertig", "Das war's": `"end_conversation": true`.

Antworte AUSSCHLIESSLICH als gültiges JSON-Objekt (ohne Markdown-Codeblöcke):
{{
  "reply": "Deine gesprochene Antwort an Sir",
  "voice_lang": "de",
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

async def make_voice(text, voice_lang="de"):
    clean_text = text.replace("*", "").replace("#", "").replace("...", ".").strip()
    voice_name = "sq-AL-IlirNeural" if voice_lang == "sq" else "de-DE-FlorianMultilingualNeural"
    communicate = edge_tts.Communicate(clean_text, voice_name, rate="+5%")
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
        if "audio" in data or any(w in lower_msg for w in ["kalender", "termin", "heute", "morgen", "woche", "statusbericht", "plan", "besichtigung", "fahre", "los", "nächste"]):
            calendar_info = get_ical_events()

        client = genai.Client(api_key=api_key)
        contents = []

        if "image" in data:
            contents.append(types.Part.from_bytes(data=base64.b64decode(data["image"]), mime_type="image/jpeg"))
            contents.append(msg or "Erstelle anhand dieses Fotos einen professionellen Objekt-Mängelbericht.")
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
        voice_lang = result.get("voice_lang", "de")
        audio_b64 = asyncio.run(make_voice(reply, voice_lang))

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
