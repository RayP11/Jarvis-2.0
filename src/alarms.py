import os
import threading
import time
import keyboard  # pip install keyboard
from datetime import datetime

from persona import llm_reply
from new_voice import speak_text
from spotify_functions import play_song

def after_music_greeting(context_text=""):
    prompt = (
        f"I've just gotten back after you set a timer or alarm for me. "
        f"{context_text} Give me a friendly greeting, keep it concise and conversational."
    )
    greeting = llm_reply(prompt)
    speak_text(greeting)
    return greeting

def set_alarm(alarm_time_str):
    def alarm_task():
        print(f"⏰ Alarm set for {alarm_time_str}")
        while True:
            now = datetime.now().strftime("%H:%M")
            if now == alarm_time_str:
                speak_text("Good morning sir, it's time to wake up!")
                os.system("spotify &")
                time.sleep(2)
                song_prompt = "Pick a song. Only respond with the song title."
                song = llm_reply(song_prompt)
                play_song(song)

                print("⌨ Waiting for spacebar to stop music...")
                keyboard.wait("space")
                time.sleep(1)

                after_music_greeting("This was an alarm to wake me up.")
                break
            time.sleep(30)

    threading.Thread(target=alarm_task, daemon=True).start()
    return f"Alarm set for {alarm_time_str}, sir."

def set_timer(minutes):
    def timer_task():
        print(f"⏳ Timer started for {minutes} minutes")
        time.sleep(minutes * 60)
        speak_text(f"Sir, your {minutes}-minute timer is up!")
        os.system("spotify &")
        time.sleep(2)
        song_prompt = "Pick a song to alert me. Only respond with the song title."
        song = llm_reply(song_prompt)
        play_song(song)

        print("⌨ Waiting for spacebar to stop music...")
        keyboard.wait("space")
        time.sleep(1)

        after_music_greeting("This was a timer you set for me.")

    threading.Thread(target=timer_task, daemon=True).start()
    return f"Timer set for {minutes} minutes, sir."
