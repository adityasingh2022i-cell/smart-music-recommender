import queue
import threading
import os
import time
from gtts import gTTS
import playsound
import pyttsx3

VOICE_FILE = "voice.mp3"
_speak_queue = queue.Queue()
_engine = pyttsx3.init()
_use_gtts = True
_stop_event = threading.Event()

def _loop():
    while not _stop_event.is_set():
        try:
            text, lang = _speak_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            if _use_gtts:
                try:
                    tts = gTTS(text=text, lang=lang if lang in ["en", "hi"] else "en")
                    tts.save(VOICE_FILE)
                    playsound.playsound(VOICE_FILE)
                    if os.path.exists(VOICE_FILE):
                        os.remove(VOICE_FILE)
                except Exception:
                    _engine.say(text)
                    _engine.runAndWait()
            else:
                _engine.say(text)
                _engine.runAndWait()
        except Exception as e:
            print("TTS error:", e)
        finally:
            _speak_queue.task_done()

def speak(text, lang="en"):
    _speak_queue.put((text, lang))

def stop():
    _stop_event.set()

# start
threading.Thread(target=_loop, daemon=True).start()
