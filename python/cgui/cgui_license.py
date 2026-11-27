#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cgui_license.py
---------------
Offline Ed25519 license verification and anti-tamper clock rollback protection
for cgui (Python standard library only -- no third-party packages required at
runtime, compatible with Python 3.6+ / RHEL 7 / Nuitka native binaries).

Checks performed on startup and before key operations:
  1. Digital Signature : verifies payload + Ed25519 signature against the
                         embedded public key (prevents tampering).
  2. Anti-Tamper Clock : compares current time against an encrypted high-water
                         timestamp file; rejects backward clock rollbacks beyond
                         CLOCK_SKEW_TOLERANCE_SEC.
  3. Expiry & Grace    : warns within WARNING_DAYS (30 days) before expiry,
                         allows operation with a popup/banner warning during the
                         grace period (default 14 days), and locks once expired.
"""

import binascii
import datetime
import hashlib
import hmac
import json
import os
import socket
import struct
import sys
import tempfile
import time

import config

LICENSE_ENV_VAR = "CADSEMI_LICENSE_FILE"
LEGACY_LICENSE_ENV_VARS = ("CTMP_LICENSE_FILE",)
DEFAULT_LICENSE_FILENAME = "cadsemi.lic"
LEGACY_LICENSE_FILENAMES = ("ctmp.lic",)

WARNING_DAYS = 30
DEFAULT_GRACE_DAYS = 14
CLOCK_SKEW_TOLERANCE_SEC = 300   # tolerate 5 min NTP / multi-host clock skew
SUPPORT_EMAIL = "support@cadsemi.com"
ENFORCE_DOMAIN = False           # Mode 1: expiry-only trial mode; set True to enforce payload.domain

STATUS_OK = "ok"
STATUS_EXPIRING = "expiring_soon"
STATUS_GRACE = "grace_period"
STATUS_EXPIRED = "expired"
STATUS_MISSING = "missing"
STATUS_INVALID = "invalid"
STATUS_TAMPERED = "tampered"
STATUS_DOMAIN_MISMATCH = "domain_mismatch"

# --- BEGIN EMBEDDED ED25519 PUBLIC KEY (managed by lic_issuer/cgui_lic_admin.py) ---
_PUBKEY_MASK = (
    0x5c, 0x86, 0x80, 0x05, 0xad, 0x3a, 0xb6, 0x5f,
    0x1a, 0x4c, 0x50, 0xdb, 0x13, 0xfd, 0xe1, 0xb9,
    0x69, 0xb3, 0x4a, 0x60, 0xe9, 0x34, 0x4e, 0x8f,
    0xf9, 0x9a, 0x7a, 0xe1, 0x0a, 0x36, 0x0f, 0xf1,
)
_PUBKEY_OBF = (
    0x20, 0xe5, 0xa1, 0x4e, 0x86, 0x71, 0xba, 0xcd,
    0xc7, 0x25, 0x23, 0x1f, 0xea, 0xaa, 0xc1, 0xbd,
    0x86, 0xfc, 0x52, 0x21, 0x00, 0x16, 0x4a, 0x6d,
    0x15, 0x2e, 0x81, 0xb7, 0x53, 0x1d, 0x61, 0xc7,
)
# --- END EMBEDDED ED25519 PUBLIC KEY ---

_STATE_MAGIC = b"CGLS"
_STATE_VERSION = 1
_STATE_HEADER_LEN = len(_STATE_MAGIC) + 1 + 16
_STATE_TAG_LEN = 32
_INTERNAL_AT_SALT = b"ctmp-cgui-watermark-salt-2026"

# --------------------------------------------------------------------------
# Pure-Python RFC 8032 Ed25519 verification
# --------------------------------------------------------------------------
_P = (1 << 255) - 19
_L = (1 << 252) + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)
_BX = 15112221349535400772501151409588531511454012693041857206046113283949847762202
_BY = 46316835694926478169428394003475163141307993866256225615783033603165251855960
_BASE_POINT = (_BX, _BY, 1, (_BX * _BY) % _P)
_IDENTITY_POINT = (0, 1, 1, 0)


def _point_add(p1, p2):
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = ((y1 - x1) * (y2 - x2)) % _P
    b = ((y1 + x1) * (y2 + x2)) % _P
    c = (t1 * 2 * _D * t2) % _P
    d = (z1 * 2 * z2) % _P
    e = (b - a) % _P
    f = (d - c) % _P
    g = (d + c) % _P
    h = (b + a) % _P
    return ((e * f) % _P, (g * h) % _P, (f * g) % _P, (e * h) % _P)


def _scalar_mult(scalar, point):
    acc = _IDENTITY_POINT
    addend = point
    while scalar > 0:
        if scalar & 1:
            acc = _point_add(acc, addend)
        addend = _point_add(addend, addend)
        scalar >>= 1
    return acc


def _point_equal(p1, p2):
    x1, y1, z1, _ = p1
    x2, y2, z2, _ = p2
    return (x1 * z2 - x2 * z1) % _P == 0 and (y1 * z2 - y2 * z1) % _P == 0


def _decode_point(raw):
    if len(raw) != 32:
        raise ValueError("invalid point length")
    y = int.from_bytes(raw, "little") & ((1 << 255) - 1)
    if y >= _P:
        raise ValueError("y coordinate out of range")
    sign = (raw[31] >> 7) & 1

    u = (y * y - 1) % _P
    v = (_D * y * y + 1) % _P
    v3 = (v * v * v) % _P
    v7 = (v3 * v3 * v) % _P
    x = (u * v3 * pow((u * v7) % _P, (_P - 5) // 8, _P)) % _P

    vx2 = (v * x * x) % _P
    if vx2 != u:
        if vx2 == (-u) % _P:
            x = (x * _I) % _P
        else:
            raise ValueError("point is not on curve")
    if x == 0 and sign == 1:
        raise ValueError("non-canonical zero x")
    if (x & 1) != sign:
        x = _P - x
    return (x, y, 1, (x * y) % _P)


def ed25519_verify(public_key, message, signature):
    """Verify an Ed25519 signature per RFC 8032. Returns True iff valid."""
    if not isinstance(public_key, (bytes, bytearray)):
        return False
    if not isinstance(message, (bytes, bytearray)):
        return False
    if not isinstance(signature, (bytes, bytearray)):
        return False
    if len(public_key) != 32 or len(signature) != 64:
        return False

    pubkey_b = bytes(public_key)
    msg_b = bytes(message)
    sig_b = bytes(signature)

    r_bytes = sig_b[:32]
    s_val = int.from_bytes(sig_b[32:], "little")
    if s_val >= _L:
        return False

    try:
        a_pt = _decode_point(pubkey_b)
        r_pt = _decode_point(r_bytes)
    except ValueError:
        return False

    h_digest = hashlib.sha512(r_bytes + pubkey_b + msg_b).digest()
    h_val = int.from_bytes(h_digest, "little") % _L

    lhs = _scalar_mult(s_val, _BASE_POINT)
    rhs = _point_add(r_pt, _scalar_mult(h_val, a_pt))
    return _point_equal(lhs, rhs)


def get_embedded_public_key():
    """Recover the 32-byte raw Ed25519 public key embedded in this module."""
    return bytes((m ^ o) & 0xFF for m, o in zip(_PUBKEY_MASK, _PUBKEY_OBF))


def is_public_key_configured(pubkey=None):
    key = get_embedded_public_key() if pubkey is None else bytes(pubkey)
    return len(key) == 32 and any(b != 0 for b in key)


def canonical_payload_bytes(payload):
    """Deterministic UTF-8 JSON byte encoding signed/verified by issuer & app."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


# --------------------------------------------------------------------------
# Anti-tamper encrypted timestamp watermark
# --------------------------------------------------------------------------
def _state_key(pubkey_bytes):
    return hashlib.sha256(
        b"cgui-anti-tamper-v1:" + pubkey_bytes + _INTERNAL_AT_SALT
    ).digest()


def _ctr_xor(key, nonce, data):
    out = bytearray(len(data))
    counter = 0
    offset = 0
    while offset < len(data):
        block = hashlib.sha256(
            key + nonce + struct.pack(">I", counter)
        ).digest()
        chunk = data[offset:offset + len(block)]
        for i, byte_val in enumerate(chunk):
            out[offset + i] = byte_val ^ block[i]
        offset += len(block)
        counter += 1
    return bytes(out)


def _seal_state(obj, key):
    plaintext = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    nonce = os.urandom(16)
    ciphertext = _ctr_xor(key, nonce, plaintext)
    header = _STATE_MAGIC + struct.pack("B", _STATE_VERSION) + nonce
    body = header + ciphertext
    tag = hmac.new(key, body, hashlib.sha256).digest()
    return body + tag


def _open_state(blob, key):
    if len(blob) < _STATE_HEADER_LEN + _STATE_TAG_LEN:
        raise ValueError("state truncated")
    if blob[:4] != _STATE_MAGIC or blob[4] != _STATE_VERSION:
        raise ValueError("bad state header")
    body = blob[:-_STATE_TAG_LEN]
    tag = blob[-_STATE_TAG_LEN:]
    expected_tag = hmac.new(key, body, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("state MAC mismatch")
    nonce = blob[5:_STATE_HEADER_LEN]
    ciphertext = body[_STATE_HEADER_LEN:]
    plaintext = _ctr_xor(key, nonce, ciphertext)
    data = json.loads(plaintext.decode("utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("last_seen"), int):
        raise ValueError("malformed state payload")
    if data["last_seen"] < 0:
        raise ValueError("negative timestamp")
    return data


def _state_paths(state_dir=None):
    explicit = state_dir or os.environ.get("CGUI_LIC_STATE_DIR")
    if explicit:
        return [os.path.join(os.path.expanduser(explicit), ".lic_state")]
    return [
        os.path.join(config.USER_DIR, ".lic_state"),
        os.path.expanduser("~/.cache/.cgui_lic_ts"),
    ]


def _check_anti_tamper(now_ts, pubkey_bytes, state_dir=None):
    """Verify no state tampering or clock rollback occurred.

    Returns (ok: bool, last_seen: int | None, error_message: str).
    """
    key = _state_key(pubkey_bytes)
    seen_values = []
    for path in _state_paths(state_dir):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "rb") as f:
                blob = f.read()
            data = _open_state(blob, key)
            seen_values.append(data["last_seen"])
        except Exception as e:
            return (
                False,
                None,
                "License anti-tamper state is corrupted or modified (%s: %s).\n"
                "Please contact %s." % (path, e, SUPPORT_EMAIL),
            )

    last_seen = max(seen_values) if seen_values else None
    if last_seen is not None and now_ts + CLOCK_SKEW_TOLERANCE_SEC < last_seen:
        now_str = datetime.datetime.fromtimestamp(
            now_ts, datetime.timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
        last_str = datetime.datetime.fromtimestamp(
            last_seen, datetime.timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
        return (
            False,
            last_seen,
            "System clock rollback detected -- execution blocked.\n"
            "  Current time : %s\n"
            "  Last run time: %s\n"
            "Restore the system clock or contact %s."
            % (now_str, last_str, SUPPORT_EMAIL),
        )
    return True, last_seen, ""


def _write_anti_tamper(new_ts, pubkey_bytes, state_dir=None):
    key = _state_key(pubkey_bytes)
    blob = _seal_state({"version": 1, "last_seen": int(new_ts)}, key)
    for path in _state_paths(state_dir):
        parent = os.path.dirname(path)
        tmp_path = None
        try:
            os.makedirs(parent, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix=".lic_tmp_", dir=parent)
            try:
                os.write(fd, blob)
            finally:
                os.close(fd)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, path)
            tmp_path = None
        except OSError:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


# --------------------------------------------------------------------------
# License result & check_license()
# --------------------------------------------------------------------------
class LicenseResult(object):
    """Structured outcome from check_license()."""

    def __init__(
        self,
        allowed,
        status,
        message="",
        notice="",
        license_path=None,
        customer="",
        domain="",
        expire_date="",
        features=None,
        days_left=None,
        grace_days=DEFAULT_GRACE_DAYS,
        grace_left=None,
    ):
        self.allowed = allowed
        self.status = status
        self.message = message
        self.notice = notice
        self.license_path = license_path
        self.customer = customer
        self.domain = domain
        self.expire_date = expire_date
        self.features = list(features or [])
        self.days_left = days_left
        self.grace_days = grace_days
        self.grace_left = grace_left


def _resolve_now(now):
    if now is None:
        now_ts = int(time.time())
        today = datetime.date.today()
        return now_ts, today
    if isinstance(now, datetime.datetime):
        return int(now.timestamp()), now.date()
    if isinstance(now, (int, float)):
        now_ts = int(now)
        return now_ts, datetime.date.fromtimestamp(now_ts)
    raise TypeError("now must be None, datetime, or timestamp, got %r" % (type(now),))


def _resolve_license_path(license_file=None):
    """Return (resolved_path_or_None, env_value_or_None, searched_paths)."""
    if license_file:
        p = os.path.abspath(os.path.expanduser(license_file))
        return (p if os.path.isfile(p) else None), license_file, [p]

    for env_name in (LICENSE_ENV_VAR,) + LEGACY_LICENSE_ENV_VARS:
        env_val = os.environ.get(env_name, "").strip()
        if env_val:
            searched = []
            for entry in env_val.split(os.pathsep):
                entry = entry.strip()
                if not entry:
                    continue
                p = os.path.abspath(os.path.expanduser(entry))
                searched.append(p)
                if os.path.isfile(p):
                    return p, env_val, searched
            return None, env_val, searched

    searched = []
    saved_prefs = config.load_json(config.user_global_file("UI"))
    saved_lic = saved_prefs.get("license_file", "").strip() if isinstance(saved_prefs, dict) else ""
    if saved_lic:
        p = os.path.abspath(os.path.expanduser(saved_lic))
        searched.append(p)
        if os.path.isfile(p):
            return p, None, searched

    for base in (config.APP_DIR, config.BASE_DIR):
        for fname in (DEFAULT_LICENSE_FILENAME,) + LEGACY_LICENSE_FILENAMES:
            p = os.path.join(base, fname)
            if p not in searched:
                searched.append(p)
            if os.path.isfile(p):
                return p, None, searched
    return None, None, searched


_IGNORED_DOMAINS = {"", "(none)", "none", "localdomain", "localhost"}


def detect_host_domains(
    resolv_conf_path="/etc/resolv.conf",
    domainname_path="/proc/sys/kernel/domainname",
):
    """Collect normalized host domain candidates from Linux config & DNS."""
    found = []
    seen = set()

    def _add(val):
        d = (val or "").strip().lower().rstrip(".")
        if not d or d in _IGNORED_DOMAINS or d in seen:
            return
        seen.add(d)
        found.append(d)

    if resolv_conf_path:
        try:
            with open(resolv_conf_path, "r", encoding="utf-8", errors="ignore") as f:
                for raw in f:
                    line = raw.split("#", 1)[0].split(";", 1)[0].strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) >= 2 and parts[0].lower() in ("domain", "search"):
                        for tok in parts[1:]:
                            _add(tok)
        except OSError:
            pass

    if domainname_path:
        try:
            with open(domainname_path, "r", encoding="utf-8", errors="ignore") as f:
                _add(f.read())
        except OSError:
            pass

    for fn in (socket.getfqdn, socket.gethostname):
        try:
            name = (fn() or "").strip().lower().rstrip(".")
            if "." in name:
                _add(name.split(".", 1)[1])
        except Exception:
            pass

    return found


def _domain_matches(licensed_domain, host_domains):
    raw = (licensed_domain or "").strip().lower()
    allowed = [d.strip().rstrip(".") for d in raw.split(",") if d.strip()]
    if "*" in allowed:
        return True
    if not allowed:
        return False
    norm_hosts = [
        h.strip().lower().rstrip(".")
        for h in (host_domains or [])
        if h and h.strip()
    ]
    for dom in allowed:
        for hd in norm_hosts:
            if hd == dom or hd.endswith("." + dom):
                return True
    return False


def _parse_expire_date(value):
    if not isinstance(value, str):
        raise ValueError("expire_date must be YYYY-MM-DD string")
    return datetime.datetime.strptime(value.strip(), "%Y-%m-%d").date()


def check_license(
    now=None,
    update_state=True,
    license_file=None,
    state_dir=None,
    public_key=None,
    enforce_domain=None,
    host_domains=None,
    check_anti_tamper=True,
):
    """Validate the offline Ed25519 license and anti-tamper timestamp state."""
    now_ts, today = _resolve_now(now)

    pubkey = get_embedded_public_key() if public_key is None else bytes(public_key)
    if not is_public_key_configured(pubkey):
        return LicenseResult(
            allowed=False,
            status=STATUS_INVALID,
            message="License verification key is not configured in this build.\n"
                    "Please contact %s." % SUPPORT_EMAIL,
        )

    lic_path, env_val, searched = _resolve_license_path(license_file=license_file)
    if not lic_path:
        if env_val:
            hint = "%s is set to:\n  %s\nbut no license file was found there." % (
                LICENSE_ENV_VAR,
                ", ".join(searched) if searched else env_val,
            )
        else:
            hint = (
                "No license file found and %s is not set.\n"
                "Checked: %s" % (LICENSE_ENV_VAR, ", ".join(searched))
            )
        return LicenseResult(
            allowed=False,
            status=STATUS_MISSING,
            message=(
                "%s\n\n"
                "Set %s in your shell (e.g. ~/.cshrc):\n"
                "  setenv %s /proj/cad/lic/%s\n"
                "Contact %s to obtain a license."
                % (hint, LICENSE_ENV_VAR, LICENSE_ENV_VAR,
                   DEFAULT_LICENSE_FILENAME, SUPPORT_EMAIL)
            ),
        )

    try:
        with open(lic_path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except Exception as e:
        return LicenseResult(
            allowed=False,
            status=STATUS_INVALID,
            license_path=lic_path,
            message="Failed to read license file (%s):\n  %s\nContact %s."
                    % (lic_path, e, SUPPORT_EMAIL),
        )

    if not isinstance(doc, dict):
        return LicenseResult(
            allowed=False,
            status=STATUS_INVALID,
            license_path=lic_path,
            message="Invalid license format in %s (expected JSON object)." % lic_path,
        )

    payload = doc.get("payload")
    sig_hex = doc.get("signature")
    if not isinstance(payload, dict) or not isinstance(sig_hex, str):
        return LicenseResult(
            allowed=False,
            status=STATUS_INVALID,
            license_path=lic_path,
            message="Invalid license structure in %s (missing payload or signature)."
                    % lic_path,
        )

    try:
        sig_bytes = binascii.unhexlify(sig_hex.strip())
    except (binascii.Error, ValueError):
        return LicenseResult(
            allowed=False,
            status=STATUS_INVALID,
            license_path=lic_path,
            message="Malformed license signature in %s." % lic_path,
        )

    if not ed25519_verify(pubkey, canonical_payload_bytes(payload), sig_bytes):
        return LicenseResult(
            allowed=False,
            status=STATUS_INVALID,
            license_path=lic_path,
            message="License signature verification failed (%s).\n"
                    "The license file may be tampered with or issued for another key.\n"
                    "Contact %s." % (lic_path, SUPPORT_EMAIL),
        )

    customer = str(payload.get("customer") or "")
    domain = str(payload.get("domain") or "")
    features = payload.get("features")
    if features is None:
        features = []
    elif not isinstance(features, list):
        return LicenseResult(
            allowed=False,
            status=STATUS_INVALID,
            license_path=lic_path,
            message="Invalid 'features' field in license %s." % lic_path,
        )

    raw_grace = payload.get("grace_days", DEFAULT_GRACE_DAYS)
    if isinstance(raw_grace, bool) or not isinstance(raw_grace, int) or raw_grace < 0:
        return LicenseResult(
            allowed=False,
            status=STATUS_INVALID,
            license_path=lic_path,
            message="Invalid 'grace_days' field in license %s." % lic_path,
        )
    grace_days = raw_grace

    try:
        expire_dt = _parse_expire_date(payload.get("expire_date"))
    except Exception as e:
        return LicenseResult(
            allowed=False,
            status=STATUS_INVALID,
            license_path=lic_path,
            customer=customer,
            domain=domain,
            message="Invalid 'expire_date' in license %s: %s" % (lic_path, e),
        )
    expire_str = expire_dt.strftime("%Y-%m-%d")

    do_domain = ENFORCE_DOMAIN if enforce_domain is None else bool(enforce_domain)
    if do_domain:
        detected_domains = (
            list(host_domains) if host_domains is not None else detect_host_domains()
        )
        if not _domain_matches(domain, detected_domains):
            return LicenseResult(
                allowed=False,
                status=STATUS_DOMAIN_MISMATCH,
                license_path=lic_path,
                customer=customer,
                domain=domain,
                expire_date=expire_str,
                features=features,
                grace_days=grace_days,
                message=(
                    "License domain mismatch -- execution blocked.\n"
                    "  Licensed domain : %s\n"
                    "  Host domain(s)  : %s\n"
                    "This license is restricted to '%s'.\n"
                    "Please contact %s."
                    % (
                        domain or "(empty)",
                        ", ".join(detected_domains) if detected_domains else "(none)",
                        domain or "(empty)",
                        SUPPORT_EMAIL,
                    )
                ),
            )

    last_seen = None
    if check_anti_tamper:
        at_ok, last_seen, at_msg = _check_anti_tamper(now_ts, pubkey, state_dir=state_dir)
        if not at_ok:
            return LicenseResult(
                allowed=False,
                status=STATUS_TAMPERED,
                license_path=lic_path,
                customer=customer,
                domain=domain,
                expire_date=expire_str,
                features=features,
                grace_days=grace_days,
                message=at_msg,
            )

    days_left = (expire_dt - today).days
    grace_end_str = (expire_dt + datetime.timedelta(days=grace_days)).strftime("%Y-%m-%d")

    if days_left > WARNING_DAYS:
        res = LicenseResult(
            allowed=True,
            status=STATUS_OK,
            license_path=lic_path,
            customer=customer,
            domain=domain,
            expire_date=expire_str,
            features=features,
            days_left=days_left,
            grace_days=grace_days,
            message="License valid (%d days remaining, expires %s)." % (days_left, expire_str),
        )
    elif days_left >= 0:
        notice = (
            "[Notice] License will expire on %s. Please contact %s for renewal."
            % (expire_str, SUPPORT_EMAIL)
        )
        res = LicenseResult(
            allowed=True,
            status=STATUS_EXPIRING,
            license_path=lic_path,
            customer=customer,
            domain=domain,
            expire_date=expire_str,
            features=features,
            days_left=days_left,
            grace_days=grace_days,
            notice=notice,
            message=notice,
        )
    elif days_left >= -grace_days:
        grace_left = grace_days + days_left
        notice = (
            "[Warning] License expired on %s (%d grace day(s) left, locks after %s). "
            "Please contact %s for renewal."
            % (expire_str, grace_left, grace_end_str, SUPPORT_EMAIL)
        )
        res = LicenseResult(
            allowed=True,
            status=STATUS_GRACE,
            license_path=lic_path,
            customer=customer,
            domain=domain,
            expire_date=expire_str,
            features=features,
            days_left=days_left,
            grace_days=grace_days,
            grace_left=grace_left,
            notice=notice,
            message=notice,
        )
    else:
        res = LicenseResult(
            allowed=False,
            status=STATUS_EXPIRED,
            license_path=lic_path,
            customer=customer,
            domain=domain,
            expire_date=expire_str,
            features=features,
            days_left=days_left,
            grace_days=grace_days,
            grace_left=0,
            message=(
                "License expired on %s (grace period ended on %s).\n"
                "Please contact %s for renewal and update %s."
                % (expire_str, grace_end_str, SUPPORT_EMAIL, LICENSE_ENV_VAR)
            ),
        )

    if res.allowed and update_state:
        _write_anti_tamper(max(now_ts, last_seen or 0), pubkey, state_dir=state_dir)
    return res


def format_terminal_notice(result, use_color=None):
    """Format warning/grace notice for terminal output (plain text by default)."""
    if not result.notice:
        return ""
    if use_color:
        return "\033[1;33m%s\033[0m" % result.notice
    return result.notice


def format_license_info(result):
    """Human-readable multi-line summary of LicenseResult for CLI/diagnostics."""
    if not result.allowed and result.status in (
        STATUS_MISSING, STATUS_INVALID, STATUS_TAMPERED, STATUS_DOMAIN_MISMATCH
    ):
        lines = [
            "Status      : %s (BLOCKED)" % result.status.upper(),
            "License File: %s" % (result.license_path or "(none)"),
        ]
        if result.customer:
            lines.append("Customer    : %s" % result.customer)
        if result.domain:
            lines.append("Domain      : %s" % result.domain)
        if result.expire_date:
            lines.append("Expire Date : %s" % result.expire_date)
        lines.append("Detail      : %s" % result.message)
        return "\n".join(lines)

    if result.status == STATUS_OK:
        rem = "%d day(s) remaining" % result.days_left
    elif result.status == STATUS_EXPIRING:
        rem = "%d day(s) remaining (EXPIRING SOON)" % result.days_left
    elif result.status == STATUS_GRACE:
        rem = "EXPIRED (%d grace day(s) remaining)" % (result.grace_left or 0)
    else:
        rem = "EXPIRED (LOCKED)"

    lines = [
        "Status      : %s" % result.status.upper(),
        "Allowed     : %s" % ("Yes" if result.allowed else "No"),
        "Customer    : %s" % (result.customer or "-"),
        "Domain      : %s" % (result.domain or "-"),
        "Expire Date : %s (%s)" % (result.expire_date or "-", rem),
        "Features    : %s" % (", ".join(result.features) if result.features else "-"),
        "License File: %s" % (result.license_path or "-"),
    ]
    return "\n".join(lines)
