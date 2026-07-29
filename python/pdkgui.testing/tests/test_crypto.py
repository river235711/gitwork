#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The encryption used by the deploy build.

Nothing else in this suite exercises it -- the tests run against the source
checkout, where no .pdkc exist -- yet it is what every user actually runs, and
it is where the start-up time went.
"""

import hashlib
import struct
import unittest

import pdkcrypt
import pdk_pack

KEY = "a-test-key"
OTHER_KEY = "a-different-key"


class RoundTrip(unittest.TestCase):
    def test_what_goes_in_comes_out(self):
        for data in (b"", b"x", b"def f():\n    return 1\n" * 500):
            self.assertEqual(pdkcrypt.decrypt(pdkcrypt.encrypt(data, KEY), KEY), data)

    def test_the_output_does_not_show_the_source(self):
        source = "def secret_function():\n    return 'the answer'\n"
        blob = pdk_pack.pack_source(source, "x.py")
        self.assertNotIn(b"secret_function", blob)
        self.assertNotIn(b"def ", blob)
        self.assertTrue(blob.startswith(pdkcrypt.MAGIC))

    def test_another_key_cannot_read_it(self):
        blob = pdkcrypt.encrypt(b"private", KEY)
        with self.assertRaises(ValueError):
            pdkcrypt.decrypt(blob, OTHER_KEY)

    def test_a_tampered_file_is_refused(self):
        blob = bytearray(pdkcrypt.encrypt(b"private data here", KEY))
        blob[-40] ^= 0x01                      # flip a bit in the ciphertext
        with self.assertRaises(ValueError):
            pdkcrypt.decrypt(bytes(blob), KEY)

    def test_something_else_entirely_is_refused(self):
        for junk in (b"", b"not a pdkc file at all", b"PDKC" + b"\x00" * 10):
            with self.assertRaises(ValueError):
                pdkcrypt.decrypt(junk, KEY)


class BuildSalt(unittest.TestCase):
    """A build shares one salt so the key is derived once, but each file must
    still get its own nonce -- reusing a keystream would leak the plaintext."""

    def test_files_of_one_build_share_the_salt_but_not_the_nonce(self):
        salt = pdkcrypt.new_salt()
        blobs = [pdkcrypt.encrypt(b"module %d" % i, KEY, salt=salt) for i in range(4)]
        salts = {self._field(b, "salt") for b in blobs}
        nonces = {self._field(b, "nonce") for b in blobs}
        self.assertEqual(len(salts), 1, "the build did not share one salt")
        self.assertEqual(len(nonces), 4, "a nonce was reused between files")

    def test_the_key_is_derived_once_for_a_whole_build(self):
        salt = pdkcrypt.new_salt()
        blobs = [pdkcrypt.encrypt(b"module %d" % i, KEY, salt=salt) for i in range(6)]

        pdkcrypt._key_cache.clear()
        calls = self._count_derivations()
        for blob in blobs:
            pdkcrypt.decrypt(blob, KEY)
        self.assertEqual(calls["n"], 1,
                         "derived the key %d times for one build" % calls["n"])

    def test_a_different_build_derives_its_own_key(self):
        one = pdkcrypt.encrypt(b"build one", KEY, salt=pdkcrypt.new_salt())
        two = pdkcrypt.encrypt(b"build two", KEY, salt=pdkcrypt.new_salt())

        pdkcrypt._key_cache.clear()
        calls = self._count_derivations()
        pdkcrypt.decrypt(one, KEY)
        pdkcrypt.decrypt(two, KEY)
        self.assertEqual(calls["n"], 2)

    @staticmethod
    def _field(blob, which):
        start = len(pdkcrypt.MAGIC) + 1 + pdkcrypt._ITERS_LEN
        if which == "salt":
            return blob[start:start + pdkcrypt._SALT_LEN]
        return blob[start + pdkcrypt._SALT_LEN:
                    start + pdkcrypt._SALT_LEN + pdkcrypt._NONCE_LEN]

    def _count_derivations(self):
        calls = {"n": 0}
        real = hashlib.pbkdf2_hmac

        def counting(*a, **kw):
            calls["n"] += 1
            return real(*a, **kw)

        self.addCleanup(setattr, hashlib, "pbkdf2_hmac", real)
        hashlib.pbkdf2_hmac = counting
        return calls


class OlderBuilds(unittest.TestCase):
    """Version 1 files predate the iteration count being recorded. Builds made
    before that must keep working, and say so clearly if they cannot."""

    def test_a_version_1_file_still_decrypts(self):
        blob = self._make_v1(b"packed by the old build", KEY)
        self.assertEqual(blob[len(pdkcrypt.MAGIC)], 1)
        self.assertEqual(pdkcrypt.decrypt(blob, KEY), b"packed by the old build")

    def test_a_version_from_the_future_is_reported(self):
        blob = bytearray(pdkcrypt.encrypt(b"x", KEY))
        blob[len(pdkcrypt.MAGIC)] = 99
        with self.assertRaises(ValueError) as caught:
            pdkcrypt.decrypt(bytes(blob), KEY)
        self.assertIn("version", str(caught.exception))

    @staticmethod
    def _make_v1(plaintext, key):
        """Build a file in the old format, the way the previous code did."""
        import hmac
        import os
        salt, nonce = os.urandom(16), os.urandom(16)
        enc, mac = pdkcrypt._derive_keys(key, salt, pdkcrypt.LEGACY_KDF_ITERS)
        ciphertext = pdkcrypt._xor(
            plaintext, pdkcrypt._keystream(enc, nonce, len(plaintext)))
        header = pdkcrypt.MAGIC + bytes([1]) + salt + nonce
        tag = hmac.new(mac, header + ciphertext, hashlib.sha256).digest()
        return header + ciphertext + tag


class Header(unittest.TestCase):
    def test_the_file_records_how_to_derive_its_own_key(self):
        blob = pdkcrypt.encrypt(b"x", KEY, iters=4321)
        start = len(pdkcrypt.MAGIC) + 1
        recorded = struct.unpack(">I", blob[start:start + pdkcrypt._ITERS_LEN])[0]
        self.assertEqual(recorded, 4321)
        self.assertEqual(pdkcrypt.decrypt(blob, KEY), b"x",
                         "the recorded count was not used to decrypt")


if __name__ == "__main__":
    unittest.main()
