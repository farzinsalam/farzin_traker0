"""
BottleVision AI - Web Application & Live Streaming Server
Author: Antigravity AI

Runs a Flask web server that streams real-time YOLOv8 bottle detection,
Anti-Theft Kireedam alarm, 30% smile verification, visual CAPTCHA solver,
Thanos Infinity Gauntlet pose & snap, and "YOU CAN DRINK WATER NOW" notification.

Features:
  - Live MJPEG video stream with dynamic HUD overlays
  - Browser-side audio playback (Kireedam dialogue alarm, Iron Man snap, speech synthesis)
  - Interactive web buttons ("I Want Water", CAPTCHA input, Arm/Disarm, Demo Theft)
  - Automatic SSH public tunneling via localhost.run (generates instant https://... web link)
"""

import os
import sys
import time
import math
import io
import json
import threading
import subprocess
import re
import cv2
import numpy as np
from PIL import Image

from flask import Flask, Response, jsonify, request, send_from_directory, render_template_string

# Import core detection & guardian engines from main
from main import (
    BottleDetector,
    BottleGuardian,
    BottleAlarmPlayer,
    SmileDetector,
    CaptchaGenerator
)

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Global application state & instances
camera = None
detector = None
guardian = None
alarm_player = None
camera_lock = threading.Lock()
simulated_no_bottle = False
public_tunnel_url = None

def init_engines():
    global detector, guardian, alarm_player, camera
    print("[BottleVision Web] Initializing AI models and audio engine...")
    alarm_player = BottleAlarmPlayer()
    detector = BottleDetector()
    guardian = BottleGuardian(alarm_player=alarm_player, debounce_sec=0.7, smile_threshold=30)
    guardian.arm()
    
    # Try opening webcam (index 0)
    try:
        camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not camera.isOpened():
            camera = cv2.VideoCapture(0)
    except Exception as e:
        print(f"[BottleVision Web] Camera open warning: {e}")
        camera = None

def get_fallback_frame():
    """Generates a high-tech synthetic frame if webcam is unavailable or in use."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Background gradient
    for y in range(480):
        c = int(20 + 25 * (y / 480.0))
        img[y, :, :] = (c, c - 5, c + 10)
    
    cv2.putText(img, "BOTTLEVISION AI - VIRTUAL CAMERA", (110, 200),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 200), 2, cv2.LINE_AA)
    cv2.putText(img, "Webcam busy or in background mode", (140, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1, cv2.LINE_AA)
    cv2.putText(img, "Anti-Theft Guardian Active", (190, 280),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2, cv2.LINE_AA)
    
    # Draw simulated bottle
    if not simulated_no_bottle:
        bx1, by1, bx2, by2 = 280, 140, 360, 360
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (0, 255, 120), 2)
        cv2.putText(img, "Bottle: 96%", (bx1, by1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 120), 1, cv2.LINE_AA)
    return img

def generate_frames():
    """Video streaming generator function (MJPEG)."""
    global camera, detector, guardian, simulated_no_bottle
    
    while True:
        frame = None
        if camera is not None and camera.isOpened():
            with camera_lock:
                success, cap_frame = camera.read()
                if success and cap_frame is not None:
                    frame = cap_frame
        
        if frame is None:
            frame = get_fallback_frame()
        
        # Mirror for natural selfie webcam view
        frame = cv2.flip(frame, 1)
        
        # If simulated theft is active, blank out bottle detections
        if simulated_no_bottle:
            detections = []
            annotated_frame = frame.copy()
            status, alert = guardian.update(0, annotated_frame)
            cv2.putText(annotated_frame, "SIMULATED THEFT: BOTTLE MISSING!", (50, 440),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
        else:
            annotated_frame, detections, count, fps = detector.detect(
                frame,
                draw_overlay=True,
                guardian_state=guardian.state,
                smile_info=guardian.last_smile_info
            )
            status, alert = guardian.update(len(detections), annotated_frame)

        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # ~30 FPS

# ==============================================================================
# FLASK HTTP ROUTES
# ==============================================================================
@app.route('/')
def index():
    return render_template_string(HTML_PAGE, tunnel_url=public_tunnel_url)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/state')
def get_state():
    info = guardian.last_smile_info if guardian else {}
    return jsonify({
        "state": guardian.state if guardian else "UNKNOWN",
        "smile_pct": info.get("smile_pct", 0),
        "threshold": info.get("threshold", 30),
        "captcha_active": info.get("captcha_active", False),
        "captcha_code": guardian.current_captcha_code if guardian else "",
        "thanos_active": info.get("thanos_active", False),
        "water_granted": info.get("granted", False),
        "alert_playing": guardian.player.is_playing if (guardian and guardian.player) else False,
        "simulated_theft": simulated_no_bottle,
        "public_tunnel_url": public_tunnel_url
    })

@app.route('/api/request_water', methods=['POST'])
def request_water():
    if guardian:
        guardian.request_water()
        return jsonify({"success": True, "state": guardian.state})
    return jsonify({"success": False})

@app.route('/api/verify_captcha', methods=['POST'])
def verify_captcha():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    if guardian:
        success = guardian.verify_captcha(code)
        return jsonify({"success": success, "state": guardian.state})
    return jsonify({"success": False})

@app.route('/api/trigger_snap', methods=['POST'])
def trigger_snap():
    if guardian:
        guardian.trigger_snap()
        return jsonify({"success": True, "state": guardian.state})
    return jsonify({"success": False})

@app.route('/api/toggle_theft', methods=['POST'])
def toggle_theft():
    global simulated_no_bottle
    simulated_no_bottle = not simulated_no_bottle
    return jsonify({"simulated_theft": simulated_no_bottle})

@app.route('/api/arm', methods=['POST'])
def arm_guardian():
    global simulated_no_bottle
    simulated_no_bottle = False
    if guardian:
        guardian.arm()
        return jsonify({"success": True, "state": guardian.state})
    return jsonify({"success": False})

@app.route('/sounds/<path:filename>')
def serve_sounds(filename):
    return send_from_directory(os.path.join(BASE_DIR, "sounds"), filename)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(BASE_DIR, "assets"), filename)

@app.route('/captures/<path:filename>')
def serve_captures(filename):
    return send_from_directory(os.path.join(BASE_DIR, "captures"), filename)

# ==============================================================================
# AUTOMATIC TUNNEL LAUNCHER (localhost.run via built-in Windows OpenSSH)
# ==============================================================================
def start_tunnel_thread(port=5000):
    global public_tunnel_url
    def run_tunnel():
        global public_tunnel_url
        print("\n[Tunnel] Establishing instant public HTTPS web link via OpenSSH...")
        cmd = [
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-R", f"80:127.0.0.1:{port}",
            "nokey@localhost.run"
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            for line in proc.stdout:
                match = re.search(r'https://[a-zA-Z0-9-]+\.lhr\.life', line)
                if match:
                    public_tunnel_url = match.group(0)
                    print("\n" + "=" * 65)
                    print("🎉 BOTTLEVISION PUBLIC WEB LINK IS LIVE!")
                    print(f"👉 {public_tunnel_url}")
                    print(f"👉 Local: http://localhost:{port}")
                    print("=" * 65 + "\n")
                    break

        except Exception as e:
            print(f"[Tunnel] SSH tunnel note: {e}")


    t = threading.Thread(target=run_tunnel, daemon=True)
    t.start()

# ==============================================================================
# EMBEDDED HIGH-TECH CYBERPUNK WEB UI TEMPLATE
# ==============================================================================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BottleVision AI - Anti-Theft Guardian & Thanos Snap</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090b10;
      --card-bg: rgba(18, 24, 38, 0.75);
      --primary: #00f0ff;
      --danger: #ff0055;
      --success: #00ff88;
      --warning: #ffb700;
      --gold: #ffd700;
      --border: rgba(0, 240, 255, 0.25);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: radial-gradient(circle at center, #121829 0%, var(--bg) 100%);
      color: #fff;
      font-family: 'Rajdhani', sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 20px;
      overflow-x: hidden;
    }
    header {
      text-align: center;
      margin-bottom: 20px;
    }
    h1 {
      font-family: 'Orbitron', sans-serif;
      font-size: 2.2rem;
      background: linear-gradient(90deg, #00f0ff, #00ff88, #ffd700);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      text-transform: uppercase;
      letter-spacing: 2px;
    }
    .badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.85rem;
      font-weight: 700;
      letter-spacing: 1px;
      margin-top: 6px;
      background: rgba(0, 240, 255, 0.15);
      border: 1px solid var(--primary);
      color: var(--primary);
    }
    .container {
      display: grid;
      grid-template-columns: 1fr 360px;
      gap: 24px;
      max-width: 1200px;
      width: 100%;
    }
    @media (max-width: 900px) {
      .container { grid-template-columns: 1fr; }
    }
    .stream-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 0 30px rgba(0, 240, 255, 0.15);
      backdrop-filter: blur(12px);
      display: flex;
      flex-direction: column;
      align-items: center;
      position: relative;
    }
    .stream-wrapper {
      position: relative;
      width: 100%;
      background: #000;
      border-radius: 12px 12px 0 0;
      overflow: hidden;
    }
    .stream-img {
      width: 100%;
      height: auto;
      display: block;
      object-fit: cover;
    }
    .hud-overlay {
      position: absolute;
      top: 16px;
      left: 16px;
      right: 16px;
      display: flex;
      justify-content: space-between;
      pointer-events: none;
    }
    .hud-pill {
      background: rgba(0, 0, 0, 0.7);
      padding: 6px 14px;
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, 0.2);
      font-family: 'Orbitron', sans-serif;
      font-size: 0.8rem;
    }
    .panel-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 18px;
      backdrop-filter: blur(12px);
    }
    .status-box {
      background: rgba(0, 0, 0, 0.4);
      padding: 16px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      text-align: center;
    }
    .status-title {
      font-size: 0.85rem;
      color: #8892b0;
      text-transform: uppercase;
      letter-spacing: 1px;
    }
    .status-val {
      font-family: 'Orbitron', sans-serif;
      font-size: 1.3rem;
      margin-top: 6px;
      font-weight: 700;
    }
    .btn {
      background: linear-gradient(135deg, rgba(0, 240, 255, 0.2), rgba(0, 255, 136, 0.2));
      border: 1px solid var(--primary);
      color: #fff;
      padding: 14px 20px;
      border-radius: 10px;
      font-family: 'Orbitron', sans-serif;
      font-size: 0.95rem;
      font-weight: 700;
      letter-spacing: 1px;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      text-decoration: none;
    }
    .btn:hover {
      background: var(--primary);
      color: #000;
      box-shadow: 0 0 20px rgba(0, 240, 255, 0.6);
      transform: translateY(-2px);
    }
    .btn-danger {
      border-color: var(--danger);
      background: linear-gradient(135deg, rgba(255, 0, 85, 0.2), rgba(255, 100, 0, 0.2));
    }
    .btn-danger:hover {
      background: var(--danger);
      color: #fff;
      box-shadow: 0 0 20px rgba(255, 0, 85, 0.6);
    }
    .btn-gold {
      border-color: var(--gold);
      background: linear-gradient(135deg, rgba(255, 215, 0, 0.2), rgba(255, 136, 0, 0.2));
    }
    .btn-gold:hover {
      background: var(--gold);
      color: #000;
      box-shadow: 0 0 20px rgba(255, 215, 0, 0.6);
    }
    .progress-bar-wrap {
      background: rgba(0, 0, 0, 0.5);
      border-radius: 10px;
      height: 20px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.1);
      position: relative;
    }
    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, #ff0055, #ffb700, #00ff88);
      width: 0%;
      transition: width 0.3s ease;
    }
    .progress-text {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 0.75rem;
      font-weight: 700;
    }
    .captcha-box {
      display: flex;
      flex-direction: column;
      gap: 10px;
      background: rgba(0,0,0,0.3);
      padding: 14px;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .captcha-input {
      background: rgba(0,0,0,0.6);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 14px;
      color: #fff;
      font-family: 'Orbitron', sans-serif;
      font-size: 1.1rem;
      text-align: center;
      letter-spacing: 4px;
    }
    .captcha-input:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 10px rgba(0, 240, 255, 0.4);
    }
    /* Fullscreen Water Celebration Modal */
    .water-modal {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: radial-gradient(circle, #022b42 0%, #010a12 100%);
      z-index: 9999;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 30px;
      animation: fadeIn 0.5s ease;
    }
    .water-modal h2 {
      font-family: 'Orbitron', sans-serif;
      font-size: 3.5rem;
      color: #00ffcc;
      text-shadow: 0 0 30px #00ffcc, 0 0 60px #00aaff;
      margin-bottom: 20px;
      animation: pulse 1.5s infinite alternate;
    }
    .water-modal p {
      font-size: 1.5rem;
      color: #d0f4ff;
      max-width: 600px;
      margin-bottom: 30px;
    }
    @keyframes pulse {
      0% { transform: scale(0.98); }
      100% { transform: scale(1.02); text-shadow: 0 0 45px #00ffcc, 0 0 90px #0088ff; }
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
  </style>
</head>
<body>

  <header>
    <h1>🛡️ BottleVision AI</h1>
    <div class="badge">ANTI-THEFT GUARDIAN • THANOS SNAP • WATER UNLOCK</div>
    {% if tunnel_url %}
    <div style="margin-top: 10px;">
      <span style="color: #8892b0;">Public Web Link: </span>
      <a href="{{ tunnel_url }}" target="_blank" style="color: #00ff88; font-weight: 700; text-decoration: none;">
        {{ tunnel_url }}
      </a>
    </div>
    {% endif %}
  </header>

  <div class="container">
    <!-- Camera Stream Card -->
    <div class="stream-card">
      <div class="stream-wrapper">
        <img class="stream-img" src="/video_feed" alt="BottleVision AI Feed">
        <div class="hud-overlay">
          <div class="hud-pill" id="live-indicator" style="color: #00ff88;">● LIVE STREAM</div>
          <div class="hud-pill" id="hud-status">SYSTEM ARMED</div>
        </div>
      </div>
      <div style="padding: 16px; width: 100%; display: flex; justify-content: space-around; background: rgba(0,0,0,0.3);">
        <button class="btn btn-danger" onclick="toggleTheft()" id="theft-btn">🚨 SIMULATE THEFT</button>
        <button class="btn" onclick="armSystem()">🛡️ RE-ARM GUARDIAN</button>
      </div>
    </div>

    <!-- Controls Panel -->
    <div class="panel-card">
      <div class="status-box">
        <div class="status-title">Guardian Status</div>
        <div class="status-val" id="state-text" style="color: #00ff88;">ARMED & SECURE</div>
      </div>

      <!-- Stage 1: Request Water -->
      <button class="btn" onclick="requestWater()" id="water-btn">💧 I WANT WATER</button>

      <!-- Stage 2: Smile Progress -->
      <div id="smile-section" style="display: flex; flex-direction: column; gap: 6px;">
        <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
          <span>😄 Smile Meter (Target: 30%)</span>
          <span id="smile-pct-text">0%</span>
        </div>
        <div class="progress-bar-wrap">
          <div class="progress-fill" id="smile-bar"></div>
          <div class="progress-text" id="smile-req-text">Smile to Unlock</div>
        </div>
      </div>

      <!-- Stage 3: Visual CAPTCHA -->
      <div class="captcha-box" id="captcha-section" style="display: none;">
        <div style="font-weight: 700; color: #ffb700;">🧩 4-Letter Security CAPTCHA Challenge</div>
        <div style="font-size: 0.85rem; color: #8892b0;">Type the 4-letter code shown on camera or below:</div>
        <input type="text" id="captcha-input" class="captcha-input" maxlength="4" placeholder="CODE" style="text-transform: uppercase;">
        <button class="btn btn-gold" onclick="submitCaptcha()">SUBMIT CAPTCHA</button>
      </div>


      <!-- Stage 4: Thanos Pose & Snap -->
      <button class="btn btn-gold" onclick="triggerThanos()" id="thanos-btn" style="display: none;">
        🫰 THANOS POSE & SNAP
      </button>

      <!-- Audio Elements -->
      <audio id="alarm-audio" src="/sounds/kireedam_alarm.wav" preload="auto"></audio>
      <audio id="snap-audio" src="/sounds/iron_man_snap.wav" preload="auto"></audio>
    </div>
  </div>

  <!-- Fullscreen Water Celebration Modal -->
  <div class="water-modal" id="water-modal">
    <div style="font-size: 5rem; margin-bottom: 20px;">🌊</div>
    <h2>YOU CAN DRINK WATER NOW</h2>
    <p>Security protocol cleared. You survived the Kireedam alarm, proved your smile, solved the CAPTCHA, and survived the Thanos snap!</p>
    <button class="btn" onclick="closeWaterModal()" style="font-size: 1.1rem; padding: 16px 32px;">ENJOY WATER & RETURN BOTTLE</button>
  </div>

  <script>
    let currentState = "ARMED";
    let lastAlertPlaying = false;
    let waterModalShown = false;

    // Polling status loop
    async function updateState() {
      try {
        const res = await fetch('/api/state');
        const data = await res.json();
        currentState = data.state;

        // Update state label
        const stateEl = document.getElementById('state-text');
        const hudEl = document.getElementById('hud-status');
        stateEl.innerText = data.state;
        hudEl.innerText = data.state;

        if (data.state === 'THEFT_ALERT') {
          stateEl.style.color = '#ff0055';
          hudEl.style.color = '#ff0055';
          if (!lastAlertPlaying && data.alert_playing) {
            playAlarmSound();
          }
        } else if (data.state === 'WATER_GRANTED') {
          stateEl.style.color = '#00ffcc';
          hudEl.style.color = '#00ffcc';
          if (!waterModalShown) {
            showWaterModal();
          }
        } else {
          stateEl.style.color = '#00ff88';
          hudEl.style.color = '#00ff88';
          if (data.state === 'ARMED') {
            waterModalShown = false;
            document.getElementById('water-modal').style.display = 'none';
          }
        }
        lastAlertPlaying = data.alert_playing;

        // Smile meter
        const smileBar = document.getElementById('smile-bar');
        const smilePct = document.getElementById('smile-pct-text');
        smileBar.style.width = data.smile_pct + '%';
        smilePct.innerText = data.smile_pct + '%';

        // CAPTCHA visibility
        const captchaSec = document.getElementById('captcha-section');
        if (data.captcha_active) {
          captchaSec.style.display = 'flex';
          if (data.captcha_code && !document.getElementById('captcha-input').placeholder.includes(data.captcha_code)) {
            document.getElementById('captcha-input').placeholder = data.captcha_code;
          }
        } else {
          captchaSec.style.display = 'none';
        }

        // Thanos button visibility
        const thanosBtn = document.getElementById('thanos-btn');
        if (data.state === 'THANOS_POSE' || data.thanos_active) {
          thanosBtn.style.display = 'flex';
        } else {
          thanosBtn.style.display = 'none';
        }

      } catch (e) {
        console.error("State update error:", e);
      }
    }

    setInterval(updateState, 500);

    async function requestWater() {
      await fetch('/api/request_water', { method: 'POST' });
      speak("Please smile thirty percent to verify hydration clearance.");
    }

    async function submitCaptcha() {
      const input = document.getElementById('captcha-input').value.trim();
      const res = await fetch('/api/verify_captcha', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: input })
      });
      const data = await res.json();
      if (data.success) {
        speak("CAPTCHA cleared! Prepare for Thanos Pose and Snap!");
      } else {
        alert("Invalid CAPTCHA code. Check the HUD and try again!");
      }
    }

    async function triggerThanos() {
      const snapAudio = document.getElementById('snap-audio');
      snapAudio.currentTime = 0;
      snapAudio.play().catch(e => console.log(e));
      await fetch('/api/trigger_snap', { method: 'POST' });
      setTimeout(() => {
        showWaterModal();
      }, 9800);
    }

    async function toggleTheft() {
      const res = await fetch('/api/toggle_theft', { method: 'POST' });
      const data = await res.json();
      const btn = document.getElementById('theft-btn');
      if (data.simulated_theft) {
        btn.innerText = "🛑 RESTORE BOTTLE";
        playAlarmSound();
      } else {
        btn.innerText = "🚨 SIMULATE THEFT";
      }
    }

    async function armSystem() {
      await fetch('/api/arm', { method: 'POST' });
      document.getElementById('water-modal').style.display = 'none';
      waterModalShown = false;
    }

    function showWaterModal() {
      waterModalShown = true;
      document.getElementById('water-modal').style.display = 'flex';
      speak("You can drink water now!");
    }

    function closeWaterModal() {
      document.getElementById('water-modal').style.display = 'none';
      armSystem();
    }

    function playAlarmSound() {
      const a = document.getElementById('alarm-audio');
      a.currentTime = 0;
      a.play().catch(e => console.log("Audio play blocked by browser autoplay policy:", e));
    }

    function speak(text) {
      if ('speechSynthesis' in window) {
        const utter = new SpeechSynthesisUtterance(text);
        utter.rate = 1.0;
        utter.pitch = 1.1;
        window.speechSynthesis.speak(utter);
      }
    }
  </script>
</body>
</html>
"""

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="BottleVision AI Web Server")
    parser.add_argument("--port", type=int, default=5000, help="Port to run web server on")
    parser.add_argument("--no-tunnel", action="store_true", help="Disable public SSH tunnel")
    args = parser.parse_args()

    init_engines()

    if not args.no_tunnel:
        start_tunnel_thread(port=args.port)

    print(f"\n[BottleVision Web] Server running at: http://localhost:{args.port}")
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)
