"""Synthetic projects only: no customer data or credentials in fixtures."""
import base64
import hashlib
import io
import json
import unittest
import zipfile
from unittest.mock import patch

from nm_bridge.ets_archive import decode_upload, open_project
from nm_bridge.ets_import import preview

try:
    import pyzipper
except ImportError:
    pyzipper = None

PASSWORD = "Test-ETS-\u00e8-\U0001f512"
META = '<ProjectInformation Guid="12345678-1234-1234-1234-123456789abc" />'
XML = '<Project><GroupAddress Address="2305" Name="Luce test" /></Project>'


def project(password=None, schema=21, entries=None):
    entries = entries or {"0.xml": XML, "project.xml": META}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as outer:
        outer.writestr("knx_master.xml", f'<KNX xmlns="http://knx.org/xml/project/{schema}"/>')
        if password is None:
            for name, data in entries.items():
                outer.writestr("P-0001/" + name, data)
        else:
            inside = io.BytesIO()
            with pyzipper.AESZipFile(inside, "w", compression=pyzipper.ZIP_DEFLATED,
                                     encryption=pyzipper.WZ_AES) as inner:
                secret = base64.b64encode(hashlib.pbkdf2_hmac(
                    "sha256", password.encode("utf-16-le"), b"21.project.ets.knx.org", 65536, 32))
                inner.setpassword(secret)
                for name, data in entries.items():
                    inner.writestr(name, data)
            outer.writestr("P-0001.zip", inside.getvalue())
    return output.getvalue()


class UploadTests(unittest.TestCase):
    def test_unicode_password_and_legacy_upload(self):
        raw = project()
        encoded = PASSWORD.encode()
        body = len(encoded).to_bytes(4, "big") + encoded + raw
        self.assertEqual(decode_upload(body, "application/vnd.nm.ets-upload", 100000), (raw, PASSWORD))
        self.assertEqual(decode_upload(raw, "application/octet-stream", 100000), (raw, ""))

    def test_invalid_envelopes_do_not_echo_password(self):
        for body in (b"", (1025).to_bytes(4, "big") + b"private", b"\x00\x00\x00\x01\xffPKxx"):
            with self.assertRaises(ValueError) as caught:
                decode_upload(body, "application/vnd.nm.ets-upload", 10000)
            self.assertNotIn("private", str(caught.exception))

    def test_nested_archive_requires_password_before_reading(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as outer:
            outer.writestr("P-0001.zip", b"dummy")
        with self.assertRaisesRegex(ValueError, "inserisci la password"):
            preview(buf.getvalue())

    def test_corrupt_archive_is_actionable(self):
        with self.assertRaisesRegex(ValueError, "esporta nuovamente"):
            preview(b"not a project")


@unittest.skipUnless(pyzipper, "Install nm_bridge/requirements.txt to exercise AES")
class PasswordProjectTests(unittest.TestCase):
    def test_decrypt_unicode_password_and_keep_project_identity(self):
        encrypted = preview(project(PASSWORD), PASSWORD)
        plain = preview(project())
        self.assertEqual(encrypted["project_key"], plain["project_key"])
        self.assertEqual(encrypted["addresses"], plain["addresses"])
        self.assertEqual(encrypted["total"], 1)
        self.assertNotIn(PASSWORD, json.dumps(encrypted))

    def test_missing_and_wrong_password(self):
        raw = project(PASSWORD)
        for password, message in (("", "inserisci la password"), ("wrong", "Password ETS errata")):
            with self.assertRaisesRegex(ValueError, message):
                preview(raw, password)

    def test_encrypted_members_still_obey_limits(self):
        raw = project(PASSWORD, entries={"0.xml": "x" * 100})
        with self.assertRaisesRegex(ValueError, "XML too large"):
            with open_project(raw, PASSWORD, 500, 99, 10000):
                pass
        with self.assertRaisesRegex(ValueError, "Too many archive entries"):
            with open_project(raw, PASSWORD, 2, 10000, 10000):
                pass

    def test_encrypted_xml_entities_rejected(self):
        raw = project(PASSWORD, entries={"0.xml": '<!DOCTYPE x [<!ENTITY a "x">]><Project/>'})
        with self.assertRaisesRegex(ValueError, "XML entities"):
            preview(raw, PASSWORD)

    def test_nested_paths_rejected(self):
        raw = project(PASSWORD, entries={"../0.xml": XML})
        with self.assertRaisesRegex(ValueError, "Percorso interno"):
            preview(raw, PASSWORD)


if __name__ == "__main__":
    unittest.main()
