# central example (golden command file + fab deck pointer)

An **example** of `config.DEFAULT_COM_DIR` (the central golden directory). To use
it, copy it to your central path, or point `PDKGUI_DEFAULT_DIR` at it.

## Structure

```
<CENTRAL>/
├── system.txt                    revision history -- design-independent, read by every user
└── <DESIGN>/                     e.g. t22_1p7m_4x1z1u/
    ├── <MODULE>.com              golden command-file template (LoadDefault reads this)
    ├── <MODULE>.inc              latest fab deck path (one line)
    ├── XRC.inc                   four XRC paths as key=value (hcell/xcell/rules/deck)
    ├── DOC.txt                   document index: <Doc. No.>|<Doc ID>|<Title> per line
    ├── doc/<Doc. No.>/<Doc ID>/  the PDFs of each document (see doc/README.md)
    └── SKIPPER.conf              skipper viewer paths (cdsTech/cdsDisp/cdsLayerMap/init)
```

This example contains one design `t22_1p7m_4x1z1u`, with a `.com` + `.inc` pair
for DRC / ANT / WB / BUMP / DMDV / DPDO / LVS / XRC, plus a `SKIPPER.conf` for the
skipper GDS viewer (the SKIPPER tab and the View buttons). In `SKIPPER.conf`,
`init` is optional -- if unset or the file is missing, `-init` is omitted from the
skipper command.

## How pdkgui uses it

- The DOC tab reads `<DESIGN>/DOC.txt` (per process), one line per document:
  `<Doc. No.>|<Doc ID>|<Title>`. The first field groups the left column, the third
  is the middle column, and the PDFs of a document are looked up right here in
  `<DESIGN>/doc/<Doc. No.>/<Doc ID>/*.pdf`. Clicking a PDF opens it in a viewer.
  (Env `PDKGUI_DOC_ROOT` moves just the PDF tree to another share if needed.)
- The SYSTEM tab reads `<CENTRAL>/system.txt` -- it sits at the top level, **not**
  under a design, so every user sees the same revision history whatever PROCESS /
  design is selected. If it is absent, the built-in `data/system.txt` is used.
- On tab open (and with no session) -> load `<DESIGN>/<MODULE>.com` into the text box.
- On tab open **and** on Run -> rewrite the `include <...>` line in the text to
  the value of `<DESIGN>/<MODULE>.inc`.
- `.inc` is the single source of truth for the fab deck path: to update the deck,
  **edit just the one line in `.inc`** and everyone picks it up on their next open/run.
- **XRC is the exception**: `XRC.inc` is a `key = value` file with four keys
  (`hcell`, `xcell`, `rules`, `deck`). On open/Run the run folder symlinks
  `hcell`/`xcell`, and the two XRC includes are rebuilt as
  `include <rules>/<corner>/rules` (corner from the XrcRCCorner field) and
  `include <deck>`.

## How to apply

Either:

1. Copy it into your central directory (i.e. `config.DEFAULT_COM_DIR`):
   ```bash
   cp -r central_example/* <YOUR_CENTRAL>/
   ```
2. Or point central at this example (for testing):
   ```bash
   export PDKGUI_DEFAULT_DIR=/home/willhuang/work/gitwork/python/pdkgui/central_example
   ```

## Adding another design

Copy `t22_1p7m_4x1z1u/` to a new design name (matching a PROCESS option, e.g.
`t22_1p8m_5x1z1u/`), then edit the `.com` / `.inc` contents:

```bash
cp -r central_example/t22_1p7m_4x1z1u central_example/t22_1p8m_5x1z1u
# edit central_example/t22_1p8m_5x1z1u/*.inc with that design's deck paths
```

## Updating a deck (day-to-day)

```bash
echo /datacenter/.../CLN22ULP_7M_4X1Z1U_<new>.encrypt \
    > <CENTRAL>/t22_1p7m_4x1z1u/DRC.inc
```

> `CELL_NAME` / `./CELL_NAME.gds` in the `.com` files are placeholders; the real
> values come from the user filling in fields or loading a layout.
> The deck paths in `.inc` are example formats -- replace them with your PDK's
> actual paths.
