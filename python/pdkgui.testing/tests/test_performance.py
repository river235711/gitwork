#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The speed work: file caching and kept pages.

These optimisations are only acceptable if nothing observable changed, so most
of this checks behaviour rather than timing -- above all that editing a central
.inc is still picked up, which the whole central layout depends on.
"""

import os
import time
import unittest

import config
from harness import GuiTestCase


class FileCache(GuiTestCase):
    def setUp(self):
        super(FileCache, self).setUp()
        self.inc = config.central_include_file("DRC", self.design)

    def test_an_edited_inc_is_still_picked_up(self):
        """The contract the central layout is built on."""
        page = self.open_tab("DRC")
        first = self.active_lines(page.cmd_text.get_text(), "include")[0]

        self._rewrite(self.inc, "/new/deck/after_the_edit.encrypt\n")
        self.open_tab("XRC")                    # leave and come back
        page = self.open_tab("DRC")

        line = self.active_lines(page.cmd_text.get_text(), "include")[0]
        self.assertNotEqual(line, first, "the edited .inc was not picked up")
        self.assertIn("after_the_edit.encrypt", line)

    def test_an_edited_inc_reaches_the_next_run(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "RunFolder", self.run_folder())
        self._rewrite(self.inc, "/new/deck/before_run.encrypt\n")
        self.click(page, "Run")
        self.assertIn("before_run.encrypt", self.com_file("DRC"))

    def test_reading_the_same_file_again_does_not_reopen_it(self):
        opened = self._count_opens()
        for _ in range(5):
            config.read_lines(self.inc)
        self.assertEqual(opened["n"], 1,
                         "the file was read %d times, expected once" % opened["n"])

    def test_a_written_session_reads_back_at_once(self):
        path = config.user_session_file("DRC", self.design)
        config.save_json(path, {"marker": "first"})
        self.assertEqual(config.load_json(path)["marker"], "first")
        config.save_json(path, {"marker": "second"})
        self.assertEqual(config.load_json(path)["marker"], "second",
                         "a stale session was served after a write")

    def test_callers_cannot_corrupt_each_other(self):
        """load_json hands out a fresh object, so one caller's edit is private."""
        path = config.user_session_file("DRC", self.design)
        config.save_json(path, {"gds": ["one"]})
        first = config.load_json(path)
        first["gds"].append("added by this caller")
        self.assertEqual(config.load_json(path)["gds"], ["one"])

    def test_a_missing_file_is_not_cached_as_missing(self):
        path = os.path.join(self.paths["central"], "appears_later.txt")
        self.assertEqual(config.read_text(path, default="absent"), "absent")
        with open(path, "w", encoding="utf-8") as f:
            f.write("here now\n")
        self.assertEqual(config.read_text(path, default="absent").strip(), "here now")

    def _rewrite(self, path, text):
        """Rewrite a file so the change is visible to a timestamp check."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        # a file rewritten within the same clock tick must still look changed;
        # push the timestamp so the test does not depend on stat resolution
        stamp = time.time() + 1
        os.utime(path, (stamp, stamp))

    def _count_opens(self):
        counter = {"n": 0}
        real_open = open

        def counting_open(path, *a, **kw):
            if path == self.inc:
                counter["n"] += 1
            return real_open(path, *a, **kw)

        import builtins
        self._patch_builtin(builtins, "open", counting_open)
        config.clear_cache()
        return counter

    def _patch_builtin(self, obj, name, value):
        original = getattr(obj, name)
        self.addCleanup(setattr, obj, name, original)
        setattr(obj, name, value)


class KeptPages(GuiTestCase):
    def test_a_tab_is_built_once_and_reused(self):
        first = self.open_tab("DRC")
        self.open_tab("XRC")
        self.assertIs(self.open_tab("DRC"), first, "the tab was rebuilt")

    def test_going_back_to_a_tab_keeps_what_was_typed(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPrimary", "typed_here")
        self.open_tab("LVS")
        self.assertEqual(self.open_tab("DRC").entries["LayoutPrimary"].get(),
                         "typed_here")

    def test_switching_process_rebuilds_the_other_tabs(self):
        first = self.open_tab("DRC")
        self.set_design("t40lp_1p6m_4x1u")
        self.assertIsNot(self.open_tab("DRC"), first,
                         "a tab from the previous process was reused")

    def test_switching_process_does_not_pull_the_page_out_from_under_itself(self):
        """set_design runs from the PROCESS page's own callback."""
        page = self.open_tab("PROCESS")
        self.set_design("t40lp_1p6m_4x1u")
        self.assertTrue(page.winfo_exists(), "the PROCESS page destroyed itself")
        combo = self.widgets(page, "TCombobox")[0]
        self.assertEqual(combo.get(), "t40lp_1p6m_4x1u")

    def test_the_system_tab_rechecks_the_release_each_time_it_is_opened(self):
        import sandbox
        config.BASE_DIR = sandbox.install_dir(sandbox.OLD_RELEASE)
        sandbox.set_current_release(sandbox.OLD_RELEASE)
        page = self.open_tab("SYSTEM")
        self.assertNotIn(sandbox.NEW_RELEASE, " ".join(self.labels(page)))

        sandbox.set_current_release(sandbox.NEW_RELEASE)   # an admin switches
        self.open_tab("DRC")
        page = self.open_tab("SYSTEM")
        self.assertIn(sandbox.NEW_RELEASE, " ".join(self.labels(page)),
                      "SYSTEM did not re-check which release is current")

    def test_the_open_tab_is_saved_when_leaving(self):
        self.open_tab("XRC")
        self.app._on_close()
        saved = config.load_json(config.user_global_file("UI"))
        self.assertEqual(saved.get("module"), "XRC")


if __name__ == "__main__":
    unittest.main()
