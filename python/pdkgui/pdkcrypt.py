#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdkcrypt.py
-----------
pdkgui 程式碼加密的核心(純標準函式庫,免安裝任何套件)。

做的是「認證加密」(encrypt-then-MAC):
  - 金鑰派生:PBKDF2-HMAC-SHA256(salt + 多次迭代)
  - 對稱加密:HMAC-SHA256 計數器模式(CTR)當作 keystream 做 XOR
  - 完整性 :HMAC-SHA256 標籤(先加密再 MAC),可偵測「金鑰錯誤/被竄改」

檔案格式(bytes):
  MAGIC(4) | VERSION(1) | SALT(16) | NONCE(16) | CIPHERTEXT(n) | TAG(32)

★ 安全性說明:解密金鑰最終需與程式一起發佈,因此這屬於「靜態加密 + 混淆」,
  可防止一般使用者直接讀原始碼;若要防反編譯,請改用 Cython/.so 或商用工具。
"""

import os
import hmac
import struct
import hashlib

MAGIC = b"PDKC"
VERSION = 1
KDF_ITERS = 200000            # PBKDF2 迭代次數
_SALT_LEN = 16
_NONCE_LEN = 16
_TAG_LEN = 32
_HEADER_LEN = len(MAGIC) + 1 + _SALT_LEN + _NONCE_LEN   # = 37

# 預設通關密語。
DEFAULT_PASSPHRASE = "pdkgui-default-key-change-me"

# 「釘住」的金鑰:部署版由 pdk_build.py 於此寫入打包當下使用的金鑰。
# 一旦釘住,執行時一律用它、忽略環境變數與金鑰檔 —— 因此 dist 搬到哪、
# 環境有沒有殘留 PDKGUI_KEY 都不影響,不必手動 unset。
# None 表示「未釘住」(原始碼開發環境),此時才走 env / 檔案 / 預設。
PINNED_KEY = None

# 金鑰檔名(放在 pdkcrypt.py 同目錄)
KEY_FILENAME = "pdkgui.key"


def _read_key_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
            return key or None
    except OSError:
        return None


def get_passphrase():
    """取得通關密語,依序:

      0. 已釘住的金鑰 PINNED_KEY(部署版)—— 有就直接用,忽略以下所有來源
      1. 環境變數 PDKGUI_KEY
      2. 金鑰檔:環境變數 PDKGUI_KEY_FILE 指定的檔,或本模組同目錄的 pdkgui.key
      3. 內建預設 DEFAULT_PASSPHRASE

    部署版(dist)一定是走 (0),所以執行環境有沒有 PDKGUI_KEY 都不影響,
    不必手動 unset;原始碼開發環境 PINNED_KEY 為 None,才走 (1)~(3)。
    """
    if PINNED_KEY is not None:
        return PINNED_KEY

    if os.environ.get("PDKGUI_KEY"):
        return os.environ["PDKGUI_KEY"]

    candidates = []
    if os.environ.get("PDKGUI_KEY_FILE"):
        candidates.append(os.environ["PDKGUI_KEY_FILE"])
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   KEY_FILENAME))
    for path in candidates:
        key = _read_key_file(path)
        if key:
            return key

    return DEFAULT_PASSPHRASE


def _derive_keys(passphrase, salt):
    """由通關密語派生 64 bytes:前 32 給加密、後 32 給 MAC。"""
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", passphrase, salt, KDF_ITERS, dklen=64)
    return dk[:32], dk[32:]


def _keystream(key, nonce, length):
    """HMAC-SHA256 計數器模式產生 keystream。"""
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(key, nonce + struct.pack(">Q", counter),
                         hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _xor(data, keystream):
    return bytes(b ^ k for b, k in zip(data, keystream))


def encrypt(plaintext, passphrase=None):
    """加密 bytes,回傳完整密文檔內容(bytes)。"""
    if passphrase is None:
        passphrase = get_passphrase()
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")

    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    enc_key, mac_key = _derive_keys(passphrase, salt)

    ciphertext = _xor(plaintext, _keystream(enc_key, nonce, len(plaintext)))
    header = MAGIC + bytes([VERSION]) + salt + nonce
    tag = hmac.new(mac_key, header + ciphertext, hashlib.sha256).digest()
    return header + ciphertext + tag


def decrypt(blob, passphrase=None):
    """解密密文檔內容,回傳原始 bytes;金鑰錯誤或被竄改會丟 ValueError。"""
    if passphrase is None:
        passphrase = get_passphrase()

    if len(blob) < _HEADER_LEN + _TAG_LEN or blob[:len(MAGIC)] != MAGIC:
        raise ValueError("不是有效的 PDKC 加密檔")
    version = blob[len(MAGIC)]
    if version != VERSION:
        raise ValueError("不支援的 PDKC 版本: %d" % version)

    salt = blob[5:5 + _SALT_LEN]
    nonce = blob[5 + _SALT_LEN:_HEADER_LEN]
    ciphertext = blob[_HEADER_LEN:-_TAG_LEN]
    tag = blob[-_TAG_LEN:]
    header = blob[:_HEADER_LEN]

    enc_key, mac_key = _derive_keys(passphrase, salt)
    expected = hmac.new(mac_key, header + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, tag):
        raise ValueError("完整性驗證失敗(金鑰錯誤或檔案被竄改)")

    return _xor(ciphertext, _keystream(enc_key, nonce, len(ciphertext)))
