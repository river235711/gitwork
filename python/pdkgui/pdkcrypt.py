#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdkcrypt.py
-----------
Core of the pdkgui code encryption (standard library only, no packages needed).

It performs authenticated encryption (encrypt-then-MAC):
  - Key derivation: PBKDF2-HMAC-SHA256 (salt + many iterations)
  - Symmetric cipher: HMAC-SHA256 counter mode (CTR) as keystream, XORed in
  - Integrity: HMAC-SHA256 tag (encrypt-then-MAC), detects wrong key / tampering

File format (bytes):
  MAGIC(4) | VERSION(1) | SALT(16) | NONCE(16) | CIPHERTEXT(n) | TAG(32)

* Security note: the decryption key must ship together with the program, so this
  is "encryption at rest + obfuscation" -- it stops casual users from reading the
  source, but does not defeat decompilation. For that, use Cython/.so or a
  commercial tool.
"""

import os
import hmac
import struct
import hashlib

MAGIC = b"PDKC"
VERSION = 1
KDF_ITERS = 200000            # PBKDF2 iteration count
_SALT_LEN = 16
_NONCE_LEN = 16
_TAG_LEN = 32
_HEADER_LEN = len(MAGIC) + 1 + _SALT_LEN + _NONCE_LEN   # = 37

# Default passphrase.
DEFAULT_PASSPHRASE = "pdkgui-default-key-change-me"

# "Pinned" key: for a deployed build, pdk_build.py writes here the key used at
# pack time. Once pinned, runtime always uses it and ignores env vars and key
# files -- so dist runs anywhere regardless of a leftover PDKGUI_KEY, with no
# need to unset it. None means "not pinned" (source checkout), where env / file /
# default are consulted instead.
PINNED_KEY = None

# Key filename (kept next to pdkcrypt.py)
KEY_FILENAME = "pdkgui.key"


def _read_key_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
            return key or None
    except OSError:
        return None


def get_passphrase():
    """Return the passphrase, in order:

      0. Pinned key PINNED_KEY (deployed build) -- if set, used directly,
         ignoring every source below
      1. Environment variable PDKGUI_KEY
      2. Key file: env PDKGUI_KEY_FILE, or pdkgui.key next to this module
      3. Built-in DEFAULT_PASSPHRASE

    A deployed build (dist) always takes path (0), so a stray PDKGUI_KEY in the
    run environment does not matter and need not be unset; in a source checkout
    PINNED_KEY is None, so paths (1)-(3) apply.
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
    """Derive 64 bytes from the passphrase: first 32 for cipher, last 32 for MAC."""
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", passphrase, salt, KDF_ITERS, dklen=64)
    return dk[:32], dk[32:]


def _keystream(key, nonce, length):
    """Generate a keystream with HMAC-SHA256 in counter mode."""
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
    """Encrypt bytes, returning the full ciphertext file content (bytes)."""
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
    """Decrypt a ciphertext file, returning the original bytes; raises ValueError
    on a wrong key or tampering."""
    if passphrase is None:
        passphrase = get_passphrase()

    if len(blob) < _HEADER_LEN + _TAG_LEN or blob[:len(MAGIC)] != MAGIC:
        raise ValueError("not a valid PDKC encrypted file")
    version = blob[len(MAGIC)]
    if version != VERSION:
        raise ValueError("unsupported PDKC version: %d" % version)

    salt = blob[5:5 + _SALT_LEN]
    nonce = blob[5 + _SALT_LEN:_HEADER_LEN]
    ciphertext = blob[_HEADER_LEN:-_TAG_LEN]
    tag = blob[-_TAG_LEN:]
    header = blob[:_HEADER_LEN]

    enc_key, mac_key = _derive_keys(passphrase, salt)
    expected = hmac.new(mac_key, header + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, tag):
        raise ValueError("integrity check failed (wrong key or tampered file)")

    return _xor(ciphertext, _keystream(enc_key, nonce, len(ciphertext)))
