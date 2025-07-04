"""
Jarvis Personal Assistant
Updated: 2025-06-18

• SQLite memory
• Cached 7-day weather injected into LLM prompt
• YouTube only on explicit “play … on YouTube”
• Self-assessment routed through LLM
• Voice/Text/SMS (audio MMS → MY_NUMBER)
• Spotify:
    ─ "play …" / "put on …"  → explicit play
    ─ "put something on" / "play me some music" / "next song" → AI picks song
"""

import os, time, socket, webbrowser, requests, sqlite3, threading, queue, sys
from datetime import datetime, timedelta, timezone
from functools import wraps
from dotenv import load_dotenv

# ───────── GUI ─────────
import tkinter as tk
from PIL import Image, ImageTk, ImageSequence

# ───────── LLM / LangChain ─────────
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama
from langchain.memory import ConversationBufferMemory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
import keyboard


# ───────── Assistant modules ─────────
from recognize import listen_for_command
from new_voice import speak_text
from spotify_functions import play_music, play_song
from text_reminders import send_message_with_audio, check_for_sms_replies, send_message
from file_output import generate_audio_mp3

load_dotenv()

# ────────────────────────────────────────────────────────────────────────────────
#                                    GUI
# ────────────────────────────────────────────────────────────────────────────────
class JarvisUI:
    """Tight Jarvis UI: fixed GIF, 2-line message log, compact input field, no black space."""

    def __init__(self, gif_path: str, incoming_q: queue.Queue, outgoing_q: queue.Queue):
        self.in_q, self.out_q = incoming_q, outgoing_q

        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S.")
        self.root.configure(bg="#050505")
        self.root.geometry("380x350")  # ✅ Fits everything tightly
        self.root.resizable(False, False)

        # ───── GIF (fixed size) ─────
        self.gif = Image.open(gif_path)
        scale_factor = 0.7  # shrink to 70% of original size
        self.frames = [
            ImageTk.PhotoImage(f.convert("RGBA").resize(
                (int(f.width * scale_factor), int(f.height * scale_factor)),
                Image.Resampling.LANCZOS
            ))
            for f in ImageSequence.Iterator(self.gif)
        ]
        self.gif_lbl = tk.Label(self.root, bg="#050505", height=200)
        self.gif_lbl.pack(pady=(5, 0))
        self._animate(0)

        # ───── Message Box (2 lines max) ─────
        text_frame = tk.Frame(self.root, bg="#050505")
        text_frame.pack(padx=20, pady=(2, 0), fill="x")

        self.msg_box = tk.Text(
            text_frame,
            wrap="word",
            bg="#0a0a0a",
            fg="#00c8ff",
            font=("Consolas", 9),    # ✅ Smaller font
            relief="flat",
            height=6,                
            width=46,
            state="disabled"
        )
        self.msg_box.pack(side="left", fill="x")

        scrollbar = tk.Scrollbar(text_frame, command=self.msg_box.yview)
        scrollbar.pack(side="right", fill="y")
        self.msg_box.config(yscrollcommand=scrollbar.set)

        # ───── Input Field (pinned bottom) ─────
        self.input_frame = tk.Frame(self.root, bg="#050505")
        self.input_frame.pack(pady=(0, 0))

        self.entry = tk.Entry(
            self.input_frame,
            bg="#111820",
            fg="#00c8ff",
            insertbackground="#00c8ff",
            highlightthickness=0,
            relief="flat",
            font=("Consolas", 11),
            width=30,
        )
        self.entry.grid(row=0, column=0, padx=(0, 5))
        self.entry.bind("<Return>", self._on_send)

        self.send_btn = tk.Button(
            self.input_frame,
            text="Send",
            command=self._on_send,
            fg="#00c8ff",
            bg="#050505",
            activebackground="#0a0a0a",
            relief="flat",
        )
        self.send_btn.grid(row=0, column=1)

        self._poll_queues()

    def _animate(self, idx: int):
        self.gif_lbl.configure(image=self.frames[idx])
        self.root.after(30, self._animate, (idx + 1) % len(self.frames))

    def _on_send(self, *_):
        text = self.entry.get().strip()
        if text:
            self.out_q.put(text)
            self.entry.delete(0, "end")

    def _poll_queues(self):
        try:
            while True:
                msg = self.in_q.get_nowait()
                self._append_message("Jarvis", msg)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queues)

    def _append_message(self, sender: str, message: str):
        self.msg_box.config(state="normal")
        self.msg_box.insert("end", f"{sender}: {message}\n")
        self.msg_box.see("end")
        self.msg_box.config(state="disabled")

    def hide_entry(self):
        self.input_frame.pack_forget()

    def show_entry(self):
        self.input_frame.pack(pady=(0, 0))

    def run(self):
        self.root.mainloop()


# ────────────────────────────────────────────────────────────────────────────────
#                               Core Assistant
# ────────────────────────────────────────────────────────────────────────────────
# Connectivity ---------------------------------------------------------------
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

# Weather caching ------------------------------------------------------------
WEATHER_CACHE = {"forecast": None, "hash": None, "fetched": None}
WEATHER_TTL   = timedelta(hours=1)


def _hash(txt: str) -> str:
    import hashlib
    return hashlib.sha1(txt.encode()).hexdigest()


@requires_online
def fetch_weekly_weather() -> str:
    try:
        loc = requests.get("http://ip-api.com/json", timeout=3).json()
        lat, lon = loc["lat"], loc["lon"]
        city, region = loc["city"], loc["regionName"]
    except Exception:
        lat, lon, city, region = 39.3722, -76.9684, "Default Location", "MD"

    point   = requests.get(f"https://api.weather.gov/points/{lat},{lon}",
                           timeout=5).json()
    periods = (requests.get(point["properties"]["forecast"], timeout=5)
               .json()["properties"]["periods"][:14])

    daily = {}
    for p in periods:
        name     = p["name"]
        day_name = name.split()[0]
        if day_name.lower() == "tonight":
            day_name = datetime.now(timezone.utc).strftime("%A") + " Night"
        daily.setdefault(day_name,
                         f"{p['temperature']}{p['temperatureUnit']} – {p['shortForecast']}")

    summary = "; ".join([f"{d}: {s}" for d, s in list(daily.items())[:7]])
    return f"7-day forecast for {city}, {region}: {summary}."


def get_cached_weather() -> str:
    now = datetime.now(timezone.utc)
    if WEATHER_CACHE["forecast"] and WEATHER_CACHE["fetched"] \
       and now - WEATHER_CACHE["fetched"] < WEATHER_TTL:
        return WEATHER_CACHE["forecast"]

    fresh = fetch_weekly_weather()
    if _hash(fresh) != WEATHER_CACHE.get("hash"):
        WEATHER_CACHE.update({"forecast": fresh,
                              "hash": _hash(fresh),
                              "fetched": now})
    return WEATHER_CACHE["forecast"]

# Memory / SQLite -----------------------------------------------------------
DB_FILE     = "jarvis_memory.db"
TOKEN_LIMIT = 2000
memory      = ConversationBufferMemory(memory_key="chat_history",
                                       return_messages=True)


def _init_db():
    with sqlite3.connect(DB_FILE) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS memory (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp   TEXT,
                        user_input  TEXT,
                        ai_output   TEXT)""")


def _load_db():
    with sqlite3.connect(DB_FILE) as c:
        rows = c.execute(
            "SELECT user_input, ai_output FROM memory ORDER BY id DESC LIMIT ?",
            (TOKEN_LIMIT,),
        ).fetchall()[::-1]
    for u, a in rows:
        memory.save_context({"input": f"{u}"}, {"output": f"{a}"})


def _save_entry(u: str, a: str):
    with sqlite3.connect(DB_FILE) as c:
        c.execute(
            "INSERT INTO memory (user_input, ai_output) VALUES (?, ?)",
            (u, a),
        )


_init_db()
_load_db()

# Persona & LLM -------------------------------------------------------------
def persona() -> str:
    local_time = datetime.now().strftime("%A, %B %d %Y %I:%M %p")
    return (
        f"You are Jarvis, my personal assistant. I am Ray, I created you. Traits: professional, "
        f"efficient, witty but respectful. Call me sir. Today is {local_time}. "
        f"Weekly forecast: {WEATHER_CACHE.get('forecast', 'unavailable')}."
        f"You live in my laptop and have access to the following tools, and no others: AI Voice, Spotify, Youtube, Weather data, SMS texting, seld assessments, and increased memory."
        f"I prefer classic rock, alternative, indie, and yacht rock music, but you can play any genre."
        f"You can only use these tools when I explicitly ask you to do so. We're a partnership, combinging your AI brain with my own human intelligence."
        f"Keep your responses very conise, unless I ask for more detail. You should speak conversationally, and allow me room to speak. You're primarily a voice assistant."
        f"Do not use any emojis or other symbols in your responses."
        f"Do not use any markdown formatting in your responses. Keep your responses in sentence format, do not use actists or bullet points."
        f"Everything we say is one long conversation, so do not repeat yourself or previous messages."
        f"Remember you are Jarvis, my personal assistant, and I am Ray."
        f"Your memory database marks each interaction with a timestamp, do NOT include the timestamp in your response! it is only for your record"
    )


def llm_reply(user_input: str) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", persona()),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ]
    )

    chain = (
        RunnablePassthrough.assign(
            chat_history=lambda x: memory.load_memory_variables(x)["chat_history"]
        )
        | prompt
        | ChatOllama(model="dolphin3:8b")
        | StrOutputParser()
    )

    return chain.invoke({"input": user_input}).strip()



# Online helpers ------------------------------------------------------------
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
            "https://www.youtube.com/results?search_query="
            + cleaned.replace(" ", "+")
        ).text
        vid = html.split("/watch?v=")[1].split('"')[0]
        webbrowser.open(f"https://www.youtube.com/watch?v={vid}")
        return f"Opening {cleaned} on YouTube, sir."
    except Exception:
        return "Sorry sir, I couldn't find that video."

# Spotify triggers ----------------------------------------------------------
EXPLICIT_PLAY_PREFIXES = ("play ", "put on ", "next song")
AI_SONG_TRIGGERS       = ("put something on", "play me some music", "next song")

# Command keys --------------------------------------------------------------
KEYS = {
    "weather": ["weather", "forecast"],
    "youtube": ["play", "youtube"],
}

# Router --------------------------------------------------------------------
def route(user_input: str):
    text = user_input.lower()

    # Weather
    if any(k in text for k in KEYS["weather"]):
        forecast = get_cached_weather()
        weather_reply = llm_reply(
            "Weather data (internal): "
            + forecast
            + ". Summarize for me in a friendly, concise way, in sentence format."
        )
        memory.save_context({"input": user_input}, {"output": weather_reply})
        _save_entry(user_input, weather_reply)
        return weather_reply

    # YouTube (explicit)
    if "play" in text and "on youtube" in text:
        return play_youtube(user_input)

    # AI-picked Spotify song
    if any(trigger in text for trigger in AI_SONG_TRIGGERS):
        prompt = (
            "Pick a song. Do not include the artist name or anything else. "
            "Only respond with the song title."
        )
        song = llm_reply(prompt)
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
        analysis = llm_reply(diagnostic)
        memory.save_context({"input": user_input}, {"output": analysis})
        _save_entry(user_input, analysis)
        return analysis

    # No special route
    return None

# Chat loop -----------------------------------------------------------------
def chat(gui: JarvisUI, incoming_q: queue.Queue, outgoing_q: queue.Queue):
    mode = "text"
    incoming_q.put("Jarvis initialized. Say 'quit' to exit.")

    while True:
        try:
            # ───── Input depending on mode ─────
            if mode == "voice":
                gui.hide_entry()
                user_in = listen_for_command()
                if "jarvis" not in user_in.lower():
                    continue
            elif mode in ("texting", "voice_texting"):
                gui.hide_entry()
                if not is_online():
                    time.sleep(5)
                    continue
                user_in = check_for_sms_replies("4438964231@vzwpix.com")
            else:  # text / headphone
                gui.show_entry()
                user_in = outgoing_q.get().strip()

            if not user_in:
                continue
            if user_in.lower() == "quit":
                incoming_q.put("Good-bye, sir.")
                break

            # ───── Mode switching ─────
            switches = {
                "switch to voice": "voice",
                "switch to text": "text",
                "switch to headphone": "headphone",
                "switch to phone": "voice_texting",
            }

            # Lowercase input once for consistency
            user_in_lower = user_in.lower()

            # Flag to check if a mode was switched
            mode_switched = False

            for phrase, new_mode in switches.items():
                if phrase in user_in_lower:
                    mode = new_mode
                    incoming_q.put(f"Mode → {mode.upper()}")
                    mode_switched = True
                    break

            if mode_switched:
                continue

            resp = route(user_in)



            if resp == "__handled__":
                continue  # ✅ Spotify was handled; no need to show or speak anything

            if resp is None:
                resp = llm_reply(user_in)
                memory.save_context({"input": user_in}, {"output": resp})
                _save_entry(user_in, resp)

            incoming_q.put(resp)


            # Voice / SMS output
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

def ai_generated_wake_up():
    print("⏰ Wake-up triggered: generating song...")
    prompt = (
        "Pick a song. Do not include the artist name or anything else. "
        "Only respond with the song title."
    )
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
        f"Give me a nice morning greeting, I'm probably just waking up and very tired. Give me the current time and a nice run-down of the weather."
        f"You can mess with me a little bit, but keep it friendly and respectful."
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


# ────────────────────────────────────────────────────────────────────────────────
#                                   Bootstrap
# ────────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    gif_path = os.path.join(os.path.dirname(__file__), "JARVIS.gif")
    if not os.path.exists(gif_path):
        sys.exit("❌  JARVIS.gif not found – place it in the same folder.")

    gui_in_q  = queue.Queue()   # assistant → GUI
    gui_out_q = queue.Queue()   # GUI → assistant

    ui = JarvisUI(gif_path, gui_in_q, gui_out_q)

    # ✅ Start wake-up monitor in background
    threading.Thread(target=wake_up_monitor, daemon=True).start()

    # Run assistant loop in background
    threading.Thread(target=chat,
                     args=(ui, gui_in_q, gui_out_q),
                     daemon=True).start()
    

    ui.run()
