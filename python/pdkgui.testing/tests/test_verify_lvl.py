#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The LVL tab: one layout against another.

Built from the LVS page but with two layouts and no command file -- dbdiff
writes the comparison rules itself, so there is nothing to edit, load or save.
"""

import os
import unittest

import config
from harness import GuiTestCase

GDS1 = "/datacenter/users/will.huang/work/t22n/lvl/20250207/test1.gds"
GDS2 = "/datacenter/users/will.huang/work/t22n/lvl/20250207/test2.gds"


class LvlTab(GuiTestCase):
    def setUp(self):
        super(LvlTab, self).setUp()
        self.page = self.open_tab("LVL")
        self.set_entry(self.page, "RunFolder", self.run_folder())

    def test_it_sits_under_lvs_in_the_menu(self):
        items = config.MENU_ITEMS
        self.assertEqual(items[items.index("LVS") + 1], "LVL")

    def test_two_layouts_a_run_folder_and_nothing_else(self):
        self.assertEqual(list(self.page.entries),
                         ["LayoutPath1", "LayoutPrimary1",
                          "LayoutPath2", "LayoutPrimary2", "RunFolder"])
        self.assertIsNone(self.page.cmd_text, "LVL has no command file")

    def test_the_buttons_are_the_lvs_ones_without_the_file_dialogs(self):
        labels = [b.cget("text") for b in self.widgets(self.page, "Button")]
        self.assertEqual(labels, ["Open", "View", "Open", "View",
                                  "Open", "FileManager", "Run", "Rve"])
        for gone in ("LoadDefault", "Load", "Save"):
            self.assertNotIn(gone, labels, "%s has no meaning without a command file"
                             % gone)

    # --- the cell names ------------------------------------------------
    def test_choosing_a_layout_names_its_cell(self):
        self.browse(self.page, "LayoutPath1", GDS1)
        self.browse(self.page, "LayoutPath2", GDS2)
        self.assertEqual(self.page.entries["LayoutPrimary1"].get(), "test1")
        self.assertEqual(self.page.entries["LayoutPrimary2"].get(), "test2")

    def test_the_two_layouts_are_named_independently(self):
        self.browse(self.page, "LayoutPath1", "/p/a/first_block.gds.gz")
        self.set_entry(self.page, "LayoutPrimary2", "CHOSEN_BY_HAND")
        self.assertEqual(self.page.entries["LayoutPrimary1"].get(), "first_block")
        self.assertEqual(self.page.entries["LayoutPrimary2"].get(), "CHOSEN_BY_HAND")

    # --- the run script ------------------------------------------------
    def test_run_compares_the_two_layouts(self):
        self.browse(self.page, "LayoutPath1", GDS1)
        self.browse(self.page, "LayoutPath2", GDS2)
        self.click(self.page, "Run")

        script = self.run_script().splitlines()
        self.assertEqual(script[0], "#!/bin/bash -l")
        self.assertEqual(script[1], "module load %s" % self.app.env["calibre"])
        self.assertEqual(script[2], "rm -rf lvl.log xor.rules*")
        self.assertEqual(
            script[3],
            "dbdiff -system GDS -design %s test1 -refdesign %s test2"
            " -write_xor_rules xor.rules -turbo" % (GDS1, GDS2))
        self.assertEqual(
            script[4],
            "calibre -drc -hier -turbo -hyper -fx xor.rules | tee lvl.log")

    def test_run_writes_no_command_file(self):
        """dbdiff writes the only rules there are."""
        self.click(self.page, "Run")
        self.assertTrue(os.path.isfile(os.path.join(self.run_folder(), "run")))
        stray = [n for n in os.listdir(self.run_folder()) if n.endswith(".com")]
        self.assertEqual(stray, [], "LVL wrote a command file")
        self.assertTrue(self.spawned, "Run opened no terminal")

    def test_the_design_and_the_refdesign_do_not_get_swapped(self):
        self.browse(self.page, "LayoutPath1", "/p/one.gds")
        self.browse(self.page, "LayoutPath2", "/p/two.gds")
        self.click(self.page, "Run")
        line = [l for l in self.run_script().splitlines() if l.startswith("dbdiff")][0]
        self.assertLess(line.index("-design /p/one.gds one"),
                        line.index("-refdesign /p/two.gds two"))

    def test_run_reports_a_missing_run_folder(self):
        self.set_entry(self.page, "RunFolder", "")
        self.click(self.page, "Run")
        self.assertTrue(any(kind == "showerror" for kind, _ in self.dialogs))

    # --- rve -----------------------------------------------------------
    def test_rve_opens_what_the_comparison_produced(self):
        self.click(self.page, "Rve")
        self.assertEqual(self.run_script(),
                         "#!/bin/bash -l\n"
                         "module load %s\n"
                         "calibre -rve xor.rules.asc\n" % self.app.env["calibre"])

    def test_both_scripts_use_the_calibre_picked_on_env(self):
        env = self.open_tab("ENV")
        pick = list(env.combos["calibre"].cget("values"))[-1]
        env.combos["calibre"].set(pick)
        env.combos["calibre"].event_generate("<<ComboboxSelected>>")
        self.app.update()

        page = self.open_tab("LVL")
        self.set_entry(page, "RunFolder", self.run_folder())
        for button in ("Run", "Rve"):
            self.click(page, button)
            self.assertIn("module load %s" % pick, self.run_script(), button)

    # --- state ---------------------------------------------------------
    def test_the_two_layouts_are_remembered(self):
        self.browse(self.page, "LayoutPath1", GDS1)
        self.browse(self.page, "LayoutPath2", GDS2)
        self.page.flush()

        again = self.open_tab("LVL")
        self.assertEqual(again.entries["LayoutPath1"].get(), GDS1)
        self.assertEqual(again.entries["LayoutPrimary2"].get(), "test2")

    def test_view_opens_either_layout(self):
        for key in ("LayoutPath1", "LayoutPath2"):
            self.set_entry(self.page, key,
                           os.path.join(self.paths["work"], "top.gds"))
        views = [b for b in self.widgets(self.page, "Button")
                 if b.cget("text") == "View"]
        self.assertEqual(len(views), 2, "each layout needs its own View")
        for view in views:
            self.spawned = []
            view.invoke()
            self.app.update()
            self.assertTrue(self.spawned, "View launched nothing")


if __name__ == "__main__":
    unittest.main()
