#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdk_build.py
------------
產生「加密部署版」目錄 dist/。

  - 商業邏輯模組(config / widgets / pdkgui_app / pages/*)→ 加密成 .pdkc
  - 只有 bootstrap 與解密器保持明文(pdkgui / pdkgui.py / pdkcrypt.py /
    pdk_secure.py),因為要靠它們啟動與解密。
  - data/ 原樣複製;示範用的 secure_page.pdkc 以目前金鑰重新產生。

用法:
    export PDKGUI_KEY='your-secret'        # 部署與執行要用同一把金鑰
    python3 pdk_build.py [輸出目錄=dist]

部署:把整個 dist/ 搬到目標機器,設定 PDKGUI_HOME 指向它並設好 PDKGUI_KEY,
      執行 dist/pdkgui 即可。dist/ 內 `ls` 只會看到 .pdkc,看不到邏輯原始碼。
"""

import os
import sys
import glob
import shutil

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
    # 用目前金鑰重新產生示範加密頁
    pdk_pack.pack_file(
        os.path.join(SRC, "secure_src", "secure_page.py"),
        os.path.join(dist, "data", "secure", "secure_page.pdkc"),
    )

    # 2. 明文檔照抄
    for rel in PLAINTEXT:
        s = os.path.join(SRC, rel)
        d = os.path.join(dist, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)

    # 3. 加密邏輯模組
    encrypted = []
    for rel in ENCRYPT_TOP:
        encrypted.append(_encrypt_to(rel, dist))
    for py in sorted(glob.glob(os.path.join(SRC, "pages", "*.py"))):
        encrypted.append(_encrypt_to(os.path.relpath(py, SRC), dist))

    key_src = "PDKGUI_KEY" if os.environ.get("PDKGUI_KEY") else "內建預設金鑰(請改用 PDKGUI_KEY)"
    print("部署版已建立: %s" % dist)
    print("  金鑰來源  : %s" % key_src)
    print("  明文檔    : %s" % ", ".join(PLAINTEXT))
    print("  加密模組  : %d 個 .pdkc" % len(encrypted))
    print("\n部署後在目標機器:")
    print("  export PDKGUI_HOME=%s" % dist)
    print("  export PDKGUI_KEY='<同一把金鑰>'")
    print("  %s/pdkgui" % dist)
    return dist


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "dist")
