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

import sys
import zlib
import types

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


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("用法: python3 pdk_secure.py <檔案.pdkc>\n")
        return 2
    run_file(argv[1], {"__name__": "__main__"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
