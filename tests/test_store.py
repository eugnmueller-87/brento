"""What the Microsoft Store package needs: sample notes, a way to delete everything, and a manifest that says what it should."""
import http.client
import json
import re
import struct
import sys
import threading
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packaging"))
sys.path.insert(0, str(ROOT / "tests"))
import address
import calendar_feed
import launcher
import library
import phone
import samples
import secret
import server
import settings
import slack_notify
import sources
import store
import test_access
import wizard

F = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10}"
UAP = "{http://schemas.microsoft.com/appx/manifest/uap/windows10}"
UAP10 = "{http://schemas.microsoft.com/appx/manifest/uap/windows10/10}"
UAP17 = "{http://schemas.microsoft.com/appx/manifest/uap/windows10/17}"
DESKTOP = "{http://schemas.microsoft.com/appx/manifest/desktop/windows10}"
RESCAP = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities}"


class Samples(test_access.Home):
    def test_every_task_is_found_and_none_is_late(self):
        folder = samples.write(self.home, date(2026, 12, 28))
        self.assertEqual(folder, self.home / "sample-notes")
        index = sources.TaskIndex(folder)
        data, src = sources.read_tasks(index, date(2026, 12, 28))
        wanted = sum(len(re.findall(r"\{\d\}", text)) for text in samples.NOTES.values())
        self.assertEqual((len(data["items"]), src["state"]), (wanted, "fresh"))
        self.assertEqual(sorted(t["due"] for t in data["items"])[0], "2026-12-28")
        self.assertEqual(sorted(t["due"] for t in data["items"])[-1], "2027-01-03")
        self.assertEqual(wizard.vault_stats(str(folder))["notes"], len(samples.NOTES))

    def test_every_link_leads_somewhere(self):
        folder = samples.write(self.home, date(2026, 11, 25))
        lib = library.Library(folder)
        lib.refresh()
        names = {Path(name).stem for name in samples.NOTES}
        for name, text in samples.NOTES.items():
            for link in re.findall(r"\[\[([^\]]+)\]\]", text):
                self.assertIn(link, names, name)
            self.assertEqual(lib.note(name)["title"], Path(name).stem)

    def test_writing_again_brings_new_dates_and_keeps_what_is_not_ours(self):
        folder = samples.write(self.home, date(2026, 11, 25))
        (folder / "Work" / "mine.md").write_text("mine", encoding="utf-8")
        samples.write(self.home, date(2026, 12, 1))
        self.assertIn("2026-12-01", (folder / "Work" / "Offer for the bakery.md").read_text(encoding="utf-8"))
        samples.remove(self.home)
        self.assertEqual([p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()], ["Work/mine.md"])
        (folder / "Work" / "mine.md").unlink()
        samples.remove(self.home)
        self.assertFalse(folder.exists())


class Forget(test_access.Home):
    def test_only_what_daytag_made_goes(self):
        for name in settings.OWN_FILES + ("server.log",):
            (self.home / name).write_text("x", encoding="utf-8")
        (self.home / "phone.tmp").write_text("x", encoding="utf-8")
        (self.home / "bin").mkdir()
        (self.home / "bin" / "gh").write_text("x", encoding="utf-8")
        (self.home / "notes").mkdir()
        (self.home / "notes" / "mine.md").write_text("mine", encoding="utf-8")
        for name in ("projects.json", "private-terms.txt"):
            (self.home / name).write_text("mine", encoding="utf-8")
        (self.home / "bin" / "mine").write_text("mine", encoding="utf-8")
        samples.write(self.home, date(2026, 11, 25))
        self.assertEqual(settings.forget(), [])
        self.assertEqual(sorted(p.relative_to(self.home).as_posix() for p in self.home.rglob("*") if p.is_file()),
                         ["bin/mine", "notes/mine.md", "private-terms.txt", "projects.json"])

    def test_every_file_daytag_writes_into_its_folder_is_known(self):
        # A file that is added one day must be deleted too, or be named here as the owner's.
        owners = {"projects.json", "private-terms.txt", "notes", "bin"}
        for path in ROOT.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for name in re.findall(r'(?:settings\.home\(\)|self\.home|\bhome\(\)|Path\(folder\)|\bfolder|\bbase|\bhome) / "([a-z][a-z.-]+)"', text):
                if path.name in ("settings.py", "launcher.py") and name in ("python", "app", "obsidian"):
                    continue
                self.assertIn(name, set(settings.OWN_FILES) | owners | {"server.log"}, path.name)
        self.assertIn(phone.FILE, settings.OWN_FILES)

    def test_nothing_is_left_when_nothing_is_the_owners(self):
        (self.home / "notes").mkdir()
        (self.home / "daytag.json").write_text("{}", encoding="utf-8")
        settings.forget()
        self.assertFalse(self.home.exists())
        self.home.mkdir()

    def test_only_the_log_is_emptied_when_it_cannot_be_deleted(self):
        log, saved = self.home / "server.log", self.home / "daytag.json"
        log.write_text("Open http://127.0.0.1:8770/?ticket=secret", encoding="utf-8")
        saved.write_text('{"name": "Alex"}', encoding="utf-8")
        real = Path.unlink

        def held(path, *args, **kwargs):
            if path in (log, saved):
                raise PermissionError("another program holds it")
            return real(path, *args, **kwargs)
        with mock.patch.object(Path, "unlink", held), mock.patch.object(settings.time, "sleep") as slept:
            self.assertEqual(settings.forget(), ["daytag.json"])
        self.assertGreater(slept.call_count, 3)
        self.assertEqual(log.read_text(encoding="utf-8"), "")
        # An empty one would be a Daytag that never starts again.
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8")), {"name": "Alex"})

    def test_settings_with_nothing_in_them_start_the_setup(self):
        for text in ("", " \n", "\ufeff"):
            (self.home / "daytag.json").write_text(text, encoding="utf-8")
            self.assertIsNone(settings.load())
        (self.home / "daytag.json").write_text("{", encoding="utf-8")
        with self.assertRaises(SystemExit):
            settings.load()


class Routes(test_access.Home):
    def setUp(self):
        super().setUp()
        self.app = server.App(None, "127.0.0.1", [], "sonnet")
        server.Handler.app = self.app
        self.srv = server.Server(("127.0.0.1", 0), server.Handler)
        self.port = self.app.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def post(self, path, body, key=True):
        headers = {"Host": "127.0.0.1:%d" % self.port, "X-Daytag": "1"}
        if key:
            headers["X-Daytag-Key"] = self.app.key
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("POST", path, body=json.dumps(body), headers=headers)
        reply = conn.getresponse()
        out = reply.status, json.loads(reply.read())
        conn.close()
        return out

    def test_the_sample_notes_become_a_folder_that_can_be_chosen(self):
        status, answer = self.post("/api/wizard/sample", {})
        self.assertEqual(status, 200)
        self.assertEqual(answer["path"], self.app.setup_view()["sample"])
        self.assertFalse(self.app.sampled())
        self.assertNotIn("obsidian", [c["id"] for c in self.app.catalog()])
        self.app.save_setup({"profile": {"vault": answer["path"], "sources": {"tasks": {"on": True}, "library": {"on": True}}}})
        self.assertEqual(self.app.profile["vault"], answer["path"])
        self.assertTrue(self.app.sampled())
        # There is no such vault in Obsidian.
        self.assertNotIn("obsidian", [c["id"] for c in self.app.catalog()])

    def test_made_up_tasks_do_not_go_to_slack(self):
        self.app.needs_setup = False
        for chosen, sent in ((True, ["calendar", "board"]), (False, ["calendar", "board", "tasks"])):
            seen = []
            with mock.patch.object(self.app, "sampled", return_value=chosen), mock.patch.object(self.app, "state", return_value={}), \
                    mock.patch.object(self.app.slack, "connected", return_value=True), \
                    mock.patch.object(self.app.slack, "tick", lambda state, cfg, name: seen.append(cfg["sources"])), \
                    mock.patch.object(server.time, "sleep", side_effect=[None, SystemExit]):
                with self.assertRaises(SystemExit):
                    self.app.notify_loop()
            self.assertEqual(seen, [sent])

    def test_deleting_needs_the_store_the_word_and_the_owner(self):
        with mock.patch.object(type(self.app), "forget", return_value=[]) as forget:
            for stored, body in ((False, {"delete": True}), (True, {}), (True, {"delete": "yes"}), (True, {"delete": 1})):
                with mock.patch.object(settings, "STORE", stored):
                    self.assertEqual(self.post("/api/forget", body)[0], 400, (stored, body))
            with mock.patch.object(settings, "STORE", True):
                self.assertEqual(self.post("/api/forget", {"delete": True}, key=False)[0], 401)
            forget.assert_not_called()
            with mock.patch.object(settings, "STORE", True):
                self.assertEqual(self.post("/api/forget", {"delete": True}), (200, {"deleted": True, "left": []}))
            forget.assert_called_once_with()
        self.assertFalse(phone.allowed("POST", "/api/forget"))
        self.assertFalse(phone.allowed("POST", "/api/wizard/sample"))

    def test_other_notes_are_not_news_for_slack(self):
        memory = self.home / "slack-state.json"
        memory.write_text(json.dumps({"seeded": True, "seen": ["a"], "digest": "2026-11-25"}), encoding="utf-8")
        self.app.save_setup({"profile": {"name": "Alex"}})
        self.assertTrue(json.loads(memory.read_text(encoding="utf-8"))["seeded"])
        status, answer = self.post("/api/wizard/sample", {})
        self.app.save_setup({"profile": {"vault": answer["path"]}})
        self.assertEqual(json.loads(memory.read_text(encoding="utf-8")), {"seeded": False, "seen": ["a"], "digest": "2026-11-25"})

    def test_the_end_takes_along_what_was_started(self):
        class Program:
            killed = False

            def kill(self):
                self.killed = True
        signing, answering = Program(), Program()
        self.app.answering = answering
        with mock.patch.object(server.threading, "Timer"), mock.patch.object(wizard.SIGNIN, "proc", signing):
            self.app.quit()
        self.assertEqual((signing.killed, answering.killed), (True, True))

    def test_quitting_is_for_the_store_only(self):
        with mock.patch.object(type(self.app), "quit") as ends:
            self.assertEqual(self.post("/api/quit", {})[0], 400)
            with mock.patch.object(settings, "STORE", True):
                self.assertEqual(self.post("/api/quit", {}, key=False)[0], 401)
                ends.assert_not_called()
                self.assertEqual(self.post("/api/quit", {}), (200, {"ended": True}))
            ends.assert_called_once_with()
        self.assertFalse(phone.allowed("POST", "/api/quit"))

    def test_after_the_end_nothing_is_answered_and_nothing_is_written(self):
        with mock.patch.object(server.threading, "Timer") as timer:
            self.assertEqual(self.app.forget(), [])
            timer.return_value.start.assert_called_once_with()
        for path in ("/api/whose?n=" + "x" * 32, "/api/state", "/"):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
            conn.request("GET", path, headers={"Host": "127.0.0.1:%d" % self.port})
            self.assertEqual(conn.getresponse().status, 503, path)
            conn.close()
        self.assertFalse(self.home.exists())
        self.home.mkdir()

    def test_the_other_daytag_is_seen_only_by_the_one_from_the_store(self):
        other = self.home / "Programs" / "Daytag" / "app" / "launcher.py"
        with mock.patch.dict("os.environ", {"LOCALAPPDATA": str(self.home)}):
            with mock.patch.object(settings, "STORE", True):
                self.assertFalse(settings.twice())
                other.parent.mkdir(parents=True)
                other.write_text("", encoding="utf-8")
                self.assertTrue(settings.twice())
            self.assertFalse(settings.twice())

    def test_the_one_from_the_store_offers_no_other_software(self):
        with mock.patch.object(settings, "STORE", True), mock.patch.object(wizard, "install_gh") as install:
            with self.assertRaises(ValueError):
                wizard.start_action("gh-install")
            install.assert_not_called()
            with mock.patch.object(server.sources, "gh_status", return_value={"ready": False, "reason": ""}), \
                    mock.patch.object(type(self.app), "auth", return_value={}):
                self.assertFalse(self.app.wizard_view()["canInstall"])
        page = (Path(server.__file__).resolve().parent / "web" / "app.js").read_text(encoding="utf-8")
        # Whoever adds a link to another program has to say here that the Store version does not show it.
        offers = sorted(set(re.findall(r"https://(claude\.com|cli\.github\.com|obsidian\.md|tailscale\.com|git-scm\.com|www\.google\.com/chrome)", page)))
        self.assertEqual(offers, ["claude.com", "cli.github.com"])
        for link in ("https://claude.com/claude-code", "https://cli.github.com/"):
            before = page[:page.index(link)]
            self.assertIn("d.store ? ", before[-400:], link)

    def test_the_other_daytag_is_removed_by_its_own_uninstaller_which_asks(self):
        other = self.home / "Programs" / "Daytag"
        with mock.patch.dict("os.environ", {"LOCALAPPDATA": str(self.home)}), \
                mock.patch.object(server.os, "startfile", create=True) as opened:
            with mock.patch.object(settings, "STORE", True):
                self.assertEqual(self.post("/api/remove-other", {})[0], 400)
                (other / "app").mkdir(parents=True)
                (other / "app" / "launcher.py").write_text("", encoding="utf-8")
                self.assertEqual(self.post("/api/remove-other", {})[0], 400)
                (other / "unins000.exe").write_bytes(b"")
                self.assertEqual(self.post("/api/remove-other", {}, key=False)[0], 401)
                opened.assert_not_called()
                self.assertEqual(self.post("/api/remove-other", {}), (200, {"opened": True}))
            self.assertEqual(self.post("/api/remove-other", {})[0], 400)
        opened.assert_called_once_with(str(other / "unins000.exe"))
        self.assertFalse(phone.allowed("POST", "/api/remove-other"))


class Starting(test_access.Home):
    def test_at_sign_in_the_one_from_the_store_waits_for_a_yes(self):
        def started(stored):
            with mock.patch.object(settings, "STORE", stored), mock.patch.object(launcher, "start", return_value="") as start:
                self.assertEqual(launcher.main(["--start"]), 0)
            return start.called
        self.assertEqual((started(False), started(True)), (True, False))
        settings.save({"name": "Alex"})
        self.assertFalse(started(True))
        settings.save({"name": "Alex", "autostart": True})
        self.assertTrue(started(True))
        (self.home / "daytag.json").write_text("{", encoding="utf-8")
        self.assertFalse(started(True))

    def test_only_a_clear_yes_counts(self):
        for given in (None, "", "yes", 1, [True]):
            self.assertIs(settings.normalize({"autostart": given})["autostart"], False, given)

    def test_there_is_no_phone_door_in_the_store(self):
        app = server.App(None, "127.0.0.1", [], "sonnet")
        app.phones.switch(True)
        with mock.patch.object(settings, "STORE", True), mock.patch.object(server, "PhoneServer") as door:
            app.phone_listen()
            door.assert_not_called()
            for action in ("on", "code", "off", "forget"):
                with self.assertRaises(ValueError):
                    app.phone_action(action)


class Secrets(test_access.Home):
    LINK = "https://calendar.example/private-äöü/basic.ics"

    def test_what_is_hidden_comes_back_and_an_old_file_still_counts(self):
        kept = secret.hidden(self.LINK)
        self.assertEqual(secret.shown(kept), self.LINK)
        self.assertEqual(secret.shown(" %s\n" % self.LINK), self.LINK)
        if sys.platform == "win32":
            self.assertTrue(kept.startswith("dpapi:"))
            self.assertNotIn("example", kept)
            self.assertEqual(secret.shown("dpapi:" + "AAAA"), "")
            self.assertEqual(secret.shown("dpapi:not base64!"), "")
        else:
            self.assertEqual(kept, self.LINK)

    def test_the_two_links_are_hidden_on_disk(self):
        feed = calendar_feed.Feed(self.home / "calendar-url")
        with mock.patch.object(calendar_feed.Feed, "read", return_value="BEGIN:VCALENDAR END:VCALENDAR"):
            feed.connect(self.LINK.replace("äöü", "abc"))
        self.assertEqual(feed.url(), self.LINK.replace("äöü", "abc"))
        slack = slack_notify.Slack(self.home)
        hook = "https://hooks.slack.com/services/T0ABCDEF/B0ABCDEF/abcdefABCDEF123456"
        with mock.patch.object(slack_notify.Slack, "send", return_value=""):
            slack.connect(hook, "hello")
        self.assertEqual(slack.url(), hook)
        if sys.platform == "win32":
            for name in ("calendar-url", "slack-webhook"):
                self.assertNotIn("://", (self.home / name).read_text(encoding="utf-8"), name)

    def test_a_link_that_cannot_be_encrypted_is_not_kept(self):
        feed = calendar_feed.Feed(self.home / "calendar-url")
        with mock.patch.object(secret.sys, "platform", "win32"), mock.patch.object(secret, "_windows", return_value=None), \
                mock.patch.object(calendar_feed.Feed, "read", return_value="BEGIN:VCALENDAR END:VCALENDAR"):
            with self.assertRaises(ValueError) as refused:
                feed.connect("https://calendar.example/private-abc/basic.ics")
        self.assertNotIn("calendar.example", str(refused.exception))
        self.assertFalse((self.home / "calendar-url").exists() and (self.home / "calendar-url").read_text(encoding="utf-8"))
        self.assertFalse(feed.connected())

    def test_what_daytag_starts_reports_nothing(self):
        env = server.locked_env()
        self.assertEqual((env["DISABLE_TELEMETRY"], env["DISABLE_ERROR_REPORTING"]), ("1", "1"))


class TakingOver(test_access.Home):
    def opened(self, stored, args, whose="mine", own=False):
        calls = []
        with mock.patch.object(settings, "STORE", stored), mock.patch.object(address, "whose", return_value=whose), \
                mock.patch.object(launcher, "listener", return_value=4711), mock.patch.object(launcher, "ours", return_value=own), \
                mock.patch.object(launcher, "stop", lambda any_daytag=False: calls.append(any_daytag)), \
                mock.patch.object(launcher, "start", return_value=""), mock.patch.object(launcher, "show"):
            launcher.main(args)
        return calls

    def test_opening_the_one_from_the_store_ends_the_other_one(self):
        self.assertEqual(self.opened(True, []), [True])
        # Not its own, not at sign-in, not someone else's, and never the other way round.
        self.assertEqual(self.opened(True, [], own=True), [])
        self.assertEqual(self.opened(True, ["--start"]), [])
        self.assertEqual(self.opened(True, [], whose="other"), [])
        self.assertEqual(self.opened(False, []), [])


class Package(unittest.TestCase):
    def setUp(self):
        self.text = store.manifest(store.TEST, "1.2.0.0", False)
        self.root = ET.fromstring(self.text)

    def test_the_version_counts_on_and_is_one_the_store_takes(self):
        self.assertEqual([store.store_version(v) for v in ("0.2.0", "0.2.1", "0.10.0", "1.0.0")],
                         ["1.2.0.0", "1.2.1.0", "1.10.0.0", "2.0.0.0"])
        self.assertEqual(self.root.find(F + "Identity").get("Version"), "1.2.0.0")

    def test_it_starts_the_windowless_python_and_asks_for_nothing_but_full_trust(self):
        app, = self.root.find(F + "Applications")
        self.assertEqual((app.get("Executable"), app.get("EntryPoint"), app.get(UAP10 + "Parameters")),
                         (r"python\pythonw.exe", "Windows.FullTrustApplication", "-m launcher"))
        self.assertEqual([c.get("Name") for c in self.root.find(F + "Capabilities")], ["runFullTrust"])
        start = app.find(F + "Extensions").find(DESKTOP + "Extension")
        self.assertEqual((start.get("Category"), start.get(UAP10 + "Parameters")), ("windows.startupTask", "-m launcher --start"))
        self.assertEqual(self.root.find(F + "Properties").find(UAP17 + "UpdateWhileInUse").text, "defer")

    def test_it_changes_nothing_in_windows(self):
        self.assertIsNone(self.root.find(F + "Extensions"))
        self.assertNotIn("firewall", self.text.lower())

    def test_every_logo_it_names_is_there_in_every_size(self):
        named = {self.root.find(F + "Properties").find(F + "Logo").text}
        look = self.root.find(F + "Applications")[0].find(UAP + "VisualElements")
        named |= {look.get("Square150x150Logo"), look.get("Square44x44Logo")}
        self.assertEqual(len(named), 3)
        for logo in named:
            base, size = logo[len("Assets\\"):-len(".png")], {"StoreLogo": 50}.get(logo[len("Assets\\"):-len(".png")], 0)
            size = size or int(re.search(r"(\d+)x", base).group(1))
            for scale in (100, 125, 150, 200, 400):
                head = (ROOT / "packaging" / "store" / "Assets" / ("%s.scale-%d.png" % (base, scale))).read_bytes()[:24]
                wide, high = struct.unpack(">II", head[16:24])
                self.assertEqual(wide, high)
                self.assertLess(abs(wide - size * scale / 100.0), 1.0, (base, scale))

    def test_the_probe_is_in_test_builds_only(self):
        self.assertNotIn("robe", self.text)
        with mock.patch.object(sys, "argv", ["store.py", "--probe"]), mock.patch.object(sys, "stderr"), self.assertRaises(SystemExit) as end:
            store.main()
        self.assertEqual(end.exception.code, 2)
        self.assertEqual(len(ET.fromstring(store.manifest(store.TEST, "1.2.0.0", True)).find(F + "Applications")), 2)

    def test_a_name_cannot_break_the_manifest(self):
        names = {"name": "A.Daytag", "publisher": 'CN="X & Y", O=<Z>', "display": "Tom & Co <x>"}
        root = ET.fromstring(store.manifest(names, "1.2.0.0", False))
        self.assertEqual(root.find(F + "Identity").get("Publisher"), names["publisher"])
        self.assertEqual(root.find(F + "Properties").find(F + "PublisherDisplayName").text, names["display"])

    def test_without_the_stores_names_nothing_is_built(self):
        with mock.patch.object(store, "STORE", ROOT / "tests"):
            with self.assertRaises(SystemExit):
                store.identity(False)
        self.assertEqual(store.identity(True), store.TEST)
        own = ROOT / "packaging" / "store" / "identity.json"
        if own.is_file():
            self.assertEqual(sorted(store.identity(False)), ["display", "name", "publisher"])

    def test_the_store_is_known_by_its_manifest(self):
        self.assertFalse(settings.STORE)


if __name__ == "__main__":
    unittest.main()
