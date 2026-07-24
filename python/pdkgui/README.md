# pdkgui

A Tkinter GUI modeled on an internal EDA flow manager (PROCESS / ENV / DRC / ANT
/ WB / BUMP / DMDV / DPDO / LVS / XRC / JIVARO / SKIPPER / KLAYOUT / DOC / SYSTEM).

## File layout

```
pdkgui/
├── pdkgui              launcher (bash): module-load a tkinter python, then run
├── pdkgui.py           bootstrap (plaintext, no logic): install the encrypted
│                       import hook -> pdkgui_app.main()
├── pdkgui_app.py       main window + left menu + page routing
├── config.py           central settings (which file each tab reads, paths, constants)
├── widgets.py          shared widgets (ScrolledText with two scrollbars, LogoPanel)
├── pages/              per-tab pages
│   ├── base.py  process.py  env.py  verify.py  skipper.py
│   ├── klayout.py  doc.py  system.py  __init__.py (page registry)
├── data/               content files each tab reads (system.txt / env.txt / verify/*.com / doc/*)
├── pdkcrypt.py         encryption core (stdlib only: PBKDF2 + HMAC-CTR + encrypt-then-MAC)
├── pdk_secure.py       runtime loader + encrypted-module import hook
├── pdk_pack.py         single-file encryptor (.py -> .pdkc)
└── pdk_build.py        produce the full encrypted deploy build dist/
```

## Running (development)

Run directly from the source directory (with no .pdkc present the import hook
does nothing and the plaintext .py load as usual):

```bash
./pdkgui                 # or  python3 pdkgui.py
```

The launcher loads a tkinter-capable python via Environment Modules
(`module load python/3.6.3`; override with `PDKGUI_MODULE` / `PDKGUI_PYTHON`) and
starts in the background. Needs an X display (`ssh -X`).

## Encrypted deployment

```bash
python3 pdk_build.py dist        # produce dist/; the key is pinned into dist/pdkcrypt.py
dist/pdkgui                      # run directly, no environment variables needed
```

- In `dist/` only the bootstrap and decryptor are plaintext; the rest
  (`config`/`widgets`/`pdkgui_app`/`pages/*`) are `.pdkc`, so tracing/reading the
  files reveals no logic source.
- The key is **pinned into `dist/pdkcrypt.py`** and env vars are ignored at
  runtime -- it runs anywhere regardless of a stray `PDKGUI_KEY`, no unset needed.
  For a custom key: `PDKGUI_KEY=xxx python3 pdk_build.py dist`.
- `dist/` is a reproducible artifact and is **not committed**; rebuild it with
  `pdk_build.py` when deploying.

### Security level

Client-side protection = **encryption at rest + obfuscation**: the decryption key
ships with the program, so the files on disk are ciphertext and plaintext only
lives briefly in memory. It stops casual `cat`/trace, but not decompilation or a
memory dump. For stronger protection use **Cython** (compile to `.so`) or a tool
like **PyArmor**.

## Default command files (central golden directory)

The default command files for the verify pages
(DRC/ANT/WB/BUMP/DMDV/DPDO/LVS/XRC) live in a central directory, one subdir per
design (set via `config.DEFAULT_COM_DIR`, or override with env
`PDKGUI_DEFAULT_DIR`):

```
<DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.com     golden command-file template (LoadDefault reads this)
<DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.inc     latest fab deck path (one line, optional)
<DEFAULT_COM_DIR>/<DESIGN>/SKIPPER.conf     skipper viewer paths (cdsTech/cdsDisp/cdsLayerMap/init)
```

- The LoadDefault button reads `.com`; if the central file is missing it falls
  back to the built-in template `data/verify/<MODULE>.com`.
- `.inc` (optional) holds the **latest fab PDK deck path** (one line). On **tab
  open and on Run**, pdkgui rewrites the `include <...>` line in the command to
  the value of `.inc` -- when the deck is updated you edit just this one-line
  file and everyone picks up the new path on their next open/run. If `.inc` is
  absent the existing include is left untouched (backward compatible).
  e.g. `echo /datacenter/.../CLN22ULP_..._<new>.encrypt > <DEFAULT_COM_DIR>/<DESIGN>/DRC.inc`

## GDS viewers (skipper / klayout)

- **SKIPPER** tab and the **View** button on other tabs -> open with `skipper`.
- **KLAYOUT** tab -> same GDS-list UI, but opens with `klayout`
  (`config.KLAYOUT_BIN`, default `/usr/bin/klayout`; override via env
  `PDKGUI_KLAYOUT`). Independent of the PROCESS selection -- no SKIPPER.conf /
  module load needed.

Both generate a shell in `~/.pdkgui/` (never in `./`, so it works even when viewing
a GDS in a directory you cannot write to) and run it in a terminal (falling back to
a detached background launch). Both tabs remember their GDS list in the user session
(`~/.pdkgui/session/SKIPPER.json` / `KLAYOUT.json`).

The skipper shell is:

```
#!/bin/bash -l
module load <skipper>      # from the ENV tab
module load <calibre>      # from the ENV tab
skipper -noterm -i <gds> -cdsTech <..> -cdsDisp <..> -cdsLayerMap <..> [-init <..>]
```

The `-cdsTech` / `-cdsDisp` / `-cdsLayerMap` / `init` paths come from
`<DEFAULT_COM_DIR>/<DESIGN>/SKIPPER.conf` (`key = value` lines). `init` is optional:
`-init` is added only when it is set and the file exists, otherwise it is omitted.

## Per-user state `~/.pdkgui/`

Each user's "last time" fields and command text are stored here (override the
root with `PDKGUI_USER_DIR`):

```
~/.pdkgui/session/<DESIGN>/<MODULE>.json    per-tab last working state (fields + command)
```

Tab open read order: **session (last time) -> central default -> built-in template**.
