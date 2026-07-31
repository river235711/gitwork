#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What each Open dialog offers in its "files of type" list.

Netlists here are not named consistently enough to filter on an extension, so
the patterns match anywhere in the name; layouts are the other way round. Every
list ends in "All types", so a file that follows no convention is still
reachable.
"""

import unittest

import config
from harness import GuiTestCase

LAYOUT = [("*.gds", "*.gds"), ("*.gds.gz", "*.gds.gz"), ("All types", "*")]
SOURCE = [("*sp*", "*sp*"), ("*spi*", "*spi*"), ("*netlist*", "*netlist*"),
          ("All types", "*")]
EXTRACTED = [("*sp*", "*sp*"), ("*spi*", "*spi*"), ("*netlist*", "*netlist*"),
             ("*dist*", "*dist*"), ("*dspf*", "*dspf*"), ("*lump*", "*lump*"),
             ("All types", "*")]

VERIFY_TABS = ("DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO", "LVS", "LVL", "XRC")


class FileTypes(GuiTestCase):
    def offered(self, page, key):
        """The types the Open button on that field's row put in the dialog."""
        self.file_dialogs = []
        self.browse(page, key, "/p/whatever.gds")
        kind, kwargs = self.file_dialogs[-1]
        self.assertEqual(kind, "askopenfilename")
        return [tuple(t) for t in kwargs.get("filetypes", ())]

    def test_every_layout_field_offers_gds(self):
        for module in VERIFY_TABS:
            page = self.open_tab(module)
            keys = [k for k in page.entries if k.startswith("LayoutPath")]
            self.assertTrue(keys, "%s has no layout field" % module)
            for key in keys:
                self.assertEqual(self.offered(page, key), LAYOUT,
                                 "%s/%s" % (module, key))

    def test_the_source_netlist_fields_offer_netlist_names(self):
        for module in ("LVS", "XRC"):
            page = self.open_tab(module)
            self.assertEqual(self.offered(page, "SourcePath"), SOURCE, module)

    def test_jivaro_also_offers_the_extracted_netlists(self):
        """It reduces XRC's output, so it has to see .dist / .lump / .dspf."""
        page = self.open_tab("JIVARO")
        self.assertEqual(self.offered(page, "File"), EXTRACTED)

    def test_the_gds_viewers_offer_gds(self):
        for module in ("SKIPPER", "KLAYOUT"):
            page = self.open_tab(module)
            self.file_dialogs = []
            self.files = ["/p/whatever.gds"]
            self.button(page, "Open").invoke()
            self.app.update()
            _kind, kwargs = self.file_dialogs[-1]
            self.assertEqual([tuple(t) for t in kwargs["filetypes"]], LAYOUT,
                             module)

    def test_choosing_a_run_folder_is_not_filtered(self):
        """It asks for a directory, which has no file type at all."""
        page = self.open_tab("DRC")
        self.file_dialogs = []
        self.browse(page, "RunFolder", "/p/somewhere")
        kind, kwargs = self.file_dialogs[-1]
        self.assertEqual(kind, "askdirectory")
        self.assertNotIn("filetypes", kwargs)

    def test_every_list_ends_in_all_types(self):
        """However badly a file is named, it can still be picked."""
        for kind, offered in config.FILE_TYPES.items():
            self.assertEqual(tuple(offered[-1]), ("All types", "*"), kind)

    def test_a_field_with_no_convention_gets_no_filter(self):
        self.assertEqual(config.file_types("something else"), ())
