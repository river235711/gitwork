#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The widgets are really wired to the handlers the other tests call.

Everywhere else the tests call _on_field_change / _on_text_change directly,
because Tk only delivers key events to a window mapped on screen. That leaves
one thing unproven -- that the widgets are bound to those handlers at all -- so
it is checked here.

Delivering a real event needs a mapped window, and that is not worth it: a test
that mapped one (off the visible desktop) and generated a genuine <<Paste>> did
pass, but roughly one run in four ended with "XIO: fatal IO error on X server",
which kills the whole process and takes all 200-odd tests with it. The paste
path was verified by hand instead; what is kept here is that the bindings exist.
"""

import unittest

from harness import GuiTestCase

VERIFY_TABS = ("DRC", "LVS", "XRC")


class Bindings(GuiTestCase):
    def test_entries_react_to_typing(self):
        for module in VERIFY_TABS:
            page = self.open_tab(module)
            for key, widget in page.entries.items():
                if not hasattr(widget, "bind"):
                    continue          # BooleanVar (checkbox), handled below
                if widget.winfo_class() == "TCombobox":
                    self.assertTrue(widget.bind("<<ComboboxSelected>>"),
                                    "%s/%s has no selection handler" % (module, key))
                else:
                    self.assertTrue(widget.bind("<KeyRelease>"),
                                    "%s/%s does not react to typing" % (module, key))

    def test_command_box_reacts_to_typing(self):
        for module in VERIFY_TABS:
            page = self.open_tab(module)
            self.assertTrue(page.cmd_text.text.bind("<KeyRelease>"),
                            "%s command box does not react to typing" % module)

    def test_checkboxes_have_a_command(self):
        page = self.open_tab("XRC")
        checks = [w for w in self.widgets(page, "Checkbutton")]
        self.assertTrue(checks, "XRC has no checkboxes")
        for box in checks:
            self.assertTrue(box.cget("command"),
                            "a checkbox saves nothing when toggled")

    def test_fields_react_to_pasting_as_well_as_typing(self):
        """A middle-click paste on X11 sends no key event at all: a name deleted
        (a keystroke) and pasted back never reached the command text, which kept
        the empty one."""
        for module in VERIFY_TABS:
            page = self.open_tab(module)
            for key, widget in page.entries.items():
                if not hasattr(widget, "bind") or widget.winfo_class() == "TCombobox":
                    continue
                for sequence in ("<<Paste>>", "<ButtonRelease-2>", "<FocusOut>"):
                    self.assertTrue(widget.bind(sequence),
                                    "%s/%s ignores %s" % (module, key, sequence))

    def test_the_command_box_reacts_to_pasting_too(self):
        for module in VERIFY_TABS:
            page = self.open_tab(module)
            for sequence in ("<<Paste>>", "<ButtonRelease-2>", "<FocusOut>"):
                self.assertTrue(page.cmd_text.text.bind(sequence),
                                "%s command box ignores %s" % (module, sequence))

    def test_gds_rows_react_to_typing(self):
        for module in ("SKIPPER", "KLAYOUT"):
            page = self.open_tab(module)
            for entry in page.entries:
                self.assertTrue(entry.bind("<KeyRelease>"),
                                "%s row does not react to typing" % module)


if __name__ == "__main__":
    unittest.main()
