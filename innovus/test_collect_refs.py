#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for collect_refs.py -- self-contained fixture, no design data needed.

    python3 innovus/test_collect_refs.py
"""

import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect_refs  # noqa: E402


GLOBALS = """\
###########################################################
# Version 1.1
#
set ::MSV::designHasPGPin 1
set conf_qxconf_file {NULL}
set defHierChar {/}
set extract_shrink_factor 0.855
set init_lef_file {../ref/PRTF_Innovus_22nm.tlef ../ref/std/tcbn22.lef}
set init_mmmc_file {../script/viewdefinition.tcl}
set init_verilog {../ref/WF_6T7R_A_DIE.vg.will}
set init_pwr_net {DVDD08}
#set init_gnd_net {../ref/commented_out.lef}
"""

VIEWDEF = """\
create_library_set -name lib_wcl_tt0p8v\\
   -timing\\
    [list ../ref/io/dblib/tphn22_m40c.lib\\
     ../ref/std/dblib/tcbn22_m40c.lib]\\
   -aocv ../ref/std/dblib/tcbn22_setup.aocvm
create_rc_corner -name rcworst_125c\\
   -T 125\\
   -qx_tech_file ../ref/QRC/RC_QRC_rcworst.tar.gz_FILE/qrcTechFile
set qrc_dir {../ref/QRC/RC_QRC_rcworst.tar.gz_FILE}
create_constraint_mode -name func\\
   -sdc_files\\
    [list ../ref/WF_6T7R_A_DIE_pt.sdc.0731]
"""

SDC = """\
#-----------------------
# Timing exception
#-----------------------
#set_max_delay 3 -from [get_ports PAD_CHIP_EN]

#### Analog Interface
source da_max_delay.sdc
"""

FILES = {
    "run1/sylincom_top_0803.globals": GLOBALS,
    "script/viewdefinition.tcl": VIEWDEF,
    "ref/PRTF_Innovus_22nm.tlef": "# tlef\n",
    "ref/std/tcbn22.lef": "# lef\n",
    "ref/std/dblib/tcbn22_m40c.lib": "/* lib */\n",
    "ref/std/dblib/tcbn22_setup.aocvm": "# aocv\n",
    "ref/io/dblib/tphn22_m40c.lib": "/* io lib */\n",
    "ref/WF_6T7R_A_DIE.vg.will": "module top; endmodule\n",
    "ref/WF_6T7R_A_DIE_pt.sdc.0731": SDC,
    "ref/da_max_delay.sdc": "set_max_delay 1 -from [get_ports A]\n",
    "ref/commented_out.lef": "# never referenced for real\n",
    "ref/QRC/RC_QRC_rcworst.tar.gz_FILE/qrcTechFile": "# qrc tech\n",
    "ref/QRC/RC_QRC_rcworst.tar.gz_FILE/extra.dat": "# side car\n",
}


def write(path, text):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "w") as fh:
        fh.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="collect_refs_")
        self.proj = os.path.join(self.tmp, "proj")
        for rel, text in FILES.items():
            write(os.path.join(self.proj, rel), text)
        self.inp = os.path.join(self.proj, "run1",
                                "sylincom_top_0803.globals")
        self.out_root = os.path.join(self.tmp, "xxx")
        self.out = os.path.join(self.out_root, "run1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, *extra):
        argv = [self.inp, self.out] + list(extra)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = collect_refs.main(argv)
        return code, out.getvalue(), err.getvalue()

    def collected(self, rel):
        """Path under the output root, i.e. what ../<rel> maps to."""
        return os.path.join(self.out_root, rel)

    def assertCollected(self, rel, src_rel=None):
        dest = self.collected(rel)
        self.assertTrue(os.path.isfile(dest), "not collected: %s" % rel)
        with open(os.path.join(self.proj, src_rel or rel)) as fh:
            want = fh.read()
        with open(dest) as fh:
            self.assertEqual(want, fh.read(), "content differs: %s" % rel)

    def manifest(self):
        with open(os.path.join(self.out, collect_refs.MANIFEST_NAME)) as fh:
            return fh.read()


class TestHierarchy(Base):
    def test_full_hierarchy_is_collected(self):
        code, _, _ = self.run_tool()
        self.assertEqual(0, code)
        # level 1: the input file itself
        self.assertCollected("run1/sylincom_top_0803.globals")
        # level 2: refs named in the .globals
        self.assertCollected("ref/PRTF_Innovus_22nm.tlef")
        self.assertCollected("ref/std/tcbn22.lef")
        self.assertCollected("ref/WF_6T7R_A_DIE.vg.will")
        self.assertCollected("script/viewdefinition.tcl")
        # level 3: refs named in viewdefinition.tcl
        self.assertCollected("ref/io/dblib/tphn22_m40c.lib")
        self.assertCollected("ref/std/dblib/tcbn22_m40c.lib")
        self.assertCollected("ref/std/dblib/tcbn22_setup.aocvm")
        self.assertCollected("ref/QRC/RC_QRC_rcworst.tar.gz_FILE/qrcTechFile")
        self.assertCollected("ref/WF_6T7R_A_DIE_pt.sdc.0731")

    def test_bare_filename_sourced_from_sibling_dir(self):
        # `source da_max_delay.sdc` inside ref/WF_..._pt.sdc.0731 has no path,
        # it must resolve against the directory of the file that sources it.
        self.run_tool()
        self.assertCollected("ref/da_max_delay.sdc")

    def test_directory_reference_is_copied_whole(self):
        self.run_tool()
        self.assertCollected("ref/QRC/RC_QRC_rcworst.tar.gz_FILE/extra.dat")
        self.assertIn("DIR ", self.manifest())

    def test_unreferenced_file_is_not_copied(self):
        self.run_tool()
        self.assertFalse(os.path.exists(self.collected("ref/commented_out.lef")),
                         "a commented-out reference must not be collected")

    def test_manifest_lists_every_copy(self):
        self.run_tool()
        text = self.manifest()
        self.assertIn("PRTF_Innovus_22nm.tlef", text)
        self.assertIn("da_max_delay.sdc", text)


class TestReporting(Base):
    def test_missing_declared_reference(self):
        write(os.path.join(self.proj, "ref", "WF_6T7R_A_DIE_pt.sdc.0731"),
              SDC + "source nope.sdc\n")
        code, _, err = self.run_tool()
        self.assertEqual(1, code, "missing refs must set a non-zero exit code")
        self.assertIn("nope.sdc", self.manifest())
        self.assertIn("MISSING", err)

    def test_missing_reference_without_a_keyword(self):
        # -timing [list ...] has no directive word in front of it, but an
        # unfindable .lib there must still be reported, not dropped silently
        write(os.path.join(self.proj, "script", "viewdefinition.tcl"),
              VIEWDEF.replace("../ref/std/dblib/tcbn22_m40c.lib",
                              "../ref/std/dblib/gone.lib"))
        code, _, err = self.run_tool()
        self.assertEqual(1, code)
        self.assertIn("gone.lib", self.manifest())
        self.assertIn("MISSING", err)

    def test_design_objects_are_not_reported_as_missing(self):
        write(self.inp, GLOBALS + """\
set_max_delay 3 -from [get_cells u_iq_logger/u_iq_logger_rg/rg_mode_reg*]
set_clock_groups -asynchronous -group [get_clocks {CLK_A CLK_B}]
""")
        code, _, _ = self.run_tool()
        self.assertEqual(0, code)
        self.assertNotIn("MISSING", self.manifest())

    def test_external_reference_is_skipped(self):
        outside = os.path.join(self.tmp, "outside", "vendor.lib")
        write(outside, "/* vendor */\n")
        write(self.inp, GLOBALS + "set outside_file {%s}\n" % outside)
        code, _, _ = self.run_tool()
        self.assertEqual(0, code)
        self.assertIn("EXTERNAL", self.manifest())
        self.assertFalse(os.path.exists(os.path.join(self.out_root,
                                                     "_external")))
        # nothing may be written above the output root
        for entry in os.listdir(self.tmp):
            self.assertIn(entry, ("proj", "xxx", "outside"))

    def test_external_copy_mode(self):
        outside = os.path.join(self.tmp, "outside", "vendor.lib")
        write(outside, "/* vendor */\n")
        write(self.inp, GLOBALS + "set outside_file {%s}\n" % outside)
        self.run_tool("--external", "copy")
        dest = os.path.join(self.out, "_external", outside.lstrip("/"))
        self.assertTrue(os.path.isfile(dest), "not copied: %s" % dest)

    def test_unresolved_variable_is_reported(self):
        write(self.inp, GLOBALS + "set spef_file {$NO_SUCH_VAR/x.spef}\n")
        self.run_tool()
        self.assertIn("UNRESOLVED_VAR", self.manifest())


class TestPatterns(Base):
    def test_verilog_include(self):
        write(os.path.join(self.proj, "ref", "WF_6T7R_A_DIE.vg.will"),
              '`include "defines.vh"\nmodule top; endmodule\n')
        write(os.path.join(self.proj, "ref", "defines.vh"), "`define X 1\n")
        code, _, _ = self.run_tool()
        self.assertEqual(0, code)
        self.assertCollected("ref/defines.vh")

    def test_whole_dir_pulls_in_siblings(self):
        # drop the line that references the QRC directory itself, so only the
        # file .../RC_QRC_rcworst.tar.gz_FILE/qrcTechFile is referenced
        no_dir_ref = VIEWDEF.replace(
            "set qrc_dir {../ref/QRC/RC_QRC_rcworst.tar.gz_FILE}\n", "")
        self.assertNotIn("qrc_dir", no_dir_ref)
        write(os.path.join(self.proj, "script", "viewdefinition.tcl"),
              no_dir_ref)
        sibling = "ref/QRC/RC_QRC_rcworst.tar.gz_FILE/extra.dat"

        self.run_tool()
        self.assertFalse(os.path.exists(self.collected(sibling)),
                         "sibling must not come along by default")

        shutil.rmtree(self.out_root)
        self.run_tool("--whole-dir", "*_FILE")
        self.assertCollected(sibling)

    def test_wildcard_reference_expands(self):
        write(self.inp, GLOBALS + "set spef_file {../ref/spef/*.spef}\n")
        for name in ("a.spef", "b.spef"):
            write(os.path.join(self.proj, "ref", "spef", name), "# %s\n" % name)
        self.run_tool()
        self.assertCollected("ref/spef/a.spef")
        self.assertCollected("ref/spef/b.spef")


class TestSymlinks(Base):
    """EDA trees are full of symlinks (ref -> /proj/.../ref).  Paths must be
    mapped as written, not as resolved, or everything behind the link lands
    outside the tree and is dropped as EXTERNAL."""

    def link_ref_dir(self):
        real = os.path.join(self.tmp, "elsewhere", "ref")
        shutil.move(os.path.join(self.proj, "ref"), real)
        os.symlink(real, os.path.join(self.proj, "ref"))

    def test_symlinked_ref_dir_is_still_internal(self):
        self.link_ref_dir()
        code, _, _ = self.run_tool()
        self.assertEqual(0, code)
        self.assertNotIn("EXTERNAL", self.manifest())
        self.assertCollected("ref/PRTF_Innovus_22nm.tlef")
        self.assertCollected("ref/io/dblib/tphn22_m40c.lib")

    def test_descends_through_a_symlinked_dir(self):
        self.link_ref_dir()
        self.run_tool()
        # ref/WF_..._pt.sdc.0731 lives behind the link and sources a sibling
        self.assertCollected("ref/da_max_delay.sdc")

    def test_symlinked_input_path_is_kept(self):
        os.symlink(self.proj, os.path.join(self.tmp, "proj_link"))
        self.inp = os.path.join(self.tmp, "proj_link", "run1",
                                "sylincom_top_0803.globals")
        code, _, _ = self.run_tool()
        self.assertEqual(0, code)
        self.assertCollected("ref/PRTF_Innovus_22nm.tlef")

    def test_whole_dir_descends_into_a_linked_subdir(self):
        qrc = os.path.join(self.proj, "ref", "QRC",
                           "RC_QRC_rcworst.tar.gz_FILE")
        target = os.path.join(self.tmp, "elsewhere", "icecaps")
        write(os.path.join(target, "cap.dat"), "# caps\n")
        os.symlink(target, os.path.join(qrc, "icecaps"))
        self.run_tool("--whole-dir", "*_FILE")
        self.assertCollected(
            "ref/QRC/RC_QRC_rcworst.tar.gz_FILE/icecaps/cap.dat",
            src_rel=os.path.relpath(os.path.join(target, "cap.dat"),
                                    self.proj))

    def test_directory_link_loop_terminates(self):
        qrc = os.path.join(self.proj, "ref", "QRC",
                           "RC_QRC_rcworst.tar.gz_FILE")
        os.symlink(qrc, os.path.join(qrc, "self"))
        code, _, _ = self.run_tool("--whole-dir", "*_FILE")
        self.assertEqual(0, code)
        self.assertCollected("ref/QRC/RC_QRC_rcworst.tar.gz_FILE/extra.dat")

    def test_keep_links_links_the_whole_tree_behind_it(self):
        self.link_ref_dir()
        code, out, _ = self.run_tool("--keep-links")
        self.assertEqual(0, code)
        link = self.collected("ref")
        self.assertTrue(os.path.islink(link), "ref/ must be a symlink")
        self.assertEqual(os.path.join(self.tmp, "elsewhere", "ref"),
                         os.path.realpath(link))
        self.assertIn("links kept", out)
        self.assertIn("LINK ", self.manifest())
        # nothing was copied behind the link ...
        self.assertNotIn("xxx/ref/", self.manifest())
        # ... yet every reference still reads back through it
        self.assertCollected("ref/io/dblib/tphn22_m40c.lib")
        self.assertCollected("ref/da_max_delay.sdc")
        # and files outside the link are copied as usual
        self.assertFalse(os.path.islink(self.collected("script")))
        self.assertCollected("script/viewdefinition.tcl")

    def test_keep_links_never_writes_through_a_link(self):
        self.link_ref_dir()
        self.run_tool("--keep-links")
        # the originals behind the link must be untouched
        real = os.path.join(self.tmp, "elsewhere", "ref")
        self.assertEqual(sorted(os.listdir(real)),
                         sorted(os.listdir(os.path.join(self.proj, "ref"))))
        self.assertFalse(os.path.exists(os.path.join(real, "collect_refs.manifest")))

    def test_keep_links_on_a_linked_file(self):
        target = os.path.join(self.tmp, "elsewhere", "real.tlef")
        write(target, "# real tlef\n")
        link = os.path.join(self.proj, "ref", "PRTF_Innovus_22nm.tlef")
        os.remove(link)
        os.symlink(target, link)
        self.run_tool("--keep-links")
        dest = self.collected("ref/PRTF_Innovus_22nm.tlef")
        self.assertTrue(os.path.islink(dest))
        self.assertEqual(target, os.path.realpath(dest))

    def test_keep_links_is_idempotent(self):
        self.link_ref_dir()
        self.run_tool("--keep-links")
        code, _, err = self.run_tool("--keep-links")
        self.assertEqual(0, code)
        self.assertNotIn("warning", err)
        self.assertTrue(os.path.islink(self.collected("ref")))

    def test_keep_links_falls_back_when_a_real_dir_is_there(self):
        self.link_ref_dir()
        self.run_tool()                      # materialise first
        code, _, err = self.run_tool("--keep-links")
        self.assertEqual(0, code)
        self.assertIn("exists as a real path", err)
        self.assertFalse(os.path.islink(self.collected("ref")))
        self.assertCollected("ref/io/dblib/tphn22_m40c.lib")

    def test_symlinked_file_is_copied_as_a_real_file(self):
        target = os.path.join(self.tmp, "elsewhere", "real.tlef")
        write(target, "# real tlef\n")
        link = os.path.join(self.proj, "ref", "PRTF_Innovus_22nm.tlef")
        os.remove(link)
        os.symlink(target, link)
        self.run_tool()
        dest = self.collected("ref/PRTF_Innovus_22nm.tlef")
        self.assertFalse(os.path.islink(dest), "must be copied, not linked")
        with open(dest) as fh:
            self.assertEqual("# real tlef\n", fh.read())


class TestSafety(Base):
    def test_source_cycle_terminates(self):
        write(os.path.join(self.proj, "script", "a.tcl"), "source b.tcl\n")
        write(os.path.join(self.proj, "script", "b.tcl"), "source a.tcl\n")
        write(self.inp, GLOBALS + "set extra_file {../script/a.tcl}\n")
        code, _, _ = self.run_tool()
        self.assertEqual(0, code)
        self.assertCollected("script/a.tcl")
        self.assertCollected("script/b.tcl")

    def test_root_and_ancestor_tokens_are_ignored(self):
        # `set defHierChar {/}` must never drag in the filesystem root
        self.run_tool()
        text = self.manifest()
        self.assertNotIn("DIR       /  ", text)
        self.assertNotIn("  ->  %s/\n" % self.out_root, text)

    def test_dry_run_writes_nothing(self):
        code, out, _ = self.run_tool("-n")
        self.assertEqual(0, code)
        self.assertIn("dry-run", out)
        self.assertFalse(os.path.exists(self.out_root))

    def test_rerun_is_idempotent(self):
        self.run_tool()
        before = sorted(os.walk(self.out_root))
        code, _, err = self.run_tool()
        self.assertEqual(0, code)
        self.assertNotIn("warning", err)
        self.assertEqual(before, sorted(os.walk(self.out_root)))

    def test_modified_destination_is_refreshed(self):
        self.run_tool()
        dest = self.collected("ref/PRTF_Innovus_22nm.tlef")
        write(dest, "# stale\n")
        _, _, err = self.run_tool("--overwrite")
        self.assertNotIn("warning", err)
        self.assertCollected("ref/PRTF_Innovus_22nm.tlef")


class TestUnits(unittest.TestCase):
    def test_looks_like_path(self):
        for tok in ("../ref/a.tlef", "da_max_delay.sdc", "a/b/qrcTechFile",
                    "WF_pt.sdc.0731"):
            self.assertTrue(collect_refs.looks_like_path(tok), tok)
        for tok in ("-timing", "125", "0.855", "NULL", "/", ".", "..",
                    "$PDK", "`include", ""):
            self.assertFalse(collect_refs.looks_like_path(tok), tok)

    def test_is_directive(self):
        for tok in ("source", "include", "`include", "read_lef",
                    "init_lef_file", "-sdc_files", "-qx_tech_file"):
            self.assertTrue(collect_refs.is_directive(tok), tok)
        for tok in ("set", "-timing", "create_rc_corner", "-name",
                    # a path is never a directive, however it is spelled
                    "../ref/QRC/RC_QRC_rcworst.tar.gz_FILE"):
            self.assertFalse(collect_refs.is_directive(tok), tok)

    def test_size_arg(self):
        self.assertEqual(1024, collect_refs.size_arg("1k"))
        self.assertEqual(32 * 1024 ** 2, collect_refs.size_arg("32M"))
        self.assertEqual(1500, collect_refs.size_arg("1500"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
