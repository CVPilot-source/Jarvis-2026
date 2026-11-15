import os
import re
import time
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
ICAL_CACHE = {"ts": 0, "events": []}

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="115" fill="#020408"/>
  <circle cx="256" cy="256" r="155" fill="none" stroke="#00f3ff" stroke-width="8" stroke-dasharray="16 10"/>
  <circle cx="256" cy="256" r="110" fill="none" stroke="#ff9900" stroke-width="5"/>
  <circle cx="256" cy="256" r="24" fill="#ff9900"/>
</svg>"""

HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#020408">
    <link rel="manifest" href="/manifest.json">
    <title>NEO // ENTERPRISE OS - COMMAND CENTER</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Courier+New:wght@400;700&family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --bg-deep: #020408;
            --hud-panel: rgba(3, 11, 22, 0.94);
            --neon-cyan: #00f3ff;
            --neon-purple: #b000ff;
            --neon-orange: #ff9900;
            --text-main: #e0fbfc;
            --text-dim: #64748b;
            --border-glow: rgba(0, 243, 255, 0.4);
        }

        * { box-sizing: border-box; user-select: none; -webkit-tap-highlight-color: transparent; }

        html, body {
            margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden;
            background-color: var(--bg-deep);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            background-image: 
                radial-gradient(circle at 50% 50%, rgba(0, 243, 255, 0.08) 0%, transparent 90%),
                linear-gradient(rgba(0,243,255,0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0,243,255,0.02) 1px, transparent 1px);
            background-size: 100% 100%, 30px 30px, 30px 30px;
        }

        .desktop-view { display: none; width: 100vw; height: 100vh; }
        .mobile-view { display: block; width: 100vw; height: 100vh; overflow-y: auto; }

        @media (min-width: 1024px) {
            .desktop-view { display: flex; flex-direction: column; justify-content: space-between; padding: 12px; }
            .mobile-view { display: none; }
        }

        /* ================= MOBILE VIEW ================= */
        .mobile-container {
            max-width: 480px; margin: 0 auto; padding: 15px; min-height: 100vh;
            display: flex; flex-direction: column; justify-content: space-between;
        }
        .mobile-header {
            background: var(--hud-panel); border: 1px solid var(--border-glow);
            border-radius: 12px; padding: 12px 15px; display: flex; justify-content: space-between; align-items: center;
            backdrop-filter: blur(12px); box-shadow: 0 0 20px rgba(0, 243, 255, 0.15);
        }
        .mobile-core-box { text-align: center; margin: 15px 0; position: relative; }
        .core-pulse {
            width: 95px; height: 95px;
            background: radial-gradient(circle, var(--neon-cyan) 0%, rgba(176,0,255,0.4) 70%, transparent 100%);
            border-radius: 50%; margin: 0 auto 10px auto;
            box-shadow: 0 0 35px var(--neon-cyan); animation: pulseCore 3s infinite alternate;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
            border: 2px solid var(--neon-cyan);
        }
        .core-pulse::after {
            content: ''; width: 55px; height: 55px; border: 2px dashed var(--text-main);
            border-radius: 50%; animation: spin 12s linear infinite;
        }
        @keyframes pulseCore {
            0% { transform: scale(0.95); box-shadow: 0 0 20px var(--neon-cyan); }
            100% { transform: scale(1.06); box-shadow: 0 0 45px var(--neon-cyan); }
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .voice-bar {
            background: var(--hud-panel); border: 1px solid var(--border-glow);
            border-radius: 20px; padding: 8px 15px; font-size: 11px; color: var(--neon-cyan);
            display: inline-block; box-shadow: 0 0 10px rgba(0,243,255,0.15);
        }
        .mobile-cards { display: flex; flex-direction: column; gap: 10px; margin-bottom: 15px; }
        .m-card {
            background: var(--hud-panel); border: 1px solid rgba(0, 243, 255, 0.25);
            border-radius: 12px; padding: 12px 14px; backdrop-filter: blur(10px); cursor: pointer;
        }
        .m-card h3 { font-size: 11px; color: var(--neon-orange); margin-bottom: 4px; display: flex; justify-content: space-between; }
        .m-card p { font-size: 11px; color: var(--text-dim); }
        .calc-box input {
            width: 100%; background: rgba(0,0,0,0.6); border: 1px solid var(--border-glow);
            color: var(--text-main); padding: 6px 8px; border-radius: 6px; margin-top: 4px; font-size: 12px;
        }
        .calc-result { margin-top: 6px; font-size: 12px; color: var(--neon-orange); font-weight: bold; }
        .action-btn {
            display: block; width: 100%; background: linear-gradient(135deg, var(--neon-orange), #ff5500);
            color: #000; border: none; padding: 8px; border-radius: 6px; font-weight: bold;
            margin-top: 8px; cursor: pointer; text-align: center; text-decoration: none; font-size: 11px;
        }

        /* ================= DESKTOP VIEW (HOLOGRAPHIC SCI-FI COMMAND CENTER) ================= */
        .hud-header {
            display: flex; justify-content: space-between; align-items: center;
            background: var(--hud-panel); border: 1px solid var(--border-glow);
            padding: 10px 20px; border-radius: 6px; backdrop-filter: blur(15px);
            box-shadow: 0 0 25px rgba(0, 243, 255, 0.2); position: relative;
        }
        .hud-header h1 { font-size: 13px; color: var(--neon-cyan); letter-spacing: 3px; margin: 0; }

        .hud-main-grid {
            display: grid;
            grid-template-columns: 280px 1fr 280px;
            gap: 12px; flex: 1; margin: 10px 0; align-items: stretch;
        }

        .hud-box {
            background: var(--hud-panel); border: 1px solid var(--border-glow);
            border-radius: 8px; padding: 12px; backdrop-filter: blur(15px);
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.05), 0 0 20px rgba(0, 243, 255, 0.08);
            display: flex; flex-direction: column; gap: 8px; position: relative;
            overflow: hidden;
        }
        .hud-box h3 {
            font-size: 10px; color: var(--neon-orange); margin: 0;
            letter-spacing: 2px; border-bottom: 1px dashed rgba(255,153,0,0.4); padding-bottom: 3px;
            text-transform: uppercase;
        }

        /* Central Holographic Stage with Node Network */
        .hud-center-stage {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            position: relative; background: radial-gradient(circle, rgba(0,243,255,0.08) 0%, rgba(176,0,255,0.03) 60%, transparent 90%);
            border: 1px solid rgba(0, 243, 255, 0.25); border-radius: 8px; padding: 15px; overflow: hidden;
        }

        .node-svg-overlay {
            position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; opacity: 0.6;
        }

        .hud-core-ring {
            width: 140px; height: 140px;
            background: radial-gradient(circle, var(--neon-cyan) 0%, rgba(176,0,255,0.4) 65%, transparent 100%);
            border-radius: 50%; box-shadow: 0 0 50px var(--neon-cyan);
            display: flex; align-items: center; justify-content: center;
            animation: pulseCore 4s infinite alternate; cursor: pointer; z
