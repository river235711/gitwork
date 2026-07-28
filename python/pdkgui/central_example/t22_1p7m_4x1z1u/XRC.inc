# XRC central files (parsed as 'key = value'; #-comments and blank lines
# ignored). Four keys, plus one optional:
#   hcell / xcell -- the run script does 'ln -sf <path> hcell|xcell'
#   rules         -- the XRC_calibre.<ver> base; pdkgui appends /<corner>/rules
#                    using the XrcRCCorner selection on the XRC tab
#   deck          -- the DFM_LVS_RC deck (second include line)
#   dfm           -- optional: when set, the run script exports it as
#                    TSMC_CAL_DFM_PATH (needed by the t40lp decks, not by t22)
#                    e.g. dfm = /datacenter/.../layout_utility/xrc/include_for_xrc/DFM
# On tab open / on Run the XRC command file's two include lines are rewritten
# from 'rules' and 'deck'. To bump a version, edit this one file.
hcell = /datacenter/techLibs/tsmc/T22N/tools/pdk_sirius/T22N/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_run/xrc/hcell
xcell = /datacenter/techLibs/tsmc/T22N/tools/pdk_sirius/T22N/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_run/xrc/xcell
rules = /datacenter/techLibs/tsmc/T22N/tools/pdk_sirius/T22N/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/include_for_xrc/XRC_calibre.v1.0p3a
deck  = /datacenter/techLibs/tsmc/T22N/tools/pdk_sirius/T22N/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/xrc/DFM_LVS_RC_CALIBRE_N22_1p7M_4X1Z1U_ALRDL.v1.2k
