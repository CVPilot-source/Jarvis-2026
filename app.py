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

MANIFEST_JSON = {
    "name": "NEO",
    "short_name": "NEO",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#0A0A0A",
    "theme_color": "#0A0A0A",
    "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]
}

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="120" fill="#0A0A0A"/>
  <circle cx="256" cy="256" r="150" fill="none" stroke="#F5F5F5" stroke-width="12"/>
  <circle cx="256" cy="256" r="28" fill="#F5F5F5"/>
</svg>"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#0A0A0A">
    <link rel="manifest" href="/manifest.json">
    <title>NEO</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0A0A0A;
            --card: #111111;
            --card-hi: #171717;
            --border: rgba(255,255,255,0.09);
            --border-hi: rgba(255,255,255,0.22);
            --text: #F5F5F5;
            --muted: #8A8A8A;
            --dim: #555555;
            --live: #22C55E;
            --warn: #F59E0B;
            --alert: #EF4444;
            --state: #F5F5F5;
        }
        body.listening { --state: #22C55E; }
        body.thinking  { --state: #F59E0B; }
        body.speaking  { --state: #60A5FA; }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; touch-action: manipulation; }
        button, input { font-family: inherit; }

        body {
            margin: 0 auto;
            background: var(--bg);
            color: var(--text);
            font-family: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            height: 100dvh;
            overflow-x: hidden;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            padding: 14px 16px;
            max-width: 520px;
            gap: 12px;
        }

        .eyebrow { font-size: 10px; letter-spacing: 3px; color: var(--muted); text-transform: uppercase; }

        /* Top bar */
        .top { display: flex; justify-content: space-between; align-items: center; }
        .brand { display: flex; align-items: center; gap: 10px; }
        .brand svg { width: 26px; height: 26px; flex-shrink: 0; }
        .brand-n { font-size: 14px; font-weight: 700; letter-spacing: 4px; line-height: 1; }
        .brand-s { font-size: 8.5px; letter-spacing: 2.5px; color: var(--muted); margin-top: 4px; }
        .top-r { display: flex; gap: 6px; }
        .chip {
            background: transparent; border: 1px solid var(--border); color: var(--text);
            padding: 7px 10px; border-radius: 10px; font-size: 10.5px; font-weight: 500;
            letter-spacing: 1px; text-transform: uppercase;
            display: inline-flex; align-items: center; gap: 7px; cursor: pointer; white-space: nowrap;
        }
        .chip:active { border-color: var(--border-hi); background: var(--card-hi); }
        .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--live); flex-shrink: 0; }
        .dot.off { background: var(--dim); }

        /* Greeting */
        .head { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; }
        .head h1 { margin: 6px 0 8px; font-size: 25px; font-weight: 700; letter-spacing: -0.5px; line-height: 1.1; }
        .meta { display: flex; flex-wrap: nowrap; white-space: nowrap; align-items: center; gap: 6px 8px; font-size: 11.5px; color: var(--muted); }
        .meta .sep { color: var(--dim); }
        .attn {
            display: none; align-items: center; gap: 6px; color: var(--alert);
            border: 1px solid rgba(239,68,68,0.45); border-radius: 999px; padding: 2px 9px; font-size: 11px;
        }
        .attn.on { display: inline-flex; }
        .attn::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--alert); }
        .avatar {
            width: 54px; height: 54px; border-radius: 14px; overflow: hidden; flex-shrink: 0; cursor: pointer;
            border: 1px solid var(--border-hi); background: var(--card);
            box-shadow: 0 0 0 3px var(--bg), 0 0 0 4px var(--state);
            transition: box-shadow .2s;
        }
        .avatar img { width: 100%; height: 100%; object-fit: cover; object-position: center 15%; display: block; filter: grayscale(1) contrast(1.05); }

        /* Stats */
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
        .stat {
            border: 1px solid var(--border); border-radius: 14px; padding: 10px 12px;
            background: linear-gradient(180deg, #141414, #0D0D0D); cursor: pointer;
        }
        .stat-l { font-size: 10px; color: var(--muted); display: flex; align-items: center; gap: 6px; white-space: nowrap; }
        .stat-l::before { content: ""; width: 2px; height: 10px; background: var(--text); border-radius: 1px; }
        .stat-v { font-size: 24px; font-weight: 600; margin-top: 4px; line-height: 1; }
        .stat-v small { font-size: 10px; color: var(--muted); font-weight: 400; margin-left: 3px; }

        /* Next appointment */
        .cal-box {
            border: 1px solid var(--border); border-radius: 14px; padding: 11px 12px; background: var(--card);
            display: flex; align-items: center; gap: 12px; cursor: pointer;
        }
        .cal-box:active, .tile:active, .stat:active { border-color: var(--border-hi); background: var(--card-hi); }
        .cal-main { flex: 1; min-width: 0; }
        .cal-val { font-size: 13.5px; font-weight: 500; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .cal-val.soon { color: var(--warn); }
        .arrow { color: var(--dim); font-size: 14px; }

        /* Actions */
        .grid { display: grid; grid-template-columns: 1fr 1fr; grid-auto-rows: 1fr; gap: 8px; flex: 1; min-height: 150px; }
        .tile {
            border: 1px solid var(--border); border-radius: 14px; padding: 12px; background: var(--card);
            display: flex; flex-direction: column; justify-content: space-between; cursor: pointer; min-height: 0;
        }
        .tile-top { display: flex; justify-content: space-between; font-size: 10px; color: var(--dim); letter-spacing: 1px; }
        .tile-t { font-size: 14px; font-weight: 600; }
        .tile-s { font-size: 10.5px; color: var(--muted); margin-top: 3px; }

        .action-bar { display: flex; gap: 8px; justify-content: center; min-height: 0; }
        .action-bar:empty { display: none; }
        .pill {
            background: var(--text); color: var(--bg); border: none; border-radius: 999px;
            padding: 7px 14px; font-size: 11px; font-weight: 600; letter-spacing: .5px;
            text-transform: uppercase; text-decoration: none; cursor: pointer;
        }

        /* Dock / command bar */
        .dock { border: 1px solid var(--border); border-radius: 16px; background: var(--card); padding: 10px; display: flex; flex-direction: column; gap: 10px; }
        .dock-top { display: flex; align-items: center; gap: 10px; }
        .mic {
            width: 42px; height: 42px; border-radius: 50%; background: var(--bg);
            border: 1px solid var(--state); color: var(--state); flex-shrink: 0; cursor: pointer;
            display: flex; align-items: center; justify-content: center; transition: border-color .2s, color .2s;
        }
        .mic svg { width: 18px; height: 18px; }
        body.listening .mic, body.speaking .mic { animation: pulse 1.2s ease-in-out infinite; }
        @keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 var(--state); } 50% { box-shadow: 0 0 0 5px transparent; } }
        .status-txt { flex: 1; min-width: 0; font-size: 11.5px; color: var(--state); cursor: pointer; line-height: 1.3; }
        .cmd { border: 1px solid var(--border); border-radius: 12px; background: var(--bg); padding: 8px 8px 7px 12px; }
        .cmd-row { display: flex; align-items: center; gap: 8px; }
        .cmd input { flex: 1; min-width: 0; background: transparent; border: none; outline: none; color: var(--text); font-size: 14px; padding: 4px 0; }
        .cmd input::placeholder { color: var(--muted); }
        .send {
            width: 32px; height: 32px; border-radius: 9px; border: 1px solid var(--border-hi);
            background: var(--card-hi); color: var(--text); cursor: pointer; font-size: 15px; flex-shrink: 0;
        }
        .hint { font-size: 9.5px; color: var(--dim); margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

        /* Panels */
        .modal { position: fixed; inset: 0; background: var(--bg); z-index: 40; display: none; flex-direction: column; padding: 16px; }
        .modal.open { display: flex; }
        .modal-wrap { width: 100%; max-width: 520px; margin: 0 auto; display: flex; flex-direction: column; flex: 1; min-height: 0; }
        .modal-h { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
        .modal-h h2 { margin: 6px 0 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }
        .modal-b { flex: 1; overflow-y: auto; }
        .kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 18px; }
        .kpi { border: 1px solid var(--border); border-radius: 14px; padding: 11px 12px; background: linear-gradient(180deg, #141414, #0D0D0D); }
        .kpi .stat-v { font-size: 28px; }
        .sec { margin: 4px 0 10px; display: flex; justify-content: space-between; align-items: center; }
        .sec button { background: none; border: none; color: var(--muted); font-size: 10px; letter-spacing: 2px; text-transform: uppercase; cursor: pointer; padding: 0; }
        .row {
            display: flex; justify-content: space-between; align-items: center; gap: 10px;
            border: 1px solid var(--border); background: var(--card); padding: 11px 12px; border-radius: 12px; margin-bottom: 8px; font-size: 12.5px;
        }
        .row-sub { color: var(--muted); font-size: 10.5px; margin-top: 3px; }
        .log { border: 1px solid var(--border); background: var(--card); padding: 11px 12px; border-radius: 12px; margin-bottom: 8px; font-size: 12.5px; line-height: 1.45; }
        .log-q { color: var(--muted); font-size: 10.5px; margin-bottom: 4px; }
        .empty { color: var(--muted); font-size: 12px; margin: 0 0 18px; }
        .ok-btn { background: transparent; border: 1px solid var(--border-hi); color: var(--text); border-radius: 8px; width: 30px; height: 30px; cursor: pointer; flex-shrink: 0; }


        /* Brain */
        .brain-legend { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
        .lg { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--border); border-radius: 999px; padding: 4px 9px; font-size: 10.5px; color: var(--muted); }
        .lg i { width: 7px; height: 7px; border-radius: 50%; display: block; }
        .lg b { color: var(--text); font-weight: 600; }
        .brain-wrap { position: relative; border: 1px solid var(--border); border-radius: 16px; background: radial-gradient(circle at 50% 50%, #151515 0%, #0A0A0A 70%); overflow: hidden; }
        .brain-wrap svg { display: block; width: 100%; height: auto; }
        .brain-wrap text { font-family: inherit; }
        .bn-leaf { cursor: pointer; }
        .bn-pulse { animation: bnp 3s ease-in-out infinite; transform-origin: 200px 200px; }
        @keyframes bnp { 0%,100% { opacity: .55; } 50% { opacity: 1; } }
        .brain-count { position: absolute; top: 10px; right: 12px; text-align: right; }
        .brain-count b { font-size: 22px; font-weight: 600; display: block; line-height: 1; }
        .brain-count span { font-size: 9.5px; color: var(--muted); letter-spacing: 1px; }
        .brain-detail { border: 1px solid var(--border); border-radius: 14px; background: var(--card); padding: 12px; margin-top: 10px; font-size: 12.5px; line-height: 1.45; }
        .brain-detail .gtag { display: flex; align-items: center; gap: 6px; font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
        .brain-detail .gtag i { width: 7px; height: 7px; border-radius: 50%; }
        .links { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
        .links button { background: transparent; border: 1px solid var(--border-hi); color: var(--text); border-radius: 999px; padding: 4px 10px; font-size: 11px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
        .links button i { width: 6px; height: 6px; border-radius: 50%; }
        .dump { display: flex; align-items: center; gap: 8px; border: 1px solid var(--border-hi); border-radius: 999px; padding: 6px 6px 6px 14px; margin-top: 10px; background: var(--card); }
        .dump input { flex: 1; min-width: 0; background: transparent; border: none; outline: none; color: var(--text); font-size: 13px; }
        .dump input::placeholder { color: var(--muted); }

        @media (max-height: 700px) {
            body { gap: 9px; padding: 10px 14px; }
            .head h1 { font-size: 21px; margin: 4px 0 6px; }
            .avatar { width: 46px; height: 46px; }
            .stat-v { font-size: 20px; }
            .hint { display: none; }
            .stat { padding: 8px 10px; }
            .cal-box { padding: 9px 12px; }
        }
        @media (max-height: 620px) {
            .tile { padding: 10px 12px; justify-content: center; }
            .tile-top, .tile-s { display: none; }
        }
        .top, .head, .stats, .cal-box, .action-bar, .dock { flex-shrink: 0; }
        @media (max-width: 370px) {
            .status-txt { display: none; }
            .dock-top { justify-content: space-between; }
            .head h1 { font-size: 20px; }
            .stat-v small, .wx { display: none; }
        }
    </style>
</head>
<body>
    <div class="top">
        <div class="brand">
            <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
                <circle cx="16" cy="16" r="13" stroke="#F5F5F5" stroke-width="2"/>
                <circle cx="16" cy="16" r="4" fill="#F5F5F5"/>
                <path d="M16 3v5M16 24v5M3 16h5M24 16h5" stroke="#F5F5F5" stroke-width="2"/>
            </svg>
            <div>
                <div class="brand-n">NEO</div>
                <div class="brand-s">OPERATOR MODE</div>
            </div>
        </div>
        <div class="top-r">
            <button type="button" class="chip" onclick="toggleWake()"><span class="dot" id="wDot"></span><span id="wLabel">Voice</span></button>
            <button type="button" class="chip" id="mBtn" onclick="toggleMode()">Arbeit</button>
        </div>
    </div>

    <div class="head">
        <div style="min-width:0;">
            <div class="eyebrow">// Home · Hamburg</div>
            <h1 id="greet">Guten Tag, Margil</h1>
            <div class="meta">
                <span class="attn" id="attn"></span>
                <span id="clock">--:--</span><span class="sep wx">·</span><span id="weather" class="wx">–°C</span>
            </div>
        </div>
        <div class="avatar" onclick="toggleRec()"><img src="/avatar" alt="NEO" onerror="this.src='/icon.svg'"></div>
    </div>

    <div class="stats">
        <div class="stat" onclick="openDash()"><div class="stat-l">Termine</div><div class="stat-v" id="sToday">–<small>heute</small></div></div>
        <div class="stat" onclick="openList()"><div class="stat-l">Notizen</div><div class="stat-v"><span id="nCount">0</span><small>offen</small></div></div>
        <div class="stat" onclick="openDash()"><div class="stat-l">Anfragen</div><div class="stat-v"><span id="sAsk">0</span><small>heute</small></div></div>
    </div>

    <div class="cal-box" onclick="quickCmd('Erkläre mir kurz meine nächsten Termine im Kalender.')">
        <div class="cal-main">
            <div class="eyebrow">Nächster Termin</div>
            <div class="cal-val" id="nextEv">Wird geladen...</div>
        </div>
        <span class="arrow">→</span>
    </div>

    <div class="grid">
        <div class="tile" onclick="quickCmd('Ich fahre los zum nächsten Termin. Gib mir das Briefing mit Codes und starte Navigation.')">
            <div class="tile-top"><span>01</span><span>↗</span></div>
            <div><div class="tile-t">Auto-Briefing</div><div class="tile-s">Codes & Route</div></div>
        </div>
        <div class="tile" onclick="quickCmd('Kalkuliere 600 qm Büro, 2x pro Woche, mit WhatsApp-Angebot.')">
            <div class="tile-top"><span>02</span><span>↗</span></div>
            <div><div class="tile-t">Angebot</div><div class="tile-s">m² & Preis</div></div>
        </div>
        <div class="tile" onclick="document.getElementById('cam').click()">
            <div class="tile-top"><span>03</span><span>↗</span></div>
            <div><div class="tile-t">Mängel-Foto</div><div class="tile-s">Kamera-Bericht</div></div>
        </div>
        <div class="tile" onclick="sendTg()">
            <div class="tile-top"><span>04</span><span>↗</span></div>
            <div><div class="tile-t">Telegram</div><div class="tile-s">Autorisierung</div></div>
        </div>
    </div>

    <div class="action-bar" id="actBar"></div>

    <div class="dock">
        <div class="dock-top">
            <button type="button" class="mic" onclick="toggleRec()" aria-label="Mikrofon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5"/></svg>
            </button>
            <div class="status-txt" id="stTxt" onclick="toggleRec()">Tippen oder „Hey Neo“</div>
            <button type="button" class="chip" onclick="openDash()">Übersicht</button>
            <button type="button" class="chip" onclick="openBrain()">Gehirn</button>
        </div>
        <div class="cmd">
            <div class="cmd-row">
                <input type="text" id="msg" placeholder="Sag NEO, was zu tun ist…" onkeypress="if(event.key==='Enter')sendTxt()">
                <button type="button" class="send" onclick="sendTxt()" aria-label="Senden">↑</button>
            </div>
            <div class="hint">Freitext fragt NEO · „Notiz …“ speichert direkt</div>
        </div>
    </div>

    <input type="file" id="cam" accept="image/*" capture="environment" style="display:none" onchange="handleImg(event)">

    <div class="modal" id="modal">
        <div class="modal-wrap">
            <div class="modal-h">
                <div><div class="eyebrow">// Speicher</div><h2>Notizen & Codes</h2></div>
                <button type="button" class="chip" onclick="closeList()">✕ Schließen</button>
            </div>
            <div class="modal-b" id="listBody"></div>
        </div>
    </div>

    <div class="modal" id="dash">
        <div class="modal-wrap">
            <div class="modal-h">
                <div><div class="eyebrow">// Übersicht · Heute</div><h2>Lagebild</h2></div>
                <button type="button" class="chip" onclick="closeDash()">✕ Schließen</button>
            </div>
            <div class="modal-b">
                <div class="kpis">
                    <div class="kpi"><div class="stat-l">Termine heute</div><div class="stat-v" id="kToday">–</div></div>
                    <div class="kpi"><div class="stat-l">Offene Notizen</div><div class="stat-v" id="kNotes">0</div></div>
                    <div class="kpi"><div class="stat-l">Anfragen heute</div><div class="stat-v" id="kAsk">0</div></div>
                    <div class="kpi"><div class="stat-l">Angebote & Berichte</div><div class="stat-v" id="kOffer">0</div></div>
                </div>
                <div class="sec"><span class="eyebrow">// Kommende Termine</span></div>
                <div id="dCal"></div>
                <div class="sec" style="margin-top:14px;"><span class="eyebrow">// Verlauf</span><button type="button" onclick="clearLog()">Löschen</button></div>
                <div id="dLog"></div>
            </div>
        </div>
    </div>

    <div class="modal" id="brain">
        <div class="modal-wrap">
            <div class="modal-h">
                <div><div class="eyebrow">// Wissen · Radial</div><h2>Gehirn</h2></div>
                <button type="button" class="chip" onclick="closeBrain()">✕ Schließen</button>
            </div>
            <div class="modal-b">
                <div class="brain-legend" id="bLegend"></div>
                <div class="brain-wrap">
                    <div class="brain-count"><b id="bCount">0</b><span>EINTRÄGE</span></div>
                    <svg id="bSvg" viewBox="0 0 400 400" role="img" aria-label="Wissens-Graph"></svg>
                </div>
                <div class="brain-detail" id="bDetail"></div>
                <div class="dump">
                    <input type="text" id="bInput" placeholder="Ins Gehirn werfen… z. B. Code Müller 4711" onkeypress="if(event.key==='Enter')brainDump()">
                    <button type="button" class="send" onclick="brainDump()" aria-label="Speichern">↑</button>
                </div>
            </div>
        </div>
    </div>

    <audio id="player" playsinline></audio>

    <script>
        function updClock() {
            document.getElementById('clock').innerText = new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'}) + " Uhr";
        }
        updClock(); setInterval(updClock, 15000);
        (function () {
            const h = new Date().getHours();
            document.getElementById('greet').innerText = (h < 11 ? 'Guten Morgen' : (h < 18 ? 'Guten Tag' : 'Guten Abend')) + ', Margil';
        })();

        fetch('https://api.open-meteo.com/v1/forecast?latitude=53.5511&longitude=9.9937&current_weather=true')
            .then(r => r.json()).then(d => {
                if (d.current_weather) document.getElementById('weather').innerText = Math.round(d.current_weather.temperature) + "°C";
            }).catch(()=>{});

        function esc(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
        function minsUntil(ev) { return ev.iso ? Math.round((new Date(ev.iso) - new Date()) / 60000) : null; }
        let calEvents = [];
        function renderNext() {
            const el = document.getElementById('nextEv');
            const next = calEvents.find(e => { const m = minsUntil(e); return m === null || m >= -30; });
            updStats();
            if (!next) { el.innerText = "Keine Termine"; el.classList.remove('soon'); document.getElementById('attn').classList.remove('on'); return; }
            const m = minsUntil(next);
            const soon = m !== null && m >= 0 && m <= 90;
            el.innerText = (soon ? "In " + m + " Min – " : next.time + " – ") + next.title;
            el.classList.toggle('soon', soon);
            const attn = document.getElementById('attn');
            attn.classList.toggle('on', soon);
            attn.innerText = soon ? 'Termin in ' + m + ' Min' : '';
        }
        function loadCal() {
            fetch('/calendar_preview?n=10').then(r => r.json()).then(d => { calEvents = d.events || []; renderNext(); })
                .catch(() => { document.getElementById('nextEv').innerText = "Kalender nicht erreichbar"; });
        }
        loadCal(); setInterval(renderNext, 60000); setInterval(loadCal, 300000);

        let mem = JSON.parse(localStorage.getItem('neo_memory') || '[]');
        let mode = localStorage.getItem('neo_mode') || 'ARBEIT';
        let neoLog = JSON.parse(localStorage.getItem('neo_log') || '[]');
        function addLog(q, a, kind) {
            neoLog.unshift({ t: new Date().toISOString(), q: q, a: a, kind: kind });
            neoLog = neoLog.slice(0, 50);
            localStorage.setItem('neo_log', JSON.stringify(neoLog));
            updStats();
        }
        function updStats() {
            const todayEv = calEvents.filter(e => e.iso && new Date(e.iso).toDateString() === new Date().toDateString());
            document.getElementById('sToday').innerHTML = (calEvents.length ? todayEv.length : '–') + '<small>heute</small>';
            document.getElementById('sAsk').innerText = neoLog.filter(x => x.kind !== 'note' && new Date(x.t).toDateString() === new Date().toDateString()).length;
        }
        function clearLog() { neoLog = []; localStorage.setItem('neo_log', '[]'); updStats(); renderDash(); }
        function isToday(d) { return d.toDateString() === new Date().toDateString(); }
        function renderDash() {
            const todayEv = calEvents.filter(e => e.iso && isToday(new Date(e.iso)));
            document.getElementById('kToday').innerText = calEvents.length ? todayEv.length : '–';
            document.getElementById('kNotes').innerText = mem.length;
            document.getElementById('kAsk').innerText = neoLog.filter(x => x.kind !== 'note' && isToday(new Date(x.t))).length;
            document.getElementById('kOffer').innerText = neoLog.filter(x => x.kind === 'offer' || x.kind === 'photo').length;
            document.getElementById('dCal').innerHTML = calEvents.length
                ? calEvents.map(e => `<div class="row"><div><div>${esc(e.title)}</div><div class="row-sub">${esc(e.time)}${e.loc ? ' · ' + esc(e.loc) : ''}</div></div><span class="arrow">→</span></div>`).join('')
                : '<p class="empty">Keine Termine (ICAL_URL gesetzt?).</p>';
            document.getElementById('dLog').innerHTML = neoLog.length
                ? neoLog.slice(0, 20).map(x => `<div class="log"><div class="log-q">${new Date(x.t).toLocaleString('de-DE', {day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'})} · ${esc(x.q)}</div>${esc(x.a)}</div>`).join('')
                : '<p class="empty">Noch keine Gespräche.</p>';
        }
        // ---------- Gehirn (Wissens-Graph) ----------
        const BG = {
            client: { n: 'Kunden',    c: '#F472B6' },
            event:  { n: 'Termine',   c: '#60A5FA' },
            code:   { n: 'Codes',     c: '#F59E0B' },
            offer:  { n: 'Angebote',  c: '#34D399' },
            report: { n: 'Berichte',  c: '#A78BFA' },
            note:   { n: 'Notizen',   c: '#D4D4D4' }
        };
        const BG_ORDER = ['client', 'event', 'code', 'offer', 'report', 'note'];
        const STOP = new Set(('termin termine angebot angebote notiz notizen büro buero hamburg objektbegehung praxis schule ' +
            'qualitätskontrolle schlüsselcode schlüssel code codes kunde kunden woche monat netto brutto uhr heute morgen ' +
            'bericht mängelbericht mängel reinigung gebäudereinigung objekt straße strasse gibt bitte danke kalkuliere erstelle ' +
            'erkläre briefing navigation fahre nächsten nächster auto whatsapp text kurz meine mein eine einen dein deine ' +
            'sprachbefehl foto mängel-foto alarm alarmcode türcode pin tür eingang hintereingang keller büros stunde stunden ' +
            'preis gesamt bitte sofort neuer neue neues kontrolle angebotspreis ' +
            'altona wandsbek barmbek eppendorf eimsbüttel harburg bergedorf ottensen winterhude hammerbrook ' +
            'billstedt rahlstedt bahrenfeld uhlenhorst hafencity steindamm montag dienstag mittwoch donnerstag freitag samstag sonntag').split(' '));
        const CODE_RE = /(code|schlüssel|schluessel|pin|tür|tuer|alarm|tresor|passwort)/i;
        let brainSel = null, brainItems = [];

        function brainKeywords(t) {
            const out = new Set();
            (String(t).match(/[A-ZÄÖÜ][a-zäöüß]{3,}/g) || []).forEach(w => { if (!STOP.has(w.toLowerCase())) out.add(w); });
            return out;
        }
        function short(t, n) { t = String(t || '').replace(/\\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n - 1) + '…' : t; }

        function buildBrain() {
            const items = [];
            mem.forEach((x, i) => items.push({ id: 'n' + i, g: CODE_RE.test(x) ? 'code' : 'note', label: x, text: x, sub: 'Notiz' }));
            calEvents.forEach((e, i) => items.push({ id: 'e' + i, g: 'event', label: e.title, text: e.title + ' ' + (e.loc || ''), sub: e.time + (e.loc ? ' · ' + e.loc : '') }));
            neoLog.filter(x => x.kind === 'offer').slice(0, 10).forEach((x, i) => items.push({ id: 'o' + i, g: 'offer', label: x.q, text: x.q + ' ' + x.a, sub: new Date(x.t).toLocaleDateString('de-DE') + ' · ' + x.a }));
            neoLog.filter(x => x.kind === 'photo').slice(0, 10).forEach((x, i) => items.push({ id: 'r' + i, g: 'report', label: x.a, text: x.a, sub: new Date(x.t).toLocaleDateString('de-DE') + ' · Mängelbericht' }));
            // Kunden = Namen, die in mindestens zwei Einträgen vorkommen
            const kwMap = {};
            items.forEach(it => { it.kw = brainKeywords(it.text); it.kw.forEach(k => (kwMap[k] = kwMap[k] || []).push(it.id)); });
            Object.keys(kwMap).filter(k => kwMap[k].length >= 2)
                .sort((a, b) => kwMap[b].length - kwMap[a].length).slice(0, 10)
                .forEach(k => items.push({ id: 'c_' + k, g: 'client', label: k, text: k, sub: kwMap[k].length + ' Verknüpfungen', links: kwMap[k] }));
            items.forEach(it => { if (!it.links) it.links = []; });
            items.filter(it => it.g === 'client').forEach(c => c.links.forEach(id => { const o = items.find(x => x.id === id); if (o) o.links.push(c.id); }));
            return items.slice(0, 60);
        }

        function svgEl(tag, attrs, text) {
            const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
            for (const k in attrs) el.setAttribute(k, attrs[k]);
            if (text != null) el.textContent = text;
            return el;
        }

        function renderBrain() {
            brainItems = buildBrain();
            const svg = document.getElementById('bSvg');
            svg.innerHTML = '';
            const C = 200, RH = 60, RL = 124;
            const groups = BG_ORDER.map(g => ({ g, items: brainItems.filter(i => i.g === g) })).filter(x => x.items.length);
            document.getElementById('bCount').innerText = brainItems.length;
            document.getElementById('bLegend').innerHTML = BG_ORDER.map(g =>
                `<span class="lg"><i style="background:${BG[g].c}"></i><b>${brainItems.filter(i => i.g === g).length}</b>${BG[g].n}</span>`).join('');

            // Ringe
            svg.appendChild(svgEl('circle', { cx: C, cy: C, r: RL, fill: 'none', stroke: 'rgba(255,255,255,0.06)' }));
            svg.appendChild(svgEl('circle', { cx: C, cy: C, r: RH, fill: 'none', stroke: 'rgba(255,255,255,0.08)', 'stroke-dasharray': '2 4' }));
            svg.appendChild(svgEl('circle', { cx: C, cy: C, r: 40, fill: 'none', stroke: 'rgba(255,255,255,0.05)' }));
            for (let a = 0; a < 120; a++) {
                const t = a / 120 * Math.PI * 2;
                svg.appendChild(svgEl('circle', { cx: C + Math.cos(t) * (RH + 18), cy: C + Math.sin(t) * (RH + 18), r: 0.6, fill: 'rgba(255,255,255,0.18)' }));
            }

            if (!groups.length) {
                svg.appendChild(svgEl('text', { x: C, y: C + 44, 'text-anchor': 'middle', fill: '#8A8A8A', 'font-size': 9 }, 'Noch leer – wirf etwas ins Gehirn'));
            }

            // Winkel verteilen
            const total = brainItems.length, gap = groups.length > 1 ? 0.22 : 0;
            const span = Math.PI * 2 - gap * groups.length;
            let ang = -Math.PI / 2 + gap / 2;
            const pos = {}, hubs = {};
            groups.forEach(gr => {
                const w = span * gr.items.length / total;
                hubs[gr.g] = { a: ang + w / 2, x: C + Math.cos(ang + w / 2) * RH, y: C + Math.sin(ang + w / 2) * RH, n: gr.items.length };
                gr.items.forEach((it, k) => {
                    const a = ang + w * (k + 0.5) / gr.items.length;
                    pos[it.id] = { a, x: C + Math.cos(a) * RL, y: C + Math.sin(a) * RL };
                });
                ang += w + gap;
            });

            const sel = brainSel && brainItems.find(i => i.id === brainSel) ? brainSel : null;
            const selItem = sel ? brainItems.find(i => i.id === sel) : null;
            const lit = new Set(sel ? [sel, ...selItem.links] : []);
            const dimOf = id => (sel && !lit.has(id)) ? 0.15 : 1;

            // Querverbindungen Kunde <-> Eintrag
            brainItems.filter(i => i.g === 'client').forEach(c => c.links.forEach(id => {
                if (!pos[id] || !pos[c.id]) return;
                const p1 = pos[c.id], p2 = pos[id];
                const on = sel && (sel === c.id || sel === id);
                svg.appendChild(svgEl('path', {
                    d: `M${p1.x},${p1.y} Q${C + (p1.x + p2.x - 2 * C) * 0.15},${C + (p1.y + p2.y - 2 * C) * 0.15} ${p2.x},${p2.y}`,
                    fill: 'none', stroke: BG.client.c, 'stroke-width': on ? 1.2 : 0.6, opacity: sel ? (on ? 0.9 : 0.06) : 0.35
                }));
            }));

            // Zentrum -> Gruppen -> Einträge
            groups.forEach(gr => {
                const h = hubs[gr.g];
                svg.appendChild(svgEl('line', { x1: C, y1: C, x2: h.x, y2: h.y, stroke: 'rgba(255,255,255,0.12)', 'stroke-dasharray': '1 3' }));
                gr.items.forEach(it => {
                    const p = pos[it.id], mr = (RH + RL) / 2;
                    svg.appendChild(svgEl('path', {
                        d: `M${h.x},${h.y} Q${C + Math.cos(p.a) * mr},${C + Math.sin(p.a) * mr} ${p.x},${p.y}`,
                        fill: 'none', stroke: BG[gr.g].c, 'stroke-width': 0.7, opacity: 0.3 * dimOf(it.id)
                    }));
                });
            });

            // Blätter + Beschriftung
            brainItems.forEach(it => {
                const p = pos[it.id]; if (!p) return;
                const g = svgEl('g', { class: 'bn-leaf', opacity: dimOf(it.id) });
                g.addEventListener('click', () => { brainSel = (brainSel === it.id ? null : it.id); renderBrain(); });
                g.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: 11, fill: 'transparent' }));
                if (it.id === sel) g.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: 7, fill: 'none', stroke: BG[it.g].c, 'stroke-width': 1 }));
                g.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: it.g === 'client' ? 4.2 : 3.4, fill: BG[it.g].c }));
                let deg = p.a * 180 / Math.PI, left = deg > 90 && deg < 270 || deg < -90;
                const lx = C + Math.cos(p.a) * (RL + 9), ly = C + Math.sin(p.a) * (RL + 9);
                g.appendChild(svgEl('text', {
                    x: lx, y: ly, 'font-size': 7, fill: it.id === sel ? '#F5F5F5' : '#A3A3A3', 'dominant-baseline': 'middle',
                    'text-anchor': left ? 'end' : 'start', transform: `rotate(${left ? deg + 180 : deg} ${lx} ${ly})`
                }, short(it.label, 14)));
                svg.appendChild(g);
            });

            // Gruppen-Knoten
            groups.forEach(gr => {
                const h = hubs[gr.g];
                svg.appendChild(svgEl('circle', { cx: h.x, cy: h.y, r: 9, fill: BG[gr.g].c, opacity: 0.18 }));
                svg.appendChild(svgEl('circle', { cx: h.x, cy: h.y, r: 5.5, fill: BG[gr.g].c }));
                const right = Math.cos(h.a) >= 0;
                svg.appendChild(svgEl('text', { x: h.x + (right ? 10 : -10), y: h.y + 0.5, 'font-size': 7.5, fill: '#E5E5E5', 'dominant-baseline': 'middle', 'text-anchor': right ? 'start' : 'end' }, BG[gr.g].n.toLowerCase() + ' ' + h.n));
            });

            // Zentrum
            const defs = svgEl('defs', {});
            const rg = svgEl('radialGradient', { id: 'bnCore' });
            rg.appendChild(svgEl('stop', { offset: '0%', 'stop-color': '#FFFFFF' }));
            rg.appendChild(svgEl('stop', { offset: '70%', 'stop-color': '#D4D4D4' }));
            rg.appendChild(svgEl('stop', { offset: '100%', 'stop-color': '#737373' }));
            defs.appendChild(rg); svg.appendChild(defs);
            svg.appendChild(svgEl('circle', { cx: C, cy: C, r: 22, fill: 'none', stroke: 'rgba(255,255,255,0.25)', class: 'bn-pulse' }));
            svg.appendChild(svgEl('circle', { cx: C, cy: C, r: 13, fill: 'url(#bnCore)' }));
            svg.appendChild(svgEl('text', { x: C, y: C + 34, 'text-anchor': 'middle', 'font-size': 8.5, fill: '#F5F5F5', 'font-weight': 600 }, 'NEO'));

            // Detail
            const d = document.getElementById('bDetail');
            if (!selItem) {
                d.innerHTML = '<div class="gtag">// Tipp</div>Tippe auf einen Punkt, um die Notiz und ihre Verbindungen zu sehen. Namen, die mehrfach vorkommen (z. B. „Müller“), werden automatisch als Kunde verknüpft.';
            } else {
                const links = selItem.links.map(id => brainItems.find(x => x.id === id)).filter(Boolean);
                d.innerHTML = `<div class="gtag"><i style="background:${BG[selItem.g].c}"></i>${BG[selItem.g].n}</div>` +
                    `<div>${esc(selItem.label)}</div><div class="row-sub">${esc(short(selItem.sub, 160))}</div>` +
                    (links.length ? `<div class="links">${links.map(l => `<button type="button" data-id="${esc(l.id)}"><i style="background:${BG[l.g].c}"></i>${esc(short(l.label, 28))}</button>`).join('')}</div>` : '');
                d.querySelectorAll('.links button').forEach(b => b.addEventListener('click', () => { brainSel = b.getAttribute('data-id'); renderBrain(); }));
            }
        }
        function brainDump() {
            const inp = document.getElementById('bInput');
            const v = inp.value.trim(); if (!v) return;
            mem.push(v); saveState(); addLog('Notiz: ' + v, 'Notiz gespeichert.', 'note');
            inp.value = ''; brainSel = 'n' + (mem.length - 1); renderBrain();
        }
        function openBrain() { brainSel = null; renderBrain(); document.getElementById('brain').classList.add('open'); }
        function closeBrain() { document.getElementById('brain').classList.remove('open'); }
        function openDash() { renderDash(); document.getElementById('dash').classList.add('open'); }
        function closeDash() { document.getElementById('dash').classList.remove('open'); }
        let wakeOn = true, isRec = false, isSpk = false, inConv = false;
        let rec = null, stream = null, chunks = [], wakeRec = null;
        const player = document.getElementById('player');
        const stTxt = document.getElementById('stTxt');

        function saveState() {
            localStorage.setItem('neo_memory', JSON.stringify(mem));
            localStorage.setItem('neo_mode', mode);
            document.getElementById('nCount').innerText = mem.length;
            updStats();
            document.getElementById('mBtn').innerText = mode === 'ARBEIT' ? 'Arbeit' : 'Privat';
        }
        saveState();

        function toggleMode() { mode = mode === 'ARBEIT' ? 'PRIVAT' : 'ARBEIT'; saveState(); }
        function setSt(s) {
            document.body.className = s || '';
            stTxt.innerText = s === 'listening' ? 'Hört zu...' : (s === 'thinking' ? 'Antwort kommt...' : (s === 'speaking' ? 'NEO spricht...' : 'Tippen oder „Hey Neo“'));
        }

        function stopWake() { if (wakeRec) { try { wakeRec.onend = null; wakeRec.abort(); } catch(e){} wakeRec = null; } }
        function toggleWake() {
            wakeOn = !wakeOn;
            document.getElementById('wLabel').innerText = wakeOn ? 'Voice' : 'Stumm';
            document.getElementById('wDot').classList.toggle('off', !wakeOn);
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
            wakeRec.onend = () => { wakeRec = null; if (wakeOn && !isRec && !isSpk && !inConv) setTimeout(startWake, 500); };
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

        function openList() {
            document.getElementById('modal').classList.add('open');
            document.getElementById('listBody').innerHTML = mem.length ? mem.map((x,i) => `<div class="row"><span>${esc(x)}</span><button class="ok-btn" aria-label="Erledigt" onclick="mem.splice(${i},1);saveState();openList();">✓</button></div>`).join('') : '<p class="empty">Keine Notizen.</p>';
        }
        function closeList() { document.getElementById('modal').classList.remove('open'); }

        async function sendTg() {
            stTxt.innerText = "Sende Telegram...";
            const r = await fetch('/telegram_notify', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:"📞 NEO Autorisierung angefordert!"}) });
            const d = await r.json();
            stTxt.innerText = d.ok ? "Telegram gesendet!" : (d.error || "Fehler");
        }

        function handleImg(ev) {
            const f = ev.target.files[0]; if (!f) return;
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
            const note = v.match(/^notiz(?:\\s*:|\\s)\\s*(.+)$/i);
            if (note) {
                mem.push(note[1].trim()); saveState();
                addLog(v, 'Notiz gespeichert.', 'note');
                stTxt.innerText = 'Notiz gespeichert ✓';
                return;
            }
            setSt('thinking'); sendNeo({ message: v });
        }

        async function sendNeo(payload) {
            stopWake();
            document.getElementById('actBar').innerHTML = '';
            payload.mode = mode; payload.memory = mem; payload.local_time_str = new Date().toLocaleString('de-DE');
            try {
                const res = await fetch('/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
                const d = await res.json();
                if (d.error) { inConv = false; setSt(null); stTxt.innerText = d.error; return; }
                if (d.end_conversation) inConv = false;
                const q = payload.image ? '📷 Mängel-Foto' : (payload.audio ? '🎙️ Sprachbefehl' : payload.message);
                addLog(q, d.reply || '', payload.image ? 'photo' : (d.copy_text ? 'offer' : 'chat'));
                if (d.new_memory) { mem.push(d.new_memory); saveState(); }
                if (d.copy_text) {
                    const b = document.createElement('button'); b.className = 'pill'; b.innerText = 'Text kopieren';
                    b.onclick = () => { navigator.clipboard.writeText(d.copy_text); b.innerText = '✓ Kopiert'; };
                    document.getElementById('actBar').appendChild(b);
                }
                if (d.action_url) {
                    inConv = false;
                    const a = document.createElement('a'); a.href = d.action_url; a.className = 'pill'; a.innerText = d.action_label || 'Öffnen';
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
</html>
"""

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
                        "iso": dt.isoformat(),
                        "time": dt.strftime("%d.%m. %H:%M") if "T" in clean else dt.strftime("%d.%m."),
                        "title": tm.group(1).strip().replace("\\n", " ").replace("\\,", ","),
                        "loc": lm.group(1).strip().replace("\\n", " ").replace("\\,", ",") if lm else ""
                    }))
        out.sort(key=lambda x: x[0])
        ICAL_CACHE["ts"] = now_ts
        ICAL_CACHE["events"] = [x[1] for x in out[:10]]
        return ICAL_CACHE["events"]
    except Exception:
        return ICAL_CACHE["events"]

SYSTEM_PROMPT = """Du bist NEO, der schnelle KI-Assistent von Margil (Kundenbetreuer Gebäudereinigung Hamburg).
Modus: {mode} | Zeit: {local_time}. Antworte kurz, höflich, ohne Markdown/Sternchen.
- Auto-Briefing ("Ich fahre los"): Nächster Termin + Codes aus Notizen + Google Maps URL in `action_url`.
- Dolmetscher DE <-> SQ: Bei Übersetzung ins Albanische `voice_lang`: "sq", sonst "de".
- Kalkulator: Büro ~220 m²/Std, 31,50 €/Std netto. Fertiger Text in `copy_text` + WhatsApp Intent (`intent://send?text=URL_ENCODED#Intent;scheme=whatsapp;package=com.whatsapp.w4b;end`).
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
    n = max(1, min(request.args.get("n", 3, type=int), 10))
    return jsonify({"events": parse_upcoming_events()[:n]})

@app.route("/manifest.json")
def manifest():
    return jsonify(MANIFEST_JSON)

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
