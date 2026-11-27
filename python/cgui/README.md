# Cadsemi CGUI

**Cadsemi CGUI** (`v1.0.0`) is a standalone Tkinter-based Linux EDA workflow launcher and layout verification workspace built for **RHEL / CentOS 7+** (`glibc >= 2.17`, `x86_64`) and compatible distributions.

## Key Features

- **Multi-Tab Workspace (`Home`, `+`, `Ctrl+T` / `Ctrl+W`)**:
  - **Home** launcher with `Tools` tiles (`DRC`, `GdsViewer`, `LVS`/`XRC` custom-on-request placeholders, and `Help`).
  - Proportionally shrinking tab strip, `File -> Recent Runs` history, and `Window` management (`New Window`, `Full Screen F11`, `Keyboard Shortcuts`).
- **DRC Verification (`pages/verify.py`)**:
  - Manages `LayoutPath`, `LayoutPrimary`, `CmdFile` (with automatic `DRC ICSTATION YES` and `include` syncing), and `RunFolder`.
  - Runs user-licensed verification commands (`Run`), launches results debugging (`RunRVE`), opens command files via `File -> Open Cmd...` / `Save Cmd...`, edits in `gvim`/`gedit`, and previews layouts in KLayout (`View`).
- **GDS Viewer (`pages/gdsviewer.py`, `pages/gdsview.py`)**:
  - Pure-Python binary `.gds` / `.gds.gz` **Scan Cells** parser with top-cell detection (`* TOP_CELL`).
  - Built-in Virtuoso/EDA `.layermap` to KLayout `.lyp` converter (`layermap_to_lyp`).
  - 3-tier KLayout executable resolution: `CGUI_KLAYOUT` env var &rarr; `klayout` on `PATH` &rarr; bundled `tools/klayout` fallback.
- **Offline Ed25519 Licensing (`cgui_license.py`, `lic_issuer/`)**:
  - Zero-daemon license verification checking `CADSEMI_LICENSE_FILE`, saved GUI preference, or `<APP_DIR>/cadsemi.lic`.
  - Supports expiry warning banner, configurable grace period, anti-tamper clock-rollback detection, `License -> License Info...`, and `License -> Select License File...`.
- **Offline HTML User Guide & Notices**:
  - `F1` / `Help -> CGUI Help` / Home `Help` tile opens `data/help/index.html` in a browser (`CGUI_BROWSER`, `google-chrome`, `chromium`, `chromium-browser`, `xdg-open`, `firefox` with CentOS 7 X11/VNC safe defaults, or `webbrowser` fallback).
  - `Help -> About CGUI` includes a `Notices` button opening `Legal Notices` for third-party trademark and open-source disclosures.

## Repository Layout

```text
cgui/
├── cgui                  # Bash launcher for source/dev runs
├── cgui.py               # Entry point (CLI flags, license check, GUI boot)
├── cgui_app.py           # Main CGui window, menu bar, tabs, About/Notices, Help launcher
├── cgui_license.py       # Offline Ed25519 verifier & anti-tamper policy
├── cgui_eng.py           # Engineer CLI mode (-e)
├── config.py             # Paths, cadsemi.com light THEME, fonts, desktop_env()
├── widgets.py            # Shared Tkinter widgets
├── cgui_build_nuitka.py  # Nuitka standalone builder + security/GLIBC auditor
├── build_rhel7.ps1       # WSL Ubuntu -> CentOS7Build release packager
├── LICENSE_GUIDE.md      # Licensing architecture & issuer guide
├── data/
│   ├── system.txt        # Release revision history (v1.0.0)
│   ├── help/index.html   # Offline HTML User Guide
│   ├── process.txt       # Process list
│   ├── env.txt           # Editor defaults
│   ├── hosts.txt         # Host list template
│   └── verify/*.com      # Verification command templates
├── pages/
│   ├── home.py           # Home launcher tiles
│   ├── verify.py         # DRC Verification page
│   ├── gdsviewer.py      # GdsViewer UI page
│   ├── gdsview.py        # Pure-Python GDSII scanner, .layermap->.lyp, KLayout launcher
│   ├── system.py         # System & license summary helper
│   ├── base.py           # BasePage
│   └── ...
├── lic_issuer/           # Vendor-only license keygen/issue/verify CLI (keys/ gitignored)
└── tests/
    └── test_cgui_license.py
```

## Running from Source (Development)

```bash
cd /home/willhuang/work/gitwork/python/cgui
export CADSEMI_LICENSE_FILE=/path/to/cadsemi.lic   # or place cadsemi.lic in this folder
python3 cgui.py
```

### Useful Environment Variables

- `CADSEMI_LICENSE_FILE`: Explicit path to `.lic` file.
- `CGUI_KLAYOUT`: Override path to the `klayout` binary.
- `CGUI_BROWSER`: Override browser command for `Help -> CGUI Help` (`F1`).

## Testing

```bash
cd /home/willhuang/work/gitwork/python/cgui
python3 -W error::DeprecationWarning -m unittest discover -s tests -v
```

## Building the RHEL 7+ Standalone Release (`cgui_<version>_linux_x64.tar.gz`)

From Windows PowerShell (uses WSL `Ubuntu` for staging and WSL `CentOS7Build` with `glibc 2.17` + Nuitka):

```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\willhuang\work\gitwork\python\cgui\build_rhel7.ps1
```

The build script reads the latest version from `data/system.txt` (`1.0.0`), verifies `Max GLIBC <= 2.17` and zero leaked `.py` / `.pyc` / `.pem` / `.lic` / `lic_issuer` files, and writes `dist/cgui_1.0.0_linux_x64.tar.gz`.

## Issuing Licenses (Vendor-Only)

> **Security Note:** Never commit `lic_issuer/keys/*.pem` or customer `.lic` files to Git.

```bash
python3 lic_issuer/cgui_lic_admin.py issue \
  --key lic_issuer/keys/private_key.pem \
  --customer "Evaluation (Monthly Trial)" \
  --domain '*' \
  --expire 2026-11-30 \
  --grace-days 0 \
  --features gui_pro,batch_char \
  --out dist/cadsemi.lic

python3 lic_issuer/cgui_lic_admin.py verify --lic dist/cadsemi.lic
```
