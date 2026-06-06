"""
voice_assistant.py — AEye Project
Advanced Interrupter-Enabled Voice Assistant with TTL Expiration Shield
"""

import threading
import time
from queue import PriorityQueue
import pyttsx3


class VoiceAssistant:
    def __init__(self, global_cooldown: float = 2.5):
        self.global_cooldown = global_cooldown
        # Queue format: (Priority, Timestamp, UniqueKey, Message)
        self.queue = PriorityQueue()
        self.last_spoken: dict[str, float] = {}

        self.running = True
        self.engine_lock = threading.Lock()

        # Start background worker thread
        self.worker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.worker_thread.start()

    def _speech_worker(self):
        """Background worker that monitors the queue and handles speech output."""
        while self.running:
            if not self.queue.empty():
                priority, timestamp, unique_key, message = self.queue.get()

                # TTL FILTER:
                # If a message waited more than 0.5s in queue, it's stale — discard it
                # No point announcing old positional info, it may already be wrong
                if (time.time() - timestamp) > 0.5 and priority > 1:
                    self.queue.task_done()
                    continue

                # Speech loop
                try:
                    with self.engine_lock:
                        engine = pyttsx3.init()
                        engine.setProperty('rate', 200)  # Fast and natural assistant pace
                        engine.say(message)
                        engine.runAndWait()
                        del engine
                except Exception as e:
                    pass

                self.queue.task_done()
            else:
                time.sleep(0.02)  # Tight polling loop — keeps latency low

    def speak(self, message: str, unique_key: str, priority: int = 2, force: bool = False):
        """
        Adds an announcement to the queue.
        priority=1 (Person, Phone, Close Hazard): Zero delay, interrupts current speech if needed.
        priority=2 (Chair, Couch, Background objects): Calm delivery in background.
        """
        now = time.time()

        # Cooldown check — prevents the same message from spamming
        if not force and (now - self.last_spoken.get(unique_key, 0) < self.global_cooldown):
            return False

        # If this is a critical alert (priority=1) and force=True:
        if force and priority == 1:
            # 1. Clear all pending static object announcements from the queue immediately
            with self.queue.mutex:
                self.queue.queue.clear()

            # 2. Stop current speech by triggering a stop via a secondary engine instance
            try:
                dummy_engine = pyttsx3.init()
                dummy_engine.stop()
                del dummy_engine
            except Exception:
                pass

        self.last_spoken[unique_key] = now
        self.queue.put((priority, now, unique_key, message))
        return True

    def stop(self):
        self.running = False
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=0.5)