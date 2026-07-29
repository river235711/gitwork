#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The XRC tab: every option, and what each one changes.

XrcFormat / XrcUseName / XrcGround / XrcRCCorner rewrite the command text,
XrcExtType and XrcReduction shape the run script, and SourcePrimary names the
netlist files. The four central paths in XRC.inc drive the includes and the
hcell/xcell links.
"""

import os
import unittest

import config
import sandbox
from harness import GuiTestCase

NETLIST_KINDS = ("DISTRIBUTED", "LUMPED", "SIMPLE")


class XrcOptions(GuiTestCase):
    def setUp(self):
        super(XrcOptions, self).setUp()
        self.page = self.open_tab("XRC")
        self.set_entry(self.page, "RunFolder", self.run_folder())

    # --- the option lists themselves ----------------------------------
    def test_option_lists(self):
        expected = {
            "XrcFormat": ["SPECTRE", "DSPF"],
            "XrcUseName": ["SOURCE", "LAYOUT"],
            "XrcRCCorner": ["typical", "cbest", "cworst", "rcbest", "rcworst"],
            "XrcExtType": ["c", "rcc"],
        }
        for key, values in expected.items():
            self.assertEqual(list(self.page.entries[key].cget("values")), values,
                             "%s offers the wrong options" % key)

    def test_defaults(self):
        self.assertEqual(self.page.entries["XrcFormat"].get(), "SPECTRE")
        self.assertEqual(self.page.entries["XrcUseName"].get(), "SOURCE")
        self.assertEqual(self.page.entries["XrcRCCorner"].get(), "typical")
        self.assertEqual(self.page.entries["XrcExtType"].get(), "c")
        self.assertTrue(self.page.entries["LvsHier"].get(), "LvsHier should default on")
        self.assertFalse(self.page.entries["XrcReduction"].get(),
                         "XrcReduction should default off")

    # --- 1. format ----------------------------------------------------
    def test_format_applies_to_the_extracted_netlists(self):
        for value in self.page.entries["XrcFormat"].cget("values"):
            self.set_combo(self.page, "XrcFormat", value)
            for line in self._netlist_lines():
                if "SIMPLE" in line:
                    continue
                self.assertEqual(self._token(line, 0), value,
                                 "format not applied: %s" % line)

    def test_the_simple_netlist_keeps_its_format(self):
        """XrcFormat picks the format of the extracted netlists; the simple one
        stays SPECTRE."""
        before = [ln for ln in self._netlist_lines() if "SIMPLE" in ln][0]
        self.assertEqual(self._token(before, 0), "SPECTRE")

        self.set_combo(self.page, "XrcFormat", "DSPF")
        after = [ln for ln in self._netlist_lines() if "SIMPLE" in ln][0]
        self.assertEqual(after, before, "the SIMPLE line was rewritten")

    # --- 2. use name --------------------------------------------------
    def test_use_name_rewrites_all_three_netlist_lines(self):
        for value in self.page.entries["XrcUseName"].cget("values"):
            self.set_combo(self.page, "XrcUseName", value)
            for line in self._netlist_lines():
                self.assertEqual(self._token(line, 1), value,
                                 "use name not applied: %s" % line)

    def test_format_and_use_name_are_independent(self):
        self.set_combo(self.page, "XrcFormat", "DSPF")
        self.set_combo(self.page, "XrcUseName", "LAYOUT")
        for line in self._netlist_lines():
            # the format skips SIMPLE, the use name does not
            self.assertEqual(self._token(line, 0),
                             "SPECTRE" if "SIMPLE" in line else "DSPF")
            self.assertEqual(self._token(line, 1), "LAYOUT")

    # --- 3. ground ----------------------------------------------------
    def test_ground_changes_only_the_lines_that_have_one(self):
        self.set_entry(self.page, "XrcGround", "AVSS")
        for line in self._netlist_lines():
            if "SIMPLE" in line:
                self.assertNotIn("GROUND", line,
                                 "a GROUND clause was invented on the SIMPLE line")
            else:
                self.assertIn("GROUND AVSS", line)

    def test_empty_ground_leaves_the_text_alone(self):
        self.set_entry(self.page, "XrcGround", "AVSS")
        before = self.page.cmd_text.get_text()
        self.set_entry(self.page, "XrcGround", "")
        self.assertEqual(self.page.cmd_text.get_text(), before)

    # --- 4. rc corner -------------------------------------------------
    def test_every_corner_rewrites_the_rules_include(self):
        rules = config.central_xrc_paths(config.DESIGN_NAME)["rules"]
        for corner in self.page.entries["XrcRCCorner"].cget("values"):
            self.set_combo(self.page, "XrcRCCorner", corner)
            includes = self.active_lines(self.page.cmd_text.get_text(), "/rules")
            self.assertEqual(len(includes), 1, "expected exactly one rules include")
            self.assertEqual(includes[0].strip(),
                             "include %s/%s/rules" % (rules, corner))

    def test_the_deck_include_is_the_one_from_central(self):
        deck = config.central_xrc_paths(config.DESIGN_NAME)["deck"]
        includes = self.active_lines(self.page.cmd_text.get_text(), "include")
        self.assertIn("include %s" % deck, [ln.strip() for ln in includes])

    # --- 5. extraction type -------------------------------------------
    def test_extraction_type_drives_the_calibre_flags_and_cleanup(self):
        cases = {"c": "lump", "rcc": "dist"}
        base = self.page.entries["SourcePrimary"].get().strip()
        for ext_type, netlist in cases.items():
            self.set_combo(self.page, "XrcExtType", ext_type)
            self.click(self.page, "Run")
            script = self.run_script()
            self.assertIn("-xrc -pdb -turbo -turbo_all -xcell xcell -%s" % ext_type,
                          script)
            self.assertIn("-xrc -fmt -xcell xcell -%s" % ext_type, script)
            self.assertIn("rm -rf lvs.log pdb.log fmt.log %s.%s*" % (base, netlist),
                          script)

    # --- 6. reduction -------------------------------------------------
    def test_reduction_off_leaves_jivaro_out(self):
        self.set_check(self.page, "XrcReduction", False)
        self.click(self.page, "Run")
        self.assertNotIn("jivaro -xml", self.run_script())
        self.assertFalse(os.path.exists(os.path.join(self.run_folder(), "jivaro.xml")))

    def test_reduction_on_adds_jivaro_and_writes_its_xml(self):
        base = self.page.entries["SourcePrimary"].get().strip()
        for ext_type, netlist in (("c", "lump"), ("rcc", "dist")):
            self.set_combo(self.page, "XrcExtType", ext_type)
            self.set_check(self.page, "XrcReduction", True)
            self.click(self.page, "Run")

            self.assertIn("jivaro -xml jivaro.xml", self.run_script())
            xml = self.jivaro_xml()
            self.assertIn('<inputFile value="%s.%s"/>' % (base, netlist), xml)
            self.assertIn('<outputFile value="./%s.red.%s"/>' % (base, netlist), xml)

    # --- 7. central files ---------------------------------------------
    def test_hcell_and_xcell_are_linked_from_central(self):
        central = config.central_xrc_paths(config.DESIGN_NAME)
        self.click(self.page, "Run")
        script = self.run_script()
        self.assertIn("ln -sf %s;" % central["hcell"], script)
        self.assertIn("ln -sf %s;" % central["xcell"], script)

    def test_lvs_hier_toggles_the_lvs_flags(self):
        self.set_check(self.page, "LvsHier", True)
        self.click(self.page, "Run")
        self.assertIn("calibre -64 -lvs -hier -turbo -turbo_all -hcell hcell",
                      self.run_script())

        self.set_check(self.page, "LvsHier", False)
        self.click(self.page, "Run")
        self.assertIn("calibre -64 -lvs -hcell hcell", self.run_script())

    # --- the optional DFM export --------------------------------------
    def test_no_dfm_export_when_the_process_does_not_need_one(self):
        self.click(self.page, "Run")
        script = self.run_script()
        self.assertNotIn("TSMC_CAL_DFM_PATH", script)
        # the module loads are still followed by a blank line
        self.assertEqual(script.splitlines()[3], "")

    def test_dfm_export_follows_the_module_loads_when_central_sets_it(self):
        self.set_design(sandbox.DESIGN2)
        page = self.open_tab("XRC")
        self.set_entry(page, "RunFolder", self.run_folder())
        self.click(page, "Run")

        lines = self.run_script().splitlines()
        self.assertEqual(lines[3], "export TSMC_CAL_DFM_PATH=%s" % sandbox.DFM_PATH,
                         "the export is not on the line after the module loads")
        self.assertTrue(lines[1].startswith("module load"))
        self.assertTrue(lines[2].startswith("module load"))
        self.assertTrue(lines[4].startswith("rm -rf"))

    # --- rve ----------------------------------------------------------
    def test_rve_opens_the_pex_view_of_the_svdb(self):
        self.click(self.page, "Rve")
        script = self.run_script()
        self.assertIn("calibre -turbo 8 -rve -pex svdb", script)
        self.assertIn("module load %s" % self.app.env["calibre"], script)

    # --- netlist naming -----------------------------------------------
    def test_source_primary_renames_the_netlist_files(self):
        self.set_entry(self.page, "SourcePrimary", "new_top")
        for line, kind in zip(self._netlist_lines(), NETLIST_KINDS):
            self.assertIn('"new_top.%s"' % kind.lower().replace("distributed", "dist")
                          .replace("lumped", "lump"), line)

    def test_editing_source_primary_in_the_text_renames_them_too(self):
        text = self.page.cmd_text.get_text().replace(
            'SOURCE PRIMARY "%s"' % self.page.entries["SourcePrimary"].get(),
            'SOURCE PRIMARY "typed_top"')
        self.set_text(self.page, text)
        self.assertEqual(self.page.entries["SourcePrimary"].get(), "typed_top")
        for line in self._netlist_lines():
            self.assertIn('"typed_top.', line)

    # ------------------------------------------------------------------
    def _netlist_lines(self):
        lines = self.active_lines(self.page.cmd_text.get_text(), "PEX NETLIST")
        self.assertEqual(len(lines), 3, "expected three PEX NETLIST lines")
        return lines

    @staticmethod
    def _token(line, index):
        """Token after the quoted file name: 0 = format, 1 = use name."""
        after = line.split('"')[2].split()
        return after[index]


if __name__ == "__main__":
    unittest.main()
