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
TG_STATE = {
    "chat_id": os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
    "last_update_id": 0,
    "notified_events": set()
}

MANIFEST_JSON = {
    "name": "NEO",
    "short_name": "NEO",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#050811",
    "theme_color": "#050811",
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
  <rect width="512" height="512" rx="120" fill="#050811"/>
  <circle cx="256" cy="256" r="160" fill="none" stroke="#00F0FF" stroke-width="10" stroke-dasharray="28 16"/>
  <circle cx="256" cy="256" r="105" fill="none" stroke="#6366F1" stroke-width="5"/>
  <circle cx="256" cy="256" r="24" fill="#00F0FF"/>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#050811">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/svg+xml" href="/icon.svg">
    <title>NEO OS</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        :root {
            --accent: #00F0FF;
            --accent-2: #6366F1;
            --glow: rgba(0, 240, 255, 0.32);
            --bg: #050811;
            --glass: rgba(17, 25, 46, 0.72);
            --border: rgba(255, 255, 255, 0.10);
            --text: #F8FAFC;
            --muted: #94A3B8;
        }

        body.listening { --accent: #10B981; --accent-2: #34D399; --glow: rgba(16, 185, 129, 0.45); }
        body.thinking  { --accent: #F59E0B; --accent-2: #FB923C; --glow: rgba(245, 158, 11, 0.45); }
        body.speaking  { --accent: #38BDF8; --accent-2: #A855F7; --glow: rgba(168, 85, 247, 0.45); }

        * {
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
            touch-action: manipulation;
        }

        html, body {
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100dvh;
            overflow: hidden;
            background:
                radial-gradient(circle at 15% 10%, rgba(99, 102, 241, 0.22) 0%, transparent 45%),
                radial-gradient(circle at 85% 85%, rgba(0, 240, 255, 0.14) 0%, transparent 45%),
                #050811;
            color: var(--text);
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        }

        .app-shell {
            width: 100%;
            max-width: 540px;
            height: 100dvh;
            margin: 0 auto;
            padding: 12px 14px 14px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 10px;
        }

        /* TOP HEADER */
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .pill-btn {
            background: var(--glass);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 7px 13px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            display: inline-flex;
            align-items: center;
            gap: 7px;
            cursor: pointer;
        }
        .pill-btn:active { transform: scale(0.96); }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent);
            box-shadow: 0 0 10px var(--accent);
        }

        .os-logo {
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 3px;
            color: var(--accent);
        }

        /* HERO PROFILE CARD */
        .hero-card {
            background: linear-gradient(135deg, rgba(23, 33, 62, 0.85), rgba(11, 17, 34, 0.90));
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 12px;
            display: flex;
            align-items: center;
            gap: 14px;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.45);
        }

        .neo-avatar {
            width: 78px;
            height: 88px;
            border-radius: 18px;
            padding: 2.5px;
            background: linear-gradient(145deg, var(--accent), var(--accent-2));
            box-shadow: 0 0 22px var(--glow);
            flex-shrink: 0;
            cursor: pointer;
        }

        .neo-avatar-img {
            width: 100%;
            height: 100%;
            border-radius: 15.5px;
            overflow: hidden;
            background: #090E1D;
        }

        .neo-avatar-img img {
            width: 100%;
            height: 115%;
            object-fit: cover;
            object-position: center 12%;
            display: block;
        }

        body.speaking .neo-avatar-img img {
            animation: pulseAvatar 0.9s infinite alternate ease-in-out;
        }
        @keyframes pulseAvatar {
            from { transform: scale(1); }
            to { transform: scale(1.06); }
        }

        .hero-info {
            flex: 1;
            min-width: 0;
        }

        .hero-greeting {
            font-size: 19px;
            font-weight: 800;
            letter-spacing: -0.3px;
            color: #FFFFFF;
        }

        .hero-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 7px;
        }

        .meta-tag {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 4px 8px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            font-weight: 700;
            color: var(--accent);
        }

        /* NEXT EVENT BANNER */
        .mission-card {
            background: var(--glass);
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 16px;
            padding: 11px 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            cursor: pointer;
        }
        .mission-card:active { background: rgba(0, 240, 255, 0.10); }

        .mission-label {
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1.2px;
            text-transform: uppercase;
            color: var(--accent);
        }

        .mission-title {
            font-size: 14px;
            font-weight: 700;
            color: #FFFFFF;
            margin-top: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .mission-sub {
            font-size: 11.5px;
            color: var(--muted);
            margin-top: 1px;
        }

        /* 2x2 BENTO ACTION GRID */
        .bento-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            flex: 1;
            min-height: 0;
        }

        .bento-tile {
            background: var(--glass);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 14px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            cursor: pointer;
            transition: transform 0.12s, border-color 0.15s;
        }
        .bento-tile:active {
            transform: scale(0.97);
            border-color: var(--accent);
        }

        .tile-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .tile-icon {
            width: 36px;
            height: 36px;
            border-radius: 11px;
            background: rgba(0, 240, 255, 0.10);
            border: 1px solid rgba(0, 240, 255, 0.22);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .tile-icon svg {
            width: 19px;
            height: 19px;
            stroke: var(--accent);
            stroke-width: 2.1;
            fill: none;
        }

        .tile-badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            color: var(--muted);
        }

        .tile-name {
            font-size: 14px;
            font-weight: 700;
            color: #FFFFFF;
            margin-top: 8px;
        }
        .tile-desc {
            font-size: 11px;
            color: var(--muted);
            margin-top: 2px;
        }

        /* DYNAMIC ACTION PILLS */
        .action-bar {
            display: flex;
            gap: 8px;
            justify-content: center;
            min-height: 32px;
        }

        .action-pill {
            background: var(--accent);
            color: #050811;
            border: none;
            border-radius: 999px;
            padding: 7px 16px;
            font-size: 12px;
            font-weight: 800;
            text-decoration: none;
            cursor: pointer;
            box-shadow: 0 4px 16px var(--glow);
        }

        /* BOTTOM COMMAND DOCK (VOICE + QUICK INPUT) */
        .command-dock {
            background: rgba(13, 20, 38, 0.94);
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 10px 12px;
            display: flex;
            flex-direction: column;
            gap: 9px;
        }

        .dock-row {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .mic-btn {
            width: 54px;
            height: 54px;
            border-radius: 50%;
            background: radial-gradient(circle, var(--glow) 0%, #0B1328 75%);
            border: 2px solid var(--accent);
            box-shadow: 0 0 20px var(--glow);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            flex-shrink: 0;
        }
        .mic-btn svg {
            width: 24px;
            height: 24px;
            stroke: #FFFFFF;
            stroke-width: 2.2;
            fill: none;
        }

        .dock-status {
            flex: 1;
            min-width: 0;
            cursor: pointer;
        }
        .dock-status-title {
            font-size: 13.5px;
            font-weight: 700;
            color: var(--accent);
        }
        .dock-status-sub {
            font-size: 11px;
            color: var(--muted);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .dock-tools {
            display: flex;
            gap: 6px;
        }

        .mini-icon-btn {
            width: 40px;
            height: 40px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--border);
            color: #FFFFFF;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
        }
        .mini-icon-btn svg {
            width: 18px;
            height: 18px;
            stroke: var(--accent);
            stroke-width: 2;
            fill: none;
        }

        .quick-input {
            display: flex;
            gap: 8px;
            background: rgba(5, 8, 17, 0.75);
            border: 1px solid var(--border);
            border-radius: 13px;
            padding: 4px 6px 4px 12px;
        }
        .quick-input input {
            flex: 1;
            background: transparent;
            border: none;
            color: #FFFFFF;
            font-size: 13.5px;
            outline: none;
        }
        .quick-input button {
            background: var(--accent);
            color: #050811;
            border: none;
            border-radius: 9px;
            padding: 7px 14px;
            font-size: 12px;
            font-weight: 800;
            cursor: pointer;
        }

        /* LISTS MODAL (ONLY VISIBLE WHEN OPEN) */
        .modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(5, 8, 17, 0.96);
            z-index: 50;
            display: none;
            flex-direction: column;
            padding: 18px 16px;
        }
        .modal-overlay.open {
            display: flex;
        }

        .modal-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }

        .modal-tabs {
            display: flex;
            gap: 8px;
            margin: 12px 0;
        }

        .m-tab {
            padding: 8px 14px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.07);
            color: var(--muted);
            font-size: 12.5px;
            font-weight: 700;
            cursor: pointer;
        }
        .m-tab.active {
            background: var(--accent);
            color: #050811;
        }

        .modal-list {
            flex: 1;
            overflow-y: auto;
        }

        .list-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--glass);
            border: 1px solid var(--border);
            padding: 12px;
            border-radius: 12px;
            margin-bottom: 8px;
            font-size: 13.5px;
        }
    </style>
</head>
<body>
    <div class="app-shell">
        <!-- TOP BAR -->
        <div class="top-bar">
            <button type="button" class="pill-btn" onclick="toggleWakeWord()">
                <span class="status-dot"></span>
                <span id="stateLabel">Voice Aktiv</span>
            </button>
            <div class="os-logo">NEO // OS</div>
            <button type="button" class="pill-btn" id="modeBtn" onclick="toggleMode()">Arbeit</button>
        </div>

        <!-- HERO PROFILE CARD -->
        <div class="hero-card">
            <div class="neo-avatar" onclick="toggleDirectRecord()">
                <div class="neo-avatar-img">
                    <img src="/avatar" alt="NEO" onerror="this.src='/icon.svg'">
                </div>
            </div>
            <div class="hero-info">
                <div class="hero-greeting">Hallo, Margil</div>
                <div class="hero-meta">
                    <span class="meta-tag" id="hudClock">12:00 Uhr</span>
                    <span class="meta-tag" id="weatherTag">Hamburg --°</span>
                    <span class="meta-tag" onclick="openDrawer()" style="cursor:pointer;">Notizen: <span id="hud-mem">0</span></span>
                </div>
            </div>
        </div>

        <!-- NEXT MISSION / CALENDAR BANNER -->
        <div class="mission-card" onclick="quickCmd('Erkläre mir ausführlich meine Termine im Kalender für heute und die nächsten Tage.')">
            <div style="min-width:0; flex:1;">
                <div class="mission-label">Nächster Termin • Live Kalender</div>
                <div class="mission-title" id="nextEvTitle">Termine werden geladen...</div>
                <div class="mission-sub" id="nextEvTime">Tippen für komplette Wochenübersicht</div>
            </div>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00F0FF" stroke-width="2.2"><polyline points="9 18 15 12 9 6"/></svg>
        </div>

        <!-- 2x2 BENTO MODULES -->
        <div class="bento-grid">
            <div class="bento-tile" onclick="quickCmd('Ich fahre los zum nächsten Termin im Kalender. Gib mir das Auto-Briefing mit Objekt-Codes und starte die Navigation.')">
                <div class="tile-top">
                    <div class="tile-icon">
                        <svg viewBox="0 0 24 24"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
                    </div>
                    <span class="tile-badge">GPS</span>
                </div>
                <div>
                    <div class="tile-name">Auto-Briefing</div>
                    <div class="tile-desc">Codes & Route starten</div>
                </div>
            </div>

            <div class="bento-tile" onclick="quickCmd('Kalkuliere ein Reinigungsangebot für 600 Quadratmeter Büro, zweimal pro Woche, und mach die WhatsApp-Nachricht fertig.')">
                <div class="tile-top">
                    <div class="tile-icon">
                        <svg viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="16" y2="10"/></svg>
                    </div>
                    <span class="tile-badge">m² / €</span>
                </div>
                <div>
                    <div class="tile-name">Angebot Rechner</div>
                    <div class="tile-desc">Kalkulation & WhatsApp</div>
                </div>
            </div>

            <div class="bento-tile" onclick="document.getElementById('camInput').click()">
                <div class="tile-top">
                    <div class="tile-icon">
                        <svg viewBox="0 0 24 24"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                    </div>
                    <span class="tile-badge">CAM</span>
                </div>
                <div>
                    <div class="tile-name">Mängel-Bericht</div>
                    <div class="tile-desc">Foto-Analyse für Kunden</div>
                </div>
            </div>

            <div class="bento-tile" onclick="testTelegramAlert()">
                <div class="tile-top">
                    <div class="tile-icon">
                        <svg viewBox="0 0 24 24"><path d="M22 2L11 13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                    </div>
                    <span class="tile-badge">BOT</span>
                </div>
                <div>
                    <div class="tile-name">Telegram Alert</div>
                    <div class="tile-desc">Autorisierung senden</div>
                </div>
            </div>
        </div>

        <!-- DYNAMIC ACTION BAR -->
        <div class="action-bar" id="actionBar"></div>

        <!-- BOTTOM COMMAND DOCK -->
        <div class="command-dock">
            <div class="dock-row">
                <button type="button" class="mic-btn" id="coreEye" onclick="toggleDirectRecord()">
                    <svg viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
                </button>
                <div class="dock-status" onclick="toggleDirectRecord()">
                    <div class="dock-status-title" id="reticleStatus">Tippen oder „Hey Neo“ sagen</div>
                    <div class="dock-status-sub">Dolmetscher DE/SQ • Kalender • Codes</div>
                </div>
                <div class="dock-tools">
                    <button type="button" class="mini-icon-btn" onclick="saveParking()" title="Parkplatz">
                        <svg viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                    </button>
                    <button type="button" class="mini-icon-btn" onclick="openDrawer()" title="Listen">
                        <svg viewBox="0 0 24 24"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                    </button>
                </div>
            </div>

            <div class="quick-input">
                <input type="text" id="msg" placeholder="Befehl, Übersetzung oder Code speichern..." onkeypress="if(event.key==='Enter')sendText()">
                <button type="button" onclick="sendText()">Senden</button>
            </div>
        </div>
    </div>

    <input type="file" id="camInput" accept="image/*" capture="environment" style="display:none" onchange="handleImage(event)">

    <!-- CLEAN LISTS MODAL -->
    <div class="modal-overlay" id="drawer">
        <div class="modal-head">
            <span style="font-size:16px; font-weight:800;">Speicher & Listen</span>
            <button type="button" class="pill-btn" onclick="closeDrawer()">✕ Schließen</button>
        </div>
        <div class="modal-tabs">
            <div class="m-tab active" id="tab-memory" onclick="switchTab('memory')">Notizen (<span id="c-mem">0</span>)</div>
            <div class="m-tab" id="tab-materials" onclick="switchTab('materials')">Material (<span id="c-mat">0</span>)</div>
            <div class="m-tab" id="tab-tasks" onclick="switchTab('tasks')">Tasks (<span id="c-task">0</span>)</div>
        </div>
        <div class="modal-list" id="drawerBody"></div>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        function updateHudClock() {
            const now = new Date();
            document.getElementById('hudClock').innerText = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) + " Uhr";
        }
        updateHudClock();
        setInterval(updateHudClock, 10000);

        async function loadDashboardWidgets() {
            try {
                const wRes = await fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true');
                const wData = await wRes.json();
                if (wData.current_weather) {
                    document.getElementById('weatherTag').innerText = "Hamburg " + Math.round(wData.current_weather.temperature) + "°C";
                }
            } catch (e) {}

            try {
                const cRes = await fetch('/calendar_preview');
                const cData = await cRes.json();
                if (cData.events && cData.events.length > 0) {
                    const first = cData.events[0];
                    document.getElementById('nextEvTitle').innerText = first.title;
                    document.getElementById('nextEvTime').innerText = first.time + (first.loc ? " • " + first.loc : "");
                } else {
                    document.getElementById('nextEvTitle').innerText = "Keine Termine eingetragen";
                }
            } catch (e) {}
        }
        loadDashboardWidgets();

        function playTone(freq1, freq2) {
            try {
                const ac = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ac.createOscillator();
                const gain = ac.createGain();
                osc.connect(gain);
                gain.connect(ac.destination);
                osc.type = 'sine';
                osc.frequency.setValueAtTime(freq1, ac.currentTime);
                osc.frequency.exponentialRampToValueAtTime(freq2, ac.currentTime + 0.10);
                gain.gain.setValueAtTime(0.10, ac.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.12);
                osc.start();
                osc.stop(ac.currentTime + 0.13);
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
            document.getElementById('modeBtn').innerText = (workMode === 'ARBEIT') ? 'Arbeit' : 'Privat';
        }
        updateBadges();

        function toggleMode() {
            workMode = (workMode === 'ARBEIT') ? 'PRIVAT' : 'ARBEIT';
            updateBadges();
        }

        function setState(state) {
            document.body.classList.remove('listening', 'thinking', 'speaking');
            if (state === 'listening') {
                document.body.classList.add('listening');
                stateLabel.innerText = "Hört zu...";
                reticleStatus.innerText = "Sprich jetzt, Margil...";
            } else if (state === 'thinking') {
                document.body.classList.add('thinking');
                stateLabel.innerText = "Analysiert...";
                reticleStatus.innerText = "NEO antwortet gleich...";
            } else if (state === 'speaking') {
                document.body.classList.add('speaking');
                stateLabel.innerText = "NEO spricht";
                reticleStatus.innerText = "Antwort läuft...";
            } else {
                stateLabel.innerText = wakeEnabled ? "Voice Aktiv" : "Stumm";
                reticleStatus.innerText = "Tippen oder „Hey Neo“ sagen";
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
            if (!wakeEnabled || isRecording || inConversation || isSpeaking) return;
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
                        setTimeout(() => startDirectAudio(), 110);
                        return;
                    }
                }
            };

            wakeRec.onend = () => {
                wakeRec = null;
                if (wakeEnabled && !isRecording && !inConversation && !isSpeaking) {
                    setTimeout(() => startWakeListener(), 350);
                }
            };

            try { wakeRec.start(); } catch(e) { wakeRec = null; }
        }

        function stopDirectAudio() {
            if (!isRecording) return;
            isRecording = false;
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
                let options = { audioBitsPerSecond: 12000 };
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

                    if (blob.size < 900 || voiceFramesCount < 6) {
                        inConversation = false;
                        setState(null);
                        if (wakeEnabled) setTimeout(() => startWakeListener(), 400);
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
                    coreEye.style.transform = `scale(${1 + Math.min(0.25, avg * 0.005)})`;

                    if (avg > 26) {
                        hasSpoken = true;
                        voiceFramesCount++;
                        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
                    } else if (hasSpoken && !silenceTimer) {
                        silenceTimer = setTimeout(() => stopDirectAudio(), 700);
                    } else if (!hasSpoken && (Date.now() - startTime > 5000)) {
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

        player.onplay = () => { isSpeaking = true; stopWakeListener(); setState('speaking'); };
        player.onended = () => {
            isSpeaking = false;
            setState(null);
            if (inConversation) setTimeout(() => startDirectAudio(), 450);
            else if (wakeEnabled) setTimeout(() => startWakeListener(), 650);
        };
        player.onerror = () => {
            isSpeaking = false;
            setState(null);
            if (wakeEnabled) setTimeout(() => startWakeListener(), 650);
        };

        async function testTelegramAlert() {
            reticleStatus.innerText = "Sende Telegram-Alert...";
            try {
                const res = await fetch('/telegram_notify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: "📞 NEO Autorisierung erforderlich:\n\nNächster Termin steht an. Soll ich das Auto-Briefing & die Navigation vorbereiten?"
                    })
                });
                const d = await res.json();
                reticleStatus.innerText = d.ok ? "Telegram gesendet!" : (d.error || "Erst /start im Bot senden");
            } catch (e) {
                reticleStatus.innerText = "Telegram Fehler";
            }
        }

        let activeTab = 'memory';
        function openDrawer() { document.getElementById('drawer').classList.add('open'); switchTab(activeTab); }
        function closeDrawer() { document.getElementById('drawer').classList.remove('open'); }
        function switchTab(tab) {
            activeTab = tab;
            document.querySelectorAll('.m-tab').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            const body = document.getElementById('drawerBody');
            let list = tab === 'materials' ? userMaterials : (tab === 'tasks' ? userTasks : userMemory);
            body.innerHTML = list.length === 0
                ? `<div style="color:#64748B; text-align:center; margin-top:40px; font-size:14px;">Keine Einträge vorhanden, Margil.</div>`
                : list.map((item, idx) => `<div class="list-row"><span>${idx + 1}. ${item}</span><button type="button" class="pill-btn" style="padding:4px 10px; color:#10B981;" onclick="deleteItem('${tab}', ${idx})">✓</button></div>`).join('');
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
                reticleStatus.innerText = "Parkplatz gespeichert (" + time + ")";
            });
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
                    const scale = Math.min(1, 720 / img.width);
                    canvas.width = img.width * scale;
                    canvas.height = img.height * scale;
                    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
                    sendToNeo({
                        image: canvas.toDataURL('image/jpeg', 0.65).split(',')[1],
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
            payload.history = chatHistory.slice(-4);
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
                    if (wakeEnabled) setTimeout(() => startWakeListener(), 800);
                    return;
                }

                if (data.ignore_background) {
                    setState(null);
                    if (inConversation) setTimeout(() => startDirectAudio(), 250);
                    else if (wakeEnabled) setTimeout(() => startWakeListener(), 400);
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
                localStorage.setItem('neo_history', JSON.stringify(chatHistory.slice(-6)));

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
                    if (!data.copy_text) setTimeout(() => { window.location.href = data.action_url; }, 500);
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
                            if (wakeEnabled) setTimeout(() => startWakeListener(), 650);
                        });
                    }
                } else {
                    setState(null);
                    if (inConversation) setTimeout(() => startDirectAudio(), 450);
                    else if (wakeEnabled) setTimeout(() => startWakeListener(), 650);
                }
            } catch (err) {
                inConversation = false;
                isSpeaking = false;
                setState(null);
                if (wakeEnabled) setTimeout(() => startWakeListener(), 800);
            }
        }

        window.addEventListener('load', () => {
            const params = new URLSearchParams(window.location.search);
            if (params.get('listen') === '1') {
                inConversation = true;
                sendToNeo({ message: "Begrüße Margil kurz beim Öffnen der App und frage, wie du helfen kannst." });
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
            return dt, dt.strftime("%d.%m. um %H:%M")
        else:
            dt = datetime.strptime(clean[:8], "%Y%m%d")
            return dt, dt.strftime("%d.%m. (Ganztägig)")
    except Exception:
        return None, raw_dt

def parse_upcoming_events():
    now_ts = time.time()
    if ICAL_CACHE["events"] and (now_ts - ICAL_CACHE["ts"] < 60):
        return ICAL_CACHE["events"]

    ical_url = os.environ.get("ICAL_URL", "").strip()
    if not ical_url:
        return []
    try:
        req = urllib.request.urlopen(ical_url, timeout=4)
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
                    title = title_m.group(1).strip().replace("\\,", ",").replace("\\n", " ")
                    loc = loc_m.group(1).strip().replace("\\,", ",").replace("\\n", " ") if loc_m else ""
                    desc = desc_m.group(1).strip().replace("\\n", " ")[:120] if desc_m else ""
                    upcoming.append((dt_obj, {
                        "dt_iso": dt_obj.isoformat(),
                        "time": dt_str,
                        "title": title,
                        "loc": loc,
                        "desc": desc
                    }))
        upcoming.sort(key=lambda x: x[0])
        res = [x[1] for x in upcoming[:15]]
        ICAL_CACHE["ts"] = now_ts
        ICAL_CACHE["events"] = res
        return res
    except Exception:
        return ICAL_CACHE["events"]

def get_ical_events():
    events = parse_upcoming_events()
    if not events:
        return "Keine anstehenden Termine gefunden."
    lines = []
    for ev in events:
        line = f"- {ev['time']}: {ev['title']}"
        if ev['loc']:
            line += f" (Ort: {ev['loc']})"
        if ev['desc']:
            line += f" [Info: {ev['desc']}]"
        lines.append(line)
    return "\n".join(lines)

SYSTEM_PROMPT = """Du bist NEO, der hochintelligente, ruhige KI-Assistent von Margil (Kundenbetreuer in einer Gebäudereinigung in Hamburg).
Aktueller Modus: {mode} | Aktuelle Zeit: {local_time}
Antworte höflich, präzise, ohne Sternchen/Markdown, und nenne den Nutzer 'Margil' oder 'Sir'. Standard-Sprache ist Deutsch (außer bei Übersetzungen ins Albanische).

WICHTIGE REGELN & 4 SPEZIAL-MODULE:
1. NUR DIREKTE STIMME BEACHTEN:
   - Konzentriere dich ausschließlich auf die lauteste, nahe Hauptstimme (Margil). Ignoriere Hintergrundstimmen im Raum, TV, Radio oder Telefon!
   - Wenn keine klare direkte Anfrage vorliegt, setze `"ignore_background": true` und `"reply": ""`.

2. MODUL A — AUTO-BRIEFING & NAVIGATION ("Ich fahre los", "Nächster Termin", "Losfahren"):
   - Lies den nächsten anstehenden Termin aus 'Kalender-Termine'.
   - Prüfe in 'Notizen' (memory), ob es Türcodes, Schlüssel-Infos oder Ansprechpartner zu diesem Objekt/Kunden gibt!
   - Fasse beides (Termin + Codes/Notizen) in 2-3 klaren Sätzen zusammen und setze `action_url` auf Google Maps Navigation: `"https://www.google.com/maps/dir/?api=1&destination=ADRESSE_URL_ENCODED&travelmode=driving"` mit `action_label`: `"Navigation starten"`.

3. MODUL B — ZWEISPRACHIGER DOLMETSCHER DEUTSCH <-> ALBANISCH ("Übersetze...", "Përktheje..."):
   - Wenn Margil sagt "Übersetze für das Team..." oder auf Deutsch spricht und Albanisch will: Übersetze den Satz in natürliches, freundliches Albanisch, setze `reply` auf die albanische Übersetzung, `voice_lang`: `"sq"` und schreibe die Übersetzung zusätzlich in `copy_text`.
   - Wenn Margil auf Albanisch spricht und die deutsche Übersetzung für einen Kunden braucht: Setze `reply` auf die höfliche deutsche Übersetzung, `voice_lang`: `"de"` und schreibe sie in `copy_text`.

4. MODUL C — ANGEBOTS- & STUNDEN-KALKULATOR ("Kalkuliere...", "Angebot berechnen..."):
   - Richtwerte: Büroreinigung ~220 m²/Std | Unterhaltsreinigung/Praxis ~160 m²/Std | Treppenhaus ~180 m²/Std | Glasreinigung ~45 m²/Std | Satz: 31,50 € netto/Std (4,33 Wochen/Monat).
   - Nenne in `reply` kurz Stunden pro Einsatz, Monatsstunden und Netto-Preis in 2 Sätzen.
   - Schreibe ein fertiges Angebots-Kurzschreiben in `copy_text` und bereite den WhatsApp-Business-Intent in `action_url` vor (`action_label`: `"Angebot per WhatsApp"`).

5. MODUL D — OBJEKT-MÄNGELBERICHT MIT KAMERA:
   - Bei einem Foto: Beschreibe den Zustand/Mangel sachlich in 2 Sätzen für Margil, schreibe einen formellen Mängelbericht (inkl. Datum & Uhrzeit `{local_time}`) in `copy_text` und setze `action_url` auf den WhatsApp-Intent (`action_label`: `"Bericht senden"`).

6. TELEGRAM BENACHRICHTIGUNG ("Schicke mir das auf Telegram", "Erinnere mich per Telegram"):
   - Wenn Margil ausdrücklich bittet, eine Info oder Autorisierung auf Telegram zu senden, fülle `telegram_alert` mit der kurzen Nachricht aus.

7. KALENDER & ALLGEMEINES:
   - Bei Kalenderfragen erkläre die Termine in 3-4 Sätzen mit Datum, Uhrzeit und Ort.
   - WHATSAPP (ANDROID NATIVE INTENT — NIEMALS web.whatsapp.com!):
     * Nummer bekannt: `"https://wa.me/49176...?text=URL_ENCODED"`
     * Nummer NICHT bekannt (ARBEIT): `"intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp.w4b;end"`
     * Nummer NICHT bekannt (PRIVAT): `"intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp;end"`
   - LISTEN: `new_memory`/`delete_memory` (Codes/Notizen), `new_material`/`delete_material` (Material), `new_task`/`delete_task` (Aufgaben).
   - GESPRÄCH ENDE: Bei "Danke", "Stopp", "Fertig", "Das war's": `"end_conversation": true`.

Antworte AUSSCHLIESSLICH als gültiges JSON-Objekt (ohne Markdown-Codeblöcke):
{{
  "reply": "Deine gesprochene Antwort",
  "voice_lang": "de",
  "ignore_background": false,
  "copy_text": "",
  "telegram_alert": "",
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
    communicate = edge_tts.Communicate(clean_text, voice_name, rate="+8%")
    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return base64.b64encode(audio_bytes).decode("utf-8")

def tg_api(method, payload=None):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        if payload:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

def send_telegram_auth(text, with_buttons=True):
    chat_id = TG_STATE.get("chat_id")
    if not chat_id:
        return False
    payload = {"chat_id": chat_id, "text": text}
    if with_buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "✅ Autorisieren", "callback_data": "approve_action"},
                {"text": "❌ Ablehnen", "callback_data": "reject_action"}
            ]]
        }
    res = tg_api("sendMessage", payload)
    return bool(res and res.get("ok"))

def process_telegram_message(chat_id, user_text):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return
    try:
        client = genai.Client(api_key=api_key)
        cal_info = get_ical_events()
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        prompt = f"Nachricht von Margil über Telegram: {user_text}\n\nAktuelle Kalender-Termine:\n{cal_info}"
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT.format(mode="ARBEIT", local_time=now_str),
                temperature=0.4
            )
        )
        res = extract_json(response.text)
        reply = res.get("reply", "Zu Befehl, Margil.")
        tg_api("sendMessage", {"chat_id": chat_id, "text": reply})
    except Exception as e:
        tg_api("sendMessage", {"chat_id": chat_id, "text": f"Fehler: {str(e)}"})

def telegram_background_worker():
    while True:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            time.sleep(10)
            continue

        updates = tg_api("getUpdates", {"offset": TG_STATE["last_update_id"] + 1, "timeout": 10})
        if updates and updates.get("ok"):
            for upd in updates.get("result", []):
                TG_STATE["last_update_id"] = upd["update_id"]
                if "message" in upd:
                    msg = upd["message"]
                    cid = str(msg["chat"]["id"])
                    TG_STATE["chat_id"] = cid
                    txt = msg.get("text", "")
                    if txt == "/start":
                        tg_api("sendMessage", {
                            "chat_id": cid,
                            "text": f"Hallo Margil! NEO ist verbunden.\nDeine Chat-ID: {cid}"
                        })
                    elif txt:
                        process_telegram_message(cid, txt)
                elif "callback_query" in upd:
                    cb = upd["callback_query"]
                    cid = str(cb["message"]["chat"]["id"])
                    TG_STATE["chat_id"] = cid
                    data_cb = cb.get("data", "")
                    tg_api("answerCallbackQuery", {"callback_query_id": cb["id"]})
                    if data_cb == "approve_action":
                        tg_api("sendMessage", {"chat_id": cid, "text": "✅ Autorisiert, Margil. Aktion wurde freigegeben!"})
                    elif data_cb == "reject_action":
                        tg_api("sendMessage", {"chat_id": cid, "text": "❌ Abgelehnt. Aktion wurde gestoppt."})

        if TG_STATE["chat_id"]:
            try:
                events = parse_upcoming_events()
                now_dt = datetime.now()
                for ev in events:
                    dt_iso = ev.get("dt_iso", "")
                    if not dt_iso or dt_iso in TG_STATE["notified_events"]:
                        continue
                    ev_dt = datetime.fromisoformat(dt_iso)
                    diff_min = (ev_dt - now_dt).total_seconds() / 60.0
                    if 0 < diff_min <= 35:
                        TG_STATE["notified_events"].add(dt_iso)
                        loc_txt = f"\nOrt: {ev['loc']}" if ev.get("loc") else ""
                        send_telegram_auth(
                            f"🔔 NEO Termin-Erinnerung ({ev['time']}):\n{ev['title']}{loc_txt}\n\nSoll ich die Navigation und das Briefing starten?",
                            with_buttons=True
                        )
            except Exception:
                pass
        time.sleep(2)

threading.Thread(target=telegram_background_worker, daemon=True).start()

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/telegram_notify", methods=["POST"])
def telegram_notify():
    data = request.json or {}
    text = data.get("text", "🔔 NEO Autorisierung angefordert.")
    if not TG_STATE.get("chat_id"):
        return jsonify({"ok": False, "error": "Bitte sende zuerst 'Hallo' an deinen Bot in Telegram!"})
    sent = send_telegram_auth(text, with_buttons=True)
    return jsonify({"ok": sent})

@app.route("/avatar")
def avatar():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for f in os.listdir(base_dir):
        if f.lower().startswith("neo_avatar") and f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return send_file(os.path.join(base_dir, f))
    for f in os.listdir(base_dir):
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and not f.lower().startswith("icon"):
            return send_file(os.path.join(base_dir, f))
    return Response(ICON_SVG, mimetype="image/svg+xml")

@app.route("/calendar_preview")
def calendar_preview():
    return jsonify({"events": parse_upcoming_events()[:4]})

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

        calendar_info = get_ical_events()
        client = genai.Client(api_key=api_key)
        contents = []

        lower_msg = msg.lower()
        needs_search = any(w in lower_msg for w in ["wetter", "temperatur", "regen", "stau", "verkehr", "nachrichten", "news", "suche", "google", "preis", "öffnungszeiten"])
        active_tools = [{"google_search": {}}] if needs_search else []

        if "image" in data:
            contents.append(types.Part.from_bytes(data=base64.b64decode(data["image"]), mime_type="image/jpeg"))
            contents.append(msg or "Erstelle anhand dieses Fotos einen professionellen Objekt-Mängelbericht.")
        elif "audio" in data:
            contents.append(types.Part.from_bytes(data=base64.b64decode(data["audio"]), mime_type=data.get("mime_type", "audio/webm")))
            contents.append("Fokussiere dich NUR auf die direkte Hauptstimme von Margil und ignoriere Hintergrundstimmen.")
        else:
            contents.append(msg)

        context_str = (
            f"Kalender:\n{calendar_info}\n"
            f"Notizen: {json.dumps(data.get('memory', []), ensure_ascii=False)} | "
            f"Material: {json.dumps(data.get('materials', []), ensure_ascii=False)} | "
            f"Tasks: {json.dumps(data.get('tasks', []), ensure_ascii=False)} | "
            f"Verlauf: {json.dumps(data.get('history', []), ensure_ascii=False)}"
        )
        contents.append(context_str)

        config_args = {
            "system_instruction": SYSTEM_PROMPT.format(mode=mode, local_time=local_time_str),
            "temperature": 0.4
        }
        if active_tools:
            config_args["tools"] = active_tools

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=contents,
            config=types.GenerateContentConfig(**config_args)
        )

        result = extract_json(response.text)
        if result.get("ignore_background"):
            return jsonify({"ignore_background": True})

        if result.get("telegram_alert"):
            send_telegram_auth(f"🔔 NEO Hinweis:\n{result['telegram_alert']}", with_buttons=True)

        reply = result.get("reply", "Zu Befehl, Margil.")
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
