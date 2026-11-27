# Cadsemi PVFlow (`pvflow`)

**Cadsemi PVFlow** (`v26.11.001`) is a standalone Tkinter-based Linux EDA physical verification workflow launcher and layout viewer workspace built for **RHEL / CentOS 7+** (`glibc >= 2.17`, `x86_64`) and compatible distributions.

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
  - 3-tier KLayout executable resolution: `PVFLOW_KLAYOUT` (or legacy `CGUI_KLAYOUT`) &rarr; `klayout` on `PATH` &rarr; bundled `<version>/tools/klayout` fallback.
- **Startup Environment Check**:
  - Echoes `calibre` and `klayout` availability (resolved path and loaded Environment Module, if any) on startup.
- **Offline Ed25519 Licensing (`cgui_license.py`, `lic_issuer/`)**:
  - Zero-daemon license verification checking `CADSEMI_LICENSE_FILE`, saved GUI preference, and automatic upward discovery across `<version>/`, `<product>/`, and `<vendor>/license/` (e.g. `/apps/cadsemi/license/cadsemi.lic`).
  - Supports expiry warning banner (plain terminal text), configurable grace period, anti-tamper clock-rollback detection, `License -> License Info...`, and `License -> Select License File...`.
- **Offline HTML User Guide & Notices**:
  - `F1` / `Help -> PVFlow Help` / Home `Help` tile opens `data/help/index.html` in a browser (`PVFLOW_BROWSER`, `google-chrome`, `chromium`, `chromium-browser`, `xdg-open`, `firefox` with CentOS 7 X11/VNC safe defaults, or `webbrowser` fallback).
  - `Help -> About PVFlow` includes a `Notices` button opening `Legal Notices` for third-party trademark and open-source disclosures.

## Standard EDA Deployment Layout

Extracting `pvflow_<version>_linux_x64.tar.gz` into `/apps/cadsemi/pvflow/` creates a self-contained version tree:

```text
/apps/cadsemi/
├── license/
│   └── cadsemi.lic                # Shared across all versions (no re-copy on upgrade)
└── pvflow/
    ├── current -> 26.11.001       # Optional symlink managed by CAD/IT
    └── 26.11.001/
        ├── README.md
        ├── bin/
        │   ├── pvflow             # Main launcher wrapper (add bin/ to PATH)
        │   └── cgui -> pvflow     # Compatibility symlink
        ├── libexec/
        │   ├── pvflow.bin         # Native ELF executable (Nuitka)
        │   └── *.so               # Bundled runtime libraries
        ├── data/                  # Help HTML, templates, system.txt
        └── etc/
            └── modulefile.example # Environment Modules template
```

## Customer Installation

```bash
# 1. Extract release tarball into /apps/cadsemi/pvflow
mkdir -p /apps/cadsemi/pvflow /apps/cadsemi/license
tar -xzf pvflow_26.11.001_linux_x64.tar.gz -C /apps/cadsemi/pvflow/

# 2. Place license file (shared across upgrades; or set CADSEMI_LICENSE_FILE)
cp cadsemi.lic /apps/cadsemi/license/cadsemi.lic

# 3. Verify license status
/apps/cadsemi/pvflow/26.11.001/bin/pvflow -L

# 4. (Optional) Point `current` symlink when ready for users
ln -sfn 26.11.001 /apps/cadsemi/pvflow/current
```

Users then add `/apps/cadsemi/pvflow/current/bin` to `PATH` (or load `etc/modulefile.example` via `module load pvflow/26.11.001`) and run `pvflow`.

## Running from Source (Development)

```bash
cd /home/willhuang/work/gitwork/python/cgui
export CADSEMI_LICENSE_FILE=/path/to/cadsemi.lic   # or place cadsemi.lic in this folder
./pvflow        # or: python3 cgui.py
```

### Useful Environment Variables

- `CADSEMI_LICENSE_FILE`: Explicit path to `.lic` file.
- `PVFLOW_KLAYOUT` (legacy: `CGUI_KLAYOUT`): Override path to the `klayout` binary.
- `PVFLOW_BROWSER` (legacy: `CGUI_BROWSER`): Override browser command for `Help -> PVFlow Help` (`F1`).
- `PVFLOW_HOME` (legacy: `CGUI_HOME`): Override PVFlow installation directory.

## Testing

```bash
cd /home/willhuang/work/gitwork/python/cgui
python3 -W error::DeprecationWarning -m unittest discover -s tests -v
```

## Building the RHEL 7+ Standalone Release (`pvflow_<version>_linux_x64.tar.gz`)

From Windows PowerShell (uses WSL `Ubuntu` for staging and WSL `CentOS7Build` with `glibc 2.17` + Nuitka):

```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\willhuang\work\gitwork\python\cgui\build_rhel7.ps1
```

The build script reads the latest version from `data/system.txt` (`26.11.001`), verifies `Max GLIBC <= 2.17` and zero leaked `.py` / `.pyc` / `.pem` / `.lic` / `lic_issuer` files, and writes:
- `dist/26.11.001/` (EDA release layout)
- `dist/pvflow_26.11.001_linux_x64.tar.gz`

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
