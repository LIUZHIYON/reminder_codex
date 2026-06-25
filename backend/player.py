import pygame
import os
import time
import threading

class AudioPlayer:
    def __init__(self):
        self._lock = threading.Lock()
        self._initialized = False

    def _ensure_init(self):
        if self._initialized:
            return True
        try:
            pygame.mixer.init(frequency=22050)
            self._initialized = True
            print("[Player] Mixer initialized")
            return True
        except Exception as e:
            print(f"[Player] Mixer init failed (audio disabled): {e}")
            return False

    def play(self, audio_path, block=True):
        if not os.path.exists(audio_path):
            print(f"[Player] File not found: {audio_path}")
            return False
        if not self._ensure_init():
            print("[Player] Cannot play - mixer not available")
            return False
        with self._lock:
            try:
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                if block:
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                return True
            except Exception as e:
                print(f"[Player] Error: {e}")
                return False

    def stop(self):
        if not self._initialized:
            return
        with self._lock:
            try:
                pygame.mixer.music.stop()
            except:
                pass

    def is_playing(self):
        if not self._initialized:
            return False
        with self._lock:
            try:
                return pygame.mixer.music.get_busy()
            except:
                return False

# Lazy init - only called when play() is first used
player = AudioPlayer()
