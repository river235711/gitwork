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
                      'LAYOUT PRIMARY "top"\n'
                      'LAYOUT PATH "%s"\n' % gds)
        self.assertEqual(page.entries["LayoutPath"].get(), os.path.realpath(gds))

        # renaming the cell alone: the layout is the same file, so the name is
        # the user's to choose and it reaches the field
        self.set_text(page,
                      'LAYOUT PRIMARY "block_a"\n'
                      'LAYOUT PATH "%s"\n' % gds)
        self.assertEqual(page.entries["LayoutPrimary"].get(), "block_a")

    def test_editing_a_field_updates_the_text(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPrimary", "block_b")
        self.assertIn('LAYOUT PRIMARY "block_b"',
                      self.active_lines(page.cmd_text.get_text(), "LAYOUT PRIMARY")[0])

    def test_a_field_emptied_and_filled_again_reaches_the_text(self):
        """Once the line held nothing, the value regexes stopped matching it, so
        the next thing typed had nowhere to go and the text kept the empty one --
        and the Run writes the text."""
        page = self.open_tab("DRC")
        self.set_text(page, 'LAYOUT PRIMARY "abc"\nLAYOUT PATH "/p/x/abc.gds"\n')

        self.set_entry(page, "LayoutPrimary", "")
        self.assertIn('LAYOUT PRIMARY ""', page.cmd_text.get_text())

        self.set_entry(page, "LayoutPrimary", "NEW_NAME")
        self.assertIn('LAYOUT PRIMARY "NEW_NAME"', page.cmd_text.get_text())

    def test_every_field_survives_being_emptied_and_filled_again(self):
        page = self.open_tab("LVS")
        self.set_text(page, 'LAYOUT PRIMARY "a"\nLAYOUT PATH "/p/a.gds"\n'
                            'SOURCE PRIMARY "b"\nSOURCE PATH "/p/b.cdl"\n')
        for key, keyword, value in (("LayoutPrimary", "LAYOUT PRIMARY", "L1"),
                                    ("LayoutPath", "LAYOUT PATH", "/p/z/L2.gds"),
                                    ("SourcePrimary", "SOURCE PRIMARY", "S1"),
                                    ("SourcePath", "SOURCE PATH", "/p/z/S2.cdl")):
            self.set_entry(page, key, "")
            self.set_entry(page, key, value)
            self.assertIn('%s "%s"' % (keyword, value), page.cmd_text.get_text(),
                          "%s did not reach the text" % key)

    def test_a_line_that_is_not_there_is_written(self):
        """A value with nowhere to go would be dropped without a word."""
        page = self.open_tab("LVS")
        self.set_text(page, 'LAYOUT PRIMARY "abc"\n')
        self.set_entry(page, "LayoutPath", "/p/y/newlayout.gds")

        lines = self.active_lines(page.cmd_text.get_text())
        self.assertIn('LAYOUT PATH "/p/y/newlayout.gds"', [ln.strip() for ln in lines])
        # and in the order these files are written: PRIMARY, then PATH
        self.assertLess([i for i, ln in enumerate(lines) if "LAYOUT PRIMARY" in ln][0],
                        [i for i, ln in enumerate(lines) if "LAYOUT PATH" in ln][0])

    def test_a_field_with_neither_line_present_still_lands_in_the_text(self):
        page = self.open_tab("LVS")
        self.set_text(page, '// nothing here\nLVS REPORT "lvs.rep"\n')
        self.set_entry(page, "SourcePrimary", "src_cell")
        self.assertIn('SOURCE PRIMARY "src_cell"', page.cmd_text.get_text())

    def test_emptying_a_name_in_the_text_empties_the_field(self):
        """The other direction of the same rule: the field must not go on showing
        a name the command file no longer has, since the Run writes the text."""
        page = self.open_tab("DRC")
        self.set_text(page, 'LAYOUT PRIMARY "abc"\nLAYOUT PATH "/p/x/abc.gds"\n')
        self.assertEqual(page.entries["LayoutPrimary"].get(), "abc")

        self.set_text(page, 'LAYOUT PRIMARY ""\nLAYOUT PATH "/p/x/abc.gds"\n')
        self.assertEqual(page.entries["LayoutPrimary"].get(), "",
                         "the field kept a name the command file dropped")

    def test_emptying_a_path_in_the_text_does_not_leave_the_current_directory(self):
        """realpath("") is the directory pdkgui happens to be in -- an empty path
        means empty."""
        page = self.open_tab("DRC")
        self.set_text(page, 'LAYOUT PATH "/p/x/abc.gds"\n')
        self.set_text(page, 'LAYOUT PATH ""\n')
        self.assertEqual(page.entries["LayoutPath"].get(), "")

    def test_commented_lines_are_left_alone(self):
        page = self.open_tab("DRC")
        self.set_text(page,
                      '//LAYOUT PRIMARY "ignored"\n'
                      'LAYOUT PRIMARY "real"\n')
        self.assertEqual(page.entries["LayoutPrimary"].get(), "real")

    # --- browsing ------------------------------------------------------
    def test_browsing_a_layout_fills_in_the_cell_name(self):
        for module in DRC_CLASS:
            page = self.open_tab(module)
            self.browse(page, "LayoutPath",
                        os.path.join(self.paths["work"], "tx_fe_top_II_2G_v4_ulvt.gds"))
            self.assertEqual(page.entries["LayoutPrimary"].get(),
                             "tx_fe_top_II_2G_v4_ulvt", "%s did not parse it" % module)

    def test_a_compressed_layout_loses_both_extensions(self):
        page = self.open_tab("DRC")
        self.browse(page, "LayoutPath",
                    os.path.join(self.paths["work"], "tx_fe_top_II_2G_v4_ulvt.gds.gz"))
        self.assertEqual(page.entries["LayoutPrimary"].get(), "tx_fe_top_II_2G_v4_ulvt")

    def test_browsing_writes_both_lines_into_the_command_text(self):
        """The run reads the text, not the fields, so a browsed path that stopped
        at the field would be silently ignored."""
        page = self.open_tab("DRC")
        gds = os.path.join(self.paths["work"], "block_top.gds")
        self.browse(page, "LayoutPath", gds)
        text = page.cmd_text.get_text()
        self.assertIn('LAYOUT PATH "%s"' % os.path.realpath(gds),
                      self.active_lines(text, "LAYOUT PATH")[0])
        self.assertIn('LAYOUT PRIMARY "block_top"',
                      self.active_lines(text, "LAYOUT PRIMARY")[0])

    def test_choosing_the_same_file_again_puts_the_name_back(self):
        """Open is a deliberate "use this one", so it re-derives the name even
        though the path did not move -- otherwise a cell renamed by hand could
        only be put right by picking some other file first."""
        page = self.open_tab("DRC")
        gds = os.path.join(self.paths["work"], "adcdac_slc.gds")
        self.browse(page, "LayoutPath", gds)
        self.assertEqual(page.entries["LayoutPrimary"].get(), "adcdac_slc")

        self.set_entry(page, "LayoutPrimary", "adcdac_slcxxxxx")
        self.browse(page, "LayoutPath", gds)              # the very same file

        self.assertEqual(page.entries["LayoutPrimary"].get(), "adcdac_slc")
        self.assertIn('LAYOUT PRIMARY "adcdac_slc"', page.cmd_text.get_text())

    def test_choosing_the_same_file_again_fills_a_cleared_name(self):
        """Same rule from the other end: the name was emptied rather than
        changed, and the file it should come from has not moved."""
        page = self.open_tab("DRC")
        gds = os.path.join(self.paths["work"], "adcdac_slc.gds")
        self.browse(page, "LayoutPath", gds)
        self.set_entry(page, "LayoutPrimary", "")
        self.assertIn('LAYOUT PRIMARY ""', page.cmd_text.get_text())

        self.browse(page, "LayoutPath", gds)              # the very same file
        self.assertEqual(page.entries["LayoutPrimary"].get(), "adcdac_slc")
        self.assertIn('LAYOUT PRIMARY "adcdac_slc"', page.cmd_text.get_text())

    def test_reopening_a_layout_leaves_the_source_cell_alone(self):
        """The force is one field, not all of them."""
        page = self.open_tab("LVS")
        gds = os.path.join(self.paths["work"], "lay.gds")
        self.browse(page, "LayoutPath", gds)
        self.browse(page, "SourcePath", os.path.join(self.paths["work"], "src.cdl"))
        self.set_entry(page, "SourcePrimary", "KEEP_MY_SOURCE")

        self.browse(page, "LayoutPath", gds)
        self.assertEqual(page.entries["SourcePrimary"].get(), "KEEP_MY_SOURCE")
        self.assertIn('SOURCE PRIMARY "KEEP_MY_SOURCE"', page.cmd_text.get_text())

    def test_browsing_a_run_folder_leaves_the_cell_name_alone(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPrimary", "kept")
        self.browse(page, "RunFolder", self.paths["work"])
        self.assertEqual(page.entries["RunFolder"].get(), self.paths["work"])
        self.assertEqual(page.entries["LayoutPrimary"].get(), "kept")

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

    # --- loading a command file that names no cell -----------------------
    def _load_com(self, page, body, name="loaded.com"):
        path = os.path.join(self.paths["work"], name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        self.files = [path]
        self.click(page, "Load")

    def test_loading_a_file_with_an_empty_primary_names_the_cell(self):
        """`LAYOUT PRIMARY ""` used to leave the field showing the *previous*
        file's cell while the text stayed empty -- and the Run writes the text."""
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPrimary", "from_the_last_file")
        self._load_com(page, 'LAYOUT PRIMARY ""\n'
                             'LAYOUT PATH "/p/other/top_block.gds"\n')

        self.assertEqual(page.entries["LayoutPrimary"].get(), "top_block")
        self.assertIn('LAYOUT PRIMARY "top_block"',
                      self.active_lines(page.cmd_text.get_text(), "LAYOUT PRIMARY")[0])

    def test_loading_a_file_with_no_primary_line_gets_one(self):
        page = self.open_tab("DRC")
        self._load_com(page, 'LAYOUT PATH "/p/third/chip_a.gds.gz"\n')

        self.assertEqual(page.entries["LayoutPrimary"].get(), "chip_a")
        lines = self.active_lines(page.cmd_text.get_text())
        self.assertIn('LAYOUT PRIMARY "chip_a"', [ln.strip() for ln in lines])
        # and it reads in the usual order, beside the path it belongs with
        self.assertLess(lines.index('LAYOUT PRIMARY "chip_a"'),
                        [i for i, ln in enumerate(lines) if "LAYOUT PATH" in ln][0])

    def test_loading_names_the_cell_after_the_file_it_points_at(self):
        """Even when the file carries a name of its own: the cell is named after
        the layout, and a loaded .com brings a new layout with it."""
        page = self.open_tab("DRC")
        self._load_com(page, 'LAYOUT PRIMARY "SOME_OLD_NAME"\n'
                             'LAYOUT PATH "/p/d/loaded_cell.gds"\n')
        self.assertEqual(page.entries["LayoutPrimary"].get(), "loaded_cell")
        self.assertIn('LAYOUT PRIMARY "loaded_cell"', page.cmd_text.get_text())

    def test_typing_a_path_into_the_field_renames_the_cell(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPath", "/p/b/other_block.gds")
        self.assertEqual(page.entries["LayoutPrimary"].get(), "other_block")
        self.assertIn('LAYOUT PRIMARY "other_block"', page.cmd_text.get_text())

    def test_editing_the_path_line_in_the_text_renames_the_cell(self):
        page = self.open_tab("DRC")
        self.set_text(page, 'LAYOUT PRIMARY "stale"\n'
                            'LAYOUT PATH "/p/c/typed_in_text.gds.gz"\n')
        self.assertEqual(page.entries["LayoutPrimary"].get(), "typed_in_text")
        self.assertIn('LAYOUT PRIMARY "typed_in_text"', page.cmd_text.get_text())

    def test_a_name_typed_by_hand_stands_until_the_file_changes(self):
        """Only a path that actually moved renames the cell, so a name chosen on
        purpose is not overwritten by the next unrelated keystroke."""
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPath", "/p/x/block.gds")
        self.set_entry(page, "LayoutPrimary", "MY_OWN_TOPCELL")

        self.set_text(page, page.cmd_text.get_text() + "\n// unrelated\n")
        self.assertEqual(page.entries["LayoutPrimary"].get(), "MY_OWN_TOPCELL")

        self.set_entry(page, "LayoutPath", "/p/e/final_block.gds")
        self.assertEqual(page.entries["LayoutPrimary"].get(), "final_block",
                         "changing the layout must rename the cell again")

    def test_reopening_the_tab_keeps_the_name_that_was_saved(self):
        """Restoring a session is not a path change; whatever was left there
        comes back."""
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPath", "/p/x/block.gds")
        self.set_entry(page, "LayoutPrimary", "MY_OWN_TOPCELL")
        page.flush()

        self.open_tab("LVS")
        self.app._drop_cached_pages()          # force a rebuild from the session
        again = self.open_tab("DRC")
        self.assertEqual(again.entries["LayoutPrimary"].get(), "MY_OWN_TOPCELL")

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

    def test_the_run_terminal_says_which_process_and_tab_it_is(self):
        """Several run windows are open at once; '(on <host>)' is the window
        manager's own suffix."""
        page = self.open_tab("DRC")
        self.set_entry(page, "RunFolder", self.run_folder())
        self.click(page, "Run")
        self.assertIn("\\033]0;.pdkgui_run.sh - %s - DRC\\007" % config.DESIGN_NAME,
                      self.run_wrapper())

    def test_view_opens_the_layout_in_skipper(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPath", os.path.join(self.paths["work"], "top.gds"))
        self.click(page, "View")
        self.assertTrue(self.spawned, "View launched nothing")


class CellNameFromPath(unittest.TestCase):
    """The rule browsing uses: strip the directory and the extension, and strip
    two extensions when the second is .gz."""

    def test_the_cases_that_come_up(self):
        from pages.verify import _cell_name
        cases = {
            "/p/verify/tx_fe_top_II_2G_v4_ulvt/tx_fe_top_II_2G_v4_ulvt.gds":
                "tx_fe_top_II_2G_v4_ulvt",
            "/p/verify/tx_fe_top_II_2G_v4_ulvt/tx_fe_top_II_2G_v4_ulvt.gds.gz":
                "tx_fe_top_II_2G_v4_ulvt",
            "/p/SYLINCOM/TRX_ABB_TOP_6G_SYLINCOM_v1.spi": "TRX_ABB_TOP_6G_SYLINCOM_v1",
            "/p/top.cdl": "top",
            "/p/top.oas": "top",
            "/p/TOP.GDS.GZ": "TOP",              # the check is case-insensitive
            "/p/top.v1.gds": "top.v1",           # only the last extension goes
            "/p/no_extension": "no_extension",
            "/p/spaced name.gds": "spaced name",
        }
        for path, expected in cases.items():
            self.assertEqual(_cell_name(path), expected, path)


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

    # --- the hcell list -----------------------------------------------
    def test_the_hcell_row_starts_at_the_central_path_and_unused(self):
        page = self.open_tab("LVS")
        hcell = config.central_xrc_paths(config.DESIGN_NAME)["hcell"]
        self.assertEqual(page.entries["Hcell"].get(), hcell,
                         "the path comes from XRC.inc, as on the XRC tab")
        self.assertFalse(page.entries["HcellUse"].get(),
                         "an LVS that never passed an hcell list must keep running as it did")

    def test_the_hcell_list_is_passed_only_when_both_boxes_are_ticked(self):
        page = self.open_tab("LVS")
        self.set_entry(page, "RunFolder", self.run_folder())
        hcell = page.entries["Hcell"].get()
        com = page._com_filename()

        self.set_check(page, "LvsHier", True)
        self.set_check(page, "HcellUse", True)
        self.click(page, "Run")
        self.assertIn("calibre -64 -lvs -hier -turbo -turbo_all -hcell %s %s"
                      % (hcell, com), self.run_script())

        # hierarchical, but the list is not wanted
        self.set_check(page, "HcellUse", False)
        self.click(page, "Run")
        script = self.run_script()
        self.assertIn("calibre -64 -lvs -hier -turbo -turbo_all %s" % com, script)
        self.assertNotIn("-hcell", script)

        # flat: the list goes whether or not its box is ticked
        for use in (True, False):
            self.set_check(page, "LvsHier", False)
            self.set_check(page, "HcellUse", use)
            self.click(page, "Run")
            script = self.run_script()
            self.assertIn("calibre -64 -lvs %s | tee lvs.log" % com, script)
            self.assertNotIn("-hcell", script)
            self.assertNotIn("-hier", script)

    def test_an_edited_hcell_path_is_the_one_that_runs(self):
        page = self.open_tab("LVS")
        self.set_entry(page, "RunFolder", self.run_folder())
        hcell = os.path.join(self.run_folder(), "my_hcell")
        self.set_entry(page, "Hcell", hcell)
        self.set_check(page, "HcellUse", True)
        self.click(page, "Run")
        self.assertIn("-hcell %s " % hcell, self.run_script())

    def test_use_with_an_empty_path_passes_no_list(self):
        """The box says 'use this list' -- with no list there, the run says
        nothing about one rather than reaching for the central path."""
        page = self.open_tab("LVS")
        self.set_entry(page, "RunFolder", self.run_folder())
        self.set_entry(page, "Hcell", "")
        self.set_check(page, "HcellUse", True)
        self.click(page, "Run")
        script = self.run_script()
        self.assertIn("calibre -64 -lvs -hier -turbo -turbo_all %s | tee lvs.log"
                      % page._com_filename(), script)
        self.assertNotIn("-hcell", script)

    def test_the_hcell_row_browses_and_is_remembered(self):
        page = self.open_tab("LVS")
        hcell = os.path.join(self.paths["work"], "picked_hcell")
        self.browse(page, "Hcell", hcell)
        self.assertEqual(page.entries["Hcell"].get(), hcell)

        self.set_check(page, "HcellUse", True)
        page.flush()
        st = self.session("LVS")
        self.assertEqual(st["Hcell"], hcell)
        self.assertTrue(st["HcellUse"])

    def test_source_fields_sync_with_the_text(self):
        page = self.open_tab("LVS")
        cdl = os.path.join(self.paths["work"], "top.cdl")
        self.set_text(page,
                      'SOURCE PRIMARY "top"\n'
                      'SOURCE PATH "%s"\n' % cdl)
        self.assertEqual(page.entries["SourcePath"].get(), os.path.realpath(cdl))

        # the netlist is unchanged, so this name is the user's own
        self.set_text(page,
                      'SOURCE PRIMARY "src_top"\n'
                      'SOURCE PATH "%s"\n' % cdl)
        self.assertEqual(page.entries["SourcePrimary"].get(), "src_top")

    def test_browsing_a_source_netlist_fills_in_its_cell_name(self):
        page = self.open_tab("LVS")
        spi = os.path.join(self.paths["work"], "TRX_ABB_TOP_6G_SYLINCOM_v1.spi")
        self.browse(page, "SourcePath", spi)
        self.assertEqual(page.entries["SourcePrimary"].get(),
                         "TRX_ABB_TOP_6G_SYLINCOM_v1")
        self.assertIn('SOURCE PRIMARY "TRX_ABB_TOP_6G_SYLINCOM_v1"',
                      self.active_lines(page.cmd_text.get_text(), "SOURCE PRIMARY")[0])

    def test_the_layout_and_source_cell_names_are_parsed_independently(self):
        page = self.open_tab("LVS")
        self.browse(page, "LayoutPath", os.path.join(self.paths["work"], "lay_top.gds"))
        self.browse(page, "SourcePath", os.path.join(self.paths["work"], "src_top.cdl"))
        self.assertEqual(page.entries["LayoutPrimary"].get(), "lay_top")
        self.assertEqual(page.entries["SourcePrimary"].get(), "src_top")

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

    def test_emptying_the_source_name_in_the_text_empties_its_field(self):
        page = self.open_tab("LVS")
        # named after its own file, so introducing it renames nothing
        cdl = "/p/net/keep.cdl"
        self.set_text(page, 'SOURCE PRIMARY "keep"\nSOURCE PATH "%s"\n' % cdl)
        self.assertEqual(page.entries["SourcePrimary"].get(), "keep")

        self.set_text(page, 'SOURCE PRIMARY ""\nSOURCE PATH "%s"\n' % cdl)
        self.assertEqual(page.entries["SourcePrimary"].get(), "")

    def test_loading_names_the_layout_and_the_source_cell_separately(self):
        page = self.open_tab("LVS")
        path = os.path.join(self.paths["work"], "pair.com")
        with open(path, "w", encoding="utf-8") as f:
            f.write('LAYOUT PRIMARY ""\n'
                    'LAYOUT PATH "/p/gds/lay_top.gds"\n'
                    'SOURCE PRIMARY ""\n'
                    'SOURCE PATH "/p/net/src_top.spi"\n')
        self.files = [path]
        self.click(page, "Load")

        self.assertEqual(page.entries["LayoutPrimary"].get(), "lay_top")
        self.assertEqual(page.entries["SourcePrimary"].get(), "src_top")
        text = page.cmd_text.get_text()
        self.assertIn('LAYOUT PRIMARY "lay_top"', text)
        self.assertIn('SOURCE PRIMARY "src_top"', text)

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
