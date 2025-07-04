import os
import sys
import queue
import threading

from ui import JarvisUI
from assistant import chat
from wakeup import wake_up_monitor

if __name__ == "__main__":
    gif_path = os.path.join(os.path.dirname(__file__), "JARVIS.gif")
    if not os.path.exists(gif_path):
        sys.exit("❌  JARVIS.gif not found – place it in the same folder.")

    gui_in_q = queue.Queue()
    gui_out_q = queue.Queue()

    ui = JarvisUI(gif_path, gui_in_q, gui_out_q)

    threading.Thread(target=wake_up_monitor, daemon=True).start()
    threading.Thread(target=chat, args=(ui, gui_in_q, gui_out_q), daemon=True).start()

    ui.run()
