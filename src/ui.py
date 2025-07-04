# ───────── GUI ─────────
import tkinter as tk
from PIL import Image, ImageTk, ImageSequence
import queue


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