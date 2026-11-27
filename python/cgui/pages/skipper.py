#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/skipper.py
----------------
SKIPPER page: a GDS list opened with the skipper viewer.
"""

from .gdslist import GdsListPage
from .gdsview import open_gds


class SkipperPage(GdsListPage):
    module = "SKIPPER"

    def _view(self, gds):
        open_gds(self.app, gds)
