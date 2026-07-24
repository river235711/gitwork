#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdk_pack.py
-----------
把一支 .py 原始碼「加密打包」成 .pdkc 檔。

用法:
    python3 pdk_pack.py <來源.py> [輸出.pdkc]      # 例:python3 pdk_pack.py config.py config.pdkc

    # 用自訂金鑰(選用):
    PDKGUI_KEY=my-secret python3 pdk_pack.py config.py config.pdkc

一般不需要單獨用這支;整包加密部署版請用 pdk_build.py。

流程:讀原始碼 → 語法檢查(compile)→ zlib 壓縮 → 加密 → 寫檔。
(加密的是「原始碼文字」而非特定版本的 bytecode,因此跨 Python 版本可用。)
"""

import io
import os
import sys
import zlib

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


def pack_source(src_text, filename="<pdkc>"):
    """壓縮 + 加密原始碼文字,回傳 .pdkc 檔內容(bytes)。"""
    compile(src_text, filename, "exec")           # 先確認語法正確
    compressed = zlib.compress(src_text.encode("utf-8"), 9)
    return pdkcrypt.encrypt(compressed)


def pack_file(src_path, out_path=None):
    if out_path is None:
        out_path = os.path.splitext(src_path)[0] + ".pdkc"
    with open(src_path, encoding="utf-8") as f:
        src_text = f.read()
    blob = pack_source(src_text, src_path)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(blob)
    return out_path


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(__doc__)
        return 2
    src = argv[1]
    out = argv[2] if len(argv) > 2 else None
    out_path = pack_file(src, out)
    key_src = "PDKGUI_KEY 環境變數" if os.environ.get("PDKGUI_KEY") else "內建預設金鑰"
    print("已加密: %s -> %s  (金鑰來源: %s)" % (src, out_path, key_src))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
