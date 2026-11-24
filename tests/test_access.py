"""Who gets in: the owner's key, the launcher's ticket, a second person on the same computer, and what a foreign page
cannot do. Real servers on real sockets, on loopback only."""
import http.client
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import address
import calendar_feed
import server
import settings
import slack_notify
import sources


class Home(unittest.TestCase):
    """A Brento of its own in a throwaway folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"BRENTO_HOME": self.tmp.name})
        self.env.start()
        os.environ.pop("BRENTO_PORT", None)
        self.kept = server.Handler.app, sources.ME, sources.ME_LOGIN

    def tearDown(self):
        server.Handler.app, sources.ME, sources.ME_LOGIN = self.kept
        sources.set_skip([])
        self.env.stop()
        sources.load_private(Path(__file__).resolve().parent / "stand-in-terms.txt")
        self.tmp.cleanup()


class Door(Home):
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

    def call(self, method, path, body=None, **headers):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        given = {"Host": "127.0.0.1:%d" % self.port}
        given.update({k.replace("_", "-"): v for k, v in headers.items()})
        conn.request(method, path, body=body, headers=given)
        reply = conn.getresponse()
        out = reply.status, reply, reply.read()
        conn.close()
        return out

    def test_without_the_key_nothing_opens(self):
        status, _, body = self.call("GET", "/")
        self.assertEqual(status, 401)
        self.assertIn(b"Open Brento with its icon", body)
        for path in ("/app.js", "/style.css", "/api/state", "/api/setup", "/api/wizard", "/api/phone", "/api/tools", "/api/library",
                     "/api/wizard/vault?path=C%3A%5C", "/api/library/page?path=x.html"):
            self.assertEqual(self.call("GET", path, X_Leitstand="1")[0], 401, path)
        for path in ("/api/ticket", "/api/setup", "/api/ask", "/api/phone", "/api/wizard/open"):
            self.assertEqual(self.call("POST", path, body=b"{}", X_Leitstand="1")[0], 401, path)
        for word in ("", "wrong", "ä"):
            self.assertEqual(self.call("GET", "/", Cookie=("leitstand=" + word).encode("utf-8"))[0], 401)

    def test_a_ticket_lets_one_browser_in_once(self):
        word = self.app.ticket()
        status, reply, _ = self.call("GET", "/?ticket=" + word)
        self.assertEqual((status, reply.getheader("Location")), (303, "/"))
        given = reply.getheader("Set-Cookie")
        for part in ("leitstand=" + self.app.key, "HttpOnly", "SameSite=Strict"):
            self.assertIn(part, given)
        cookie = given.split(";")[0]
        self.assertEqual(self.call("GET", "/", Cookie=cookie)[0], 200)
        self.assertEqual(self.call("GET", "/api/tools", Cookie=cookie, X_Leitstand="1")[0], 200)
        # The same ticket again gives nothing, and the address is cleaned all the same.
        status, reply, _ = self.call("GET", "/?ticket=" + word)
        self.assertEqual((status, reply.getheader("Location"), reply.getheader("Set-Cookie")), (303, "/", None))

    def test_a_ticket_runs_out(self):
        word = self.app.ticket()
        with mock.patch.object(server.time, "monotonic", return_value=time.monotonic() + server.TICKET_SECONDS + 1):
            self.assertFalse(self.app.redeem(word))
        self.assertFalse(self.app.redeem(""))

    def test_cookies_of_other_programs_do_not_hide_ours(self):
        for other in ('_xsrf={"a": 1, "b": "x y"}; ', "odd cookie; ", "a=b; =c; "):
            self.assertEqual(self.call("GET", "/", Cookie=other + "leitstand=" + self.app.key)[0], 200, other)

    def test_a_link_from_elsewhere_cannot_make_brento_read_a_folder(self):
        # A browser sends the cookie with a click inside Brento, but a link, a picture or a redirect carries no header.
        cookie = "leitstand=" + self.app.key
        with mock.patch.object(server.wizard, "vault_stats") as look:
            for path in ("/api/wizard/vault?path=%5C%5Cserver%5Cshare", "/api/wizard", "/api/wizard/gh", "/api/setup", "/api/state"):
                self.assertEqual(self.call("GET", path, Cookie=cookie)[0], 403, path)
            look.assert_not_called()

    def test_a_page_of_the_notes_folder_gets_none_of_brentos_rights(self):
        self.assertTrue(server.CSP_PAGE.startswith("sandbox allow-scripts;"))
        self.assertNotIn("allow-same-origin", server.CSP_PAGE)

    def test_a_foreign_host_name_is_refused_even_with_the_key(self):
        self.assertEqual(self.call("GET", "/", Host="evil.example", Cookie="leitstand=" + self.app.key)[0], 403)

    def test_the_owner_is_recognised_without_saying_the_key(self):
        self.assertEqual(address.whose(self.port), "mine")
        self.assertRegex(address.entrance(self.port), r"^http://127\.0\.0\.1:%d/\?ticket=[\w-]{20,}$" % self.port)
        self.assertEqual(self.call("GET", "/api/whose?n=short")[0], 400)
        said = []
        real = address.ask
        with mock.patch.object(address, "ask", side_effect=lambda *a, **k: said.append((a, k)) or real(*a, **k)):
            with tempfile.TemporaryDirectory() as other, mock.patch.dict(os.environ, {"BRENTO_HOME": other}):
                # Another person on the same computer, with a key of their own or with none yet.
                self.assertEqual(address.whose(self.port), "other")
                address.load_key(Path(other))
                self.assertEqual(address.whose(self.port), "other")
                self.assertEqual(address.entrance(self.port), "http://127.0.0.1:%d/" % self.port)
        self.assertNotIn(self.app.key, repr(said))

    def test_an_answer_passed_on_from_another_port_does_not_count(self):
        nonce = "n" * 24
        self.assertNotEqual(address.proof(self.app.key, 8770, nonce), address.proof(self.app.key, 8772, nonce))

    def test_the_phone_door_knows_nothing_of_all_this(self):
        self.assertFalse(server.phone.allowed("GET", "/api/whose"))
        self.assertFalse(server.phone.allowed("POST", "/api/ticket"))


class Other(BaseHTTPRequestHandler):
    """Another program, or a Brento from before the key."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b'{"error": "not found"}')


class Neighbours(Home):
    def serve(self, name):
        kind = type("Kind", (Other,), {"server_version": name, "sys_version": ""})
        srv = server.Server(("127.0.0.1", 0), kind)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return srv.server_address[1]

    def test_what_answers_on_a_port(self):
        self.assertEqual(address.whose(self.serve("SimpleHTTP")), "")
        self.assertEqual(address.whose(self.serve("Brento")), "older")
        with socket.socket() as free:
            free.bind(("127.0.0.1", 0))
            self.assertEqual(address.whose(free.getsockname()[1]), "")

    def test_the_port_is_kept_and_a_strange_one_is_not_believed(self):
        self.assertEqual(address.port(), address.FIRST)
        address.keep(address.FIRST + 4)
        self.assertEqual(address.port(), address.FIRST + 4)
        self.assertEqual(address.candidates()[:2], [address.FIRST + 4, address.FIRST])
        for strange in ("22", "8771", "x", ""):
            (self.home / "port").write_text(strange, encoding="utf-8")
            self.assertEqual(address.port(), address.FIRST, strange)
        self.assertEqual(address.candidates(9999), [9999])

    def test_two_people_on_one_computer_each_get_their_own(self):
        def start(home):
            env = dict(os.environ, BRENTO_HOME=str(home), PYTHONIOENCODING="utf-8")
            env.pop("BRENTO_PORT", None)
            return subprocess.Popen([sys.executable, "-X", "utf8", str(ROOT / "server.py")], env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def ready(home):
            ends = time.monotonic() + 60
            while time.monotonic() < ends:
                with mock.patch.dict(os.environ, {"BRENTO_HOME": str(home)}):
                    if address.whose() == "mine":
                        return address.port()
                time.sleep(0.3)
            return 0

        with tempfile.TemporaryDirectory() as anna, tempfile.TemporaryDirectory() as ben:
            running = []
            try:
                running.append(start(anna))
                first = ready(anna)
                self.assertTrue(first)
                running.append(start(ben))
                second = ready(ben)
                self.assertTrue(second)
                self.assertNotEqual(first, second)
                with mock.patch.dict(os.environ, {"BRENTO_HOME": ben}):
                    self.assertEqual(address.whose(first), "other")
                # Anna opens it twice: the second one sees that hers runs, and ends.
                again = start(anna)
                running.append(again)
                said = again.communicate(timeout=60)[0].decode("utf-8", "replace")
                self.assertEqual(again.returncode, 0, said)
                self.assertIn("is not started", said)
            finally:
                for proc in running:
                    proc.kill()
                    proc.communicate()
            time.sleep(0.3)


class LostFolder(Home):
    def test_a_renamed_notes_folder_does_not_keep_brento_from_starting(self):
        vault = self.home / "My notes"
        vault.mkdir()
        (vault / "a.md").write_text("- [ ] Send the offer \U0001f4c5 2099-01-02\n", encoding="utf-8")
        settings.save({"name": "Alex", "vault": str(vault), "sources": {"tasks": {"on": True}, "library": {"on": True}}})
        vault.rename(self.home / "My new notes")
        app = server.App(None, "127.0.0.1", [], "sonnet")
        self.assertFalse(app.needs_setup)
        self.assertFalse(vault.exists())
        tasks = next(s for s in app.state()["sources"] if s["id"] == "tasks")
        self.assertEqual(tasks["state"], "unknown")
        with mock.patch.object(sources, "gh_status", return_value={"ready": False, "reason": ""}):
            self.assertTrue(app.setup_view()["vaultMissing"])
        with self.assertRaises(ValueError):
            settings.save(dict(app.profile))
        # Choosing it again under its new name is all it takes.
        app.apply_profile(settings.save(dict(app.profile, vault=str(self.home / "My new notes"))))
        tasks = next(s for s in app.state()["sources"] if s["id"] == "tasks")
        self.assertEqual(tasks["state"], "fresh")


class Ask(unittest.TestCase):
    def test_the_notes_folder_can_neither_start_a_program_nor_open_other_folders(self):
        args = server.ask_command("claude", "sonnet", "Alex")
        self.assertEqual(args[args.index("--setting-sources") + 1], "user")
        locked = json.loads(Path(args[args.index("--settings") + 1]).read_text(encoding="utf-8"))
        self.assertTrue(locked["disableAllHooks"])
        self.assertTrue(locked["permissions"]["blockReadsOutsideWorkingDirectories"])
        self.assertEqual(args[args.index("--permission-mode") + 1], "dontAsk")
        self.assertNotIn("--allowedTools", args)
        self.assertEqual(args[args.index("--tools") + 1], "Read,Grep,Glob")
        self.assertIn("--strict-mcp-config", args)


class Links(Home):
    CAL = "https://calendar.google.com/calendar/ical/x/private-y/basic.ics"
    HOOK = "https://hooks.slack.com/services/T0ABCDEF/B0ABCDEF/abcdefABCDEF123456"

    def test_a_calendar_link_is_kept_only_when_it_answers(self):
        feed = calendar_feed.Feed(self.home / "calendar-url")
        with mock.patch.object(calendar_feed.Feed, "read", staticmethod(lambda url: "BEGIN:VCALENDAR")):
            feed.connect(self.CAL)
        self.assertEqual(feed.url(), self.CAL)
        with mock.patch.object(calendar_feed.Feed, "read", side_effect=OSError("timed out " + self.CAL)):
            with self.assertRaises(ValueError) as caught:
                feed.connect(self.CAL.replace("basic", "other"))
        self.assertNotIn("calendar.google", str(caught.exception))
        self.assertEqual(feed.url(), self.CAL)
        with self.assertRaises(ValueError) as caught:
            feed.connect("")
        self.assertIn("Paste the link", str(caught.exception))
        self.assertTrue(feed.connected())

    def test_a_slack_link_is_kept_only_when_a_message_went_through(self):
        slack = slack_notify.Slack(self.home)
        with mock.patch.object(slack, "send", return_value="") as send:
            slack.connect(self.HOOK, "hello")
            send.assert_called_once_with("hello", self.HOOK)
        with mock.patch.object(slack, "send", return_value="Slack refused the message (404). Make a new webhook link."):
            with self.assertRaises(ValueError):
                slack.connect(self.HOOK.replace("abc", "xyz"), "hello")
        self.assertEqual(slack.url(), self.HOOK)
        with self.assertRaises(ValueError):
            slack.connect("  ", "hello")

    def test_an_empty_field_never_counts_as_connected(self):
        app = server.App(None, "127.0.0.1", [], "sonnet")
        server.Handler.app = app
        srv = server.Server(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            for path in ("/api/calendar", "/api/slack"):
                for body in ({}, {"url": ""}, {"url": "   "}):
                    conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
                    conn.request("POST", path, json.dumps(body), {"X-Leitstand": "1", address.KEY_HEADER: app.key})
                    reply = conn.getresponse()
                    self.assertEqual((reply.status, json.loads(reply.read())["error"]), (400, "Paste the link first."), (path, body))
                    conn.close()
        finally:
            srv.shutdown()
            srv.server_close()


def has_zones():
    try:
        return bool(calendar_feed.ZoneInfo("America/New_York"))
    except Exception:
        return False


class Reading(unittest.TestCase):
    def test_a_folder_that_is_gone_or_locked_is_never_an_empty_one(self):
        today = calendar_feed.date(2026, 11, 24)
        index = sources.TaskIndex(Path(tempfile.gettempdir()) / "no such folder of notes")
        data, src = sources.read_tasks(index, today)
        self.assertEqual((src["state"], src["note"]), ("unknown", "the notes folder is not there"))
        with mock.patch.object(sources.os, "listdir", side_effect=PermissionError):
            data, src = sources.read_tasks(index, today)
            self.assertEqual((src["state"], src["note"]), ("unknown", "Brento may not read the notes folder"))

    def test_a_meeting_with_a_join_link_counts_without_a_guest_list(self):
        text = ("BEGIN:VEVENT\nDTSTART:20261125T100000\nSUMMARY:Budget\n"
                "DESCRIPTION:https://teams.microsoft.com/l/meetup-join/x\nEND:VEVENT")
        event = calendar_feed.parse_ics(text, calendar_feed.date(2026, 11, 24))[0]
        self.assertTrue(sources.event_matters(event))
        self.assertTrue(slack_notify.event_matters(event))

    @unittest.skipUnless(has_zones(), "this Python has no time zone data")
    def test_other_time_zones_by_either_name(self):
        for name in ("America/New_York", "Eastern Standard Time", '"Eastern Standard Time"'):
            day, clock, unknown = calendar_feed._start(";TZID=%s" % name, "20261126T100000")
            here = calendar_feed.datetime(2026, 11, 26, 15, tzinfo=calendar_feed.timezone.utc).astimezone()
            self.assertEqual((day, clock, unknown), (here.date(), here.strftime("%H:%M"), ""), name)

    def test_a_time_that_cannot_be_converted_says_whose_it_is(self):
        text = "BEGIN:VEVENT\nDTSTART;TZID=Customized Time Zone:20261125T100000\nSUMMARY:Call\nLOCATION:Room 1\nEND:VEVENT"
        event = calendar_feed.parse_ics(text, calendar_feed.date(2026, 11, 24))[0]
        self.assertEqual((event["time"], event["where"]), ("10:00", "10:00 is the time in Customized Time Zone. Room 1"))

    def test_slack_waits_for_a_source_and_then_names_it(self):
        when = calendar_feed.datetime
        state = {"sources": [{"id": "calendar", "label": "Calendar", "state": "unknown", "note": "still loading"},
                             {"id": "tasks", "label": "Obsidian tasks", "state": "fresh", "note": ""}], "alerts": [], "events": []}
        cfg = {"digest": "08:00", "alerts": True, "remind": 10, "sources": ["calendar", "tasks"]}
        texts, memory = slack_notify.plan(state, cfg, {"seeded": True, "seen": []}, when(2026, 11, 24, 8, 1))
        self.assertEqual(texts, [])
        # Read a moment later: the plain summary.
        fine = dict(state, sources=[dict(s, state="fresh", note="") for s in state["sources"]])
        self.assertIn("Enjoy the calm", slack_notify.plan(fine, cfg, memory, when(2026, 11, 24, 8, 2))[0][0])
        # Never read: named, and nothing is called calm.
        texts, memory = slack_notify.plan(state, cfg, memory, when(2026, 11, 24, 8, 20))
        self.assertIn("Calendar could not be read", texts[0])
        self.assertNotIn("calm", texts[0])
        self.assertEqual(memory["digest"], "2026-11-24")
        # A calendar nobody connected holds nothing up.
        never = dict(state, sources=[dict(s, note="not connected yet") for s in state["sources"]])
        self.assertIn("Enjoy the calm", slack_notify.plan(never, cfg, {"seeded": True, "seen": []}, when(2026, 11, 24, 8, 1))[0][0])

    def test_a_summary_that_did_not_get_through_is_tried_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            slack = slack_notify.Slack(tmp)
            slack.hook_path.write_text("https://hooks.slack.com/services/T0/B0/x", encoding="utf-8")
            state = {"sources": [], "alerts": [], "events": []}
            cfg = {"digest": "08:00", "alerts": True, "remind": 0, "sources": []}
            now = calendar_feed.datetime(2026, 11, 24, 8, 1)
            with mock.patch.object(slack, "send", return_value="Slack did not answer."):
                self.assertEqual(slack.tick(state, cfg, "", now), [])
            with mock.patch.object(slack, "send", return_value=""):
                self.assertEqual(len(slack.tick(state, cfg, "", now)), 1)
                self.assertEqual(slack.tick(state, cfg, "", now), [])


class SlackLoop(Home):
    def test_nothing_goes_out_before_the_setup_is_finished(self):
        app = server.App(None, "127.0.0.1", [], "sonnet")
        app.slack.hook_path.write_text("https://hooks.slack.com/services/T0/B0/x", encoding="utf-8")
        rounds = iter([None, StopIteration])

        def one_round(_):
            if next(rounds) is StopIteration:
                raise KeyboardInterrupt
        for setup, calls in ((True, 0), (False, 1)):
            rounds = iter([None, StopIteration])
            app.needs_setup = setup
            with mock.patch.object(server.time, "sleep", one_round), mock.patch.object(app.slack, "tick") as tick:
                with self.assertRaises(KeyboardInterrupt):
                    app.notify_loop()
                self.assertEqual(tick.call_count, calls)


class AppleTools(unittest.TestCase):
    def test_githubs_program_finds_no_placeholder_either(self):
        for system, git, expected in (("darwin", None, os.path.dirname("/x/bin/gh")), ("darwin", "/usr/bin/git", None), ("win32", None, None)):
            with mock.patch.object(settings, "system", return_value=system), mock.patch.object(settings, "find_exe", return_value=git), \
                    mock.patch.object(server.wizard.subprocess, "Popen") as popen, mock.patch.object(server.wizard.threading, "Thread"):
                server.wizard.SignIn().start("gh-login", ["/x/bin/gh", "auth", "login"])
                self.assertEqual(popen.call_args[1]["env"].get("PATH"), expected or os.environ.get("PATH"), system)

    def test_git_is_left_alone_on_a_mac_without_developer_tools(self):
        which = lambda name, path=None: "/usr/bin/git" if path is None else None
        with mock.patch.object(settings, "system", return_value="darwin"), mock.patch.object(settings.shutil, "which", which):
            with mock.patch.object(settings, "apple_tools", return_value=False):
                self.assertIsNone(settings.find_exe("git"))
                with mock.patch.object(sources.subprocess, "run") as run:
                    self.assertEqual(sources.git("/x", "log"), "")
                    self.assertFalse(sources.fetch_remote("/x"))
                    run.assert_not_called()
            with mock.patch.object(settings, "apple_tools", return_value=True):
                self.assertEqual(settings.find_exe("git"), "/usr/bin/git")

    @unittest.skipUnless(sys.platform == "win32", "Windows only")
    def test_claude_is_found_where_its_own_installer_puts_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".local" / "bin").mkdir(parents=True)
            (Path(tmp) / ".local" / "bin" / "claude.exe").write_bytes(b"")
            with mock.patch.object(settings.shutil, "which", side_effect=lambda n, path=None, real=settings.shutil.which: None if path is None else real(n, path=path)), \
                    mock.patch.object(settings.Path, "home", return_value=Path(tmp)), mock.patch.dict(os.environ, {"BRENTO_HOME": tmp}),                     mock.patch.dict(sys.modules, {"winreg": None}):
                self.assertTrue(re.search(r"\.local.bin.claude\.exe$", settings.find_exe("claude") or "", re.I))


if __name__ == "__main__":
    unittest.main()
