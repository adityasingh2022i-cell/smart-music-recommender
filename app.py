import os
import threading
import webbrowser
from datetime import datetime
import time
import queue
import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog

import pandas as pd
import cv2
from deepface import DeepFace
import speech_recognition as sr
from gtts import gTTS
from langdetect import detect
import playsound
from PIL import Image, ImageTk  # requires pillow
import pyttsx3
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------- CONFIG / PATHS --------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SONGS_CSV = os.path.join(BASE_DIR, "songs.csv")
LOG_PATH = os.path.join(BASE_DIR, "logs.txt")
VOICE_FILE = os.path.join(BASE_DIR, "voice.mp3")
DB_PATH = os.path.join(BASE_DIR, "users.db")

# -------------------- DATABASE --------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            language TEXT DEFAULT 'english',
            artist TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

def create_user(username, password):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                  (username, generate_password_hash(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def validate_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    return check_password_hash(row[0], password)

def get_preferences(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT language, artist FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return ("english", "")
    return (row[0] or "english", row[1] or "")

def update_preferences_db(username, language, artist):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET language=?, artist=? WHERE username=?", (language, artist, username))
    conn.commit()
    conn.close()

# -------------------- LOGGING --------------------
def log_event(event):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {event}\n")
    except Exception as e:
        print("Logging error:", e)

# -------------------- TTS --------------------
_speak_queue = queue.Queue()
_engine = pyttsx3.init()
_use_gtts = True
_speaker_stop_event = threading.Event()

def _speaker_loop():
    while not _speaker_stop_event.is_set():
        try:
            text, lang = _speak_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            if _use_gtts:
                try:
                    tts = gTTS(text=text, lang=lang if lang in ['en', 'hi'] else 'en')
                    tts.save(VOICE_FILE)
                    playsound.playsound(VOICE_FILE)
                    if os.path.exists(VOICE_FILE):
                        os.remove(VOICE_FILE)
                except Exception as e:
                    print("gTTS failed, fallback to pyttsx3:", e)
                    _engine.say(text)
                    _engine.runAndWait()
            else:
                _engine.say(text)
                _engine.runAndWait()
        except Exception as outer:
            print("TTS final error:", outer)
        finally:
            _speak_queue.task_done()

def speak(text, lang='en'):
    _speak_queue.put((text, lang))

def stop_speaker():
    _speaker_stop_event.set()
    time.sleep(0.2)

threading.Thread(target=_speaker_loop, daemon=True).start()

# -------------------- VOICE LISTENING --------------------
def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        audio = r.listen(source, phrase_time_limit=5)
        try:
            command_raw = r.recognize_google(audio)
            lang = 'en'
            try:
                lang = detect(command_raw)
            except:
                pass
            return command_raw.lower(), lang
        except sr.UnknownValueError:
            return "i didn't understand", 'en'
        except sr.RequestError:
            return "service unavailable", 'en'

# -------------------- RECOMMENDER --------------------
def load_songs():
    if not os.path.exists(SONGS_CSV):
        log_event(f"{SONGS_CSV} missing.")
        return pd.DataFrame()
    try:
        return pd.read_csv(SONGS_CSV)
    except Exception as e:
        log_event(f"Error reading songs.csv: {e}")
        return pd.DataFrame()

def filter_songs(mood, language=None, artist=None):
    df = load_songs()
    if df.empty:
        return df
    mood_lower = mood.lower()
    filtered = df[df['mood'].str.lower().str.contains(mood_lower, na=False)]
    if language and language.strip():
        filtered = filtered[filtered['language'].str.lower() == language.strip().lower()]
    if artist and artist.strip():
        filtered = filtered[filtered['artist'].str.lower() == artist.strip().lower()]
    return filtered

def suggest_music(mood, language=None, artist=None):
    filtered = filter_songs(mood, language=language, artist=artist)
    if filtered.empty:
        msg = f"No songs found for mood='{mood}'"
        if language:
            msg += f", language='{language}'"
        if artist:
            msg += f", artist='{artist}'"
        log_event(msg)
        speak("Sorry, I couldn't find any matching songs.", 'en')
        return []
    sample = filtered.sample(n=1).iloc[0]
    title = sample.get('title', 'Unknown')
    art = sample.get('artist', 'Unknown')
    lang = sample.get('language', 'Unknown')
    url = sample.get('url', None)
    log_event(f"Suggested ({mood}) [{lang}] by {art}: {title}")
    if url and isinstance(url, str) and url.strip():
        try:
            webbrowser.open(url)
        except Exception as e:
            log_event(f"Failed opening URL {url}: {e}")
    else:
        speak(f"I found {title} but its link is missing.", 'en')
    return [{
        "title": title,
        "artist": art,
        "language": lang,
        "mood": sample.get('mood', mood),
        "url": url
    }]

# -------------------- UI THEMES & COLORS --------------------
dark_theme = {"bg": "#1e1e2f", "fg": "white", "btn_bg": "#3949ab", "btn_fg": "white"}
light_theme = {"bg": "#f5f5f5", "fg": "#1e1e1e", "btn_bg": "#dcdcdc", "btn_fg": "black"}
mood_colors = {
    "happy": "#ffe082", "sad": "#90caf9", "neutral": "#cfd8dc",
    "angry": "#ef9a9a", "surprise": "#ffcc80", "fear": "#b39ddb"
}
current_theme = dark_theme

# -------------------- MAIN APP --------------------
root = tk.Tk()
root.title("Smart Music Recommender")
root.geometry("650x750")
root.resizable(False, False)

# login/signup modal
def prompt_login_signup():
    modal = tk.Toplevel(root)
    modal.transient(root)
    modal.grab_set()
    modal.title("Login / Sign Up")
    modal.geometry("380x300")
    tk.Label(modal, text="Smart Music Recommender", font=("Arial", 16, "bold")).pack(pady=8)

    frame = tk.Frame(modal)
    frame.pack(pady=4)

    mode_var = tk.StringVar(value="login")  # or 'signup'

    def switch_mode():
        for w in frame.winfo_children():
            w.destroy()
        if mode_var.get() == "login":
            build_login()
        else:
            build_signup()

    def build_login():
        tk.Radiobutton(modal, text="Login", variable=mode_var, value="login", command=switch_mode).pack(anchor="w", padx=20)
        tk.Radiobutton(modal, text="Sign Up", variable=mode_var, value="signup", command=switch_mode).pack(anchor="w", padx=20)
        tk.Label(frame, text="Username:").grid(row=0, column=0, sticky="e")
        user_entry = tk.Entry(frame)
        user_entry.grid(row=0, column=1, pady=4)
        tk.Label(frame, text="Password:").grid(row=1, column=0, sticky="e")
        pass_entry = tk.Entry(frame, show="*")
        pass_entry.grid(row=1, column=1, pady=4)
        msg = tk.Label(frame, text="", fg="red")
        msg.grid(row=2, column=0, columnspan=2)

        def do_login():
            username = user_entry.get().strip().lower()
            password = pass_entry.get()
            if validate_user(username, password):
                modal.destroy()
                initialize_main_ui(username)
            else:
                msg.config(text="Invalid credentials")

        def do_signup():
            username = user_entry.get().strip().lower()
            password = pass_entry.get()
            if not username or not password:
                msg.config(text="Fill both")
                return
            if create_user(username, password):
                msg.config(text="Created! Please login.", fg="green")
                mode_var.set("login")
                switch_mode()
            else:
                msg.config(text="Username exists")

        action_btn = tk.Button(frame, text="Submit", width=20)
        action_btn.grid(row=3, column=0, columnspan=2, pady=6)

        def update_action():
            if mode_var.get() == "login":
                action_btn.config(text="Login", command=do_login)
            else:
                action_btn.config(text="Sign Up", command=do_signup)
        update_action()

        mode_var.trace_add("write", lambda *args: update_action())

    def build_signup():
        build_login()  # same builder toggles

    switch_mode()
    root.wait_window(modal)

# Preference & main UI placeholders (populated after auth)
greeting_label = None
mood_label = None
command_label = None
language_var = None
artist_var = None
video_frame = None
rec_text = None
current_user = None

def initialize_main_ui(username):
    global greeting_label, mood_label, command_label, language_var, artist_var, video_frame, rec_text, current_user
    current_user = username

    for widget in root.winfo_children():
        widget.destroy()

    # Top
    tk.Label(root, text=f"Welcome, {username.capitalize()}!", font=("Arial", 18, "bold")).pack(anchor="w", padx=12, pady=6)

    # Labels
    greeting_label = tk.Label(root, text="", font=("Arial", 16, "bold"))
    greeting_label.pack(pady=4)
    mood_label = tk.Label(root, text="Detected Mood: None", font=("Arial", 12))
    mood_label.pack(pady=2)
    command_label = tk.Label(root, text="Command: None", font=("Arial", 12))
    command_label.pack(pady=2)

    # Preferences
    pref_frame = tk.Frame(root)
    pref_frame.pack(pady=8, fill="x", padx=20)
    tk.Label(pref_frame, text="Language:").grid(row=0, column=0, sticky="e")
    lang_default, artist_default = get_preferences(username)
    language_var = tk.StringVar(value=lang_default)
    language_entry = tk.Entry(pref_frame, textvariable=language_var)
    language_entry.grid(row=0, column=1, padx=5)
    tk.Label(pref_frame, text="Artist:").grid(row=0, column=2, sticky="e")
    artist_var = tk.StringVar(value=artist_default)
    artist_entry = tk.Entry(pref_frame, textvariable=artist_var)
    artist_entry.grid(row=0, column=3, padx=5)
    def save_prefs():
        update_preferences_db(username, language_var.get(), artist_var.get())
        speak("Preferences saved", "en")
    tk.Button(pref_frame, text="Save Preferences", command=save_prefs).grid(row=0, column=4, padx=6)

    # Camera
    video_frame = tk.Label(root)
    video_frame.pack(pady=6)

    # Controls
    controls = tk.Frame(root)
    controls.pack(pady=4)
    tk.Button(controls, text="Scan Your Face", command=lambda: trigger_scan(username)).grid(row=0, column=0, padx=5)
    tk.Button(controls, text="Talk to Assistant", command=voice_command_handler).grid(row=0, column=1, padx=5)
    tk.Button(controls, text="Toggle Theme", command=toggle_theme).grid(row=0, column=2, padx=5)
    tk.Button(controls, text="Logout", command=logout).grid(row=0, column=3, padx=5)

    # Recommendation box
    rec_frame = tk.Frame(root)
    rec_frame.pack(pady=10, fill="x", padx=10)
    tk.Label(rec_frame, text="Last Recommendation:", font=("Arial", 14)).pack(anchor="w")
    rec_text = tk.Text(rec_frame, height=5, bg="#1f1f2f", fg="white", wrap="word")
    rec_text.pack(fill="x")

    # Start processes
    threading.Thread(target=greeting_sequence, daemon=True).start()
    threading.Thread(target=camera_loop, args=(username,), daemon=True).start()

# -------------------- UTILITIES --------------------
def update_mood_ui(mood):
    color = mood_colors.get(mood, current_theme["bg"])
    root.configure(bg=color)
    if mood_label:
        mood_label.config(bg=color)
    if greeting_label:
        greeting_label.config(bg=color)
    if command_label:
        command_label.config(bg=color)

def personalized_comment(mood):
    if mood == "happy":
        return "Ohh you look happy, such a good smile you have!"
    if mood == "sad":
        return "You seem a bit down. Let me play something uplifting for you."
    if mood == "angry":
        return "Take a deep breath, I can play something to calm you."
    if mood == "surprise":
        return "Wow, something surprised you! Here's a song to match the vibe."
    return "I see how you are feeling. Here's something for you."

def greeting_sequence():
    hour = datetime.now().hour
    if hour < 12:
        greet = "Good morning"
    elif hour < 18:
        greet = "Good afternoon"
    else:
        greet = "Good evening"
    if greeting_label:
        greeting_label.config(text=greet + " 🎵")
    speak(f"{greet}, welcome to Smart Music Recommender!", 'en')
    log_event(f"Greeted user: {greet}")

def display_recommendation(sugg):
    if not rec_text:
        return
    rec_text.delete("1.0", tk.END)
    if not sugg:
        rec_text.insert(tk.END, "No suggestion.\n")
        return
    s = sugg[0]
    rec_text.insert(tk.END, f"Title: {s['title']}\nArtist: {s['artist']}\nLanguage: {s['language']}\nMood: {s['mood']}\nURL: {s['url']}\n")

# -------------------- CAMERA / EMOTION --------------------
last_mood = None
last_suggest_time = 0
MOOD_COOLDOWN_SECONDS = 30

def process_camera_frame(frame, username):
    global last_mood, last_suggest_time
    current_time = time.time()
    if current_time - last_suggest_time < 5:
        return
    try:
        result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        mood = result[0]['dominant_emotion'].lower()
    except Exception as e:
        mood = "neutral"
        print("Emotion analysis error:", e)
    if mood_label:
        mood_label.config(text=f"Detected Mood: {mood.capitalize()}")
    update_mood_ui(mood)
    log_event(f"Detected mood: {mood}")
    if mood != last_mood or (current_time - last_suggest_time) >= MOOD_COOLDOWN_SECONDS:
        comment = personalized_comment(mood)
        speak(comment, 'en')
        lang, art = get_preferences(username)
        suggestion = suggest_music(mood, language=lang, artist=art)
        display_recommendation(suggestion)
        last_mood = mood
        last_suggest_time = current_time

def camera_loop(username=None):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        messagebox.showerror("Camera Error", "Cannot access camera.")
        return

    def _update():
        ret, frame = cap.read()
        if ret:
            display_frame = cv2.flip(frame, 1)
            img_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb).resize((500, 380))
            if video_frame:
                imgtk = ImageTk.PhotoImage(image=img_pil)
                video_frame.imgtk = imgtk
                video_frame.config(image=imgtk)
            if username:
                process_camera_frame(frame, username)
        root.after(30, _update)

    _update()

# -------------------- ACTIONS --------------------
def trigger_scan(username):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        messagebox.showerror("Camera Error", "Cannot access camera.")
        return
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return
    try:
        result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        mood = result[0]['dominant_emotion'].lower()
    except:
        mood = "neutral"
    if mood_label:
        mood_label.config(text=f"Detected Mood: {mood.capitalize()}")
    log_event(f"Scanned mood: {mood}")
    comment = personalized_comment(mood)
    speak(comment, "en")
    lang, art = get_preferences(username)
    suggestion = suggest_music(mood, language=lang, artist=art)
    display_recommendation(suggestion)

def voice_command_handler():
    cmd, lang = listen()
    if command_label:
        command_label.config(text=f"Command: {cmd}")
    log_event(f"Voice command: {cmd}")
    if not current_user:
        return
    if any(x in cmd for x in ["gym", "जिम"]):
        speak("Here are some gym songs", lang if lang in ['hi', 'en'] else 'en')
        suggestion = suggest_music("happy", language=language_var.get(), artist=artist_var.get())
    elif any(x in cmd for x in ["relax", "आराम", "आराम से"]):
        speak("Here are some relaxing songs", lang if lang in ['hi', 'en'] else 'en')
        suggestion = suggest_music("relaxing", language=language_var.get(), artist=artist_var.get())
    elif any(x in cmd for x in ["happy", "खुश"]):
        suggestion = suggest_music("happy", language=language_var.get(), artist=artist_var.get())
    elif any(x in cmd for x in ["sad", "दुखी"]):
        suggestion = suggest_music("sad", language=language_var.get(), artist=artist_var.get())
    else:
        speak("Sorry, I didn't understand.", lang if lang in ['hi', 'en'] else 'en')
        suggestion = []
    display_recommendation(suggestion)

def toggle_theme():
    global current_theme
    current_theme = light_theme if current_theme == dark_theme else dark_theme
    # minimal apply
    root.configure(bg=current_theme["bg"])

def logout():
    python = os.sys.executable
    os.execv(python, [python] + os.sys.argv)  # restart app to show login again

# -------------------- START --------------------
init_db()
# ensure sample songs.csv if missing
if not os.path.exists(SONGS_CSV):
    sample = pd.DataFrame([
        {"mood": "happy", "title": "Happy - Pharrell Williams", "artist": "Pharrell Williams", "language": "english", "url": "https://www.youtube.com/watch?v=y6Sxv-sUYtM"},
        {"mood": "sad", "title": "Someone Like You", "artist": "Adele", "language": "english", "url": "https://www.youtube.com/watch?v=hLQl3WQQoQ0"},
        {"mood": "gym", "title": "Stronger", "artist": "Kanye West", "language": "english", "url": "https://www.youtube.com/watch?v=PsO6ZnUZI0g"},
        {"mood": "relaxing", "title": "Weightless", "artist": "Marconi Union", "language": "english", "url": "https://www.youtube.com/watch?v=UfcAVejslrU"},
        {"mood": "happy", "title": "Dil Chori", "artist": "Yo Yo Honey Singh", "language": "hindi", "url": "https://www.youtube.com/watch?v=ZbpD04zuwhQ"},
    ])
    sample.to_csv(SONGS_CSV, index=False)

# window close cleanup
def on_close():
    stop_speaker()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

# show login/signup first
prompt_login_signup()

# if user got initialized_main_ui after login, start mainloop
root.mainloop()
