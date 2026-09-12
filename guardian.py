"""
BottleVision Sentinel - Guardian Controller & Hydration Tracker
Manages anti-theft state machine, alarms, and bottle interaction statistics.
"""

import time
from audio_engine import BottleAlarmPlayer


class BottleGuardian:
    STATE_DISARMED = "DISARMED"
    STATE_ARMING = "ARMING"
    STATE_ARMED = "ARMED_SECURE"
    STATE_THEFT_ALERT = "THEFT_ALERT"

    def __init__(self, alarm_player: BottleAlarmPlayer, debounce_sec: float = 0.7, on_theft_callback=None):
        self.player = alarm_player
        self.state = self.STATE_DISARMED
        self.debounce_sec = debounce_sec
        self.on_theft_callback = on_theft_callback

        self.last_seen_time = 0.0
        self.missing_since = 0.0
        self.last_alarm_sound_time = 0.0
        self.theft_count = 0
        self.hydration_sips = 0
        self.latest_event_msg = "Sentinel ready."
        self.event_log = []

    def log_event(self, msg: str, level: str = "info"):
        timestamp = time.strftime("%H:%M:%S")
        entry = {
            "time": timestamp,
            "msg": msg,
            "level": level  # "info", "success", "warning", "danger"
        }
        self.event_log.append(entry)
        if len(self.event_log) > 60:
            self.event_log.pop(0)

    def arm(self):
        """Arms the bottle guardian."""
        self.state = self.STATE_ARMING
        self.missing_since = 0.0
        self.latest_event_msg = "Sentinel armed. Point camera at your water bottle to lock."
        self.log_event(self.latest_event_msg, "warning")

    def disarm(self):
        """Disarms the guardian and silences any alarm."""
        self.state = self.STATE_DISARMED
        self.missing_since = 0.0
        self.player.stop()
        self.latest_event_msg = "Sentinel disarmed."
        self.log_event(self.latest_event_msg, "info")

    def toggle(self) -> bool:
        """Toggles between armed and disarmed."""
        if self.state == self.STATE_DISARMED:
            self.arm()
            return True
        else:
            self.disarm()
            return False

    def update(self, bottle_count: int) -> tuple[str, bool]:
        """
        Updates state based on current frame bottle count.
        Returns (status_text, is_theft_active).
        """
        now = time.time()
        is_theft = False

        if self.state == self.STATE_DISARMED:
            return "DISARMED", False

        elif self.state == self.STATE_ARMING:
            if bottle_count > 0:
                self.state = self.STATE_ARMED
                self.last_seen_time = now
                self.missing_since = 0.0
                self.player.play_secure_chime()
                self.latest_event_msg = "Target locked! Bottle Sentinel active."
                self.log_event("Bottle locked & secured! Sentinel defense shield is now ACTIVE.", "success")
                return "ARMED_SECURE", False
            else:
                return "ARMING", False

        elif self.state == self.STATE_ARMED:
            if bottle_count > 0:
                self.last_seen_time = now
                self.missing_since = 0.0
                return "ARMED_SECURE", False
            else:
                # Bottle is missing from frame
                if self.missing_since == 0.0:
                    self.missing_since = now

                # If missing duration exceeds debounce grace period: THEFT!
                if (now - self.missing_since) >= self.debounce_sec:
                    self.state = self.STATE_THEFT_ALERT
                    self.theft_count += 1
                    self.last_alarm_sound_time = now
                    sound_desc = self.player.play_alarm()
                    self.latest_event_msg = f"THEFT DETECTED! Playing {sound_desc}"
                    self.log_event(f"🚨 THEFT ALERT! Bottle removed from desk! Triggered {sound_desc}", "danger")

                    if self.on_theft_callback:
                        try:
                            self.on_theft_callback()
                        except Exception as e:
                            print(f"[BottleGuardian] Snapshot callback error: {e}")

                    return "THEFT_ALERT", True
                else:
                    return "VERIFYING", False

        elif self.state == self.STATE_THEFT_ALERT:
            is_theft = True
            if bottle_count > 0:
                # Bottle returned!
                self.state = self.STATE_ARMED
                self.missing_since = 0.0
                self.hydration_sips += 1
                self.player.stop()
                self.player.play_secure_chime()
                self.latest_event_msg = "Bottle returned to desk! Sentinel re-armed."
                self.log_event(f"Bottle returned safely! (Sip #{self.hydration_sips} logged)", "success")
                return "ARMED_SECURE", False
            else:
                # Still missing! Periodically re-trigger alarm (14s for Kireedam, 3.5s for synth)
                repeat_sec = 14.0 if self.player.sound_mode == "KIREEDAM" else 3.5
                if (now - self.last_alarm_sound_time) >= repeat_sec:
                    self.last_alarm_sound_time = now
                    sound_desc = self.player.play_alarm()
                    self.latest_event_msg = f"ALARM RE-TRIGGER: {sound_desc}"
                return "THEFT_ALERT", True

        return "UNKNOWN", False
