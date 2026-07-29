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
VERSION = 2                   # 2 records the iteration count in the header
_SALT_LEN = 16
_NONCE_LEN = 16
_TAG_LEN = 32
_ITERS_LEN = 4

# PBKDF2 iteration count.
#
# A high count is what makes *guessing an unknown passphrase* slow. Nothing is
# guessed here: the key ships with the program (pinned into dist/pdkcrypt.py,
# which has to stay plaintext for the build to decrypt itself), so anyone who
# can read the files can read the key. The encryption is there to keep the
# source from being read casually, and that works the same at any count -- so
# the count is kept low, because it used to cost ~0.4 s per module on the EDA
# hosts, once for every module loaded.
KDF_ITERS = 1000

# Files written before the count was recorded (VERSION 1) all used this.
LEGACY_KDF_ITERS = 200000

_V1_HEADER_LEN = len(MAGIC) + 1 + _SALT_LEN + _NONCE_LEN               # = 37
_HEADER_LEN = _V1_HEADER_LEN + _ITERS_LEN                              # = 41

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


# Derived keys, kept for the life of the process. A build packs every module
# with the same salt, so loading the whole program derives once instead of once
# per module -- which is what made starting the encrypted build slow.
_key_cache = {}


def _derive_keys(passphrase, salt, iters=None):
    """Derive 64 bytes from the passphrase: first 32 for cipher, last 32 for MAC."""
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    if iters is None:
        iters = KDF_ITERS
    cached = _key_cache.get((passphrase, salt, iters))
    if cached is None:
        dk = hashlib.pbkdf2_hmac("sha256", passphrase, salt, iters, dklen=64)
        cached = _key_cache[(passphrase, salt, iters)] = (dk[:32], dk[32:])
    return cached


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


def encrypt(plaintext, passphrase=None, salt=None, iters=None):
    """Encrypt bytes, returning the full ciphertext file content (bytes).

    salt : reuse one across a build so the runtime derives the key once (the
           nonce stays random per file, which is what must not repeat).
    iters: recorded in the header, so the file says how to derive its own key."""
    if passphrase is None:
        passphrase = get_passphrase()
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")
    if salt is None:
        salt = new_salt()
    if iters is None:
        iters = KDF_ITERS

    nonce = os.urandom(_NONCE_LEN)
    enc_key, mac_key = _derive_keys(passphrase, salt, iters)

    ciphertext = _xor(plaintext, _keystream(enc_key, nonce, len(plaintext)))
    header = MAGIC + bytes([VERSION]) + struct.pack(">I", iters) + salt + nonce
    tag = hmac.new(mac_key, header + ciphertext, hashlib.sha256).digest()
    return header + ciphertext + tag


def new_salt():
    """A salt for one build (pdk_build shares it across every packed file)."""
    return os.urandom(_SALT_LEN)


def decrypt(blob, passphrase=None):
    """Decrypt a ciphertext file, returning the original bytes; raises ValueError
    on a wrong key or tampering."""
    if passphrase is None:
        passphrase = get_passphrase()

    if len(blob) < _V1_HEADER_LEN + _TAG_LEN or blob[:len(MAGIC)] != MAGIC:
        raise ValueError("not a valid PDKC encrypted file")
    version = blob[len(MAGIC)]

    # Version 1 predates the iteration count being recorded; everything written
    # then used LEGACY_KDF_ITERS, so builds made before this still load.
    if version == 1:
        header_len, iters = _V1_HEADER_LEN, LEGACY_KDF_ITERS
        after_version = len(MAGIC) + 1
    elif version == 2:
        header_len = _HEADER_LEN
        after_version = len(MAGIC) + 1 + _ITERS_LEN
        iters = struct.unpack(">I", blob[len(MAGIC) + 1:after_version])[0]
    else:
        raise ValueError("unsupported PDKC version: %d" % version)
    if len(blob) < header_len + _TAG_LEN:
        raise ValueError("not a valid PDKC encrypted file")

    salt = blob[after_version:after_version + _SALT_LEN]
    nonce = blob[after_version + _SALT_LEN:header_len]
    ciphertext = blob[header_len:-_TAG_LEN]
    tag = blob[-_TAG_LEN:]
    header = blob[:header_len]

    enc_key, mac_key = _derive_keys(passphrase, salt, iters)
    expected = hmac.new(mac_key, header + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, tag):
        raise ValueError("integrity check failed (wrong key or tampered file)")

    return _xor(ciphertext, _keystream(enc_key, nonce, len(ciphertext)))
