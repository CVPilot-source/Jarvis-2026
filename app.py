import os
import re
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

MANIFEST_JSON = {
    "name": "NEO",
    "short_name": "NEO",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#060913",
    "theme_color": "#060913",
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
  <rect width="512" height="512" rx="120" fill="#060913"/>
  <circle cx="256" cy="256" r="160" fill="none" stroke="#38BDF8" stroke-width="8" stroke-dasharray="24 14"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#818CF8" stroke-width="4"/>
  <circle cx="256" cy="256" r="22" fill="#38BDF8"/>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#060913">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/svg+xml" href="/icon.svg">
    <title>NEO AI</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

        :root {
            --accent: #38BDF8;
            --accent-2: #818CF8;
            --accent-glow: rgba(56, 189, 248, 0.35);
            --bg-main: #060913;
            --card-bg: rgba(15, 23, 42, 0.68);
            --card-border: rgba(255, 255, 255, 0.09);
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
        }

        body.listening {
            --accent: #10B981;
            --accent-2: #34D399;
            --accent-glow: rgba(16, 185, 129, 0.45);
        }
        body.thinking {
            --accent: #F59E0B;
            --accent-2: #FB923C;
            --accent-glow: rgba(245, 158, 11, 0.45);
        }
        body.speaking {
            --accent: #38BDF8;
            --accent-2: #A855F7;
            --accent-glow: rgba(168, 85, 247, 0.45);
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        body {
            margin: 0;
            background: radial-gradient(circle at 50% 25%, #111D3B 0%, #060913 65%, #03050A 100%);
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            height: 100dvh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 12px 14px 14px;
            -webkit-font-smoothing: antialiased;
        }

        /* --- TOP STATUS STRIP --- */
        .top-strip {
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 5;
        }

        .status-chip {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 11.5px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 7px;
            cursor: pointer;
        }

        .led-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent);
            box-shadow: 0 0 10px var(--accent);
        }

        .brand-badge {
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 3.5px;
            padding-left: 3.5px;
            color: #CBD5E1;
            text-transform: uppercase;
        }

        /* --- DASHBOARD CONTAINER --- */
        .dashboard {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            width: 100%;
            max-width: 560px;
            margin: 8px auto 4px;
            gap: 10px;
            z-index: 4;
        }

        /* HERO ROW: GREETING + AVATAR + WEATHER */
        .hero-grid {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            align-items: center;
            gap: 10px;
        }

        .glass-box {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 18px;
            padding: 12px;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .hello-title {
            font-size: 17px;
            font-weight: 800;
            color: #FFFFFF;
            line-height: 1.2;
        }

        .hello-sub {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 4px;
            line-height: 1.35;
        }

        .mini-badge {
            display: inline-block;
            margin-top: 8px;
            font-size: 10px;
            font-weight: 700;
            color: var(--accent);
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.25);
            padding: 3px 8px;
            border-radius: 6px;
            width: fit-content;
        }

        /* AVATAR PORTRAIT CARD */
        .avatar-frame {
            position: relative;
            width: 126px;
            height: 148px;
            border-radius: 22px;
            padding: 3px;
            background: linear-gradient(145deg, var(--accent), var(--accent-2));
            box-shadow: 0 0 28px var(--accent-glow);
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.25s;
        }
        .avatar-frame:active { transform: scale(0.96); }

        .avatar-inner {
            width: 100%;
            height: 100%;
            border-radius: 19px;
            overflow: hidden;
            background: #0A1020;
            position: relative;
        }

        /* Croppt leicht den unteren Rand (Wasserzeichen) und zentriert das Gesicht perfekt */
        .avatar-inner img {
            width: 100%;
            height: 114%;
            object-fit: cover;
            object-position: center 12%;
            display: block;
            transition: transform 0.4s ease, filter 0.3s ease;
        }

        body.speaking .avatar-inner img {
            animation: avatarBreath 1.1s infinite alternate ease-in-out;
        }

        @keyframes avatarBreath {
            from { transform: scale(1.0); }
            to { transform: scale(1.045); }
        }

        .avatar-tag {
            position: absolute;
            bottom: 6px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(6, 9, 19, 0.82);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #FFFFFF;
            font-size: 9.5px;
            font-weight: 700;
            letter-spacing: 1.5px;
            padding: 2px 10px;
            border-radius: 999px;
        }

        .weather-temp {
            font-family: 'JetBrains Mono', monospace;
            font-size: 24px;
            font-weight: 700;
            color: #FFFFFF;
            line-height: 1.1;
        }
        .weather-loc {
            font-size: 11px;
            font-weight: 600;
            color: var(--accent);
            margin-top: 2px;
        }
        .weather-desc {
            font-size: 10.5px;
            color: var(--text-muted);
            margin-top: 4px;
        }

        /* MIDDLE ROW: SMART SHORTCUTS + TODAY'S SCHEDULE */
        .mid-grid {
            display: grid;
            grid-template-columns: 1fr 1.15fr;
            gap: 10px;
            flex: 1;
            min-height: 0;
        }

        .section-label {
            font-size: 10.5px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.9px;
            color: var(--text-muted);
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .shortcut-list {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .shortcut-btn {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 11px;
            padding: 8px 10px;
            color: #F8FAFC;
            font-size: 12px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            transition: background 0.15s;
        }
        .shortcut-btn:active { background: rgba(56, 189, 248, 0.16); }
        .shortcut-btn svg {
            width: 15px;
            height: 15px;
            stroke: var(--accent);
            stroke-width: 2;
            fill: none;
            flex-shrink: 0;
        }

        .schedule-list {
            display: flex;
            flex-direction: column;
            gap: 6px;
            overflow-y: auto;
        }

        .sched-item {
            background: rgba(255, 255, 255, 0.04);
            border-left: 2.5px solid var(--accent);
            border-radius: 8px;
            padding: 6px 9px;
            font-size: 11.5px;
        }
        .sched-time {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            color: var(--accent);
            font-weight: 700;
        }
        .sched-title {
            color: #F1F5F9;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* VOICE ORB CONTROLLER */
        .voice-hub {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 4px 0;
            cursor: pointer;
            user-select: none;
        }

        .orb-ring {
            width: 72px;
            height: 72px;
            border-radius: 50%;
            background: radial-gradient(circle, var(--accent-glow) 0%, rgba(15, 23, 42, 0.95) 72%);
            border: 2px solid var(--accent);
            box-shadow: 0 0 26px var(--accent-glow), inset 0 0 14px var(--accent-glow);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.12s ease;
        }

        .orb-ring svg {
            width: 28px;
            height: 28px;
            stroke: #FFFFFF;
            stroke-width: 2;
            fill: none;
        }

        body.speaking .orb-ring {
            animation: orbPulse 0.45s infinite alternate;
        }
        @keyframes orbPulse {
            from { transform: scale(0.95); }
            to { transform: scale(1.12); }
        }

        .voice-hint {
            margin-top: 6px;
            font-size: 11.5px;
            font-weight: 600;
            color: var(--accent);
            letter-spacing: 0.3px;
        }

        /* ACTION BAR */
        .action-bar {
            min-height: 34px;
            display: flex;
            gap: 8px;
            justify-content: center;
            align-items: center;
            z-index: 6;
        }

        .action-pill {
            padding: 7px 16px;
            border-radius: 999px;
            background: var(--accent);
            color: #060913;
            border: none;
            font-size: 12px;
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
            box-shadow: 0 4px 16px var(--accent-glow);
        }

        /* BOTTOM NAVIGATION BAR */
        .bottom-nav {
            width: 100%;
            max-width: 560px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 6px;
            background: rgba(10, 15, 29, 0.92);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            border-radius: 18px;
            padding: 6px;
            z-index: 5;
        }

        .nav-tab {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 12px;
            padding: 6px 2px;
            color: var(--text-muted);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 3px;
            cursor: pointer;
            font-size: 10.5px;
            font-weight: 600;
        }
        .nav-tab svg {
            width: 18px;
            height: 18px;
            stroke: currentColor;
            stroke-width: 2;
            fill: none;
        }
        .nav-tab.active {
            background: rgba(56, 189, 248, 0.14);
            border-color: rgba(56, 189, 248, 0.35);
            color: #FFFFFF;
        }
        .nav-tab.active svg { stroke: var(--accent); }

        /* COMMAND DRAWER */
        .drawer {
            position: fixed;
            inset: 0;
            background: rgba(6, 9, 19, 0.97);
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
            color: var(--text-muted);
            font-size: 12.5px;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
        }

        .tab-pill.active {
            background: var(--accent);
            border-color: var(--accent);
            color: #060913;
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
            color: #060913;
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
    <!-- TOP STRIP -->
    <div class="top-strip">
        <div class="status-chip" onclick="toggleWakeWord()">
            <div class="led-dot"></div>
            <span id="stateLabel">Voice Active</span>
        </div>

        <div class="brand-badge">NEO • AI</div>

        <div class="status-chip" id="modeBtn" onclick="toggleMode()">
            <span>Arbeit</span>
        </div>
    </div>

    <!-- MAIN DASHBOARD -->
    <div class="dashboard">
        <!-- HERO ROW: HELLO MARGIL + NEO AVATAR + WEATHER -->
        <div class="hero-grid">
            <div class="glass-box">
                <div>
                    <div class="hello-title">Hallo, Margil</div>
                    <div class="hello-sub">Bereit für deine Objekte & Termine.</div>
                </div>
                <div class="mini-badge" id="hudClock">00:00 Uhr</div>
            </div>

            <div class="avatar-frame" onclick="toggleDirectRecord()">
                <div class="avatar-inner">
                    <img src="/avatar" alt="NEO" onerror="this.src='/icon.svg'">
                    <div class="avatar-tag">NEO</div>
                </div>
            </div>

            <div class="glass-box" onclick="quickCmd('Wie wird das Wetter heute in Hamburg?')" style="cursor:pointer;">
                <div>
                    <div class="weather-temp" id="weatherTemp">--°</div>
                    <div class="weather-loc">Hamburg</div>
                    <div class="weather-desc" id="weatherDesc">Gebäudereinigung</div>
                </div>
                <div class="mini-badge">Notizen: <span id="hud-mem">0</span></div>
            </div>
        </div>

        <!-- MIDDLE ROW: SMART SHORTCUTS + LIVE SCHEDULE -->
        <div class="mid-grid">
            <div class="glass-box">
                <div class="section-label"><span>Smart Tools</span></div>
                <div class="shortcut-list">
                    <div class="shortcut-btn" onclick="quickCmd('Ich fahre los zum nächsten Termin im Kalender. Gib mir das Auto-Briefing mit Objekt-Codes und starte die Navigation.')">
                        <svg viewBox="0 0 24 24"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
                        <span>Auto-Briefing</span>
                    </div>
                    <div class="shortcut-btn" onclick="quickCmd('Kalkuliere ein Reinigungsangebot für 600 Quadratmeter Büro, zweimal pro Woche, und mach die WhatsApp-Nachricht fertig.')">
                        <svg viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="16" y2="10"/></svg>
                        <span>Angebot Rechner</span>
                    </div>
                    <div class="shortcut-btn" onclick="document.getElementById('camInput').click()">
                        <svg viewBox="0 0 24 24"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                        <span>Mängel-Foto</span>
                    </div>
                    <div class="shortcut-btn" onclick="openDrawer()">
                        <svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
                        <span>Listen (<span id="hud-task">0</span>)</span>
                    </div>
                </div>
            </div>

            <div class="glass-box" onclick="quickCmd('Erkläre mir ausführlich meine Termine im Kalender für heute und die nächsten Tage.')" style="cursor:pointer;">
                <div class="section-label">
                    <span>Kalender</span>
                    <span style="color:var(--accent); font-size:9.5px;">LIVE</span>
                </div>
                <div class="schedule-list" id="schedulePreview">
                    <div class="sched-item">
                        <div class="sched-time">SYNCHRONISIERT</div>
                        <div class="sched-title">Termine werden geladen...</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- CENTER VOICE ORB -->
        <div class="voice-hub" onclick="toggleDirectRecord()">
            <div class="orb-ring" id="coreEye">
                <svg viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
            </div>
            <div class="voice-hint" id="reticleStatus">Tippen oder „Hey Neo“ sagen</div>
        </div>
    </div>

    <!-- DYNAMIC ACTION BAR -->
    <div class="action-bar" id="actionBar"></div>

    <!-- BOTTOM NAVIGATION BAR -->
    <div class="bottom-nav">
        <div class="nav-tab" onclick="quickCmd('Ich fahre los zum nächsten Termin im Kalender. Gib mir das Briefing und starte die Navigation.')">
            <svg viewBox="0 0 24 24"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
            <span>Navi</span>
        </div>
        <div class="nav-tab" onclick="document.getElementById('camInput').click()">
            <svg viewBox="0 0 24 24"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
            <span>Kamera</span>
        </div>
        <div class="nav-tab active" id="wakeBtn" onclick="toggleWakeWord()">
            <svg viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg>
            <span>Voice</span>
        </div>
        <div class="nav-tab" onclick="quickCmd('Erkläre mir ausführlich meine Termine im Kalender für heute und die nächsten Tage.')">
            <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            <span>Kalender</span>
        </div>
        <div class="nav-tab" onclick="openDrawer()">
            <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
            <span>System</span>
        </div>
    </div>

    <input type="file" id="camInput" accept="image/*" capture="environment" style="display:none" onchange="handleImage(event)">

    <!-- COMMAND DRAWER -->
    <div class="drawer" id="drawer">
        <div>
            <div class="drawer-top">
                <span style="font-size:16px; font-weight:800; letter-spacing:0.5px;">NEO Command Center</span>
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
            document.getElementById('hudClock').innerText = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) + " Uhr";
        }
        updateHudClock();
        setInterval(updateHudClock, 10000);

        // Lade Live-Wetter Hamburg & Kalender-Vorschau beim Start
        async function loadDashboardWidgets() {
            try {
                const wRes = await fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true');
                const wData = await wRes.json();
                if (wData.current_weather) {
                    document.getElementById('weatherTemp').innerText = Math.round(wData.current_weather.temperature) + "°C";
                    document.getElementById('weatherDesc').innerText = "Wind " + Math.round(wData.current_weather.windspeed) + " km/h";
                }
            } catch (e) {}

            try {
                const cRes = await fetch('/calendar_preview');
                const cData = await cRes.json();
                const listEl = document.getElementById('schedulePreview');
                if (cData.events && cData.events.length > 0) {
                    listEl.innerHTML = cData.events.slice(0, 3).map(ev => `
                        <div class="sched-item">
                            <div class="sched-time">${ev.time}</div>
                            <div class="sched-title">${ev.title}</div>
                        </div>
                    `).join('');
                } else {
                    listEl.innerHTML = `<div class="sched-item"><div class="sched-time">HEUTE</div><div class="sched-title">Keine Termine eingetragen</div></div>`;
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
            document.getElementById('hud-task').innerText = userTasks.length;
            document.getElementById('modeBtn').innerHTML = `<span>${workMode === 'ARBEIT' ? 'Arbeit' : 'Privat'}</span>`;
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
                reticleStatus.innerText = "NEO denkt nach...";
            } else if (state === 'speaking') {
                document.body.classList.add('speaking');
                stateLabel.innerText = "NEO spricht";
                reticleStatus.innerText = "Antwort läuft...";
            } else {
                stateLabel.innerText = wakeEnabled ? "Voice Active" : "Stummgeschaltet";
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
                        setTimeout(() => startDirectAudio(), 180);
                        return;
                    }
                }
            };

            wakeRec.onend = () => {
                wakeRec = null;
                if (wakeEnabled && !isRecording && !inConversation && !isSpeaking) {
                    setTimeout(() => startWakeListener(), 400);
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
                    coreEye.style.transform = `scale(${1 + Math.min(0.25, avg * 0.005)})`;

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
                ? `<div style="color:#64748B; text-align:center; margin-top:40px; font-size:14px;">Keine Einträge vorhanden, Margil.</div>`
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
            return dt, dt.strftime("%d.%m. um %H:%M")
        else:
            dt = datetime.strptime(clean[:8], "%Y%m%d")
            return dt, dt.strftime("%d.%m. (Ganztägig)")
    except Exception:
        return None, raw_dt

def parse_upcoming_events():
    ical_url = os.environ.get("ICAL_URL", "").strip()
    if not ical_url:
        return []
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
                    upcoming.append((dt_obj, {
                        "time": dt_str,
                        "title": title,
                        "loc": loc,
                        "desc": desc
                    }))
        upcoming.sort(key=lambda x: x[0])
        return [x[1] for x in upcoming[:15]]
    except Exception:
        return []

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
Antworte höflich, ohne Sternchen/Markdown, und nenne den Nutzer 'Margil' oder 'Sir'. Standard-Sprache ist Deutsch (außer bei Übersetzungen ins Albanische).

WICHTIGE REGELN & 4 SPEZIAL-MODULE:
1. NUR DIREKTE STIMME BEACHTEN (SEHR WICHTIG):
   - Konzentriere dich ausschließlich auf die lauteste, nahe Hauptstimme (Margil). Ignoriere Hintergrundstimmen im Raum, TV, Radio oder Telefon!
   - Wenn keine klare direkte Anfrage vorliegt, setze `"ignore_background": true` und `"reply": ""`.

2. MODUL A — AUTO-BRIEFING & NAVIGATION ("Ich fahre los", "Nächster Termin", "Losfahren"):
   - Lies den nächsten anstehenden Termin aus 'Kalender-Termine'.
   - Prüfe in 'Notizen' (memory), ob es Türcodes, Schlüssel-Infos oder Ansprechpartner zu diesem Objekt/Kunden gibt!
   - Fasse beides (Termin + Codes/Notizen) in 2-3 klaren Sätzen zusammen und setze `action_url` auf Google Maps Navigation: `"https://www.google.com/maps/dir/?api=1&destination=ADRESSE_URL_ENCODED&travelmode=driving"` mit `action_label`: `"Navigation starten"`.

3. MODUL B — ZWEISPRACHIGER DOLMETSCHER DEUTSCH <-> ALBANISCH ("Übersetze...", "Përktheje..."):
   - Wenn Margil sagt "Übersetze für das Team..." oder auf Deutsch spricht und Albanisch will: Übersetze den Satz in natürliches, freundliches Albanisch, setze `reply` auf die albanische Übersetzung (damit NEO es laut vorliest!), `voice_lang`: `"sq"` und schreibe die Übersetzung zusätzlich in `copy_text`.
   - Wenn Margil auf Albanisch spricht und die deutsche Übersetzung für einen Kunden braucht: Setze `reply` auf die höfliche deutsche Übersetzung, `voice_lang`: `"de"` und schreibe sie in `copy_text`.

4. MODUL C — ANGEBOTS- & STUNDEN-KALKULATOR ("Kalkuliere...", "Angebot berechnen..."):
   - Nutze realistische Richtwerte der Gebäudereinigung in Deutschland:
     * Büroreinigung: ca. 220 m²/Stunde | Unterhaltsreinigung / Praxis: ca. 160 m²/Stunde | Treppenhaus: ca. 180 m²/Stunde | Glasreinigung: ca. 45 m²/Stunde.
     * Verrechnungssatz: ca. 31,50 € netto/Stunde (4,33 Wochen pro Monat).
   - Nenne in `reply` die geschätzten Stunden pro Einsatz, die monatlichen Stunden und den monatlichen Netto-Preis in 2-3 Sätzen.
   - Erstelle ein fertiges, professionelles Angebots-Kurzschreiben in `copy_text` und bereite den WhatsApp-Business-Intent in `action_url` vor (`action_label`: `"Angebot per WhatsApp"`).

5. MODUL D — OBJEKT-MÄNGELBERICHT MIT KAMERA:
   - Wenn ein Bild gesendet wird: Beschreibe den Zustand/Mangel sachlich und professionell in 2 Sätzen für Margil.
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
  "reply": "Deine gesprochene Antwort",
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

@app.route("/avatar")
def avatar():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 1. Kontrollo emrat standardë (pa dallim shkronjash të mëdha/të vogla)
    for f in os.listdir(base_dir):
        if f.lower().startswith("neo_avatar") and f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return send_file(os.path.join(base_dir, f))
    # 2. Nëse e ke ngarkuar me emrin origjinal nga telefoni, merr çdo .jpg/.png në dosje
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
            contents.append("Fokussiere dich NUR auf die direkte Hauptstimme von Margil und ignoriere leise Hintergrundstimmen im Raum oder vom Fernseher/Telefon.")
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
