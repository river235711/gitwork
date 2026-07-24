# central example (golden command file + fab deck pointer)

An **example** of `config.DEFAULT_COM_DIR` (the central golden directory). To use
it, copy it to your central path, or point `PDKGUI_DEFAULT_DIR` at it.

## Structure

```
<CENTRAL>/
└── <DESIGN>/                     e.g. t22_1p7m_4x1z1u/
    ├── <MODULE>.com              golden command-file template (LoadDefault reads this)
    └── <MODULE>.inc              latest fab deck path (one line)
```

This example contains one design `t22_1p7m_4x1z1u`, with a `.com` + `.inc` pair
for DRC / ANT / WB / BUMP / DMDV / DPDO / LVS / XRC.

## How pdkgui uses it

- On tab open (and with no session) -> load `<DESIGN>/<MODULE>.com` into the text box.
- On tab open **and** on Run -> rewrite the `include <...>` line in the text to
  the value of `<DESIGN>/<MODULE>.inc`.
- `.inc` is the single source of truth for the fab deck path: to update the deck,
  **edit just the one line in `.inc`** and everyone picks it up on their next open/run.

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
