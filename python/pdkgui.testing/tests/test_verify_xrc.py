#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The XRC tab: every option, and what each one changes.

XrcFormat / XrcUseName / XrcGround / XrcRCCorner rewrite the command text,
XrcExtType and XrcReduction shape the run script, and SourcePrimary names the
netlist files. The four central paths in XRC.inc drive the includes and seed the
Hcell/Xcell fields, which the run passes to calibre as -hcell / -xcell.
"""

import os
import unittest

import config
import sandbox
from harness import GuiTestCase
from pages.verify import _cell_name

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
        xcell = self.page.entries["Xcell"].get().strip()
        for ext_type, netlist in cases.items():
            self.set_combo(self.page, "XrcExtType", ext_type)
            self.click(self.page, "Run")
            script = self.run_script()
            self.assertIn("-xrc -pdb -turbo -turbo_all -xcell %s -%s" % (xcell, ext_type),
                          script)
            self.assertIn("-xrc -fmt -xcell %s -%s" % (xcell, ext_type), script)
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

    def test_the_frequency_limit_defaults_to_jivaros_own(self):
        self.assertEqual(self.page.entries["FrequencyLimit"].get(), "20")

    def test_the_frequency_limit_field_reaches_the_jivaro_xml(self):
        self.set_check(self.page, "XrcReduction", True)
        self.set_entry(self.page, "FrequencyLimit", "40")
        self.click(self.page, "Run")
        self.assertIn('<frequencyLimit  value="40"/>', self.jivaro_xml())

    def test_an_emptied_frequency_limit_writes_the_default(self):
        """The file has to carry a number, so a field cleared mid-edit falls
        back to jivaro's own 20 rather than writing an empty value."""
        self.set_check(self.page, "XrcReduction", True)
        self.set_entry(self.page, "FrequencyLimit", "")
        self.click(self.page, "Run")
        self.assertIn('<frequencyLimit  value="20"/>', self.jivaro_xml())

    def test_the_frequency_limit_survives_the_session(self):
        self.set_entry(self.page, "FrequencyLimit", "5")
        self.page.flush()
        self.assertEqual(self.session("XRC")["FrequencyLimit"], "5")

    # --- 7. the cell lists --------------------------------------------
    def test_the_cell_rows_sit_under_lvs_hier(self):
        """They belong to the LVS/extraction pair above them, not among the
        Xrc* options below."""
        row = {key: int(self.page.entries[key].grid_info()["row"])
               for key in ("Hcell", "Xcell", "XrcFormat")}
        # LvsHier is a BooleanVar, so go by the label naming its row
        hier = min(int(w.grid_info()["row"])
                   for w in self.widgets(self.page, "Label")
                   if w.cget("text") == "LvsHier")
        self.assertEqual(row["Hcell"], hier + 1)
        self.assertEqual(row["Xcell"], hier + 2)
        self.assertEqual(row["XrcFormat"], hier + 3)

    def test_the_cell_fields_start_at_the_central_paths(self):
        central = config.central_xrc_paths(config.DESIGN_NAME)
        self.assertEqual(self.page.entries["Hcell"].get(), central["hcell"])
        self.assertEqual(self.page.entries["Xcell"].get(), central["xcell"])

    def test_the_cell_lists_go_to_calibre_as_full_paths(self):
        """No 'ln -sf hcell/xcell' in the run folder any more: the path in the
        field is handed to calibre as it stands."""
        central = config.central_xrc_paths(config.DESIGN_NAME)
        self.click(self.page, "Run")
        script = self.run_script()
        self.assertNotIn("ln -sf", script)
        self.assertIn("-hcell %s " % central["hcell"], script)
        self.assertEqual(script.count("-xcell %s " % central["xcell"]), 2,
                         "both -xrc lines take the xcell path")

    def test_an_edited_cell_path_is_the_one_that_runs(self):
        hcell = os.path.join(self.run_folder(), "my_hcell")
        xcell = os.path.join(self.run_folder(), "my_xcell")
        self.set_entry(self.page, "Hcell", hcell)
        self.set_entry(self.page, "Xcell", xcell)
        self.click(self.page, "Run")
        script = self.run_script()
        self.assertIn("-hcell %s " % hcell, script)
        self.assertIn("-xcell %s " % xcell, script)

    def test_an_emptied_cell_field_drops_the_option(self):
        """A field cleared by hand means no list, not the central path quietly
        coming back: the run has to do what the page shows."""
        self.set_entry(self.page, "Hcell", "")
        self.set_entry(self.page, "Xcell", "")
        self.click(self.page, "Run")
        script = self.run_script()
        self.assertNotIn("-hcell", script)
        self.assertNotIn("-xcell", script)
        self.assertIn("calibre -64 -lvs -hier -turbo -turbo_all %s | tee lvs.log"
                      % self.page._com_filename(), script)
        self.assertIn("-xrc -pdb -turbo -turbo_all -c ", script)
        self.assertIn("-xrc -fmt -c ", script)

    def test_load_default_puts_the_central_cell_paths_back(self):
        """LoadDefault hands back what central says -- the command file, the
        includes, and these two paths with them."""
        central = config.central_xrc_paths(config.DESIGN_NAME)
        self.set_entry(self.page, "Hcell", "/somewhere/of/my/own")
        self.set_entry(self.page, "Xcell", "")
        self.click(self.page, "LoadDefault")
        self.assertEqual(self.page.entries["Hcell"].get(), central["hcell"])
        self.assertEqual(self.page.entries["Xcell"].get(), central["xcell"])

    def test_the_central_path_comes_back_when_the_tab_is_reopened(self):
        central = config.central_xrc_paths(config.DESIGN_NAME)
        self.set_entry(self.page, "Hcell", "")
        self.page.flush()
        self.open_tab("LVS")
        self.app._drop_cached_pages()          # force a rebuild from the session
        page = self.open_tab("XRC")
        self.assertEqual(page.entries["Hcell"].get(), central["hcell"])

    def test_a_cell_path_survives_the_session(self):
        hcell = os.path.join(self.run_folder(), "kept_hcell")
        self.set_entry(self.page, "Hcell", hcell)
        self.page.flush()
        self.assertEqual(self.session("XRC")["Hcell"], hcell)

    def test_the_cell_fields_can_be_browsed_to(self):
        path = os.path.join(self.run_folder(), "picked_hcell")
        self.browse(self.page, "Hcell", path)
        self.assertEqual(self.page.entries["Hcell"].get(), path)

    def test_lvs_hier_toggles_the_lvs_flags(self):
        central = config.central_xrc_paths(config.DESIGN_NAME)
        com = self.page._com_filename()
        self.set_check(self.page, "LvsHier", True)
        self.click(self.page, "Run")
        self.assertIn("calibre -64 -lvs -hier -turbo -turbo_all -hcell %s %s"
                      % (central["hcell"], com), self.run_script())

        # a flat LVS is given no hcell list at all
        self.set_check(self.page, "LvsHier", False)
        self.click(self.page, "Run")
        script = self.run_script()
        self.assertIn("calibre -64 -lvs %s | tee lvs.log" % com, script)
        self.assertNotIn("-hcell", script)

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

    def test_rve_reads_svdb_whatever_the_command_file_says(self):
        self.set_text(self.page, self.page.cmd_text.get_text() +
                      '\nDRC RESULTS DATABASE "other.db"\n')
        self.click(self.page, "Rve")
        self.assertIn("calibre -turbo 8 -rve -pex svdb", self.run_script())

    # --- netlist naming -----------------------------------------------
    def test_source_primary_renames_the_netlist_files(self):
        self.set_entry(self.page, "SourcePrimary", "new_top")
        for line, kind in zip(self._netlist_lines(), NETLIST_KINDS):
            self.assertIn('"new_top.%s"' % kind.lower().replace("distributed", "dist")
                          .replace("lumped", "lump"), line)

    def test_browsing_a_source_netlist_renames_them_too(self):
        """The cell name parsed from the file drives the netlist names, exactly as
        typing it into SourcePrimary does."""
        self.browse(self.page, "SourcePath",
                    os.path.join(self.paths["work"], "browsed_top.spi"))
        self.assertEqual(self.page.entries["SourcePrimary"].get(), "browsed_top")
        for line in self._netlist_lines():
            self.assertIn('"browsed_top.', line)

    def test_loading_a_file_that_names_no_cell_renames_the_netlists_too(self):
        """The name filled in on load has to reach the PEX NETLIST files, the
        same as one that is typed."""
        path = os.path.join(self.paths["work"], "unnamed.com")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.page.cmd_text.get_text().replace(
                'SOURCE PRIMARY "%s"' % self.page.entries["SourcePrimary"].get(),
                'SOURCE PRIMARY ""'))
        self.files = [path]
        self.click(self.page, "Load")

        self.assertEqual(self.page.entries["SourcePrimary"].get(),
                         _cell_name(self.page.entries["SourcePath"].get()))
        for line in self._netlist_lines():
            self.assertIn('"%s.' % self.page.entries["SourcePrimary"].get(), line)

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
