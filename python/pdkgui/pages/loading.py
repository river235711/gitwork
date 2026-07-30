#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/loading.py
----------------
LOADING page: how busy each machine is, so a user can tell where to start a
verification without logging into all of them first.

The machines come from config.page_file("LOADING") (data/hosts.txt, one per
line). Each is asked for three things in a single command -- the load average,
the core count and the memory figures -- read straight out of /proc:

    cat /proc/loadavg; nproc; awk '/^Mem(Total|Available):/{print $1, $2}' \
        /proc/meminfo

The machine pdkgui runs on is read directly; the others over ssh in BatchMode,
so one without a key fails at once instead of waiting on a password prompt.

All the probes are started at the same time and collected by a poll on the Tk
event loop, so a slow or dead machine delays nothing but its own row.

Each row also has two buttons: Terminal opens a shell on that machine, pdkgui
opens one with pdkgui already starting in it.
"""

import os
import time
import shutil
import shlex
import subprocess

import tkinter as tk
from tkinter import messagebox

from .base import BasePage
import config

# what to read on the far end -- /proc only, so it works on any Linux
_PROBE = ("cat /proc/loadavg; nproc; "
          "awk '/^Mem(Total|Available):/{print $1, $2}' /proc/meminfo")

_SSH_OPTS = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=3")

PROBE_TIMEOUT = 10.0        # seconds before a machine counts as not answering
REFRESH_EVERY = 30000       # ms between automatic refreshes while on this tab
_POLL_EVERY = 200           # ms between checks for finished probes

# thresholds, in percent
_CPU_IDLE, _CPU_BUSY = 40, 75        # below/above -> idle / busy / loaded
_MEM_GOOD, _MEM_TIGHT = 30, 15       # free memory: above/below -> ok / tight / low

_GREEN = "#1a7f37"          # same green as the SYSTEM page
_AMBER = "#b3860b"
_RED = "#c0392b"
_GREY = "#888888"
_TRACK = "#d0d0d0"

_BAR_WIDTH = 130
_BAR_HEIGHT = 12


def probe_command(host):
    """The argv that prints one machine's figures.

    The machine we are on is read directly: no ssh, so the tab still works when
    keys are not set up, and the local row is always right."""
    if host == config.hostname():
        return ["bash", "-c", _PROBE]
    return ["ssh"] + list(_SSH_OPTS) + [host, _PROBE]


def shell_command(host, launcher=None, workdir=None):
    """The argv for a terminal working on `host`.

    The shell is left interactive (`exec $SHELL -l`) so the window is a place to
    work, not a one-shot command. With a launcher it starts pdkgui there first,
    in the background, so one click gives both.

    A login shell matters: the EDA tools come from Environment Modules, which a
    plain `ssh host command` shell has never sourced."""
    # each statement carries its own terminator: '&' already ends a command, and
    # following it with ';' is a bash syntax error
    parts = []
    if workdir:
        # not being able to cd is no reason to refuse the terminal
        parts.append("cd %s 2>/dev/null;" % shlex.quote(workdir))
    if launcher:
        parts.append("%s >/dev/null 2>&1 &" % shlex.quote(launcher))
    parts.append("exec $SHELL -l")
    inner = " ".join(parts)

    if host == config.hostname():
        return ["bash", "-c", inner]
    # -X forwards the display (pdkgui and the calibre viewers are X programs);
    # -t forces a pty, which ssh does not allocate when given a command
    return ["ssh", "-X", "-t", host, inner]


def parse_probe(text):
    """Turn the probe output into (cpu_percent, mem_free_percent, mem_free_gb),
    or None when it cannot be read.

    cpu_percent is the 1-minute load average over the core count, capped at 100:
    'how much of this machine is taken', which is what a load figure means only
    once you know the core count (load 8 on 32 cores is an idle machine).

    Memory is read as MemTotal/MemAvailable key-value pairs rather than by
    position, so a kernel too old to report MemAvailable just leaves the memory
    unknown instead of shifting every number along."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    try:
        load1 = float(lines[0].split()[0])
        ncpu = int(lines[1])
        if ncpu <= 0:
            return None
    except (ValueError, IndexError):
        return None

    mem = {}
    for ln in lines[2:]:
        parts = ln.split()
        if len(parts) >= 2:
            try:
                mem[parts[0].rstrip(":")] = int(parts[1])
            except ValueError:
                pass
    total, avail = mem.get("MemTotal"), mem.get("MemAvailable")

    cpu = min(100.0, load1 / ncpu * 100.0)
    if not total or avail is None:
        return cpu, None, None
    return cpu, avail * 100.0 / total, avail / 1024.0 / 1024.0


def cpu_state(cpu_percent):
    """(label, colour) for a cpu figure."""
    if cpu_percent < _CPU_IDLE:
        return "idle", _GREEN
    if cpu_percent < _CPU_BUSY:
        return "busy", _AMBER
    return "loaded", _RED


def mem_state(mem_free_percent):
    if mem_free_percent is None:
        return "", _GREY
    if mem_free_percent > _MEM_GOOD:
        return "ok", _GREEN
    if mem_free_percent > _MEM_TIGHT:
        return "tight", _AMBER
    return "low", _RED


def verdict(cpu_percent, mem_free_percent):
    """One word for the whole machine: the worse of its cpu and memory.

    A machine with spare cores but no memory left is no use for a verification,
    so it must not be reported as idle."""
    cpu_label, cpu_colour = cpu_state(cpu_percent)
    _mem_label, mem_colour = mem_state(mem_free_percent)
    if mem_colour == _RED and cpu_colour != _RED:
        return "no memory", _RED
    if mem_colour == _AMBER and cpu_colour == _GREEN:
        return "low memory", _AMBER
    return cpu_label, cpu_colour


class LoadingPage(BasePage):
    module = "LOADING"
    bg = "white"

    def build(self):
        self.hosts = config.read_lines(config.page_file(self.module))
        self._running = {}          # host -> (Popen, started_at)
        self._results = {}          # host -> (cpu, mem_percent, mem_gb) or None
        self._poll_job = None
        self._refresh_job = None

        self.grid_columnconfigure(0, weight=1)

        head = tk.Frame(self, bg=self.bg)
        head.grid(row=0, column=0, sticky="we")
        head.grid_columnconfigure(1, weight=1)
        tk.Label(head, text="Machine loading", bg=self.bg, anchor="w",
                 font=config.ui_font(1, "bold")).grid(row=0, column=0, sticky="w")
        tk.Button(head, text="Refresh", width=10,
                  command=self.refresh).grid(row=0, column=2, sticky="e")

        self._best = tk.Label(self, bg=self.bg, anchor="w", fg=_GREY,
                              font=config.ui_font(0, "bold"))
        self._best.grid(row=1, column=0, sticky="w", pady=(4, 10))

        self._rows = {}
        table = tk.Frame(self, bg=self.bg)
        table.grid(row=2, column=0, sticky="nsew")
        table.grid_columnconfigure(8, weight=1)   # slack goes on the right
        self.grid_rowconfigure(2, weight=1)
        for i, host in enumerate(self.hosts):
            self._rows[host] = self._build_row(table, i, host)

        if not self.hosts:
            tk.Label(self, bg=self.bg, fg=_GREY, justify="left", anchor="w",
                     text="No machines listed in\n%s"
                          % config.page_file(self.module)
                     ).grid(row=3, column=0, sticky="w")

        # The legend stays, but not the path of the host list: that is an admin's
        # business, and it is a long path in front of every user, every time.
        tk.Label(self, bg=self.bg, fg=_GREY, anchor="w", justify="left",
                 font=config.ui_font(-1),
                 text="CPU is the 1-minute load average over the core count; "
                      "MEM is free memory."
                 ).grid(row=4, column=0, sticky="w", pady=(12, 0))

    def _build_row(self, table, index, host):
        """One machine's row; the widgets are filled in as answers arrive."""
        row = {}
        tk.Label(table, text=host, bg=self.bg, anchor="w",
                 font=config.mono_font()).grid(row=index, column=0, sticky="w",
                                               padx=(4, 12), pady=3)
        row["cpu_bar"] = _Bar(table, self.bg)
        row["cpu_bar"].grid(row=index, column=1, padx=(0, 6))
        row["cpu"] = tk.Label(table, bg=self.bg, width=5, anchor="e",
                              font=config.mono_font())
        row["cpu"].grid(row=index, column=2, padx=(0, 18))
        row["mem_bar"] = _Bar(table, self.bg)
        row["mem_bar"].grid(row=index, column=3, padx=(0, 6))
        row["mem"] = tk.Label(table, bg=self.bg, width=14, anchor="w",
                              font=config.mono_font())
        row["mem"].grid(row=index, column=4, padx=(0, 18))
        row["verdict"] = tk.Label(table, bg=self.bg, anchor="w", width=22,
                                  font=config.ui_font(0, "bold"))
        row["verdict"].grid(row=index, column=5, sticky="w")
        tk.Button(table, text="Terminal", width=9,
                  command=lambda h=host: self._open_terminal(h)
                  ).grid(row=index, column=6, padx=(0, 4))
        tk.Button(table, text="pdkgui", width=9,
                  command=lambda h=host: self._open_terminal(h, with_pdkgui=True)
                  ).grid(row=index, column=7)
        return row

    # ------------------------------------------------------------------
    def _open_terminal(self, host, with_pdkgui=False):
        """Open a terminal on that machine, optionally starting pdkgui in it."""
        launcher = self._launcher() if with_pdkgui else None
        if with_pdkgui and not launcher:
            messagebox.showerror("pdkgui", "Could not find the pdkgui launcher "
                                           "to start on %s." % host)
            return
        command = shell_command(host, launcher=launcher,
                                workdir=getattr(self.app, "launch_dir", None))
        for term in config.terminals():
            if shutil.which(term[0]):
                try:
                    # a terminal emulator is a desktop program: see desktop_env
                    subprocess.Popen(term + command, env=config.desktop_env())
                    return
                except Exception:
                    continue
        messagebox.showerror("pdkgui", "No usable terminal found. Run it "
                                       "manually:\n%s" % " ".join(command))

    @staticmethod
    def _launcher():
        """The pdkgui to start on the other machine.

        The current release first, so a machine opened from a superseded window
        still gets the new pdkgui; otherwise the launcher beside this code. Both
        are absolute paths on the shared filesystem, so they mean the same thing
        on every machine -- no site path is hard-coded here."""
        candidates = [config.live_launcher(),
                      os.path.join(config.BASE_DIR, "pdkgui")]
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return None

    # ------------------------------------------------------------------
    def on_show(self):
        """Fresh figures every time the tab is opened -- a load average from
        when the window was started would be worse than none."""
        self.refresh()

    def flush(self):
        """Called on the way out of the tab and on close (see
        pdkgui_app._flush_page): stop polling and drop any probe still running,
        so nothing fires against a destroyed widget."""
        self._cancel_jobs()
        self._kill_running()

    # ------------------------------------------------------------------
    def refresh(self):
        """Ask every machine at once. Each row says 'checking...' until its own
        answer arrives, so a dead machine holds up nothing but itself."""
        self._cancel_jobs()
        self._kill_running()

        self._best.configure(text="Checking %d machines..." % len(self.hosts),
                             fg=_GREY)
        for host in self.hosts:
            self._results.pop(host, None)
            self._show_message(host, "checking...", _GREY)
            try:
                proc = subprocess.Popen(
                    probe_command(host), stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, universal_newlines=True)
            except Exception as e:
                self._show_message(host, "cannot run ssh (%s)" % e, _RED)
                continue
            self._running[host] = (proc, time.time())

        if self._running:
            self._poll_job = self.after(_POLL_EVERY, self._collect)
        else:
            self._update_best()
        self._refresh_job = self.after(REFRESH_EVERY, self._auto_refresh)

    def _auto_refresh(self):
        """Keep the figures live while this tab is the one on screen; a load
        average goes stale in seconds. Reschedules itself only while shown."""
        self._refresh_job = None
        if getattr(self.app, "_page", None) is self:
            self.refresh()

    def _collect(self):
        """Poll the probes; fill in each row as its machine answers."""
        # cancel rather than forget: Refresh and the poll job both land here, and
        # a forgotten job would still fire -- against a destroyed widget once the
        # tab has been left
        self._cancel_job("_poll_job")
        now = time.time()
        for host, (proc, started) in list(self._running.items()):
            if proc.poll() is None:
                if now - started > PROBE_TIMEOUT:
                    self._kill(proc)
                    del self._running[host]
                    self._results[host] = None
                    self._show_message(host, "no answer (timed out)", _RED)
                continue
            del self._running[host]
            out, err = self._read(proc)
            data = parse_probe(out)
            self._results[host] = data
            if data is None:
                self._show_message(host, "no answer%s" % _reason(err), _RED)
            else:
                self._show_data(host, *data)

        # recommend from what has answered so far: one machine that hangs must
        # not hold the answer back for the whole timeout
        self._update_best()
        if self._running:
            self._poll_job = self.after(_POLL_EVERY, self._collect)

    @staticmethod
    def _read(proc):
        try:
            return proc.communicate(timeout=1)
        except Exception:
            return "", ""

    @staticmethod
    def _kill(proc):
        try:
            proc.kill()
        except Exception:
            pass

    def _kill_running(self):
        for _host, (proc, _started) in self._running.items():
            self._kill(proc)
        self._running = {}

    def _cancel_jobs(self):
        for name in ("_poll_job", "_refresh_job"):
            self._cancel_job(name)

    def _cancel_job(self, name):
        job = getattr(self, name, None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass
            setattr(self, name, None)

    # ------------------------------------------------------------------
    def _show_message(self, host, message, colour):
        row = self._rows.get(host)
        if row is None:
            return
        row["cpu_bar"].set(None, _GREY)
        row["mem_bar"].set(None, _GREY)
        row["cpu"].configure(text="")
        row["mem"].configure(text="")
        row["verdict"].configure(text=message, fg=colour)

    def _show_data(self, host, cpu, mem_percent, mem_gb):
        row = self._rows.get(host)
        if row is None:
            return
        _cpu_label, cpu_colour = cpu_state(cpu)
        _mem_label, mem_colour = mem_state(mem_percent)
        row["cpu_bar"].set(cpu, cpu_colour)
        row["cpu"].configure(text="%d%%" % round(cpu), fg=cpu_colour)
        # the memory bar fills with what is *used*, so a full bar is bad on both
        row["mem_bar"].set(None if mem_percent is None else 100.0 - mem_percent,
                           mem_colour)
        row["mem"].configure(
            text="? GB free" if mem_gb is None else "%d GB free" % round(mem_gb),
            fg=mem_colour)
        text, colour = verdict(cpu, mem_percent)
        row["verdict"].configure(text=text, fg=colour)

    def _update_best(self):
        """Name the machine to use: the one whose most-contended resource is the
        least contended.

        Ranking on the cpu alone recommends an idle machine with 1 GB left, which
        cannot run a verification at all -- the same reason verdict() reports the
        worse of the two."""
        waiting = len(self._running)
        answered = [(h, d) for h, d in self._results.items() if d]
        if not answered:
            self._best.configure(
                text="Checking %d machines..." % waiting if waiting
                     else "No machine answered.",
                fg=_GREY if waiting else _RED)
            return
        host, (cpu, mem_percent, mem_gb) = min(answered, key=_contention)
        detail = "%d%% CPU" % round(cpu)
        if mem_gb is not None:
            detail += ", %d GB free" % round(mem_gb)
        text = "Best right now: %s  (%s)" % (host, detail)
        if waiting:
            text += "   -- still checking %d" % waiting
        _label, colour = verdict(cpu, mem_percent)
        self._best.configure(text=text, fg=colour)


class _Bar(tk.Frame):
    """A fixed-width bar filled to a percentage.

    Two frames rather than a Canvas: the fill is placed by relative width, so
    there is no geometry to compute and it colours by simply being a coloured
    frame."""

    def __init__(self, master, bg):
        super().__init__(master, width=_BAR_WIDTH, height=_BAR_HEIGHT,
                        bg=_TRACK, bd=1, relief="sunken")
        self.pack_propagate(False)
        self._fill = tk.Frame(self, bg=bg)
        self.set(None, _GREY)

    def set(self, percent, colour):
        if percent is None:
            self._fill.place_forget()
            return
        fraction = max(0.0, min(1.0, percent / 100.0))
        self._fill.configure(bg=colour)
        self._fill.place(x=0, y=0, relheight=1.0, relwidth=fraction)


def _contention(host_and_data):
    """Sort key for 'which machine should I use': how taken its worst resource
    is. Unknown memory does not count against a machine -- there is nothing to
    go on but its cpu."""
    _host, (cpu, mem_percent, _mem_gb) = host_and_data
    mem_used = 0.0 if mem_percent is None else 100.0 - mem_percent
    return max(cpu, mem_used), cpu


def _reason(stderr):
    """The first line of ssh's complaint, so a failure is diagnosable (a host
    key that was never accepted looks exactly like a machine that is down)."""
    for line in (stderr or "").splitlines():
        line = line.strip()
        if line:
            return " (%s)" % line
    return ""
