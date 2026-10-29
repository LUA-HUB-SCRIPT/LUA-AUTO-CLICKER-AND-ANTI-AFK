#!/usr/bin/env python3
"""LUAHUB AFK CONTROL CENTER - desktop keep-awake and click-target utility."""
import json
import os
import platform
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import pyautogui
    from pynput import keyboard, mouse
except ImportError as exc:
    raise SystemExit("Dependencies missing. Run: python -m pip install pyautogui pynput") from exc

APP_NAME = "LUAHUB AFK CONTROL CENTER"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".luahub_afk_config.json")
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("850x720")
        self.root.minsize(780, 650)
        self.root.configure(bg="#0b1020")
        self.running = False
        self.worker = None
        self.targets = []
        self.capture_listener = None
        self.hotkey_listener = None
        self.keepawake_process = None
        self.win_awake = False
        self.stop_event = threading.Event()
        self.clicks_done = 0
        self.started_at = None

        self.interval_var = tk.StringVar(value="1.0")
        self.duration_var = tk.StringVar(value="0")
        self.count_var = tk.StringVar(value="0")
        self.button_var = tk.StringVar(value="left")
        self.repeat_var = tk.StringVar(value="target list")
        self.start_key_var = tk.StringVar(value="f6")
        self.stop_key_var = tk.StringVar(value="f7")
        self.keepawake_var = tk.BooleanVar(value=True)
        self.topmost_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="READY • Add a target to begin")
        self.counter_var = tk.StringVar(value="Clicks: 0")
        self.profile_var = tk.StringVar(value="default")

        self._style()
        self._build_ui()
        self._load_config()
        self._start_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._tick_status()

    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame", background="#0b1020")
        s.configure("Panel.TFrame", background="#121a2e")
        s.configure("TLabel", background="#0b1020", foreground="#e7ecff", font=("Segoe UI", 10))
        s.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground="#64d9ff", background="#0b1020")
        s.configure("Sub.TLabel", foreground="#9eaccb", background="#0b1020")
        s.configure("Panel.TLabel", background="#121a2e", foreground="#e7ecff")
        s.configure("TButton", padding=7, font=("Segoe UI", 10, "bold"))
        s.configure("Accent.TButton", background="#176b87", foreground="white")
        s.map("Accent.TButton", background=[("active", "#2188a8")])
        s.configure("TEntry", fieldbackground="#17223a", foreground="#e7ecff")
        s.configure("TCombobox", fieldbackground="#17223a", foreground="#e7ecff")
        s.configure("Treeview", background="#121a2e", fieldbackground="#121a2e", foreground="#e7ecff", rowheight=25)
        s.configure("Treeview.Heading", background="#202e4a", foreground="#ffffff")

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="LUAHUB", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="AFK CONTROL CENTER  •  KEEP AWAKE + DESKTOP CLICKER", style="Sub.TLabel").pack(anchor="w", pady=(0, 12))

        panel = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        panel.pack(fill="x")
        for c in range(6):
            panel.columnconfigure(c, weight=1)
        self._field(panel, "Interval (seconds)", self.interval_var, 0, 0)
        self._field(panel, "Duration (minutes; 0 = unlimited)", self.duration_var, 0, 2)
        self._field(panel, "Maximum clicks (0 = unlimited)", self.count_var, 0, 4)
        ttk.Label(panel, text="Mouse button", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 2))
        ttk.Combobox(panel, textvariable=self.button_var, values=("left", "right", "middle"), state="readonly").grid(row=3, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(panel, text="Target mode", style="Panel.TLabel").grid(row=2, column=2, sticky="w", pady=(10, 2))
        ttk.Combobox(panel, textvariable=self.repeat_var, values=("target list", "same target"), state="readonly").grid(row=3, column=2, sticky="ew", padx=(0, 8))
        ttk.Label(panel, text="Profile name", style="Panel.TLabel").grid(row=2, column=4, sticky="w", pady=(10, 2))
        ttk.Entry(panel, textvariable=self.profile_var).grid(row=3, column=4, sticky="ew")

        actions = ttk.Frame(outer, padding=(0, 12))
        actions.pack(fill="x")
        ttk.Button(actions, text="▶ START", style="Accent.TButton", command=self.start).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="■ STOP", command=self.stop).pack(side="left", padx=6)
        ttk.Button(actions, text="＋ ADD TARGET", command=self.add_target).pack(side="left", padx=6)
        ttk.Button(actions, text="Remove selected", command=self.remove_target).pack(side="left", padx=6)

        targets = ttk.Frame(outer, style="Panel.TFrame", padding=10)
        targets.pack(fill="both", expand=True)
        ttk.Label(targets, text="CLICK TARGETS", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(targets, text="Click Add Target, then click the desired screen position within 10 seconds.", style="Panel.TLabel").pack(anchor="w", pady=(0, 8))
        self.tree = ttk.Treeview(targets, columns=("name", "x", "y"), show="headings", height=7)
        for col, title, width in (("name", "Target", 400), ("x", "X", 100), ("y", "Y", 100)):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w" if col == "name" else "center")
        self.tree.pack(fill="both", expand=True)

        opts = ttk.Frame(outer, style="Panel.TFrame", padding=10)
        opts.pack(fill="x", pady=(12, 0))
        ttk.Checkbutton(opts, text="Keep computer awake while app is open", variable=self.keepawake_var, command=self.update_keepawake).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(opts, text="Always on top", variable=self.topmost_var, command=lambda: self.root.attributes("-topmost", self.topmost_var.get())).grid(row=0, column=1, sticky="w", padx=16)
        ttk.Label(opts, text="Start hotkey", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(opts, textvariable=self.start_key_var, width=12).grid(row=2, column=0, sticky="w")
        ttk.Label(opts, text="Stop hotkey (F12 = emergency stop)", style="Panel.TLabel").grid(row=1, column=1, sticky="w", pady=(8, 2))
        ttk.Entry(opts, textvariable=self.stop_key_var, width=22).grid(row=2, column=1, sticky="w")
        ttk.Button(opts, text="Apply hotkeys", command=self._start_hotkeys).grid(row=2, column=2, padx=8)
        ttk.Button(opts, text="Save profile", command=self.save_profile).grid(row=2, column=3, padx=4)
        ttk.Button(opts, text="Load profile", command=self.load_profile).grid(row=2, column=4, padx=4)

        foot = ttk.Frame(outer)
        foot.pack(fill="x", pady=(10, 0))
        ttk.Label(foot, textvariable=self.status_var).pack(side="left")
        ttk.Label(foot, textvariable=self.counter_var).pack(side="right")
        ttk.Label(outer, text="Failsafe: move mouse to top-left corner. Use automation only where permitted; this does not bypass game AFK detection or anti-cheat.", style="Sub.TLabel", wraplength=800).pack(anchor="w", pady=(8, 0))

    def _field(self, parent, label, var, row, col):
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=col, columnspan=2, sticky="w", pady=(0, 2))
        ttk.Entry(parent, textvariable=var).grid(row=row + 1, column=col, columnspan=2, sticky="ew", padx=(0, 10))

    def status(self, msg):
        self.root.after(0, self.status_var.set, msg)

    def _tick_status(self):
        if self.running and self.started_at:
            self.counter_var.set(f"Clicks: {self.clicks_done} • Elapsed: {int(time.time()-self.started_at)}s")
        else:
            self.counter_var.set(f"Clicks: {self.clicks_done}")
        self.root.after(500, self._tick_status)

    def add_target(self):
        if self.running:
            messagebox.showinfo(APP_NAME, "Stop the clicker before editing targets.")
            return
        messagebox.showinfo(APP_NAME, "After closing this message, click the desired screen position.")
        self.status("TARGET MODE • Click the desired position within 10 seconds")
        def capture():
            try:
                listener = mouse.Listener(on_click=self._capture_click)
                self.capture_listener = listener
                listener.start()
                listener.join(10)
                if listener.is_alive():
                    listener.stop()
                self.capture_listener = None
            except Exception as exc:
                self.status(f"Target capture failed: {exc}")
        threading.Thread(target=capture, daemon=True).start()

    def _capture_click(self, x, y, button, pressed):
        if pressed:
            self.targets.append({"name": f"Target {len(self.targets)+1}", "x": int(x), "y": int(y)})
            self.root.after(0, self._refresh_targets)
            self.status(f"Added target at X={x}, Y={y}")
            if self.capture_listener:
                self.capture_listener.stop()
            return False
        return True

    def _refresh_targets(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, target in enumerate(self.targets):
            self.tree.insert("", "end", iid=str(i), values=(target["name"], target["x"], target["y"]))

    def remove_target(self):
        selection = self.tree.selection()
        if selection:
            self.targets.pop(int(selection[0]))
            self._refresh_targets()
            self.status("Target removed")

    def _validated(self):
        try:
            interval = float(self.interval_var.get())
            duration = float(self.duration_var.get()) * 60
            count = int(self.count_var.get())
            if interval < 0.05 or duration < 0 or count < 0:
                raise ValueError
            return interval, duration, count
        except ValueError:
            messagebox.showerror(APP_NAME, "Interval must be >= 0.05 seconds. Duration and click count must be >= 0.")
            return None

    def start(self):
        if self.running:
            return
        if not self.targets:
            messagebox.showwarning(APP_NAME, "Add at least one target first.")
            return
        values = self._validated()
        if not values:
            return
        self.running = True
        self.stop_event.clear()
        self.clicks_done = 0
        self.started_at = time.time()
        self.update_keepawake()
        self.status("RUNNING • Press Stop or your stop hotkey to end")
        self.worker = threading.Thread(target=self._click_loop, args=values, daemon=True)
        self.worker.start()

    def _click_loop(self, interval, duration, max_clicks):
        began = time.monotonic()
        index = 0
        try:
            while not self.stop_event.is_set():
                if duration and time.monotonic() - began >= duration:
                    break
                if max_clicks and self.clicks_done >= max_clicks:
                    break
                target = self.targets[0] if self.repeat_var.get() == "same target" else self.targets[index % len(self.targets)]
                index += 1
                pyautogui.click(target["x"], target["y"], button=self.button_var.get())
                self.clicks_done += 1
                self.stop_event.wait(interval)
        except Exception as exc:
            self.status(f"Stopped safely: {exc}")
        finally:
            self.root.after(0, self._finish)

    def _finish(self):
        self.running = False
        self.started_at = None
        self.status("STOPPED • Ready")
        self.update_keepawake()

    def stop(self):
        self.stop_event.set()
        self.status("Stopping…")

    def update_keepawake(self):
        if self.keepawake_var.get():
            if platform.system() == "Windows":
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x1 | 0x2)
                    self.win_awake = True
                except Exception:
                    pass
            elif platform.system() == "Linux" and not self.keepawake_process:
                try:
                    if subprocess.call(["which", "systemd-inhibit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                        self.keepawake_process = subprocess.Popen(["systemd-inhibit", "--what=sleep:idle", "--why=LUAHUB keep computer awake", "sleep", "infinity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    self.keepawake_process = None
        else:
            self._release_keepawake()

    def _release_keepawake(self):
        if self.keepawake_process:
            try:
                self.keepawake_process.terminate()
            except Exception:
                pass
            self.keepawake_process = None
        if platform.system() == "Windows" and self.win_awake:
            try:
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            except Exception:
                pass
            self.win_awake = False

    def _start_hotkeys(self):
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        start = self.start_key_var.get().strip().lower()
        stop = self.stop_key_var.get().strip().lower()
        mapping = {}
        if start:
            mapping[f"<{start}>" if len(start) > 1 else start] = lambda: self.root.after(0, self.start)
        if stop:
            mapping[f"<{stop}>" if len(stop) > 1 else stop] = lambda: self.root.after(0, self.stop)
        mapping["<f12>"] = lambda: self.root.after(0, self.stop)
        try:
            self.hotkey_listener = keyboard.GlobalHotKeys(mapping)
            self.hotkey_listener.start()
            self.status("Hotkeys applied • F12 is emergency stop")
        except Exception as exc:
            self.status(f"Hotkey setup failed: {exc}")

    def _data(self):
        return {"interval": self.interval_var.get(), "duration": self.duration_var.get(), "count": self.count_var.get(),
                "button": self.button_var.get(), "repeat": self.repeat_var.get(), "start_key": self.start_key_var.get(),
                "stop_key": self.stop_key_var.get(), "keepawake": self.keepawake_var.get(), "topmost": self.topmost_var.get(),
                "profile": self.profile_var.get(), "targets": self.targets}

    def _apply(self, data):
        for key, var in (("interval", self.interval_var), ("duration", self.duration_var), ("count", self.count_var),
                         ("button", self.button_var), ("repeat", self.repeat_var), ("start_key", self.start_key_var),
                         ("stop_key", self.stop_key_var), ("profile", self.profile_var)):
            if key in data:
                var.set(str(data[key]))
        self.keepawake_var.set(bool(data.get("keepawake", True)))
        self.topmost_var.set(bool(data.get("topmost", False)))
        self.targets = data.get("targets", [])
        self._refresh_targets()
        self.root.attributes("-topmost", self.topmost_var.get())
        self._start_hotkeys()
        self.update_keepawake()

    def save_profile(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile=(self.profile_var.get() or "profile") + ".json", filetypes=[("JSON profile", "*.json")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._data(), f, indent=2)
                self.status("Profile saved")
            except Exception as exc:
                messagebox.showerror(APP_NAME, str(exc))

    def load_profile(self):
        path = filedialog.askopenfilename(filetypes=[("JSON profile", "*.json")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._apply(json.load(f))
                self.status("Profile loaded")
            except Exception as exc:
                messagebox.showerror(APP_NAME, str(exc))

    def _load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self._apply(json.load(f))
            else:
                self.update_keepawake()
        except Exception:
            self.update_keepawake()

    def close(self):
        self.stop_event.set()
        self._release_keepawake()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data(), f, indent=2)
        except Exception:
            pass
        for listener in (self.hotkey_listener, self.capture_listener):
            if listener:
                try:
                    listener.stop()
                except Exception:
                    pass
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    App(window)
    window.mainloop()
