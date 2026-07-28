#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sandbox.py
----------
Builds a throwaway pdkgui environment so the tests never touch the real one.

Everything pdkgui reads or writes is redirected into <testing>/.sandbox:

    .sandbox/user/                  ~/.pdkgui        (PDKGUI_USER_DIR)
    .sandbox/central/               central dir      (PDKGUI_DEFAULT_DIR)
        system.txt                  design-independent revision history
        <DESIGN>/*.com, *.inc       command files + deck pointers
        <DESIGN>/SKIPPER.conf       skipper viewer paths
        <DESIGN>/DOC.txt            document index
        <DESIGN>/doc/<no>/<id>/*.pdf
    .sandbox/work/                  layouts / netlists a test can point at
    .sandbox/releases/_pdkgui/      versioned installs + "current" symlink
                                                     (PDKGUI_CURRENT_LINK)

The command files are copied from the source tree's central_example so the tests
run against the same golden content that ships with pdkgui, then a second design
is derived from it to cover "more than one process".

build() must be called before pdkgui's config is imported: config reads these
paths into module-level constants at import time.
"""

import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.join(HERE, ".sandbox")

# the design that central_example ships, and a second one derived from it
DESIGN = "t22_1p7m_4x1z1u"
DESIGN2 = "t40lp_1p6m_4x1u"

# document used by the DOC tests (must exist in central_example's DOC.txt)
DOC_NO = "DRCCommandFile"
DOC_ID = "T-N22-CL-DR-001-C1"
DOC_PDFS = ("TN22CLDR001C1_1_8a.pdf", "N22_DRC_Switch_UserGuide_V18a.pdf")

# releases used by the version-check tests
OLD_RELEASE = "2026.0720"
NEW_RELEASE = "2026.0728"


def paths():
    """Every location the tests care about."""
    central = os.path.join(SANDBOX, "central")
    releases = os.path.join(SANDBOX, "releases", "_pdkgui")
    return {
        "sandbox": SANDBOX,
        "user": os.path.join(SANDBOX, "user"),
        "central": central,
        "design": os.path.join(central, DESIGN),
        "design2": os.path.join(central, DESIGN2),
        "work": os.path.join(SANDBOX, "work"),
        "releases": releases,
        "current": os.path.join(releases, "current"),
    }


def build(src_dir):
    """Create a fresh sandbox from the pdkgui source tree; return paths()."""
    p = paths()
    shutil.rmtree(SANDBOX, ignore_errors=True)
    for key in ("user", "work"):
        os.makedirs(p[key])

    _build_central(src_dir, p)
    _build_work_files(p)
    _build_releases(p)
    return p


def env(p):
    """The environment that points pdkgui at the sandbox."""
    return {
        "PDKGUI_USER_DIR": p["user"],
        "PDKGUI_DEFAULT_DIR": p["central"],
        "PDKGUI_CURRENT_LINK": p["current"],
        # keep the DOC pdf tree inside central (its default is DEFAULT_COM_DIR)
        "PDKGUI_DOC_ROOT": p["central"],
    }


def apply_env(p):
    """Put the sandbox into os.environ (call before importing config)."""
    os.environ.update(env(p))


# --------------------------------------------------------------------------
def _build_central(src_dir, p):
    example = os.path.join(src_dir, "central_example")
    if not os.path.isdir(example):
        raise RuntimeError("central_example not found in %s" % src_dir)
    shutil.copytree(example, p["central"])

    # a second design, so per-design behaviour is actually exercised
    shutil.copytree(p["design"], p["design2"])

    # the DOC pdf tree the index points at (central_example ships only a README)
    group = os.path.join(p["design"], "doc", DOC_NO, DOC_ID)
    os.makedirs(group)
    for name in DOC_PDFS:
        _touch(os.path.join(group, name))
    _touch(os.path.join(group, "not_a_pdf.txt"))    # must be filtered out


def _build_work_files(p):
    """Layouts / netlists the verify tabs can point at."""
    for name in ("top.gds", "top.cdl",
                 "%s.lump" % DESIGN, "%s.dist" % DESIGN):
        _touch(os.path.join(p["work"], name))


def _build_releases(p):
    """Two installs behind a 'current' symlink, for the version check.

    Only the layout matters -- nothing is executed -- so the release dirs hold a
    launcher stub rather than a real build."""
    for release in (OLD_RELEASE, NEW_RELEASE):
        install = os.path.join(p["releases"], release, "pdkgui")
        os.makedirs(install)
        launcher = os.path.join(install, "pdkgui")
        with open(launcher, "w") as f:
            f.write("#!/bin/bash\n# stub launcher for tests\n")
        os.chmod(launcher, 0o755)
    _relink(p["current"], OLD_RELEASE)


def _relink(link, target):
    if os.path.islink(link) or os.path.exists(link):
        os.remove(link)
    os.symlink(target, link)


def set_current_release(release):
    """Point 'current' at a release (the version tests flip this)."""
    _relink(paths()["current"], release)


def install_dir(release):
    return os.path.join(paths()["releases"], release, "pdkgui")


def _touch(path, content=""):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
