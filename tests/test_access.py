"""Who gets in: the owner's key, the launcher's ticket, a second person on the same computer, and what a foreign page
cannot do. Real servers on real sockets, on loopback only."""
import contextlib
import hashlib
import hmac
import http.client
import io
import json
import os
import re
import shutil
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


def sign(word, method, path, host, body=b"", now=None, run=None):
    """What web/sign.js does, so a test can sign for something else than it sends."""
    stamp = str(int((time.time() if now is None else now) * 1000))
    total = hashlib.sha256(body).hexdigest() if body else "-"
    run = word["run"] if run is None else run
    text = "\n".join((method, path, host, stamp, total, run))
    return ".".join((word["id"], stamp, total, run, hmac.new(word["word"].encode(), text.encode(), hashlib.sha256).hexdigest()))


def answer(word, head):
    """What a page expects the answer to such a request to be signed with."""
    return hmac.new(word["word"].encode(), ("answer\n" + head.split(".")[4]).encode(), hashlib.sha256).hexdigest()


class Door(Home):
    def setUp(self):
        super().setUp()
        self.app = server.App(None, "127.0.0.1", [], "sonnet")
        server.Handler.app = self.app
        self.srv = server.Server(("127.0.0.1", 0), server.Handler)
        self.port = self.app.port = self.srv.server_address[1]
        self.host = "127.0.0.1:%d" % self.port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def call(self, method, path, body=None, **headers):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        given = {"Host": self.host}
        given.update({k.replace("_", "-"): v for k, v in headers.items()})
        conn.request(method, path, body=body, headers=given)
        reply = conn.getresponse()
        out = reply.status, reply, reply.read()
        conn.close()
        return out

    def let_in(self):
        status, _, body = self.call("POST", "/api/enter", json.dumps({"ticket": self.app.ticket()}), X_Leitstand="1")
        self.assertEqual(status, 200)
        return json.loads(body)

    def test_without_being_let_in_there_is_only_the_empty_frame(self):
        for path in ("/", "/app.js", "/sign.js", "/style.css"):
            self.assertEqual(self.call("GET", path)[0], 200, path)
        # What a page of 0.1.0 that is still open gets, so that it loads the new one.
        status, _, body = self.call("GET", "/api/state")
        self.assertEqual((status, sorted(json.loads(body))), (200, ["locked", "webVersion"]))
        for path in ("/api/state", "/api/setup", "/api/wizard", "/api/phone", "/api/tools", "/api/library", "/api/ask/status",
                     "/api/wizard/vault?path=C%3A%5C", "/api/library/seal?path=x.html", "/api/library/asset?path=x.png&s="):
            status, reply, body = self.call("GET", path, X_Leitstand="1")
            self.assertEqual((status, json.loads(body)["locked"], reply.getheader("X-Brento-Run"), reply.getheader("X-Brento-Answer")),
                             (401, True, self.app.browsers.run, None), path)
        for path in ("/api/ticket", "/api/setup", "/api/ask", "/api/phone", "/api/wizard/open"):
            self.assertEqual(self.call("POST", path, body=b"{}", X_Leitstand="1")[0], 401, path)
        for given in ({}, {"ticket": ""}, {"ticket": "x"}, {"key": ""}, {"key": "x"}, {"ticket": None, "key": ["x"]}):
            self.assertEqual(self.call("POST", "/api/enter", json.dumps(given), X_Leitstand="1")[0], 401, given)
        # A cookie opens nothing, because a browser gives it to every program on 127.0.0.1.
        self.assertEqual(self.call("GET", "/api/tools", X_Leitstand="1", Cookie="leitstand=" + self.app.key)[0], 401)

    def test_a_ticket_gives_one_browser_its_word_once(self):
        ticket = json.dumps({"ticket": self.app.ticket()})
        status, reply, body = self.call("POST", "/api/enter", ticket, X_Leitstand="1")
        self.assertEqual((status, reply.getheader("Set-Cookie")), (200, None))
        word = json.loads(body)
        self.assertEqual(self.call("POST", "/api/enter", ticket, X_Leitstand="1")[0], 401)
        self.assertEqual(self.call("GET", "/api/tools", X_Leitstand="1", X_Brento_Sign=sign(word, "GET", "/api/tools", self.host))[0], 200)
        self.assertNotIn("locked", json.loads(self.call("GET", "/api/state", X_Leitstand="1", X_Brento_Sign=sign(word, "GET", "/api/state", self.host))[2]))
        # Where other people have an account, it ends with the run that gave it, and no file is left.
        self.assertEqual(address.Browsers(self.home, keep=False).words, {})
        self.assertFalse((self.home / "browsers.json").exists())
        address.Browsers(self.home, keep=True).write(self.app.browsers.words)
        # Elsewhere it is kept over a restart, for the address it was given at, and readable for the owner only. What was
        # signed for the run before is worth nothing.
        again = address.Browsers(self.home, keep=True)
        self.assertNotEqual(again.run, word["run"])
        self.assertIsNone(again.signed(sign(word, "GET", "/x", self.host), "GET", "/x", self.host))
        head = sign(word, "GET", "/x", self.host, run=again.run)
        self.assertEqual(again.signed(head, "GET", "/x", self.host), ("-", answer(word, head)))
        self.assertIsNone(again.signed(sign(word, "GET", "/x", "127.0.0.1:8772", run=again.run), "GET", "/x", "127.0.0.1:8772"))
        if os.name == "posix":
            self.assertEqual((self.home / "browsers.json").stat().st_mode & 0o077, 0)
        # Something else was found at that address: what a browser keeps for it opens nothing any more.
        again.forget()
        self.assertIsNone(again.signed(head, "GET", "/x", self.host))
        self.assertEqual(address.Browsers(self.home, keep=True).words, {})

    def test_whether_others_have_an_account_here(self):
        self.assertIn(address.shared(), (True, False))
        # When it cannot be told, yes.
        with mock.patch.object(address.os, "scandir", side_effect=OSError), mock.patch.dict(sys.modules, {"winreg": None}):
            self.assertTrue(address.shared())

    def test_the_answer_shows_that_it_comes_from_brento(self):
        word = self.let_in()
        head = sign(word, "GET", "/api/tools", self.host)
        self.assertEqual(self.call("GET", "/api/tools", X_Leitstand="1", X_Brento_Sign=head)[1].getheader("X-Brento-Answer"), answer(word, head))
        # Also when the answer is a refusal, and never for what was not signed.
        head = sign(word, "GET", "/api/nothing", self.host)
        status, reply, _ = self.call("GET", "/api/nothing", X_Leitstand="1", X_Brento_Sign=head)
        self.assertEqual((status, reply.getheader("X-Brento-Answer")), (404, answer(word, head)))
        self.assertIsNone(self.call("GET", "/app.js")[1].getheader("X-Brento-Answer"))

    def test_the_word_a_browser_had_ends_when_it_comes_in_again(self):
        first, other = self.let_in(), self.let_in()
        self.assertNotEqual(first["id"], other["id"])
        status, _, body = self.call("POST", "/api/enter", json.dumps({"ticket": self.app.ticket(), "old": first["id"]}), X_Leitstand="1")
        second = json.loads(body)
        self.assertEqual(status, 200)
        for word, good in ((first, 401), (second, 200), (other, 200)):
            self.assertEqual(self.call("GET", "/api/tools", X_Leitstand="1", X_Brento_Sign=sign(word, "GET", "/api/tools", self.host))[0], good)
        # Without a ticket nobody can end a word.
        self.call("POST", "/api/enter", json.dumps({"ticket": "x", "old": second["id"]}), X_Leitstand="1")
        self.assertEqual(self.call("GET", "/api/tools", X_Leitstand="1", X_Brento_Sign=sign(second, "GET", "/api/tools", self.host))[0], 200)

    def test_a_ticket_is_not_taken_at_another_address(self):
        ticket = json.dumps({"ticket": self.app.ticket()})
        self.assertEqual(self.call("POST", "/api/enter", ticket, X_Leitstand="1", Host="127.0.0.1:%d" % (self.port + 1))[0], 401)
        # And on Linux not from a program of another account. The ticket is still good after that.
        with mock.patch.object(address, "peer_uid", return_value=4711), mock.patch.object(server.os, "getuid", return_value=1000, create=True):
            self.assertEqual(self.call("POST", "/api/enter", ticket, X_Leitstand="1")[0], 401)
            # The owner's key opens whichever program brings it: nobody else can read that.
            self.assertEqual(self.call("POST", "/api/enter", json.dumps({"key": self.app.key}), X_Leitstand="1")[0], 200)
        self.assertEqual(self.call("POST", "/api/enter", ticket, X_Leitstand="1")[0], 200)

    @unittest.skipUnless(sys.platform.startswith("linux"), "only Linux says whose program is at the other end")
    def test_linux_says_whose_program_is_asking(self):
        with socket.create_connection(("127.0.0.1", self.port), timeout=10) as conn:
            self.assertEqual(address.peer_uid(conn.getsockname(), conn.getpeername()), os.getuid())
        # Also when it comes with an IPv6 socket to the same address.
        try:
            six = socket.socket(socket.AF_INET6)
            six.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            six.connect(("::ffff:127.0.0.1", self.port))
        except OSError:
            self.skipTest("no IPv6 here")
        with six:
            self.assertEqual(address.peer_uid(("127.0.0.1", six.getsockname()[1]), ("127.0.0.1", self.port)), os.getuid())
        self.assertIsNone(address.peer_uid(("127.0.0.1", 1), ("127.0.0.1", 2)))

    def test_a_signature_is_good_for_one_request_to_one_address(self):
        word = self.let_in()
        good = sign(word, "GET", "/api/tools", self.host)
        self.assertEqual(self.call("GET", "/api/tools", X_Leitstand="1", X_Brento_Sign=good)[0], 200)
        self.assertEqual(self.call("GET", "/api/setup", X_Leitstand="1", X_Brento_Sign=good)[0], 401)
        self.assertEqual(self.call("GET", "/api/tools?x=1", X_Leitstand="1", X_Brento_Sign=good)[0], 401)
        self.assertEqual(self.call("POST", "/api/tools", b"{}", X_Leitstand="1", X_Brento_Sign=good)[0], 401)
        # Overheard by a program on another port, and passed on from there with that address or with this one.
        other = "127.0.0.1:%d" % (self.port + 1)
        heard = sign(word, "GET", "/api/tools", other)
        self.assertEqual(self.call("GET", "/api/tools", X_Leitstand="1", X_Brento_Sign=heard)[0], 401)
        self.assertEqual(self.call("GET", "/api/tools", X_Leitstand="1", X_Brento_Sign=heard, Host=other)[0], 401)
        self.assertEqual(self.call("GET", "/api/tools", X_Leitstand="1", X_Brento_Sign=sign(word, "GET", "/api/tools", "127.0.0.1"), Host="127.0.0.1")[0], 401)
        # Too old, from the future, of an unknown browser, or out of shape.
        day = address.SIGN_SECONDS + 1
        for bad in (sign(word, "GET", "/api/tools", self.host, now=time.time() - day), sign(word, "GET", "/api/tools", self.host, now=time.time() + day),
                    sign(dict(word, id="nobody"), "GET", "/api/tools", self.host), sign(dict(word, word="0" * 64), "GET", "/api/tools", self.host),
                    sign(word, "GET", "/api/tools", self.host, run=""), sign(word, "GET", "/api/tools", self.host, run="0" * 16),
                    "", "....", "a.b.c.d", "a.b.c.d.e", "a.b.c.d.e.f", good + "0"):
            self.assertEqual(self.call("GET", "/api/tools", X_Leitstand="1", X_Brento_Sign=bad)[0], 401, bad)

    def test_a_signed_body_cannot_be_exchanged(self):
        word = self.let_in()
        body = json.dumps({"action": "card", "id": "x"}).encode()
        head = sign(word, "POST", "/api/tools", self.host, body)
        self.assertEqual(self.call("POST", "/api/tools", body, X_Leitstand="1", X_Brento_Sign=head)[0], 200)
        self.assertEqual(self.call("POST", "/api/tools", body.replace(b'"x"', b'"y"'), X_Leitstand="1", X_Brento_Sign=head)[0], 400)
        for odd in (b"[]", b"1", b"null", b"not json"):
            self.assertEqual(self.call("POST", "/api/tools", odd, X_Leitstand="1", X_Brento_Sign=sign(word, "POST", "/api/tools", self.host, odd))[0], 400, odd)

    def test_a_ticket_runs_out(self):
        word = self.app.ticket()
        with mock.patch.object(server.time, "monotonic", return_value=time.monotonic() + server.TICKET_SECONDS + 1):
            self.assertFalse(self.app.redeem(word))
        self.assertFalse(self.app.redeem(""))

    def test_cookies_of_other_programs_do_not_hide_a_phones(self):
        for other in ('_xsrf={"a": 1, "b": "x y"}; ', "odd cookie; ", "a=b; =c; "):
            self.assertEqual(server.cookie(other + "brento_phone=abc; z=1", "brento_phone"), "abc", other)
        self.assertEqual(server.cookie(None, "x"), "")

    def test_a_link_from_elsewhere_cannot_make_brento_read_a_folder(self):
        with mock.patch.object(server.wizard, "vault_stats") as look:
            for path in ("/api/wizard/vault?path=%5C%5Cserver%5Cshare", "/api/wizard", "/api/wizard/gh", "/api/setup"):
                self.assertEqual(self.call("GET", path)[0], 401, path)
                # Not even with the right to ask: a link carries no header.
                self.assertEqual(self.call("GET", path, X_Brento_Key=self.app.key)[0], 403, path)
            look.assert_not_called()

    def test_a_picture_in_a_note_loads_by_its_sealed_address_only(self):
        vault = self.home / "vault"
        vault.mkdir()
        (vault / "a b.png").write_bytes(b"png")
        (vault / "other.png").write_bytes(b"other")
        (vault / "n.md").write_text("![[a b.png]]", encoding="utf-8")
        self.app.apply_profile(settings.save({"vault": str(vault), "sources": {"library": {"on": True}}}))
        html = self.app.library.note("n.md")["html"]
        src = re.search(r'src="([^"]+)"', html).group(1).replace("&amp;", "&")
        status, _, body = self.call("GET", src)
        self.assertEqual((status, body), (200, b"png"))
        self.assertEqual(self.call("GET", src.split("&s=")[0])[0], 401)
        self.assertEqual(self.call("GET", src.replace("a%20b.png", "other.png"))[0], 401)

    def test_a_bookmark_of_a_page_in_the_notes_folder_leads_there(self):
        vault = self.home / "vault"
        vault.mkdir()
        (vault / "live cards.html").write_text("<p>cards</p>", encoding="utf-8")
        self.app.apply_profile(settings.save({"vault": str(vault), "sources": {"library": {"on": True}}}))
        # Without its seal the address only gives the empty frame, whoever asks.
        path = "/api/library/page?path=live%20cards.html"
        for where in (path, path + "&s=0"):
            status, _, body = self.call("GET", where)
            self.assertEqual((status, body), (200, (server.WEB / "index.html").read_bytes()))
        word, ask = self.let_in(), "/api/library/seal?path=live%20cards.html"
        status, _, body = self.call("GET", ask, X_Leitstand="1", X_Brento_Sign=sign(word, "GET", ask, self.host))
        self.assertEqual(status, 200)
        status, reply, body = self.call("GET", json.loads(body)["url"])
        self.assertEqual((status, body), (200, b"<p>cards</p>"))
        self.assertIn("sandbox", reply.getheader("Content-Security-Policy"))

    def test_an_error_goes_into_the_log_without_its_text(self):
        said = io.StringIO()
        with contextlib.redirect_stdout(said), mock.patch.object(self.app, "setup_view", side_effect=ValueError("https://calendar.example/secret")):
            with self.assertRaises((http.client.HTTPException, OSError)):
                self.call("GET", "/api/setup", X_Leitstand="1", X_Brento_Key=self.app.key)
            time.sleep(0.2)
        self.assertIn("ValueError in ", said.getvalue())
        self.assertNotIn("secret", said.getvalue())

    def test_a_page_of_the_notes_folder_gets_none_of_brentos_rights(self):
        self.assertTrue(server.CSP_PAGE.startswith("sandbox allow-scripts;"))
        self.assertNotIn("allow-same-origin", server.CSP_PAGE)

    def test_a_foreign_host_name_is_refused_and_localhost_leads_to_the_one_address(self):
        self.assertEqual(self.call("GET", "/", Host="evil.example")[0], 403)
        self.assertEqual(self.call("GET", "/api/tools", Host="evil.example", X_Leitstand="1", X_Brento_Key=self.app.key)[0], 403)
        status, reply, _ = self.call("GET", "/?ticket=x", Host="localhost:%d" % self.port)
        self.assertEqual((status, reply.getheader("Location")), (303, "http://%s/?ticket=x" % self.host))

    def test_a_settings_folder_that_was_emptied_does_not_lock_the_owner_out(self):
        self.assertEqual(address.whose(self.port), "mine")
        (self.home / "access-key").unlink()
        # Asked whose it is, the server makes a new key, and the launcher finds it.
        self.assertEqual(address.whose(self.port), "mine")
        self.assertTrue((self.home / "access-key").is_file())

    def test_the_owner_is_recognised_without_saying_the_key(self):
        self.assertEqual(address.whose(self.port), "mine")
        self.assertRegex(address.entrance(self.port), r"^http://127\.0\.0\.1:%d/\?ticket=[\w-]{20,}$" % self.port)
        self.assertEqual(self.call("GET", "/api/whose?n=short")[0], 400)
        said = []
        real = address._ask
        with mock.patch.object(address, "_ask", side_effect=lambda *a: said.append(a) or real(*a)):
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

    def test_a_length_that_cannot_be_meant_is_refused_at_once(self):
        for length in ("-1", "x", "999999999"):
            with socket.create_connection(("127.0.0.1", self.port), timeout=10) as raw:
                raw.sendall(("POST /api/enter HTTP/1.1\r\nHost: %s\r\nX-Leitstand: 1\r\nContent-Length: %s\r\n\r\n{}" % (self.host, length)).encode())
                self.assertIn(raw.recv(60).split(b" ")[1], (b"400", b"413"), length)

    def test_the_phone_door_knows_nothing_of_all_this(self):
        self.assertFalse(server.phone.allowed("GET", "/api/whose"))
        self.assertFalse(server.phone.allowed("POST", "/api/ticket"))
        self.assertFalse(server.phone.allowed("POST", "/api/enter"))
        self.assertTrue(server.phone.allowed("GET", "/sign.js"))


class SignedInTheBrowser(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not on this computer")
    def test_the_page_signs_as_the_server_expects(self):
        word = {"id": "abc123", "word": "0f" * 32, "run": "00ff00ff00ff00ff"}
        for method, path, body in (("GET", "/api/library/note?path=a%20b%27c.md", ""), ("POST", "/api/ask", '{"q":"Grüße, wie läuft es? \U0001f600"}'), ("POST", "/api/refresh", "{}")):
            code = "const s=require(process.argv[1]),w=%s,h=s.header(w,w.run,%s,%s,'127.0.0.1:8770',%s,1795530000000);console.log(h+' '+s.answer(w,h))" % tuple(
                json.dumps(x) for x in (word, method, path, body))
            said = subprocess.run([shutil.which("node"), "-e", code, str(ROOT / "web" / "sign.js")], capture_output=True, timeout=60)
            head = sign(word, method, path, "127.0.0.1:8770", body.encode("utf-8"), now=1795530000)
            self.assertEqual(said.stdout.decode().strip(), head + " " + answer(word, head), said.stderr)


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

    def test_whatever_sits_on_the_port_the_question_comes_back_soon(self):
        def listener(act):
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            sock.listen(8)
            self.addCleanup(sock.close)

            def serve():
                while True:
                    try:
                        conn, _ = sock.accept()
                    except OSError:
                        return
                    try:
                        act(conn)
                    except OSError:
                        pass
            threading.Thread(target=serve, daemon=True).start()
            return sock.getsockname()[1]

        def garbage(conn):
            conn.sendall(b"220 hello, this is no web server\r\n")
            conn.close()

        def silence(conn):
            time.sleep(20)

        def drip(conn):
            conn.sendall(b"HTTP/1.1 404 x\r\nServer: Brento\r\n\r\n")
            for _ in range(200):
                conn.sendall(b"x")
                time.sleep(0.3)
        for act in (garbage, silence, drip):
            began = time.monotonic()
            self.assertEqual(address.whose(listener(act), timeout=1), "", act.__name__)
            self.assertLess(time.monotonic() - began, 8, act.__name__)

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
                # Ben used that address before. A browser may keep a word for it, and Anna's program could read that now.
                address.Browsers(ben, keep=True).add("127.0.0.1:%d" % first)
                running.append(start(ben))
                second = ready(ben)
                self.assertTrue(second)
                self.assertNotEqual(first, second)
                self.assertEqual(address.Browsers(ben, keep=True).words, {})
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
        vault = self.home.resolve() / "My notes"
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
        # Anything else can be saved meanwhile, and the folder stays as it was chosen.
        with mock.patch.object(sources, "gh_status", return_value={"ready": False, "reason": ""}):
            app.save_setup({"profile": {"name": "Ann"}})
            self.assertEqual((app.profile["name"], app.profile["vault"]), ("Ann", str(vault)))
            with self.assertRaises(ValueError):
                app.save_setup({"profile": {"vault": str(self.home / "nowhere")}})
        # Choosing it again under its new name is all it takes.
        app.apply_profile(settings.save(dict(app.profile, vault=str(self.home / "My new notes"))))
        tasks = next(s for s in app.state()["sources"] if s["id"] == "tasks")
        self.assertEqual(tasks["state"], "fresh")


class Ask(unittest.TestCase):
    def test_the_notes_folder_can_neither_start_a_program_nor_open_other_folders(self):
        args = server.ask_command("claude", "sonnet", "Alex")
        self.assertEqual(args[args.index("--setting-sources") + 1], "")
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
                    conn.request("POST", path, json.dumps(body), {"X-Leitstand": "1", address.KEY_HEADER: app.key, "Host": "127.0.0.1"})
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


def index_read(index, today, wait):
    """read_tasks with another patience."""
    with mock.patch.object(sources.TaskIndex.scan, "__defaults__", (None, wait)):
        return sources.read_tasks(index, today)


class Reading(unittest.TestCase):
    def setUp(self):
        # Until a privacy list is loaded everything is hidden.
        sources.load_private(Path(__file__).resolve().parent / "stand-in-terms.txt")

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
        day = calendar_feed.date(2026, 11, 24)
        event = calendar_feed.parse_ics(text, day)[0]
        self.assertTrue(sources.event_matters(event))
        self.assertTrue(slack_notify.event_matters(event))
        # In a calendar that does name guests, an event without any is the owner's own block, link or not.
        named = text + "\nBEGIN:VEVENT\nDTSTART:20261126T100000\nSUMMARY:Team\nATTENDEE;CN=A:mailto:a@example.com\nATTENDEE:mailto:b@example.com\nEND:VEVENT"
        block, team = calendar_feed.parse_ics(named, day)
        self.assertEqual((block["title"], sources.event_matters(block), bool(block["join"])), ("Budget", False, True))
        self.assertTrue(sources.event_matters(team))
        # A webinar or a recording is nobody waiting.
        for link in ("https://zoom.us/w/123", "https://acme.webex.com/recordingservice/sites/acme/x"):
            webinar = calendar_feed.parse_ics(text.replace("https://teams.microsoft.com/l/meetup-join/x", link), day)[0]
            self.assertFalse(sources.event_matters(webinar), link)
        for link in ("https://zoom.us/j/123", "https://acme.webex.com/meet/ann", "https://meet.google.com/abc-defg-hij"):
            self.assertTrue(sources.event_matters(calendar_feed.parse_ics(text.replace("https://teams.microsoft.com/l/meetup-join/x", link), day)[0]), link)

    def test_outlooks_quoted_zone_does_not_lose_the_meeting(self):
        text = 'BEGIN:VEVENT\nDTSTART;TZID="tzone://Microsoft/Utc":20261125T100000\nSUMMARY:Call: part 2\nLOCATION:Room: 4\nEND:VEVENT'
        event = calendar_feed.parse_ics(text, calendar_feed.date(2026, 11, 24))[0]
        self.assertEqual((event["title"], event["where"].split("time in")[-1].endswith("Room: 4")), ("Call: part 2", True))
        if has_zones():
            here = calendar_feed.datetime(2026, 11, 25, 10, tzinfo=calendar_feed.timezone.utc).astimezone()
            self.assertEqual((event["time"], event["zone"]), (here.strftime("%H:%M"), ""))

    def test_a_note_that_lies_only_in_a_cloud_holds_nothing_up(self):
        today = calendar_feed.date(2026, 11, 24)
        with tempfile.TemporaryDirectory() as tmp:
            for name, more in (("here.md", ""), ("away.md", "x" * 500)):
                (Path(tmp) / name).write_text("- [ ] From %s \U0001f4c5 2099-01-02\n%s" % (name, more), encoding="utf-8")
            index = sources.TaskIndex(Path(tmp), ttl=0)
            fetched, go = [], threading.Event()
            real = sources.task_lines

            def lines(full, size):
                if os.path.basename(full) == "away.md":
                    fetched.append("away.md")
                    if not go.wait(20):
                        raise OSError("the cloud does not deliver")
                return real(full, size)
            with mock.patch.object(sources, "elsewhere", side_effect=lambda stat: stat.st_size > 400), \
                    mock.patch.object(sources, "task_lines", side_effect=lines):
                began = time.monotonic()
                data, src = index_read(index, today, 0.5)
                self.assertLess(time.monotonic() - began, 5)
                self.assertEqual(([t["title"] for t in data["items"]], src["state"], src["note"]),
                                 (["From here.md"], "unknown", "1 note is not on this computer yet"))
                go.set()
                index.worker.join(10)
            self.assertEqual(fetched, ["away.md"])
            with mock.patch.object(sources, "elsewhere", return_value=False):
                data, src = sources.read_tasks(index, today)
            self.assertEqual((len(data["items"]), src["state"]), (2, "fresh"))

    def test_the_first_round_may_take_its_time(self):
        today = calendar_feed.date(2026, 11, 24)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.md").write_text("- [ ] Slow \U0001f4c5 2099-01-02\n", encoding="utf-8")
            index = sources.TaskIndex(Path(tmp), ttl=60)
            go, real = threading.Event(), sources.task_lines
            with mock.patch.object(sources, "task_lines", side_effect=lambda *a: go.wait(20) and real(*a)):
                data, src = index_read(index, today, 0.3)
                self.assertEqual((data["items"], src["state"], src["note"]), ([], "unknown", "still loading"))
                go.set()
                data, src = index_read(index, today, 10)
            self.assertEqual((len(data["items"]), src["state"]), (1, "fresh"))

    def test_a_folder_among_the_notes_that_cannot_be_listed_is_said(self):
        today = calendar_feed.date(2026, 11, 24)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Work").mkdir()
            (Path(tmp) / "Work" / "a.md").write_text("- [ ] Send the offer \U0001f4c5 2099-01-02\n", encoding="utf-8")
            index = sources.TaskIndex(Path(tmp), ttl=0)
            self.assertEqual(sources.read_tasks(index, today)[1]["state"], "fresh")
            real = os.scandir

            def scandir(path="."):
                if str(path).endswith("Work"):
                    raise PermissionError(13, "no", str(path))
                return real(path)
            with mock.patch.object(os, "scandir", side_effect=scandir):
                data, src = sources.read_tasks(index, today)
            # What was known of it stays, and it is said that it could not be read.
            self.assertEqual((len(data["items"]), src["state"], src["note"]), (1, "unknown", "1 note could not be read"))
            self.assertEqual(sources.read_tasks(index, today)[1]["state"], "fresh")

    def test_a_note_that_macos_13_put_into_icloud_is_counted(self):
        today = calendar_feed.date(2026, 11, 24)
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "Plan.md"
            note.write_text("- [ ] Send the offer \U0001f4c5 2099-01-02\n", encoding="utf-8")
            index = sources.TaskIndex(Path(tmp), ttl=0)
            self.assertEqual(sources.read_tasks(index, today)[1]["state"], "fresh")
            note.rename(Path(tmp) / ".Plan.md.icloud")
            data, src = sources.read_tasks(index, today)
            self.assertEqual((len(data["items"]), src["state"], src["note"]), (1, "unknown", "1 note is not on this computer yet"))

    def test_a_folder_that_came_back_is_not_called_lost_while_it_is_read(self):
        today = calendar_feed.date(2026, 11, 24)
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            index = sources.TaskIndex(vault, ttl=0)
            self.assertEqual(sources.read_tasks(index, today)[1]["note"], "the notes folder is not there")
            vault.mkdir()
            (vault / "a.md").write_text("- [ ] Slow \U0001f4c5 2099-01-02\n", encoding="utf-8")
            go, real = threading.Event(), sources.task_lines
            with mock.patch.object(sources, "task_lines", side_effect=lambda *a: go.wait(20) and real(*a)):
                self.assertEqual(index_read(index, today, 0.3)[1]["note"], "still loading")
                go.set()
                self.assertEqual(index_read(index, today, 10)[1]["state"], "fresh")

    def test_saving_a_setting_neither_hides_the_tasks_nor_shows_what_is_private_now(self):
        today = calendar_feed.date(2026, 11, 24)
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("Work", "Other"):
                (Path(tmp) / name).mkdir()
                (Path(tmp) / name / "a.md").write_text("- [ ] In %s \U0001f4c5 2099-01-02\n" % name, encoding="utf-8")
            before = sources.TaskIndex(Path(tmp))
            self.assertEqual(len(sources.read_tasks(before, today)[0]["items"]), 2)
            sources.set_skip(["Other"])
            self.addCleanup(sources.set_skip, [])
            index, go = sources.TaskIndex(Path(tmp), before=before), threading.Event()
            real = sources.os.listdir
            with mock.patch.object(sources.os, "listdir", side_effect=lambda p: go.wait(20) and real(p)):
                data, src = index_read(index, today, 0.2)
                self.assertEqual(([t["title"] for t in data["items"]], src["state"]), (["In Work"], "fresh"))
                go.set()
                index.ready.wait(10)
            self.assertEqual([t["title"] for t in sources.read_tasks(index, today)[0]["items"]], ["In Work"])

    @unittest.skipUnless(os.name == "nt", "only Windows cuts paths off")
    def test_a_path_windows_cuts_off_is_read_all_the_same(self):
        today = calendar_feed.date(2026, 11, 24)
        with tempfile.TemporaryDirectory() as tmp:
            deep = sources.whole(tmp)
            for _ in range(6):
                deep = os.path.join(deep, "a folder with a rather long name, as people give them")
                os.mkdir(deep)
            with open(os.path.join(deep, "note.md"), "w", encoding="utf-8") as out:
                out.write("- [ ] Far down \U0001f4c5 2099-01-02\n")
            data, src = sources.read_tasks(sources.TaskIndex(Path(tmp)), today)
            self.assertEqual(([t["title"] for t in data["items"]], src["state"]), (["Far down"], "fresh"))
            self.assertTrue(data["items"][0]["path"].startswith("a folder with a rather long name"))
            shutil.rmtree(sources.whole(tmp), ignore_errors=True)
            os.makedirs(tmp, exist_ok=True)

    def test_slack_learns_until_everything_has_been_read(self):
        when = calendar_feed.datetime
        cfg = {"digest": "", "alerts": True, "remind": 0, "sources": ["tasks"]}

        def state(ids, note):
            return {"sources": [{"id": "tasks", "label": "Obsidian tasks", "state": "unknown" if note else "fresh", "note": note}], "events": [],
                    "alerts": [{"id": i, "title": i, "source": "Obsidian tasks", "eyebrow": "", "why": ""} for i in ids]}
        texts, memory = slack_notify.plan(state(["a"], "9 notes are not on this computer yet"), cfg, {}, when(2026, 11, 24, 10, 0))
        self.assertEqual((texts, memory.get("seeded")), ([], None))
        texts, memory = slack_notify.plan(state(["a", "b"], ""), cfg, memory, when(2026, 11, 24, 10, 5))
        self.assertEqual((texts, memory["seeded"], len(memory["seen"])), ([], True, 2))
        self.assertEqual(len(slack_notify.plan(state(["a", "b", "c"], ""), cfg, memory, when(2026, 11, 24, 10, 6))[0]), 1)
        # A source that is never read does not keep it quiet for ever.
        texts, memory = slack_notify.plan(state(["a"], "gone"), cfg, {}, when(2026, 11, 24, 10, 0))
        self.assertTrue(slack_notify.plan(state(["a"], "gone"), cfg, memory, when(2026, 11, 24, 11, 0))[1]["seeded"])

    def test_dates_no_clock_can_hold_do_not_take_the_calendar_down(self):
        text = ("BEGIN:VEVENT\nDTSTART:19650312T140000Z\nSUMMARY:Long ago\nEND:VEVENT\n"
                "BEGIN:VEVENT\nDTSTART:99991231T235959Z\nSUMMARY:Far away\nEND:VEVENT\n"
                "BEGIN:VEVENT\nDTSTART:20261125T100000\nSUMMARY:Tomorrow\nEND:VEVENT")
        self.assertEqual([e["title"] for e in calendar_feed.parse_ics(text, calendar_feed.date(2026, 11, 24))], ["Tomorrow"])

    def test_half_a_calendar_is_no_calendar(self):
        class Reply(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None
        whole = b"BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        for body, good in ((whole, True), (whole[:-20], False), (b"<html>", False)):
            with mock.patch.object(calendar_feed.urllib.request, "urlopen", return_value=Reply(body)):
                if good:
                    self.assertIn("BEGIN:VCALENDAR", calendar_feed.Feed.read("https://x.example/a.ics"))
                else:
                    with self.assertRaises(ValueError):
                        calendar_feed.Feed.read("https://x.example/a.ics")

    def test_a_link_with_a_space_is_refused_and_never_quoted(self):
        with self.assertRaises(ValueError) as caught:
            calendar_feed.clean_url("https://calendar.google.com/calendar/ical/private-0123 456/basic.ics")
        self.assertNotIn("0123", str(caught.exception))
        with tempfile.TemporaryDirectory() as tmp:
            feed = calendar_feed.Feed(Path(tmp) / "calendar-url")
            with mock.patch.object(feed, "read", side_effect=http.client.InvalidURL("secret-0123")):
                with self.assertRaises(ValueError) as caught:
                    feed.connect("https://calendar.google.com/a.ics")
                self.assertNotIn("0123", str(caught.exception))
                feed.fetch()
            self.assertEqual(feed.error, "the calendar link did not answer")

    def test_a_note_that_could_not_be_opened_is_tried_again_and_said(self):
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "a.md"
            note.write_text("- [ ] Send the offer \U0001f4c5 2099-01-02\n", encoding="utf-8")
            index = sources.TaskIndex(Path(tmp), ttl=0)
            today = calendar_feed.date(2026, 11, 24)
            real = sources.task_lines
            with mock.patch.object(sources, "task_lines", side_effect=OSError("not here yet")):
                data, src = sources.read_tasks(index, today)
            self.assertEqual((data["items"], src["state"], src["note"]), ([], "unknown", "1 note could not be read"))
            data, src = sources.read_tasks(index, today)
            self.assertEqual((len(data["items"]), src["state"]), (1, "fresh"))
            # Known once, then out of reach: what was known stays, and it is said.
            os.utime(str(note), (1, 1))
            with mock.patch.object(sources, "task_lines", side_effect=OSError("gone again")):
                data, src = sources.read_tasks(index, today)
            self.assertEqual((len(data["items"]), src["state"]), (1, "unknown"))
            self.assertIs(sources.task_lines, real)

    def test_a_calendar_that_stopped_answering_is_not_fresh(self):
        today = calendar_feed.date.today()
        with tempfile.TemporaryDirectory() as tmp:
            feed = calendar_feed.Feed(Path(tmp) / "calendar-url", ttl=10 ** 9)
            feed.path.write_text("https://calendar.google.com/x.ics", encoding="utf-8")
            feed.text, feed.fetched, feed.error = "BEGIN:VCALENDAR", time.time() - 600, "the calendar link did not answer"
            self.assertEqual(sources.read_calendar(feed, today)[2]["state"], "fresh")
            feed.fetched = time.time() - 4000
            src = sources.read_calendar(feed, today)[2]
            self.assertEqual(src["state"], "unknown")
            self.assertIn("did not answer, last read", src["note"])
            feed.error = ""
            self.assertEqual(sources.read_calendar(feed, today)[2]["note"], "still loading")

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
