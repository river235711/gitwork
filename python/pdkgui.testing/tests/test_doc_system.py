#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The DOC browser and the SYSTEM tab (revision history + release panel)."""

import os
import unittest

import config
import sandbox
from harness import GuiTestCase


class DocTab(GuiTestCase):
    def setUp(self):
        super(DocTab, self).setUp()
        self.page = self.open_tab("DOC")
        self.index = config.read_doc_index(config.DESIGN_NAME)

    def test_left_column_lists_each_doc_number_once(self):
        listed = list(self.page.lb_docno.get(0, "end"))
        self.assertEqual(listed, sorted({d[0] for d in self.index}))

    def test_choosing_a_doc_number_lists_its_titles(self):
        for docno in self.page.lb_docno.get(0, "end"):
            self._select(self.page.lb_docno, docno)
            self.page._on_pick_docno()
            expected = [d[2] for d in self.index if d[0] == docno]
            self.assertEqual(list(self.page.lb_title.get(0, "end")), expected,
                             "%s listed the wrong titles" % docno)

    def test_choosing_a_title_lists_that_document_pdfs(self):
        self._select(self.page.lb_docno, sandbox.DOC_NO)
        self.page._on_pick_docno()
        self.page.lb_title.selection_set(0)
        self.page._on_pick_title()

        listed = list(self.page.lb_group.get(0, "end"))
        self.assertEqual(listed, sorted(sandbox.DOC_PDFS))
        self.assertNotIn("not_a_pdf.txt", listed, "non-PDF files were listed")

    def test_opening_a_pdf_launches_a_viewer(self):
        self._select(self.page.lb_docno, sandbox.DOC_NO)
        self.page._on_pick_docno()
        self.page.lb_title.selection_set(0)
        self.page._on_pick_title()
        self.page.lb_group.selection_set(0)
        self.page._on_pick_pdf()

        self.assertTrue(self.spawned, "no viewer was launched")
        self.assertTrue(self.spawned[-1][-1].endswith(".pdf"))

    def test_a_document_without_files_says_so_instead_of_failing(self):
        missing = [d for d in self.index if d[0] != sandbox.DOC_NO]
        self.assertTrue(missing, "the index needs a document with no pdf dir")
        docno = missing[0][0]
        self._select(self.page.lb_docno, docno)
        self.page._on_pick_docno()
        self.page.lb_title.selection_set(0)
        self.page._on_pick_title()

        shown = list(self.page.lb_group.get(0, "end"))
        self.assertEqual(len(shown), 1)
        self.assertTrue(shown[0].startswith("(not found:"))

    def test_all_three_columns_scroll_sideways(self):
        for name in ("lb_docno", "lb_title", "lb_group"):
            listbox = getattr(self.page, name)
            self.assertTrue(listbox.cget("xscrollcommand"),
                            "%s cannot be scrolled sideways" % name)
            self.assertTrue(listbox.cget("yscrollcommand"))

    @staticmethod
    def _select(listbox, value):
        index = list(listbox.get(0, "end")).index(value)
        listbox.selection_clear(0, "end")
        listbox.selection_set(index)


class SystemTab(GuiTestCase):
    def test_shows_the_central_revision_history(self):
        page = self.open_tab("SYSTEM")
        text = self.widgets(page, "Text")[0].get("1.0", "end-1c")
        with open(config.page_file("SYSTEM"), encoding="utf-8") as f:
            self.assertEqual(text.strip(), f.read().strip())

    def test_the_history_is_read_only(self):
        page = self.open_tab("SYSTEM")
        self.assertEqual(str(self.widgets(page, "Text")[0].cget("state")), "disabled")

    def test_page_is_split_into_two_halves(self):
        page = self.open_tab("SYSTEM")
        self.assertEqual(page.grid_rowconfigure(0)["weight"], 1)
        self.assertEqual(page.grid_rowconfigure(1)["weight"], 1)

    def test_up_to_date_shows_just_the_release(self):
        self._run_from(sandbox.OLD_RELEASE, current=sandbox.OLD_RELEASE)
        page = self.open_tab("SYSTEM")
        labels = self.labels(page)
        self.assertIn(sandbox.OLD_RELEASE, labels)
        self.assertTrue(any("current release" in t for t in labels))
        with self.assertRaises(AssertionError):
            self.button(page, "Restart now")

    def test_a_new_release_is_named_and_offers_a_restart(self):
        self._run_from(sandbox.OLD_RELEASE, current=sandbox.NEW_RELEASE)
        page = self.open_tab("SYSTEM")
        joined = " ".join(self.labels(page))
        self.assertIn(sandbox.OLD_RELEASE, joined)
        self.assertIn(sandbox.NEW_RELEASE, joined)

        self.click(page, "Restart now")
        self.assertTrue(self.spawned, "Restart launched nothing")
        self.assertEqual(self.spawned[-1][0],
                         os.path.join(sandbox.install_dir(sandbox.NEW_RELEASE),
                                      "pdkgui"),
                         "restarted from the wrong release")

    def test_outside_a_release_layout_it_just_reports_the_directory(self):
        page = self.open_tab("SYSTEM")     # running from the source checkout
        joined = " ".join(self.labels(page))
        self.assertIn("Running from", joined)

    def _run_from(self, release, current):
        """Pretend this instance was started from <release>.

        (The harness restores config.BASE_DIR after each test.)"""
        config.BASE_DIR = sandbox.install_dir(release)
        sandbox.set_current_release(current)


if __name__ == "__main__":
    unittest.main()
