#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The DRC-family tabs (DRC/ANT/WB/BUMP/DMDV/DPDO) and LVS.

Every button on the page, the field<->text syncing, and the effect each option
has on the generated run script.
"""

import os
import unittest

import config
from harness import GuiTestCase

DRC_CLASS = ("DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO")


class DrcFamily(GuiTestCase):
    """Runs the same checks over every tab that shares the DRC flow."""

    def test_each_tab_has_its_fields_and_buttons(self):
        for module in DRC_CLASS:
            page = self.open_tab(module)
            for key in ("LayoutPath", "LayoutPrimary", "RunFolder"):
                self.assertIn(key, page.entries, "%s lacks %s" % (module, key))
            for label in ("Run", "Rve", "LoadDefault", "Load", "Save",
                          "View", "FileManager"):
                self.button(page, label)

    def test_run_writes_the_command_file_and_script(self):
        for module in DRC_CLASS:
            page = self.open_tab(module)
            self.set_entry(page, "RunFolder", self.run_folder())
            self.click(page, "Run")

            script = self.run_script()
            self.assertIn("calibre -64 -drc -hier -turbo -turbo_all", script)
            self.assertIn(page._com_filename(), script)
            self.assertIn("tee %s.log" % module.lower(), script)
            # the command file itself was written next to it
            self.com_file(module)
            # and a terminal was opened on it
            self.assertTrue(self.spawned, "%s Run opened no terminal" % module)

    def test_rve_opens_the_results_database(self):
        for module in DRC_CLASS:
            page = self.open_tab(module)
            self.set_entry(page, "RunFolder", self.run_folder())
            self.click(page, "Rve")
            script = self.run_script()
            self.assertIn("calibre -rve %s_RES.db" % module, script)
            self.assertIn("module load %s" % self.app.env["calibre"], script)

    def test_the_database_name_follows_the_command_file(self):
        """Unlike LVS/XRC's svdb, the DRC family's database is named by the
        command file, so Rve has to read it back out."""
        page = self.open_tab("DRC")
        self.set_entry(page, "RunFolder", self.run_folder())
        self.set_text(page, page.cmd_text.get_text().replace(
            'DRC RESULTS DATABASE "DRC_RES.db"',
            'DRC RESULTS DATABASE "renamed.db"'))
        self.click(page, "Rve")
        self.assertIn("calibre -rve renamed.db", self.run_script())

    def test_run_reports_a_missing_run_folder_instead_of_writing(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "RunFolder", "")
        self.click(page, "Run")
        self.assertTrue(any(kind == "showerror" for kind, _ in self.dialogs),
                        "empty RunFolder was accepted silently")

    # --- field <-> command text ---------------------------------------
    def test_editing_the_text_updates_the_fields(self):
        page = self.open_tab("DRC")
        gds = os.path.join(self.paths["work"], "top.gds")
        self.set_text(page,
                      'LAYOUT PRIMARY "block_a"\n'
                      'LAYOUT PATH "%s"\n' % gds)
        self.assertEqual(page.entries["LayoutPrimary"].get(), "block_a")
        self.assertEqual(page.entries["LayoutPath"].get(), os.path.realpath(gds))

    def test_editing_a_field_updates_the_text(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPrimary", "block_b")
        self.assertIn('LAYOUT PRIMARY "block_b"',
                      self.active_lines(page.cmd_text.get_text(), "LAYOUT PRIMARY")[0])

    def test_commented_lines_are_left_alone(self):
        page = self.open_tab("DRC")
        self.set_text(page,
                      '//LAYOUT PRIMARY "ignored"\n'
                      'LAYOUT PRIMARY "real"\n')
        self.assertEqual(page.entries["LayoutPrimary"].get(), "real")

    # --- files ---------------------------------------------------------
    def test_load_default_reads_the_central_command_file(self):
        page = self.open_tab("DRC")
        self.set_text(page, "// replaced by the test\n")
        self.click(page, "LoadDefault")
        central = config.central_default_file("DRC", config.DESIGN_NAME)
        with open(central, encoding="utf-8") as f:
            self.assertIn(f.read().splitlines()[0], page.cmd_text.get_text())

    def test_the_include_line_follows_the_central_inc(self):
        deck = config.read_lines(
            config.central_include_file("DRC", config.DESIGN_NAME))[0]
        page = self.open_tab("DRC")
        includes = self.active_lines(page.cmd_text.get_text(), "include")
        self.assertEqual(includes[0].strip(), "include %s" % deck)

    def test_load_and_save_use_the_file_dialogs(self):
        page = self.open_tab("DRC")
        target = os.path.join(self.paths["work"], "saved.com")
        self.files = [target]
        self.click(page, "Save")
        self.assertTrue(os.path.isfile(target))

        self.set_text(page, "// something else\n")
        self.files = [target]
        self.click(page, "Load")
        self.assertNotIn("something else", page.cmd_text.get_text())

    def test_state_is_remembered_per_tab(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPrimary", "remembered")
        page.flush()
        self.assertEqual(self.session("DRC").get("LayoutPrimary"), "remembered")

        again = self.open_tab("DRC")
        self.assertEqual(again.entries["LayoutPrimary"].get(), "remembered")

    def test_each_design_keeps_its_own_state(self):
        first = config.DESIGN_NAME
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPrimary", "for_design_one")
        page.flush()

        self.set_design("t40lp_1p6m_4x1u")           # via the PROCESS tab
        other = self.open_tab("DRC")
        self.assertNotEqual(other.entries["LayoutPrimary"].get(), "for_design_one",
                            "the other design inherited this design's state")

        self.set_design(first)                       # and coming back restores it
        back = self.open_tab("DRC")
        self.assertEqual(back.entries["LayoutPrimary"].get(), "for_design_one")

    def test_the_file_manager_is_launched_directly(self):
        """Not through xdg-open, which on some setups passes the .desktop Exec
        line unexpanded and opens a tab literally named %i."""
        self.assertEqual(config.file_managers()[-1], "xdg-open",
                         "xdg-open must be the last resort, not the first try")

        page = self.open_tab("DRC")
        self.set_entry(page, "RunFolder", self.run_folder())
        self.click(page, "FileManager")
        self.assertTrue(self.spawned, "FileManager launched nothing")
        launched = self.spawned[-1]
        self.assertNotIn("xdg-open", launched[0])
        self.assertEqual(launched[1:], [self.run_folder()],
                         "the file manager got more than the folder")

    def test_a_chosen_file_manager_is_used(self):
        os.environ["PDKGUI_FILEMANAGER"] = "caja"
        self.addCleanup(os.environ.pop, "PDKGUI_FILEMANAGER", None)
        self.assertEqual(config.file_managers(), ("caja",))

    def test_desktop_programs_do_not_inherit_the_eda_library_path(self):
        """dolphin loaded calibre's libpng15 and failed; desktop programs are
        built against the system libraries."""
        os.environ["LD_LIBRARY_PATH"] = "/tools/mentor/calibre/2021.1/lib"
        self.addCleanup(os.environ.pop, "LD_LIBRARY_PATH", None)
        self.assertNotIn("LD_LIBRARY_PATH", config.desktop_env())
        self.assertEqual(os.environ["LD_LIBRARY_PATH"],
                         "/tools/mentor/calibre/2021.1/lib",
                         "pdkgui's own environment must be left alone")

    def test_view_opens_the_layout_in_skipper(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPath", os.path.join(self.paths["work"], "top.gds"))
        self.click(page, "View")
        self.assertTrue(self.spawned, "View launched nothing")


class LvsTab(GuiTestCase):
    def test_has_the_source_fields_on_top_of_the_layout_ones(self):
        page = self.open_tab("LVS")
        for key in ("LayoutPath", "LayoutPrimary", "SourcePath", "SourcePrimary",
                    "LvsHier", "RunFolder"):
            self.assertIn(key, page.entries)
        self.button(page, "Edit")        # opens SourcePath in the editor

    def test_lvs_hier_defaults_on_and_drives_the_run_script(self):
        page = self.open_tab("LVS")
        self.assertTrue(page.entries["LvsHier"].get(), "LvsHier should default on")

        self.set_entry(page, "RunFolder", self.run_folder())
        self.click(page, "Run")
        self.assertIn("calibre -64 -lvs -hier -turbo -turbo_all", self.run_script())

        self.set_check(page, "LvsHier", False)
        self.click(page, "Run")
        script = self.run_script()
        self.assertIn("calibre -64 -lvs", script)
        self.assertNotIn("-hier", script)

    def test_source_fields_sync_with_the_text(self):
        page = self.open_tab("LVS")
        cdl = os.path.join(self.paths["work"], "top.cdl")
        self.set_text(page,
                      'SOURCE PRIMARY "src_top"\n'
                      'SOURCE PATH "%s"\n' % cdl)
        self.assertEqual(page.entries["SourcePrimary"].get(), "src_top")
        self.assertEqual(page.entries["SourcePath"].get(), os.path.realpath(cdl))

    def test_rve_opens_the_lvs_view_of_the_svdb(self):
        page = self.open_tab("LVS")
        self.set_entry(page, "RunFolder", self.run_folder())
        self.click(page, "Rve")
        script = self.run_script()
        self.assertIn("calibre -turbo 8 -rve -lvs svdb", script)
        self.assertIn("module load %s" % self.app.env["calibre"], script)

    def test_rve_reads_svdb_whatever_the_command_file_says(self):
        """calibre writes the svdb directory itself; the RESULTS DATABASE line
        must not rename it."""
        page = self.open_tab("LVS")
        self.set_entry(page, "RunFolder", self.run_folder())
        self.set_text(page, page.cmd_text.get_text().replace(
            'DRC RESULTS DATABASE "svdb"',
            'DRC RESULTS DATABASE "lvs.db"'))
        self.click(page, "Rve")
        self.assertIn("calibre -turbo 8 -rve -lvs svdb", self.run_script())

    def test_rve_uses_the_calibre_version_picked_on_env(self):
        env = self.open_tab("ENV")
        pick = list(env.combos["calibre"].cget("values"))[-1]
        env.combos["calibre"].set(pick)
        env.combos["calibre"].event_generate("<<ComboboxSelected>>")
        self.app.update()

        page = self.open_tab("LVS")
        self.set_entry(page, "RunFolder", self.run_folder())
        self.click(page, "Rve")
        self.assertIn("module load %s" % pick, self.run_script())

    def test_edit_opens_the_source_netlist(self):
        page = self.open_tab("LVS")
        self.set_entry(page, "SourcePath", os.path.join(self.paths["work"], "top.cdl"))
        self.click(page, "Edit")
        self.assertTrue(self.spawned, "Edit launched no editor")


if __name__ == "__main__":
    unittest.main()
