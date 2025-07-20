import os
import time
import re
from db import memory, _save_entry
from weather import get_cached_weather, WEATHER_CACHE
from new_voice import speak_text
from recognize import listen_for_command
from spotify_functions import play_music, play_song
from text_reminders import (
    send_message_with_audio,
    check_for_sms_replies,
    send_message,
)
from file_output import generate_audio_mp3
from alarms import set_alarm, set_timer
from datetime import datetime

# === NEW: RAG Model ===
from rag import ChatDocument
rag_model = ChatDocument(uploads_dir="watch")  # assuming "watch" folder is used
rag_model.watch_folder()

# Online helpers ------------------------------------------------------------
import socket
import requests
import webbrowser
from functools import wraps

def is_online(host="www.google.com", port=80, timeout=2) -> bool:
    try:
        socket.create_connection((host, port), timeout=timeout)
        return True
    except OSError:
        return False

def requires_online(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_online():
            msg = (
                "Sir, I'm currently offline and cannot access online services. "
                "Please try again once connectivity is restored."
            )
            try:
                speak_text(msg)
            except Exception:
                pass
            return msg
        return func(*args, **kwargs)
    return wrapper

@requires_online
def play_youtube(q: str) -> str:
    if "on youtube" not in q.lower():
        return "Sir, say 'play … on YouTube' to open a video."
    cleaned = (
        q.lower()
        .replace("play", "")
        .replace("on youtube", "")
        .replace("youtube", "")
        .strip()
    )
    try:
        html = requests.get(
            "https://www.youtube.com/results?search_query=" + cleaned.replace(" ", "+")
        ).text
        vid = html.split("/watch?v=")[1].split('"')[0]
        webbrowser.open(f"https://www.youtube.com/watch?v={vid}")
        return f"Opening {cleaned} on YouTube, sir."
    except Exception:
        return "Sorry sir, I couldn't find that video."

# Spotify triggers
EXPLICIT_PLAY_PREFIXES = ("play ", "put on ", "next song")
AI_SONG_TRIGGERS = ("put something on", "play me some music", "next song")

# Command keys
KEYS = {
    "weather": ["weather", "forecast"],
    "youtube": ["play", "youtube"],
}

def route(user_input: str):
    text = user_input.lower()
    now = datetime.now().strftime("%A, %B %d %Y %I:%M %p")

    # Weather
    if any(k in text for k in KEYS["weather"]):
        forecast = get_cached_weather()
        weather_reply = rag_model.llm_reply(
            "Weather data (internal): "
            + forecast
            + ". Use this information to best respond to my query, ensure you respond with exactly what I asked. Today is " + now + "."
        )
        memory.save_context({"input": user_input}, {"output": weather_reply})
        _save_entry(user_input, weather_reply)
        return weather_reply

    # YouTube
    if "play" in text and "on youtube" in text:
        return play_youtube(user_input)

    # AI-picked Spotify song
    if any(trigger in text for trigger in AI_SONG_TRIGGERS):
        prompt = (
            "Pick a song. Do not include the artist name or anything else. "
            "Only respond with the song title Please mix up the song choice, Pick from my favorites"
        )
        song = rag_model.llm_reply(prompt)
        memory.save_context({"input": user_input}, {"output": song})
        _save_entry(user_input, song)
        os.system("spotify &")
        time.sleep(2)
        play_song(song)
        speak_text(f"Playing {song} on Spotify.")
        return "__handled__"

    # Explicit Spotify song
    if any(trigger in text for trigger in EXPLICIT_PLAY_PREFIXES) and "on youtube" not in text:
        os.system("spotify &")
        time.sleep(2)
        play_music(user_input)
        return "__handled__"

    # Self-assessment
    if "assessment" in text and "run" in text:
        net = "online" if is_online() else "offline"
        diagnostic = (
            f"Self-assessment: weather cache "
            f"{'set' if WEATHER_CACHE['forecast'] else 'empty'}, "
            f"network {net}, memory OK, LLM responsive."
        )
        analysis = rag_model.llm_reply(diagnostic)
        memory.save_context({"input": user_input}, {"output": analysis})
        _save_entry(user_input, analysis)
        return analysis

    # Set alarm
    alarm_match = re.search(r"wake me up at (\d{1,2}:\d{2})", text)
    if alarm_match:
        alarm_time = alarm_match.group(1)
        return set_alarm(alarm_time)

    # Set timer
    timer_match = re.search(r"set a timer for (\d+) minute", text)
    if timer_match:
        minutes = int(timer_match.group(1))
        return set_timer(minutes)

    return None

def chat(gui, incoming_q, outgoing_q):
    mode = "text"
    incoming_q.put("Jarvis initialized. Say 'quit' to exit.")

    while True:
        try:
            # === INPUT ===
            if mode == "voice":
                gui.hide_entry()
                user_in = listen_for_command()
                if "jarvis" not in user_in.lower():
                    continue
            elif mode == "hardware":
                gui.hide_entry()
                from vision import capture_image
                user_in = listen_for_command()
                if not user_in:
                    continue
                image = capture_image()
            elif mode in ("texting", "voice_texting"):
                gui.hide_entry()
                if not is_online():
                    time.sleep(5)
                    continue
                user_in = check_for_sms_replies("4438964231@vzwpix.com")
            else:  # "text" or "headphone"
                gui.show_entry()
                user_in = outgoing_q.get().strip()

            if not user_in:
                continue
            if user_in.lower() == "quit":
                incoming_q.put("Good-bye, sir.")
                break

            # === MODE SWITCHES ===
            switches = {
                "switch to voice": "voice",
                "switch to text": "text",
                "switch to headphone": "headphone",
                "switch to phone": "voice_texting",
                "switch to hardware": "hardware",
            }
            user_in_lower = user_in.lower()
            mode_switched = False
            for phrase, new_mode in switches.items():
                if phrase in user_in_lower:
                    mode = new_mode
                    incoming_q.put(f"Mode → {mode.upper()}")
                    mode_switched = True
                    break
            if mode_switched:
                continue

            # === RESPONSE ===
            if mode == "hardware":
                from vision import run_vision_prompt
                resp = run_vision_prompt(image, user_in)
                speak_text(resp)
            else:
                resp = route(user_in)
                if resp == "__handled__":
                    continue
                if resp is None:
                    resp = rag_model.llm_reply(user_in)

            memory.save_context({"input": user_in}, {"output": resp})
            _save_entry(user_in, resp)

            # === OUTPUT ===
            incoming_q.put(resp)

            if mode in ("voice", "headphone"):
                speak_text(resp)
            elif mode == "texting" and is_online():
                send_message(resp)
            elif mode == "voice_texting" and is_online():
                mp3 = generate_audio_mp3(resp)
                if mp3:
                    send_message_with_audio("Jarvis:", mp3)

        except KeyboardInterrupt:
            incoming_q.put("Session ended.")
            break
        except Exception as e:
            incoming_q.put(f"Jarvis error: {e}")
            continue

