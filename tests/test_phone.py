"""Brento on a phone and on a Mac: pairing, the phone door's short list of routes, and the Mac's own setup paths."""
import hashlib
import http.client
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import phone
import server
import settings
import wizard


class Pairing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.phones = phone.Phones(self.tmp.name)
        self.phones.switch(True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_right_code_pairs_and_only_a_hash_is_kept(self):
        code = self.phones.new_code(now=1000)
        token = self.phones.pair(code[:3] + " " + code[3:], now=1001)
        self.assertTrue(token)
        self.assertTrue(self.phones.known(token))
        saved = Path(self.tmp.name, phone.FILE).read_text(encoding="utf-8")
        self.assertNotIn(token, saved)
        self.assertIn(hashlib.sha256(token.encode()).hexdigest(), saved)
        # A restart reads the same phones back.
        self.assertTrue(phone.Phones(self.tmp.name).known(token))

    def test_five_wrong_tries_end_the_code(self):
        code = self.phones.new_code(now=1000)
        wrong = "%06d" % ((int(code) + 1) % 1000000)
        for _ in range(phone.CODE_TRIES):
            self.assertIsNone(self.phones.pair(wrong, now=1001))
        self.assertIsNone(self.phones.pair(code, now=1002))

    def test_code_runs_out_and_off_means_no_door(self):
        code = self.phones.new_code(now=1000)
        self.assertIsNone(self.phones.pair(code, now=1000 + phone.CODE_TTL + 1))
        code = self.phones.new_code(now=2000)
        token = self.phones.pair(code, now=2001)
        self.phones.switch(False)
        self.assertFalse(self.phones.known(token))
        self.assertIsNone(self.phones.pair(code, now=2002))

    def test_remove_all_phones(self):
        token = self.phones.pair(self.phones.new_code(now=1000), now=1001)
        self.phones.forget_all()
        self.assertFalse(self.phones.known(token))


class Addresses(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(phone.kind("192.168.178.23"), "home")
        self.assertEqual(phone.kind("10.0.0.7"), "home")
        self.assertEqual(phone.kind("100.67.1.2"), "tailscale")
        for ip in ("127.0.0.1", "169.254.3.4", "8.8.8.8", "0.0.0.0", "fe80::1", "nonsense"):
            self.assertEqual(phone.kind(ip), "", ip)

    def test_host_header_must_be_an_address_or_allowed_by_hand(self):
        self.assertTrue(phone.host_ok("192.168.178.23:8771", set()))
        self.assertTrue(phone.host_ok("[fe80::1]:8771", set()))
        self.assertFalse(phone.host_ok("evil.example:8771", set()))
        self.assertTrue(phone.host_ok("my-pc.tail1234.ts.net:8771", {"my-pc.tail1234.ts.net"}))

    def test_short_list_of_routes(self):
        for path in ("/", "/api/state", "/api/library/note", "/photos/calm-01.webp", "/api/ask/status"):
            self.assertTrue(phone.allowed("GET", path), path)
        for path in ("/api/setup", "/api/wizard", "/api/wizard/vault", "/api/phone"):
            self.assertFalse(phone.allowed("GET", path), path)
        for path in ("/api/ask", "/api/refresh", "/api/tools"):
            self.assertTrue(phone.allowed("POST", path), path)
        for path in ("/api/setup", "/api/phone", "/api/wizard/open", "/api/open", "/api/calendar", "/api/slack", "/api/team"):
            self.assertFalse(phone.allowed("POST", path), path)


class FakeApp:
    def __init__(self, folder):
        self.hosts = set()
        self.phones = phone.Phones(folder)
        self.phones.switch(True)

    def state(self):
        return {"alerts": []}


class PhoneDoor(unittest.TestCase):
    """The real handler on a real socket, bound to loopback so a test never opens a port to the network."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = FakeApp(self.tmp.name)
        self.old_app = server.Handler.app
        server.Handler.app = self.app
        self.srv = server.PhoneServer(("127.0.0.1", 0), server.PhoneHandler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.port = self.srv.server_address[1]

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        server.Handler.app = self.old_app
        self.tmp.cleanup()

    def call(self, method, path, body=None, cookie="", host=None, kind="application/json"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Host": host or "127.0.0.1:%d" % self.port}
        if cookie:
            headers["Cookie"] = "%s=%s" % (phone.COOKIE, cookie)
        if body is not None:
            headers["Content-Type"] = kind
            headers["X-Leitstand"] = "1"
        conn.request(method, path, body=body, headers=headers)
        r = conn.getresponse()
        out = (r.status, r.getheader("Set-Cookie") or "", r.read())
        conn.close()
        return out

    def test_unpaired_phone_gets_the_pairing_page_and_nothing_else(self):
        status, _, body = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Connect this phone", body)
        self.assertEqual(self.call("GET", "/api/state")[0], 401)
        self.assertEqual(self.call("GET", "/apple-touch-icon.png")[0], 200)

    def test_pairing_then_reading_but_never_changing(self):
        self.assertEqual(self.call("POST", "/pair", "code=000000", kind="application/x-www-form-urlencoded")[0] in (401,), True)
        code = self.app.phones.new_code()
        status, cookie, _ = self.call("POST", "/pair", "code=" + code, kind="application/x-www-form-urlencoded")
        self.assertEqual(status, 303)
        self.assertIn("HttpOnly", cookie)
        token = cookie.split(";", 1)[0].split("=", 1)[1]
        status, _, body = self.call("GET", "/api/state", cookie=token)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["phone"])
        self.assertEqual(self.call("GET", "/api/setup", cookie=token)[0], 403)
        for path in ("/api/setup", "/api/phone", "/api/wizard/open", "/api/open"):
            self.assertEqual(self.call("POST", path, json.dumps({"action": "on"}), cookie=token)[0], 403, path)
        self.assertEqual(self.call("POST", "/api/tools", json.dumps({"action": "add", "name": "x", "url": "https://x.test"}), cookie=token)[0], 403)

    def test_foreign_host_and_switched_off_door(self):
        self.assertEqual(self.call("GET", "/", host="evil.example:%d" % self.port)[0], 403)
        self.app.phones.switch(False)
        self.assertEqual(self.call("GET", "/")[0], 403)


def gh_zip(name):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name[:-4] + "/bin/gh", b"#!/bin/sh\necho gh\n")
        z.writestr(name[:-4] + "/LICENSE", b"MIT")
    return buf.getvalue()


class MacSetup(unittest.TestCase):
    def test_picks_the_right_download(self):
        names = ["gh_2.105.0_checksums.txt", "gh_2.105.0_macOS_amd64.zip", "gh_2.105.0_macOS_arm64.zip",
                 "gh_2.105.0_macOS_universal.pkg", "gh_2.105.0_linux_arm64.tar.gz", "gh_2.105.0_windows_amd64.zip"]
        self.assertEqual(wizard.gh_asset(names, "darwin", "arm64"), "gh_2.105.0_macOS_arm64.zip")
        self.assertEqual(wizard.gh_asset(names, "darwin", "x86_64"), "gh_2.105.0_macOS_amd64.zip")
        self.assertEqual(wizard.gh_asset(names, "linux", "aarch64"), "gh_2.105.0_linux_arm64.tar.gz")
        self.assertIsNone(wizard.gh_asset(names, "win32", "amd64"))
        self.assertIsNone(wizard.gh_asset(names, "darwin", "sparc"))

    def fake_fetch(self, data, digest):
        name = "gh_2.105.0_macOS_arm64.zip"
        release = {"assets": [{"name": name, "browser_download_url": "https://github.com/cli/cli/releases/download/v2.105.0/" + name},
                              {"name": "gh_2.105.0_checksums.txt", "browser_download_url": "https://github.com/cli/cli/releases/download/v2.105.0/sums"}]}

        def fetch(url):
            if url == wizard.GH_RELEASE:
                return json.dumps(release).encode()
            if url.endswith("/sums"):
                return ("%s  %s\n" % (digest, name)).encode()
            return data
        return fetch

    def test_download_is_checked_before_it_is_kept(self):
        data = gh_zip("gh_2.105.0_macOS_arm64.zip")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "bin", "gh")
            error = wizard.install_gh(self.fake_fetch(data, hashlib.sha256(data).hexdigest()), "darwin", "arm64", target)
            self.assertEqual(error, "")
            self.assertEqual(target.read_bytes(), b"#!/bin/sh\necho gh\n")
            if os.name != "nt":
                self.assertTrue(os.access(str(target), os.X_OK))
            target.unlink()
            error = wizard.install_gh(self.fake_fetch(data, "0" * 64), "darwin", "arm64", target)
            self.assertIn("checksum", error)
            self.assertFalse(target.exists())

    def test_downloads_only_from_github(self):
        with self.assertRaises(ValueError):
            wizard.fetch_https("https://evil.example/gh.zip")
        with self.assertRaises(ValueError):
            wizard.fetch_https("http://github.com/cli/cli")

    def test_sign_in_opens_in_terminal_on_a_mac(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"BRENTO_HOME": tmp}), \
                mock.patch.object(settings, "system", return_value="darwin"), \
                mock.patch.object(wizard.settings, "find_exe", return_value="/opt/homebrew/bin/gh"), \
                mock.patch.object(wizard.subprocess, "Popen") as popen:
            result = wizard.open_window("gh-login")
            self.assertTrue(result["opened"])
            script = Path(tmp, "run-gh-login.command")
            self.assertIn("/opt/homebrew/bin/gh auth login --web", script.read_text(encoding="utf-8"))
            self.assertEqual(popen.call_args[0][0], ["open", "-a", "Terminal", str(script)])

    def test_install_on_a_mac_runs_without_a_window(self):
        with mock.patch.object(settings, "system", return_value="darwin"), mock.patch.object(wizard, "install_gh") as install, \
                mock.patch.object(wizard.subprocess, "Popen") as popen:
            result = wizard.open_window("gh-install")
            self.assertTrue(result["opened"])
            popen.assert_not_called()
        install.assert_called_once()

    def test_programs_outside_launchds_short_path_are_found(self):
        calls = []

        def which(name, path=None):
            calls.append(path)
            return None if path is None else "/opt/homebrew/bin/" + name
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"BRENTO_HOME": tmp}), \
                mock.patch.object(settings, "system", return_value="darwin"), mock.patch.object(settings.shutil, "which", which):
            self.assertEqual(settings.find_exe("gh"), "/opt/homebrew/bin/gh")
        self.assertIn("/opt/homebrew/bin", calls[1].split(os.pathsep))
        self.assertIn(str(Path(tmp) / "bin"), calls[1].split(os.pathsep))

    def test_a_folder_macos_blocks_says_where_to_allow_it(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(settings, "system", return_value="darwin"), \
                mock.patch.object(wizard.os, "listdir", side_effect=PermissionError("blocked")):
            result = wizard.vault_stats(tmp)
        self.assertIn("Full Disk Access", result["error"])


if __name__ == "__main__":
    unittest.main()
