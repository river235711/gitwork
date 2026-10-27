"""Arc-reactor style machine loading monitor (Tk).

- Core: flickers while refreshing, the flicker rate ramps up over time.
- Outer light bar: on refresh it fades dark -> bright -> dark, then shows
  the machine's real loading.
- Pick a machine from the dropdown, or ALL to see every machine at once;
  every host is polled every 10s either way.
  Hosts can be overridden: python3 arc_reactor.py hostA hostB ...

Local host runs uptime directly, remote hosts go over ssh BatchMode
(keys must already be set up, it will never prompt for a password).
"""

import math
import queue
import re
import shlex
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

DEFAULT_HOSTS = ["sirius01", "sirius02", "sirius05", "sirius06", "sirius07"]
ALL_LABEL = "ALL"  # dropdown entry that shows every machine at once
GRID_COLS = 3  # reactors per row in ALL view

# ---- Palette (all-black hardware + cyan/amber lamps) ---------------------
BG = "#04070b"
PANEL = "#050a0f"
DIM = "#03060a"  # base color everything fades toward
TEXT = "#c8dbe6"
MUTED = "#5e7686"
ACCENT = "#3fd0f0"

# Hardware is almost pure black, only the edges catch a little blue light.
BODY = "#070b10"  # module body
BODY_HI = "#0d161d"  # top cap
PLATE = "#0a1219"  # base plate
EDGE = "#2b4553"  # lit edge
EDGE_DIM = "#16232c"  # dark edge
GROOVE = "#0d1c25"  # concentric grooves
RING_LINE = "#123642"

# Lamps: cyan and amber, each with halo / body / white-hot core
CYAN_HALO, CYAN_MAIN, CYAN_HOT = "#0d6f9e", "#2fc8ff", "#dbf4ff"
ORANGE_HALO, ORANGE_MAIN, ORANGE_HOT = "#a63f08", "#ff8a12", "#ffe3b4"
GLOW_CYAN = "#1f9ed6"
GLOW_ORANGE = "#e2661a"

# Fixed lamp layout (index 0 = straight up, clockwise): left side leans
# cyan, lower right leans amber, deliberately irregular.
LAMP_PATTERN = "OCCOOC" "OOCOOC" "OCOCCC" "CCOCCO"

# Load bar colors
BAR_TRACK = "#0a151c"
TICK_OFF = "#0c1b23"
BAR_LOW = (0x3A, 0xD2, 0xFF)  # light load: cyan
BAR_MID = (0xFF, 0x9A, 0x2E)  # medium load: amber
BAR_HIGH = (0xFF, 0x3B, 0x4A)  # heavy load: red

# ---- Animation ----------------------------------------------------------
FPS_MS = 33  # animation tick (~30fps)
FPS_MS_ALL = 50  # slower tick in ALL view, there are 5 reactors to repaint
FLICKER_F0 = 1.8  # flicker rate when a refresh starts (Hz)
FLICKER_F1 = 22.0  # flicker rate it ramps up to (Hz)
FLICKER_RAMP = 2.5  # seconds to go from F0 to F1
FLICKER_LOW = 0.12  # brightness of the dark half of a flicker

PULSE_SECS = 0.9  # one dark -> bright -> dark cycle of the load bar

REFRESH_MS = 10_000  # poll every host every 10 seconds

MODULES = 24  # outer hardware modules (coarse lamps)
SEGMENTS = 60  # inner fine tick count (precise readout)
SSH_TIMEOUT = 12


# ---- Helpers ------------------------------------------------------------
def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def _rgb(color):
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))


def _mix(c1, c2, t):
    """c1/c2 may be #rrggbb or (r,g,b); returns the blend as #rrggbb."""
    a = _rgb(c1) if isinstance(c1, str) else c1
    b = _rgb(c2) if isinstance(c2, str) else c2
    return _hex(a[i] + (b[i] - a[i]) * t for i in range(3))


def _dim(color, k):
    """Fade a color toward the base color; k=1 keeps it, k=0 blacks it out."""
    return _mix(DIM, color, max(0.0, min(1.0, k)))


def _load_color(frac):
    """0..1 position -> cyan / amber / red gradient."""
    if frac < 0.5:
        return _mix(BAR_LOW, BAR_MID, frac / 0.5)
    return _mix(BAR_MID, BAR_HIGH, (frac - 0.5) / 0.5)


def _pt(cx, cy, r, deg):
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)


# ---- Reading the load ---------------------------------------------------
_LOAD_RE = re.compile(r"load averages?:\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)")
_PROBE = "uptime; getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu"
_STRICT = "accept-new"  # downgraded to "no" if the local ssh is too old


def _is_local(host):
    me = socket.gethostname()
    names = {me, me.split(".")[0], "localhost", "127.0.0.1"}
    return host in names or host.split(".")[0] in names


def _run(cmd):
    try:
        # stdout/stderr=PIPE + universal_newlines instead of the 3.7-only
        # capture_output/text, so this still runs on python 3.6
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=SSH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError("timeout")
    except OSError as e:
        raise RuntimeError(str(e))


def _ssh_cmd(host, strict):
    return [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=6",
        "-o", "StrictHostKeyChecking=" + strict,
        host,
        # ssh runs this through the login shell, which may be csh/tcsh —
        # hand it to /bin/sh so the sh syntax in _PROBE is understood
        "/bin/sh -c " + shlex.quote(_PROBE),
    ]


def terminal_cmds(host):
    """Candidate command lines for opening a terminal on `host`."""
    inner = [] if _is_local(host) else ["ssh", "-t", host]
    return [
        ["mate-terminal", "--title", host] + (["-x"] + inner if inner else []),
        ["xterm", "-T", host] + (["-e"] + inner if inner else []),
    ]


def probe(host):
    """Return (load1, load5, load15, ncpu), or raise RuntimeError."""
    global _STRICT
    if _is_local(host):
        p = _run(["/bin/sh", "-c", _PROBE])
    else:
        p = _run(_ssh_cmd(host, _STRICT))
        # accept-new needs OpenSSH >= 7.6; older clients reject the option
        # outright, so fall back once and remember the choice.
        if p.returncode and "unsupported option" in (p.stderr or ""):
            _STRICT = "no"
            p = _run(_ssh_cmd(host, _STRICT))

    out = p.stdout
    m = _LOAD_RE.search(out)
    if not m:
        err = (p.stderr or out).strip().splitlines()
        raise RuntimeError(err[-1][:60] if err else "no load average")

    ncpu = 1
    for line in reversed(out.strip().splitlines()):
        if line.strip().isdigit():
            ncpu = max(1, int(line.strip()))
            break
    return float(m.group(1)), float(m.group(2)), float(m.group(3)), ncpu


# ---- Reactor widget -----------------------------------------------------
class Reactor(tk.Frame):
    """One machine = one reactor plus the text underneath."""

    SIZE = 296

    def __init__(self, master, host, on_click, on_terminal):
        super().__init__(master, bg=PANEL, padx=10, pady=12)
        self.host = host

        self.percent = 0.0  # loading percentage currently displayed
        self.busy = False  # a refresh is in flight
        self.offline = False
        self.t0 = 0.0  # start time of this refresh
        self.phase = 0.0  # flicker phase accumulator
        self._shown_pct = -1.0  # last value painted on the ticks

        # Load-bar animation: "idle" -> "pulse" (fade up and down while
        # polling) -> "idle" (the real reading).
        self.anim = "idle"
        self.pulse_t0 = 0.0
        self.pulse_end = None  # end of the current fade cycle, once data is in

        self.canvas = tk.Canvas(
            self, width=self.SIZE, height=self.SIZE,
            bg=PANEL, highlightthickness=0, cursor="hand2",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda _e: on_click(self.host))

        # host name and its TERMINAL button share one row, to keep the ALL
        # view short enough to fit on screen
        row = tk.Frame(self, bg=PANEL)
        row.pack(pady=(8, 0))
        self.name_lb = tk.Label(
            row, text=host, bg=PANEL, fg=ACCENT,
            font=("TkDefaultFont", 12, "bold"),
        )
        self.name_lb.pack(side="left")
        self.term_btn = ttk.Button(
            row, text="TERMINAL", style="Term.TButton", takefocus=False,
            command=lambda: on_terminal(self.host),
        )
        self.term_btn.pack(side="left", padx=(10, 0))
        self.pct_lb = tk.Label(
            self, text="--", bg=PANEL, fg=TEXT, font=("TkFixedFont", 20, "bold")
        )
        self.pct_lb.pack()
        self.det_lb = tk.Label(
            self, text="no data yet", bg=PANEL, fg=MUTED, font=("TkFixedFont", 10)
        )
        self.det_lb.pack()
        self.time_lb = tk.Label(self, text="", bg=PANEL, fg=MUTED, font=("TkFixedFont", 9))
        self.time_lb.pack()

        self._build()

    # -- draw the reactor (head-on view, plain circles, no perspective) --
    def _build(self):
        c = self.canvas
        m = self.SIZE / 2
        self.core = []  # (item, base color) — brightness driven by animate()

        def oval(r, **kw):
            return c.create_oval(m - r, m - r, m + r, m + r, **kw)

        def block(r0, r1, deg, half, **kw):
            """A hardware block laid along the ring (both edges are arcs)."""
            pts = []
            for j in range(6):
                pts.extend(_pt(m, m, r1, deg - half + half * 2 * j / 5))
            for j in range(6):
                pts.extend(_pt(m, m, r0, deg + half - half * 2 * j / 5))
            return c.create_polygon(pts, **kw)

        # Scattered backlight (Tk has no alpha, fake it with color steps).
        for r, col in ((142, "#050a0e"), (128, "#061019"), (112, "#07141d")):
            oval(r, fill=col, outline="")

        # --- Load bar: track + halo + body + head highlight ---
        c.create_oval(m - 138, m - 138, m + 138, m + 138,
                      outline=BAR_TRACK, width=9)
        self.bar_halo = c.create_arc(m - 138, m - 138, m + 138, m + 138,
                                     start=90, extent=-0.1, style=tk.ARC,
                                     width=17, outline=BAR_TRACK)
        self.bar = c.create_arc(m - 138, m - 138, m + 138, m + 138,
                                start=90, extent=-0.1, style=tk.ARC,
                                width=9, outline=BAR_TRACK)
        self.bar_head = block(131, 145, 90, 0.7, fill="", outline="")
        oval(131, outline="#0c2028", width=1)

        # --- Outer ring: 24 modules, each with a fixed-color lamp ---
        self.lamps = []  # [(halo, main, hot, base colors)]
        step = 360 / MODULES
        for k in range(MODULES):
            a = 90 - k * step  # start at the top, go clockwise
            big = k % 3 == 0  # every third one is taller, for an uneven look
            top = 122 if big else 115
            cyan = LAMP_PATTERN[k] == "C"
            cols = ((CYAN_HALO, CYAN_MAIN, CYAN_HOT) if cyan
                    else (ORANGE_HALO, ORANGE_MAIN, ORANGE_HOT))

            block(92, 100, a, 6.8, fill=PLATE, outline=EDGE_DIM, width=1)
            block(96, top, a, 5.4, fill=BODY, outline=EDGE, width=1)
            block(top - 7, top, a, 3.6, fill=BODY_HI, outline=EDGE_DIM, width=1)
            # chamfered side edges
            block(98, top - 4, a - 4.6, 0.9, fill=EDGE_DIM, outline="")
            block(98, top - 4, a + 4.6, 0.9, fill=EDGE_DIM, outline="")

            block(100, 113, a, 3.5, fill="#04080b", outline=EDGE_DIM, width=1)  # socket
            self.lamps.append((
                block(100.5, 112.5, a, 3.3, fill=cols[0], outline=""),  # halo
                block(102, 111, a, 2.5, fill=cols[1], outline=""),      # body
                block(104.5, 108.5, a, 1.1, fill=cols[2], outline=""),  # white core
                cols,
            ))
            if big:  # the tall ones get an extra lamp on top
                self.lamps.append((
                    block(top - 6, top - 1, a, 2.0, fill=cols[0], outline=""),
                    block(top - 5.5, top - 1.5, a, 1.6, fill=cols[1], outline=""),
                    block(top - 4.5, top - 2.5, a, 0.7, fill=cols[2], outline=""),
                    cols,
                ))

        # --- Fine tick ring, 60 segments, for the precise readout ---
        self.segs = []
        st = 360 / SEGMENTS
        for i in range(SEGMENTS):
            self.segs.append(
                c.create_arc(
                    m - 85, m - 85, m + 85, m + 85,
                    start=90 - (i + 1) * st + st * 0.22, extent=st * 0.56,
                    style=tk.ARC, width=7, outline=TICK_OFF,
                )
            )
        oval(90, outline=RING_LINE, width=1)
        oval(79, outline=RING_LINE, width=1)

        # --- Broken inner glow ring: cyan upper left, amber lower right ---
        for i in range(30):
            a0 = 90 - i * 12
            col = GLOW_CYAN if 30 <= (a0 % 360) < 210 else GLOW_ORANGE
            self.core.append((
                c.create_arc(
                    m - 71, m - 71, m + 71, m + 71,
                    start=a0 - 11, extent=9.4,
                    style=tk.ARC, width=10, outline=col,
                ), col))

        # --- Middle hardware ring: grooves + fine radial lines ---
        oval(63, fill="#060b0f", outline=EDGE_DIM, width=2)
        for k in range(72):  # fine radial scoring
            a = k * 5
            x1, y1 = _pt(m, m, 54, a)
            x2, y2 = _pt(m, m, 61, a)
            c.create_line(x1, y1, x2, y2, fill=GROOVE, width=1)
        oval(53, fill="#05090d", outline=RING_LINE, width=1)
        for r in (49, 45, 41):
            oval(r, outline=GROOVE, width=1)

        # Thin blue ring that breathes/flickers with the core
        self.core.append((oval(39, outline="#1a7fa4", width=2), "#1a7fa4"))

        # --- Core: dark, with a deep well in the middle ---
        oval(36, fill="#04080c", outline=EDGE_DIM, width=1)
        for k in range(36):  # fine texture inside the core
            a = k * 10
            x1, y1 = _pt(m, m, 22, a)
            x2, y2 = _pt(m, m, 36, a)
            c.create_line(x1, y1, x2, y2, fill="#0a141b", width=1)
        for r in (32, 27):
            oval(r, outline="#0c1a22", width=1)
        oval(20, fill="#03060a", outline="#0d2b38", width=1)
        self.core.append((oval(13, outline="#176d8d", width=1), "#176d8d"))
        oval(9, fill="#020508", outline="")

    # -- called from the app --
    def start_refresh(self):
        self.busy = True
        self.offline = False
        self.t0 = time.monotonic()
        self.phase = 0.0
        self.anim = "pulse"
        self.pulse_t0 = self.t0
        self.pulse_end = None
        self.det_lb.config(text="polling…", fg=ACCENT)

    def set_result(self, load, ncpu, stamp):
        self.busy = False
        self.offline = False
        self.percent = max(0.0, min(100.0, load[0] / ncpu * 100.0))
        self.pct_lb.config(text="%d%%" % round(self.percent), fg=_load_color(self.percent / 100))
        self.det_lb.config(
            text="load %.2f %.2f %.2f / %d cpu" % (load[0], load[1], load[2], ncpu),
            fg=MUTED,
        )
        self.time_lb.config(text=stamp)
        self._finish_pulse()

    def set_error(self, msg, stamp):
        self.busy = False
        self.offline = True
        self.percent = 0.0
        self._shown_pct = -1.0
        self.pct_lb.config(text="--", fg="#ff5566")
        self.det_lb.config(text=msg[:34], fg="#ff5566")
        self.time_lb.config(text=stamp)
        self._finish_pulse()

    def _finish_pulse(self):
        """Data is in: let the bar finish fading back to dark, then show it."""
        if self.anim != "pulse":
            self.anim = "idle"
            return
        elapsed = time.monotonic() - self.pulse_t0
        cycles = math.floor(elapsed / PULSE_SECS) + 1  # always at least one
        self.pulse_end = self.pulse_t0 + cycles * PULSE_SECS

    # -- per-frame brightness update --
    def animate(self, now, dt):
        if self.busy:
            # flicker rate ramps from low to high
            prog = min(1.0, (now - self.t0) / FLICKER_RAMP)
            freq = FLICKER_F0 + (FLICKER_F1 - FLICKER_F0) * prog
            self.phase += freq * dt
            bright = 1.0 if (self.phase % 1.0) < 0.5 else FLICKER_LOW
        elif self.offline:
            bright = 0.22
        else:
            # idle breathing
            bright = 0.82 + 0.18 * math.sin(now * 2.2)

        # everything in the core is an outline-only arc or circle
        for item, col in self.core:
            c = "#ff3b4a" if self.offline else col
            if not self.offline and self.percent > 85:
                c = _mix(c, "#ff4436", (self.percent - 85) / 15 * 0.7)  # overload warning
            self.canvas.itemconfig(item, outline=_dim(c, bright))

        self._paint_lamps(now, bright)
        self._paint_loadbar(now, bright)
        self._paint_ticks(now, bright)

    def _paint_lamps(self, now, bright):
        """Outer module lamps: fixed cyan/amber colors, only brightness moves."""
        n = len(self.lamps)
        for i, (halo, main, hot, cols) in enumerate(self.lamps):
            if self.offline:
                k, cols = 0.30, ("#5a1a1f", "#8e2730", "#c05a5a")
            elif self.busy:
                # a chase light running lamp by lamp, on top of the flicker
                d = (int(now * 14) % n - i) % n
                k = bright * (1.0 if d < 3 else 0.55)
            else:
                k = 0.80 + 0.20 * math.sin(now * 1.7 + i * 0.5)  # gentle breathing
            for item, col in zip((halo, main, hot), cols):
                self.canvas.itemconfig(item, fill=_dim(col, k))

    def _paint_loadbar(self, now, bright):
        """Outer load bar: length = load, color = how bad the load is."""
        c = self.canvas

        if self.anim == "pulse":
            if self.pulse_end is not None and now >= self.pulse_end:
                self.anim = "idle"  # faded back to dark, show the real value
            else:
                # the whole ring fades dark -> bright -> dark while polling
                t = ((now - self.pulse_t0) / PULSE_SECS) % 1.0
                k = math.sin(math.pi * t) ** 1.4
                c.itemconfig(self.bar, extent=-359.9, outline=_dim(BAR_LOW, k))
                c.itemconfig(self.bar_halo, extent=-359.9, outline=_dim(BAR_LOW, k * 0.30))
                c.itemconfig(self.bar_head, fill="", outline="")
                return

        if self.offline:
            for it in (self.bar, self.bar_halo):
                c.itemconfig(it, extent=-0.1, outline=BAR_TRACK)
            c.itemconfig(self.bar_head, fill="", outline="")
            return

        ext = max(0.1, self.percent / 100 * 359.9)
        col = _load_color(min(1.0, self.percent / 100))
        k = bright if self.busy else 0.88 + 0.12 * math.sin(now * 2.2)
        c.itemconfig(self.bar, extent=-ext, outline=_dim(col, k))
        c.itemconfig(self.bar_halo, extent=-ext, outline=_dim(col, k * 0.28))

        # head highlight rides the tail of the bar
        m = self.SIZE / 2
        a = 90 - ext
        pts = []
        for j in range(4):  # outer edge, left -> right
            pts.extend(_pt(m, m, 145, a - 1.1 + 2.2 * j / 3))
        for j in range(4):  # inner edge, right -> left
            pts.extend(_pt(m, m, 131, a + 1.1 - 2.2 * j / 3))
        c.coords(self.bar_head, *pts)
        c.itemconfig(self.bar_head, fill=_dim(col, min(1.0, k * 1.25)))

    def _paint_ticks(self, now, bright):
        """Inner 60-segment ring: the precise load readout."""
        lit = int(round(self.percent / 100 * SEGMENTS))

        if self.busy:
            head = int(now * 42) % SEGMENTS
            for i, item in enumerate(self.segs):
                d = (head - i) % SEGMENTS
                if d < 6:
                    col = _dim(_load_color(i / SEGMENTS), 1.0 - d / 6 * 0.75)
                elif i < lit:
                    col = _dim(_load_color(i / SEGMENTS), 0.30)
                else:
                    col = TICK_OFF
                self.canvas.itemconfig(item, outline=col)
            self._shown_pct = -1.0
            return

        if self.offline:
            if self._shown_pct != -2.0:
                for i, item in enumerate(self.segs):
                    self.canvas.itemconfig(item, outline="#2c1015" if i % 5 else "#6e2029")
                self._shown_pct = -2.0
            return

        if self._shown_pct != self.percent:
            for i, item in enumerate(self.segs):
                self.canvas.itemconfig(
                    item, outline=_load_color(i / SEGMENTS) if i < lit else TICK_OFF
                )
            self._shown_pct = self.percent

        # the leading segment breathes along with the core
        if 0 < lit <= SEGMENTS:
            self.canvas.itemconfig(
                self.segs[lit - 1],
                outline=_dim(_load_color((lit - 1) / SEGMENTS), bright),
            )


# ---- Main window --------------------------------------------------------
class App(tk.Tk):
    def __init__(self, hosts):
        super().__init__()
        self.title("ARC REACTOR — machine loading monitor")
        self.configure(bg=BG)
        self.resizable(False, False)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground="#10202a", background="#16303c",
                        foreground=TEXT, arrowcolor=ACCENT, bordercolor="#2a5364",
                        lightcolor="#16303c", darkcolor="#16303c", padding=4)
        style.configure("Term.TButton", background="#0e2029", foreground=ACCENT,
                        bordercolor="#2a5364", lightcolor="#0e2029",
                        darkcolor="#0e2029", focuscolor=BG, relief="flat",
                        padding=(12, 3), font=("TkDefaultFont", 9, "bold"))
        style.map("Term.TButton",
                  background=[("active", "#1f4657"), ("pressed", "#26586c")],
                  foreground=[("active", CYAN_HOT)])
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#10202a")],
                  foreground=[("readonly", TEXT)],
                  background=[("active", "#1f4657")])
        self.option_add("*TCombobox*Listbox.background", "#0a1720")
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", "#1f4657")
        self.option_add("*TCombobox*Listbox.selectForeground", ACCENT)

        top = tk.Frame(self, bg=BG, padx=14, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="click the reactor to refresh it now", bg=BG,
                 fg=MUTED, font=("TkDefaultFont", 10)).pack(side="left")

        self.hosts = list(hosts)
        self.host_var = tk.StringVar(value=self.hosts[0])
        self.picker = ttk.Combobox(
            top, textvariable=self.host_var, values=self.hosts + [ALL_LABEL],
            state="readonly",
            width=max(12, max(len(h) for h in self.hosts) + 2),
            font=("TkDefaultFont", 10),
        )
        self.picker.pack(side="right")
        self.picker.bind("<<ComboboxSelected>>", self._host_changed)
        tk.Label(top, text="MACHINE ", bg=BG, fg=MUTED,
                 font=("TkDefaultFont", 10, "bold")).pack(side="right")

        self.body = tk.Frame(self, bg=BG, padx=10, pady=4)
        self.body.pack()
        self.reactors = {h: Reactor(self.body, h, self.refresh_one, self.open_terminal)
                         for h in self.hosts}
        self.visible = []
        self._show([self.hosts[0]])

        self.status = tk.Label(self, text="", bg=BG, fg=MUTED, anchor="w",
                               font=("TkFixedFont", 10), padx=16, pady=8)
        self.status.pack(fill="x")

        self.q = queue.Queue()
        self.inflight = set()
        self._last = time.monotonic()

        self.after(FPS_MS, self._tick)
        self.after(60, self._drain)
        self.after(300, self._auto_fire)

    # -- machine picker --
    def _show(self, hosts):
        """Lay out exactly these reactors, in a grid for the ALL view."""
        for r in self.reactors.values():
            r.grid_forget()
        for i, h in enumerate(hosts):
            self.reactors[h].grid(row=i // GRID_COLS, column=i % GRID_COLS,
                                  padx=6, pady=4)
        self.visible = list(hosts)

    def _host_changed(self, _event=None):
        pick = self.host_var.get()
        hosts = self.hosts if pick == ALL_LABEL else [pick]
        if hosts == self.visible:
            return
        self._show(hosts)
        self.picker.selection_clear()
        if pick == ALL_LABEL:
            self._say("showing all %d machines" % len(self.hosts))
        else:
            self._say("%s  %s" % (pick, self.reactors[pick].det_lb.cget("text")))

    # -- terminal --
    def open_terminal(self, host):
        """Open a terminal on that machine (ssh unless it is this one)."""
        for cmd in terminal_cmds(host):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError:
                continue  # that terminal is not installed, try the next
            self._say("%s: opened %s" % (host, cmd[0]))
            return
        self._say("no terminal found (tried mate-terminal, xterm)")

    # -- fetching --
    def refresh_all(self):
        for h in self.reactors:
            self.refresh_one(h)

    def refresh_one(self, host):
        if host in self.inflight:
            return
        self.inflight.add(host)
        self.reactors[host].start_refresh()
        if host in self.visible:
            self._say("polling %s …" % host)
        threading.Thread(target=self._work, args=(host,), daemon=True).start()

    def _work(self, host):
        try:
            l1, l5, l15, ncpu = probe(host)
            self.q.put((host, True, ((l1, l5, l15), ncpu)))
        except Exception as e:  # unreachable / no key / timeout all count as offline
            self.q.put((host, False, str(e)))

    def _drain(self):
        stamp = time.strftime("%H:%M:%S")
        while True:
            try:
                host, ok, payload = self.q.get_nowait()
            except queue.Empty:
                break
            self.inflight.discard(host)
            r = self.reactors[host]
            if ok:
                load, ncpu = payload
                r.set_result(load, ncpu, stamp)
                if host in self.visible:
                    self._say("%s  load %.2f / %d cpu  →  %d%%"
                              % (host, load[0], ncpu, round(r.percent)))
            else:
                r.set_error(payload, stamp)
                if host in self.visible:
                    self._say("%s unreachable: %s" % (host, payload))
        self.after(60, self._drain)

    # -- animation loop (only the visible reactors need painting) --
    def _tick(self):
        now = time.monotonic()
        dt = now - self._last
        self._last = now
        for h in self.visible:
            self.reactors[h].animate(now, dt)
        self.after(FPS_MS if len(self.visible) == 1 else FPS_MS_ALL, self._tick)

    # -- auto refresh every 10s --
    def _auto_fire(self):
        self.refresh_all()
        self.after(REFRESH_MS, self._auto_fire)

    def _say(self, msg):
        self.status.config(text=msg)


def main():
    hosts = sys.argv[1:] or DEFAULT_HOSTS
    App(hosts).mainloop()


if __name__ == "__main__":
    main()
