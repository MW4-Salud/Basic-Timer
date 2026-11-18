# Electron Timer
# A small desktop timer and stopwatch with an atom animation.
# Run it with: python electron_timer.py
#
# Keys:
#   Space = start / pause
#   R     = reset
#   L     = lap (stopwatch only)
#   T     = switch between timer and stopwatch

import math
import sys
import time
import threading
import subprocess
import tkinter as tk

# colors
BG = "#151833"
PANEL = "#1e2245"
TEXT = "#e9ecfb"
GRAY = "#9aa1c7"
ORBIT_COLOR = "#2f3462"
ELECTRON_COLOR = "#7fd1ff"
NUCLEUS_COLOR = "#f2b134"

if sys.platform == "win32":
    FONT = "Segoe UI"
elif sys.platform == "darwin":
    FONT = "Helvetica Neue"
else:
    FONT = "DejaVu Sans"


def blend(color1, color2, amount):
    # mix two hex colors, amount 0 = color1, amount 1 = color2
    r1 = int(color1[1:3], 16)
    g1 = int(color1[3:5], 16)
    b1 = int(color1[5:7], 16)
    r2 = int(color2[1:3], 16)
    g2 = int(color2[3:5], 16)
    b2 = int(color2[5:7], 16)
    r = round(r1 + (r2 - r1) * amount)
    g = round(g1 + (g2 - g1) * amount)
    b = round(b1 + (b2 - b1) * amount)
    return "#%02x%02x%02x" % (r, g, b)


def timer_text(seconds):
    seconds = max(0, math.ceil(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return "%d:%02d:%02d" % (hours, minutes, secs)
    return "%02d:%02d" % (minutes, secs)


def stopwatch_text(seconds):
    hundredths = int(seconds * 100)
    hours = hundredths // 360000
    minutes = (hundredths // 6000) % 60
    secs = (hundredths // 100) % 60
    hs = hundredths % 100
    if hours > 0:
        return "%d:%02d:%02d.%02d" % (hours, minutes, secs, hs)
    return "%02d:%02d.%02d" % (minutes, secs, hs)


def orbit_point(angle, t, width, height, cx, cy):
    # point on an ellipse that is rotated by angle
    x = width * math.cos(t)
    y = height * math.sin(t)
    new_x = cx + x * math.cos(angle) - y * math.sin(angle)
    new_y = cy + x * math.sin(angle) + y * math.cos(angle)
    return new_x, new_y


class TimerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Electron Timer")
        self.root.configure(bg=BG)
        self.root.geometry("340x560")
        self.root.minsize(280, 480)
        self.root.attributes("-topmost", True)
        self.on_top = True

        self.mode = "timer"

        # timer
        self.total = 300.0
        self.remaining = 300.0
        self.timer_running = False
        self.timer_done = False
        self.end_time = 0

        # stopwatch
        self.sw_saved = 0.0
        self.sw_start = 0
        self.sw_running = False
        self.sw_time = 0.0
        self.laps = []

        # animation
        self.speed = 0.35
        self.target_speed = 0.35
        self.phase = 0
        self.burst = 0
        self.last_frame = time.perf_counter()
        # each orbit is (tilt angle, speed, starting offset)
        self.orbits = [
            (0, 1.0, 0),
            (math.pi / 3, 1.17, 2.1),
            (2 * math.pi / 3, 1.34, 4.2),
        ]

        self.make_widgets()
        self.refresh()

        self.root.bind("<Key>", self.key_pressed)

        self.draw()

    def key_pressed(self, event):
        # don't trigger shortcuts while typing in the min/sec boxes
        if isinstance(event.widget, tk.Entry):
            return
        key = event.keysym.lower()
        if key == "space":
            self.start_pause()
        elif key == "r":
            self.reset()
        elif key == "l":
            self.lap()
        elif key == "t":
            if self.mode == "timer":
                self.set_mode("stopwatch")
            else:
                self.set_mode("timer")

    def make_button(self, parent, text, command, main=False):
        if main:
            button = tk.Label(parent, text=text, bg=TEXT, fg=BG, cursor="hand2",
                              padx=16, pady=8, font=(FONT, 11, "bold"))
        else:
            button = tk.Label(parent, text=text, bg=PANEL, fg=TEXT, cursor="hand2",
                              padx=16, pady=8, font=(FONT, 11))
        button.bind("<Button-1>", lambda event: command())
        return button

    def make_widgets(self):
        # top bar with the two tabs and the stay on top toggle
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 0))

        self.timer_tab = self.make_button(top, "Timer", lambda: self.set_mode("timer"))
        self.timer_tab.pack(side="left")
        self.sw_tab = self.make_button(top, "Stopwatch", lambda: self.set_mode("stopwatch"))
        self.sw_tab.pack(side="left", padx=(6, 0))

        self.pin_label = tk.Label(top, bg=BG, fg=GRAY, cursor="hand2", font=(FONT, 9))
        self.pin_label.bind("<Button-1>", lambda event: self.toggle_on_top())
        self.pin_label.pack(side="right")

        # canvas for the atom
        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=6)

        # timer settings (preset buttons and min/sec boxes)
        self.timer_frame = tk.Frame(self.root, bg=BG)

        presets = tk.Frame(self.timer_frame, bg=BG)
        presets.pack()
        self.add_preset(presets, "1m", 60)
        self.add_preset(presets, "5m", 300)
        self.add_preset(presets, "10m", 600)
        self.add_preset(presets, "25m", 1500)
        self.add_preset(presets, "1h", 3600)

        custom = tk.Frame(self.timer_frame, bg=BG)
        custom.pack(pady=(8, 0))
        self.min_box = tk.StringVar(value="5")
        self.sec_box = tk.StringVar(value="0")
        self.add_entry(custom, self.min_box, "min")
        self.add_entry(custom, self.sec_box, "sec")

        # lap list for the stopwatch
        self.lap_label = tk.Label(self.root, bg=BG, fg=GRAY, font=(FONT, 10), justify="left")

        # bottom buttons
        self.buttons = tk.Frame(self.root, bg=BG)
        self.start_button = self.make_button(self.buttons, "Start", self.start_pause, main=True)
        self.start_button.configure(width=8)
        self.start_button.pack(side="left", padx=5)
        self.second_button = self.make_button(self.buttons, "Reset", self.second_button_clicked)
        self.second_button.pack(side="left", padx=5)
        self.reset_button = self.make_button(self.buttons, "Reset", self.reset)

    def add_preset(self, parent, text, seconds):
        button = self.make_button(parent, text, lambda: self.set_time(seconds))
        button.configure(padx=10, pady=5, font=(FONT, 10))
        button.pack(side="left", padx=3)

    def add_entry(self, parent, variable, unit):
        entry = tk.Entry(parent, textvariable=variable, width=4, justify="center",
                         bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                         font=(FONT, 12))
        entry.pack(side="left", ipady=4)
        entry.bind("<Return>", self.entry_enter)
        entry.bind("<FocusOut>", lambda event: self.use_typed_time())
        tk.Label(parent, text=unit, bg=BG, fg=GRAY, font=(FONT, 10)).pack(side="left", padx=(4, 10))

    def entry_enter(self, event):
        self.use_typed_time()
        self.root.focus_set()

    def set_mode(self, mode):
        self.mode = mode
        self.refresh()

    def toggle_on_top(self):
        self.on_top = not self.on_top
        self.root.attributes("-topmost", self.on_top)
        self.refresh()

    def is_paused(self):
        if self.mode == "timer":
            return (not self.timer_running) and self.remaining < self.total and not self.timer_done
        return (not self.sw_running) and self.sw_time > 0

    def refresh(self):
        # update tab colors
        if self.mode == "timer":
            self.timer_tab.configure(bg=TEXT, fg=BG)
            self.sw_tab.configure(bg=PANEL, fg=TEXT)
        else:
            self.timer_tab.configure(bg=PANEL, fg=TEXT)
            self.sw_tab.configure(bg=TEXT, fg=BG)

        if self.on_top:
            self.pin_label.configure(text="Stays on top: on")
        else:
            self.pin_label.configure(text="Stays on top: off")

        # hide everything at the bottom, then show what this mode needs
        self.timer_frame.pack_forget()
        self.lap_label.pack_forget()
        self.buttons.pack_forget()
        self.reset_button.pack_forget()

        if self.mode == "timer":
            self.timer_frame.pack(pady=(0, 10))
            if self.timer_running:
                self.start_button.configure(text="Pause")
            elif self.is_paused():
                self.start_button.configure(text="Resume")
            else:
                self.start_button.configure(text="Start")
            self.second_button.configure(text="Reset")
            running = self.timer_running
        else:
            if len(self.laps) > 0:
                self.lap_label.pack(pady=(0, 8))
            if self.sw_running:
                self.start_button.configure(text="Pause")
            elif self.sw_time > 0:
                self.start_button.configure(text="Resume")
            else:
                self.start_button.configure(text="Start")
            self.second_button.configure(text="Lap")
            if not self.sw_running and self.sw_time > 0:
                self.reset_button.pack(side="left", padx=5)
            running = self.sw_running

        self.buttons.pack(pady=(0, 16))

        # electrons spin faster when running, slower when paused
        if self.burst < 0.05:
            if running:
                self.target_speed = 1.0
            elif self.is_paused():
                self.target_speed = 0.12
            else:
                self.target_speed = 0.35

    def start_pause(self):
        if self.mode == "timer":
            if self.timer_running:
                self.remaining = self.end_time - time.time()
                self.timer_running = False
            else:
                if self.timer_done:
                    self.remaining = self.total
                    self.timer_done = False
                self.end_time = time.time() + self.remaining
                self.timer_running = True
        else:
            if self.sw_running:
                self.sw_saved = self.sw_saved + (time.time() - self.sw_start)
                self.sw_time = self.sw_saved
                self.sw_running = False
            else:
                self.sw_start = time.time()
                self.sw_running = True
        self.refresh()

    def second_button_clicked(self):
        if self.mode == "timer":
            self.reset()
        else:
            self.lap()

    def reset(self):
        if self.mode == "timer":
            self.timer_running = False
            self.timer_done = False
            self.remaining = self.total
        else:
            self.sw_running = False
            self.sw_saved = 0.0
            self.sw_time = 0.0
            self.laps = []
            self.lap_label.configure(text="")
        self.refresh()

    def lap(self):
        if self.mode != "stopwatch" or not self.sw_running:
            return
        if len(self.laps) > 0:
            last_total = self.laps[-1][1]
        else:
            last_total = 0.0
        split = self.sw_time - last_total
        self.laps.append((split, self.sw_time))

        # show the 5 newest laps, newest on top
        lines = []
        for i in range(len(self.laps) - 1, -1, -1):
            split, total = self.laps[i]
            lines.append("Lap %d    %s    %s" % (i + 1, stopwatch_text(split), stopwatch_text(total)))
            if len(lines) == 5:
                break
        self.lap_label.configure(text="\n".join(lines))
        self.refresh()

    def set_time(self, seconds):
        if self.timer_running:
            return
        if seconds < 1:
            seconds = 1
        self.total = float(seconds)
        self.remaining = float(seconds)
        self.timer_done = False
        self.min_box.set(str(int(seconds) // 60))
        self.sec_box.set(str(int(seconds) % 60))
        self.refresh()

    def use_typed_time(self):
        try:
            minutes = int(self.min_box.get() or 0)
            seconds = int(self.sec_box.get() or 0)
        except ValueError:
            return
        if seconds > 59:
            seconds = 59
        new_total = minutes * 60 + seconds
        if not self.timer_running and new_total != int(self.total):
            self.set_time(new_total)

    def time_up(self):
        self.timer_running = False
        self.timer_done = True
        self.remaining = 0.0
        self.burst = 1.0
        self.target_speed = 2.4
        self.mode = "timer"
        self.refresh()
        self.play_sound()
        self.show_popup()

    def show_popup(self):
        self.root.deiconify()
        self.root.lift()

        popup = tk.Toplevel(self.root, bg=PANEL)
        popup.title("Time's up")
        popup.attributes("-topmost", True)
        popup.resizable(False, False)

        tk.Label(popup, text="Time's up", bg=PANEL, fg=TEXT,
                 font=(FONT, 18, "bold")).pack(padx=40, pady=(22, 4))
        tk.Label(popup, text=timer_text(self.total) + " is done.", bg=PANEL, fg=GRAY,
                 font=(FONT, 11)).pack()

        def close():
            popup.destroy()
            self.target_speed = 0.35

        ok = self.make_button(popup, "Dismiss", close, main=True)
        ok.pack(pady=18)
        popup.bind("<Return>", lambda event: close())
        popup.bind("<Escape>", lambda event: close())

        # put the popup in the middle of the main window
        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - popup.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - popup.winfo_height()) // 2
        popup.geometry("+%d+%d" % (x, y))
        popup.focus_force()

    def play_sound(self):
        def beep():
            try:
                if sys.platform == "win32":
                    import winsound
                    for i in range(3):
                        winsound.Beep(659, 130)
                        winsound.Beep(784, 130)
                        winsound.Beep(988, 130)
                        winsound.Beep(1319, 130)
                        time.sleep(0.4)
                elif sys.platform == "darwin":
                    for i in range(3):
                        subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
                else:
                    for i in range(3):
                        self.root.bell()
                        time.sleep(0.5)
            except Exception:
                pass

        # play in the background so the window doesn't freeze
        threading.Thread(target=beep, daemon=True).start()

    def update_times(self):
        if self.timer_running:
            self.remaining = self.end_time - time.time()
            if self.remaining <= 0:
                self.time_up()
        if self.sw_running:
            self.sw_time = self.sw_saved + (time.time() - self.sw_start)

    def draw(self):
        now = time.perf_counter()
        dt = min(0.05, now - self.last_frame)
        self.last_frame = now

        self.update_times()

        # ease the speed toward the target speed
        self.speed = self.speed + (self.target_speed - self.speed) * min(1, dt * 3)
        self.phase = self.phase + dt * self.speed * 2.2
        self.burst = self.burst * (0.35 ** dt)

        canvas = self.canvas
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()

        if w > 20 and h > 20:
            cx = w / 2
            cy = h / 2
            radius = min(w, h) / 2 - 8
            spread = 1 + self.burst * 0.25 * (1 + math.sin(self.phase * 6) * 0.3)
            orbit_w = radius * 0.82 * spread
            orbit_h = radius * 0.3 * spread

            # outer progress ring
            if self.mode == "timer":
                if self.total > 0:
                    progress = max(0.0, self.remaining / self.total)
                else:
                    progress = 0
            else:
                progress = (self.sw_time % 60) / 60

            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                               outline=ORBIT_COLOR, width=3)
            if progress > 0.001:
                canvas.create_arc(cx - radius, cy - radius, cx + radius, cy + radius,
                                  start=90, extent=-min(359.9, 360 * progress),
                                  style="arc", outline=NUCLEUS_COLOR, width=3)

            # orbit lines
            for angle, rate, offset in self.orbits:
                points = []
                for i in range(49):
                    t = i / 48 * 2 * math.pi
                    x, y = orbit_point(angle, t, orbit_w, orbit_h, cx, cy)
                    points.append(x)
                    points.append(y)
                canvas.create_line(points, fill=ORBIT_COLOR, smooth=True, width=1)

            # glowing nucleus in the middle
            pulse = 1 + self.burst * 0.4
            if self.target_speed >= 1:
                pulse = pulse + math.sin(now * 3.3) * 0.06
            nucleus_r = radius * 0.1 * pulse
            for i in range(8, 0, -1):
                r = nucleus_r * (0.6 + i * 0.3)
                color = blend(BG, NUCLEUS_COLOR, (1 - i / 9) ** 1.6)
                canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")

            # electrons with a fading tail
            electron_r = radius * 0.035
            for angle, rate, offset in self.orbits:
                for k in range(2):
                    t = self.phase * rate + offset + k * math.pi
                    for j in range(12, -1, -1):
                        x, y = orbit_point(angle, t - j * 0.045, orbit_w, orbit_h, cx, cy)
                        if j == 0:
                            r = electron_r
                            color = ELECTRON_COLOR
                        else:
                            r = electron_r * (1 - j / 16)
                            color = blend(BG, ELECTRON_COLOR, (1 - j / 13) * 0.45)
                        canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")

            # time in the center
            if self.mode == "timer":
                text = timer_text(self.remaining)
            else:
                text = stopwatch_text(self.sw_time)
            if len(text) <= 5:
                size = max(14, int(radius * 0.26))
            else:
                size = max(14, int(radius * 0.2))
            canvas.create_text(cx, cy, text=text, fill=TEXT, font=(FONT, size, "bold"))

            # status under the time
            if self.mode == "timer":
                if self.timer_done:
                    status = "Done"
                elif self.timer_running:
                    status = "Running"
                elif self.is_paused():
                    status = "Paused"
                else:
                    status = "Ready"
            else:
                if self.sw_running:
                    status = "Running"
                elif self.sw_time > 0:
                    status = "Paused"
                else:
                    status = "Ready"
            canvas.create_text(cx, cy + size * 1.05, text=status, fill=GRAY,
                               font=(FONT, max(9, size // 3)))

            # window title shows the time while running
            if self.mode == "timer" and self.timer_running:
                self.root.title(timer_text(self.remaining) + " left")
            elif self.mode == "stopwatch" and self.sw_running:
                self.root.title(stopwatch_text(self.sw_time)[:-3])
            else:
                self.root.title("Electron Timer")

        # about 60 frames a second
        self.root.after(16, self.draw)


if __name__ == "__main__":
    root = tk.Tk()
    app = TimerApp(root)
    root.mainloop()
