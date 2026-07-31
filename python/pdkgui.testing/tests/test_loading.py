#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The LOADING tab: reading each machine's figures and saying which to use.

The probe output is parsed and judged by three module-level functions, tested
here on their own; the page itself is checked for what it launches, what it
shows while waiting, and what happens when a machine never answers.
"""

import os
import unittest

import config
from harness import GuiTestCase
from pages import loading

# what the probe prints: loadavg, core count, memory (kB)
PROBE_OUT = ("0.52 0.61 0.70 2/812 31337\n"
             "32\n"
             "MemTotal: 263901184\n"
             "MemAvailable: 198234112\n")


def probe(load, ncpu, total_kb=None, avail_kb=None):
    out = "%s 0.00 0.00 1/100 1\n%d\n" % (load, ncpu)
    if total_kb is not None:
        out += "MemTotal: %d\nMemAvailable: %d\n" % (total_kb, avail_kb)
    return out


GB = 1024 * 1024        # kB in a GB


class ParseProbe(unittest.TestCase):
    def test_a_normal_answer(self):
        cpu, mem_pct, mem_gb = loading.parse_probe(PROBE_OUT)
        self.assertAlmostEqual(cpu, 0.52 / 32 * 100, places=6)
        self.assertAlmostEqual(mem_pct, 198234112 * 100.0 / 263901184, places=6)
        self.assertAlmostEqual(mem_gb, 198234112 / GB, places=6)

    def test_cpu_is_the_load_over_the_core_count(self):
        """A load of 8 is idle on 32 cores and hopeless on 4."""
        self.assertAlmostEqual(loading.parse_probe(probe("8.0", 32))[0], 25.0)
        self.assertAlmostEqual(loading.parse_probe(probe("8.0", 8))[0], 100.0)

    def test_an_overloaded_machine_caps_at_100(self):
        cpu, _pct, _gb = loading.parse_probe(probe("120.0", 8))
        self.assertEqual(cpu, 100.0, "the bar would run off the row")

    def test_memory_is_read_by_name_not_by_position(self):
        """A kernel that reports them the other way round must not swap them."""
        out = ("0.50 0 0 1/1 1\n2\n"
               "MemAvailable: 1048576\nMemTotal: 4194304\n")
        _cpu, mem_pct, mem_gb = loading.parse_probe(out)
        self.assertAlmostEqual(mem_pct, 25.0)
        self.assertAlmostEqual(mem_gb, 1.0)

    def test_a_kernel_without_memavailable_leaves_the_memory_unknown(self):
        """Rather than shifting the numbers along, as reading by position would."""
        cpu, mem_pct, mem_gb = loading.parse_probe(probe("1.0", 4))
        self.assertAlmostEqual(cpu, 25.0, "the cpu figure is still good")
        self.assertIsNone(mem_pct)
        self.assertIsNone(mem_gb)

    def test_what_cannot_be_read_is_none(self):
        for bad in ("", None, "\n\n", "ssh: connect to host sirius07: no route",
                    "0.52 0.61 0.70\n", "0.52 0.61 0.70\nnot-a-number\n",
                    probe("1.0", 0)):
            self.assertIsNone(loading.parse_probe(bad), repr(bad))


class Verdict(unittest.TestCase):
    def test_the_cpu_bands(self):
        self.assertEqual(loading.cpu_state(0)[0], "idle")
        self.assertEqual(loading.cpu_state(39.9)[0], "idle")
        self.assertEqual(loading.cpu_state(40)[0], "busy")
        self.assertEqual(loading.cpu_state(74.9)[0], "busy")
        self.assertEqual(loading.cpu_state(75)[0], "loaded")
        self.assertEqual(loading.cpu_state(100)[0], "loaded")

    def test_the_memory_bands(self):
        self.assertEqual(loading.mem_state(80)[0], "ok")
        self.assertEqual(loading.mem_state(20)[0], "tight")
        self.assertEqual(loading.mem_state(5)[0], "low")
        self.assertEqual(loading.mem_state(None)[0], "")

    def test_an_idle_machine_with_no_memory_is_not_reported_as_idle(self):
        """It cannot run a verification, whatever its cores are doing."""
        self.assertEqual(loading.verdict(5, 2)[0], "no memory")
        self.assertEqual(loading.verdict(5, 20)[0], "low memory")
        self.assertEqual(loading.verdict(5, 80)[0], "idle")

    def test_a_loaded_machine_stays_loaded(self):
        self.assertEqual(loading.verdict(90, 80)[0], "loaded")
        self.assertEqual(loading.verdict(90, 2)[0], "loaded")

    def test_unknown_memory_is_judged_on_the_cpu_alone(self):
        self.assertEqual(loading.verdict(5, None)[0], "idle")
        self.assertEqual(loading.verdict(90, None)[0], "loaded")


class HostList(unittest.TestCase):
    """hosts.txt: a name per line, plus a route for a machine behind another."""

    def test_a_plain_name(self):
        m = loading.parse_host_line("sirius02")
        self.assertEqual((m.name, m.target, m.jump), ("sirius02", "sirius02", None))

    def test_a_machine_reached_through_a_jump_host(self):
        m = loading.parse_host_line("sirius03 via will.huang@wswillhuang")
        self.assertEqual((m.name, m.target, m.jump),
                         ("sirius03", "sirius03", "will.huang@wswillhuang"))

    def test_a_login_that_differs_is_not_shown_as_the_machine_name(self):
        m = loading.parse_host_line("will.huang@sirius03 via will.huang@wswillhuang")
        self.assertEqual(m.name, "sirius03", "the row is labelled with the machine")
        self.assertEqual(m.target, "will.huang@sirius03")

    def test_blank_and_junk_lines(self):
        self.assertIsNone(loading.parse_host_line("   "))
        # 'via' with nothing after it is not a route; the machine still works
        self.assertEqual(loading.parse_host_line("sirius03 via").jump, None)


class ProbeCommand(unittest.TestCase):
    def test_the_local_machine_is_not_reached_over_ssh(self):
        """It always works, keys or no keys."""
        argv = loading.probe_command(config.hostname())
        self.assertNotIn("ssh", argv)
        self.assertEqual(argv[:2], ["bash", "-c"])

    def test_a_remote_machine_cannot_stop_to_ask_for_a_password(self):
        argv = loading.probe_command("sirius05")
        self.assertEqual(argv[0], "ssh")
        self.assertIn("BatchMode=yes", argv)
        self.assertIn("ConnectTimeout=3", argv)
        self.assertIn("sirius05", argv)

    def test_a_machine_behind_a_jump_host_is_probed_through_it(self):
        machine = loading.parse_host_line("sirius03 via will.huang@wswillhuang")
        argv = loading.probe_command(machine)
        self.assertEqual(argv[:4], ["ssh", "-J", "will.huang@wswillhuang", "-o"])
        self.assertIn("BatchMode=yes", argv, "the hop must not stop for a password")
        self.assertIn("sirius03", argv)

    def test_it_reads_proc_and_nothing_else(self):
        """No tool that may not be installed, no scheduler."""
        command = loading.probe_command("sirius05")[-1]
        self.assertIn("/proc/loadavg", command)
        self.assertIn("/proc/meminfo", command)


class ShellCommand(unittest.TestCase):
    """What the Terminal / pdkgui buttons on each row launch."""

    def test_a_remote_terminal_forwards_the_display_and_takes_a_pty(self):
        argv = loading.shell_command("sirius05")
        self.assertEqual(argv[:4], ["ssh", "-X", "-t", "sirius05"])

    def test_the_shell_is_left_interactive(self):
        """The window is somewhere to work, not a command that exits."""
        self.assertIn("exec $SHELL -l", loading.shell_command("sirius05")[-1])

    @staticmethod
    def _inner(argv):
        """What the far machine is asked to run, unwrapped from its bash -lc."""
        import shlex
        command = argv[-1]
        return shlex.split(command)[-1] if command.startswith("bash -lc ") else command

    def test_a_terminal_on_this_machine_does_not_go_through_ssh(self):
        argv = loading.shell_command(config.hostname())
        self.assertEqual(argv[:2], ["bash", "-lc"])
        self.assertNotIn("ssh", argv)

    def test_a_terminal_on_a_machine_behind_a_jump_host_hops_through_it(self):
        machine = loading.parse_host_line("sirius03 via will.huang@wswillhuang")
        argv = loading.shell_command(machine, launcher="/tools/pdkgui")
        self.assertEqual(argv[:6], ["ssh", "-J", "will.huang@wswillhuang",
                                    "-X", "-t", "sirius03"])
        self.assertIn("/tools/pdkgui", argv[-1])

    def test_a_jump_host_route_is_used_even_for_this_machine_s_own_name(self):
        """The row is only there because the direct path does not work."""
        machine = loading._machine(config.hostname())._replace(
            jump="will.huang@wswillhuang")
        self.assertEqual(loading.shell_command(machine)[0], "ssh")
        self.assertEqual(loading.probe_command(machine)[0], "ssh")

    def test_without_a_launcher_nothing_is_started(self):
        self.assertNotIn("&", self._inner(loading.shell_command("sirius05")))

    def test_with_a_launcher_pdkgui_starts_in_the_background(self):
        command = self._inner(
            loading.shell_command("sirius05", launcher="/tools/pdkgui"))
        self.assertIn("/tools/pdkgui >/dev/null 2>&1 &", command)
        self.assertTrue(command.endswith("exec $SHELL -l"),
                        "the shell must outlive the launcher")

    def test_it_opens_in_the_directory_this_window_was_started_from(self):
        command = self._inner(
            loading.shell_command("sirius05", workdir="/p/my project"))
        self.assertIn("cd '/p/my project' 2>/dev/null", command)
        self.assertTrue(command.startswith("cd "), "cd has to come first")

    def test_it_does_not_assume_the_login_shell_is_bash(self):
        """`ssh host '<cmd>'` hands the command to the login shell, and on these
        machines that is tcsh, which has no `2>` redirect: it read
        `cd <dir> 2>/dev/null` as `cd <dir> 2` and answered "cd: Too many
        arguments", then never started pdkgui."""
        argv = loading.shell_command("sirius05", launcher="/tools/pdkgui",
                                     workdir="/p/work")
        self.assertTrue(argv[-1].startswith("bash -lc "), argv[-1])
        # the interactive shell at the end is still the user's own
        self.assertIn("exec $SHELL -l", argv[-1])

    def test_the_remote_command_runs_under_tcsh_as_well_as_bash(self):
        """Not a syntax check -- the launcher has to actually start."""
        import shutil
        import subprocess
        import tempfile
        import time
        for shell in ("tcsh", "bash"):
            if not shutil.which(shell):
                self.skipTest("%s is not installed here" % shell)

        work = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(work, ignore_errors=True))
        launcher = os.path.join(work, "launcher")
        with open(launcher, "w") as f:
            f.write("#!/bin/bash\ntouch started\n")
        os.chmod(launcher, 0o755)

        # the string the far machine's login shell is handed
        command = loading.shell_command("somewhere", launcher=launcher,
                                        workdir=work)[-1]
        for shell in ("tcsh", "bash"):
            started = os.path.join(work, "started")
            if os.path.exists(started):
                os.remove(started)
            run = subprocess.run([shell, "-c", command], stdin=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, universal_newlines=True,
                                 timeout=30)
            self.assertEqual(run.returncode, 0, "%s: %s" % (shell, run.stderr))
            self.assertEqual(run.stderr, "", "%s complained" % shell)
            # it was started in the background, so the shell can exit first
            for _ in range(50):
                if os.path.exists(started):
                    break
                time.sleep(0.1)
            self.assertTrue(os.path.exists(started),
                            "%s did not start the launcher" % shell)

    def test_what_it_builds_is_valid_shell(self):
        """'cmd &' followed by ';' is a syntax error, and every combination of
        workdir and launcher is assembled from the same pieces."""
        import subprocess
        for workdir in (None, "/p/my project"):
            for launcher in (None, "/tools/pdkgui"):
                command = loading.shell_command(
                    "sirius05", launcher=launcher, workdir=workdir)[-1]
                check = subprocess.run(["bash", "-n", "-c", command],
                                       stderr=subprocess.PIPE,
                                       universal_newlines=True)
                self.assertEqual(check.returncode, 0,
                                 "%s\n%s" % (command, check.stderr))


class LoadingTab(GuiTestCase):
    HOSTS = ("hostA", "hostB", "hostC")

    def setUp(self):
        super(LoadingTab, self).setUp()
        listing = os.path.join(self.paths["work"], "hosts.txt")
        with open(listing, "w", encoding="utf-8") as f:
            f.write("# machines\n" + "\n".join(self.HOSTS) + "\n")
        os.environ["PDKGUI_LOADING_FILE"] = listing
        self.addCleanup(os.environ.pop, "PDKGUI_LOADING_FILE", None)
        config.clear_cache()

    def test_the_tab_is_in_the_menu_before_system(self):
        items = config.MENU_ITEMS
        self.assertIn("LOADING", items)
        self.assertEqual(items.index("LOADING") + 1, items.index("SYSTEM"))

    def test_the_heading_says_how_to_open_this_page_on_its_own(self):
        page = self.open_tab("LOADING")
        self.assertIn("(command: pdkgui -l)", self.labels(page))

    def test_every_listed_machine_is_probed_at_once(self):
        """All together, so the slowest one sets the wait, not their sum."""
        self.outputs = {}
        page = self.open_tab("LOADING")
        probed = [argv[-2] for argv in self.spawned if argv[0] == "ssh"]
        self.assertEqual(sorted(probed), sorted(self.HOSTS))
        self.assertEqual(len(page.hosts), len(self.HOSTS))

    def test_the_figures_land_in_the_row_of_the_machine_they_came_from(self):
        self.outputs = {
            "hostA": (probe("0.4", 8, 100 * GB, 80 * GB), ""),    # 5%, 80 GB
            "hostB": (probe("7.6", 8, 100 * GB, 50 * GB), ""),    # 95%, 50 GB
            "hostC": (probe("4.0", 8, 100 * GB, 5 * GB), ""),     # 50%, 5 GB
        }
        page = self.open_tab("LOADING")
        page._collect()
        self.app.update()

        self.assertEqual(self._cell(page, "hostA", "cpu"), "5%")
        self.assertEqual(self._cell(page, "hostA", "mem"), "80 GB free")
        self.assertEqual(self._cell(page, "hostA", "verdict"), "idle")
        self.assertEqual(self._cell(page, "hostB", "cpu"), "95%")
        self.assertEqual(self._cell(page, "hostB", "verdict"), "loaded")
        self.assertEqual(self._cell(page, "hostC", "verdict"), "no memory")

    def test_it_names_the_machine_to_use(self):
        self.outputs = {
            "hostA": (probe("4.0", 8, 100 * GB, 80 * GB), ""),
            "hostB": (probe("0.8", 8, 100 * GB, 80 * GB), ""),   # the emptiest
            "hostC": (probe("6.0", 8, 100 * GB, 80 * GB), ""),
        }
        page = self.open_tab("LOADING")
        page._collect()
        self.app.update()
        self.assertIn("hostB", page._best.cget("text"))
        self.assertIn("80 GB free", page._best.cget("text"))

    def test_a_machine_with_no_memory_left_is_not_the_best_pick(self):
        self.outputs = {
            "hostA": (probe("0.1", 8, 100 * GB, 1 * GB), ""),    # idle, no memory
            "hostB": (probe("0.8", 8, 100 * GB, 80 * GB), ""),
            "hostC": (probe("6.0", 8, 100 * GB, 80 * GB), ""),
        }
        page = self.open_tab("LOADING")
        page._collect()
        self.app.update()
        self.assertNotIn("hostA", page._best.cget("text"))

    def test_a_machine_that_says_nothing_useful_reports_the_reason(self):
        self.outputs = {
            "hostA": (probe("0.4", 8, 100 * GB, 80 * GB), ""),
            "hostB": ("", "ssh: connect to host hostB port 22: No route to host\n"),
            "hostC": ("", ""),
        }
        page = self.open_tab("LOADING")
        page._collect()
        self.app.update()

        self.assertIn("No route to host", self._cell(page, "hostB", "verdict"))
        self.assertIn("no answer", self._cell(page, "hostC", "verdict"))
        self.assertEqual(self._cell(page, "hostA", "verdict"), "idle",
                         "one dead machine spoiled the others")

    def test_a_machine_that_never_answers_is_given_up_on(self):
        self.outputs = {"hostA": None, "hostB": None, "hostC": None}
        page = self.open_tab("LOADING")
        for host in self.HOSTS:
            self.assertIn("checking", self._cell(page, host, "verdict"))

        original = loading.PROBE_TIMEOUT
        loading.PROBE_TIMEOUT = -1                      # everything is overdue
        self.addCleanup(setattr, loading, "PROBE_TIMEOUT", original)
        page._collect()
        self.app.update()

        for host in self.HOSTS:
            self.assertIn("no answer", self._cell(page, host, "verdict"))
        self.assertIn("No machine answered", page._best.cget("text"))
        self.assertFalse(page._running, "a given-up probe is still on the list")

    def test_one_hanging_machine_does_not_hold_back_the_recommendation(self):
        self.outputs = {
            "hostA": (probe("0.8", 8, 100 * GB, 80 * GB), ""),
            "hostB": None,                                 # never answers
            "hostC": None,
        }
        page = self.open_tab("LOADING")
        page._collect()
        self.app.update()
        self.assertIn("hostA", page._best.cget("text"))
        self.assertIn("still checking 2", page._best.cget("text"))

    def test_refresh_asks_again(self):
        self.outputs = {}
        page = self.open_tab("LOADING")
        page._collect()
        self.spawned = []
        self.click(page, "Refresh")
        self.assertEqual(len(self.spawned), len(self.HOSTS))

    def test_leaving_the_tab_stops_the_polling(self):
        """An after() job outliving the window fires against a dead widget."""
        self.outputs = {"host": None}          # nothing ever finishes
        page = self.open_tab("LOADING")
        self.assertIsNotNone(page._poll_job)

        self.open_tab("SYSTEM")                # show_module flushes on the way out
        self.assertIsNone(page._poll_job)
        self.assertIsNone(page._refresh_job)
        self.assertFalse(page._running, "an ssh was left running")

    # --- the per-machine buttons --------------------------------------
    def test_every_machine_has_its_own_two_buttons(self):
        page = self.open_tab("LOADING")
        for label, expected in (("Terminal", len(self.HOSTS)),
                                ("pdkgui", len(self.HOSTS))):
            found = [b for b in self.widgets(page, "Button")
                     if b.cget("text") == label]
            self.assertEqual(len(found), expected,
                             "expected one %s button per machine" % label)

    def test_the_terminal_button_opens_a_shell_on_that_machine(self):
        page = self.open_tab("LOADING")
        self.spawned = []
        self._press(page, "hostB", "Terminal")

        argv = self.spawned[-1]
        self.assertIn("ssh", argv)
        self.assertIn("hostB", argv)
        self.assertNotIn("&", argv[-1], "nothing should be started in it")
        self.assertFalse(self.dialogs, "the button complained: %s" % self.dialogs)

    def test_the_pdkgui_button_starts_it_on_that_machine(self):
        page = self.open_tab("LOADING")
        self.spawned = []
        self._press(page, "hostC", "pdkgui")

        command = self.spawned[-1][-1]
        self.assertIn("hostC", self.spawned[-1])
        self.assertIn("pdkgui >/dev/null 2>&1 &", command)
        self.assertIn("exec $SHELL -l", command)

    def test_the_pdkgui_it_starts_is_a_launcher_that_exists(self):
        """An absolute path on the shared filesystem, so it means the same thing
        on the other machine."""
        launcher = loading.LoadingPage._launcher()
        self.assertTrue(os.path.isabs(launcher), launcher)
        self.assertTrue(os.path.isfile(launcher), launcher)

    def test_the_terminal_emulator_comes_from_the_shared_list(self):
        page = self.open_tab("LOADING")
        self.spawned = []
        self._press(page, "hostA", "Terminal")
        self.assertEqual(self.spawned[-1][:len(config.TERMINALS[0])],
                         list(config.TERMINALS[0]))

    def test_a_chosen_terminal_is_used(self):
        os.environ["PDKGUI_TERMINAL"] = "mate-terminal"
        self.addCleanup(os.environ.pop, "PDKGUI_TERMINAL", None)
        self.assertEqual(config.terminals(), (["mate-terminal", "-e"],))

    def test_an_empty_list_says_so_instead_of_looking_broken(self):
        listing = os.path.join(self.paths["work"], "none.txt")
        with open(listing, "w", encoding="utf-8") as f:
            f.write("# nothing here\n")
        os.environ["PDKGUI_LOADING_FILE"] = listing
        config.clear_cache()

        page = self.open_tab("LOADING")
        self.assertEqual(page.hosts, [])
        self.assertTrue(any("No machines listed" in text
                            for text in self.labels(page)))

    def test_the_shipped_list_is_the_sirius_machines(self):
        os.environ.pop("PDKGUI_LOADING_FILE")
        config.clear_cache()
        machines = [loading.parse_host_line(ln) for ln in
                    config.read_lines(config.page_file("LOADING"))]
        self.assertEqual([m.name for m in machines],
                         ["sirius01", "sirius02", "sirius03", "sirius05",
                          "sirius06", "sirius07"])
        # sirius03 is only reachable through the workstation
        routed = {m.name: m.jump for m in machines if m.jump}
        self.assertEqual(routed, {"sirius03": "will.huang@wswillhuang"})

    # ------------------------------------------------------------------
    def _cell(self, page, host, key):
        return page._rows[host][key].cget("text")

    def _press(self, page, host, label):
        """The button with this label on that machine's row."""
        row = str(page._rows[host]["verdict"].grid_info().get("row"))
        for b in self.widgets(page, "Button"):
            info = b.grid_info()
            if (b.cget("text") == label and info
                    and str(info.get("row")) == row):
                b.invoke()
                self.app.update()
                return
        self.fail("no %s button on the %s row" % (label, host))


class CommandLine(unittest.TestCase):
    """`pdkgui -l` -- the machine chooser on its own."""

    def test_no_arguments_opens_the_full_window(self):
        import pdkgui_app
        self.assertEqual(pdkgui_app.parse_argv([]), (None, None, 0))

    def test_both_spellings_ask_for_the_chooser(self):
        import pdkgui_app
        for flag in ("-l", "--loading"):
            self.assertEqual(pdkgui_app.parse_argv([flag]), ("LOADING", None, 0))

    def test_help_prints_and_stops(self):
        import pdkgui_app
        only, message, status = pdkgui_app.parse_argv(["--help"])
        self.assertIsNone(only, "--help must not open a window")
        self.assertIn("-l, --loading", message)
        self.assertEqual(status, 0)

    def test_an_unknown_option_is_refused_rather_than_ignored(self):
        import pdkgui_app
        for argv in (["-x"], ["-l", "extra"], ["--loading", "-x"]):
            only, message, status = pdkgui_app.parse_argv(argv)
            self.assertIsNone(only, argv)
            self.assertEqual(status, 2, argv)
            self.assertIn("unknown option", message)


class ChooserWindow(GuiTestCase):
    """The window `pdkgui -l` opens: one page, and none of a session's state."""

    def setUp(self):
        super(ChooserWindow, self).setUp()
        listing = os.path.join(self.paths["work"], "hosts.txt")
        with open(listing, "w", encoding="utf-8") as f:
            f.write("hostA\nhostB\n")
        os.environ["PDKGUI_LOADING_FILE"] = listing
        self.addCleanup(os.environ.pop, "PDKGUI_LOADING_FILE", None)
        config.clear_cache()

    def _chooser(self):
        """Replace the harness window with a chooser one, so tearDown closes it
        (two live Tk interpreters in one process interfere with each other)."""
        self.app.destroy()
        self.app = self.pdkgui_app.PdkGui(only="LOADING")
        self.app.withdraw()
        self.app.update()
        return self.app._page

    def test_it_shows_the_loading_page_and_nothing_else(self):
        page = self._chooser()
        self.assertEqual(page.module, "LOADING")
        self.assertEqual(self.app._menu_buttons, {},
                         "the chooser should have no menu")
        labels = [b.cget("text") for b in self.widgets(self.app, "Button")]
        for tab in ("DRC", "LVS", "XRC", "SYSTEM", "PROCESS"):
            self.assertNotIn(tab, labels, "a tab button leaked into the chooser")
        self.assertIn("Refresh", labels, "this is not the loading page")

    def test_it_does_not_tell_you_the_command_you_just_typed(self):
        page = self._chooser()
        self.assertNotIn("(command: pdkgui -l)", self.labels(page))

    def test_the_title_says_what_the_window_is_for(self):
        self._chooser()
        title = self.app.title()
        self.assertIn("loading", title)
        self.assertNotIn(config.DESIGN_NAME, title,
                         "choosing a machine has nothing to do with a process")

    def test_the_page_knows_it_is_on_screen(self):
        """_auto_refresh stops rescheduling unless app._page is the page, so
        without this the chooser would never update itself again."""
        page = self._chooser()
        self.assertIs(self.app._page, page)
        self.assertIsNotNone(page._refresh_job)

    def test_closing_it_does_not_move_the_full_window_to_this_page(self):
        ui = config.user_global_file("UI")
        config.save_json(ui, {"module": "XRC"})

        self._chooser()
        self.app._on_close()
        self.app = self.pdkgui_app.PdkGui()      # for tearDown
        self.app.withdraw()

        self.assertEqual(config.load_json(ui).get("module"), "XRC",
                         "the chooser overwrote the remembered tab")

    def test_the_machine_buttons_open_the_full_pdkgui_not_another_chooser(self):
        page = self._chooser()
        self.spawned = []
        row = str(page._rows["hostB"]["verdict"].grid_info().get("row"))
        for b in self.widgets(page, "Button"):
            info = b.grid_info()
            if (b.cget("text") == "pdkgui" and info
                    and str(info.get("row")) == row):
                b.invoke()
                break
        else:
            self.fail("no pdkgui button on the hostB row")

        # the launcher is invoked with no arguments at all, so what opens on the
        # other machine is the full window and not a second chooser
        # (the trailing "exec $SHELL -l" is the login shell, not a pdkgui flag)
        command = self.spawned[-1][-1]
        self.assertIn("pdkgui >/dev/null 2>&1 &", command)
        self.assertNotIn("--loading", command)


if __name__ == "__main__":
    unittest.main()
