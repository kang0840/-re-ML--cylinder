"""Local visual demo of the cylinder dataset capture screen.

This is for documenting the capture workflow on a PC without the Pi camera.
It deliberately does not save training images.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime


class CaptureDemo(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Smart Cylinder — YOLO Dataset Capture")
        self.geometry("900x620")
        self.configure(bg="#101827")
        self.class_name = tk.StringVar(value="A_CYLINDER")
        self.progress = 0
        self.running = False
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="Smart Cylinder Dataset Capture", font=("Segoe UI", 22, "bold"), fg="white", bg="#101827").pack(pady=(22, 4))
        tk.Label(self, text="YOLO A/B cylinder image collection", font=("Segoe UI", 11), fg="#9fb3c8", bg="#101827").pack()

        main = tk.Frame(self, bg="#101827")
        main.pack(fill="both", expand=True, padx=40, pady=26)
        preview = tk.Canvas(main, bg="#1d2939", width=570, height=355, highlightthickness=1, highlightbackground="#506680")
        preview.pack(side="left", fill="both", expand=True)
        preview.create_rectangle(150, 88, 420, 284, outline="#37d67a", width=3)
        preview.create_text(285, 160, text="CAMERA PREVIEW", fill="#d9e2ec", font=("Segoe UI", 18, "bold"))
        preview.create_text(285, 195, text="Cylinder positioned in frame", fill="#9fb3c8", font=("Segoe UI", 11))
        self.time_text = preview.create_text(520, 330, text="", fill="#37d67a", font=("Consolas", 10))

        controls = tk.Frame(main, bg="#172233", width=230)
        controls.pack(side="right", fill="y", padx=(22, 0))
        tk.Label(controls, text="Capture class", bg="#172233", fg="white", font=("Segoe UI", 12, "bold")).pack(pady=(25, 10))
        for value in ("A_CYLINDER", "B_CYLINDER"):
            tk.Radiobutton(controls, text=value, variable=self.class_name, value=value, bg="#172233", fg="white", selectcolor="#243b53", activebackground="#172233", activeforeground="white", font=("Segoe UI", 10)).pack(anchor="w", padx=28, pady=5)
        self.button = tk.Button(controls, text="Start 100-image capture", command=self.start, bg="#168d5c", fg="white", activebackground="#20b875", activeforeground="white", relief="flat", font=("Segoe UI", 10, "bold"), padx=14, pady=12)
        self.button.pack(pady=(35, 16))
        self.status = tk.Label(controls, text="Ready", justify="left", bg="#172233", fg="#9fb3c8", font=("Segoe UI", 10))
        self.status.pack(padx=20)
        self.preview = preview
        self.tick()

    def tick(self) -> None:
        self.preview.itemconfigure(self.time_text, text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.after(500, self.tick)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.progress = 0
        self.button.configure(state="disabled", text="Capturing...")
        self.capture_next()

    def capture_next(self) -> None:
        self.progress += 1
        self.status.configure(text=f"{self.class_name.get()}\nCaptured: {self.progress} / 100\nLabels: auto-generated")
        if self.progress < 100:
            self.after(45, self.capture_next)
        else:
            self.running = False
            self.button.configure(state="normal", text="Start 100-image capture")
            self.status.configure(text=f"{self.class_name.get()}\nCaptured: 100 / 100\nBatch complete")


if __name__ == "__main__":
    CaptureDemo().mainloop()
