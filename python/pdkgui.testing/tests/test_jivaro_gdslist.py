#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JIVARO, and the two GDS-list tabs (SKIPPER / KLAYOUT)."""

import os
import unittest

import config
from harness import GuiTestCase


class JivaroTab(GuiTestCase):
    def setUp(self):
        super(JivaroTab, self).setUp()
        self.page = self.open_tab("JIVARO")

    def test_has_only_a_file_and_a_run_folder(self):
        self.assertEqual(sorted(self.page.entries), ["File", "RunFolder"])
        self.assertIsNone(self.page.cmd_text, "JIVARO should have no command box")
        for label in ("Open", "Edit", "FileManager", "Run"):
            self.button(self.page, label)

    def test_run_writes_the_xml_and_the_script(self):
        netlist = os.path.join(self.paths["work"], "%s.lump" % config.DESIGN_NAME)
        self.set_entry(self.page, "File", netlist)
        self.set_entry(self.page, "RunFolder", self.run_folder())
        self.click(self.page, "Run")

        script = self.run_script()
        self.assertIn("module load", script)
        self.assertIn("jivaro -xml jivaro.xml", script)

        xml = self.jivaro_xml()
        self.assertIn('<inputFile value="%s"/>' % netlist, xml)
        self.assertIn('<outputFile value="./%s.red.lump"/>' % config.DESIGN_NAME, xml)
        self.assertIn('<reductionParameters version="2020.1">', xml)
        # this tab has no frequencyLimit field (the XRC one does), so the xml
        # keeps jivaro's own 20
        self.assertIn('<frequencyLimit  value="20"/>', xml)

    def test_output_name_follows_the_input_suffix(self):
        for suffix in ("lump", "dist"):
            netlist = os.path.join(self.paths["work"],
                                   "%s.%s" % (config.DESIGN_NAME, suffix))
            self.set_entry(self.page, "File", netlist)
            self.set_entry(self.page, "RunFolder", self.run_folder())
            self.click(self.page, "Run")
            self.assertIn('<outputFile value="./%s.red.%s"/>'
                          % (config.DESIGN_NAME, suffix), self.jivaro_xml())

    def test_run_without_a_file_complains_instead_of_writing(self):
        self.set_entry(self.page, "File", "")
        self.set_entry(self.page, "RunFolder", self.run_folder())
        self.click(self.page, "Run")
        self.assertTrue(any(kind == "showerror" for kind, _ in self.dialogs),
                        "an empty File was accepted silently")

    def test_fields_are_remembered(self):
        netlist = os.path.join(self.paths["work"], "%s.lump" % config.DESIGN_NAME)
        self.set_entry(self.page, "File", netlist)
        self.page.flush()
        self.assertEqual(self.session("JIVARO").get("File"), netlist)
        self.assertEqual(self.open_tab("JIVARO").entries["File"].get(), netlist)


class GdsListTabs(GuiTestCase):
    """SKIPPER and KLAYOUT share one page class but open different viewers."""

    def test_both_tabs_offer_ten_rows_with_open_and_view(self):
        for module in ("SKIPPER", "KLAYOUT"):
            page = self.open_tab(module)
            self.assertEqual(len(page.entries), page.ROWS)
            self.assertEqual(len(self.widgets(page, "Button")), page.ROWS * 2)

    def test_rows_are_remembered_per_design(self):
        gds = os.path.join(self.paths["work"], "top.gds")
        page = self.open_tab("SKIPPER")
        page.entries[0].delete(0, "end")
        page.entries[0].insert(0, gds)
        page.flush()
        self.assertEqual(self.session("SKIPPER")["gds"][0], gds)

        self.set_design("t40lp_1p6m_4x1u")
        other = self.open_tab("SKIPPER")
        self.assertNotEqual(other.entries[0].get(), gds,
                            "the GDS list leaked into another design")

    def test_view_opens_skipper_with_the_central_cds_paths(self):
        conf = config.read_conf(config.central_skipper_conf(config.DESIGN_NAME))
        gds = os.path.join(self.paths["work"], "top.gds")
        page = self.open_tab("SKIPPER")
        page.entries[0].delete(0, "end")
        page.entries[0].insert(0, gds)

        from pages import gdsview
        script = gdsview.build_skipper_script(self.app, gds)
        self.assertIn("skipper -noterm -i %s" % gds, script)
        for key in ("cdsTech", "cdsDisp", "cdsLayerMap"):
            self.assertIn("-%s %s" % (key, conf[key]), script)
        self.assertIn("module load %s" % self.app.env["skipper"], script)

    def test_klayout_view_is_independent_of_the_process(self):
        from pages import gdsview
        gds = os.path.join(self.paths["work"], "top.gds")
        script = gdsview.build_klayout_script(gds)
        self.assertIn("%s %s" % (config.KLAYOUT_BIN, gds), script)
        self.assertNotIn("cdsTech", script)

    def test_view_button_launches_something(self):
        gds = os.path.join(self.paths["work"], "top.gds")
        for module in ("SKIPPER", "KLAYOUT"):
            page = self.open_tab(module)
            page.entries[0].delete(0, "end")
            page.entries[0].insert(0, gds)
            self.spawned = []
            self.widgets(page, "Button")[1].invoke()      # the first row's View
            self.app.update()
            self.assertTrue(self.spawned, "%s View launched nothing" % module)


if __name__ == "__main__":
    unittest.main()
