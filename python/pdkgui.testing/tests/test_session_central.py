#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Things that sit under the tabs: where files are read from, what is
remembered between runs, and the conversion of the old flat layout."""

import os
import unittest

import config
import sandbox
from harness import GuiTestCase


class CentralFiles(GuiTestCase):
    def test_command_files_come_from_the_central_design_dir(self):
        for module in ("DRC", "LVS", "XRC"):
            self.assertEqual(config.central_default_file(module, config.DESIGN_NAME),
                             os.path.join(self.paths["design"], "%s.com" % module))

    def test_the_revision_history_is_shared_by_every_design(self):
        first = config.page_file("SYSTEM")
        config.DESIGN_NAME = "t40lp_1p6m_4x1u"
        self.assertEqual(config.page_file("SYSTEM"), first,
                         "SYSTEM should not depend on the process")
        self.assertEqual(first, os.path.join(self.paths["central"], "system.txt"))

    def test_a_missing_central_file_falls_back_to_the_built_in_one(self):
        os.remove(os.path.join(self.paths["design"], "DRC.com"))
        page = self.open_tab("DRC")
        self.click(page, "LoadDefault")
        self.assertTrue(page.cmd_text.get_text().strip(),
                        "nothing was loaded when central was missing")

    def test_xrc_inc_provides_the_four_paths(self):
        paths = config.central_xrc_paths(config.DESIGN_NAME)
        for key in ("hcell", "xcell", "rules", "deck"):
            self.assertTrue(paths.get(key), "XRC.inc is missing %s" % key)

    def test_the_doc_pdfs_live_under_the_design(self):
        group = config.doc_group_dir(config.DESIGN_NAME, sandbox.DOC_NO, sandbox.DOC_ID)
        self.assertTrue(os.path.isdir(group))
        self.assertIn(self.paths["design"], group)


class SessionState(GuiTestCase):
    def test_each_tab_has_its_own_file(self):
        """Tabs keep separate state, so they cannot overwrite each other."""
        drc = self.open_tab("DRC")
        self.set_entry(drc, "LayoutPrimary", "drc_cell")
        drc.flush()
        lvs = self.open_tab("LVS")
        self.set_entry(lvs, "LayoutPrimary", "lvs_cell")
        lvs.flush()

        self.assertEqual(self.session("DRC")["LayoutPrimary"], "drc_cell")
        self.assertEqual(self.session("LVS")["LayoutPrimary"], "lvs_cell")

    def test_the_open_tab_is_restored(self):
        self.open_tab("XRC")
        self.app._on_close()
        self.app = self.pdkgui_app.PdkGui()
        self.app.withdraw()
        self.assertEqual(self.app.current_module.get(), "XRC")

    def test_closing_saves_without_waiting_for_the_debounce(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "LayoutPrimary", "saved_on_close")
        self.app._on_close()
        self.assertEqual(self.session("DRC")["LayoutPrimary"], "saved_on_close")


class LegacyMigration(GuiTestCase):
    """The old ~/.pdkgui/.pdkgui.<tab><PROCESS>.{commandfile,gui} files."""

    def setUp(self):
        super(LegacyMigration, self).setUp()
        # starting the app already ran the conversion (on an empty user dir).
        # Forget that, so each test can stage its own old files and convert as
        # if this were the user's first start on the new version.
        self._forget_migration()

    def _forget_migration(self):
        for marker in (config.LEGACY_MARKER, config.LEGACY_MARKER_V1):
            path = os.path.join(self.paths["user"], marker)
            if os.path.exists(path):
                os.remove(path)

    def _legacy(self, name, content):
        path = os.path.join(self.paths["user"], name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def _migrate(self):
        return config.migrate_legacy_user_files()

    def test_command_files_become_sessions(self):
        self._legacy(".pdkgui.drc%s.commandfile" % config.DESIGN_NAME,
                     'LAYOUT PRIMARY "from_legacy"\n')
        self._migrate()
        self.assertIn("from_legacy", self.session("DRC")["__command__"])

    def test_gds_lists_become_sessions(self):
        self._legacy(".pdkgui.skipper%s.gui" % config.DESIGN_NAME,
                     "layout_path1 /a/one.gds\nlayout_path3 /a/three.gds\n")
        self._migrate()
        gds = self.session("SKIPPER")["gds"]
        self.assertEqual(gds[0], "/a/one.gds")
        self.assertEqual(gds[1], "", "row 2 should stay empty")
        self.assertEqual(gds[2], "/a/three.gds")
        self.assertEqual(len(gds), 10, "the list should be padded to ten rows")

    def test_the_originals_are_kept(self):
        path = self._legacy(".pdkgui.drc%s.commandfile" % config.DESIGN_NAME, "x\n")
        self._migrate()
        self.assertTrue(os.path.isfile(path), "the old file was deleted")

    def test_it_runs_only_once(self):
        self._legacy(".pdkgui.drc%s.commandfile" % config.DESIGN_NAME, "first\n")
        self.assertTrue(self._migrate())
        self.assertEqual(self._migrate(), [], "the conversion ran twice")

    def test_work_already_done_in_the_new_layout_wins(self):
        config.save_json(config.user_session_file("DRC", config.DESIGN_NAME),
                         {"__command__": "NEWER", "RunFolder": "/keep"})
        self._legacy(".pdkgui.drc%s.commandfile" % config.DESIGN_NAME, "OLDER\n")
        self._migrate()
        session = self.session("DRC")
        self.assertEqual(session["__command__"], "NEWER")
        self.assertEqual(session["RunFolder"], "/keep")

    def test_a_gds_list_is_merged_row_by_row(self):
        """The reported case: one row typed in the new version, the rest still
        only in the old file."""
        config.save_json(config.user_session_file("SKIPPER", config.DESIGN_NAME),
                         {"gds": ["/typed/by_hand.gds"] + [""] * 9})
        self._legacy(".pdkgui.skipper%s.gui" % config.DESIGN_NAME,
                     "layout_path1 /old/one.gds\nlayout_path2 /old/two.gds\n")
        self._migrate()
        gds = self.session("SKIPPER")["gds"]
        self.assertEqual(gds[0], "/typed/by_hand.gds", "the typed row was lost")
        self.assertEqual(gds[1], "/old/two.gds", "the empty row was not filled")

    def test_a_marker_from_an_older_version_does_not_block_new_steps(self):
        config.save_json(os.path.join(self.paths["user"], ".migrated"),
                         {"done": ["commandfile", "gui"]})     # no version key
        self._legacy(".pdkgui.skipper%s.gui" % config.DESIGN_NAME,
                     "layout_path1 /a/one.gds\n")
        self.assertTrue(self._migrate(), "an old marker blocked the conversion")


if __name__ == "__main__":
    unittest.main()
