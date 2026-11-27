// ==== DMDV command file (golden template) ====
// Users may edit DEFINE / EXCLUDE etc.; pdkgui auto-updates the bottom
// include line from DMDV.inc.
LAYOUT PRIMARY "CELL_NAME"
LAYOUT PATH "./CELL_NAME.gds"
LAYOUT SYSTEM GDSII

DRC RESULTS DATABASE "DMDV_RES.db"
DRC SUMMARY REPORT "DMDV.rep"  // HIER

//#DEFINE FULL_CHIP            // Turn on for chip level design
//#DEFINE WITH_SEALRING        // Turn on if sealring is assembled in chip
#DEFINE IP_TIGHTEN_DENSITY     // Turn on to tighten local density check
#DEFINE SKIP_CELL_BOUNDARY     // Turn on to skip PO.W.15~20 boundary check
#DEFINE DFM                    // Turn on to check DFM rules

//EXCLUDE CELL ""

include /datacenter/techLibs/tsmc/T22N/tools/pdk_sirius/T22N/calibre_layout/tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_utility/dmdv/CLN22ULP_7M_4X1Z1U_dmdv_001.19_2a.encrypt
