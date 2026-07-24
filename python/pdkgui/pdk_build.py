#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdk_build.py
------------
產生「加密部署版」目錄 dist/。

  - 商業邏輯模組(config / widgets / pdkgui_app / pages/*)→ 加密成 .pdkc
  - 只有 bootstrap 與解密器保持明文(pdkgui / pdkgui.py / pdkcrypt.py /
    pdk_secure.py),因為要靠它們啟動與解密。
  - data/ 原樣複製。
  - 金鑰會被「釘」進 dist/pdkcrypt.py:執行時一律用它、忽略環境變數,
    所以部署後直接執行即可,不必設定或 unset 任何環境變數。

用法:
    python3 pdk_build.py [輸出目錄=dist]

    # 想用自訂金鑰(選用):打包時設定即可,執行時不必再設。
    PDKGUI_KEY='your-secret' python3 pdk_build.py dist

部署:把整個 dist/ 搬到目標機器,直接執行 dist/pdkgui 即可。
      dist/ 內 `ls` 只會看到 .pdkc,看不到邏輯原始碼。
"""

import io
import os
import re
import sys
import glob
import shutil

# 舊版 Python 在 locale=C 環境下 stdout 是 ASCII,print 中文會 UnicodeEncodeError。
# 這裡把 stdout/stderr 轉成 UTF-8 作為保險。
for _name in ("stdout", "stderr"):
    _stream = getattr(sys, _name, None)
    try:
        if _stream is not None and (_stream.encoding is None
                                    or "utf" not in _stream.encoding.lower()):
            setattr(sys, _name, io.TextIOWrapper(_stream.buffer, encoding="utf-8"))
    except Exception:
        pass

import pdk_pack
import pdkcrypt

SRC = os.path.dirname(os.path.abspath(__file__))

# 保持明文(bootstrap + 解密器 + launcher)
PLAINTEXT = ["pdkgui", "pdkgui.py", "pdkcrypt.py", "pdk_secure.py"]

# 要加密的頂層模組(pages/* 另外用 glob 收集)
ENCRYPT_TOP = ["config.py", "widgets.py", "pdkgui_app.py"]


def _encrypt_to(src_rel, dist):
    src = os.path.join(SRC, src_rel)
    out = os.path.join(dist, src_rel[:-len(".py")] + ".pdkc")
    pdk_pack.pack_file(src, out)
    return out


def build(dist_name="dist"):
    dist = os.path.join(SRC, dist_name)
    if os.path.exists(dist):
        shutil.rmtree(dist)
    os.makedirs(dist)

    # 1. data/(原樣複製)
    shutil.copytree(os.path.join(SRC, "data"), os.path.join(dist, "data"))

    # 2. 明文檔照抄
    for rel in PLAINTEXT:
        s = os.path.join(SRC, rel)
        d = os.path.join(dist, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)

    # 3. 加密邏輯模組(用打包當下的金鑰)
    build_key = pdkcrypt.get_passphrase()
    encrypted = []
    for rel in ENCRYPT_TOP:
        encrypted.append(_encrypt_to(rel, dist))
    for py in sorted(glob.glob(os.path.join(SRC, "pages", "*.py"))):
        encrypted.append(_encrypt_to(os.path.relpath(py, SRC), dist))

    # 4. 把金鑰「釘」進 dist/pdkcrypt.py:執行時一律用它、忽略環境變數,
    #    因此 dist 不論搬到哪、環境有沒有殘留 PDKGUI_KEY 都能直接跑,不必 unset。
    _pin_key(os.path.join(dist, "pdkcrypt.py"), build_key)

    using_default = (build_key == pdkcrypt.DEFAULT_PASSPHRASE)
    print("部署版已建立: %s" % dist)
    print("  金鑰      : 已釘入 dist/pdkcrypt.py(執行時忽略環境變數,不必 unset)")
    print("  金鑰來源  : %s" % ("內建預設" if using_default else "打包當下的 PDKGUI_KEY / 金鑰檔"))
    print("  明文檔    : %s" % ", ".join(PLAINTEXT))
    print("  加密模組  : %d 個 .pdkc" % len(encrypted))
    print("\n部署:把整個 dist/ 搬到目標機器後直接執行(免設任何環境變數):")
    print("  %s/pdkgui" % dist)
    return dist


def _pin_key(pdkcrypt_path, key):
    """把 dist/pdkcrypt.py 裡的 `PINNED_KEY = None` 改成實際金鑰。"""
    with open(pdkcrypt_path, encoding="utf-8") as f:
        src = f.read()
    new_line = "PINNED_KEY = %r" % key
    if "PINNED_KEY = None" in src:
        src = src.replace("PINNED_KEY = None", new_line, 1)
    else:
        src = re.sub(r'(?m)^PINNED_KEY\s*=.*$', new_line, src, count=1)
    with open(pdkcrypt_path, "w", encoding="utf-8") as f:
        f.write(src)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "dist")
