// ==== XRC command file (golden 範本) ====
LAYOUT PRIMARY "CELL_NAME"
LAYOUT PATH "./CELL_NAME.gds"
LAYOUT SYSTEM GDSII

SOURCE PRIMARY "CELL_NAME"
SOURCE PATH "./CELL_NAME.cdl"
SOURCE SYSTEM SPICE

PEX REPORT "pex.rep"

include /datacenter/techLibs/tsmc/T22N/tools/pdk_sirius/T22N/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/xrc/CLN22ULP_7M_4X1Z1U_xrc_001.19_2a.encrypt
