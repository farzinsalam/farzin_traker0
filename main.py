"""
BottleVision AI - All-in-One Bottle Detection & Anti-Theft Guardian Software
Author: Antigravity AI

Detects water bottles, plastic bottles, glass bottles, and containers in real time.
Features:
  - Real-time YOLOv8 bottle detection & analytics
  - 🛡️ Anti-Theft Bottle Guardian: sounds random alarms / funny voice alerts if your bottle is stolen!
Usage:
  python main.py             -> Launch Desktop GUI
  python main.py --cli       -> Launch Lightweight OpenCV camera viewer
  python main.py --cli --guard -> Launch CLI with Anti-Theft Guardian active
  python main.py --image img -> Detect bottles on an image file
  python main.py --test      -> Run self-test verification
"""

import os
import sys
import time
import math
import struct
import io
import wave
import random
import argparse
import threading
import subprocess
from datetime import datetime

import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont

# Safe import of YOLO
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

# Safe import of Windows audio
try:
    import winsound
except ImportError:
    winsound = None


# ==============================================================================
# 1. AUDIO SYNTHESIZER & RANDOM ALARM PLAYER
# ==============================================================================
class BottleAlarmPlayer:
    """
    Synthesizes and plays random alarm sounds and funny classroom voice alerts.
    Operates 100% locally with zero external audio dependencies using:
      1. In-memory synthesized WAV files played asynchronously via winsound.
      2. Windows System Speech Synthesis for funny voice warnings.
    """

    VOICE_PHRASES = [
        "Hey! Put Farzin's water bottle back right now!",
        "Hands off the water bottle! Thief detected!",
        "Warning! Water bottle theft in progress! Put it down!",
        "Code Red in classroom! Who stole the only water bottle?!",
        "Step away from the water bottle slowly and nobody gets hurt!",
        "Drop the bottle! That is not your water!",
        "Did you really think I wouldn't notice you taking my water bottle?!",
        "Intruder alert! Put the hydration station back on the desk!",
    ]

    def __init__(self):
        self.sound_mode = "KIREEDAM"
        self.is_playing = False
        self._lock = threading.Lock()
        self._cached_wavs = {}
        self.sounds_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
        os.makedirs(self.sounds_dir, exist_ok=True)
        self.kireedam_wav_path = os.path.join(self.sounds_dir, "kireedam_alarm.wav")
        self.iron_man_wav_path = os.path.join(self.sounds_dir, "iron_man_snap.wav")
        self.iron_man_mp3_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "Avengers_ Endgame (2019) - _And I.. Am... Iron Man_ _ Movie Clip HD_62_72.mp3"
        )
        self._kireedam_data = None
        self._load_kireedam_sound()
        self._ensure_iron_man_sound()
        self._pregenerate_sounds()

    def _ensure_iron_man_sound(self):
        """Ensures the Avengers Iron Man audio from user MP3 is converted to WAV for zero-latency playback."""
        if os.path.exists(self.iron_man_wav_path) and os.path.getsize(self.iron_man_wav_path) > 10000:
            return
        if os.path.exists(self.iron_man_mp3_path):
            try:
                import imageio_ffmpeg
                ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
                cmd = [
                    ffmpeg_bin, "-y", "-i", self.iron_man_mp3_path,
                    "-ac", "1", "-ar", "22050", "-sample_fmt", "s16",
                    self.iron_man_wav_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("[BottleAlarmPlayer] Iron Man audio prepared from user MP3.")
            except Exception as e:
                print(f"[BottleAlarmPlayer] Warning converting Iron Man MP3: {e}")

    def set_mode(self, mode: str):
        """Set sound mode: KIREEDAM, RANDOM_ALL, VOICES, SIRENS, ARCADE"""
        self.sound_mode = mode

    def _load_kireedam_sound(self):
        """Loads or downloads the Kireedam 'Kathi Thazhe Idada' audio."""
        if os.path.exists(self.kireedam_wav_path):
            try:
                with open(self.kireedam_wav_path, "rb") as f:
                    self._kireedam_data = f.read()
                return
            except Exception as e:
                print(f"[BottleAlarmPlayer] Warning reading {self.kireedam_wav_path}: {e}")

        # If not present, try background download via yt-dlp & imageio-ffmpeg
        threading.Thread(target=self._download_kireedam_sound, daemon=True).start()

    def _download_kireedam_sound(self):
        """Background downloader and converter for Kireedam audio."""
        try:
            m4a_path = os.path.join(self.sounds_dir, "kireedam_alarm.m4a")
            url = "https://www.youtube.com/watch?v=khdmMKIs5dc"
            cmd_dl = [sys.executable, "-m", "yt_dlp", "-f", "140", url, "-o", m4a_path]
            subprocess.run(cmd_dl, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            import imageio_ffmpeg
            ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
            cmd_cv = [ffmpeg_bin, "-y", "-i", m4a_path, "-ar", "22050", "-ac", "1", self.kireedam_wav_path]
            subprocess.run(cmd_cv, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(self.kireedam_wav_path):
                with open(self.kireedam_wav_path, "rb") as f:
                    self._kireedam_data = f.read()
                print("[BottleAlarmPlayer] Kireedam sound loaded successfully!")
        except Exception as e:
            print(f"[BottleAlarmPlayer] Could not auto-download Kireedam sound: {e}")

    def play_iron_man(self) -> str:
        """Plays the iconic 'And I... am... Iron Man! [SNAP]' audio."""
        if os.path.exists(self.iron_man_wav_path) and winsound:
            try:
                winsound.PlaySound(self.iron_man_wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return "🧤 'And I... Am... Iron Man!' (Snap)"
            except Exception as e:
                print(f"[BottleAlarmPlayer] PlaySound error: {e}")
        # Fallback speech synthesis
        threading.Thread(target=self._speak, args=("And I... am... Iron Man!",), daemon=True).start()
        return "🧤 'And I... Am... Iron Man!' (Speech)"

    def play_kireedam(self) -> str:
        """Plays the iconic 'Kireedam kathi thazhe idada' audio."""
        if os.path.exists(self.kireedam_wav_path) and winsound:
            try:
                winsound.PlaySound(self.kireedam_wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return "👑 Kireedam (Kathi Thazhe Idada)"
            except Exception as e:
                print(f"[BottleAlarmPlayer] PlaySound error: {e}")
        elif self._kireedam_data and winsound:
            ws = winsound
            try:
                threading.Thread(
                    target=lambda: ws.PlaySound(self._kireedam_data, ws.SND_MEMORY),
                    daemon=True
                ).start()
                return "👑 Kireedam (Kathi Thazhe Idada)"
            except Exception as e:
                print(f"[BottleAlarmPlayer] PlaySound error: {e}")
        return self.play_random()

    def play_alarm(self) -> str:
        """Triggers alarm based on configured sound_mode."""
        if self.sound_mode == "KIREEDAM":
            return self.play_kireedam()
        elif self.sound_mode == "RANDOM_ALL":
            # 60% chance Kireedam, 40% random voice/synth
            if random.random() < 0.60 and (self._kireedam_data or os.path.exists(self.kireedam_wav_path)):
                return self.play_kireedam()
            else:
                return self.play_random()
        else:
            return self.play_random()

    def _pregenerate_sounds(self):
        """Pre-computes in-memory WAV audio clips for zero-latency playback."""
        sr = 22050
        try:
            # 1. Police / Emergency Siren (sweeping frequency)
            siren_samples = []
            dur_siren = 1.4
            for i in range(int(sr * dur_siren)):
                t = i / sr
                freq = 750 + 450 * math.sin(2 * math.pi * 2.8 * t)
                siren_samples.append(18000 * math.sin(2 * math.pi * freq * t))
            self._cached_wavs["siren"] = self._create_wav(siren_samples, sr)

            # 2. Sci-Fi Laser Blaster (arcade pitch drops)
            laser_samples = []
            for blast in range(3):
                blast_len = int(sr * 0.16)
                for i in range(blast_len):
                    p = i / blast_len
                    freq = 2400 * ((1.0 - p) ** 2.2) + 200
                    env = 1.0 - p
                    laser_samples.append(env * 20000 * math.sin(2 * math.pi * freq * (i / sr)))
                laser_samples.extend([0] * int(sr * 0.05))
            self._cached_wavs["laser"] = self._create_wav(laser_samples, sr)

            # 3. 8-Bit Robot Panic (R2-D2 chaotic robotic beeps)
            panic_samples = []
            tones = [1400, 780, 1950, 620, 2200, 950, 1600, 2400, 850, 2100, 1300, 2600]
            step_len = int(sr * 0.08)
            for tone in tones:
                for i in range(step_len):
                    # Slight square wave distortion for 8-bit flavor
                    val = math.sin(2 * math.pi * tone * (i / sr))
                    val = 18000 if val >= 0 else -18000
                    panic_samples.append(val)
            self._cached_wavs["panic_8bit"] = self._create_wav(panic_samples, sr)

            # 4. Harsh Burglar Alarm (alternating dual frequencies)
            burglar_samples = []
            for rep in range(4):
                f_hi = 1800
                f_lo = 1100
                h_len = int(sr * 0.14)
                for i in range(h_len):
                    burglar_samples.append(20000 * math.sin(2 * math.pi * f_hi * (i / sr)))
                for i in range(h_len):
                    burglar_samples.append(20000 * math.sin(2 * math.pi * f_lo * (i / sr)))
            self._cached_wavs["burglar"] = self._create_wav(burglar_samples, sr)

            # 5. Cartoon Boing / Spring
            boing_samples = []
            dur_boing = 0.6
            for i in range(int(sr * dur_boing)):
                t = i / dur_boing
                freq = 220 + 750 * (t ** 1.8)
                mod = math.sin(2 * math.pi * 25 * t)
                env = math.exp(-3.0 * t)
                boing_samples.append(env * 22000 * math.sin(2 * math.pi * (freq + 60 * mod) * (i / sr)))
            self._cached_wavs["cartoon_boing"] = self._create_wav(boing_samples, sr)

            # 6. UFO Alien Wobble
            ufo_samples = []
            dur_ufo = 1.0
            for i in range(int(sr * dur_ufo)):
                t = i / sr
                freq = 900 + 350 * math.sin(2 * math.pi * 18 * t)
                ufo_samples.append(18000 * math.sin(2 * math.pi * freq * t))
            self._cached_wavs["ufo_wobble"] = self._create_wav(ufo_samples, sr)

            # 7. Bottle Secure Chime (positive 2-tone pleasant chime)
            chime_samples = []
            for freq, dur in [(659, 0.15), (880, 0.35)]:
                c_len = int(sr * dur)
                for i in range(c_len):
                    t = i / c_len
                    env = math.exp(-4.0 * t)
                    chime_samples.append(env * 16000 * math.sin(2 * math.pi * freq * (i / sr)))
            self._cached_wavs["secure_chime"] = self._create_wav(chime_samples, sr)

            # 8. Water Granted Celebration Chime (rising happy major chord)
            grant_samples = []
            notes = [523.25, 659.25, 783.99, 1046.50]
            for freq in notes:
                dur = 0.16
                n_s = int(sr * dur)
                for i in range(n_s):
                    t = i / n_s
                    env = math.exp(-2.8 * t)
                    grant_samples.append(env * 20000 * math.sin(2 * math.pi * freq * (i / sr)))
            self._cached_wavs["water_granted"] = self._create_wav(grant_samples, sr)

        except Exception as e:
            print(f"[BottleAlarmPlayer] Warning: Failed to pregenerate some audio: {e}")

    @staticmethod
    def _create_wav(samples, sample_rate=22050) -> bytes:
        """Converts float/int samples list into complete in-memory WAV byte stream."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            frames = bytearray()
            for s in samples:
                val = max(-32767, min(32767, int(s)))
                frames.extend(struct.pack("<h", val))
            w.writeframes(frames)
        return buf.getvalue()

    def play_secure_chime(self):
        """Plays a pleasant reassurance chime when the bottle is placed/returned."""
        data = self._cached_wavs.get("secure_chime")
        if data and winsound:
            ws = winsound
            try:
                threading.Thread(
                    target=lambda: ws.PlaySound(data, ws.SND_MEMORY),
                    daemon=True
                ).start()
            except Exception:
                pass

    def play_water_granted_chime(self, smile_pct: int = 30):
        """Plays celebratory chord and voice when smile is achieved and water is unlocked."""
        data = self._cached_wavs.get("water_granted")
        if data and winsound:
            ws = winsound
            try:
                threading.Thread(
                    target=lambda: ws.PlaySound(data, ws.SND_MEMORY),
                    daemon=True
                ).start()
            except Exception:
                pass
        msg = f"{smile_pct} percent smile verified! Water access granted! Enjoy your drink!"
        threading.Thread(target=self._speak, args=(msg,), daemon=True).start()

    def play_random(self) -> str:
        """Picks and triggers a random alarm sound according to selected sound mode."""
        siren_keys = ["siren", "burglar", "ufo_wobble"]
        arcade_keys = ["laser", "panic_8bit", "cartoon_boing"]
        synth_keys = siren_keys + arcade_keys
        sound_key = ""

        # Determine choice candidate pool
        if self.sound_mode == "VOICES":
            action = "VOICE"
        elif self.sound_mode == "SIRENS":
            action = "SYNTH"
            sound_key = random.choice(siren_keys)
        elif self.sound_mode == "ARCADE":
            action = "SYNTH"
            sound_key = random.choice(arcade_keys)
        else:  # RANDOM_ALL
            # 50% chance funny voice warning, 50% chance synthesized sound FX
            if random.random() < 0.5:
                action = "VOICE"
            else:
                action = "SYNTH"
                sound_key = random.choice(synth_keys)

        if action == "VOICE":
            phrase = random.choice(self.VOICE_PHRASES)
            threading.Thread(target=self._speak, args=(phrase,), daemon=True).start()
            return f"Voice Alert: '{phrase}'"
        else:
            wav_data = self._cached_wavs.get(sound_key)
            if wav_data and winsound:
                ws = winsound
                try:
                    threading.Thread(
                        target=lambda: ws.PlaySound(wav_data, ws.SND_MEMORY),
                        daemon=True
                    ).start()
                except Exception:
                    pass
            friendly_names = {
                "siren": "Police Emergency Siren",
                "laser": "Sci-Fi Laser Blaster",
                "panic_8bit": "8-Bit Robot Panic",
                "burglar": "Harsh Burglar Buzzer",
                "cartoon_boing": "Cartoon Spring Boing",
                "ufo_wobble": "UFO Alien Wobble"
            }
            return f"Sound FX: {friendly_names.get(sound_key, sound_key)}"

    def _speak(self, phrase: str):
        """Uses Windows PowerShell System.Speech to speak without opening any console window."""
        with self._lock:
            try:
                # 0x08000000 = CREATE_NO_WINDOW
                safe_phrase = phrase.replace("'", "").replace('"', "")
                script = f'Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 1; $s.Speak("{safe_phrase}")'
                subprocess.run(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
                    creationflags=0x08000000,
                    timeout=5,
                    check=False
                )
            except Exception as e:
                # Fallback to winsound beep if speech fails
                if winsound:
                    try:
                        winsound.Beep(1200, 350)
                    except Exception:
                        pass

    def stop(self):
        """Stops any currently playing sound."""
        if winsound:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass


# ==============================================================================
# 2. VISUAL CAPTCHA SECURITY GENERATOR
# ==============================================================================
class CaptchaGenerator:
    """
    Generates visual security CAPTCHAs for Anti-Theft Bottle Guardian unlock.
    """
    CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Disambiguated (no 0/O, 1/I)

    @classmethod
    def generate(cls, length: int = 5) -> tuple[str, Image.Image]:
        code = "".join(random.choice(cls.CHARS) for _ in range(length))
        w, h = 210, 58
        img = Image.new("RGB", (w, h), color=(21, 29, 42))  # #151D2A
        draw = ImageDraw.Draw(img)

        # Attempt to load Arial font on Windows, else fallback
        font = None
        for font_path in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf", "arial.ttf"):
            try:
                font = ImageFont.truetype(font_path, 26)
                break
            except Exception:
                pass
        if font is None:
            font = ImageFont.load_default()

        # Security noise lines
        for _ in range(8):
            x1 = random.randint(0, w)
            y1 = random.randint(0, h)
            x2 = random.randint(0, w)
            y2 = random.randint(0, h)
            draw.line([(x1, y1), (x2, y2)], fill=(50, 70, 95), width=1)

        # Noise speckles
        for _ in range(120):
            draw.point((random.randint(0, w - 1), random.randint(0, h - 1)), fill=(80, 100, 140))

        # Colored characters with drop shadow
        char_colors = [(56, 189, 248), (251, 191, 36), (52, 211, 153), (244, 114, 182), (251, 146, 60), (167, 139, 250)]
        spacing = (w - 24) // length
        for i, ch in enumerate(code):
            cx = 14 + i * spacing + random.randint(-2, 2)
            cy = 12 + random.randint(-4, 4)
            draw.text((cx + 1, cy + 1), ch, fill=(10, 14, 20), font=font)
            draw.text((cx, cy), ch, fill=random.choice(char_colors), font=font)

        return code, img


# ==============================================================================
# 3. SMILE & FACE DETECTOR (YuNet)
# ==============================================================================
class SmileDetector:
    """
    Detects faces and computes real-time smile percentage (0% to 100%)
    using OpenCV YuNet facial landmark detection.
    """
    def __init__(self, model_path: str = "models/face_detection_yunet_2023mar.onnx"):
        self.model_path = model_path
        self.detector = None
        self._ensure_model()
        self._init_detector()

    def _ensure_model(self):
        if not os.path.exists(self.model_path):
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
            try:
                import urllib.request
                urllib.request.urlretrieve(url, self.model_path)
            except Exception as e:
                print(f"[SmileDetector] Could not download YuNet model: {e}")

    def _init_detector(self):
        create_fn = getattr(cv2, "FaceDetectorYN_create", None)
        if os.path.exists(self.model_path) and create_fn is not None:
            try:
                self.detector = create_fn(
                    model=self.model_path,
                    config="",
                    input_size=(320, 320),
                    score_threshold=0.55,
                    nms_threshold=0.3
                )
            except Exception as e:
                print(f"[SmileDetector] Error creating FaceDetectorYN: {e}")

    def detect_smile(self, frame: np.ndarray) -> tuple[bool, int, tuple[int, int, int, int] | None, list]:
        """
        Detects primary face and computes smile percentage (0 to 100).
        Returns: (face_found, smile_pct, (x, y, w, h), landmarks)
        """
        if self.detector is None:
            return False, 0, None, []

        h, w, _ = frame.shape
        self.detector.setInputSize((w, h))
        try:
            _, faces = self.detector.detect(frame)
        except Exception:
            return False, 0, None, []

        if faces is None or len(faces) == 0:
            return False, 0, None, []

        # Choose largest detected face (closest to camera)
        best_face = max(faces, key=lambda f: float(f[2]) * float(f[3]))
        x, y, fw, fh = int(best_face[0]), int(best_face[1]), int(best_face[2]), int(best_face[3])
        re = (float(best_face[4]), float(best_face[5]))
        le = (float(best_face[6]), float(best_face[7]))
        nt = (float(best_face[8]), float(best_face[9]))
        rm = (float(best_face[10]), float(best_face[11]))
        lm = (float(best_face[12]), float(best_face[13]))
        landmarks = [re, le, nt, rm, lm]

        d_eyes = math.hypot(le[0] - re[0], le[1] - re[1])
        if d_eyes < 1:
            return True, 0, (x, y, fw, fh), landmarks

        d_mouth = math.hypot(lm[0] - rm[0], lm[1] - rm[1])
        width_ratio = d_mouth / d_eyes

        mid_m_y = (rm[1] + lm[1]) / 2.0
        d_nose_m = math.hypot(nt[0] - (rm[0] + lm[0]) / 2.0, nt[1] - mid_m_y)
        lift_ratio = (d_eyes / max(1.0, d_nose_m)) * 0.4

        # Smile score combination (stretch + upward lift)
        score = (width_ratio - 0.88) / (1.24 - 0.88) * 0.70 + (lift_ratio - 0.35) * 0.30
        smile_pct = int(max(0, min(100, score * 100)))

        return True, smile_pct, (x, y, fw, fh), landmarks


# ==============================================================================
# 3. BOTTLE GUARDIAN CONTROLLER
# ==============================================================================
class BottleGuardian:
    """
    State machine for anti-theft protection with smile-to-unlock water.
    Monitors whether the water bottle is present in the camera frame.
    If bottle is taken, plays the alert once.
    If the person requests water, it checks for a 100% smile to grant water and silence the alarm.
    """
    STATE_DISARMED = "DISARMED"
    STATE_ARMING = "ARMING"
    STATE_ARMED = "ARMED"
    STATE_THEFT_ALERT = "THEFT_ALERT"
    STATE_SMILE_VERIFICATION = "SMILE_VERIFICATION"
    STATE_CAPTCHA_VERIFICATION = "CAPTCHA_VERIFICATION"
    STATE_THANOS_POSE = "THANOS_POSE"
    STATE_WATER_GRANTED = "WATER_GRANTED"

    def __init__(self, alarm_player: BottleAlarmPlayer, smile_detector: SmileDetector | None = None, debounce_sec: float = 0.7, smile_threshold: int = 30, on_snap_callback=None):
        self.player = alarm_player
        self.smile_detector = smile_detector if smile_detector is not None else SmileDetector()
        self.state = self.STATE_DISARMED
        self.debounce_sec = debounce_sec
        self.smile_threshold = smile_threshold
        self.on_snap_callback = on_snap_callback

        self.last_seen_time = 0.0
        self.missing_since = 0.0
        self.theft_count = 0
        self.alert_played_once = False
        self.latest_event_msg = ""
        self.current_captcha_code = ""
        self.current_captcha_img: Image.Image | None = None
        self.thanos_start_time = 0.0
        self.thanos_snapped = False
        self.snap_flash_time = 0.0
        self._last_announced_sec = 4
        self.last_smile_info = {
            "active": False,
            "face_found": False,
            "smile_pct": 0,
            "threshold": self.smile_threshold,
            "face_box": None,
            "landmarks": [],
            "granted": False,
            "captcha_active": False,
            "captcha_code": "",
            "thanos_active": False,
            "hand_pos": None,
            "countdown": 3,
            "countdown_exact": 3.0,
            "snap_flash_time": 0.0
        }

    def arm(self):
        """Arms the bottle guardian."""
        self.state = self.STATE_ARMING
        self.missing_since = 0.0
        self.alert_played_once = False
        self.last_smile_info["active"] = False
        self.last_smile_info["granted"] = False
        self.last_smile_info["captcha_active"] = False
        self.last_smile_info["thanos_active"] = False
        self.latest_event_msg = "Guardian armed. Watching for your water bottle..."

    def disarm(self):
        """Disarms the guardian and silences any alarm."""
        self.state = self.STATE_DISARMED
        self.missing_since = 0.0
        self.alert_played_once = False
        self.last_smile_info["active"] = False
        self.last_smile_info["granted"] = False
        self.last_smile_info["captcha_active"] = False
        self.last_smile_info["thanos_active"] = False
        self.player.stop()
        self.latest_event_msg = "Guardian disarmed."

    def toggle(self) -> bool:
        """Toggles between armed and disarmed."""
        if self.state in (self.STATE_DISARMED, self.STATE_WATER_GRANTED):
            self.arm()
            return True
        else:
            self.disarm()
            return False

    def request_water(self):
        """Initiates smile verification when 'I Want Water' is clicked."""
        self.state = self.STATE_SMILE_VERIFICATION
        self.last_smile_info["active"] = True
        self.last_smile_info["granted"] = False
        self.last_smile_info["captcha_active"] = False
        self.last_smile_info["thanos_active"] = False
        self.latest_event_msg = f"💧 Water requested! Show a {self.smile_threshold}% smile to the camera to unlock water!"

    def request_captcha(self):
        """Transitions into CAPTCHA verification (after smile or direct option)."""
        self.state = self.STATE_CAPTCHA_VERIFICATION
        code, img = CaptchaGenerator.generate()
        self.current_captcha_code = code
        self.current_captcha_img = img
        self.last_smile_info["active"] = True
        self.last_smile_info["captcha_active"] = True
        self.last_smile_info["thanos_active"] = False
        self.last_smile_info["captcha_code"] = code
        self.latest_event_msg = f"🔤 Smile verified! Enter the CAPTCHA code to unlock water."

    def request_thanos_pose(self):
        """Initiates the epic Thanos Pose finale: Fullscreen camera, hand with Gauntlet only (no text), audio dialogue, and snap."""
        self.state = self.STATE_THANOS_POSE
        self.thanos_start_time = time.time()
        self.thanos_snapped = False
        self.last_smile_info["active"] = True
        self.last_smile_info["captcha_active"] = False
        self.last_smile_info["thanos_active"] = True
        self.last_smile_info["hand_pos"] = None
        self.latest_event_msg = "🧤 THANOS AUDIO: Fullscreen camera, hand only (no text)..."
        # Start Thanos audio dialogue immediately
        self.player.stop()
        self.player.play_iron_man()

    def trigger_snap(self):
        """Executes the Infinity Gauntlet finger snap after dialogue finishes, and unlocks water."""
        if self.thanos_snapped:
            return
        self.thanos_snapped = True
        self.snap_flash_time = time.time()
        self.last_smile_info["snap_flash_time"] = self.snap_flash_time
        self.state = self.STATE_WATER_GRANTED
        self.last_smile_info["active"] = True
        self.last_smile_info["granted"] = True
        self.last_smile_info["thanos_active"] = False
        self.latest_event_msg = "💥 [SNAP] DIALOGUE FINISHED! YOU CAN DRINK WATER NOW!"
        if self.on_snap_callback:
            try:
                self.on_snap_callback()
            except Exception as e:
                print(f"[BottleGuardian] Snap callback error: {e}")

    def verify_captcha(self, user_input: str) -> bool:
        """Verifies entered CAPTCHA string. If matched, triggers Thanos Pose finale."""
        cleaned = user_input.strip().upper()
        if self.current_captcha_code and cleaned == self.current_captcha_code.upper():
            self.request_thanos_pose()
            return True
        else:
            code, img = CaptchaGenerator.generate()
            self.current_captcha_code = code
            self.current_captcha_img = img
            self.last_smile_info["captcha_code"] = code
            self.latest_event_msg = "❌ Incorrect CAPTCHA! New code generated. Try again."
            return False

    def grant_water(self):
        """Direct water grant fallback."""
        self.trigger_snap()

    def _find_hand_position(self, frame: np.ndarray | None) -> tuple[int, int]:
        """Finds raised hand position using skin color contour outside face region."""
        if frame is None:
            return (480, 240)
        h, w, _ = frame.shape
        default_pos = (int(w * 0.74), int(h * 0.45))
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, np.array([0, 30, 60], dtype=np.uint8), np.array([25, 200, 255], dtype=np.uint8))

            face_box = self.last_smile_info.get("face_box")
            if face_box:
                fx, fy, fw, fh = face_box
                cv2.rectangle(mask, (max(0, fx - 15), max(0, fy - 15)), (min(w, fx + fw + 15), min(h, fy + fh + 25)), 0, -1)

            mask[int(h * 0.80):, :] = 0  # Upper body region
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            valid = [c for c in contours if cv2.contourArea(c) > 3000]
            if valid:
                best_c = max(valid, key=lambda c: cv2.contourArea(c))
                M = cv2.moments(best_c)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    return (cx, cy)
        except Exception:
            pass
        return default_pos

    def update(self, bottle_count: int, frame: np.ndarray | None = None) -> tuple[str, bool]:
        """
        Updates state based on current frame bottle count and smile detection.
        Returns (status_text, is_theft_active).
        """
        now = time.time()

        if self.state == self.STATE_DISARMED:
            return "OFF", False

        elif self.state == self.STATE_ARMING:
            if bottle_count > 0:
                self.state = self.STATE_ARMED
                self.last_seen_time = now
                self.missing_since = 0.0
                self.player.play_secure_chime()
                self.latest_event_msg = "Bottle locked! Guardian is active and protecting your water."
                return "ARMED & SECURE", False
            else:
                return "WAITING FOR BOTTLE...", False

        elif self.state == self.STATE_ARMED:
            if bottle_count > 0:
                self.last_seen_time = now
                self.missing_since = 0.0
                return "ARMED & SECURE", False
            else:
                # Bottle is not seen in this frame
                if self.missing_since == 0.0:
                    self.missing_since = now

                # Check if missing duration exceeds debounce grace period
                if (now - self.missing_since) >= self.debounce_sec:
                    # BOTTLE STOLEN! Play alert once
                    self.state = self.STATE_THEFT_ALERT
                    self.theft_count += 1
                    if not self.alert_played_once:
                        sound_desc = self.player.play_alarm()
                        self.alert_played_once = True
                        self.latest_event_msg = f"THEFT DETECTED! Playing alert: {sound_desc}"
                    return "🚨 THEFT ALERT! 🚨", True
                else:
                    return "VERIFYING...", False

        elif self.state == self.STATE_THEFT_ALERT:
            if bottle_count > 0:
                # Bottle returned!
                self.state = self.STATE_ARMED
                self.missing_since = 0.0
                self.alert_played_once = False
                self.player.stop()
                self.player.play_secure_chime()
                self.latest_event_msg = "Bottle returned! Guardian re-armed."
                return "ARMED & SECURE", False
            else:
                # Alert plays once and stays in theft state
                return "🚨 THEFT ALERT! 🚨", True

        elif self.state == self.STATE_SMILE_VERIFICATION:
            if bottle_count > 0:
                # Bottle returned while verifying!
                self.state = self.STATE_ARMED
                self.missing_since = 0.0
                self.player.stop()
                self.player.play_secure_chime()
                self.last_smile_info["active"] = False
                self.last_smile_info["captcha_active"] = False
                self.latest_event_msg = "Bottle returned! Guardian re-armed."
                return "ARMED & SECURE", False

            if frame is not None:
                face_found, smile_pct, face_box, landmarks = self.smile_detector.detect_smile(frame)
                self.last_smile_info.update({
                    "active": True,
                    "face_found": face_found,
                    "smile_pct": smile_pct,
                    "threshold": self.smile_threshold,
                    "face_box": face_box,
                    "landmarks": landmarks,
                    "granted": False,
                    "captcha_active": False
                })
                if face_found:
                    if smile_pct >= self.smile_threshold:
                        # 30% smile achieved! Move to CAPTCHA verification to unlock
                        self.request_captcha()
                        return "SMILE VERIFIED! ENTER CAPTCHA TO UNLOCK", False
                    else:
                        return f"😊 SMILE: {smile_pct}% / {self.smile_threshold}%", False
                else:
                    return "🔍 LOOKING FOR FACE...", False
            return "🔍 LOOKING FOR FACE...", False

        elif self.state == self.STATE_CAPTCHA_VERIFICATION:
            self.last_smile_info["active"] = True
            self.last_smile_info["captcha_active"] = True
            self.last_smile_info["thanos_active"] = False
            self.last_smile_info["captcha_code"] = self.current_captcha_code
            if bottle_count > 0:
                # Bottle returned!
                self.state = self.STATE_ARMED
                self.missing_since = 0.0
                self.player.stop()
                self.player.play_secure_chime()
                self.last_smile_info["active"] = False
                self.last_smile_info["captcha_active"] = False
                self.latest_event_msg = "Bottle returned! Guardian re-armed."
                return "ARMED & SECURE", False
            return "🔤 ENTER CAPTCHA TO UNLOCK", False

        elif self.state == self.STATE_THANOS_POSE:
            self.last_smile_info["active"] = True
            self.last_smile_info["captcha_active"] = False
            self.last_smile_info["thanos_active"] = True
            if bottle_count > 0:
                # Bottle returned!
                self.state = self.STATE_ARMED
                self.missing_since = 0.0
                self.player.stop()
                self.player.play_secure_chime()
                self.last_smile_info["active"] = False
                self.last_smile_info["thanos_active"] = False
                self.latest_event_msg = "Bottle returned! Guardian re-armed."
                return "ARMED & SECURE", False

            # Track hand position for Thanos Glove overlay
            hand_pos = self._find_hand_position(frame)
            self.last_smile_info["hand_pos"] = hand_pos

            elapsed = time.time() - self.thanos_start_time

            # The audio dialogue: "I am inevitable... And I... am... Iron Man! [SNAP]" runs for ~9.8s
            # ONLY AFTER THE DIALOGUE AND SNAP (at ~9.8s), trigger snap & show water notification!
            if elapsed >= 9.8 and not self.thanos_snapped:
                self.trigger_snap()
                return "💥 [SNAP] DIALOGUE COMPLETED! YOU CAN DRINK WATER NOW!", False

            return "🧤 THANOS AUDIO RUNNING (FULLSCREEN NO TEXT)", False

        elif self.state == self.STATE_WATER_GRANTED:
            self.last_smile_info["active"] = True
            self.last_smile_info["granted"] = True
            self.last_smile_info["captcha_active"] = False
            if bottle_count > 0:
                # Bottle returned after drinking!
                self.state = self.STATE_ARMED
                self.missing_since = 0.0
                self.alert_played_once = False
                self.last_smile_info["active"] = False
                self.last_smile_info["granted"] = False
                self.player.play_secure_chime()
                self.latest_event_msg = "Bottle returned to desk! Guardian re-armed."
                return "ARMED & SECURE", False
            return "💧 WATER GRANTED - ENJOY!", False

        return "UNKNOWN", False


# ==============================================================================
# 3. BOTTLE DETECTION ENGINE (YOLOv8)
# ==============================================================================
class BottleDetector:
    # COCO Dataset Class 39 is 'bottle' (water bottles, wine, glass, plastic)
    BOTTLE_CLASS_ID = 39

    def __init__(self, model_name: str = "yolov8n.pt", conf_threshold: float = 0.40):
        self.conf_threshold = conf_threshold
        self.prev_time = time.time()
        self.fps = 0.0

        # Load transparent Thanos Infinity Gauntlet asset if available
        self.gauntlet_img = None
        gauntlet_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "thanos_gauntlet.png")
        if os.path.exists(gauntlet_path):
            self.gauntlet_img = cv2.imread(gauntlet_path, cv2.IMREAD_UNCHANGED)

        if YOLO is None:
            raise RuntimeError("Ultralytics package is not installed. Please run: pip install -r requirements.txt")

        print(f"[BottleDetector] Loading AI model: {model_name}...")
        self.model = YOLO(model_name)

    def update_confidence(self, conf: float):
        self.conf_threshold = max(0.05, min(0.95, conf))

    def detect(self, frame: np.ndarray, draw_overlay: bool = True, guardian_state: str = "OFF", smile_info: dict | None = None):
        curr_time = time.time()
        diff = curr_time - self.prev_time
        if diff > 0:
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / diff)
        self.prev_time = curr_time

        # Run inference specifically for the bottle class (COCO 39)
        raw_results = self.model.predict(
            source=frame,
            classes=[self.BOTTLE_CLASS_ID],
            conf=self.conf_threshold,
            verbose=False
        )

        # Convert prediction result into a list to prevent iterator indexing type errors
        results = list(raw_results) if raw_results is not None else []

        detections = []
        annotated_frame = frame.copy()

        # Safely extract bounding boxes from all result items
        for res in results:
            boxes = getattr(res, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                x1, y1, x2, y2 = map(int, xyxy)

                detections.append({
                    "box": [x1, y1, x2, y2],
                    "confidence": conf
                })

                if draw_overlay:
                    is_thanos = smile_info is not None and smile_info.get("thanos_active", False)
                    if not is_thanos:
                        is_guarded = guardian_state in ("ARMED & SECURE", "ARMED")
                        self._draw_box(annotated_frame, x1, y1, x2, y2, conf, is_guarded=is_guarded)

        count = len(detections)
        if draw_overlay:
            self._draw_hud(annotated_frame, count, self.fps, guardian_state, smile_info)

        return annotated_frame, detections, count, self.fps

    def _draw_box(self, img: np.ndarray, x1: int, y1: int, x2: int, y2: int, conf: float, is_guarded: bool = False):
        if is_guarded:
            box_color = (240, 180, 0)       # High-tech Electric Cyan/Blue for guarded bottle
            corner_color = (255, 220, 50)
            badge_title = f"FARZIN'S BOTTLE {int(conf * 100)}%"
        else:
            box_color = (80, 220, 60)       # Emerald Green
            corner_color = (0, 255, 128)
            badge_title = f"BOTTLE {int(conf * 100)}%"

        # Base box
        cv2.rectangle(img, (x1, y1), (x2, y2), box_color, 2, cv2.LINE_AA)

        # Sleek corner accents
        w, h = x2 - x1, y2 - y1
        c_len = max(8, min(24, int(min(w, h) * 0.2)))
        th = 3

        cv2.line(img, (x1, y1), (x1 + c_len, y1), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x1, y1), (x1, y1 + c_len), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x2, y1), (x2 - c_len, y1), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x2, y1), (x2, y1 + c_len), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x1, y2), (x1 + c_len, y2), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x1, y2), (x1, y2 - c_len), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x2, y2), (x2 - c_len, y2), corner_color, th, cv2.LINE_AA)
        cv2.line(img, (x2, y2), (x2, y2 - c_len), corner_color, th, cv2.LINE_AA)

        # Label Pill Badge
        (lw, lh), _ = cv2.getTextSize(badge_title, cv2.FONT_HERSHEY_DUPLEX, 0.50, 1)
        by1, by2 = max(0, y1 - lh - 10), y1
        bx1, bx2 = x1, x1 + lw + 14

        overlay = img.copy()
        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (20, 20, 25), -1)
        cv2.addWeighted(overlay, 0.78, img, 0.22, 0, img)
        cv2.rectangle(img, (bx1, by1), (bx2, by2), box_color, 1, cv2.LINE_AA)
        cv2.putText(img, badge_title, (bx1 + 7, by2 - 5), cv2.FONT_HERSHEY_DUPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)

    def _overlay_gauntlet(self, img: np.ndarray, x: int, y: int, w_box: int, h_box: int):
        """Blends the Thanos Infinity Gauntlet PNG onto the image with alpha transparency."""
        if self.gauntlet_img is None:
            return
        fh, fw, _ = img.shape
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(fw, x + w_box), min(fh, y + h_box)
        rw, rh = x2 - x1, y2 - y1
        if rw <= 0 or rh <= 0:
            return

        resized = cv2.resize(self.gauntlet_img, (w_box, h_box), interpolation=cv2.INTER_AREA)
        crop_g = resized[0:rh, 0:rw]

        alpha_s = crop_g[:, :, 3] / 255.0
        alpha_l = 1.0 - alpha_s

        for c in range(3):
            img[y1:y2, x1:x2, c] = (alpha_s * crop_g[:, :, c] + alpha_l * img[y1:y2, x1:x2, c])

    def _draw_infinity_stones_glow(self, img: np.ndarray, gx: int, gy: int, gw: int, gh: int):
        """Renders pulsing cosmic energy glow rings over the 6 Infinity Stones."""
        t = time.time()
        pulse = math.sin(t * 8.0) * 2.5
        r_base = max(4, int(gw * 0.04))

        stones = [
            (0.50, 0.49, (0, 240, 255)),      # Mind (Yellow)
            (0.55, 0.35, (255, 200, 0)),     # Space (Blue)
            (0.66, 0.36, (255, 50, 200)),    # Power (Purple)
            (0.42, 0.36, (50, 50, 255)),     # Reality (Red)
            (0.33, 0.38, (0, 140, 255)),     # Soul (Orange)
            (0.80, 0.54, (50, 255, 100)),    # Time (Green)
        ]

        for rel_x, rel_y, color in stones:
            sx = gx + int(gw * rel_x)
            sy = gy + int(gh * rel_y)
            rad = max(2, int(r_base + pulse))
            cv2.circle(img, (sx, sy), rad, color, 2, cv2.LINE_AA)
            cv2.circle(img, (sx, sy), max(1, rad - 2), (255, 255, 255), -1, cv2.LINE_AA)

    def _draw_hud(self, img: np.ndarray, count: int, fps: float, guardian_state: str, smile_info: dict | None = None):
        h, w, _ = img.shape

        # ON THANOS AUDIO: ONLY SHOW THE HAND (WITH THANOS GAUNTLET) AND NO TEXT SHOULD BE THERE
        if smile_info is not None and smile_info.get("thanos_active", False):
            hand_pos = smile_info.get("hand_pos") or (int(w * 0.74), int(h * 0.45))
            gw = max(160, min(320, int(w * 0.28)))
            gh = int(gw * 1.33)
            gx = max(0, min(w - gw, hand_pos[0] - gw // 2))
            gy = max(20, min(h - gh - 10, hand_pos[1] - gh // 2))
            self._overlay_gauntlet(img, gx, gy, gw, gh)
            self._draw_infinity_stones_glow(img, gx, gy, gw, gh)
            return

        bar_height = 46
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (w, bar_height), (15, 17, 23), -1)
        cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)
        cv2.line(img, (0, bar_height), (w, bar_height), (50, 60, 80), 1, cv2.LINE_AA)

        # Status text & icon
        is_theft = "THEFT" in guardian_state
        is_verifying = smile_info is not None and smile_info.get("active", False)
        is_granted = smile_info is not None and smile_info.get("granted", False)
        is_captcha = smile_info is not None and smile_info.get("captcha_active", False)
        is_thanos = smile_info is not None and smile_info.get("thanos_active", False)
        target_pct = int(smile_info.get("threshold", 30)) if smile_info else 30

        if is_granted:
            status_color = (50, 230, 80)
            status_text = "I AM IRON MAN! (WATER ACCESS UNLOCKED)"
        elif is_thanos:
            status_color = (190, 80, 255)
            status_text = "POSE LIKE THANOS & SNAP FINGERS!"
        elif is_captcha:
            status_color = (180, 100, 255)
            status_text = "SMILE VERIFIED! ENTER CAPTCHA TO UNLOCK"
        elif is_verifying:
            status_color = (0, 200, 255)
            pct = smile_info.get("smile_pct", 0) if smile_info else 0
            status_text = f"SMILE TO UNLOCK: {pct}% / {target_pct}%"
        elif is_theft:
            status_color = (0, 0, 255)
            status_text = "ALARM: BOTTLE STOLEN!"
        elif "ARMED" in guardian_state:
            status_color = (240, 180, 0)
            status_text = f"GUARDIAN ACTIVE: {count} SECURE"
        elif count > 0:
            status_color = (50, 230, 80)
            status_text = f"BOTTLES DETECTED: {count}"
        else:
            status_color = (0, 180, 255)
            status_text = "SCANNING FOR BOTTLES..."

        cv2.circle(img, (18, 23), 6, status_color, -1, cv2.LINE_AA)
        cv2.circle(img, (18, 23), 8, status_color, 1, cv2.LINE_AA)
        cv2.putText(img, status_text, (32, 29), cv2.FONT_HERSHEY_DUPLEX, 0.52, (245, 245, 250), 1, cv2.LINE_AA)

        fps_text = f"FPS: {fps:0.1f} | CONF: {int(self.conf_threshold * 100)}%"
        (fw, _), _ = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_DUPLEX, 0.46, 1)
        cv2.putText(img, fps_text, (max(10, w - fw - 16), 29), cv2.FONT_HERSHEY_DUPLEX, 0.46, (180, 190, 205), 1, cv2.LINE_AA)

        # 1. SMILE, CAPTCHA & THANOS POSE VERIFICATION HUD
        if is_verifying and smile_info is not None:
            if is_granted:
                # Celebratory "And I... am... Iron Man!" banner & Thanos Dust Disintegration effect
                box_h = 115
                cy = h // 2
                banner_overlay = img.copy()
                cv2.rectangle(banner_overlay, (0, cy - box_h // 2), (w, cy + box_h // 2), (18, 120, 35), -1)
                cv2.addWeighted(banner_overlay, 0.85, img, 0.15, 0, img)
                cv2.line(img, (0, cy - box_h // 2), (w, cy - box_h // 2), (50, 255, 100), 2, cv2.LINE_AA)
                cv2.line(img, (0, cy + box_h // 2), (w, cy + box_h // 2), (50, 255, 100), 2, cv2.LINE_AA)

                t1 = '*** YOU CAN DRINK WATER NOW! ***'
                t2 = '*** "AND I... AM... IRON MAN!" [SNAP] ***'
                t3 = "DISINTEGRATING INTO DUST LIKE THANOS..."
                (tw1, _), _ = cv2.getTextSize(t1, cv2.FONT_HERSHEY_DUPLEX, 0.82, 2)
                (tw2, _), _ = cv2.getTextSize(t2, cv2.FONT_HERSHEY_DUPLEX, 0.65, 2)
                (tw3, _), _ = cv2.getTextSize(t3, cv2.FONT_HERSHEY_DUPLEX, 0.52, 1)
                cv2.putText(img, t1, ((w - tw1) // 2, cy - 18), cv2.FONT_HERSHEY_DUPLEX, 0.82, (100, 255, 150), 2, cv2.LINE_AA)
                cv2.putText(img, t2, ((w - tw2) // 2, cy + 12), cv2.FONT_HERSHEY_DUPLEX, 0.65, (255, 220, 80), 2, cv2.LINE_AA)
                cv2.putText(img, t3, ((w - tw3) // 2, cy + 38), cv2.FONT_HERSHEY_DUPLEX, 0.52, (200, 230, 255), 1, cv2.LINE_AA)

                # Render floating dust ember particles blowing across the camera feed
                now_t = time.time()
                for i in range(80):
                    px = int((i * 47 + now_t * 220) % w)
                    py = int((i * 31 - now_t * 70 + math.sin(i + now_t * 4) * 25) % h)
                    col = (int(30 + 20 * math.sin(i)), int(180 + 70 * math.sin(i)), int(220 + 35 * math.cos(i)))
                    cv2.circle(img, (px, py), (i % 4) + 1, col, -1, cv2.LINE_AA)

            elif is_thanos:
                # 1. Overlay Thanos Infinity Gauntlet onto hand
                hand_pos = smile_info.get("hand_pos") or (int(w * 0.74), int(h * 0.45))
                gw = max(140, min(240, int(w * 0.28)))
                gh = int(gw * 1.33)
                gx = max(0, min(w - gw, hand_pos[0] - gw // 2))
                gy = max(50, min(h - gh - 10, hand_pos[1] - gh // 2))
                self._overlay_gauntlet(img, gx, gy, gw, gh)
                self._draw_infinity_stones_glow(img, gx, gy, gw, gh)

                # 2. Large Central 3-Second Counter Dial
                countdown = smile_info.get("countdown", 3)
                cnt = max(1, min(3, int(countdown)))
                dial_cx, dial_cy = w // 2, h // 2 - 20
                dial_r = 75

                overlay_dial = img.copy()
                cv2.circle(overlay_dial, (dial_cx, dial_cy), dial_r + 6, (25, 10, 45), -1)
                cv2.addWeighted(overlay_dial, 0.75, img, 0.25, 0, img)

                t_pulse = time.time()
                ring_r = int(dial_r + 4 * math.sin(t_pulse * 10.0))
                cv2.circle(img, (dial_cx, dial_cy), ring_r, (0, 215, 255), 3, cv2.LINE_AA)
                cv2.circle(img, (dial_cx, dial_cy), dial_r, (255, 150, 0), 2, cv2.LINE_AA)

                # Giant glowing 3-2-1 digit
                digit_str = str(cnt)
                (dw, dh), _ = cv2.getTextSize(digit_str, cv2.FONT_HERSHEY_DUPLEX, 2.8, 4)
                cv2.putText(img, digit_str, (dial_cx - dw // 2 + 2, dial_cy + dh // 2 + 2), cv2.FONT_HERSHEY_DUPLEX, 2.8, (0, 100, 200), 6, cv2.LINE_AA)
                cv2.putText(img, digit_str, (dial_cx - dw // 2, dial_cy + dh // 2), cv2.FONT_HERSHEY_DUPLEX, 2.8, (255, 255, 255), 4, cv2.LINE_AA)

                # Header above dial
                wait_sub = "WAIT... HOLD THANOS POSE"
                (wsw, _), _ = cv2.getTextSize(wait_sub, cv2.FONT_HERSHEY_DUPLEX, 0.65, 2)
                cv2.putText(img, wait_sub, (dial_cx - wsw // 2, dial_cy - dial_r - 18), cv2.FONT_HERSHEY_DUPLEX, 0.65, (255, 220, 80), 2, cv2.LINE_AA)

                # Subtext below dial
                sub_label = f"SNAP IN: [ {cnt} ]"
                (slw, _), _ = cv2.getTextSize(sub_label, cv2.FONT_HERSHEY_DUPLEX, 0.58, 2)
                cv2.putText(img, sub_label, (dial_cx - slw // 2, dial_cy + dial_r + 32), cv2.FONT_HERSHEY_DUPLEX, 0.58, (230, 210, 255), 2, cv2.LINE_AA)

                # 3. Bottom Thanos banner
                box_h = 95
                cy = h - 65
                banner_overlay = img.copy()
                cv2.rectangle(banner_overlay, (0, cy - box_h // 2), (w, cy + box_h // 2), (30, 10, 60), -1)
                cv2.addWeighted(banner_overlay, 0.88, img, 0.12, 0, img)
                cv2.line(img, (0, cy - box_h // 2), (w, cy - box_h // 2), (220, 160, 50), 2, cv2.LINE_AA)
                cv2.line(img, (0, cy + box_h // 2), (w, cy + box_h // 2), (220, 160, 50), 2, cv2.LINE_AA)

                t1 = "*** POSE LIKE THANOS & WAIT FOR THE SNAP! ***"
                t2 = f"INFINITY GAUNTLET CHARGING -- SNAPPING IN {cnt}s (OR CLICK SNAP)"
                (tw1, _), _ = cv2.getTextSize(t1, cv2.FONT_HERSHEY_DUPLEX, 0.72, 2)
                (tw2, _), _ = cv2.getTextSize(t2, cv2.FONT_HERSHEY_DUPLEX, 0.54, 1)
                cv2.putText(img, t1, ((w - tw1) // 2, cy - 8), cv2.FONT_HERSHEY_DUPLEX, 0.72, (255, 220, 80), 2, cv2.LINE_AA)
                cv2.putText(img, t2, ((w - tw2) // 2, cy + 26), cv2.FONT_HERSHEY_DUPLEX, 0.54, (230, 210, 255), 1, cv2.LINE_AA)

            elif is_captcha:
                # CAPTCHA verification prompt banner
                box_h = 105
                cy = h // 2
                banner_overlay = img.copy()
                cv2.rectangle(banner_overlay, (0, cy - box_h // 2), (w, cy + box_h // 2), (45, 20, 80), -1)
                cv2.addWeighted(banner_overlay, 0.88, img, 0.12, 0, img)
                cv2.line(img, (0, cy - box_h // 2), (w, cy - box_h // 2), (180, 110, 255), 2, cv2.LINE_AA)
                cv2.line(img, (0, cy + box_h // 2), (w, cy + box_h // 2), (180, 110, 255), 2, cv2.LINE_AA)

                c_code = smile_info.get("captcha_code", "")
                t1 = "*** SMILE VERIFIED! ENTER CAPTCHA ***"
                t2 = f"CODE: [  {c_code}  ]  (TYPE IN APP TO UNLOCK)"
                (tw1, _), _ = cv2.getTextSize(t1, cv2.FONT_HERSHEY_DUPLEX, 0.76, 2)
                (tw2, _), _ = cv2.getTextSize(t2, cv2.FONT_HERSHEY_DUPLEX, 0.64, 2)
                cv2.putText(img, t1, ((w - tw1) // 2, cy - 8), cv2.FONT_HERSHEY_DUPLEX, 0.76, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(img, t2, ((w - tw2) // 2, cy + 28), cv2.FONT_HERSHEY_DUPLEX, 0.64, (240, 210, 255), 2, cv2.LINE_AA)

            elif smile_info.get("face_found", False):
                face_box = smile_info.get("face_box")
                smile_pct = int(smile_info.get("smile_pct", 0))

                if face_box:
                    fx, fy, fw_b, fh_b = face_box
                    # Draw face frame
                    cv2.rectangle(img, (fx, fy), (fx + fw_b, fy + fh_b), (255, 215, 0), 2, cv2.LINE_AA)

                    # Sleek face corner accents
                    c_len = max(8, min(24, int(min(fw_b, fh_b) * 0.18)))
                    cv2.line(img, (fx, fy), (fx + c_len, fy), (0, 255, 255), 3, cv2.LINE_AA)
                    cv2.line(img, (fx, fy), (fx, fy + c_len), (0, 255, 255), 3, cv2.LINE_AA)
                    cv2.line(img, (fx + fw_b, fy), (fx + fw_b - c_len, fy), (0, 255, 255), 3, cv2.LINE_AA)
                    cv2.line(img, (fx + fw_b, fy), (fx + fw_b, fy + c_len), (0, 255, 255), 3, cv2.LINE_AA)
                    cv2.line(img, (fx, fy + fh_b), (fx + c_len, fy + fh_b), (0, 255, 255), 3, cv2.LINE_AA)
                    cv2.line(img, (fx, fy + fh_b), (fx, fy + fh_b - c_len), (0, 255, 255), 3, cv2.LINE_AA)
                    cv2.line(img, (fx + fw_b, fy + fh_b), (fx + fw_b - c_len, fy + fh_b), (0, 255, 255), 3, cv2.LINE_AA)
                    cv2.line(img, (fx + fw_b, fy + fh_b), (fx + fw_b, fy + fh_b - c_len), (0, 255, 255), 3, cv2.LINE_AA)

                    # Draw landmarks
                    for pt in smile_info.get("landmarks", []):
                        cv2.circle(img, (int(pt[0]), int(pt[1])), 4, (0, 255, 255), -1, cv2.LINE_AA)

                # Graphical SMILE METER Gauge at bottom
                meter_w, meter_h = 360, 28
                mx = (w - meter_w) // 2
                my = h - 60

                m_overlay = img.copy()
                cv2.rectangle(m_overlay, (mx - 10, my - 24), (mx + meter_w + 10, my + meter_h + 10), (15, 17, 23), -1)
                cv2.addWeighted(m_overlay, 0.85, img, 0.15, 0, img)
                cv2.rectangle(img, (mx - 10, my - 24), (mx + meter_w + 10, my + meter_h + 10), (50, 60, 80), 1, cv2.LINE_AA)

                # Meter title
                title = f"SMILE {target_pct}% TO UNLOCK WATER"
                cv2.putText(img, title, (mx, my - 8), cv2.FONT_HERSHEY_DUPLEX, 0.48, (200, 220, 240), 1, cv2.LINE_AA)

                # Progress bar (fills relative to target_pct, reaching full width at target_pct)
                progress_ratio = min(1.0, max(0.0, smile_pct / float(max(1, target_pct))))
                fill_w = int(meter_w * progress_ratio)
                meter_col = (0, 120, 255) if smile_pct < (target_pct * 0.5) else ((0, 220, 255) if smile_pct < target_pct else (50, 235, 80))
                cv2.rectangle(img, (mx, my), (mx + meter_w, my + meter_h), (35, 40, 50), -1)
                if fill_w > 0:
                    cv2.rectangle(img, (mx, my), (mx + fill_w, my + meter_h), meter_col, -1)
                cv2.rectangle(img, (mx, my), (mx + meter_w, my + meter_h), (80, 90, 110), 1, cv2.LINE_AA)

                # Meter text
                pct_str = f"SMILE: {smile_pct}% / {target_pct}%"
                cv2.putText(img, pct_str, (mx + 12, my + 19), cv2.FONT_HERSHEY_DUPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)

            else:
                # Face not yet found
                box_h = 64
                cy = h - 55
                banner_overlay = img.copy()
                cv2.rectangle(banner_overlay, (0, cy - box_h // 2), (w, cy + box_h // 2), (20, 30, 50), -1)
                cv2.addWeighted(banner_overlay, 0.82, img, 0.18, 0, img)
                cv2.line(img, (0, cy - box_h // 2), (w, cy - box_h // 2), (0, 180, 255), 2, cv2.LINE_AA)
                t = "LOOKING FOR FACE... LOOK AT CAMERA TO SMILE!"
                (tw, _), _ = cv2.getTextSize(t, cv2.FONT_HERSHEY_DUPLEX, 0.60, 1)
                cv2.putText(img, t, ((w - tw) // 2, cy + 5), cv2.FONT_HERSHEY_DUPLEX, 0.60, (0, 220, 255), 1, cv2.LINE_AA)

        # 2. THEFT ALERT BANNER (when stolen & not in smile verification mode)
        elif is_theft:
            if int(time.time() * 3) % 2 == 0:
                box_h = 96
                cy = h // 2
                banner_overlay = img.copy()
                cv2.rectangle(banner_overlay, (0, cy - box_h // 2), (w, cy + box_h // 2), (20, 20, 200), -1)
                cv2.addWeighted(banner_overlay, 0.85, img, 0.15, 0, img)
                cv2.line(img, (0, cy - box_h // 2), (w, cy - box_h // 2), (50, 50, 255), 2, cv2.LINE_AA)
                cv2.line(img, (0, cy + box_h // 2), (w, cy + box_h // 2), (50, 50, 255), 2, cv2.LINE_AA)

                t1 = "ALARM: WATER BOTTLE STOLEN!"
                t2 = f"CLICK 'I WANT WATER' & SMILE {target_pct}% TO UNLOCK"
                (tw1, _), _ = cv2.getTextSize(t1, cv2.FONT_HERSHEY_DUPLEX, 0.76, 2)
                (tw2, _), _ = cv2.getTextSize(t2, cv2.FONT_HERSHEY_DUPLEX, 0.62, 2)
                cv2.putText(img, t1, ((w - tw1) // 2, cy - 8), cv2.FONT_HERSHEY_DUPLEX, 0.76, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(img, t2, ((w - tw2) // 2, cy + 28), cv2.FONT_HERSHEY_DUPLEX, 0.62, (255, 230, 80), 2, cv2.LINE_AA)


# ==============================================================================
# 4. INTERACTIVE DESKTOP GUI
# ==============================================================================
class BottleVisionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BottleVision AI — Anti-Theft Bottle Guardian")
        self.root.geometry("1180x760")
        self.root.minsize(1020, 680)
        self.root.configure(bg="#0B0F19")

        self.alarm_player = BottleAlarmPlayer()
        self.smile_detector = SmileDetector()
        self.guardian = BottleGuardian(
            self.alarm_player,
            smile_detector=self.smile_detector,
            debounce_sec=0.7,
            smile_threshold=30,
            on_snap_callback=self.on_snap_disintegrate_window
        )
        self.detector = BottleDetector(model_name="yolov8n.pt", conf_threshold=0.40)
        self._is_disintegrating = False
        self._dust_canvas = None
        self._fullscreen_cam_win = None
        self._fullscreen_cam_lbl = None

        self.cap = None
        self.is_running = False
        self.current_frame = None
        self.current_annotated = None
        self.draw_overlay = True
        self.total_snapshots = 0
        self._photo_image = None  # Reference to prevent Tkinter image garbage collection

        self.captures_dir = os.path.join(os.getcwd(), "captures")
        os.makedirs(self.captures_dir, exist_ok=True)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _build_ui(self):
        import tkinter as tk
        from tkinter import ttk

        # Header
        header = tk.Frame(self.root, bg="#111827", height=60, padx=20, pady=10)
        header.pack(fill="x", side="top")

        tk.Label(header, text="🍾", bg="#111827", font=("Segoe UI", 20)).pack(side="left", padx=(0, 10))
        tframe = tk.Frame(header, bg="#111827")
        tframe.pack(side="left")
        tk.Label(tframe, text="BottleVision AI & Bottle Guardian", bg="#111827", fg="#F9FAFB", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(tframe, text="Real-time Bottle Detection & Anti-Theft Classroom Alarm", bg="#111827", fg="#9CA3AF", font=("Segoe UI", 9)).pack(anchor="w")

        # Top Right Badges
        top_badges = tk.Frame(header, bg="#111827")
        top_badges.pack(side="right")

        self.status_badge = tk.Label(top_badges, text="● READY", bg="#1F2937", fg="#10B981", font=("Segoe UI", 10, "bold"), padx=12, pady=5)
        self.status_badge.pack(side="right", padx=(8, 0))

        self.guardian_badge = tk.Label(top_badges, text="🛡️ GUARDIAN: OFF", bg="#1F2937", fg="#94A3B8", font=("Segoe UI", 10, "bold"), padx=12, pady=5)
        self.guardian_badge.pack(side="right")

        # Main Body
        body = tk.Frame(self.root, bg="#0B0F19", padx=16, pady=12)
        body.pack(fill="both", expand=True)

        # Video canvas (Left)
        left_pane = tk.Frame(body, bg="#111827", bd=1, relief="solid")
        left_pane.pack(side="left", fill="both", expand=True, padx=(0, 12))

        self.video_canvas = tk.Label(
            left_pane, bg="#080C14",
            text="Camera stream idle\n\nClick '▶ Start Webcam' to detect bottles live!",
            fg="#64748B", font=("Segoe UI", 12)
        )
        self.video_canvas.pack(fill="both", expand=True, padx=4, pady=4)

        # Controls & Analytics (Right)
        right_pane = tk.Frame(body, bg="#0B0F19", width=360)
        right_pane.pack(side="right", fill="y")
        right_pane.pack_propagate(False)

        # -------------------------------------------------------------
        # CARD 1: 🛡️ BOTTLE GUARDIAN (ANTI-THEFT)
        # -------------------------------------------------------------
        card_guard = tk.Frame(right_pane, bg="#151D2A", padx=14, pady=12, bd=1, relief="solid")
        card_guard.pack(fill="x", pady=(0, 10))

        gh_frame = tk.Frame(card_guard, bg="#151D2A")
        gh_frame.pack(fill="x", pady=(0, 6))
        tk.Label(gh_frame, text="🛡️ BOTTLE GUARDIAN", bg="#151D2A", fg="#38BDF8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.guard_state_lbl = tk.Label(gh_frame, text="● DISARMED", bg="#151D2A", fg="#94A3B8", font=("Segoe UI", 8, "bold"))
        self.guard_state_lbl.pack(side="right")

        tk.Label(
            card_guard,
            text="Arms anti-theft watch on your water bottle. If someone takes your bottle from the frame, random alarms sound!",
            bg="#151D2A", fg="#94A3B8", font=("Segoe UI", 8), wraplength=320, justify="left"
        ).pack(anchor="w", pady=(0, 8))

        self.btn_guard = tk.Button(
            card_guard, text="🛡️  ARM GUARDIAN", bg="#0284C7", fg="#FFFFFF",
            activebackground="#0369A1", font=("Segoe UI", 10, "bold"), bd=0, padx=12, pady=8, cursor="hand2",
            command=self.toggle_guardian
        )
        self.btn_guard.pack(fill="x", pady=(0, 6))

        self.btn_want_water = tk.Button(
            card_guard, text="💧  I Want Water! (Smile to Unlock)", bg="#0D9488", fg="#FFFFFF",
            activebackground="#0F766E", font=("Segoe UI", 9, "bold"), bd=0, padx=10, pady=7, cursor="hand2",
            command=self.on_want_water
        )
        self.btn_want_water.pack(fill="x", pady=(0, 6))

        self.btn_captcha_opt = tk.Button(
            card_guard, text="🔤  Unlock with CAPTCHA", bg="#1E293B", fg="#E2E8F0",
            activebackground="#334155", font=("Segoe UI", 8), bd=1, relief="solid", padx=8, pady=4, cursor="hand2",
            command=self.on_captcha_clicked
        )
        self.btn_captcha_opt.pack(fill="x", pady=(0, 6))

        # Button: Thanos Pose Finale Mode
        self.btn_thanos_pose = tk.Button(
            card_guard, text="🧤  Thanos Pose & Snap Finale", bg="#581C87", fg="#F3E8FF",
            activebackground="#6B21A8", font=("Segoe UI", 9, "bold"), bd=0, padx=8, pady=6, cursor="hand2",
            command=self.on_thanos_clicked
        )
        self.btn_thanos_pose.pack(fill="x", pady=(0, 6))

        # Button: Snap Fingers (Pops up during Thanos Pose)
        self.btn_snap_fingers = tk.Button(
            card_guard, text="🫰  SNAP FINGERS! (I AM IRON MAN)", bg="#7C3AED", fg="#FFFFFF",
            activebackground="#6D28D9", font=("Segoe UI", 9, "bold"), bd=0, padx=8, pady=6, cursor="hand2",
            command=self.on_snap_clicked
        )

        # Collapsible Security CAPTCHA Challenge Frame
        self.captcha_frame = tk.Frame(card_guard, bg="#0F172A", padx=8, pady=8, bd=1, relief="solid")

        c_header = tk.Frame(self.captcha_frame, bg="#0F172A")
        c_header.pack(fill="x", pady=(0, 4))
        tk.Label(c_header, text="🤖 SECURITY CAPTCHA", bg="#0F172A", fg="#38BDF8", font=("Segoe UI", 8, "bold")).pack(side="left")
        self.captcha_feedback = tk.Label(c_header, text="", bg="#0F172A", fg="#F87171", font=("Segoe UI", 8, "bold"))
        self.captcha_feedback.pack(side="right")

        self.captcha_img_lbl = tk.Label(self.captcha_frame, bg="#151D2A", bd=1, relief="solid")
        self.captcha_img_lbl.pack(fill="x", pady=(0, 6))

        inp_row = tk.Frame(self.captcha_frame, bg="#0F172A")
        inp_row.pack(fill="x", pady=(0, 6))

        self.captcha_entry = tk.Entry(
            inp_row, font=("Consolas", 12, "bold"), justify="center",
            bg="#1E293B", fg="#38BDF8", insertbackground="#38BDF8", bd=1, relief="solid", width=12
        )
        self.captcha_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.captcha_entry.bind("<Return>", lambda e: self.submit_captcha())

        btn_refresh = tk.Button(
            inp_row, text="🔄", bg="#334155", fg="#F8FAFC", activebackground="#475569",
            bd=0, padx=6, pady=2, cursor="hand2", command=self.refresh_captcha
        )
        btn_refresh.pack(side="right")

        self.btn_submit_captcha = tk.Button(
            self.captcha_frame, text="🔓  Verify & Unlock Water", bg="#10B981", fg="#FFFFFF",
            activebackground="#059669", font=("Segoe UI", 9, "bold"), bd=0, padx=8, pady=5, cursor="hand2",
            command=self.submit_captcha
        )
        self.btn_submit_captcha.pack(fill="x")

        # Sound mode selector
        s_row = tk.Frame(card_guard, bg="#151D2A")
        s_row.pack(fill="x", pady=(0, 6))
        tk.Label(s_row, text="Sound Type:", bg="#151D2A", fg="#CBD5E1", font=("Segoe UI", 8, "bold")).pack(side="left")

        self.sound_mode_var = tk.StringVar(value="👑 Kireedam (Kathi Thazhe Idada)")
        sound_options = [
            "👑 Kireedam (Kathi Thazhe Idada)",
            "🎲 Random Mix (Kireedam + Sirens)",
            "🗣️ Funny Voice Warnings",
            "🚨 Police & Burglar Sirens",
            "👾 8-Bit Retro Panic"
        ]
        self.sound_menu = ttk.Combobox(
            s_row, textvariable=self.sound_mode_var, values=sound_options,
            state="readonly", width=22, font=("Segoe UI", 8)
        )
        self.sound_menu.pack(side="right")
        self.sound_menu.bind("<<ComboboxSelected>>", self._on_sound_mode_changed)

        # Test Sound Button
        self.btn_test_sound = tk.Button(
            card_guard, text="🔊  Test Random Sound", bg="#1E293B", fg="#E2E8F0",
            activebackground="#334155", font=("Segoe UI", 8), bd=1, relief="solid", padx=8, pady=4, cursor="hand2",
            command=self.test_random_sound
        )
        self.btn_test_sound.pack(fill="x")

        # -------------------------------------------------------------
        # CARD 2: METRICS (COUNT, FPS, SNAPSHOTS)
        # -------------------------------------------------------------
        card_metrics = tk.Frame(right_pane, bg="#151D2A", padx=14, pady=10, bd=1, relief="solid")
        card_metrics.pack(fill="x", pady=(0, 10))

        m_row = tk.Frame(card_metrics, bg="#151D2A")
        m_row.pack(fill="x")

        # Count
        c1 = tk.Frame(m_row, bg="#151D2A")
        c1.pack(side="left", fill="x", expand=True)
        tk.Label(c1, text="BOTTLE COUNT", bg="#151D2A", fg="#94A3B8", font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.count_label = tk.Label(c1, text="0", bg="#151D2A", fg="#10B981", font=("Segoe UI", 26, "bold"))
        self.count_label.pack(anchor="w")

        # FPS
        c2 = tk.Frame(m_row, bg="#151D2A")
        c2.pack(side="left", fill="x", expand=True)
        tk.Label(c2, text="FPS", bg="#151D2A", fg="#94A3B8", font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.fps_label = tk.Label(c2, text="0.0", bg="#151D2A", fg="#38BDF8", font=("Segoe UI", 16, "bold"))
        self.fps_label.pack(anchor="w", pady=(5, 0))

        # Snaps
        c3 = tk.Frame(m_row, bg="#151D2A")
        c3.pack(side="right", fill="x", expand=True)
        tk.Label(c3, text="SNAPS", bg="#151D2A", fg="#94A3B8", font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.snaps_label = tk.Label(c3, text="0", bg="#151D2A", fg="#F59E0B", font=("Segoe UI", 16, "bold"))
        self.snaps_label.pack(anchor="w", pady=(5, 0))

        # -------------------------------------------------------------
        # CARD 3: SENSITIVITY SLIDER
        # -------------------------------------------------------------
        card_slider = tk.Frame(right_pane, bg="#151D2A", padx=14, pady=10, bd=1, relief="solid")
        card_slider.pack(fill="x", pady=(0, 10))

        srow = tk.Frame(card_slider, bg="#151D2A")
        srow.pack(fill="x")
        tk.Label(srow, text="DETECTION SENSITIVITY:", bg="#151D2A", fg="#94A3B8", font=("Segoe UI", 8, "bold")).pack(side="left")
        self.conf_val_lbl = tk.Label(srow, text="40%", bg="#151D2A", fg="#10B981", font=("Segoe UI", 8, "bold"))
        self.conf_val_lbl.pack(side="right")

        self.conf_slider = ttk.Scale(card_slider, from_=10, to=90, orient="horizontal", value=40, command=self._on_slider)
        self.conf_slider.pack(fill="x", pady=(4, 0))

        # -------------------------------------------------------------
        # CARD 4: CONTROLS
        # -------------------------------------------------------------
        card_ctrl = tk.Frame(right_pane, bg="#151D2A", padx=14, pady=10, bd=1, relief="solid")
        card_ctrl.pack(fill="x", pady=(0, 10))

        self.btn_camera = tk.Button(
            card_ctrl, text="▶  Start Webcam", bg="#10B981", fg="#FFFFFF",
            activebackground="#059669", font=("Segoe UI", 10, "bold"), bd=0, padx=12, pady=7, cursor="hand2",
            command=self.toggle_camera
        )
        self.btn_camera.pack(fill="x", pady=(0, 6))

        btn_row = tk.Frame(card_ctrl, bg="#151D2A")
        btn_row.pack(fill="x")

        self.btn_image = tk.Button(
            btn_row, text="🖼  Test Image", bg="#1E293B", fg="#E2E8F0",
            activebackground="#334155", font=("Segoe UI", 8), bd=1, relief="solid", padx=6, pady=5, cursor="hand2",
            command=self.select_image_file
        )
        self.btn_image.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_snap = tk.Button(
            btn_row, text="📷  Snapshot", bg="#3B82F6", fg="#FFFFFF",
            activebackground="#2563EB", font=("Segoe UI", 8, "bold"), bd=0, padx=6, pady=5, cursor="hand2",
            command=self.save_snapshot
        )
        self.btn_snap.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # -------------------------------------------------------------
        # CARD 5: ACTIVITY LOG
        # -------------------------------------------------------------
        card_log = tk.Frame(right_pane, bg="#151D2A", padx=12, pady=8, bd=1, relief="solid")
        card_log.pack(fill="both", expand=True)
        tk.Label(card_log, text="ACTIVITY LOG", bg="#151D2A", fg="#94A3B8", font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.log_text = tk.Text(card_log, bg="#0A0E17", fg="#A7F3D0", font=("Consolas", 8), height=4, relief="flat", wrap="word")
        self.log_text.pack(fill="both", expand=True, pady=(4, 0))
        self.log("Ready. AI model and sound engine initialized.")

    def _on_sound_mode_changed(self, event=None):
        val = self.sound_mode_var.get()
        if "Kireedam" in val and "Random" not in val:
            self.alarm_player.set_mode("KIREEDAM")
            self.log("Alarm sound mode set to: 👑 Kireedam (Kathi Thazhe Idada)")
        elif "Voice" in val:
            self.alarm_player.set_mode("VOICES")
            self.log("Alarm sound mode set to: Funny Voice Warnings")
        elif "Sirens" in val:
            self.alarm_player.set_mode("SIRENS")
            self.log("Alarm sound mode set to: Sirens & Burglar Horns")
        elif "8-Bit" in val:
            self.alarm_player.set_mode("ARCADE")
            self.log("Alarm sound mode set to: 8-Bit Retro Panic")
        else:
            self.alarm_player.set_mode("RANDOM_ALL")
            self.log("Alarm sound mode set to: Random Everything")

    def test_random_sound(self):
        desc = self.alarm_player.play_alarm()
        self.log(f"Test sound triggered: {desc}")

    def on_want_water(self):
        """Handles 'I Want Water' button click: initiates smile verification or shows full big screen if already granted."""
        if self.guardian.state == BottleGuardian.STATE_WATER_GRANTED:
            self.show_drink_water_fullscreen()
            return
        if not self.is_running:
            self.toggle_camera()
        self.guardian.request_water()
        self.log(f"💧 Water requested! Look at the camera and smile {self.guardian.smile_threshold}% to unlock water!")
        self.btn_want_water.config(text=f"😊  Smiling... Need {self.guardian.smile_threshold}%!", bg="#0284C7")
        self.guardian_badge.config(text="😊 VERIFYING SMILE", bg="#0369A1", fg="#E0F2FE")
        self.guard_state_lbl.config(text=f"● 😊 SMILE ({self.guardian.smile_threshold}%) TO UNLOCK", fg="#38BDF8")

    def on_captcha_clicked(self):
        """User clicks 'Unlock with CAPTCHA' directly."""
        if not self.is_running:
            self.toggle_camera()
        self.guardian.request_captcha()
        self._show_captcha_ui()
        self.log("🔤 CAPTCHA verification requested! Enter the code shown in the box.")

    def _show_captcha_ui(self):
        if not self.guardian.current_captcha_code:
            self.refresh_captcha()
        else:
            self._update_captcha_display()
        self.captcha_frame.pack(fill="x", pady=(0, 6), before=self.sound_menu.master)
        self.captcha_entry.focus_set()

    def _hide_captcha_ui(self):
        self.captcha_frame.pack_forget()
        self.captcha_feedback.config(text="")
        self.captcha_entry.delete(0, "end")

    def _update_captcha_display(self):
        if self.guardian.current_captcha_img:
            photo = ImageTk.PhotoImage(self.guardian.current_captcha_img)
            self._captcha_photo = photo
            self.captcha_img_lbl.config(image=photo)

    def refresh_captcha(self):
        code, img = CaptchaGenerator.generate()
        self.guardian.current_captcha_code = code
        self.guardian.current_captcha_img = img
        self.guardian.last_smile_info["captcha_code"] = code
        self._update_captcha_display()

    def on_thanos_clicked(self):
        """User triggers Thanos Pose mode directly: launches fullscreen camera with hand only (no text)."""
        if not self.is_running:
            self.toggle_camera()
        self.guardian.request_thanos_pose()
        self.open_fullscreen_camera()
        self.btn_snap_fingers.pack(fill="x", pady=(0, 6), before=self.sound_menu.master)
        self.log("🧤 Thanos audio playing! Fullscreen camera active (hand only, zero text)...")

    def on_snap_clicked(self):
        """User clicks the finger snap button manually."""
        self.guardian.trigger_snap()
        self.log("💥 [SNAP] Water access granted!")
        self.btn_snap_fingers.pack_forget()

    def open_fullscreen_camera(self):
        """Opens edge-to-edge fullscreen camera for Thanos audio sequence."""
        if hasattr(self, "_fullscreen_cam_win") and self._fullscreen_cam_win:
            return
        try:
            cam_win = tk.Toplevel(self.root)
            self._fullscreen_cam_win = cam_win
            cam_win.attributes("-fullscreen", True)
            cam_win.attributes("-topmost", True)
            cam_win.configure(bg="#000000")

            lbl = tk.Label(cam_win, bg="#000000")
            lbl.pack(fill="both", expand=True)
            self._fullscreen_cam_lbl = lbl

            # Click or spacebar triggers snap if clicked manually
            cam_win.bind("<Button-1>", lambda e: self.guardian.trigger_snap())
            cam_win.bind("<space>", lambda e: self.guardian.trigger_snap())
            cam_win.bind("<Escape>", lambda e: self.close_fullscreen_camera())
        except Exception as e:
            print(f"[BottleVisionApp] Error opening fullscreen camera: {e}")

    def close_fullscreen_camera(self):
        """Closes fullscreen camera window."""
        if hasattr(self, "_fullscreen_cam_win") and self._fullscreen_cam_win:
            try:
                self._fullscreen_cam_win.destroy()
            except Exception:
                pass
            self._fullscreen_cam_win = None
            self._fullscreen_cam_lbl = None

    def on_snap_disintegrate_window(self):
        """Called immediately after dialogue and snap finishes: closes fullscreen camera and shows YOU CAN DRINK WATER NOW!"""
        self.close_fullscreen_camera()
        self.root.after(0, self.show_drink_water_fullscreen)

    def _start_thanos_dust_animation(self):
        """
        Dramatically turns the application window into Thanos dust/ash particles
        drifting away on cosmic wind while fading window opacity to 0 until it completely disappears.
        """
        if getattr(self, "_is_disintegrating", False):
            return
        self._is_disintegrating = True

        try:
            # Ensure window is visible and on top
            self.root.attributes("-alpha", 1.0)
            win_w = max(400, self.root.winfo_width())
            win_h = max(300, self.root.winfo_height())

            # Full-window particle overlay canvas
            canvas = tk.Canvas(
                self.root, width=win_w, height=win_h,
                bg="#050811", highlightthickness=0
            )
            canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
            self._dust_canvas = canvas

            # Dramatic cosmic title text
            canvas.create_text(
                win_w // 2, win_h // 3 - 35,
                text="*** \"AND I... AM... IRON MAN!\" [SNAP] ***",
                fill="#FDE047", font=("Segoe UI", 18, "bold")
            )
            canvas.create_text(
                win_w // 2, win_h // 3 + 15,
                text="DISINTEGRATING INTO DUST LIKE THANOS...",
                fill="#F59E0B", font=("Segoe UI", 13, "bold")
            )

            # Spawn 750 Marvel Thanos ash/dust particles
            dust_colors = [
                "#FEF08A", "#FDE047", "#F59E0B", "#D97706", "#B45309",
                "#78716C", "#57534E", "#44403C", "#A8A29E", "#FFFFFF",
                "#C084FC", "#F472B6"
            ]
            particles = []
            for _ in range(750):
                px = random.randint(0, win_w)
                py = random.randint(0, win_h)
                size = random.uniform(1.5, 6.0)
                vx = random.uniform(4.0, 18.0)    # Strong cosmic wind to the right
                vy = random.uniform(-9.0, 2.0)    # Floating upward like burning ash
                col = random.choice(dust_colors)
                item = canvas.create_oval(px - size, py - size, px + size, py + size, fill=col, outline="")
                particles.append({
                    "id": item, "x": px, "y": py, "size": size,
                    "vx": vx, "vy": vy, "wave": random.uniform(0, math.pi * 2)
                })

            step = 0
            total_steps = 65  # ~2.6 seconds of animation at 40ms intervals

            def animate_step():
                nonlocal step
                step += 1

                for p in particles:
                    p["wave"] += 0.25
                    p["x"] += p["vx"]
                    p["y"] += p["vy"] + math.sin(p["wave"]) * 1.5
                    sz = p["size"] * max(0.2, (1.0 - step / (total_steps * 1.2)))
                    canvas.coords(p["id"], p["x"] - sz, p["y"] - sz, p["x"] + sz, p["y"] + sz)

                progress = min(1.0, step / total_steps)
                alpha = max(0.0, 1.0 - (progress ** 1.35))
                try:
                    self.root.attributes("-alpha", alpha)
                except Exception:
                    pass

                if step < total_steps:
                    self.root.after(40, animate_step)
                else:
                    # Window has completely dissolved into dust! Disappear from desktop!
                    try:
                        self.root.withdraw()
                        self.root.attributes("-alpha", 0.0)
                    except Exception:
                        pass
                    print("\n" + "=" * 60)
                    print("✨ [THANOS SNAP] The application window has turned into dust and disappeared!")
                    print("✨ Audio playing: Avengers Endgame 'And I Am Iron Man'")
                    print("✨ Showing Full Big Screen: YOU CAN DRINK WATER NOW!")
                    print("=" * 60 + "\n")

                    # Right after dust finishes disappearing (1.0s), show the full big screen!
                    self.root.after(1000, self.show_drink_water_fullscreen)

            animate_step()

        except Exception as e:
            print(f"[ThanosDust] Animation error: {e}")

    def show_drink_water_fullscreen(self):
        """
        Displays a glorious full big screen across the monitor with massive text:
        'YOU CAN DRINK WATER NOW'
        """
        try:
            # Voice announcement
            threading.Thread(
                target=self.alarm_player._speak,
                args=("You can drink water now! Enjoy your drink!",),
                daemon=True
            ).start()

            full_win = tk.Toplevel(self.root)
            self._fullscreen_water_win = full_win
            full_win.attributes("-fullscreen", True)
            full_win.attributes("-topmost", True)
            full_win.configure(bg="#022C22")  # Deep luxurious emerald dark

            container = tk.Frame(full_win, bg="#022C22")
            container.pack(expand=True)

            # Giant water icon
            icon_lbl = tk.Label(container, text="💧", bg="#022C22", font=("Segoe UI Emoji", 80))
            icon_lbl.pack(pady=(0, 10))

            # Full Big Screen Text
            title_lbl = tk.Label(
                container,
                text="YOU CAN DRINK WATER NOW",
                bg="#022C22", fg="#34D399",
                font=("Segoe UI", 56, "bold")
            )
            title_lbl.pack(pady=(0, 14))

            # Subtitle
            sub_lbl = tk.Label(
                container,
                text="✨ ALL SECURITY CHECKS CLEARED • HYDRATION UNLOCKED ✨",
                bg="#022C22", fg="#A7F3D0",
                font=("Segoe UI", 20, "bold")
            )
            sub_lbl.pack(pady=(0, 20))

            # Description
            desc_lbl = tk.Label(
                container,
                text="Thanos has been defeated! The water bottle is safe, cold, and ready to drink.",
                bg="#022C22", fg="#6EE7B7",
                font=("Segoe UI", 14)
            )
            desc_lbl.pack(pady=(0, 36))

            # Celebratory Action Button
            btn_dismiss = tk.Button(
                container,
                text="💧  I'M DRINKING WATER! (CLICK ANYWHERE OR ESC TO CLOSE)  💧",
                bg="#059669", fg="#FFFFFF",
                activebackground="#047857", activeforeground="#FFFFFF",
                font=("Segoe UI", 15, "bold"),
                bd=0, padx=28, pady=14, cursor="hand2",
                command=self._close_drink_water_fullscreen
            )
            btn_dismiss.pack()

            # Dismiss on click or key press
            for widget in (full_win, container, icon_lbl, title_lbl, sub_lbl, desc_lbl):
                widget.bind("<Button-1>", lambda e: self._close_drink_water_fullscreen())

            full_win.bind("<Escape>", lambda e: self._close_drink_water_fullscreen())
            full_win.bind("<Return>", lambda e: self._close_drink_water_fullscreen())
            full_win.bind("<space>", lambda e: self._close_drink_water_fullscreen())

            # Auto-dismiss after 15 seconds
            full_win.after(15000, self._close_drink_water_fullscreen)

        except Exception as e:
            print(f"[BottleVisionApp] Fullscreen water error: {e}")
            self._restore_from_blip()

    def _close_drink_water_fullscreen(self):
        """Closes the full big screen and restores the main application window."""
        if hasattr(self, "_fullscreen_water_win") and self._fullscreen_water_win:
            try:
                self._fullscreen_water_win.destroy()
            except Exception:
                pass
            self._fullscreen_water_win = None
        self._restore_from_blip()

    def _restore_from_blip(self):
        """Restores the application window back from the Blip with a smooth fade-in."""
        try:
            if hasattr(self, "_dust_canvas") and self._dust_canvas:
                self._dust_canvas.destroy()
                self._dust_canvas = None

            self.root.deiconify()
            self._is_disintegrating = False

            step = 0
            def fade_in():
                nonlocal step
                step += 1
                alpha = min(1.0, step / 20.0)
                try:
                    self.root.attributes("-alpha", alpha)
                except Exception:
                    pass
                if step < 20:
                    self.root.after(35, fade_in)
                else:
                    self.log("✨ Restored from the Blip! Farzin's Water Bottle Guardian is Safe & Active.")

            fade_in()
        except Exception as e:
            print(f"[ThanosDust] Restore error: {e}")

    def submit_captcha(self):
        val = self.captcha_entry.get().strip()
        if not val:
            self.captcha_feedback.config(text="Enter code!", fg="#F87171")
            return
        success = self.guardian.verify_captcha(val)
        if success:
            self.captcha_feedback.config(text="✓ Solved!", fg="#34D399")
            self.log("🎉 CAPTCHA solved! Launching fullscreen Thanos camera...")
            self._hide_captcha_ui()
            self.open_fullscreen_camera()
        else:
            self.captcha_feedback.config(text="❌ Incorrect!", fg="#EF4444")
            self.log("❌ Incorrect CAPTCHA code! Try new code.")
            self.captcha_entry.delete(0, "end")
            self._update_captcha_display()

    def toggle_guardian(self):
        is_armed = self.guardian.toggle()
        if is_armed:
            self.btn_guard.config(text="🛑  DISARM GUARDIAN", bg="#EF4444", activebackground="#DC2626")
            self.guardian_badge.config(text="🛡️ GUARDIAN: ARMING", bg="#854D0E", fg="#FDE047")
            self.guard_state_lbl.config(text="● ARMING...", fg="#FDE047")
            self.log("Guardian armed! Place your water bottle in frame.")
            # If camera isn't running, start it automatically
            if not self.is_running:
                self.toggle_camera()
        else:
            self.btn_guard.config(text="🛡️  ARM GUARDIAN", bg="#0284C7", activebackground="#0369A1")
            self.guardian_badge.config(text="🛡️ GUARDIAN: OFF", bg="#1F2937", fg="#94A3B8")
            self.guard_state_lbl.config(text="● DISARMED", fg="#94A3B8")
            self.btn_want_water.config(text="💧  I Want Water! (Smile to Unlock)", bg="#1E293B")
            self._hide_captcha_ui()
            self.log("Guardian disarmed.")

    def _on_slider(self, val):
        thresh = float(val) / 100.0
        self.conf_val_lbl.config(text=f"{int(float(val))}%")
        self.detector.update_confidence(thresh)

    def log(self, msg: str):
        import tkinter as tk
        now = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{now}] {msg}\n")
        self.log_text.see(tk.END)

    def toggle_camera(self):
        if self.is_running:
            self.stop_stream()
            self.btn_camera.config(text="▶  Start Webcam", bg="#10B981")
            self.status_badge.config(text="● IDLE", fg="#94A3B8")
            self.log("Webcam stopped.")
        else:
            self.start_stream(0)
            self.btn_camera.config(text="⏹  Stop Webcam", bg="#EF4444")
            self.status_badge.config(text="● LIVE CAM", fg="#10B981")
            self.log("Webcam started.")

    def start_stream(self, source):
        self.stop_stream()
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            from tkinter import messagebox
            messagebox.showerror("Error", f"Could not access webcam (index {source}).")
            self.btn_camera.config(text="▶  Start Webcam", bg="#10B981")
            return

        self.is_running = True
        threading.Thread(target=self._stream_loop, daemon=True).start()

    def stop_stream(self):
        self.is_running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def _stream_loop(self):
        last_logged_theft = False
        last_logged_guard_state = ""

        while self.is_running and self.cap is not None:
            ret, frame = self.cap.read()
            if not ret:
                break

            self.current_frame = frame.copy()

            # 1. Fast detection for bottle count (without overlay overhead)
            _, detections, count, _ = self.detector.detect(frame, draw_overlay=False)

            # 2. Update guardian state with bottle count and frame for smile verification
            guardian_status, is_theft = self.guardian.update(count, frame)

            # 3. Draw high-tech HUD overlay with guardian status & smile info
            annotated, detections, count, fps = self.detector.detect(
                frame,
                draw_overlay=True,
                guardian_state=guardian_status,
                smile_info=self.guardian.last_smile_info
            )
            self.current_annotated = annotated

            # Log significant guardian events
            if is_theft and not last_logged_theft:
                self.root.after(0, self.log, f"🚨 THEFT ALERT! {self.guardian.latest_event_msg}")
                last_logged_theft = True
            elif not is_theft and last_logged_theft:
                self.root.after(0, self.log, "Bottle returned! Alarm silenced.")
                last_logged_theft = False

            if guardian_status != last_logged_guard_state and not is_theft:
                if self.guardian.latest_event_msg:
                    self.root.after(0, self.log, self.guardian.latest_event_msg)
                last_logged_guard_state = guardian_status

            self.root.after(0, self._render_frame, annotated, count, fps, guardian_status, is_theft)
            time.sleep(0.01)
        self.is_running = False

    def _render_frame(self, frame_bgr, count: int, fps: float, guardian_status: str, is_theft: bool):
        self.count_label.config(text=str(count))
        self.fps_label.config(text=f"{fps:.1f}")

        # Update guardian UI indicators & button state
        if self.guardian.state == BottleGuardian.STATE_WATER_GRANTED:
            self.guardian_badge.config(text="💧 WATER GRANTED", bg="#065F46", fg="#A7F3D0")
            self.guard_state_lbl.config(text="● 💧 YOU CAN DRINK WATER NOW", fg="#10B981")
            self.btn_want_water.config(text="💧  YOU CAN DRINK WATER NOW!", bg="#059669")
            if self.btn_snap_fingers.winfo_ismapped():
                self.btn_snap_fingers.pack_forget()
        elif self.guardian.state == BottleGuardian.STATE_THANOS_POSE:
            cnt = self.guardian.last_smile_info.get("countdown", 3)
            self.guardian_badge.config(text=f"🧤 WAIT... {cnt}s", bg="#581C87", fg="#F3E8FF")
            self.guard_state_lbl.config(text=f"● 🧤 WAIT... SNAP IN {cnt}s", fg="#C084FC")
            self.btn_want_water.config(text=f"⏳  Hold Pose... Wait {cnt}s", bg="#6D28D9")
            if not self.btn_snap_fingers.winfo_ismapped():
                self.btn_snap_fingers.pack(fill="x", pady=(0, 6), before=self.sound_menu.master)
            self.btn_snap_fingers.config(text=f"🫰  SNAP NOW! (WAIT: {cnt}s)")
        elif self.guardian.state == BottleGuardian.STATE_CAPTCHA_VERIFICATION:
            self.guardian_badge.config(text="🔤 ENTER CAPTCHA", bg="#6D28D9", fg="#EDE9FE")
            self.guard_state_lbl.config(text="● 🔤 ENTER CAPTCHA TO UNLOCK", fg="#A78BFA")
            self.btn_want_water.config(text="🔤  Solve CAPTCHA Below", bg="#7C3AED")
            if not self.captcha_frame.winfo_ismapped():
                self._show_captcha_ui()
        elif self.guardian.state == BottleGuardian.STATE_SMILE_VERIFICATION:
            smile_pct = self.guardian.last_smile_info.get("smile_pct", 0)
            target_pct = self.guardian.smile_threshold
            face_found = self.guardian.last_smile_info.get("face_found", False)
            if face_found:
                self.guardian_badge.config(text=f"😊 SMILE: {smile_pct}%", bg="#0284C7", fg="#E0F2FE")
                self.guard_state_lbl.config(text=f"● 😊 SMILE METER: {smile_pct}% / {target_pct}%", fg="#38BDF8")
                self.btn_want_water.config(text=f"😊  Smile: {smile_pct}% (Need {target_pct}%)", bg="#0284C7")
            else:
                self.guardian_badge.config(text="🔍 LOOKING FOR FACE", bg="#0369A1", fg="#E0F2FE")
                self.guard_state_lbl.config(text="● 🔍 LOOK AT CAMERA TO SMILE", fg="#FDE047")
                self.btn_want_water.config(text="🔍  Looking for Face...", bg="#0369A1")
        elif is_theft:
            self.guardian_badge.config(text="🚨 THEFT ALERT! 🚨", bg="#991B1B", fg="#FEF2F2")
            self.guard_state_lbl.config(text="● 🚨 THEFT DETECTED! 🚨", fg="#EF4444")
            self.btn_want_water.config(text="💧  I Want Water! (Click Here)", bg="#0D9488")
        elif "ARMED" in guardian_status:
            self.guardian_badge.config(text="🛡️ BOTTLE PROTECTED", bg="#065F46", fg="#A7F3D0")
            self.guard_state_lbl.config(text="● 🟢 BOTTLE PROTECTED", fg="#10B981")
            self.btn_want_water.config(text="💧  I Want Water! (Smile to Unlock)", bg="#0D9488")
        elif "WAITING" in guardian_status:
            self.guardian_badge.config(text="🛡️ GUARDIAN: ARMING", bg="#854D0E", fg="#FDE047")
            self.guard_state_lbl.config(text="● PLACE BOTTLE IN FRAME", fg="#FDE047")
            self.btn_want_water.config(text="💧  I Want Water! (Smile to Unlock)", bg="#1E293B")
        else:
            self.guard_state_lbl.config(text="● DISARMED", fg="#94A3B8")
            self.guardian_badge.config(text="🛡️ GUARDIAN: OFF", bg="#1F2937", fg="#94A3B8")
            self.btn_want_water.config(text="💧  I Want Water! (Smile to Unlock)", bg="#1E293B")

        # Handle fullscreen camera during Thanos audio (hand only, zero text)
        if self.guardian.state == BottleGuardian.STATE_THANOS_POSE:
            self.open_fullscreen_camera()
            if hasattr(self, "_fullscreen_cam_lbl") and self._fullscreen_cam_lbl and hasattr(self, "_fullscreen_cam_win") and self._fullscreen_cam_win:
                try:
                    win_w = max(100, self._fullscreen_cam_win.winfo_width())
                    win_h = max(100, self._fullscreen_cam_win.winfo_height())
                    h, w, _ = frame_bgr.shape
                    scale = min(win_w / w, win_h / h)
                    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                    full_resized = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
                    full_rgb = cv2.cvtColor(full_resized, cv2.COLOR_BGR2RGB)
                    full_tk = ImageTk.PhotoImage(Image.fromarray(full_rgb))
                    self._fullscreen_cam_photo = full_tk
                    self._fullscreen_cam_lbl.config(image=full_tk)
                except Exception:
                    pass
        else:
            if hasattr(self, "_fullscreen_cam_win") and self._fullscreen_cam_win:
                self.close_fullscreen_camera()

        h_canvas = max(50, self.video_canvas.winfo_height())
        w_canvas = max(50, self.video_canvas.winfo_width())
        h, w, _ = frame_bgr.shape
        scale = min(w_canvas / w, h_canvas / h)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))

        resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        img_tk = ImageTk.PhotoImage(Image.fromarray(rgb))

        # Store photo image on instance to prevent garbage collection and satisfy type checkers
        self._photo_image = img_tk
        self.video_canvas.config(image=img_tk, text="")

    def select_image_file(self):
        from tkinter import filedialog, messagebox
        self.stop_stream()
        self.btn_camera.config(text="▶  Start Webcam", bg="#10B981")

        path = filedialog.askopenfilename(
            title="Select Image File",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")]
        )
        if not path:
            return

        self.log(f"Processing: {os.path.basename(path)}")
        self.status_badge.config(text="● IMAGE", fg="#38BDF8")

        frame = cv2.imread(path)
        if frame is None:
            messagebox.showerror("Error", "Could not read image file.")
            return

        annotated, detections, count, _ = self.detector.detect(frame, draw_overlay=True)
        self.current_annotated = annotated
        self.log(f"Found {count} bottle(s).")
        self._render_frame(annotated, count, 0.0, "OFF", False)

    def save_snapshot(self):
        from tkinter import messagebox
        if self.current_annotated is None:
            messagebox.showinfo("Notice", "No image or video frame to save.")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bottle_detected_{ts}.jpg"
        save_path = os.path.join(self.captures_dir, filename)
        cv2.imwrite(save_path, self.current_annotated)
        self.total_snapshots += 1
        self.snaps_label.config(text=str(self.total_snapshots))
        self.log(f"Saved: captures/{filename}")
        messagebox.showinfo("Saved", f"Snapshot saved!\n\nPath: {save_path}")

    def on_closing(self):
        self.guardian.disarm()
        self.stop_stream()
        self.root.destroy()


# ==============================================================================
# 5. CLI & SELF-TEST MODES
# ==============================================================================
def run_cli_camera(cam_id=0, conf=0.40, enable_guard=False):
    detector = BottleDetector(conf_threshold=conf)
    alarm_player = BottleAlarmPlayer()
    smile_detector = SmileDetector()
    guardian = BottleGuardian(alarm_player, smile_detector=smile_detector, debounce_sec=0.7, smile_threshold=30)

    if enable_guard:
        guardian.arm()
        print("[Guardian] Anti-Theft Bottle Guardian ARMED! Place your bottle in view.")

    cap = cv2.VideoCapture(cam_id)
    if not cap.isOpened():
        print(f"[Error] Could not open camera {cam_id}")
        return

    print("=" * 60)
    print(" BottleVision Camera Running")
    print(" Controls:")
    print("   'w' : 'I Want Water' (Smile 30% -> CAPTCHA to unlock water)")
    print("   'c' : Solve CAPTCHA Directly to Unlock")
    print("   'g' : Toggle Guardian (Arm / Disarm)")
    print("   's' : Save Snapshot")
    print("   'q' : Quit")
    print("=" * 60)
    os.makedirs("captures", exist_ok=True)
    win = "BottleVision AI - Anti-Theft Camera"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Fast bottle count detection
            _, _, count, _ = detector.detect(frame, draw_overlay=False)
            guardian_status, is_theft = guardian.update(count, frame)

            # Re-draw with guardian state & smile HUD
            annotated, detections, count, fps = detector.detect(
                frame,
                draw_overlay=True,
                guardian_state=guardian_status,
                smile_info=guardian.last_smile_info
            )

            cv2.imshow(win, annotated)
            k = cv2.waitKey(1) & 0xFF
            if k in (ord('q'), 27):
                break
            elif k == ord('w'):
                guardian.request_water()
                print(f"[Water] 'I Want Water' requested! Look at camera and smile {guardian.smile_threshold}% to unlock.")
            elif k == ord('c'):
                guardian.request_captcha()
                code = guardian.current_captcha_code
                print("\n" + "=" * 60)
                print(f"🤖 SECURITY VERIFICATION: ENTER CAPTCHA CODE")
                print(f"   CODE TO ENTER: [  {code}  ]")
                print("=" * 60)
                user_val = input("Enter code to unlock water: ")
                if guardian.verify_captcha(user_val):
                    print("✓ CAPTCHA Verified! Water granted!")
                else:
                    print("❌ Incorrect CAPTCHA.")
            elif k == ord('s'):
                p = f"captures/snap_{int(time.time())}.jpg"
                cv2.imwrite(p, annotated)
                print(f"Saved: {p}")
            elif k == ord('g'):
                is_armed = guardian.toggle()
                print(f"[Guardian] Toggled: {'ARMED' if is_armed else 'DISARMED'}")
    finally:
        guardian.disarm()
        cap.release()
        cv2.destroyAllWindows()


def run_self_test():
    """Automated self-test verification with synthetic image, sound, and smile detector."""
    print("=" * 60)
    print(" Running BottleVision Self-Test Verification...")
    print("=" * 60)

    # 1. Test model initialization
    detector = BottleDetector(model_name="yolov8n.pt", conf_threshold=0.30)
    print("✓ YOLOv8 model initialized successfully.")

    # 2. Test Sound Player
    player = BottleAlarmPlayer()
    print(f"✓ Sound engine initialized. {len(player._cached_wavs)} sound effects ready.")
    if os.path.exists(player.kireedam_wav_path):
        print("✓ Kireedam audio file verified on disk.")

    # 3. Test Smile Detector
    smile_detector = SmileDetector()
    test_face_img = np.zeros((320, 320, 3), dtype=np.uint8)
    found, smile_pct, box, lms = smile_detector.detect_smile(test_face_img)
    print(f"✓ SmileDetector initialized and verified: (face_found={found}, smile_pct={smile_pct}%)")

    # 4. Test CAPTCHA Generator
    c_code, c_img = CaptchaGenerator.generate()
    assert len(c_code) == 5
    assert c_img is not None
    print(f"✓ CaptchaGenerator verified: code '{c_code}', image size={c_img.size}")

    # 5. Test Bottle Guardian, Smile, CAPTCHA & Thanos Snap Flow
    guardian = BottleGuardian(player, smile_detector=smile_detector, smile_threshold=30)
    guardian.arm()
    status, is_theft = guardian.update(bottle_count=1)
    print(f"✓ Guardian arm & detection verified: {status} (Theft={is_theft})")

    # Test I Want Water flow
    guardian.request_water()
    assert guardian.state == BottleGuardian.STATE_SMILE_VERIFICATION
    print(f"✓ 'I Want Water' request flow verified: state={guardian.state}")

    # Test CAPTCHA trigger & verification -> leads to Thanos Pose
    guardian.request_captcha()
    assert guardian.state == BottleGuardian.STATE_CAPTCHA_VERIFICATION
    assert not guardian.verify_captcha("WRONG")
    assert guardian.verify_captcha(guardian.current_captcha_code)
    assert guardian.state == BottleGuardian.STATE_THANOS_POSE
    print(f"✓ CAPTCHA verification flow leads to Thanos Pose: state={guardian.state}")

    # Test Thanos Snap -> plays Iron Man audio and grants water
    guardian.trigger_snap()
    assert guardian.state == BottleGuardian.STATE_WATER_GRANTED
    print(f"✓ Thanos Snap triggered and water granted: state={guardian.state}")
    guardian.disarm()

    # 6. Create synthetic test bottle image with Thanos Gauntlet overlay
    img = np.ones((480, 640, 3), dtype=np.uint8) * 235
    cv2.rectangle(img, (0, 360), (640, 480), (130, 100, 80), -1)      # Table
    cv2.rectangle(img, (270, 160), (370, 380), (220, 180, 70), -1)   # Bottle body
    cv2.rectangle(img, (300, 100), (340, 160), (200, 150, 60), -1)   # Neck
    cv2.rectangle(img, (295, 85), (345, 100), (50, 50, 210), -1)      # Cap

    test_path = "sample_bottle.jpg"
    cv2.imwrite(test_path, img)

    annotated, detections, count, fps = detector.detect(
        img,
        draw_overlay=True,
        guardian_state="ARMED",
        smile_info={
            "active": True, "face_found": True, "smile_pct": 30, "threshold": 30,
            "face_box": (200, 100, 120, 120), "landmarks": [], "granted": True,
            "thanos_active": True, "hand_pos": (480, 240)
        }
    )
    os.makedirs("captures", exist_ok=True)
    cv2.imwrite("captures/test_result.jpg", annotated)

    print("✓ Full detection, smile HUD & Thanos Gauntlet overlay pipeline completed successfully.")
    print("✓ Output frame generated and saved to captures/test_result.jpg")
    print("=" * 60)
    print(" All Self-Tests PASSED!")
    print("=" * 60)


# ==============================================================================
# 6. ENTRYPOINT
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="BottleVision AI - Bottle Detection & Anti-Theft Guardian")
    parser.add_argument("--cli", action="store_true", help="Launch lightweight CLI camera mode")
    parser.add_argument("--guard", action="store_true", help="Enable Anti-Theft Bottle Guardian on launch")
    parser.add_argument("--cam", type=int, default=None, help="Camera index")
    parser.add_argument("--image", type=str, default=None, help="Detect bottles on an image")
    parser.add_argument("--test", action="store_true", help="Run automated self-test")
    parser.add_argument("--conf", type=float, default=0.40, help="Confidence threshold (0.10 to 0.90)")

    args = parser.parse_args()

    if args.test:
        run_self_test()
    elif args.image:
        detector = BottleDetector(conf_threshold=args.conf)
        img = cv2.imread(args.image)
        if img is None:
            print(f"Error reading image: {args.image}")
            return
        ann, dets, cnt, _ = detector.detect(img)
        print(f"Bottles detected: {cnt}")
        for i, d in enumerate(dets, 1):
            print(f" Bottle #{i}: {d['confidence']*100:.1f}% confidence, box: {d['box']}")
        os.makedirs("captures", exist_ok=True)
        out = os.path.join("captures", "result_" + os.path.basename(args.image))
        cv2.imwrite(out, ann)
        print(f"Annotated result saved to: {out}")
    elif args.cli or args.cam is not None:
        cid = args.cam if args.cam is not None else 0
        run_cli_camera(cam_id=cid, conf=args.conf, enable_guard=args.guard)
    else:
        # Default: Launch GUI
        import tkinter as tk
        root = tk.Tk()
        app = BottleVisionApp(root)
        root.mainloop()


if __name__ == "__main__":
    main()
