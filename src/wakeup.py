import os
import time
import threading
from datetime import datetime

from persona import llm_reply
from spotify_functions import play_song
from new_voice import speak_text

def ai_generated_wake_up():
    print("⏰ Wake-up triggered: generating song...")
    prompt = "Pick a song. Do not include the artist name or anything else. Only respond with the song title."
    song = llm_reply(prompt)
    print(f"🎵 Playing: {song}")

    os.system("spotify &")
    time.sleep(2)
    play_song(song)

    print("⌨ Waiting for spacebar to stop music...")
    try:
        import keyboard
    except ImportError:
        os.system("pip install keyboard")
        import keyboard

    keyboard.wait("space")
    time.sleep(1)

    wake_prompt = (
        f"Give me a nice morning greeting, I'm probably just waking up and very tired. "
        f"Give me the current time and a nice run-down of the weather. "
        f"You can mess with me a little bit, but keep it friendly and respectful. "
        f"Also give me any reminders I have for today, if any."
    )
    full_msg = llm_reply(wake_prompt)
    speak_text(full_msg)


def wake_up_monitor():
    WAKE_UP_TIME = "09:15"
    while True:
        now = datetime.now().strftime("%H:%M")
        if now == WAKE_UP_TIME:
            threading.Thread(target=ai_generated_wake_up, daemon=True).start()
            break
        time.sleep(30)
