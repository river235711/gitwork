#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lic_issuer/cgui_lic_admin.py
----------------------------
Vendor-only offline Ed25519 license administration CLI for cgui.
NEVER ship this directory or private_key.pem to customers.

Requires: cryptography (installed on vendor workstation).

Subcommands:
  keygen  Generate Ed25519 keypair (private_key.pem / public_key.pem) and
          optionally embed the XOR-masked public key into cgui_license.py.
  embed   Embed an existing public_key.pem into cgui_license.py.
  issue   Sign a customer .lic JSON file using private_key.pem.
  verify  Cross-check a .lic file with cryptography and pure-Python Ed25519.
"""

import argparse
import binascii
import datetime
import json
import os
import re
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import cgui_license

_EMBED_BEGIN = "# --- BEGIN EMBEDDED ED25519 PUBLIC KEY (managed by lic_issuer/cgui_lic_admin.py) ---"
_EMBED_END = "# --- END EMBEDDED ED25519 PUBLIC KEY ---"


def _format_byte_tuple(name, data):
    lines = ["%s = (" % name]
    for offset in range(0, len(data), 8):
        chunk = ", ".join("0x%02x" % b for b in data[offset:offset + 8])
        lines.append("    %s," % chunk)
    lines.append(")")
    return "\n".join(lines)


def embed_public_key_bytes(target_path, pubkey_raw):
    if len(pubkey_raw) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes, got %d" % len(pubkey_raw))
    with open(target_path, "r", encoding="utf-8") as f:
        src = f.read()

    pattern = re.compile(
        re.escape(_EMBED_BEGIN) + r".*?" + re.escape(_EMBED_END),
        re.DOTALL,
    )
    if not pattern.search(src):
        raise ValueError("Could not find embedded public key markers in %s" % target_path)

    mask = os.urandom(32)
    obf = bytes(p ^ m for p, m in zip(pubkey_raw, mask))
    block = "\n".join([
        _EMBED_BEGIN,
        _format_byte_tuple("_PUBKEY_MASK", mask),
        _format_byte_tuple("_PUBKEY_OBF", obf),
        _EMBED_END,
    ])
    new_src = pattern.sub(block, src, count=1)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(new_src)


def _load_public_key_raw(pubkey_pem_path):
    with open(pubkey_pem_path, "rb") as f:
        pub = serialization.load_pem_public_key(f.read())
    if not isinstance(pub, ed25519.Ed25519PublicKey):
        raise ValueError("%s is not an Ed25519 public key" % pubkey_pem_path)
    return pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def cmd_keygen(args):
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    priv_path = os.path.join(out_dir, "private_key.pem")
    pub_path = os.path.join(out_dir, "public_key.pem")

    if not args.force and (os.path.exists(priv_path) or os.path.exists(pub_path)):
        sys.stderr.write(
            "Error: key file already exists in %s (pass --force to overwrite)\n" % out_dir
        )
        return 1

    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()

    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    with open(priv_path, "wb") as f:
        f.write(priv_pem)
    os.chmod(priv_path, 0o600)
    with open(pub_path, "wb") as f:
        f.write(pub_pem)
    os.chmod(pub_path, 0o644)

    print("Private key : %s (mode 0600 -- KEEP SECRET)" % priv_path)
    print("Public key  : %s" % pub_path)
    print("Raw pub hex : %s" % pub_raw.hex())

    if args.embed:
        target = os.path.abspath(args.embed)
        embed_public_key_bytes(target, pub_raw)
        print("Embedded    : %s" % target)
    return 0


def cmd_embed(args):
    pub_raw = _load_public_key_raw(args.pubkey)
    target = os.path.abspath(args.target)
    embed_public_key_bytes(target, pub_raw)
    print("Embedded public key (%s) into %s" % (pub_raw.hex(), target))
    return 0


def cmd_issue(args):
    try:
        datetime.datetime.strptime(args.expire, "%Y-%m-%d")
    except ValueError:
        sys.stderr.write("Error: --expire must be YYYY-MM-DD, got %r\n" % args.expire)
        return 1

    with open(args.key, "rb") as f:
        priv = serialization.load_pem_private_key(f.read(), password=None)
    if not isinstance(priv, ed25519.Ed25519PrivateKey):
        sys.stderr.write("Error: %s is not an Ed25519 private key\n" % args.key)
        return 1

    features = [x.strip() for x in (args.features or "").split(",") if x.strip()]
    payload = {
        "customer": args.customer,
        "domain": args.domain,
        "expire_date": args.expire,
        "features": features,
    }
    if args.grace_days is not None:
        if args.grace_days < 0:
            sys.stderr.write("Error: --grace-days must be >= 0\n")
            return 1
        payload["grace_days"] = args.grace_days

    msg = cgui_license.canonical_payload_bytes(payload)
    sig = priv.sign(msg)
    lic_doc = {
        "payload": payload,
        "signature": sig.hex(),
    }

    out_path = os.path.abspath(args.out)
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(lic_doc, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("Issued license: %s" % out_path)
    print("  customer    : %s" % payload["customer"])
    print("  domain      : %s" % payload["domain"])
    print("  expire_date : %s" % payload["expire_date"])
    if "grace_days" in payload:
        print("  grace_days  : %d" % payload["grace_days"])
    print("  features    : %s" % (", ".join(features) or "-"))
    return 0


def cmd_verify(args):
    lic_path = os.path.abspath(args.lic)
    with open(lic_path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    payload = doc.get("payload")
    sig_hex = doc.get("signature")
    if not isinstance(payload, dict) or not isinstance(sig_hex, str):
        sys.stderr.write("Invalid license JSON structure in %s\n" % lic_path)
        return 1

    try:
        sig_bytes = binascii.unhexlify(sig_hex.strip())
    except (binascii.Error, ValueError) as e:
        sys.stderr.write("Malformed signature hex: %s\n" % e)
        return 1

    if args.pubkey:
        pub_raw = _load_public_key_raw(args.pubkey)
        key_src = os.path.abspath(args.pubkey)
    else:
        pub_raw = cgui_license.get_embedded_public_key()
        key_src = "embedded key in cgui_license.py"

    msg = cgui_license.canonical_payload_bytes(payload)

    crypto_ok = False
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(pub_raw).verify(sig_bytes, msg)
        crypto_ok = True
    except InvalidSignature:
        crypto_ok = False

    pure_ok = cgui_license.ed25519_verify(pub_raw, msg, sig_bytes)

    print("License file : %s" % lic_path)
    print("Public key   : %s (%s)" % (key_src, pub_raw.hex()))
    print("cryptography : %s" % ("VALID" if crypto_ok else "INVALID"))
    print("pure-python  : %s" % ("VALID" if pure_ok else "INVALID"))

    if not (crypto_ok and pure_ok):
        return 1

    res = cgui_license.check_license(
        update_state=False,
        license_file=lic_path,
        public_key=pub_raw,
        enforce_domain=False,
        check_anti_tamper=False,
    )
    print("\n" + cgui_license.format_license_info(res))
    if payload.get("domain"):
        suffix = (
            "(enforced on target workstations)"
            if cgui_license.ENFORCE_DOMAIN
            else "(enforcement currently OFF)"
        )
        print("Domain lock  : %s %s" % (payload["domain"], suffix))
    return 0 if res.allowed else 2


def build_parser():
    parser = argparse.ArgumentParser(
        description="cgui offline Ed25519 license administration CLI (vendor-only)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_kg = sub.add_parser("keygen", help="Generate Ed25519 keypair")
    p_kg.add_argument("--out-dir", default=os.path.join(_HERE, "keys"),
                      help="Directory to write private_key.pem and public_key.pem")
    p_kg.add_argument("--embed", default=None,
                      help="Path to cgui_license.py to embed public key into")
    p_kg.add_argument("--force", action="store_true",
                      help="Overwrite existing keys")
    p_kg.set_defaults(func=cmd_keygen)

    p_em = sub.add_parser("embed", help="Embed public_key.pem into cgui_license.py")
    p_em.add_argument("--pubkey", required=True, help="Path to public_key.pem")
    p_em.add_argument("--target", default=os.path.join(_ROOT, "cgui_license.py"),
                      help="Path to cgui_license.py")
    p_em.set_defaults(func=cmd_embed)

    p_is = sub.add_parser("issue", help="Sign a customer .lic file")
    p_is.add_argument("--key", required=True, help="Path to private_key.pem")
    p_is.add_argument("--customer", required=True, help="Customer name")
    p_is.add_argument("--domain", default="", help="Customer domain")
    p_is.add_argument("--expire", required=True, help="Expiry date (YYYY-MM-DD)")
    p_is.add_argument("--features", default="gui_pro,batch_char",
                      help="Comma-separated feature list")
    p_is.add_argument("--grace-days", type=int, default=None,
                      help="Optional grace period override (default 14)")
    p_is.add_argument("--out", required=True, help="Output .lic path")
    p_is.set_defaults(func=cmd_issue)

    p_vf = sub.add_parser("verify", help="Verify a .lic file")
    p_vf.add_argument("--lic", required=True, help="Path to .lic file")
    p_vf.add_argument("--pubkey", default=None,
                      help="Optional public_key.pem (default: embedded key)")
    p_vf.set_defaults(func=cmd_verify)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
