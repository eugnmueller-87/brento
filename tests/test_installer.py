"""The installers and what they stand on: sign-ins without a window, the launcher, and the packages themselves."""
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packaging"))
import address
import build
import launcher
import macpkg
import server
import settings
import wizard


def program(code):
    """A stand-in for the GitHub program: a real process that says what it is told to."""
    return [sys.executable, "-c", code]


def until(check, seconds=10):
    ends = time.monotonic() + seconds
    while time.monotonic() < ends:
        if check():
            return True
        time.sleep(0.05)
    return False


class SignIns(unittest.TestCase):
    def setUp(self):
        self.signin = wizard.SignIn()

    def tearDown(self):
        if self.signin.proc is not None:
            self.signin.proc.kill()

    def test_the_code_is_read_and_the_program_waits(self):
        self.signin.start("gh-login", program("import sys,time; print('! First copy your one-time code: AB12-CD34', file=sys.stderr); "
                                               "sys.stderr.flush(); time.sleep(60)"))
        self.assertTrue(until(lambda: self.signin.view()["code"] == "AB12-CD34"))
        view = self.signin.view()
        self.assertTrue(view["running"])
        self.assertEqual(view["url"], "https://github.com/login/device")

    def test_a_new_click_replaces_the_old_code(self):
        self.signin.start("gh-login", program("import time; print('one-time code: AAAA-1111', flush=True); time.sleep(60)"))
        self.assertTrue(until(lambda: self.signin.view()["code"] == "AAAA-1111"))
        first = self.signin.proc
        self.signin.start("gh-login", program("import time; print('one-time code: BBBB-2222', flush=True); time.sleep(60)"))
        self.assertTrue(until(lambda: self.signin.view()["code"] == "BBBB-2222"))
        self.assertTrue(until(lambda: first.poll() is not None))
        # The first one's end says nothing about the second.
        self.assertTrue(self.signin.view()["running"])
        self.assertEqual(self.signin.view()["error"], "")

    def test_done_and_failed(self):
        self.signin.start("gh-login", program("print('one-time code: AAAA-1111', flush=True)"))
        self.assertTrue(until(lambda: not self.signin.view()["running"]))
        self.assertEqual((self.signin.view()["error"], self.signin.view()["code"]), ("", ""))
        self.signin.start("gh-login", program("import sys; print('This device_code has expired.'); sys.exit(1)"))
        self.assertTrue(until(lambda: not self.signin.view()["running"]))
        self.assertIn("ran out of time", self.signin.view()["error"])

    def test_an_error_never_carries_the_code(self):
        text = wizard.SignIn.explain("could not use code AB12-CD34 on this host")
        self.assertNotIn("AB12-CD34", text)
        self.assertIn("did not work", text)

    def test_claudes_program_is_not_read(self):
        fake = mock.Mock(stdout=None)
        fake.wait.return_value = 0
        with mock.patch.object(wizard.subprocess, "Popen", return_value=fake) as popen:
            self.signin.start("claude-login", ["claude", "auth", "login"])
            self.assertEqual(popen.call_args[1]["stdout"], subprocess.DEVNULL)
            self.assertEqual(popen.call_args[1]["stderr"], subprocess.DEVNULL)
        self.assertTrue(until(lambda: not self.signin.view()["running"]))

    def test_no_system_opens_a_terminal_for_a_sign_in(self):
        for system in ("darwin", "win32", "linux"):
            signin = wizard.SignIn()
            fake = mock.Mock(stdout=io.BytesIO(b"! First copy your one-time code: AB12-CD34\n"))
            fake.wait.return_value = 0
            with mock.patch.object(settings, "system", return_value=system), mock.patch.object(wizard, "SIGNIN", signin), \
                    mock.patch.object(wizard.settings, "find_exe", return_value="/somewhere/gh"), \
                    mock.patch.object(wizard.subprocess, "Popen", return_value=fake) as popen:
                result = wizard.start_action("gh-login")
            self.assertTrue(result["started"])
            self.assertEqual(popen.call_count, 1)
            args, options = popen.call_args[0][0], popen.call_args[1]
            self.assertEqual(args[:3], ["/somewhere/gh", "auth", "login"])
            self.assertIn("github.com", args)
            self.assertNotIn("Terminal", " ".join(args))
            self.assertEqual(options["stdin"], subprocess.DEVNULL)

    def test_only_fixed_programs(self):
        with self.assertRaises(ValueError):
            wizard.start_action("rm -rf /")
        with mock.patch.object(wizard.settings, "find_exe", return_value=None):
            with self.assertRaises(ValueError) as caught:
                wizard.start_action("gh-login")
        self.assertIn("not installed", str(caught.exception))

    def test_the_page_tells_the_three_states_apart(self):
        # The wizard decides by these words which button it shows.
        text = (ROOT / "sources.py").read_text(encoding="utf-8")
        for words in ("The GitHub program is not installed yet.", "GitHub is not signed in yet.",
                      "GitHub does not let Brento read your boards yet."):
            self.assertIn(words, text)
        for name in ("sources.py", "server.py", "wizard.py", "web/app.js"):
            self.assertNotIn("gh auth login", (ROOT / name).read_text(encoding="utf-8"), name)

    def test_the_installers_gh_is_found_last(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"BRENTO_HOME": tmp}), \
                mock.patch.object(settings, "BUNDLED_BIN", Path(tmp, "bundled")):
            for system in ("darwin", "win32"):
                seen = []

                def which(name, path=None):
                    seen.append(path)
                    return None
                with mock.patch.object(settings, "system", return_value=system), mock.patch.object(settings.shutil, "which", which):
                    self.assertIsNone(settings.find_exe("gh"))
                folders = seen[-1].split(os.pathsep)
                self.assertEqual(folders[-2:], [str(Path(tmp, "bin")), str(Path(tmp, "bundled"))])


class Start(unittest.TestCase):
    def test_no_name_is_looked_up_before_brento_listens(self):
        # The lookup can take half a minute, and on a Mac it can raise a question about the local network.
        def never(*args):
            raise AssertionError("looked up %r" % (args,))
        with mock.patch.object(socket, "getfqdn", never), mock.patch.object(socket, "gethostbyaddr", never):
            for kind, handler in ((server.Server, server.Handler), (server.PhoneServer, server.PhoneHandler)):
                srv = kind(("127.0.0.1", 0), handler)
                try:
                    self.assertEqual((srv.server_name, srv.server_port), srv.server_address[:2])
                finally:
                    srv.server_close()

    def test_a_second_brento_does_not_share_the_port(self):
        first = server.Server(("127.0.0.1", 0), server.Handler)
        try:
            with self.assertRaises(OSError):
                server.Server(first.server_address[:2], server.Handler).server_close()
        finally:
            first.server_close()


class Launcher(unittest.TestCase):
    NETSTAT = ("Aktive Verbindungen\r\n\r\n  Proto  Lokale Adresse         Remoteadresse          Status           PID\r\n"
               "  TCP    127.0.0.1:8770         127.0.0.1:50312        HERGESTELLT      4242\r\n"
               "  TCP    127.0.0.1:8770         0.0.0.0:0              ABHÖREN          26444\r\n")

    def test_finds_the_process_behind_the_port_in_any_language(self):
        with mock.patch.object(launcher, "output", return_value=self.NETSTAT), mock.patch.object(launcher.sys, "platform", "win32"), \
                mock.patch.object(address, "port", return_value=8770):
            self.assertEqual(launcher.listener(), 26444)
        with mock.patch.object(launcher, "output", return_value=self.NETSTAT), mock.patch.object(launcher.sys, "platform", "win32"), \
                mock.patch.object(address, "port", return_value=8771):
            self.assertEqual(launcher.listener(), 0)
        for text, pid in (("512\n", 512), ("", 0), ("lsof: no such thing", 0)):
            with mock.patch.object(launcher, "output", return_value=text), mock.patch.object(launcher.sys, "platform", "darwin"):
                self.assertEqual(launcher.listener(), pid)

    def test_stop_leaves_another_copy_alone(self):
        with mock.patch.object(launcher, "agent", return_value=None), mock.patch.object(launcher, "listener", return_value=77), \
                mock.patch.object(launcher, "ours", return_value=False), mock.patch.object(address, "whose", return_value="mine"), \
                mock.patch.object(launcher, "until", return_value=True), mock.patch.object(launcher.os, "kill") as kill:
            launcher.stop()
            kill.assert_not_called()
            launcher.stop(any_brento=True)
            kill.assert_called_once()

    def test_stop_never_ends_another_program_or_another_persons_brento(self):
        for whose in ("", "other"):
            with mock.patch.object(launcher, "agent", return_value=None), mock.patch.object(launcher, "listener", return_value=77), \
                    mock.patch.object(launcher, "ours", return_value=False), mock.patch.object(address, "whose", return_value=whose), \
                    mock.patch.object(launcher, "until", return_value=True), mock.patch.object(launcher.os, "kill") as kill:
                launcher.stop(any_brento=True)
                kill.assert_not_called()

    def test_another_persons_brento_is_never_opened_as_ones_own(self):
        with mock.patch.object(launcher, "agent", return_value=None), mock.patch.object(address, "whose", return_value="other"), \
                mock.patch.object(launcher, "until", return_value=False), mock.patch.object(launcher, "spawn") as spawn:
            self.assertIn("did not start", launcher.start())
            spawn.assert_called_once()

    def test_only_programs_of_the_installed_copy_count_as_its_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "python").mkdir()
            (base / "app").mkdir()
            programs = {1: base / "python" / "pythonw.exe", 2: base / "app" / "bin" / "gh.exe", 3: base / "unins000.exe",
                        4: base.parent / "chrome.exe", 5: ""}
            with mock.patch.object(launcher, "HERE", base / "app"), mock.patch.object(launcher.sys, "platform", "win32"), \
                    mock.patch.object(launcher, "program_of", side_effect=lambda pid: str(programs[pid])):
                self.assertEqual([pid for pid in programs if launcher.ours(pid)], [1, 2])
                with mock.patch.object(launcher, "every_pid", return_value=list(programs)), mock.patch.object(launcher.os, "getpid", return_value=1), \
                        mock.patch.object(launcher.os, "kill") as kill:
                    launcher.end_helpers()
                    self.assertEqual([c.args[0] for c in kill.call_args_list], [2])
            # A copy of the source code has no programs of its own: nothing beside it may ever be ended.
            with mock.patch.object(launcher, "HERE", base), mock.patch.object(launcher.sys, "platform", "win32"), \
                    mock.patch.object(launcher, "program_of", side_effect=lambda pid: str(programs[pid])), \
                    mock.patch.object(launcher.os, "kill") as kill:
                self.assertFalse(any(launcher.ours(pid) for pid in programs))
                launcher.end_helpers()
                kill.assert_not_called()

    @unittest.skipUnless(sys.platform == "win32", "Windows only")
    def test_every_process_is_seen(self):
        self.assertIn(os.getpid(), launcher.every_pid())

    def test_the_login_service_gets_a_second_try(self):
        answers = iter([False, False, False, True])
        with mock.patch.object(launcher, "launchctl", side_effect=lambda *a: next(answers)), \
                mock.patch.object(launcher.os, "getuid", return_value=501, create=True), mock.patch.object(launcher.time, "sleep"):
            self.assertTrue(launcher.start_service("/x.plist"))

    def test_starts_restarts_and_is_found_again(self):
        if sys.platform != "win32" and not shutil.which("lsof"):
            self.skipTest("lsof is not on this computer")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, BRENTO_PORT=str(port), BRENTO_HOME=tmp, BRENTO_NO_BROWSER="1")

            def run(*args):
                return subprocess.run([sys.executable, str(ROOT / "launcher.py")] + list(args), env=env, timeout=90).returncode

            with mock.patch.dict(os.environ, env):
                try:
                    self.assertEqual(run("--start"), 0)
                    self.assertEqual(address.whose(), "mine")
                    first = launcher.listener()
                    self.assertTrue(first)
                    self.assertEqual(run("--start"), 0)
                    self.assertEqual(launcher.listener(), first)
                    self.assertEqual(run("--replace", "--start"), 0)
                    self.assertEqual(address.whose(), "mine")
                    self.assertNotEqual(launcher.listener(), first)
                finally:
                    launcher.stop(any_brento=True)
                self.assertEqual(address.whose(), "")
                # Windows lets go of the log a moment after the process is gone.
                until(lambda: not launcher.listener())
                time.sleep(0.5)


class MacPackage(unittest.TestCase):
    def test_what_is_written_reads_back(self):
        scripts = macpkg.scripts_archive({"postinstall": (b"#!/bin/sh\nexit 0\n", True), "brento.tar.gz": (b"\x1f\x8b data", False)})
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "x.pkg")
            macpkg.write(target, b"<installer-gui-script/>", {"en.lproj/welcome.html": b"<p>Hello & welcome</p>"}, "brento.pkg",
                         macpkg.package_info("app.brento.pkg", "1.2.3", 5), scripts)
            raw = target.read_bytes()
        self.assertEqual(raw[:4], b"xar!")
        inside = macpkg.read_xar(raw)
        self.assertEqual(sorted(inside), ["Distribution", "Resources/en.lproj/welcome.html", "brento.pkg/PackageInfo", "brento.pkg/Scripts"])
        files = macpkg.read_scripts(inside["brento.pkg/Scripts"])
        self.assertEqual(files["./postinstall"], (0o100755, b"#!/bin/sh\nexit 0\n"))
        self.assertEqual(files["./brento.tar.gz"], (0o100644, b"\x1f\x8b data"))
        self.assertEqual(files["."][0], 0o040755)
        info = ET.fromstring(inside["brento.pkg/PackageInfo"])
        self.assertEqual((info.get("version"), info.get("auth")), ("1.2.3", "none"))
        self.assertEqual(info.find("scripts/postinstall").get("file"), "./postinstall")

    def test_a_damaged_package_is_noticed(self):
        raw = bytearray(macpkg.xar({"a": b"hello", "b/c": b"world"}))
        raw[-1] ^= 1
        with self.assertRaises(ValueError):
            macpkg.read_xar(bytes(raw))

    def test_installs_only_for_the_person_and_runs_on_both_chips(self):
        text = (ROOT / "packaging" / "mac" / "Distribution.xml").read_text(encoding="utf-8")
        root = ET.fromstring(text.replace("{version}", "1.2.3").replace("{kbytes}", "5"))
        domains = root.find("domains").attrib
        self.assertEqual((domains["enable_currentUserHome"], domains["enable_localSystem"], domains["enable_anywhere"]), ("true", "false", "false"))
        self.assertEqual(root.find("options").get("hostArchitectures"), "arm64,x86_64")
        refs = [r for r in root.findall("pkg-ref") if r.text]
        self.assertEqual(refs[0].text, "#brento.pkg")
        for name in (root.find("welcome").get("file"), root.find("conclusion").get("file")):
            for lang in ("en", "de"):
                page = (ROOT / "packaging" / "mac" / (lang + ".lproj") / name).read_text(encoding="utf-8")
                # Apple's Installer shows these pages on a dark window in dark mode.
                self.assertIn("prefers-color-scheme: dark", page)

    def test_the_python_that_goes_along_keeps_what_brento_needs(self):
        for name in ("python/lib/python3.14/http/server.py", "python/lib/python3.14/ssl.py", "python/lib/python3.14/json/decoder.py",
                     "python/lib/python3.14/threading.py", "python/lib/python3.14/LICENSE.txt", "python/lib/python3.14/zoneinfo/__init__.py",
                     "python/lib/python3.14/encodings/utf_8.py", "python/lib/python3.14/importlib/__init__.py"):
            self.assertIsNone(build.PYTHON_DROP.search(name), name)
        for name in ("python/lib/libpython3.14.dylib", "python/lib/tk9.0/x.tcl", "python/lib/python3.14/tkinter/__init__.py",
                     "python/lib/python3.14/site-packages/pip/x.py", "python/include/python3.14/Python.h", "python/lib/python3.14/test/x.py"):
            self.assertIsNotNone(build.PYTHON_DROP.search(name), name)


class Contents(unittest.TestCase):
    def test_downloads_are_pinned(self):
        entries = {k: v for k, v in json.loads((ROOT / "packaging" / "runtimes.json").read_text(encoding="utf-8")).items() if k != "about"}
        self.assertEqual(len(entries), 7)
        for key, entry in entries.items():
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$", key)
            self.assertRegex(entry["url"], r"^https://(github\.com/(astral-sh/python-build-standalone|cli/cli)/releases/download/|www\.python\.org/ftp/python/"
                                           r"|files\.pythonhosted\.org/packages/)", key)

    def test_a_changed_download_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(build, "CACHE", Path(tmp)):
            Path(tmp, build.RUNTIMES["gh-mac-arm64"]["url"].rsplit("/", 1)[1]).write_bytes(b"not what was published")
            with self.assertRaises(SystemExit):
                build.fetch("gh-mac-arm64")

    def test_the_program_goes_in_and_nothing_else(self):
        if not (ROOT / "VERSION").is_file() or not (ROOT / ".git").exists():
            self.skipTest("only in the public repository")
        files = build.program_files()
        for needed in ("server.py", "launcher.py", "address.py", "wizard.py", "web/app.js", "web/photos/CREDITS.md", "LICENSE", "install.sh",
                       "ask-settings.json", "windows-zones.json"):
            self.assertIn(needed, files)
        for rel in files:
            self.assertFalse(rel.startswith(("tests/", "packaging/", "docs/", ".github/")), rel)
        self.assertNotIn(b"\r\n", files["install.sh"])

    def test_windows_installs_for_the_person_and_cleans_up(self):
        text = (ROOT / "packaging" / "windows" / "brento.iss").read_text(encoding="utf-8")
        self.assertIn("PrivilegesRequired=lowest", text)
        self.assertIn("uninsdeletevalue", text)
        self.assertIn('--stop"; RunOnceId', text)

    def test_shell_scripts_have_unix_line_endings(self):
        for rel in ("install.sh", "packaging/mac/postinstall", "Install Brento.command"):
            self.assertNotIn(b"\r\n", (ROOT / rel).read_bytes(), rel)


if __name__ == "__main__":
    unittest.main()
