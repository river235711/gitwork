#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROCESS and ENV tabs: every selectable option, and that it is remembered."""

import unittest

import config
from harness import GuiTestCase


class ProcessTab(GuiTestCase):
    def test_lists_the_configured_designs(self):
        page = self.open_tab("PROCESS")
        combo = self.widgets(page, "TCombobox")[0]
        listed = list(combo.cget("values"))
        self.assertEqual(listed, config.read_lines(config.page_file("PROCESS")))
        self.assertIn(config.DESIGN_NAME, listed)

    def test_every_design_can_be_selected_and_is_remembered(self):
        page = self.open_tab("PROCESS")
        combo = self.widgets(page, "TCombobox")[0]
        for design in combo.cget("values"):
            combo.set(design)
            combo.event_generate("<<ComboboxSelected>>")
            self.app.update()

            self.assertEqual(config.DESIGN_NAME, design)
            self.assertIn(design, self.app.title())
            saved = config.load_json(config.user_global_file("PROCESS"))
            self.assertEqual(saved.get("design"), design)

    def test_the_title_names_the_design_and_the_host(self):
        host = config.hostname()
        self.assertTrue(host, "no host name to show")
        self.assertEqual(self.app.title(),
                         "pdkgui - %s (on %s)" % (config.DESIGN_NAME, host))

    def test_the_title_follows_the_selected_design(self):
        page = self.open_tab("PROCESS")
        combo = self.widgets(page, "TCombobox")[0]
        for design in combo.cget("values"):
            combo.set(design)
            combo.event_generate("<<ComboboxSelected>>")
            self.app.update()
            self.assertEqual(self.app.title(),
                             "pdkgui - %s (on %s)" % (design, config.hostname()))

    def test_the_title_names_the_release_when_there_is_one(self):
        """Running from a release directory, the title carries its version."""
        import sandbox
        config.BASE_DIR = sandbox.install_dir(sandbox.OLD_RELEASE)
        sandbox.set_current_release(sandbox.OLD_RELEASE)
        self.assertEqual(
            config.window_title(),
            "pdkgui v%s - %s (on %s)" % (sandbox.OLD_RELEASE, config.DESIGN_NAME,
                                         config.hostname()))

    def test_the_title_leaves_out_a_release_it_cannot_name(self):
        """A source checkout is not a release, so no version is claimed."""
        self.assertIsNone(config.running_release())
        self.assertNotIn(" v", self.app.title())

    def test_design_choice_survives_a_restart(self):
        page = self.open_tab("PROCESS")
        combo = self.widgets(page, "TCombobox")[0]
        other = [d for d in combo.cget("values") if d != config.DESIGN_NAME]
        if not other:
            self.skipTest("only one design configured")
        combo.set(other[0])
        combo.event_generate("<<ComboboxSelected>>")
        self.app.update()

        self.app.destroy()
        self.app = self.pdkgui_app.PdkGui()
        self.app.withdraw()
        self.assertEqual(config.DESIGN_NAME, other[0])


class EnvTab(GuiTestCase):
    def test_every_tool_offers_its_configured_versions(self):
        page = self.open_tab("ENV")
        parsed = page._parse(config.page_file("ENV"))
        self.assertTrue(parsed, "env.txt produced no tools")
        for tool, info in parsed.items():
            combo = page.combos[tool]
            self.assertEqual(list(combo.cget("values")), info["values"],
                             "%s options differ from env.txt" % tool)
            self.assertEqual(combo.get(), info["default"],
                             "%s did not start on its default" % tool)

    def test_selecting_each_version_updates_the_shared_env(self):
        page = self.open_tab("ENV")
        for tool, combo in page.combos.items():
            for value in combo.cget("values"):
                combo.set(value)
                combo.event_generate("<<ComboboxSelected>>")
                self.app.update()
                self.assertEqual(self.app.env[tool], value)

        saved = config.load_json(config.user_global_file("ENV"))
        for tool, combo in page.combos.items():
            self.assertEqual(saved.get(tool), combo.get())

    def test_chosen_versions_reach_the_run_script(self):
        """What ENV selects is what `module load` gets on a verify tab."""
        page = self.open_tab("ENV")
        calibre_versions = list(page.combos["calibre"].cget("values"))
        pick = calibre_versions[-1]
        page.combos["calibre"].set(pick)
        page.combos["calibre"].event_generate("<<ComboboxSelected>>")
        self.app.update()

        drc = self.open_tab("DRC")
        self.set_entry(drc, "RunFolder", self.run_folder())
        self.click(drc, "Run")
        self.assertIn("module load %s" % pick, self.run_script())


if __name__ == "__main__":
    unittest.main()
