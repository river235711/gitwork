#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_runs.py: the generator that turns central into runnable folders.

Runs it into a temporary directory and checks the tree it produces, so the tool
people rely on for the real calibre runs is itself covered.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import config
import sandbox
from harness import GuiTestCase

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKE_RUNS = os.path.join(HERE, "make_runs.py")


class MakeRuns(GuiTestCase):
    """The generator runs in its own process -- it drives a pdkgui of its own,
    and must not disturb the window this test already has open."""

    def setUp(self):
        super(MakeRuns, self).setUp()
        self.out = tempfile.mkdtemp(prefix="pdkgui_runs_")
        self.addCleanup(shutil.rmtree, self.out, True)

    def _generate(self, *extra):
        cmd = [sys.executable, MAKE_RUNS, "--out", self.out,
               "--src", os.environ["PDKGUI_SRC"],
               "--central", self.paths["central"],
               "--process", self.design] + list(extra)
        env = dict(os.environ)
        env["PDKGUI_USER_DIR"] = os.path.join(self.out, ".session")
        with self.stubs.paused():          # this one really must start a process
            done = subprocess.run(cmd, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, env=env)
        self.assertEqual(done.returncode, 0,
                         "make_runs failed:\n%s" % done.stdout.decode("utf-8"))
        return done.stdout.decode("utf-8")

    def _cases(self, tab):
        folder = os.path.join(self.out, self.design, tab)
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    # ------------------------------------------------------------------
    def test_every_option_value_gets_a_case(self):
        self._generate("--tabs", "XRC")
        cases = self._cases("XRC")
        page = self.open_tab("XRC")
        for key, widget in page.entries.items():
            if hasattr(widget, "cget") and widget.winfo_class() == "TCombobox":
                for value in widget.cget("values"):
                    if value != widget.get():           # the default is baseline
                        self.assertIn("%s_%s" % (key, value), cases)
        self.assertIn("baseline", cases)
        self.assertNotIn("rve", cases,
                         "Rve opens the interactive viewer; keep it out of a batch")

    def test_rve_can_still_be_asked_for(self):
        self._generate("--tabs", "LVS", "--with-rve")
        self.assertIn("rve", self._cases("LVS"))

    def test_each_case_holds_what_is_needed_to_run(self):
        self._generate("--tabs", "DRC")
        for case in self._cases("DRC"):
            folder = os.path.join(self.out, self.design, "DRC", case)
            run = os.path.join(folder, "run")
            self.assertTrue(os.access(run, os.X_OK), "%s/run is not executable" % case)
            self.assertTrue(os.path.isfile(os.path.join(folder, "case.txt")))
            self.assertTrue(os.path.isfile(
                os.path.join(folder, "calibre_%s_drc.com" % self.design)))

    def test_the_option_really_reaches_the_run_script(self):
        self._generate("--tabs", "XRC")
        base = os.path.join(self.out, self.design, "XRC")
        with open(os.path.join(base, "baseline", "run"), encoding="utf-8") as f:
            self.assertIn("-c ", f.read())
        with open(os.path.join(base, "XrcExtType_rcc", "run"), encoding="utf-8") as f:
            script = f.read()
        self.assertIn("-rcc ", script)
        self.assertIn(".dist*", script)

    def test_the_reduction_case_brings_its_jivaro_xml(self):
        self._generate("--tabs", "XRC")
        folder = os.path.join(self.out, self.design, "XRC", "XrcReduction_on")
        self.assertTrue(os.path.isfile(os.path.join(folder, "jivaro.xml")))
        with open(os.path.join(folder, "run"), encoding="utf-8") as f:
            self.assertIn("jivaro -xml jivaro.xml", f.read())

    def test_jivaro_needs_a_netlist(self):
        self._generate("--tabs", "JIVARO")
        self.assertEqual(self._cases("JIVARO"), [],
                         "JIVARO was generated without a netlist")

        netlist = os.path.join(self.paths["work"], "%s.lump" % self.design)
        self._generate("--tabs", "JIVARO", "--netlist", netlist)
        cases = self._cases("JIVARO")
        self.assertEqual(cases, ["baseline"])
        with open(os.path.join(self.out, self.design, "JIVARO", "baseline",
                               "jivaro.xml"), encoding="utf-8") as f:
            self.assertIn(netlist, f.read())

    def test_given_fields_are_used_in_every_case(self):
        layout = os.path.join(self.paths["work"], "top.gds")
        self._generate("--tabs", "LVS", "--layout", layout, "--primary", "given_top")
        com = os.path.join(self.out, self.design, "LVS", "baseline",
                           "calibre_%s_lvs.com" % self.design)
        with open(com, encoding="utf-8") as f:
            text = f.read()
        self.assertIn('LAYOUT PRIMARY "given_top"', text)
        self.assertIn(layout, text)

    def test_run_all_lists_every_case(self):
        self._generate("--tabs", "LVS")
        run_all = os.path.join(self.out, "run_all")
        self.assertTrue(os.access(run_all, os.X_OK))

        with self.stubs.paused():
            listed = subprocess.run([run_all, "-n"], stdout=subprocess.PIPE,
                                    cwd=self.out).stdout.decode("utf-8")
        for case in self._cases("LVS"):
            self.assertIn(case, listed)
        self.assertIn("run without -n", listed)

    def test_run_all_reports_a_failing_case(self):
        self._generate("--tabs", "LVS")
        base = os.path.join(self.out, self.design, "LVS")
        broken = "LvsHier_off"
        for case in os.listdir(base):
            self._fake_run(os.path.join(base, case, "run"), ok=(case != broken))

        with self.stubs.paused():
            done = subprocess.run([os.path.join(self.out, "run_all")],
                                  stdout=subprocess.PIPE, cwd=self.out)
        output = done.stdout.decode("utf-8")
        self.assertEqual(done.returncode, 1, "a failing case did not fail the run")
        self.assertIn("1 failed", output)
        self.assertIn("LVS/" + broken, output)
        self.assertTrue(os.path.isfile(os.path.join(base, broken, "run.log")))

    def test_a_second_run_repeats_only_what_failed(self):
        """Cases are real calibre runs, so a rerun must not redo hours of work."""
        self._generate("--tabs", "LVS")
        base = os.path.join(self.out, self.design, "LVS")
        broken = "LvsHier_off"
        for case in os.listdir(base):
            self._fake_run(os.path.join(base, case, "run"), ok=(case != broken))
        self._run_all()                                   # first pass

        listed = self._run_all("-n")
        self.assertIn(broken, listed, "the failed case was not queued again")
        self.assertIn("1 case(s) to run", listed,
                      "cases that already passed were queued again")

        self._fake_run(os.path.join(base, broken, "run"), ok=True)
        self.assertIn("1 ok", self._run_all())
        self.assertIn("nothing to run", self._run_all(),
                      "everything passed, yet it wanted to run more")
        self.assertIn("ok", self._run_all("-s"))

    def _run_all(self, *args):
        with self.stubs.paused():
            done = subprocess.run([os.path.join(self.out, "run_all")] + list(args),
                                  stdout=subprocess.PIPE, cwd=self.out)
        return done.stdout.decode("utf-8")

    def test_it_writes_nothing_outside_the_output_directory(self):
        before = _snapshot(self.paths["user"])
        self._generate("--tabs", "DRC")
        self.assertEqual(_snapshot(self.paths["user"]), before,
                         "the generator wrote into the user's session dir")
        self.assertTrue(os.path.isdir(os.path.join(self.out, ".session")),
                        "its own session should live under --out")

    def test_the_index_names_every_case(self):
        self._generate("--tabs", "XRC")
        with open(os.path.join(self.out, "cases.txt"), encoding="utf-8") as f:
            index = f.read()
        for case in self._cases("XRC"):
            self.assertIn(case, index)

    @staticmethod
    def _fake_run(path, ok):
        with open(path, "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n" if ok else "#!/bin/bash\nexit 3\n")
        os.chmod(path, 0o755)


def _snapshot(folder):
    out = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            out.append(os.path.join(root, name))
    return sorted(out)


if __name__ == "__main__":
    unittest.main()
