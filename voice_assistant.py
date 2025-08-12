import speech_recognition as sr
import os
from gtts import gTTS
from langdetect import detect
import playsound

def speak(text, lang='en'):
    """Speak in given language (default English)"""
    tts = gTTS(text=text, lang=lang)
    file = "voice.mp3"
    tts.save(file)
    playsound.playsound(file)
    os.remove(file)

def listen():
    """Listen to user command in any language"""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        audio = r.listen(source)

        try:
            command = r.recognize_google(audio)
            lang = detect(command)
            print(f"Command: {command} | Detected Language: {lang}")
            return command.lower(), lang
        except sr.UnknownValueError:
            return "I didn't understand", 'en'
        except sr.RequestError:
            return "Service unavailable", 'en'
