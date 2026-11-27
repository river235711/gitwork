#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_cgui_license.py
--------------------------
Comprehensive tests for cgui offline Ed25519 licensing, anti-tamper clock
rollback detection, vendor issuer CLI, GUI integration, and compiled Nuitka ELF
binary (dist/cgui/cgui.bin + dist/cgui/cgui).
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cgui_license
import config
from lic_issuer import cgui_lic_admin


def _issue_temp_lic(priv_key, path, expire_date, customer="ctmp",
                    domain="*", features=None, grace_days=None):
    payload = {
        "customer": customer,
        "domain": domain,
        "expire_date": expire_date,
        "features": features if features is not None else ["gui_pro", "batch_char"],
    }
    if grace_days is not None:
        payload["grace_days"] = grace_days
    sig = priv_key.sign(cgui_license.canonical_payload_bytes(payload))
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"payload": payload, "signature": sig.hex()}, f, indent=2)


class TestEd25519(unittest.TestCase):
    def test_rfc8032_vectors_against_cryptography(self):
        # RFC 8032 Section 7.1 Test Vector 1 (empty msg) & Test Vector 2 (1-byte 0x72)
        vectors = [
            (
                "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
                "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
                b"",
                "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
                "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
            ),
            (
                "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
                "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
                b"\x72",
                "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
                "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
            ),
        ]
        for seed_hex, pub_hex, msg, sig_hex in vectors:
            priv = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex))
            pub_raw = priv.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            self.assertEqual(pub_raw, bytes.fromhex(pub_hex))
            sig = priv.sign(msg)
            self.assertEqual(sig, bytes.fromhex(sig_hex))
            self.assertTrue(cgui_license.ed25519_verify(pub_raw, msg, sig))
            self.assertFalse(cgui_license.ed25519_verify(pub_raw, msg + b"x", sig))

    def test_cross_check_random_keys_and_tamper_rejection(self):
        for idx in range(5):
            priv = ed25519.Ed25519PrivateKey.generate()
            pub_raw = priv.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            payload = {
                "customer": "Customer_%d" % idx,
                "domain": "example%d.com" % idx,
                "expire_date": "2028-01-15",
                "features": ["gui_pro", "batch_char"],
            }
            msg = cgui_license.canonical_payload_bytes(payload)
            sig = priv.sign(msg)
            self.assertTrue(cgui_license.ed25519_verify(pub_raw, msg, sig))

            # Flip 1 bit in signature
            bad_sig = bytearray(sig)
            bad_sig[idx * 7 % 64] ^= 0x01
            self.assertFalse(cgui_license.ed25519_verify(pub_raw, msg, bytes(bad_sig)))

            # Flip 1 bit in public key
            bad_pub = bytearray(pub_raw)
            bad_pub[idx * 5 % 32] ^= 0x01
            self.assertFalse(cgui_license.ed25519_verify(bytes(bad_pub), msg, sig))

            # Flip 1 bit in message
            bad_msg = bytearray(msg)
            bad_msg[10] ^= 0x01
            self.assertFalse(cgui_license.ed25519_verify(pub_raw, bytes(bad_msg), sig))

            # Non-canonical S >= L (set S = _L)
            s_ge_l = sig[:32] + cgui_license._L.to_bytes(32, "little")
            self.assertFalse(cgui_license.ed25519_verify(pub_raw, msg, s_ge_l))

        self.assertFalse(cgui_license.ed25519_verify(b"\x00" * 31, b"a", b"\x00" * 64))
        self.assertFalse(cgui_license.ed25519_verify(b"\x00" * 32, b"a", b"\x00" * 63))


class TestIssuerCLI(unittest.TestCase):
    def test_keygen_embed_issue_verify_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            keys_dir = os.path.join(tmp, "keys")
            lic_copy = os.path.join(tmp, "cgui_license.py")
            shutil.copy2(os.path.join(ROOT, "cgui_license.py"), lic_copy)
            lic_path = os.path.join(tmp, "ctmp.lic")

            rc = cgui_lic_admin.main(["keygen", "--out-dir", keys_dir, "--embed", lic_copy])
            self.assertEqual(rc, 0)
            priv_path = os.path.join(keys_dir, "private_key.pem")
            pub_path = os.path.join(keys_dir, "public_key.pem")
            self.assertTrue(os.path.isfile(priv_path))
            self.assertTrue(os.path.isfile(pub_path))
            self.assertEqual(os.stat(priv_path).st_mode & 0o777, 0o600)

            rc = cgui_lic_admin.main([
                "issue",
                "--key", priv_path,
                "--customer", "ctmp",
                "--domain", "sirius-wireless.com",
                "--expire", "2036-11-20",
                "--features", "gui_pro,batch_char",
                "--out", lic_path,
            ])
            self.assertEqual(rc, 0)

            with open(lic_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual(doc["payload"], {
                "customer": "ctmp",
                "domain": "sirius-wireless.com",
                "expire_date": "2036-11-20",
                "features": ["gui_pro", "batch_char"],
            })
            self.assertEqual(len(bytes.fromhex(doc["signature"])), 64)

            with mock.patch.dict(os.environ, {
                "CGUI_LIC_STATE_DIR": os.path.join(tmp, "state"),
            }):
                rc = cgui_lic_admin.main(["verify", "--lic", lic_path, "--pubkey", pub_path])
                self.assertEqual(rc, 0)

                # Tampering fails verify
                doc["payload"]["expire_date"] = "2099-12-31"
                with open(lic_path, "w", encoding="utf-8") as f:
                    json.dump(doc, f)
                rc = cgui_lic_admin.main(["verify", "--lic", lic_path, "--pubkey", pub_path])
                self.assertNotEqual(rc, 0)


class TestLicensePolicyAndAntiTamper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.priv = ed25519.Ed25519PrivateKey.generate()
        self.pub = self.priv.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.state_dir = os.path.join(self.tmp.name, "state")
        self.lic_path = os.path.join(self.tmp.name, "ctmp.lic")
        self.base_dt = datetime.datetime(2026, 11, 19, 12, 0, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def _check(self, dt, update_state=True, lic_path=None):
        return cgui_license.check_license(
            now=dt,
            update_state=update_state,
            license_file=lic_path if lic_path is not None else self.lic_path,
            state_dir=self.state_dir,
            public_key=self.pub,
        )

    def test_valid_expiring_grace_and_expired_windows(self):
        expire = (self.base_dt.date() + datetime.timedelta(days=45)).strftime("%Y-%m-%d")
        _issue_temp_lic(self.priv, self.lic_path, expire)
        res = self._check(self.base_dt, update_state=False)
        self.assertTrue(res.allowed)
        self.assertEqual(res.status, cgui_license.STATUS_OK)
        self.assertEqual(res.days_left, 45)
        self.assertEqual(res.notice, "")

        # Exactly 30 days left -> warning notice
        dt_30 = datetime.datetime.combine(
            datetime.date.fromisoformat(expire) - datetime.timedelta(days=30),
            datetime.time(12, 0),
        )
        res = self._check(dt_30, update_state=False)
        self.assertTrue(res.allowed)
        self.assertEqual(res.status, cgui_license.STATUS_EXPIRING)
        self.assertEqual(
            res.notice,
            "[Notice] License will expire on %s. Please contact support@cadsemi.com for renewal."
            % expire,
        )

        # Day of expiry (0 days left) -> still expiring warning
        dt_0 = datetime.datetime.combine(
            datetime.date.fromisoformat(expire), datetime.time(12, 0)
        )
        res = self._check(dt_0, update_state=False)
        self.assertTrue(res.allowed)
        self.assertEqual(res.status, cgui_license.STATUS_EXPIRING)

        # 1 day after expiry -> grace period (13 grace days left)
        dt_g1 = dt_0 + datetime.timedelta(days=1)
        res = self._check(dt_g1, update_state=False)
        self.assertTrue(res.allowed)
        self.assertEqual(res.status, cgui_license.STATUS_GRACE)
        self.assertEqual(res.grace_left, 13)
        self.assertIn("13 grace day(s) left", res.notice)

        # 14 days after expiry -> last grace day (0 grace days left)
        dt_g14 = dt_0 + datetime.timedelta(days=14)
        res = self._check(dt_g14, update_state=False)
        self.assertTrue(res.allowed)
        self.assertEqual(res.status, cgui_license.STATUS_GRACE)
        self.assertEqual(res.grace_left, 0)

        # 15 days after expiry -> hard expired (blocked)
        dt_exp = dt_0 + datetime.timedelta(days=15)
        res = self._check(dt_exp, update_state=False)
        self.assertFalse(res.allowed)
        self.assertEqual(res.status, cgui_license.STATUS_EXPIRED)

        # grace_days=0 (no grace period): allowed on expire_date, blocked next day
        no_grace_lic = os.path.join(self.tmp.name, "no_grace.lic")
        _issue_temp_lic(self.priv, no_grace_lic, expire, grace_days=0)
        res_ng_day0 = self._check(dt_0, update_state=False, lic_path=no_grace_lic)
        self.assertTrue(res_ng_day0.allowed)
        self.assertEqual(res_ng_day0.status, cgui_license.STATUS_EXPIRING)
        res_ng_day1 = self._check(dt_g1, update_state=False, lic_path=no_grace_lic)
        self.assertFalse(res_ng_day1.allowed)
        self.assertEqual(res_ng_day1.status, cgui_license.STATUS_EXPIRED)

    def test_tampered_license_and_missing_file(self):
        expire = (self.base_dt.date() + datetime.timedelta(days=60)).strftime("%Y-%m-%d")
        _issue_temp_lic(self.priv, self.lic_path, expire)
        with open(self.lic_path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        doc["payload"]["expire_date"] = "2099-12-31"
        with open(self.lic_path, "w", encoding="utf-8") as f:
            json.dump(doc, f)

        res = self._check(self.base_dt, update_state=False)
        self.assertFalse(res.allowed)
        self.assertEqual(res.status, cgui_license.STATUS_INVALID)

        res_missing = self._check(
            self.base_dt,
            update_state=False,
            lic_path=os.path.join(self.tmp.name, "missing.lic"),
        )
        self.assertFalse(res_missing.allowed)
        self.assertEqual(res_missing.status, cgui_license.STATUS_MISSING)
        self.assertIn("CADSEMI_LICENSE_FILE", res_missing.message)

        # Legacy CTMP_LICENSE_FILE still resolves when CADSEMI_LICENSE_FILE is unset
        with mock.patch.dict(os.environ, {"CTMP_LICENSE_FILE": self.lic_path}):
            os.environ.pop("CADSEMI_LICENSE_FILE", None)
            _issue_temp_lic(self.priv, self.lic_path, expire)
            res_legacy = cgui_license.check_license(
                now=self.base_dt,
                update_state=False,
                state_dir=self.state_dir,
                public_key=self.pub,
            )
            self.assertTrue(res_legacy.allowed)
            self.assertEqual(res_legacy.license_path, self.lic_path)

    def test_anti_tamper_clock_rollback_and_state_corruption(self):
        expire = (self.base_dt.date() + datetime.timedelta(days=60)).strftime("%Y-%m-%d")
        _issue_temp_lic(self.priv, self.lic_path, expire)

        t0 = int(self.base_dt.timestamp())
        res0 = self._check(t0, update_state=True)
        self.assertTrue(res0.allowed)
        state_file = os.path.join(self.state_dir, ".lic_state")
        self.assertTrue(os.path.isfile(state_file))
        self.assertEqual(os.stat(state_file).st_mode & 0o777, 0o600)

        # Advance by 60s
        res1 = self._check(t0 + 60, update_state=True)
        self.assertTrue(res1.allowed)

        # Minor clock skew (-120s from T0+60) within 300s tolerance stays allowed
        res_skew = self._check(t0 - 60, update_state=True)
        self.assertTrue(res_skew.allowed)

        # Large rollback (-3600s) -> blocked
        res_back = self._check(t0 - 3600, update_state=True)
        self.assertFalse(res_back.allowed)
        self.assertEqual(res_back.status, cgui_license.STATUS_TAMPERED)

        # Clock restored -> allowed again
        res_restored = self._check(t0 + 120, update_state=True)
        self.assertTrue(res_restored.allowed)

        # Corrupt state file -> blocked
        with open(state_file, "wb") as f:
            f.write(b"corrupted-tampered-bytes" * 4)
        res_corrupt = self._check(t0 + 180, update_state=True)
        self.assertFalse(res_corrupt.allowed)
        self.assertEqual(res_corrupt.status, cgui_license.STATUS_TAMPERED)

    def test_detect_host_domains_from_resolv_and_nis(self):
        resolv = os.path.join(self.tmp.name, "resolv.conf")
        domf = os.path.join(self.tmp.name, "domainname")
        with open(resolv, "w", encoding="utf-8") as f:
            f.write("# comment\nnameserver 10.0.0.1\nsearch sirius sirius-wireless.com\n")
        with open(domf, "w", encoding="utf-8") as f:
            f.write("sirius\n")
        with mock.patch.object(cgui_license.socket, "getfqdn", return_value="sirius07"), \
             mock.patch.object(cgui_license.socket, "gethostname", return_value="sirius07"):
            domains = cgui_license.detect_host_domains(
                resolv_conf_path=resolv, domainname_path=domf
            )
        self.assertEqual(domains, ["sirius", "sirius-wireless.com"])

    def test_domain_enforcement_rules(self):
        self.assertFalse(cgui_license.ENFORCE_DOMAIN)
        expire = (self.base_dt.date() + datetime.timedelta(days=60)).strftime("%Y-%m-%d")
        _issue_temp_lic(self.priv, self.lic_path, expire, domain="sirius-wireless.com")

        def _check_dom(hosts):
            return cgui_license.check_license(
                now=self.base_dt,
                update_state=False,
                license_file=self.lic_path,
                state_dir=self.state_dir,
                public_key=self.pub,
                enforce_domain=True,
                host_domains=hosts,
            )

        # Exact, subdomain, and case-insensitive / trailing-dot matches
        self.assertTrue(_check_dom(["sirius", "sirius-wireless.com"]).allowed)
        self.assertTrue(_check_dom(["rd.sirius-wireless.com"]).allowed)
        self.assertTrue(_check_dom(["SIRIUS-WIRELESS.COM."]).allowed)

        # Spoofed suffix, wrong domain, and empty host domains -> blocked
        for bad_hosts in (["evil-sirius-wireless.com"], ["othercorp.com"], []):
            res = _check_dom(bad_hosts)
            self.assertFalse(res.allowed)
            self.assertEqual(res.status, cgui_license.STATUS_DOMAIN_MISMATCH)

        # Empty domain in license -> fail closed when enforcement enabled
        empty_lic = os.path.join(self.tmp.name, "empty_dom.lic")
        _issue_temp_lic(self.priv, empty_lic, expire, domain="")
        res_empty = cgui_license.check_license(
            now=self.base_dt, update_state=False, license_file=empty_lic,
            state_dir=self.state_dir, public_key=self.pub,
            enforce_domain=True, host_domains=["sirius-wireless.com"],
        )
        self.assertFalse(res_empty.allowed)
        self.assertEqual(res_empty.status, cgui_license.STATUS_DOMAIN_MISMATCH)

        # Wildcard '*' allows any host
        star_lic = os.path.join(self.tmp.name, "star_dom.lic")
        _issue_temp_lic(self.priv, star_lic, expire, domain="*")
        res_star = cgui_license.check_license(
            now=self.base_dt, update_state=False, license_file=star_lic,
            state_dir=self.state_dir, public_key=self.pub,
            enforce_domain=True, host_domains=[],
        )
        self.assertTrue(res_star.allowed)
        self.assertEqual(res_star.status, cgui_license.STATUS_OK)


class TestSubprocessCLI(unittest.TestCase):
    _VER = config.latest_revision()
    BIN_PATH = os.path.join(ROOT, "dist", _VER, "libexec", "pvflow.bin")
    WRAPPER_PATH = os.path.join(ROOT, "dist", _VER, "bin", "pvflow")
    PRIV_KEY_PATH = os.path.join(ROOT, "lic_issuer", "keys", "private_key.pem")

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(cls.PRIV_KEY_PATH):
            raise unittest.SkipTest("Vendor private_key.pem not present in checkout")
        with open(cls.PRIV_KEY_PATH, "rb") as f:
            cls.priv = serialization.load_pem_private_key(f.read(), password=None)

    def _run_target(self, cmd, tmp_dir, lic_path=None):
        env = dict(os.environ)
        env["HOME"] = tmp_dir
        env["PVFLOW_USER_DIR"] = os.path.join(tmp_dir, "pvflow_user")
        env["PVFLOW_LIC_STATE_DIR"] = os.path.join(tmp_dir, "lic_state")
        env["DISPLAY"] = ""
        env.pop("CADSEMI_LICENSE_FILE", None)
        env.pop("CTMP_LICENSE_FILE", None)
        if lic_path is not None:
            env["CADSEMI_LICENSE_FILE"] = lic_path
        return subprocess.run(cmd, env=env, cwd=ROOT, capture_output=True, text=True)

    def _targets(self):
        targets = [[sys.executable, os.path.join(ROOT, "cgui.py")]]
        if os.path.isfile(self.BIN_PATH) and os.access(self.BIN_PATH, os.X_OK):
            targets.append([self.BIN_PATH])
        if os.path.isfile(self.WRAPPER_PATH) and os.access(self.WRAPPER_PATH, os.X_OK):
            targets.append([self.WRAPPER_PATH])
        return targets

    def test_compiled_binary_exists_and_clean(self):
        self.assertTrue(
            os.path.isfile(self.BIN_PATH) and os.access(self.BIN_PATH, os.X_OK),
            "Compiled binary missing: %s" % self.BIN_PATH,
        )
        dist_dir = os.path.dirname(os.path.dirname(self.BIN_PATH))
        for dp, dirs, files in os.walk(dist_dir):
            self.assertNotIn("lic_issuer", dirs)
            for fn in files:
                self.assertFalse(fn.endswith(".py"), "Unexpected .py in dist: %s" % fn)
                self.assertFalse(fn.endswith(".pem"), "Unexpected .pem in dist: %s" % fn)
                self.assertFalse(fn.endswith(".lic"), "Unexpected .lic in dist: %s" % fn)

    def test_end_to_end_scenarios(self):
        today = datetime.date.today()
        for cmd_prefix in self._targets():
            with self.subTest(target=cmd_prefix[0]):
                with tempfile.TemporaryDirectory() as tmp:
                    lic_ok = os.path.join(tmp, "ok.lic")
                    _issue_temp_lic(
                        self.priv, lic_ok,
                        (today + datetime.timedelta(days=60)).strftime("%Y-%m-%d"),
                    )
                    r = self._run_target(cmd_prefix + ["-L"], tmp, lic_ok)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertIn("Status      : OK", r.stdout)
                    self.assertIn("ctmp", r.stdout)

                    r_eng = self._run_target(cmd_prefix + ["-e", "-P"], tmp, lic_ok)
                    self.assertEqual(r_eng.returncode, 0, r_eng.stderr)
                    self.assertIn("demo_process", r_eng.stdout)

                    # Expiring soon (15 days left) -> allowed + plain notice
                    lic_warn = os.path.join(tmp, "warn.lic")
                    exp_warn = (today + datetime.timedelta(days=15)).strftime("%Y-%m-%d")
                    _issue_temp_lic(self.priv, lic_warn, exp_warn)
                    r_w = self._run_target(cmd_prefix + ["-e", "-P"], tmp, lic_warn)
                    self.assertEqual(r_w.returncode, 0, r_w.stderr)
                    self.assertIn("[Notice] License will expire on %s" % exp_warn, r_w.stderr)

                    # Grace period (5 days past expiry) -> allowed + grace warning
                    lic_grace = os.path.join(tmp, "grace.lic")
                    exp_grace = (today - datetime.timedelta(days=5)).strftime("%Y-%m-%d")
                    _issue_temp_lic(self.priv, lic_grace, exp_grace)
                    r_g = self._run_target(cmd_prefix + ["-e", "-P"], tmp, lic_grace)
                    self.assertEqual(r_g.returncode, 0, r_g.stderr)
                    self.assertIn("[Warning] License expired on %s" % exp_grace, r_g.stderr)

                    # Hard expired (30 days past expiry) -> blocked (exit 3)
                    lic_exp = os.path.join(tmp, "expired.lic")
                    exp_old = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
                    _issue_temp_lic(self.priv, lic_exp, exp_old)
                    r_x = self._run_target(cmd_prefix + ["-e", "-P"], tmp, lic_exp)
                    self.assertEqual(r_x.returncode, 3)
                    self.assertIn("License expired on %s" % exp_old, r_x.stderr)

                    # Tampered .lic -> blocked (exit 3)
                    lic_bad = os.path.join(tmp, "tampered.lic")
                    with open(lic_ok, "r", encoding="utf-8") as f:
                        doc = json.load(f)
                    doc["payload"]["customer"] = "EvilCorp"
                    with open(lic_bad, "w", encoding="utf-8") as f:
                        json.dump(doc, f)
                    r_t = self._run_target(cmd_prefix + ["-e", "-P"], tmp, lic_bad)
                    self.assertEqual(r_t.returncode, 3)
                    self.assertIn("signature verification failed", r_t.stderr)

                    # Missing .lic -> blocked (exit 3)
                    r_m = self._run_target(
                        cmd_prefix + ["-e", "-P"],
                        tmp,
                        os.path.join(tmp, "does_not_exist.lic"),
                    )
                    self.assertEqual(r_m.returncode, 3)
                    self.assertIn("CADSEMI_LICENSE_FILE", r_m.stderr)

                    # Clock rollback against seeded future state -> blocked (exit 3)
                    state_rb = os.path.join(tmp, "lic_state_rb")
                    cgui_license._write_anti_tamper(
                        int(time.time()) + 7200,
                        cgui_license.get_embedded_public_key(),
                        state_dir=state_rb,
                    )
                    env_rb = dict(os.environ)
                    env_rb["HOME"] = tmp
                    env_rb["PVFLOW_USER_DIR"] = os.path.join(tmp, "pvflow_user")
                    env_rb["PVFLOW_LIC_STATE_DIR"] = state_rb
                    env_rb["DISPLAY"] = ""
                    env_rb.pop("CTMP_LICENSE_FILE", None)
                    env_rb["CADSEMI_LICENSE_FILE"] = lic_ok
                    r_rb = subprocess.run(
                        cmd_prefix + ["-e", "-P"],
                        env=env_rb,
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(r_rb.returncode, 3)
                    self.assertIn("rollback", r_rb.stderr.lower())

                    # Domain-labeled license allowed on non-matching host when ENFORCE_DOMAIN is False
                    lic_dom = os.path.join(tmp, "sirius.lic")
                    _issue_temp_lic(
                        self.priv, lic_dom, "2036-11-20", domain="sirius-wireless.com"
                    )
                    r_dom = self._run_target(cmd_prefix + ["-e", "-P"], tmp, lic_dom)
                    self.assertEqual(r_dom.returncode, 0)
                    self.assertIn("demo_process", r_dom.stdout)


class TestGuiSmoke(unittest.TestCase):
    def test_cadsemi_branding(self):
        self.assertEqual(config.LOGO_TEXT, "cadsemi")
        sys_txt = os.path.join(ROOT, "data", "system.txt")
        with open(sys_txt, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        self.assertEqual(first_line, "pvflow @cadsemi")
        self.assertEqual(config.latest_revision(), "26.11.001")

    def test_simplified_drc_trial_config_and_scripts(self):
        self.assertEqual(config.MENU_ITEMS, ["DRC", "SYSTEM"])
        self.assertEqual(config.VERIFY_MODULES, ["DRC"])
        title = config.window_title()
        self.assertTrue(title.startswith("pvflow"))
        self.assertNotIn("Cadsemi", title)
        self.assertNotIn(" - ", title)
        self.assertNotIn("t22_1p7m_4x1z1u", title)

    @unittest.skipUnless(os.environ.get("DISPLAY"), "No DISPLAY available for Tk smoke test")
    def test_gui_status_bar_and_system_page(self):
        if not os.path.isfile(TestSubprocessCLI.PRIV_KEY_PATH):
            self.skipTest("Vendor private_key.pem not present in checkout")
        import cgui_app
        with open(TestSubprocessCLI.PRIV_KEY_PATH, "rb") as f:
            priv = serialization.load_pem_private_key(f.read(), password=None)

        today = datetime.date.today()
        with tempfile.TemporaryDirectory() as tmp:
            old_user_dir = config.USER_DIR
            config.USER_DIR = os.path.join(tmp, "pvflow_user")
            try:
                lic_warn = os.path.join(tmp, "warn.lic")
                _issue_temp_lic(
                    priv, lic_warn,
                    (today + datetime.timedelta(days=10)).strftime("%Y-%m-%d"),
                    customer="cadsemi",
                )
                with mock.patch.dict(os.environ, {
                    "CADSEMI_LICENSE_FILE": lic_warn,
                    "PVFLOW_LIC_STATE_DIR": os.path.join(tmp, "state"),
                }):
                    os.environ.pop("CTMP_LICENSE_FILE", None)
                    res = cgui_license.check_license(update_state=False)
                    self.assertEqual(res.status, cgui_license.STATUS_EXPIRING)
                    app = cgui_app.CGui(license_result=res)
                    try:
                        app.withdraw()
                        app.update_idletasks()
                        # Always starts on Home tab, with top-right cadsemi & 6 menus
                        self.assertEqual(app.current_module.get(), "HOME")
                        self.assertEqual(len(app._tabs), 1)
                        self.assertEqual(app._brand_label.cget("text"), "cadsemi")
                        self.assertEqual(
                            list(app._menus.keys()),
                            ["File", "Tools", "Options", "Window", "License", "Help"],
                        )
                        self.assertTrue(app.title().startswith("pvflow"))
                        self.assertNotIn("Cadsemi", app.title())
                        self.assertNotIn("t22_1p7m_4x1z1u", app.title())
                        self.assertEqual(app.cget("bg"), config.THEME["bg"])
                        self.assertEqual(app._lic_bar.cget("bg"), config.THEME["warn_bg"])
                        self.assertTrue(app._lic_bar_packed)

                        def _menu_labels(menu):
                            end = menu.index("end")
                            if end is None:
                                return []
                            out = []
                            for idx in range(end + 1):
                                if menu.type(idx) != "separator":
                                    out.append(menu.entrycget(idx, "label"))
                            return out

                        home_page = app._pages["HOME"]
                        self.assertEqual(home_page.heading_lbl.cget("text"), "PVFlow")
                        self.assertEqual(home_page.tools_lbl.cget("text"), "Tools")
                        self.assertEqual(home_page.app_tiles["Help"].sub_lbl.cget("text"), "User Guide")

                        # Offline User Guide exists and Help tile / Help -> PVFlow Help opens it via browser
                        guide_path = app.user_guide_path()
                        self.assertTrue(os.path.isfile(guide_path))
                        self.assertTrue(guide_path.endswith(os.path.join("data", "help", "index.html")))
                        help_menu = app.nametowidget(app._menus["Help"].cget("menu"))
                        self.assertEqual(
                            _menu_labels(help_menu),
                            ["PVFlow Help", "About PVFlow"],
                        )
                        tools_menu = app.nametowidget(app._menus["Tools"].cget("menu"))
                        self.assertEqual(
                            _menu_labels(tools_menu),
                            [
                                "DRC Verification",
                                "GDS Viewer",
                                "LVS (Custom on request)",
                                "XRC (Custom on request)",
                                "Terminal",
                            ],
                        )

                        # About CGUI dialog + Legal Notices sub-dialog
                        app._show_about()
                        self.assertIsNotNone(app._about_win)
                        self.assertTrue(app._about_win.winfo_exists())
                        app._about_win._notices_btn.invoke()
                        self.assertIsNotNone(app._notices_win)
                        self.assertTrue(app._notices_win.winfo_exists())
                        notices_txt = app._notices_win._text.get("1.0", "end")
                        self.assertIn("Siemens", notices_txt)
                        self.assertIn("KLayout", notices_txt)
                        app._notices_win._ok_btn.invoke()
                        app._about_win._ok_btn.invoke()
                        self.assertIsNone(app._notices_win)
                        self.assertIsNone(app._about_win)
                        with mock.patch.object(
                            cgui_app.shutil, "which",
                            side_effect=lambda cmd: (
                                "/usr/bin/" + cmd if cmd in ("google-chrome", "xdg-open", "firefox") else None
                            ),
                        ), mock.patch.object(cgui_app.subprocess, "Popen") as m_popen:
                            home_page.app_tiles["Help"]._on_click()
                            self.assertTrue(m_popen.called)
                            cmd_arg = m_popen.call_args[0][0]
                            self.assertEqual(cmd_arg[0], "/usr/bin/google-chrome")
                            self.assertTrue(cmd_arg[1].startswith("file://"))
                            self.assertTrue(cmd_arg[1].endswith("/data/help/index.html"))
                        with mock.patch.object(
                            cgui_app.shutil, "which",
                            side_effect=lambda cmd: (
                                "/usr/bin/" + cmd if cmd in ("xdg-open", "firefox") else None
                            ),
                        ), mock.patch.object(cgui_app.subprocess, "Popen") as m_popen:
                            app.open_user_guide()
                            self.assertTrue(m_popen.called)
                            self.assertEqual(m_popen.call_args[0][0][0], "/usr/bin/xdg-open")
                        with mock.patch.object(
                            cgui_app.shutil, "which",
                            side_effect=lambda cmd: "/usr/bin/firefox" if cmd == "firefox" else None,
                        ), mock.patch.object(cgui_app.subprocess, "Popen") as m_popen:
                            app.open_user_guide()
                            self.assertTrue(m_popen.called)
                            self.assertEqual(m_popen.call_args[0][0][0], "/usr/bin/firefox")
                            kw = m_popen.call_args[1]
                            self.assertEqual(kw["env"].get("MOZ_WEBRENDER"), "0")
                            self.assertEqual(kw["stdin"], cgui_app.subprocess.DEVNULL)
                        app._rebuild_file_menu()
                        home_file_labels = _menu_labels(app._file_menu)
                        self.assertEqual(home_file_labels, ["Recent Runs", "Close Current Tab", "Quit"])
                        self.assertEqual(_menu_labels(app._recent_menu), ["(No recent runs)"])
                        app.record_recent_run({
                            "LayoutPath": "/proj/demo/top.gds",
                            "LayoutPrimary": "top",
                            "RunFolder": "/proj/demo/run_drc",
                        })
                        app._rebuild_recent_menu()
                        rec_labels = _menu_labels(app._recent_menu)
                        self.assertTrue(any("top.gds" in lbl for lbl in rec_labels))
                        self.assertIn("Clear Recent Runs", rec_labels)
                        app._clear_recent_runs()
                        self.assertEqual(_menu_labels(app._recent_menu), ["(No recent runs)"])

                        app._rebuild_window_menu()
                        win_labels = _menu_labels(app._window_menu)
                        for expected in ("New Window", "New Tab", "Full Screen",
                                         "Keyboard Shortcuts...", "\u2022 1 Home"):
                            self.assertIn(expected, win_labels)

                        # Options radiobutton vars stay in sync
                        app._set_font_px(17)
                        self.assertEqual(app._font_var.get(), 17)
                        app._set_font_px(15)
                        app._set_editor("gedit")
                        self.assertEqual(app._editor_var.get(), "gedit")
                        app._set_editor("gvim")

                        self.assertEqual(
                            list(home_page.app_tiles.keys()),
                            ["DRC", "GdsViewer", "LVS", "XRC", "Help"],
                        )
                        self.assertTrue(home_page.app_tiles["DRC"].enabled)
                        self.assertEqual(home_page.app_tiles["DRC"].sub_lbl.cget("text"), "DRC Verification")
                        self.assertTrue(home_page.app_tiles["GdsViewer"].enabled)
                        self.assertFalse(home_page.app_tiles["LVS"].enabled)
                        self.assertFalse(home_page.app_tiles["XRC"].enabled)
                        self.assertEqual(home_page.app_tiles["LVS"].sub_lbl.cget("text"), "Custom on request")
                        self.assertEqual(home_page.app_tiles["XRC"].sub_lbl.cget("text"), "Custom on request")
                        self.assertTrue(home_page.app_tiles["Help"].enabled)

                        # Synopsys Custom Compiler tab flow:
                        # [Home] -> DRC tile -> [DRC 1] -> "+" -> [DRC 1, Home] -> DRC -> [DRC 1, DRC 2]
                        self.assertEqual([t["title"] for t in app._tabs], ["Home"])
                        home_page.app_tiles["DRC"]._on_click()
                        app.update_idletasks()
                        self.assertEqual([t["title"] for t in app._tabs], ["DRC 1"])
                        drc1 = app._pages["DRC"]

                        app._rebuild_file_menu()
                        drc_file_labels = _menu_labels(app._file_menu)
                        self.assertEqual(
                            drc_file_labels,
                            ["Open Cmd...", "Save Cmd...", "Recent Runs", "Close Current Tab", "Quit"],
                        )

                        app._add_tab_btn.invoke()
                        app.update_idletasks()
                        self.assertEqual([t["title"] for t in app._tabs], ["DRC 1", "Home"])
                        self.assertEqual(app.current_module.get(), "HOME")

                        app._pages["HOME"].app_tiles["DRC"]._on_click()
                        app.update_idletasks()
                        self.assertEqual([t["title"] for t in app._tabs], ["DRC 1", "DRC 2"])
                        drc2 = app._pages["DRC"]
                        self.assertIsNot(drc1, drc2)

                        # Proportional tab shrinking keeps "+" visible as many tabs open
                        w2, _, ov2 = app._compute_tab_width(800, 2)
                        w15, _, ov15 = app._compute_tab_width(800, 15)
                        w40, _, ov40 = app._compute_tab_width(800, 40)
                        self.assertEqual(w2, 136)
                        self.assertFalse(ov2)
                        self.assertLess(w15, 60)
                        self.assertFalse(ov15)
                        self.assertEqual(w40, 26)
                        self.assertTrue(ov40)

                        # Closing all tabs leaves a fresh Home tab
                        for tid in [t["id"] for t in list(app._tabs)]:
                            app.close_tab(tid)
                        app.update_idletasks()
                        self.assertEqual([t["title"] for t in app._tabs], ["Home"])

                        # Opening 15 tabs shrinks each tab cleanly while keeping "+" alive
                        for _ in range(14):
                            app._add_tab_btn.invoke()
                        app.update_idletasks()
                        self.assertEqual(len(app._tabs), 15)
                        self.assertLess(app._last_tab_width, 100)
                        self.assertTrue(app._add_tab_btn.winfo_exists())
                        for tid in [t["id"] for t in list(app._tabs)][:-1]:
                            app.close_tab(tid)
                        app.update_idletasks()

                        app.show_module("DRC")
                        app.update_idletasks()
                        drc_page = app._pages["DRC"]
                        self.assertEqual(drc_page._com_filename(), "calibre_drc.com")
                        self.assertEqual(drc_page._terminal_title(), ".cgui_run.sh - DRC")
                        drc_sh = drc_page._run_script_drc()
                        self.assertTrue(drc_sh.startswith("#!/bin/bash\n"))
                        self.assertNotIn("module load", drc_sh)
                        self.assertIn("calibre -64 -drc", drc_sh)
                        rve_sh = drc_page._run_script_rve()
                        self.assertTrue(rve_sh.startswith("#!/bin/bash\n"))
                        self.assertNotIn("module load", rve_sh)
                        self.assertIn("calibre -rve", rve_sh)

                        # Button row: Run / RunRve (LoadCmd/SaveCmd moved solely under File menu)
                        import tkinter as tk
                        texts = {}

                        def _walk(w):
                            for c in w.winfo_children():
                                if isinstance(c, tk.Button):
                                    texts[c.cget("text")] = c
                                _walk(c)
                        _walk(drc_page)
                        for t in ("Run", "RunRve", "Edit"):
                            self.assertIn(t, texts)
                        for t in ("LoadCmd", "SaveCmd", "LoadDefault", "Rve", "Load", "Save"):
                            self.assertNotIn(t, texts)
                        self.assertEqual(texts["Run"].cget("bg"), config.THEME["btn_bg"])
                        self.assertEqual(texts["Run"].cget("fg"), config.THEME["btn_fg"])
                        self.assertEqual(texts["RunRve"].cget("bg"), config.THEME["card"])

                        # CmdFile -> include "<path>" with DRC ICSTATION YES right above
                        self.assertIn("CmdFile", drc_page.entries)
                        init_lines = drc_page.cmd_text.get_text().split("\n")
                        self.assertIn('include ""', init_lines)
                        drc_page._fill_entry("CmdFile", "/path/calibre.drc")
                        drc_page._on_field_change("CmdFile")
                        drc_page._on_field_change("CmdFile")   # idempotent
                        lines = drc_page.cmd_text.get_text().split("\n")
                        idx = lines.index('include "/path/calibre.drc"')
                        self.assertEqual(lines[idx - 1], "DRC ICSTATION YES")
                        self.assertEqual(
                            sum(1 for l in lines if l.strip().lower().startswith("include")), 1)
                        self.assertEqual(lines.count("DRC ICSTATION YES"), 1)
                        self.assertFalse(any("//" in l and "include" in l for l in lines))

                        # Editing the include line in the text updates CmdFile
                        lines[idx] = 'include "/other/rules.drc"'
                        drc_page.cmd_text.set_text("\n".join(lines))
                        drc_page._on_text_change()
                        self.assertEqual(drc_page._entry("CmdFile"), "/other/rules.drc")

                        # An old session text (commented placeholder) is migrated
                        drc_page.cmd_text.set_text(
                            'LAYOUT PRIMARY "top"\n\n// include "/path/to/drc_rule_deck"\n')
                        drc_page._fill_entry("CmdFile", "/path/calibre.drc")
                        drc_page._refresh_include()
                        self.assertEqual(
                            drc_page.cmd_text.get_text().split("\n"),
                            ['LAYOUT PRIMARY "top"', "", "DRC ICSTATION YES",
                             'include "/path/calibre.drc"', ""])

                        app.show_module("SYSTEM")
                        app.update_idletasks()
                        self.assertIn("EXPIRING SOON",
                                      app._pages["SYSTEM"]._lic_panel.winfo_children()[1].cget("text"))
                        self.assertTrue(app.ensure_license("test run"))

                        # GdsViewer tab creation from "+" Home -> GdsViewer tile
                        app._add_tab_btn.invoke()
                        app.update_idletasks()
                        app._pages["HOME"].app_tiles["GdsViewer"]._on_click()
                        app.update_idletasks()
                        self.assertEqual(app.current_module.get(), "GDSVIEWER")
                        gds_page = app._pages["GDSVIEWER"]
                        gds_sample = os.path.join(tmp, "sample.gds")
                        _write_minimal_gds(gds_sample)
                        gds_page._set_entry("LayoutFile", gds_sample)
                        gds_page._on_scan_cells()
                        self.assertEqual(gds_page._entry("TopCell"), "TOP_CELL")
                        items = list(gds_page.cell_list.get(0, "end"))
                        self.assertIn("* TOP_CELL", items)
                        self.assertIn("  SUB_CELL", items)

                        # License -> Select License File... persists path & resolves without env var
                        lic_picked = os.path.join(tmp, "picked.lic")
                        _issue_temp_lic(
                            priv, lic_picked,
                            (today + datetime.timedelta(days=45)).strftime("%Y-%m-%d"),
                            customer="cadsemi",
                        )
                        with mock.patch.object(cgui_app.filedialog, "askopenfilename", return_value=lic_picked), \
                             mock.patch.object(cgui_app.messagebox, "showinfo") as m_info:
                            app._select_license_file()
                            self.assertTrue(m_info.called)
                            self.assertEqual(app.license_result.license_path, lic_picked)
                            self.assertEqual(app.license_result.status, cgui_license.STATUS_OK)
                            self.assertEqual(app._saved_license_file, lic_picked)
                            self.assertFalse(app._lic_bar_packed)
                        with mock.patch.dict(os.environ, {}, clear=False):
                            os.environ.pop("CADSEMI_LICENSE_FILE", None)
                            os.environ.pop("CTMP_LICENSE_FILE", None)
                            res_saved = cgui_license.check_license(
                                update_state=False, public_key=priv.public_key().public_bytes(
                                    serialization.Encoding.Raw, serialization.PublicFormat.Raw
                                ),
                            )
                            self.assertEqual(res_saved.license_path, lic_picked)

                        # Grace period popup check
                        lic_grace = os.path.join(tmp, "grace.lic")
                        _issue_temp_lic(
                            priv, lic_grace,
                            (today - datetime.timedelta(days=3)).strftime("%Y-%m-%d"),
                            customer="cadsemi",
                        )
                        os.environ["CADSEMI_LICENSE_FILE"] = lic_grace
                        with mock.patch.object(cgui_app.messagebox, "showwarning") as m_warn:
                            res_g = cgui_license.check_license(update_state=False)
                            app2 = cgui_app.CGui(license_result=res_g)
                            app2.withdraw()
                            app2._show_grace_popup()
                            app2.update_idletasks()
                            self.assertEqual(app2._lic_bar.cget("bg"), config.THEME["grace_bg"])
                            self.assertTrue(app2._lic_bar_packed)
                            self.assertTrue(m_warn.called)
                            app2._on_close()

                        # Fresh startup with valid STATUS_OK keeps bottom license bar hidden
                        app_ok = cgui_app.CGui(license_result=res_saved)
                        app_ok.withdraw()
                        app_ok.update_idletasks()
                        self.assertFalse(app_ok._lic_bar_packed)
                        app_ok._on_close()
                    finally:
                        try:
                            if app.winfo_exists():
                                app._on_close()
                        except Exception:
                            pass
            finally:
                config.USER_DIR = old_user_dir


def _gds_rec(rec_id, payload=b""):
    if len(payload) % 2:
        payload += b"\x00"
    import struct
    return struct.pack(">HH", 4 + len(payload), rec_id) + payload


def _write_minimal_gds(path, gzipped=False):
    raw = b"".join([
        _gds_rec(0x0002, b"\x02\x58"),             # HEADER
        _gds_rec(0x0206, b"LIB1"),                 # LIBNAME
        _gds_rec(0x0502, b"\x00" * 24),            # BGNSTR
        _gds_rec(0x0606, b"TOP_CELL"),             # STRNAME TOP_CELL
        _gds_rec(0x0A00),                          # SREF
        _gds_rec(0x1206, b"SUB_CELL"),             # SNAME SUB_CELL
        _gds_rec(0x1100),                          # ENDEL
        _gds_rec(0x0700),                          # ENDSTR
        _gds_rec(0x0502, b"\x00" * 24),            # BGNSTR
        _gds_rec(0x0606, b"SUB_CELL"),             # STRNAME SUB_CELL
        _gds_rec(0x0700),                          # ENDSTR
        _gds_rec(0x0400),                          # ENDLIB
    ])
    if gzipped:
        import gzip
        with gzip.open(path, "wb") as f:
            f.write(raw)
    else:
        with open(path, "wb") as f:
            f.write(raw)


class TestGdsViewer(unittest.TestCase):
    def test_scan_gds_cells_and_layermap_and_fallback(self):
        from pages import gdsview
        with tempfile.TemporaryDirectory() as tmp:
            gds_plain = os.path.join(tmp, "top.gds")
            gds_gz = os.path.join(tmp, "top.gds.gz")
            _write_minimal_gds(gds_plain, gzipped=False)
            _write_minimal_gds(gds_gz, gzipped=True)

            for p in (gds_plain, gds_gz):
                tops, all_c = gdsview.scan_gds_cells(p)
                self.assertEqual(tops, ["TOP_CELL"])
                self.assertEqual(all_c, ["TOP_CELL", "SUB_CELL"])

            # Virtuoso .layermap -> KLayout XML .lyp
            lmap = os.path.join(tmp, "tech.layermap")
            with open(lmap, "w", encoding="utf-8") as f:
                f.write("# comment\n// ignore\nM1 drawing 10 0\nVIA1 pin 11 2\n")
            lyp = gdsview.layermap_to_lyp(lmap, out_path=os.path.join(tmp, "tech.lyp"))
            with open(lyp, "r", encoding="utf-8") as f:
                xml_txt = f.read()
            self.assertIn("<name>M1/drawing</name>", xml_txt)
            self.assertIn("<source>10/0@1</source>", xml_txt)
            self.assertIn("<name>VIA1/pin</name>", xml_txt)
            self.assertIn("<source>11/2@1</source>", xml_txt)

            # 3-tier KLayout fallback (<APP_DIR>/tools/klayout/klayout)
            fake_app = os.path.join(tmp, "dist_app")
            fake_bin = os.path.join(fake_app, "tools", "klayout", "klayout")
            os.makedirs(os.path.dirname(fake_bin), exist_ok=True)
            with open(fake_bin, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\n")
            os.chmod(fake_bin, 0o755)
            with mock.patch.dict(os.environ, {"CGUI_KLAYOUT": "", "PATH": ""}):
                with mock.patch.object(config, "APP_DIR", fake_app), \
                     mock.patch.object(config, "BASE_DIR", fake_app):
                    self.assertEqual(gdsview.find_klayout(), fake_bin)


class TestTerminalOutput(unittest.TestCase):
    def test_terminal_notice_uses_default_color(self):
        res = cgui_license.LicenseResult(
            allowed=True,
            status=cgui_license.STATUS_EXPIRING,
            notice="[Notice] License will expire on 2026-11-30.",
        )
        with mock.patch.object(sys.stderr, "isatty", return_value=True):
            out = cgui_license.format_terminal_notice(res)
        self.assertEqual(out, res.notice)
        self.assertNotIn("\033[", out)

    def test_format_eda_tool_status_found_and_missing(self):
        import cgui_app
        with mock.patch.dict(os.environ, {"LOADEDMODULES": "calibre/2024.1_36.20:other/1.0"}):
            with mock.patch.object(cgui_app.shutil, "which", return_value="/eda/calibre/bin/calibre"), \
                 mock.patch("pages.gdsview.find_klayout", return_value="/usr/bin/klayout"):
                out = cgui_app.format_eda_tool_status()
        self.assertIn("[Tool] calibre : OK (/eda/calibre/bin/calibre, module: calibre/2024.1_36.20)", out)
        self.assertIn("[Tool] klayout : OK (/usr/bin/klayout)", out)

        with mock.patch.dict(os.environ, {"LOADEDMODULES": ""}):
            with mock.patch.object(cgui_app.shutil, "which", return_value=None), \
                 mock.patch("pages.gdsview.find_klayout", return_value=None):
                out_missing = cgui_app.format_eda_tool_status()
        self.assertIn("[Tool] calibre : NOT FOUND (not sourced or module loaded)", out_missing)
        self.assertIn("[Tool] klayout : NOT FOUND (not sourced or module loaded)", out_missing)


class TestEdaHierarchyAndUpwardLicense(unittest.TestCase):
    def test_upward_license_discovery_in_eda_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            vendor = os.path.join(tmp, "cadsemi")
            product = os.path.join(vendor, "pvflow")
            ver = os.path.join(product, "26.11.001")
            libexec = os.path.join(ver, "libexec")
            vendor_lic_dir = os.path.join(vendor, "license")
            os.makedirs(libexec, exist_ok=True)
            os.makedirs(vendor_lic_dir, exist_ok=True)

            vendor_lic = os.path.join(vendor_lic_dir, "cadsemi.lic")
            with open(vendor_lic, "w", encoding="utf-8") as f:
                f.write("{}")

            env_clean = dict(os.environ)
            env_clean.pop("CADSEMI_LICENSE_FILE", None)
            env_clean.pop("CTMP_LICENSE_FILE", None)
            old_user_dir = config.USER_DIR
            config.USER_DIR = os.path.join(tmp, "empty_user")
            try:
                with mock.patch.dict(os.environ, env_clean, clear=True), \
                     mock.patch.object(config, "INSTALL_DIR", ver), \
                     mock.patch.object(config, "APP_DIR", libexec), \
                     mock.patch.object(config, "BASE_DIR", libexec):
                    found, _, _ = cgui_license._resolve_license_path()
                    self.assertEqual(found, vendor_lic)

                    # Product-level license overrides vendor-level
                    prod_lic = os.path.join(product, "cadsemi.lic")
                    with open(prod_lic, "w", encoding="utf-8") as f:
                        f.write("{}")
                    found2, _, _ = cgui_license._resolve_license_path()
                    self.assertEqual(found2, prod_lic)

                    # Version-level license takes highest auto-discovery priority
                    ver_lic = os.path.join(ver, "cadsemi.lic")
                    with open(ver_lic, "w", encoding="utf-8") as f:
                        f.write("{}")
                    found3, _, _ = cgui_license._resolve_license_path()
                    self.assertEqual(found3, ver_lic)
            finally:
                config.USER_DIR = old_user_dir

    def test_current_symlink_release_detection_and_pending_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            product = os.path.join(tmp, "cadsemi", "pvflow")
            v1 = os.path.join(product, "26.11.001")
            v2 = os.path.join(product, "26.12.001")
            for v in (v1, v2):
                os.makedirs(os.path.join(v, "bin"), exist_ok=True)
                os.makedirs(os.path.join(v, "libexec"), exist_ok=True)
                with open(os.path.join(v, "bin", "pvflow"), "w", encoding="utf-8") as f:
                    f.write("#!/bin/bash\n")
            cur = os.path.join(product, "current")
            os.symlink("26.11.001", cur)

            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("PVFLOW_CURRENT_LINK", None)
                os.environ.pop("CGUI_CURRENT_LINK", None)
                with mock.patch.object(config, "INSTALL_DIR", v1), \
                     mock.patch.object(config, "APP_DIR", os.path.join(v1, "libexec")):
                    self.assertEqual(config.current_link(), cur)
                    self.assertEqual(config.running_release(), "26.11.001")
                    self.assertEqual(config.live_install_dir(), os.path.realpath(v1))
                    self.assertEqual(config.live_launcher(), os.path.join(os.path.realpath(v1), "bin", "pvflow"))
                    self.assertIsNone(config.pending_update())

                    # Flip current -> 26.12.001
                    os.unlink(cur)
                    os.symlink("26.12.001", cur)
                    upd = config.pending_update()
                    self.assertIsNotNone(upd)
                    self.assertEqual(upd[0], "26.11.001")
                    self.assertEqual(upd[1], "26.12.001")
                    self.assertEqual(config.live_launcher(), os.path.join(os.path.realpath(v2), "bin", "pvflow"))

    def test_pvflow_and_cgui_launchers_help(self):
        for script in ("pvflow", "cgui"):
            r = subprocess.run(
                [os.path.join(ROOT, script), "--help"],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("usage: pvflow", r.stdout)

    def test_eda_release_assembly_helpers_and_wrapper(self):
        import cgui_build_nuitka as builder
        with tempfile.TemporaryDirectory() as tmp:
            ver = os.path.join(tmp, "cadsemi", "pvflow", "26.11.001")
            bin_d = os.path.join(ver, "bin")
            libexec_d = os.path.join(ver, "libexec")
            etc_d = os.path.join(ver, "etc")
            os.makedirs(bin_d)
            os.makedirs(libexec_d)

            fake_bin = os.path.join(libexec_d, "pvflow.bin")
            with open(fake_bin, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\necho FAKE_BIN:$@\n")
            os.chmod(fake_bin, 0o755)

            launcher = os.path.join(bin_d, "pvflow")
            shutil.copy2(os.path.join(ROOT, "pvflow"), launcher)
            builder._pin_default_home(launcher, "/apps/cadsemi/pvflow/current")
            os.symlink("pvflow", os.path.join(bin_d, "cgui"))
            mod = builder._write_modulefile_example(etc_d, "26.11.001")
            readme = builder._write_release_readme(ver, "26.11.001")
            builder._audit_dist(ver)

            with open(mod, "r", encoding="utf-8") as f:
                self.assertEqual(f.readline().strip(), "#%Module1.0")
            with open(readme, "r", encoding="utf-8") as f:
                self.assertIn("pvflow_26.11.001_linux_x64.tar.gz", f.read())

            cur = os.path.join(tmp, "cadsemi", "pvflow", "current")
            os.symlink("26.11.001", cur)
            for name in ("pvflow", "cgui"):
                r = subprocess.run(
                    [os.path.join(cur, "bin", name), "-L"],
                    capture_output=True, text=True,
                )
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.strip(), "FAKE_BIN:-L")


if __name__ == "__main__":
    unittest.main()
