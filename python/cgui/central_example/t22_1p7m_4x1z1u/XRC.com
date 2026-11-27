// ==== XRC command file (golden template) ====
LAYOUT PRIMARY "CELL_NAME"
LAYOUT PATH "./CELL_NAME.gds"
LAYOUT SYSTEM GDSII

SOURCE PRIMARY "CELL_NAME"
SOURCE PATH "./CELL_NAME.cdl"
SOURCE SYSTEM SPICE

PEX REPORT "pex.rep"

//EXCLUDE CELL ""
//LVS BOX
include /datacenter/techLibs/tsmc/T22N/tools/pdk_sirius/T22N/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/include_for_xrc/XRC_calibre.v1.0p3a/typical/rules
//include /tools/pdk_sirius/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/include_for_xrc/XRC_calibre/typical/rules
//include /tools/pdk_sirius/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/include_for_xrc/XRC_calibre/cbest/rules
//include /tools/pdk_sirius/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/include_for_xrc/XRC_calibre/cworst/rules
//include /tools/pdk_sirius/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/include_for_xrc/XRC_calibre/rcbest/rules
//include /tools/pdk_sirius/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/include_for_xrc/XRC_calibre/rcworst/rules

//***filiter lumped c and floating nets***//
//PEX REDUCE CC ABSOLUTE 1 //filiter c < 1f
//PEX EXTRACT FLOATING NETS ALL
//PEX REDUCE TICER 20e9
//PEX REDUCE MINCAP COMBINE 1
//PEX REDUCE MINCAP REMOVE 0.3
//PEX REDUCE MINRES COMBINE 10
//PEX REDUCE MINRES SHORT 2

PEX PIN ORDER SOURCE

PEX REDUCE VIA RESISTANCE off
//PEX REDUCE TICER
//PEX Reduce Minres SHORT
//PEX PROBE FILE
//PEX REDUCE ANALOG NO

//***modify ground name***//
PEX NETLIST DISTRIBUTED "CELL_NAME.dist" SPECTRE SOURCE GROUND GND MASK DIRECT LOCATION
PEX NETLIST LUMPED "CELL_NAME.lump" SPECTRE SOURCE GROUND GND MASK DIRECT LOCATION
PEX NETLIST SIMPLE "CELL_NAME.simple" SPECTRE SOURCE MASK DIRECT LOCATION

include /datacenter/techLibs/tsmc/T22N/tools/pdk_sirius/T22N/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/xrc/DFM_LVS_RC_CALIBRE_N22_1p7M_4X1Z1U_ALRDL.v1.2k
