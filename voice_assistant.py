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
        # Kuyruk yapısı: (Priority, Timestamp, UniqueKey, Message)
        self.queue = PriorityQueue()
        self.last_spoken: dict[str, float] = {}
        
        self.running = True
        self.engine_lock = threading.Lock()
        
        # Arka plan işçisini başlat
        self.worker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.worker_thread.start()

    def _speech_worker(self):
        """Kuyruğu milisaniyelik izleyen ve yüksek öncelikte söz kesen motor."""
        while self.running:
            if not self.queue.empty():
                priority, timestamp, unique_key, message = self.queue.get()
                
                # GEÇERLİLİK SÜRESİ (TTL) FİLTRESİ: 
                # Eğer mesaj kuyrukta 0.5 saniyeden fazla beklediyse eskiyip geçerliliğini yitirmiştir, ÇÖPE AT!
                if (time.time() - timestamp) > 0.5 and priority > 1:
                    self.queue.task_done()
                    continue
                
                # Konuşma döngüsü
                try:
                    with self.engine_lock:
                        engine = pyttsx3.init()
                        engine.setProperty('rate', 200) # Hızlı ve dinamik asistan tonu
                        engine.say(message)
                        engine.runAndWait()
                        del engine
                except Exception as e:
                    pass
                
                self.queue.task_done()
            else:
                time.sleep(0.02) # Çok daha sıkı tarama döngüsü

    def speak(self, message: str, unique_key: str, priority: int = 2, force: bool = False):
        """
        Kuyruğa anons ekler.
        priority=1 (İnsan, Telefon, Yakın Tehlike): Sıfır gecikme, gerekirse mevcut konuşmayı durdurur.
        priority=2 (Koltuk, Sandalye): Arka plandan sakin akış.
        """
        now = time.time()
        
        # Cooldown koruması (Aynı mesajın spam olmasını engeller)
        if not force and (now - self.last_spoken.get(unique_key, 0) < self.global_cooldown):
            return False

        # EĞER KRİTİK BİR DURUM VARSA (Priority=1) VE FORCE=TRUE İSE:
        if force and priority == 1:
            # 1. Kuyrukta birikmiş tüm eski statik nesne anonslarını anında temizle
            with self.queue.mutex:
                self.queue.queue.clear()
            
            # 2. Sesi hemen kesmek için pyttsx3 motorunu durdurmayı tetikle
            try:
                dummy_engine = pyttsx3.init()
                dummy_engine.stop() # Mevcut konuşmayı anında yarıda keser!
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