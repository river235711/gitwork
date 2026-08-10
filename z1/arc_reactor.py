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

# ---- 配色 (照參考圖：全黑機械件 + 青/橘雙色燈) ---------------------------
BG = "#04070b"
PANEL = "#050a0f"
DIM = "#03060a"  # 變暗時要混向的底色
TEXT = "#c8dbe6"
MUTED = "#5e7686"
ACCENT = "#3fd0f0"

# 機械件(參考圖裡幾乎是純黑，只有邊角吃到一點藍光)
BODY = "#070b10"  # 模組本體
BODY_HI = "#0d161d"  # 上蓋
PLATE = "#0a1219"  # 底座
EDGE = "#2b4553"  # 亮邊
EDGE_DIM = "#16232c"  # 暗邊
GROOVE = "#0d1c25"  # 同心刻紋
RING_LINE = "#123642"

# 燈：參考圖的青與橘，各有 光暈 / 本體 / 白熱芯 三層
CYAN_HALO, CYAN_MAIN, CYAN_HOT = "#0d6f9e", "#2fc8ff", "#dbf4ff"
ORANGE_HALO, ORANGE_MAIN, ORANGE_HOT = "#a63f08", "#ff8a12", "#ffe3b4"
GLOW_CYAN = "#1f9ed6"
GLOW_ORANGE = "#e2661a"

# 燈的固定排列(0=正上方，順時針)：左半偏青、右下偏橘，刻意排得不規則
LAMP_PATTERN = "OCCOOC" "OOCOOC" "OCOCCC" "CCOCCO"

# 負載光條(額外加的，不屬於參考圖)
BAR_TRACK = "#0a151c"
TICK_OFF = "#0c1b23"
BAR_LOW = (0x3A, 0xD2, 0xFF)  # 低載：青
BAR_MID = (0xFF, 0x9A, 0x2E)  # 中載：橘
BAR_HIGH = (0xFF, 0x3B, 0x4A)  # 高載：紅

# ---- 動畫參數 ------------------------------------------------------------
FPS_MS = 33  # 動畫 tick (約 30fps)
FLICKER_F0 = 1.8  # 開始 refresh 時的閃爍頻率 (Hz)
FLICKER_F1 = 22.0  # 衝到最高的閃爍頻率 (Hz)
FLICKER_RAMP = 2.5  # 幾秒內從 F0 拉到 F1
FLICKER_LOW = 0.12  # 閃爍暗相的亮度

MODULES = 24  # 外圈機械模組(粗顆粒燈)數量
SEGMENTS = 60  # 內圈細刻度格數(精準讀值)
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

    SIZE = 296

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

    # -- 畫出反應爐本體 (正面視角，全部用正圓，無透視) --
    def _build(self):
        c = self.canvas
        m = self.SIZE / 2
        self.core = []  # (item, 基礎色) — 亮度由動畫控制

        def oval(r, **kw):
            return c.create_oval(m - r, m - r, m + r, m + r, **kw)

        def block(r0, r1, deg, half, **kw):
            """一塊沿著圓周擺的機械件(內外兩條邊都是圓弧)。"""
            pts = []
            for j in range(6):
                pts.extend(_pt(m, m, r1, deg - half + half * 2 * j / 5))
            for j in range(6):
                pts.extend(_pt(m, m, r0, deg + half - half * 2 * j / 5))
            return c.create_polygon(pts, **kw)

        # 背後的散光暈(Tk 沒有 alpha，用幾層同心色階假裝)
        for r, col in ((142, "#050a0e"), (128, "#061019"), (112, "#07141d")):
            oval(r, fill=col, outline="")

        # --- 加的東西 1：最外圈負載光條(底軌 + 光暈 + 本體 + 頭端亮點) ---
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

        # --- 外圈：24 顆機械模組，每顆中間一盞方燈(顏色固定，照參考圖排) ---
        self.lamps = []  # [(halo, main, hot, 基礎三色)]
        step = 360 / MODULES
        for k in range(MODULES):
            a = 90 - k * step  # 正上方開始順時針
            big = k % 3 == 0  # 每三顆做一顆比較高的，做出參考圖的參差感
            top = 122 if big else 115
            cyan = LAMP_PATTERN[k] == "C"
            cols = ((CYAN_HALO, CYAN_MAIN, CYAN_HOT) if cyan
                    else (ORANGE_HALO, ORANGE_MAIN, ORANGE_HOT))

            block(92, 100, a, 6.8, fill=PLATE, outline=EDGE_DIM, width=1)
            block(96, top, a, 5.4, fill=BODY, outline=EDGE, width=1)
            block(top - 7, top, a, 3.6, fill=BODY_HI, outline=EDGE_DIM, width=1)
            # 側邊斜切亮邊
            block(98, top - 4, a - 4.6, 0.9, fill=EDGE_DIM, outline="")
            block(98, top - 4, a + 4.6, 0.9, fill=EDGE_DIM, outline="")

            block(100, 113, a, 3.5, fill="#04080b", outline=EDGE_DIM, width=1)  # 燈座
            self.lamps.append((
                block(100.5, 112.5, a, 3.3, fill=cols[0], outline=""),  # 光暈
                block(102, 111, a, 2.5, fill=cols[1], outline=""),      # 本體
                block(104.5, 108.5, a, 1.1, fill=cols[2], outline=""),  # 白熱芯
                cols,
            ))
            if big:  # 大顆的頂上多一盞小燈
                self.lamps.append((
                    block(top - 6, top - 1, a, 2.0, fill=cols[0], outline=""),
                    block(top - 5.5, top - 1.5, a, 1.6, fill=cols[1], outline=""),
                    block(top - 4.5, top - 2.5, a, 0.7, fill=cols[2], outline=""),
                    cols,
                ))

        # --- 加的東西 2：細刻度環 60 格，精準讀值 ---
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

        # --- 內側斷續發光環：左上青、右下橘(照參考圖) ---
        for i in range(30):
            a0 = 90 - i * 12
            col = GLOW_CYAN if 30 <= (a0 % 360) < 210 else GLOW_ORANGE
            self.core.append((
                c.create_arc(
                    m - 71, m - 71, m + 71, m + 71,
                    start=a0 - 11, extent=9.4,
                    style=tk.ARC, width=10, outline=col,
                ), col))

        # --- 中段機械環：同心刻紋 + 細放射線 ---
        oval(63, fill="#060b0f", outline=EDGE_DIM, width=2)
        for k in range(72):  # 細放射刻線
            a = k * 5
            x1, y1 = _pt(m, m, 54, a)
            x2, y2 = _pt(m, m, 61, a)
            c.create_line(x1, y1, x2, y2, fill=GROOVE, width=1)
        oval(53, fill="#05090d", outline=RING_LINE, width=1)
        for r in (49, 45, 41):
            oval(r, outline=GROOVE, width=1)

        # 內環上的一圈藍色細光(會跟著呼吸/閃爍)
        self.core.append((oval(39, outline="#1a7fa4", width=2), "#1a7fa4"))

        # --- 核心：暗色，中間是深洞 ---
        oval(36, fill="#04080c", outline=EDGE_DIM, width=1)
        for k in range(36):  # 核心內的細紋路
            a = k * 10
            x1, y1 = _pt(m, m, 22, a)
            x2, y2 = _pt(m, m, 36, a)
            c.create_line(x1, y1, x2, y2, fill="#0a141b", width=1)
        for r in (32, 27):
            oval(r, outline="#0c1a22", width=1)
        oval(20, fill="#03060a", outline="#0d2b38", width=1)
        self.core.append((oval(13, outline="#176d8d", width=1), "#176d8d"))
        oval(9, fill="#020508", outline="")

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

        # 核心那些件都是只有 outline 的圓弧/圓圈
        for item, col in self.core:
            c = "#ff3b4a" if self.offline else col
            if not self.offline and self.percent > 85:
                c = _mix(c, "#ff4436", (self.percent - 85) / 15 * 0.7)  # 過載示警
            self.canvas.itemconfig(item, outline=_dim(c, bright))

        self._paint_lamps(now, bright)
        self._paint_loadbar(now, bright)
        self._paint_ticks(now, bright)

    def _paint_lamps(self, now, bright):
        """外圈模組燈：顏色固定(照參考圖的青/橘)，只有亮度會動。"""
        n = len(self.lamps)
        for i, (halo, main, hot, cols) in enumerate(self.lamps):
            if self.offline:
                k, cols = 0.30, ("#5a1a1f", "#8e2730", "#c05a5a")
            elif self.busy:
                # 一顆一顆跑的掃描光，疊在閃爍的亮度上
                d = (int(now * 14) % n - i) % n
                k = bright * (1.0 if d < 3 else 0.55)
            else:
                k = 0.80 + 0.20 * math.sin(now * 1.7 + i * 0.5)  # 微微呼吸
            for item, col in zip((halo, main, hot), cols):
                self.canvas.itemconfig(item, fill=_dim(col, k))

    def _paint_loadbar(self, now, bright):
        """最外圈負載光條：整條的長度 = 負載，顏色 = 負載嚴重度。"""
        c = self.canvas
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

        # 頭端亮點跟著條子的尾巴跑
        m = self.SIZE / 2
        a = 90 - ext
        pts = []
        for j in range(4):  # 外緣 左->右
            pts.extend(_pt(m, m, 145, a - 1.1 + 2.2 * j / 3))
        for j in range(4):  # 內緣 右->左
            pts.extend(_pt(m, m, 131, a + 1.1 - 2.2 * j / 3))
        c.coords(self.bar_head, *pts)
        c.itemconfig(self.bar_head, fill=_dim(col, min(1.0, k * 1.25)))

    def _paint_ticks(self, now, bright):
        """內圈 60 格細刻度：精準的負載讀值。"""
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

        # 最前端那格跟著核心一起呼吸
        if 0 < lit <= SEGMENTS:
            self.canvas.itemconfig(
                self.segs[lit - 1],
                outline=_dim(_load_color((lit - 1) / SEGMENTS), bright),
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
