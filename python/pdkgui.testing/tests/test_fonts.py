#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fonts: the same size and the same family on every machine.

Two things used to differ per host. The family was named "Arial", which is not
installed on these hosts -- and Tk substitutes something silently rather than
complaining, so what appeared depended on what that host happened to have. The
size was in points, which Tk multiplies by the X server's scaling, so the same
number came out 14 px on one display and 27 on another.
"""

import os
import unittest

import tkinter as tk
from tkinter import font as tkfont

import config
from harness import GuiTestCase


class PickFamily(GuiTestCase):
    """config._pick_family, against the fonts this machine really has."""

    def setUp(self):
        super(PickFamily, self).setUp()
        config.clear_font_cache()
        self.addCleanup(config.clear_font_cache)
        self.installed = set(tkfont.families())

    def test_it_takes_the_first_candidate_that_is_installed(self):
        present = sorted(self.installed)[0]
        self.assertEqual(
            config._pick_family(("NoSuchFontA", "NoSuchFontB", present)), present)

    def test_it_prefers_the_earlier_candidate(self):
        two = sorted(self.installed)[:2]
        if len(two) < 2:
            self.skipTest("only one font family on this machine")
        self.assertEqual(config._pick_family(tuple(two)), two[0])

    def test_none_of_them_installed_leaves_the_choice_to_tk(self):
        """Naming a font that is not there is what caused this; None at least
        does not pretend."""
        self.assertIsNone(config._pick_family(("NoSuchFontA", "NoSuchFontB")))

    def test_an_override_is_taken_as_given(self):
        """Someone asking for a particular font gets it, installed or not."""
        self.assertEqual(config._pick_family(("DejaVu Sans",), "Whatever I Say"),
                         "Whatever I Say")

    def test_the_shipped_candidates_are_real_fonts_somewhere(self):
        """Not a typo check on this machine -- just that the lists are not empty
        and end in the Windows names they used to be."""
        self.assertGreaterEqual(len(config.UI_FONT_CANDIDATES), 3)
        self.assertGreaterEqual(len(config.MONO_FONT_CANDIDATES), 3)
        self.assertEqual(config.UI_FONT_CANDIDATES[0], "Liberation Sans")
        self.assertEqual(config.MONO_FONT_CANDIDATES[0], "Liberation Mono")


class FontSize(GuiTestCase):
    def setUp(self):
        super(FontSize, self).setUp()
        config.clear_font_cache()
        self.addCleanup(config.clear_font_cache)

    def test_the_size_is_in_pixels(self):
        """Negative means pixels to Tk. A positive size is points, which is the
        one the display scaling multiplies."""
        self.assertLess(config.ui_font()[1], 0)
        self.assertLess(config.mono_font()[1], 0)

    def test_delta_still_shifts_the_size(self):
        base = abs(config.ui_font()[1])
        self.assertEqual(abs(config.ui_font(1)[1]), base + 1)
        self.assertEqual(abs(config.ui_font(-1)[1]), base - 1)
        self.assertEqual(abs(config.mono_font(2)[1]), base + 2)

    def test_a_weight_comes_last(self):
        spec = config.ui_font(0, "bold")
        self.assertEqual(len(spec), 3)
        self.assertEqual(spec[2], "bold")

    def test_the_size_does_not_shrink_below_something_readable(self):
        self.assertGreaterEqual(abs(config.ui_font(-50)[1]), 8)

    def test_the_same_size_renders_the_same_at_any_display_scaling(self):
        """The whole point: one machine at 96 dpi and another at 144 must show
        the same thing."""
        spec = config.ui_font()
        heights = self._at_each_scaling(family=spec[0] or "", size=spec[1])
        self.assertEqual(len(heights), 1,
                         "the size follows the display scaling: %s" % heights)

    def test_points_would_not_have_been_the_same(self):
        """Why the change was needed, rather than an assumption about Tk."""
        self.assertGreater(len(self._at_each_scaling(size=11)), 1)

    def _at_each_scaling(self, **font):
        """Rendered line heights at three display scalings.

        The scaling is put back here rather than through addCleanup, which runs
        after tearDown has destroyed the window."""
        original = self.app.tk.call("tk", "scaling")
        try:
            heights = set()
            for scaling in (1.0, 1.333, 2.0):
                self.app.tk.call("tk", "scaling", scaling)
                heights.add(
                    tkfont.Font(root=self.app, **font).metrics("linespace"))
            return heights
        finally:
            self.app.tk.call("tk", "scaling", original)


class Overrides(GuiTestCase):
    def setUp(self):
        super(Overrides, self).setUp()
        config.clear_font_cache()
        self.addCleanup(config.clear_font_cache)

    def test_the_family_can_be_forced(self):
        os.environ["PDKGUI_FONT_FAMILY"] = "DejaVu Serif"
        os.environ["PDKGUI_MONO_FAMILY"] = "DejaVu Sans Mono"
        self.addCleanup(os.environ.pop, "PDKGUI_FONT_FAMILY", None)
        self.addCleanup(os.environ.pop, "PDKGUI_MONO_FAMILY", None)
        config.clear_font_cache()

        self.assertEqual(config.ui_font()[0], "DejaVu Serif")
        self.assertEqual(config.mono_font()[0], "DejaVu Sans Mono")

    def test_the_older_point_size_setting_still_works(self):
        """Someone may already have PDKGUI_FONT_SIZE in their profile."""
        self.assertIsNone(config.UI_FONT_POINTS, "the default is pixels")
        original = config.UI_FONT_POINTS
        config.UI_FONT_POINTS = 13
        self.addCleanup(setattr, config, "UI_FONT_POINTS", original)
        self.assertEqual(config.ui_font()[1], 13, "points are positive")

    def test_the_window_grows_with_the_font(self):
        original = config.UI_FONT_PX
        self.addCleanup(setattr, config, "UI_FONT_PX", original)

        config.UI_FONT_PX = config.UI_FONT_BASE_PX
        small = config.window_geometry()
        config.UI_FONT_PX = config.UI_FONT_BASE_PX * 2
        big = config.window_geometry()

        self.assertEqual(small, "%dx%d" % (config.WINDOW_W, config.WINDOW_H))
        self.assertEqual(big, "%dx%d" % (config.WINDOW_W * 2, config.WINDOW_H * 2))


class FontReport(GuiTestCase):
    def test_the_system_tab_says_what_was_resolved(self):
        """So "this machine looks different" can be answered by looking."""
        config.clear_font_cache()
        self.addCleanup(config.clear_font_cache)
        report = config.font_report()
        self.assertIn(config.ui_font()[0], report)
        self.assertIn(config.mono_font()[0], report)
        self.assertIn("px", report)

        page = self.open_tab("SYSTEM")
        self.assertTrue(any(text.startswith("Fonts: ")
                            for text in self.labels(page)),
                        "the SYSTEM tab does not show the fonts")


if __name__ == "__main__":
    unittest.main()
