"""
BottleVision Sentinel - Audio Engine
Synthesizes and plays random alarm sounds and funny classroom voice alerts.
Supports both local host speaker playback and web client sound serving.
"""

import os
import sys
import time
import math
import struct
import io
import wave
import random
import threading
import subprocess

try:
    import winsound
except ImportError:
    winsound = None


class BottleAlarmPlayer:
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
        self._kireedam_data = None
        self._load_kireedam_sound()
        self._pregenerate_sounds()

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
                print(f"[AudioEngine] Warning reading {self.kireedam_wav_path}: {e}")

        # If not present, background download via yt-dlp & imageio-ffmpeg
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
                print("[AudioEngine] Kireedam sound loaded successfully!")
        except Exception as e:
            print(f"[AudioEngine] Could not auto-download Kireedam sound: {e}")

    def get_sound_bytes(self, sound_name: str) -> bytes | None:
        """Returns WAV bytes for a given sound name for web streaming."""
        if sound_name == "kireedam":
            if self._kireedam_data:
                return self._kireedam_data
            if os.path.exists(self.kireedam_wav_path):
                with open(self.kireedam_wav_path, "rb") as f:
                    return f.read()
            return None
        return self._cached_wavs.get(sound_name)

    def play_kireedam(self) -> str:
        """Plays the iconic 'Kireedam kathi thazhe idada' audio."""
        if os.path.exists(self.kireedam_wav_path) and winsound:
            try:
                winsound.PlaySound(self.kireedam_wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return "👑 Kireedam (Kathi Thazhe Idada)"
            except Exception as e:
                print(f"[AudioEngine] PlaySound error: {e}")
        elif self._kireedam_data and winsound:
            ws = winsound
            try:
                threading.Thread(
                    target=lambda: ws.PlaySound(self._kireedam_data, ws.SND_MEMORY),
                    daemon=True
                ).start()
                return "👑 Kireedam (Kathi Thazhe Idada)"
            except Exception as e:
                print(f"[AudioEngine] PlaySound error: {e}")
        return self.play_random()

    def play_alarm(self) -> str:
        """Triggers alarm based on configured sound_mode."""
        if self.sound_mode == "KIREEDAM":
            return self.play_kireedam()
        elif self.sound_mode == "RANDOM_ALL":
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

        except Exception as e:
            print(f"[AudioEngine] Warning: Failed to pregenerate some audio: {e}")

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
        """Plays reassurance chime when bottle is returned."""
        data = self._cached_wavs.get("secure_chime")
        if data and winsound:
            try:
                winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_ASYNC)
            except Exception:
                pass

    def play_sound_by_name(self, sound_key: str) -> str:
        """Plays specific sound by key name."""
        if sound_key == "kireedam":
            return self.play_kireedam()
        elif sound_key == "voice":
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
            return f"Sound FX: {sound_key}"

    def play_custom_speech(self, phrase: str):
        """Speaks custom text on host machine."""
        threading.Thread(target=self._speak, args=(phrase,), daemon=True).start()

    def play_random(self) -> str:
        """Picks and triggers a random alarm sound according to selected sound mode."""
        siren_keys = ["siren", "burglar", "ufo_wobble"]
        arcade_keys = ["laser", "panic_8bit", "cartoon_boing"]
        synth_keys = siren_keys + arcade_keys

        if self.sound_mode == "VOICES":
            action = "VOICE"
        elif self.sound_mode == "SIRENS":
            action = "SYNTH"
            sound_key = random.choice(siren_keys)
        elif self.sound_mode == "ARCADE":
            action = "SYNTH"
            sound_key = random.choice(arcade_keys)
        else:  # RANDOM_ALL
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
                safe_phrase = phrase.replace("'", "").replace('"', "")
                script = f'Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 1; $s.Speak("{safe_phrase}")'
                subprocess.run(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
                    creationflags=0x08000000,
                    timeout=5,
                    check=False
                )
            except Exception as e:
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
