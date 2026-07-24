#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdk_secure.py
-------------
Runtime loader for encrypted code.

pdkgui uses this to decrypt .pdkc files in memory and run them, leaving no
plaintext source on disk.

Main interface:
    load_source(path)                 -> decrypted source text
    run_file(path, namespace=None)    -> run a whole encrypted file, return its namespace
    import_from_encrypted(path, name) -> load as a module, return the module object

Key: decided by pdkcrypt.get_passphrase() (env PDKGUI_KEY, else built-in default).

Can also be used as a CLI to run one encrypted file:
    python3 pdk_secure.py <file.pdkc>
"""

import io
import os
import sys
import zlib
import types
import importlib.abc
import importlib.util

# Safety net for printing under locale=C (wrap stdout/stderr as UTF-8)
for _name in ("stdout", "stderr"):
    _stream = getattr(sys, _name, None)
    try:
        if _stream is not None and (_stream.encoding is None
                                    or "utf" not in _stream.encoding.lower()):
            setattr(sys, _name, io.TextIOWrapper(_stream.buffer, encoding="utf-8"))
    except Exception:
        pass

import pdkcrypt


def load_source(path):
    """Read and decrypt a .pdkc, returning the source text."""
    with open(path, "rb") as f:
        blob = f.read()
    compressed = pdkcrypt.decrypt(blob)
    return zlib.decompress(compressed).decode("utf-8")


def run_file(path, namespace=None):
    """Decrypt and run a whole encrypted file; return the resulting namespace dict."""
    src = load_source(path)
    code = compile(src, path, "exec")
    ns = namespace if namespace is not None else {}
    ns.setdefault("__name__", "__pdkc__")
    ns.setdefault("__file__", path)
    exec(code, ns)
    return ns


def import_from_encrypted(path, name):
    """Load an encrypted file as a module, returning the module object
    (not registered in sys.modules)."""
    src = load_source(path)
    code = compile(src, path, "exec")
    mod = types.ModuleType(name)
    mod.__file__ = path
    exec(code, mod.__dict__)
    return mod


# --------------------------------------------------------------------------
# Import hook for encrypted modules: makes `import config` etc. load from .pdkc
# --------------------------------------------------------------------------
class _EncryptedLoader(importlib.abc.Loader):
    def __init__(self, path):
        self._path = path

    def create_module(self, spec):
        return None  # use the default module object

    def exec_module(self, module):
        # Set __file__ so os.path.abspath(__file__) etc. still work in the module
        module.__file__ = self._path
        src = load_source(self._path)
        exec(compile(src, self._path, "exec"), module.__dict__)


class _EncryptedFinder(importlib.abc.MetaPathFinder):
    """Map a fullname to <root>/<...>.pdkc, supporting packages (__init__.pdkc)."""

    def __init__(self, root, names):
        self._root = root
        self._names = set(names)     # only take over these top-level names; rest fall through

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in self._names:
            return None
        base = os.path.join(self._root, *fullname.split("."))
        init = os.path.join(base, "__init__.pdkc")
        if os.path.isfile(init):     # package
            spec = importlib.util.spec_from_loader(
                fullname, _EncryptedLoader(init), is_package=True)
            spec.submodule_search_locations = [base]
            return spec
        modfile = base + ".pdkc"
        if os.path.isfile(modfile):  # regular module
            return importlib.util.spec_from_loader(fullname, _EncryptedLoader(modfile))
        return None


def install_import_hook(root=None, names=None):
    """Install the encrypted-module loader.

    root : directory holding the .pdkc files (default: this file's directory).
    names: set of top-level names to take over; when None, auto-detect all
           <name>.pdkc and package dirs containing __init__.pdkc under root.
    When no .pdkc are found (e.g. a plain source checkout) nothing is installed
    and the plaintext .py are used as usual.
    """
    if root is None:
        root = os.path.dirname(os.path.abspath(__file__))
    if names is None:
        names = set()
        try:
            entries = os.listdir(root)
        except OSError:
            entries = []
        for entry in entries:
            full = os.path.join(root, entry)
            if entry.endswith(".pdkc"):
                names.add(entry[:-len(".pdkc")])
            elif os.path.isdir(full) and os.path.isfile(os.path.join(full, "__init__.pdkc")):
                names.add(entry)
    if not names:
        return None
    finder = _EncryptedFinder(root, names)
    sys.meta_path.insert(0, finder)
    return finder


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: python3 pdk_secure.py <file.pdkc>\n")
        return 2
    run_file(argv[1], {"__name__": "__main__"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
