"""鋼鐵人反應爐風格的機器 loading 監看器 (Tk)。

- 中間反應爐核心：refresh(抓資料)時快速閃爍，閃爍頻率由低到高。
- 周圍圓周光條：顯示那台機器的 loading 高低 (load average / CPU 數)。
- 預設監看 TE0037 / sirius01 / WilldeMacBook-Air.local 三台，
  也可以用 argv 換掉：python3 arc_reactor.py hostA hostB ...

本機直接跑 uptime，遠端用 ssh BatchMode(需先設好金鑰，不會跳密碼)。
"""

import math
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

DEFAULT_HOSTS = ["TE0037", "sirius01", "WilldeMacBook-Air.local"]

# ---- 配色 ----------------------------------------------------------------
BG = "#070c11"
PANEL = "#0c141b"
DIM = "#05090d"  # 變暗時要混向的底色
TEXT = "#c8dbe6"
MUTED = "#5e7686"
ACCENT = "#3fd0f0"

BAR_OFF = "#11242d"  # 光條沒亮的格子
BAR_LOW = (0x2F, 0xE6, 0xFF)  # 低載：青
BAR_MID = (0xFF, 0xC1, 0x3B)  # 中載：琥珀
BAR_HIGH = (0xFF, 0x3B, 0x4A)  # 高載：紅

# ---- 動畫參數 ------------------------------------------------------------
FPS_MS = 33  # 動畫 tick (約 30fps)
FLICKER_F0 = 1.8  # 開始 refresh 時的閃爍頻率 (Hz)
FLICKER_F1 = 22.0  # 衝到最高的閃爍頻率 (Hz)
FLICKER_RAMP = 2.5  # 幾秒內從 F0 拉到 F1
FLICKER_LOW = 0.12  # 閃爍暗相的亮度

SEGMENTS = 60  # 圓周光條格數
SSH_TIMEOUT = 12


# ---- 小工具 --------------------------------------------------------------
def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def _rgb(color):
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))


def _mix(c1, c2, t):
    """c1、c2 可以是 #rrggbb 或 (r,g,b)，回傳混色後的 #rrggbb。"""
    a = _rgb(c1) if isinstance(c1, str) else c1
    b = _rgb(c2) if isinstance(c2, str) else c2
    return _hex(a[i] + (b[i] - a[i]) * t for i in range(3))


def _dim(color, k):
    """把顏色往底色壓暗，k=1 原色、k=0 全暗。"""
    return _mix(DIM, color, max(0.0, min(1.0, k)))


def _load_color(frac):
    """0~1 的位置 -> 青 / 琥珀 / 紅 漸層。"""
    if frac < 0.5:
        return _mix(BAR_LOW, BAR_MID, frac / 0.5)
    return _mix(BAR_MID, BAR_HIGH, (frac - 0.5) / 0.5)


def _pt(cx, cy, r, deg):
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)


# ---- 抓 loading ----------------------------------------------------------
_LOAD_RE = re.compile(r"load averages?:\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)")
_PROBE = "uptime; getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu"


def _is_local(host):
    me = socket.gethostname()
    names = {me, me.split(".")[0], "localhost", "127.0.0.1"}
    return host in names or host.split(".")[0] in names


def probe(host):
    """回傳 (load1, load5, load15, ncpu)，失敗就丟 RuntimeError。"""
    if _is_local(host):
        cmd = ["/bin/sh", "-c", _PROBE]
    else:
        cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=6",
            "-o", "StrictHostKeyChecking=accept-new",
            host,
            _PROBE,
        ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=SSH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError("timeout")
    except OSError as e:
        raise RuntimeError(str(e))

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


# ---- 反應爐 widget -------------------------------------------------------
class Reactor(tk.Frame):
    """一台機器 = 一顆反應爐 + 底下的文字。"""

    SIZE = 236

    def __init__(self, master, host, on_click):
        super().__init__(master, bg=PANEL, padx=10, pady=12)
        self.host = host

        self.percent = 0.0  # 目前顯示的負載百分比
        self.busy = False  # 是否正在 refresh
        self.offline = False
        self.t0 = 0.0  # 這次 refresh 的起始時間
        self.phase = 0.0  # 閃爍相位累加器
        self._shown_pct = -1.0  # 光條上次畫的值，避免每格都重畫

        self.canvas = tk.Canvas(
            self, width=self.SIZE, height=self.SIZE,
            bg=PANEL, highlightthickness=0, cursor="hand2",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda _e: on_click(self.host))

        self.name_lb = tk.Label(
            self, text=host, bg=PANEL, fg=ACCENT,
            font=("TkDefaultFont", 12, "bold"),
        )
        self.name_lb.pack(pady=(8, 0))
        self.pct_lb = tk.Label(
            self, text="--", bg=PANEL, fg=TEXT, font=("TkFixedFont", 20, "bold")
        )
        self.pct_lb.pack()
        self.det_lb = tk.Label(
            self, text="尚未讀取", bg=PANEL, fg=MUTED, font=("TkFixedFont", 10)
        )
        self.det_lb.pack()
        self.time_lb = tk.Label(self, text="", bg=PANEL, fg=MUTED, font=("TkFixedFont", 9))
        self.time_lb.pack()

        self._build()

    # -- 畫出反應爐本體 --
    def _build(self):
        c = self.canvas
        m = self.SIZE / 2

        def oval(r, **kw):
            return c.create_oval(m - r, m - r, m + r, m + r, **kw)

        # 外殼
        oval(112, fill="#0f171e", outline="#1e2d38", width=3)
        oval(106, outline="#16222b", width=1)

        # 圓周光條：60 格，從正上方順時針排
        self.segs = []
        step = 360 / SEGMENTS
        for i in range(SEGMENTS):
            start = 90 - (i + 1) * step + step * 0.18
            self.segs.append(
                c.create_arc(
                    m - 98, m - 98, m + 98, m + 98,
                    start=start, extent=step * 0.64,
                    style=tk.ARC, width=13, outline=BAR_OFF,
                )
            )

        oval(86, outline="#22323d", width=2)

        # 線圈之間的縫隙光(先畫一整圈亮環，等下用線圈蓋掉大部分)
        self.gap_glow = oval(80, fill="#1c9ec2", outline="")

        # 10 顆線圈
        for k in range(10):
            a0 = 90 + k * 36
            half = 14.0
            pts = []
            for a in (a0 - half + half * 2 * j / 6 for j in range(7)):
                pts.extend(_pt(m, m, 79, a))
            for a in (a0 + half - half * 2 * j / 6 for j in range(7)):
                pts.extend(_pt(m, m, 50, a))
            c.create_polygon(pts, fill="#8d9dab", outline="#26343f", width=2)
            c.create_polygon(
                pts[:14] + list(_pt(m, m, 68, a0 + half)) + list(_pt(m, m, 68, a0 - half)),
                fill="#b9c8d4", outline="",
            )

        # 核心
        oval(47, fill="#061019", outline="#2b3d49", width=2)
        self.core = []  # (item, 基礎色) — 亮度由動畫控制
        for r, col in ((42, "#0c5f7d"), (34, "#189fc4"), (26, "#5fd8f2")):
            self.core.append((oval(r, fill=col, outline=""), col))

        # 核心放射光芒
        for k in range(12):
            a = k * 30 + 15
            x1, y1 = _pt(m, m, 15, a)
            x2, y2 = _pt(m, m, 33, a)
            self.core.append(
                (c.create_line(x1, y1, x2, y2, fill="#d8f6ff", width=3), "#d8f6ff")
            )

        for r, col in ((15, "#a8ecff"), (8, "#ffffff")):
            self.core.append((oval(r, fill=col, outline=""), col))

        self.core.append((self.gap_glow, "#1c9ec2"))

    # -- 外部呼叫 --
    def start_refresh(self):
        self.busy = True
        self.offline = False
        self.t0 = time.monotonic()
        self.phase = 0.0
        self.det_lb.config(text="讀取中…", fg=ACCENT)

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

    def set_error(self, msg, stamp):
        self.busy = False
        self.offline = True
        self.percent = 0.0
        self._shown_pct = -1.0
        self.pct_lb.config(text="--", fg="#ff5566")
        self.det_lb.config(text=msg[:34], fg="#ff5566")
        self.time_lb.config(text=stamp)

    # -- 每個 frame 更新亮度 --
    def animate(self, now, dt):
        if self.busy:
            # 閃爍頻率隨時間由低到高
            prog = min(1.0, (now - self.t0) / FLICKER_RAMP)
            freq = FLICKER_F0 + (FLICKER_F1 - FLICKER_F0) * prog
            self.phase += freq * dt
            bright = 1.0 if (self.phase % 1.0) < 0.5 else FLICKER_LOW
        elif self.offline:
            bright = 0.22
        else:
            # 平常慢慢呼吸
            bright = 0.82 + 0.18 * math.sin(now * 2.2)

        base = "#ff3b4a" if self.offline else None
        for item, col in self.core:
            c = base if base else col
            if not self.offline and self.percent > 60:
                # 高載時核心偏紅
                c = _mix(c, "#ff5a3c", (self.percent - 60) / 40 * 0.55)
            self.canvas.itemconfig(item, fill=_dim(c, bright))

        self._paint_bar(now, bright)

    def _paint_bar(self, now, bright):
        lit = int(round(self.percent / 100 * SEGMENTS))

        if self.busy:
            # refresh 中：光條跑一圈掃描光
            head = int(now * 42) % SEGMENTS
            for i, item in enumerate(self.segs):
                d = (head - i) % SEGMENTS
                if d < 6:
                    col = _dim(_load_color(i / SEGMENTS), 1.0 - d / 6 * 0.75)
                elif i < lit:
                    col = _dim(_load_color(i / SEGMENTS), 0.30)
                else:
                    col = BAR_OFF
                self.canvas.itemconfig(item, outline=col)
            self._shown_pct = -1.0
            return

        if self.offline:
            if self._shown_pct != -2.0:
                for i, item in enumerate(self.segs):
                    self.canvas.itemconfig(
                        item, outline="#3a1218" if i % 5 else "#7d2530"
                    )
                self._shown_pct = -2.0
            return

        if self._shown_pct != self.percent:
            for i, item in enumerate(self.segs):
                col = _load_color(i / SEGMENTS) if i < lit else BAR_OFF
                self.canvas.itemconfig(item, outline=col)
            self._shown_pct = self.percent

        # 最前端那格跟著核心一起呼吸，看起來比較活
        if 0 < lit <= SEGMENTS:
            head = self.segs[lit - 1]
            self.canvas.itemconfig(
                head, outline=_dim(_load_color((lit - 1) / SEGMENTS), bright)
            )


# ---- 主視窗 --------------------------------------------------------------
class App(tk.Tk):
    def __init__(self, hosts):
        super().__init__()
        self.title("ARC REACTOR — 機器 loading 監看")
        self.configure(bg=BG)
        self.resizable(False, False)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", background="#16303c", foreground=TEXT,
                        bordercolor="#2a5364", focuscolor=BG, padding=6)
        style.map("TButton", background=[("active", "#1f4657")])
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TSpinbox", fieldbackground="#10202a", foreground=TEXT,
                        arrowcolor=TEXT, bordercolor="#2a5364")

        top = tk.Frame(self, bg=BG, padx=14, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="ARC  REACTOR", bg=BG, fg=ACCENT,
                 font=("TkDefaultFont", 15, "bold")).pack(side="left")
        tk.Label(top, text="  機器 loading 監看 — 點反應爐可單獨更新", bg=BG,
                 fg=MUTED, font=("TkDefaultFont", 10)).pack(side="left")

        self.auto = tk.BooleanVar(value=False)
        self.interval = tk.IntVar(value=30)
        ttk.Spinbox(top, from_=5, to=600, increment=5, width=5,
                    textvariable=self.interval).pack(side="right", padx=(4, 0))
        ttk.Checkbutton(top, text="自動更新 (秒)", variable=self.auto,
                        command=self._auto_changed).pack(side="right", padx=6)
        ttk.Button(top, text="REFRESH ALL", command=self.refresh_all).pack(side="right")

        body = tk.Frame(self, bg=BG, padx=10, pady=4)
        body.pack()
        self.reactors = {}
        for h in hosts:
            r = Reactor(body, h, self.refresh_one)
            r.pack(side="left", padx=6)
            self.reactors[h] = r

        self.status = tk.Label(self, text="", bg=BG, fg=MUTED, anchor="w",
                               font=("TkFixedFont", 10), padx=16, pady=8)
        self.status.pack(fill="x")

        self.q = queue.Queue()
        self.inflight = set()
        self._last = time.monotonic()
        self._auto_job = None

        self.after(FPS_MS, self._tick)
        self.after(60, self._drain)
        self.after(300, self.refresh_all)

    # -- 抓資料 --
    def refresh_all(self):
        for h in self.reactors:
            self.refresh_one(h)

    def refresh_one(self, host):
        if host in self.inflight:
            return
        self.inflight.add(host)
        self.reactors[host].start_refresh()
        self._say("讀取 %s …" % host)
        threading.Thread(target=self._work, args=(host,), daemon=True).start()

    def _work(self, host):
        try:
            l1, l5, l15, ncpu = probe(host)
            self.q.put((host, True, ((l1, l5, l15), ncpu)))
        except Exception as e:  # 連不上 / 沒金鑰 / timeout 都算離線
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
                self._say("%s  load %.2f / %d cpu  →  %d%%"
                          % (host, load[0], ncpu, round(r.percent)))
            else:
                r.set_error(payload, stamp)
                self._say("%s 連不上：%s" % (host, payload))
        self.after(60, self._drain)

    # -- 動畫主迴圈 --
    def _tick(self):
        now = time.monotonic()
        dt = now - self._last
        self._last = now
        for r in self.reactors.values():
            r.animate(now, dt)
        self.after(FPS_MS, self._tick)

    # -- 自動更新 --
    def _auto_changed(self):
        if self._auto_job:
            self.after_cancel(self._auto_job)
            self._auto_job = None
        if self.auto.get():
            self._schedule_auto()

    def _schedule_auto(self):
        secs = max(5, self.interval.get())
        self._auto_job = self.after(secs * 1000, self._auto_fire)

    def _auto_fire(self):
        self.refresh_all()
        if self.auto.get():
            self._schedule_auto()

    def _say(self, msg):
        self.status.config(text=msg)


def main():
    hosts = sys.argv[1:] or DEFAULT_HOSTS
    App(hosts).mainloop()


if __name__ == "__main__":
    main()
