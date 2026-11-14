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
    "background_color": "#05080F",
    "theme_color": "#05080F",
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
  <rect width="512" height="512" rx="120" fill="#05080F"/>
  <circle cx="256" cy="256" r="160" fill="none" stroke="#00E5FF" stroke-width="6" stroke-dasharray="24 14"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#38BDF8" stroke-width="3" stroke-opacity="0.7"/>
  <circle cx="256" cy="256" r="20" fill="#00E5FF"/>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#05080F">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/svg+xml" href="/icon.svg">
    <title>NEO</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        :root {
            --accent: #00E5FF;
            --accent-glow: rgba(0, 229, 255, 0.28);
            --bg-deep: #05080F;
            --card-bg: rgba(15, 23, 42, 0.62);
            --card-border: rgba(255, 255, 255, 0.11);
            --text-primary: #F8FAFC;
            --text-secondary: #94A3B8;
        }

        body.listening {
            --accent: #10B981;
            --accent-glow: rgba(16, 185, 129, 0.35);
        }
        body.thinking {
            --accent: #F59E0B;
            --accent-glow: rgba(245, 158, 11, 0.35);
        }
        body.speaking {
            --accent: #38BDF8;
            --accent-glow: rgba(56, 189, 248, 0.38);
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        body {
            margin: 0;
            background: radial-gradient(circle at 50% 38%, #0F1C34 0%, #05080F 68%, #020408 100%);
            color: var(--text-primary);
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            height: 100dvh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 14px 14px 16px;
            -webkit-font-smoothing: antialiased;
        }

        /* --- TOP HEADER --- */
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 5;
            gap: 8px;
        }

        .pill-btn {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            color: var(--text-primary);
            padding: 7px 12px;
            border-radius: 999px;
            font-size: 11.5px;
            font-weight: 600;
            letter-spacing: 0.4px;
            display: flex;
            align-items: center;
            gap: 7px;
            cursor: pointer;
            transition: border-color 0.2s, transform 0.15s;
        }
        .pill-btn:active { transform: scale(0.96); }

        .status-led {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent);
            box-shadow: 0 0 10px var(--accent);
        }

        .brand-center {
            text-align: center;
        }

        .brand-title {
            font-size: 17px;
            font-weight: 800;
            letter-spacing: 5px;
            padding-left: 5px;
            color: #FFFFFF;
            text-shadow: 0 0 20px var(--accent-glow);
        }

        .clock-display {
            margin-top: 6px;
            text-align: center;
        }

        .clock-time {
            font-family: 'JetBrains Mono', monospace;
            font-size: 32px;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: #FFFFFF;
            line-height: 1.05;
        }

        .clock-date {
            font-size: 11.5px;
            font-weight: 500;
            color: var(--text-secondary);
            margin-top: 3px;
            letter-spacing: 0.3px;
        }

        /* --- MAIN GRID --- */
        .main-stage {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            width: 100%;
            max-width: 540px;
            margin: 8px auto 4px;
            z-index: 4;
        }

        .cards-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .glass-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 11px 13px;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
            transition: border-color 0.2s, background 0.2s;
        }
        .glass-card.clickable { cursor: pointer; }
        .glass-card.clickable:active { background: rgba(30, 41, 59, 0.8); }

        .card-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 6px;
            margin-bottom: 8px;
        }

        .card-label {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-secondary);
        }

        .card-badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            color: var(--accent);
            background: rgba(0, 229, 255, 0.1);
            border: 1px solid rgba(0, 229, 255, 0.25);
            padding: 2px 7px;
            border-radius: 6px;
        }

        .metric-line {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            font-weight: 500;
            color: #CBD5E1;
            margin: 5px 0;
        }

        .progress-bg {
            width: 48%;
            height: 5px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 99px;
            overflow: hidden;
        }

        .progress-bar {
            height: 100%;
            background: var(--accent);
            border-radius: 99px;
            box-shadow: 0 0 8px var(--accent);
        }

        .counter-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 2px;
        }

        .counter-box span {
            display: block;
            font-size: 11px;
            color: var(--text-secondary);
        }

        .counter-box strong {
            font-family: 'JetBrains Mono', monospace;
            font-size: 20px;
            font-weight: 700;
            color: #FFFFFF;
        }

        /* --- NEURAL CORE (CENTER REACTOR) --- */
        .core-stage {
            position: relative;
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
            min-height: 195px;
        }

        .core-status-pill {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10.5px;
            font-weight: 600;
            letter-spacing: 1.4px;
            text-transform: uppercase;
            color: var(--accent);
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid var(--card-border);
            padding: 4px 12px;
            border-radius: 999px;
            margin-bottom: 10px;
        }

        .reactor-rings {
            position: relative;
            width: 175px;
            height: 175px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .r-ring {
            position: absolute;
            border-radius: 50%;
            pointer-events: none;
            transition: border-color 0.25s;
        }

        .r-outer {
            width: 175px;
            height: 175px;
            border: 1.5px dashed rgba(255, 255, 255, 0.22);
            animation: rotCW 28s linear infinite;
        }

        .r-mid {
            width: 138px;
            height: 138px;
            border: 2.5px solid transparent;
            border-top-color: var(--accent);
            border-right-color: var(--accent);
            filter: drop-shadow(0 0 8px var(--accent-glow));
            animation: rotCCW 9s linear infinite;
        }

        .r-inner {
            width: 102px;
            height: 102px;
            border: 1px solid rgba(255, 255, 255, 0.16);
            animation: rotCW 14s linear infinite;
        }

        .r-center {
            width: 68px;
            height: 68px;
            border-radius: 50%;
            background: radial-gradient(circle, var(--accent-glow) 0%, rgba(15, 23, 42, 0.9) 75%);
            border: 1.5px solid var(--accent);
            box-shadow: 0 0 28px var(--accent-glow), inset 0 0 14px var(--accent-glow);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 2px;
            padding-left: 2px;
            color: #FFFFFF;
            transition: transform 0.12s ease;
        }

        body.listening .r-mid { animation-duration: 2.8s; }
        body.thinking .r-mid { animation-duration: 1.4s; }
        body.speaking .r-center { animation: speakBeat 0.42s infinite alternate; }

        @keyframes rotCW { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes rotCCW { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
        @keyframes speakBeat { from { transform: scale(0.95); } to { transform: scale(1.14); } }

        .card-subtext {
            font-size: 12.5px;
            font-weight: 500;
            color: #E2E8F0;
            line-height: 1.45;
        }
        .card-hint {
            font-size: 11.5px;
            font-weight: 600;
            color: var(--accent);
            margin-top: 3px;
        }

        /* --- ACTION BAR --- */
        .action-bar {
            min-height: 36px;
            display: flex;
            gap: 8px;
            justify-content: center;
            align-items: center;
            z-index: 6;
        }

        .action-pill {
            padding: 8px 18px;
            border-radius: 999px;
            background: var(--accent);
            color: #05080F;
            border: none;
            font-size: 12.5px;
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
            box-shadow: 0 4px 18px var(--accent-glow);
        }

        /* --- BOTTOM WAVE & DOCK --- */
        .bottom-area {
            width: 100%;
            max-width: 540px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 8px;
            z-index: 5;
        }

        .wave-strip {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 5px 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 36px;
        }

        .wave-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            color: var(--text-secondary);
            letter-spacing: 0.8px;
        }

        #waveCanvas {
            flex: 1;
            height: 24px;
            margin: 0 10px;
        }

        .nav-dock {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 6px;
            background: rgba(10, 15, 28, 0.88);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            border-radius: 16px;
            padding: 6px;
        }

        .dock-item {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 11px;
            padding: 7px 2px;
            color: var(--text-secondary);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 4px;
            cursor: pointer;
            font-size: 10.5px;
            font-weight: 600;
            transition: all 0.18s;
        }

        .dock-item svg {
            width: 19px;
            height: 19px;
            stroke: currentColor;
            stroke-width: 2;
            fill: none;
        }

        .dock-item.active {
            background: rgba(0, 229, 255, 0.12);
            border-color: rgba(0, 229, 255, 0.35);
            color: #FFFFFF;
        }
        .dock-item.active svg { stroke: var(--accent); }

        /* --- COMMAND DRAWER --- */
        .drawer {
            position: fixed;
            inset: 0;
            background: rgba(5, 8, 15, 0.97);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            z-index: 30;
            display: none;
            flex-direction: column;
            justify-content: space-between;
            padding: 18px 16px 20px;
        }
        .drawer.open { display: flex; }

        .drawer-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 14px;
            border-bottom: 1px solid var(--card-border);
        }

        .drawer-title {
            font-size: 16px;
            font-weight: 800;
            letter-spacing: 1px;
            color: #FFFFFF;
        }

        .close-btn {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.18);
            color: #FFFFFF;
            padding: 7px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
        }

        .tab-bar {
            display: flex;
            gap: 8px;
            margin: 14px 0;
            overflow-x: auto;
        }

        .tab-pill {
            padding: 8px 14px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--card-border);
            color: var(--text-secondary);
            font-size: 12.5px;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
        }

        .tab-pill.active {
            background: var(--accent);
            border-color: var(--accent);
            color: #05080F;
            font-weight: 700;
        }

        .drawer-content {
            flex: 1;
            overflow-y: auto;
            padding: 4px 0;
        }

        .action-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .action-tile {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 14px 12px;
            color: #FFFFFF;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
            cursor: pointer;
        }

        .action-tile svg {
            width: 20px;
            height: 20px;
            stroke: var(--accent);
            stroke-width: 2;
            fill: none;
        }

        .item-card {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            padding: 12px 14px;
            border-radius: 12px;
            margin-bottom: 8px;
            font-size: 14px;
            color: #F8FAFC;
        }

        .done-btn {
            background: rgba(16, 185, 129, 0.16);
            color: #10B981;
            border: 1px solid rgba(16, 185, 129, 0.35);
            border-radius: 8px;
            padding: 5px 10px;
            font-weight: 700;
            cursor: pointer;
        }

        .input-bar {
            display: flex;
            gap: 8px;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid var(--card-border);
            padding: 6px 8px;
            border-radius: 14px;
        }

        .input-bar input {
            flex: 1;
            background: transparent;
            border: none;
            color: #FFFFFF;
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-size: 14.5px;
            padding: 8px;
            outline: none;
        }

        .input-bar button {
            background: var(--accent);
            color: #05080F;
            border: none;
            border-radius: 10px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <!-- TOP BAR -->
    <div class="top-bar">
        <div class="pill-btn" onclick="toggleWakeWord()">
            <div class="status-led"></div>
            <span id="stateLabel">Voice Active</span>
        </div>

        <div class="brand-center">
            <div class="brand-title">NEO</div>
        </div>

        <div class="pill-btn" id="modeBtn" onclick="toggleMode()">
            <span>Arbeit</span>
            <span style="color:var(--accent); font-family:'JetBrains Mono',monospace;">ON</span>
        </div>
    </div>

    <!-- CLOCK -->
    <div class="clock-display">
        <div class="clock-time" id="hudClock">00:00</div>
        <div class="clock-date" id="hudDate">Hamburg • System bereit</div>
    </div>

    <!-- MAIN STAGE -->
    <div class="main-stage">
        <!-- TOP CARDS -->
        <div class="cards-row">
            <div class="glass-card">
                <div class="card-head">
                    <span class="card-label">System</span>
                    <span class="card-badge">Online</span>
                </div>
                <div class="metric-line"><span>Gemini 3.8</span><div class="progress-bg"><div class="progress-bar" style="width:96%"></div></div></div>
                <div class="metric-line"><span>Voice Gate</span><div class="progress-bg"><div class="progress-bar" style="width:92%"></div></div></div>
                <div class="metric-line"><span>Kalender</span><div class="progress-bg"><div class="progress-bar" style="width:100%"></div></div></div>
            </div>

            <div class="glass-card clickable" onclick="openDrawer()">
                <div class="card-head">
                    <span class="card-label">Speicher</span>
                    <span class="card-badge">Sync</span>
                </div>
                <div class="counter-grid">
                    <div class="counter-box">
                        <span>Notizen</span>
                        <strong id="hud-mem">0</strong>
                    </div>
                    <div class="counter-box">
                        <span>Material</span>
                        <strong id="hud-mat">0</strong>
                    </div>
                </div>
            </div>
        </div>

        <!-- CENTER REACTOR -->
        <div class="core-stage" onclick="toggleDirectRecord()">
            <div class="core-status-pill" id="reticleStatus">Neural Core • Bereit</div>
            <div class="reactor-rings">
                <div class="r-ring r-outer"></div>
                <div class="r-ring r-mid"></div>
                <div class="r-ring r-inner"></div>
                <div class="r-center" id="coreEye">NEO</div>
            </div>
        </div>

        <!-- BOTTOM CARDS -->
        <div class="cards-row">
            <div class="glass-card clickable" onclick="quickCmd('Ich fahre jetzt los zum nächsten Termin. Gib mir das Auto-Briefing mit Codes und starte die Navigation.')">
                <div class="card-head">
                    <span class="card-label">Auto-Briefing</span>
                    <span class="card-badge">Go</span>
                </div>
                <div class="card-subtext">Nächster Termin & Codes</div>
                <div class="card-hint">Offene Tasks: <span id="hud-task">0</span></div>
            </div>

            <div class="glass-card clickable" onclick="findParking()">
                <div class="card-head">
                    <span class="card-label">Standort</span>
                    <span class="card-badge">GPS</span>
                </div>
                <div class="card-subtext">Hamburg, DE</div>
                <div class="card-hint">Auto-Position öffnen</div>
            </div>
        </div>
    </div>

    <!-- DYNAMIC ACTION BUTTONS -->
    <div class="action-bar" id="actionBar"></div>

    <!-- BOTTOM WAVE & DOCK -->
    <div class="bottom-area">
        <div class="wave-strip">
            <span class="wave-label">AUDIO</span>
            <canvas id="waveCanvas" width="420" height="40"></canvas>
            <span class="wave-label" style="color:var(--accent);">DE / SQ</span>
        </div>

        <div class="nav-dock">
            <div class="dock-item" onclick="quickCmd('Ich fahre los zum nächsten Termin im Kalender. Gib mir das Briefing und starte die Navigation.')">
                <svg viewBox="0 0 24 24"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
                <span>Navi</span>
            </div>
            <div class="dock-item" onclick="document.getElementById('camInput').click()">
                <svg viewBox="0 0 24 24"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                <span>Kamera</span>
            </div>
            <div class="dock-item" onclick="quickCmd('Erkläre mir ausführlich meine Termine im Kalender für heute und die nächsten Tage.')">
                <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                <span>Kalender</span>
            </div>
            <div class="dock-item active" id="wakeBtn" onclick="toggleWakeWord()">
                <svg viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
                <span>Voice</span>
            </div>
            <div class="dock-item" onclick="openDrawer()">
                <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
                <span>System</span>
            </div>
        </div>
    </div>

    <input type="file" id="camInput" accept="image/*" capture="environment" style="display:none" onchange="handleImage(event)">

    <!-- COMMAND DRAWER -->
    <div class="drawer" id="drawer">
        <div>
            <div class="drawer-top">
                <span class="drawer-title">NEO Command Center</span>
                <button class="close-btn" onclick="closeDrawer()">✕ Schließen</button>
            </div>
            <div class="tab-bar">
                <div class="tab-pill active" id="tab-tools" onclick="switchTab('tools')">Aktionen</div>
                <div class="tab-pill" id="tab-memory" onclick="switchTab('memory')">Notizen (<span id="c-mem">0</span>)</div>
                <div class="tab-pill" id="tab-materials" onclick="switchTab('materials')">Material (<span id="c-mat">0</span>)</div>
                <div class="tab-pill" id="tab-tasks" onclick="switchTab('tasks')">Tasks (<span id="c-task">0</span>)</div>
            </div>
        </div>

        <div class="drawer-content" id="drawerBody"></div>

        <div class="input-bar">
            <input type="text" id="msg" placeholder="Befehl, Kalkulation oder Übersetzung..." onkeypress="if(event.key==='Enter'){closeDrawer();sendText();}">
            <button onclick="closeDrawer();sendText();">Senden</button>
        </div>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        function updateHudClock() {
            const now = new Date();
            document.getElementById('hudClock').innerText = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
            document.getElementById('hudDate').innerText = now.toLocaleDateString('de-DE', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });
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
            let color = '#00E5FF';

            if (currentState === 'listening') {
                amp = 4 + audioEnergy * 0.42;
                color = '#10B981';
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
            wCtx.lineWidth = 2.2;
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
            const modeText = workMode === 'ARBEIT' ? 'Arbeit' : 'Privat';
            document.getElementById('modeBtn').innerHTML = `<span>${modeText}</span><span style="color:var(--accent); font-family:'JetBrains Mono',monospace;">ON</span>`;
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
                stateLabel.innerText = "Hört zu...";
                reticleStatus.innerText = "Audio Input • Aktiv";
            } else if (state === 'thinking') {
                document.body.classList.add('thinking');
                stateLabel.innerText = "Analysiert...";
                reticleStatus.innerText = "Neural Processing";
            } else if (state === 'speaking') {
                document.body.classList.add('speaking');
                stateLabel.innerText = "NEO spricht";
                reticleStatus.innerText = "Voice Output • Live";
            } else {
                stateLabel.innerText = wakeEnabled ? "Voice Active" : "Stummgeschaltet";
                reticleStatus.innerText = "Neural Core • Bereit";
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
            document.querySelectorAll('.tab-pill').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            const body = document.getElementById('drawerBody');

            if (tab === 'tools') {
                body.innerHTML = `
                    <div class="action-grid">
                        <div class="action-tile" onclick="closeDrawer();quickCmd('Ich fahre los zum nächsten Termin im Kalender. Gib mir das Auto-Briefing mit Objekt-Codes und starte die Navigation.')">
                            <svg viewBox="0 0 24 24"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
                            <span>Auto-Briefing & Navi</span>
                        </div>
                        <div class="action-tile" onclick="closeDrawer();quickCmd('Erkläre mir ausführlich meine Termine im Kalender für heute und die nächsten Tage.')">
                            <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                            <span>Kalender erklären</span>
                        </div>
                        <div class="action-tile" onclick="closeDrawer();quickCmd('Kalkuliere ein Reinigungsangebot für 600 Quadratmeter Büro, zweimal pro Woche, und mach die WhatsApp-Nachricht fertig.')">
                            <svg viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="12" y2="14"/></svg>
                            <span>Angebots-Rechner</span>
                        </div>
                        <div class="action-tile" onclick="closeDrawer();document.getElementById('camInput').click()">
                            <svg viewBox="0 0 24 24"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                            <span>Mängelbericht Foto</span>
                        </div>
                        <div class="action-tile" onclick="closeDrawer();saveParking()">
                            <svg viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                            <span>Parkplatz merken</span>
                        </div>
                        <div class="action-tile" onclick="closeDrawer();findParking()">
                            <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>
                            <span>Auto finden (GPS)</span>
                        </div>
                    </div>`;
                return;
            }
            let list = tab === 'materials' ? userMaterials : (tab === 'tasks' ? userTasks : userMemory);
            body.innerHTML = list.length === 0
                ? `<div style="color:#64748B; text-align:center; margin-top:40px; font-size:14px;">Keine Einträge vorhanden, Sir.</div>`
                : list.map((item, idx) => `<div class="item-card"><span>${idx + 1}. ${item}</span><button class="done-btn" onclick="deleteItem('${tab}', ${idx})">✓</button></div>`).join('');
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
                reticleStatus.innerText = "Parkplatz gespeichert";
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
                    reticleStatus.innerText = "Systemfehler";
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
                    cBtn.innerText = "Text kopieren";
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
