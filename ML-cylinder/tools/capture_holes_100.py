"""Pi camera preview and batch photo collection; no YOLO or auto labels."""

from datetime import datetime
from pathlib import Path
import math
import time
from uuid import uuid4


def validate_batch(count, interval):
    count = int(count)
    interval = float(interval)
    if not 1 <= count <= 1000:
        raise ValueError("촬영 수는 1~1000장이어야 합니다.")
    if not math.isfinite(interval) or interval < 0.2:
        raise ValueError("촬영 간격은 0.2초 이상이어야 합니다.")
    return count, interval


def save_photo(image, directory, label, session, index):
    """Save exclusively: filenames classify photos, not bounding-box labels."""
    if label not in {"small_hole", "large_hole", "no_hole"}:
        raise ValueError("촬영 대상이 올바르지 않습니다.")
    destination = Path(directory)
    if not destination.is_dir():
        raise ValueError("저장 폴더가 없습니다.")
    path = destination / f"{label}_{session}_{index:04d}.jpg"
    # Refuse overwrite even if two processes choose the same filename.
    with path.open("xb") as stream:
        image.save(stream, format="JPEG", quality=95)
    return path


def main():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from PIL import Image, ImageTk
    from picamera2 import Picamera2

    root = tk.Tk()
    root.title("IMX500 사진 수집 — YOLO 미사용")
    root.geometry("1000x820")
    root.minsize(680, 580)
    selected = tk.StringVar(value="작은 구멍")
    count_text = tk.StringVar(value="100")
    interval_text = tk.StringVar(value="1.0")
    directory = tk.StringVar(value=str(Path.home() / "Desktop"))
    status = tk.StringVar(value="미리보기 준비 중 — 기존 카메라 프로그램은 종료하세요.")
    state = {"running": False, "closed": False, "saved": 0}
    labels = {
        "작은 구멍": "small_hole",
        "큰 구멍": "large_hole",
        "구멍 없음": "no_hole",
    }

    ttk.Label(root, text="구멍 학습용 사진 수집", font=("sans-serif", 18, "bold")).pack(
        pady=10
    )
    preview = ttk.Label(root, anchor="center")
    preview.pack(fill="both", expand=True)
    controls = ttk.Frame(root)
    controls.pack(fill="x", padx=16, pady=8)
    ttk.Label(controls, text="촬영 대상").grid(row=0, column=0)
    choice = ttk.Combobox(
        controls, textvariable=selected, values=list(labels), state="readonly", width=12
    )
    choice.grid(row=0, column=1, padx=6)
    ttk.Label(controls, text="촬영 수").grid(row=0, column=2)
    count_entry = ttk.Entry(controls, textvariable=count_text, width=6)
    count_entry.grid(row=0, column=3, padx=6)
    ttk.Label(controls, text="간격(초)").grid(row=0, column=4)
    interval_entry = ttk.Entry(controls, textvariable=interval_text, width=6)
    interval_entry.grid(row=0, column=5, padx=6)
    ttk.Label(root, textvariable=directory, wraplength=900).pack(pady=3)
    ttk.Label(root, textvariable=status, wraplength=900).pack(pady=8)
    ttk.Label(
        root,
        text="자동 박스/라벨·A/B 판정 없음. 테스트 사진은 별도 촬영 회차로 확보하세요.",
        wraplength=900,
    ).pack(pady=3)
    buttons = ttk.Frame(root)
    buttons.pack(pady=10)

    def set_running(value):
        state["running"] = value
        start_button.configure(state="disabled" if value else "normal")
        folder_button.configure(state="disabled" if value else "normal")
        choice.configure(state="disabled" if value else "readonly")
        for entry in (count_entry, interval_entry):
            entry.configure(state="disabled" if value else "normal")

    def select_folder():
        folder = filedialog.askdirectory(parent=root, title="기존 저장 폴더 선택")
        if folder:
            directory.set(folder)

    def start_batch():
        try:
            count, interval = validate_batch(count_text.get(), interval_text.get())
            if not Path(directory.get()).is_dir():
                raise ValueError("기존 저장 폴더를 선택하세요.")
        except (ValueError, OverflowError) as error:
            messagebox.showerror("설정 확인", str(error), parent=root)
            return
        state.update(
            saved=0,
            count=count,
            interval=interval,
            label=labels[selected.get()],
            directory=directory.get(),
            session=datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:10],
            next_photo=time.monotonic() + 3,
        )
        set_running(True)
        status.set("3초 뒤 촬영 시작 — 제품을 배치하세요.")

    def stop_batch():
        set_running(False)
        status.set(f"촬영 중지 · 저장된 {state['saved']}장은 보존됩니다.")

    camera = Picamera2(0)

    def close():
        state["closed"] = True
        state["running"] = False
        root.destroy()

    def tick():
        if state["closed"]:
            return
        try:
            # capture_image handles Picamera2's RGB/BGR pixel layout.
            # Save the full image; only the displayed copy is resized.
            image = camera.capture_image("main")
            now = time.monotonic()
            if state["running"] and now >= state["next_photo"]:
                path = save_photo(
                    image,
                    state["directory"],
                    state["label"],
                    state["session"],
                    state["saved"] + 1,
                )
                state["saved"] += 1
                state["next_photo"] = time.monotonic() + state["interval"]
                status.set(f"저장 {state['saved']} / {state['count']}장 · {path.name}")
                if state["saved"] >= state["count"]:
                    set_running(False)
                    status.set(f"촬영 완료: {state['saved']}장 · {state['directory']}")
            display = image.copy()
            display.thumbnail(
                (
                    max(320, root.winfo_width() - 32),
                    max(240, root.winfo_height() - 230),
                ),
                Image.Resampling.LANCZOS,
            )
            photo = ImageTk.PhotoImage(display)
            preview.configure(image=photo)
            preview.image = photo
        except Exception as error:
            set_running(False)
            status.set(f"촬영/저장 오류: {error} · 기존 사진은 보존됩니다.")
            messagebox.showerror("카메라 또는 저장 오류", str(error), parent=root)
            close()
            return
        root.after(100, tick)

    start_button = ttk.Button(buttons, text="연속 촬영 시작", command=start_batch)
    start_button.pack(side="left", padx=6)
    ttk.Button(buttons, text="촬영 중지", command=stop_batch).pack(side="left", padx=6)
    folder_button = ttk.Button(buttons, text="저장 폴더 선택", command=select_folder)
    folder_button.pack(side="left", padx=6)
    ttk.Button(buttons, text="종료", command=close).pack(side="left", padx=6)
    root.protocol("WM_DELETE_WINDOW", close)
    try:
        camera.configure(
            camera.create_preview_configuration(
                main={"size": (2028, 1520), "format": "RGB888"}
            )
        )
        camera.start()
        status.set("준비 완료 · 기본 100장, 1초 간격 · 시작 후 3초 대기")
        root.after(500, tick)
        root.mainloop()
    finally:
        camera.close()


if __name__ == "__main__":
    main()
