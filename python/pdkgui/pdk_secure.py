#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdk_secure.py
-------------
加密程式碼的「執行期載入器」。

pdkgui 透過這裡把 .pdkc 加密檔在記憶體解密後執行,磁碟上不留明文原始碼。

主要介面:
    load_source(path)                 -> 解密後的原始碼文字
    run_file(path, namespace=None)    -> 執行整支加密檔,回傳其命名空間
    import_from_encrypted(path, name) -> 當成模組載入,回傳 module 物件

金鑰:由 pdkcrypt.get_passphrase() 決定(環境變數 PDKGUI_KEY,否則內建預設)。

也可當 CLI 直接執行一支加密檔:
    python3 pdk_secure.py <檔案.pdkc>
"""

import io
import os
import sys
import zlib
import types
import importlib.abc
import importlib.util

# locale=C 下 print 中文的保險(stdout/stderr 轉 UTF-8)
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
    """讀取並解密 .pdkc,回傳原始碼文字。"""
    with open(path, "rb") as f:
        blob = f.read()
    compressed = pdkcrypt.decrypt(blob)
    return zlib.decompress(compressed).decode("utf-8")


def run_file(path, namespace=None):
    """解密並執行整支加密檔;回傳執行後的命名空間 dict。"""
    src = load_source(path)
    code = compile(src, path, "exec")
    ns = namespace if namespace is not None else {}
    ns.setdefault("__name__", "__pdkc__")
    ns.setdefault("__file__", path)
    exec(code, ns)
    return ns


def import_from_encrypted(path, name):
    """把加密檔當成模組載入,回傳 module 物件(不寫進 sys.modules)。"""
    src = load_source(path)
    code = compile(src, path, "exec")
    mod = types.ModuleType(name)
    mod.__file__ = path
    exec(code, mod.__dict__)
    return mod


# --------------------------------------------------------------------------
# 加密模組的 import hook:讓 `import config` 之類直接從 .pdkc 載入
# --------------------------------------------------------------------------
class _EncryptedLoader(importlib.abc.Loader):
    def __init__(self, path):
        self._path = path

    def create_module(self, spec):
        return None  # 用預設的 module 物件

    def exec_module(self, module):
        # 設定 __file__,讓被加密模組裡的 os.path.abspath(__file__) 等仍可運作
        module.__file__ = self._path
        src = load_source(self._path)
        exec(compile(src, self._path, "exec"), module.__dict__)


class _EncryptedFinder(importlib.abc.MetaPathFinder):
    """把 fullname 對應到 <root>/<...>.pdkc,支援套件(__init__.pdkc)。"""

    def __init__(self, root, names):
        self._root = root
        self._names = set(names)     # 只接管這些頂層名稱,其餘交回預設機制

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in self._names:
            return None
        base = os.path.join(self._root, *fullname.split("."))
        init = os.path.join(base, "__init__.pdkc")
        if os.path.isfile(init):     # 套件
            spec = importlib.util.spec_from_loader(
                fullname, _EncryptedLoader(init), is_package=True)
            spec.submodule_search_locations = [base]
            return spec
        modfile = base + ".pdkc"
        if os.path.isfile(modfile):  # 一般模組
            return importlib.util.spec_from_loader(fullname, _EncryptedLoader(modfile))
        return None


def install_import_hook(root=None, names=None):
    """安裝加密模組載入器。

    root : .pdkc 檔所在目錄(預設本檔所在目錄)。
    names: 要接管的頂層名稱集合;None 時自動偵測 root 下所有
           <name>.pdkc 與含 __init__.pdkc 的套件目錄。
    找不到任何 .pdkc(例如純原始碼環境)時不安裝,直接沿用明文 .py。
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
        sys.stderr.write("用法: python3 pdk_secure.py <檔案.pdkc>\n")
        return 2
    run_file(argv[1], {"__name__": "__main__"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
