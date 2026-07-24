#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/klayout.py
----------------
KLAYOUT page: a GDS list opened with klayout (same UI as SKIPPER, but View runs
klayout instead of skipper). Independent of the PROCESS selection.
"""

from .gdslist import GdsListPage
from .gdsview import open_gds_klayout


class KlayoutPage(GdsListPage):
    module = "KLAYOUT"

    def _view(self, gds):
        open_gds_klayout(self.app, gds)
