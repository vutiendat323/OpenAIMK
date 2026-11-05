#!/usr/bin/env python3
"""Trend Kiosk Manager: a small window to start, stop and restart the kiosk services.

For staff who do not use a terminal. Closing the window does not stop the kiosk; the
services keep running on their own. All the logic is in `kiosk_manager.py`.
"""

import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from tkinter import ttk

try:  # run as a script from this folder, or as `scripts.kiosk_manager_gui`
    import kiosk_manager as core
except ImportError:  # pragma: no cover
    from scripts import kiosk_manager as core

REFRESH_MS = 2000
IDLE_READINGS = 15  # 15 refreshes of 2 s: the kiosk must stay free for 30 s
GREEN, AMBER, RED, GREY = "#2e9e5b", "#d97706", "#c0392b", "#8a8a8a"
STATE_COLOR = {"running": GREEN, "starting": AMBER, "stopped": RED, "other": GREY}
STATE_TEXT = {
    "running": "Đang chạy",
    "starting": "Đang khởi động…",
    "stopped": "Đã tắt",
    "other": "Cổng đang do chương trình khác dùng",
}
BANNER_COLOR = {"free": GREEN, "busy": AMBER, "unknown": GREY}
PREFERRED_FONTS = ("Cantarell", "Noto Sans", "DejaVu Sans", "Liberation Sans", "Arial")
VERB = {"start": "bật", "stop": "tắt", "restart": "khởi động lại"}


def label_of(service):
    return "tất cả dịch vụ" if service == "all" else core.LABELS[service]


class ManagerApp:
    def __init__(self, root):
        self.root = root
        self.settings = core.load_settings()
        self.events = queue.Queue()
        self.busy = False
        self.sampling = False
        self.pending = None  # (action, service) waiting for the kiosk to be free
        self.idle = core.IdleWait(IDLE_READINGS)
        self.watchdog = core.Watchdog()
        self.wanted = None  # services that should run; set from the first reading
        self.states = {name: "stopped" for name in core.SERVICE_NAMES}
        self.status = None
        self.rows = {}
        self.build()
        self.loop()
        self.root.after(200, self.pump)

    # ----- window -----

    def build(self):
        root = self.root
        root.title("Trend Kiosk Manager")
        root.minsize(760, 520)
        families = {name.lower(): name for name in tkfont.families()}
        family = next(
            (families[f.lower()] for f in PREFERRED_FONTS if f.lower() in families), "fixed"
        )
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name).configure(family=family, size=-17)  # pixels: same on any DPI
        base = tkfont.nametofont("TkDefaultFont")
        self.big = tkfont.Font(family=family, size=-26, weight="bold")
        self.bold = tkfont.Font(family=family, size=-17, weight="bold")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=(12, 8), font=base)
        style.configure("Big.TButton", padding=(16, 12), font=self.bold)

        outer = ttk.Frame(root, padding=16)
        outer.pack(fill="both", expand=True)

        self.banner = tk.Label(outer, text="", font=self.big, fg="white", pady=10)
        self.banner.pack(fill="x")
        self.cancel_wait = ttk.Button(outer, text="Hủy chờ", command=self.stop_waiting)

        top = ttk.Frame(outer)
        top.pack(fill="x", pady=(14, 6))
        for text, action in (
            ("Bật tất cả", "start"),
            ("Tắt tất cả", "stop"),
            ("Khởi động lại tất cả", "restart"),
        ):
            button = ttk.Button(
                top, text=text, style="Big.TButton", command=lambda a=action: self.request(a, "all")
            )
            button.pack(side="left", padx=(0, 8))
            self.rows.setdefault("all", {})[action] = button

        for name in core.SERVICE_NAMES:
            self.add_row(outer, name)

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(14, 0))
        ttk.Button(bottom, text="Mở kiosk", command=self.open_kiosk).pack(side="left")
        ttk.Button(bottom, text="Cài đặt", command=self.open_settings).pack(side="left", padx=8)
        self.message = ttk.Label(outer, text="", anchor="w", justify="left", wraplength=720)
        self.message.pack(fill="x", pady=(10, 0))
        note = ttk.Label(
            outer,
            text="Đóng cửa sổ này không tắt kiosk. Dịch vụ vẫn chạy.",
            foreground=GREY,
            anchor="w",
        )
        note.pack(fill="x", pady=(4, 0))
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        self.update_banner()

    def add_row(self, parent, name):
        card = ttk.LabelFrame(parent, text=core.LABELS[name], padding=10)
        card.pack(fill="x", pady=6)
        dot = tk.Canvas(card, width=22, height=22, highlightthickness=0)
        oval = dot.create_oval(3, 3, 19, 19, fill=GREY, outline="")
        dot.pack(side="left")
        status = ttk.Label(card, text="…", font=self.bold, width=34, anchor="w")
        status.pack(side="left", padx=8)
        buttons = {}
        for text, action in (("Bật", "start"), ("Tắt", "stop"), ("Khởi động lại", "restart")):
            button = ttk.Button(
                card, text=text, command=lambda a=action, n=name: self.request(a, n)
            )
            button.pack(side="left", padx=3)
            buttons[action] = button
        ttk.Button(card, text="Nhật ký", command=lambda n=name: self.open_log(n)).pack(
            side="left", padx=3
        )
        self.rows[name] = {"dot": dot, "oval": oval, "status": status, **buttons}

    def update_view(self):
        for name in core.SERVICE_NAMES:
            row, state = self.rows[name], self.states[name]
            row["dot"].itemconfigure(row["oval"], fill=STATE_COLOR[state])
            row["status"].configure(text=STATE_TEXT[state])
            can_start = state == "stopped" and not self.busy
            can_stop = state in ("running", "starting") and not self.busy
            row["start"].state(["!disabled"] if can_start else ["disabled"])
            row["stop"].state(["!disabled"] if can_stop else ["disabled"])
            row["restart"].state(["!disabled"] if can_stop else ["disabled"])
        states = self.states.values()
        everything = {
            "start": any(s == "stopped" for s in states),
            "stop": any(s in ("running", "starting") for s in states),
            "restart": any(s in ("running", "starting") for s in states),
        }
        for action, button in self.rows["all"].items():
            button.state(["!disabled"] if everything[action] and not self.busy else ["disabled"])
        self.update_banner()

    def update_banner(self):
        if self.busy:
            text, color = "Đang xử lý… xin chờ", AMBER
        elif self.pending:
            action, service = self.pending
            text = f"Đang chờ khách xong để {VERB[action]} {label_of(service)}…"
            color = AMBER
        else:
            kind, text = core.kiosk_banner(self.status)
            color = BANNER_COLOR[kind]
        self.banner.configure(text=text, bg=color)
        if self.pending and not self.busy:
            self.cancel_wait.pack(after=self.banner, pady=(6, 0))
        else:
            self.cancel_wait.pack_forget()

    def say(self, text, good=True):
        self.message.configure(text=text, foreground=GREEN if good else RED)

    # ----- actions -----

    def request(self, action, service):
        if self.busy:
            return
        if core.guest_would_be_cut(action, self.status):
            choice = self.choose(
                "Đang có khách",
                f"Kiosk đang phục vụ khách. {VERB[action].capitalize()} "
                f"{label_of(service)} bây giờ sẽ ngắt cuộc trò chuyện.",
                [
                    ("Chờ khách xong rồi làm", "wait"),
                    (f"{VERB[action].capitalize()} ngay", "now"),
                    ("Hủy", None),
                ],
            )
            if choice is None:
                return
            if choice == "wait":
                self.pending = (action, service)
                self.idle = core.IdleWait(IDLE_READINGS)
                self.update_banner()
                return
        self.run(action, service)

    def stop_waiting(self):
        self.pending = None
        self.update_banner()

    def run(self, action, service):
        self.pending = None
        self.busy = True
        self.say(f"Đang {VERB[action]} {label_of(service)}…", good=True)
        self.update_view()
        token = self.settings["staff_token"]

        def work():
            ok, message = core.run_launcher(action, service, token)
            self.events.put(("done", action, service, ok, message))

        threading.Thread(target=work, daemon=True).start()

    def loop(self):
        self.sample()
        self.root.after(REFRESH_MS, self.loop)

    def sample(self):
        if not self.sampling:
            self.sampling = True

            def work():
                states = {name: core.service_state(name) for name in core.SERVICE_NAMES}
                self.events.put(("snapshot", states, core.fetch_kiosk()))

            threading.Thread(target=work, daemon=True).start()

    def pump(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "snapshot":
                    self.on_snapshot(event[1], event[2])
                else:
                    self.on_done(*event[1:])
        except queue.Empty:
            pass
        self.root.after(200, self.pump)

    def on_snapshot(self, states, status):
        self.sampling = False
        self.states, self.status = states, status
        if self.wanted is None:  # what was running when the window opened should stay running
            self.wanted = {n for n, s in states.items() if s in ("running", "starting")}
        self.update_view()
        if self.busy:
            return
        if self.pending and self.idle.ready(status):
            action, service = self.pending
            self.run(action, service)
            return
        if self.settings["auto_restart"]:
            for name in core.SERVICE_NAMES:
                if self.watchdog.should_restart(
                    name, states[name], name in self.wanted, time.monotonic()
                ):
                    self.say(f"{core.LABELS[name]} bị tắt. Đang tự bật lại…", good=False)
                    self.run("start", name)
                    return

    def on_done(self, action, service, ok, message):
        self.busy = False
        names = core.SERVICE_NAMES if service == "all" else (service,)
        if ok and action in ("start", "restart"):
            self.wanted = (self.wanted or set()) | set(names)
        elif ok and action == "stop":
            self.wanted = (self.wanted or set()) - set(names)
        if ok:
            self.say(f"Đã {VERB[action]} {label_of(service)}.")
        else:
            first = message.splitlines()[0] if message else "không rõ lý do"
            self.say(f"Không {VERB[action]} được {label_of(service)}: {first}", good=False)
        self.update_view()
        self.sample()

    def open_kiosk(self):
        webbrowser.open(f"http://127.0.0.1:{core.API_PORT}")

    # ----- dialogs -----

    def choose(self, title, text, options):
        """A small Vietnamese dialog; returns the value of the pressed button."""
        result = {"value": None}
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=18)
        body.pack()
        ttk.Label(body, text=text, wraplength=440, justify="left").pack(anchor="w")
        row = ttk.Frame(body)
        row.pack(fill="x", pady=(16, 0))

        def pick(value):
            result["value"] = value
            dialog.destroy()

        for label, value in options:
            ttk.Button(row, text=label, command=lambda v=value: pick(v)).pack(side="left", padx=4)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        self.root.wait_window(dialog)
        return result["value"]

    def open_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Cài đặt")
        dialog.transient(self.root)
        body = ttk.Frame(dialog, padding=18)
        body.pack()
        from_env = bool(os.environ.get("TREND_STAFF_TOKEN"))
        ttk.Label(body, text="Mã nhân viên (TREND_STAFF_TOKEN)", anchor="w").pack(fill="x")
        token = tk.StringVar(value=self.settings["staff_token"])
        entry = ttk.Entry(body, textvariable=token, show="•", width=36)
        entry.pack(fill="x", pady=(4, 2))
        if from_env:
            entry.state(["disabled"])
            hint = "Đang dùng mã từ biến môi trường của máy."
        else:
            hint = "Dùng để mở cài đặt nhân viên trên kiosk. Lưu riêng trên máy này."
        ttk.Label(body, text=hint, foreground=GREY, anchor="w", wraplength=420).pack(fill="x")
        auto = tk.BooleanVar(value=self.settings["auto_restart"])
        ttk.Checkbutton(
            body,
            text="Tự bật lại dịch vụ nếu bị tắt ngoài ý muốn",
            variable=auto,
        ).pack(anchor="w", pady=(14, 0))

        def save():
            typed = token.get().strip()
            saved = core.load_settings(use_env=False)["staff_token"]
            kept = saved if from_env else typed  # a code from the environment is never written
            core.save_settings({"staff_token": kept, "auto_restart": auto.get()})
            self.settings = core.load_settings()
            dialog.destroy()
            self.say("Đã lưu cài đặt.")

        ttk.Button(body, text="Lưu", command=save).pack(anchor="e", pady=(16, 0))
        dialog.grab_set()

    def open_log(self, name):
        window = tk.Toplevel(self.root)
        window.title(f"Nhật ký: {core.LABELS[name]}")
        window.geometry("820x480")
        text = tk.Text(window, wrap="none", font=("Liberation Mono", -14), state="disabled")
        scroll = ttk.Scrollbar(window, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)

        def refresh():
            if not window.winfo_exists():
                return
            content = core.tail_log(core.log_path(name))
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("end", content)
            text.configure(state="disabled")
            text.see("end")
            window.after(2000, refresh)

        refresh()


def main():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise SystemExit(f"Không mở được cửa sổ (cần màn hình): {error}") from error
    ManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
