"""Where Daytag answers on this computer, and whose Daytag answers there.

127.0.0.1 belongs to everyone who is signed in to a computer at the same time. So every Daytag has its owner's key, a
file only that person can read, and opens for nobody else. The second person's Daytag takes the next free port.
"""
import hashlib
import hmac
import http.client
import json
import os
import re
import secrets
import socket
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import settings

FIRST = 8770
# The phone's door is always one above, so the steps are two wide.
PORTS = range(FIRST, FIRST + 60, 2)
KEY_HEADER = "X-Daytag-Key"
SIGN_HEADER = "X-Daytag-Sign"
ANSWER_HEADER = "X-Daytag-Answer"
RUN_HEADER = "X-Daytag-Run"
# A signature counts for one run of the server only. The time is a last fence, wide enough that a clock which was put
# right locks nobody out.
SIGN_SECONDS = 24 * 3600
MAX_BROWSERS = 40
MAX_ANSWER = 256 * 1024
NONCE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
# Daytag is on this computer, so it is never asked through a proxy.
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def port():
    """The port this person's Daytag uses: the usual one, or the one it had to move to."""
    forced = os.environ.get("DAYTAG_PORT")
    if forced:
        return int(forced)
    try:
        kept = int((settings.home() / "port").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return FIRST
    return kept if kept in PORTS else FIRST


def keep(number):
    (settings.home() / "port").write_text(str(number), encoding="utf-8")


def candidates(given=0):
    """The ports a starting server tries, in order. One named by hand is the only one."""
    if given:
        return [given]
    first = port()
    return [first] + [p for p in PORTS if p != first]


def page(number=0):
    return "http://127.0.0.1:%d/" % (number or port())


def load_key(folder):
    """The owner's key. Made on the first start, readable for the owner only."""
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = folder / "access-key"
    try:
        key = path.read_text(encoding="utf-8").strip()
    except OSError:
        key = ""
    if not key:
        key = secrets.token_urlsafe(24)
        private_file(path, key)
    try:
        path.chmod(0o600)
        folder.chmod(0o700)
    except OSError:
        pass
    return key


def key():
    try:
        return (settings.home() / "access-key").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def proof(secret, number, nonce):
    """Shows that a server knows the key without saying it. The port is part of it, so a program on another port
    cannot pass the question on to the real one and repeat its answer."""
    return hmac.new(secret.encode("utf-8"), ("daytag %d %s" % (number, nonce)).encode("utf-8"), hashlib.sha256).hexdigest()


def private_file(path, text):
    """Written so that only the owner can read it, from the first byte on."""
    with os.fdopen(os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as out:
        out.write(text)


def shared():
    """Whether other people have an account on this computer as well. When that cannot be told, yes."""
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList") as listed:
                names = [winreg.EnumKey(listed, n) for n in range(winreg.QueryInfoKey(listed)[0])]
            return sum(1 for name in names if re.match(r"^S-1-(?:5-21|12-1)-[\d-]+$", name)) != 1
        import pwd
        first = 500 if sys.platform == "darwin" else 1000
        with os.scandir("/Users" if sys.platform == "darwin" else "/home") as homes:
            people = {uid for uid in (home.stat(follow_symlinks=False).st_uid for home in homes) if uid >= first}
        # Accounts that can sign in, also those whose home folder lies elsewhere. The last numbers belong to "nobody".
        people |= {p.pw_uid for p in pwd.getpwall() if first <= p.pw_uid < 60000 and not p.pw_shell.endswith(("nologin", "false"))}
        return people != {os.getuid()}
    except (ImportError, OSError):
        return True


def mac(word, text):
    return hmac.new(word.encode("utf-8"), text.encode("utf-8"), hashlib.sha256).hexdigest()


class Browsers:
    """The browsers that were let in. Each got a word of its own, once, for a ticket, and signs its requests with it
    (web/sign.js). The word is never sent again, and no cookie is used, because a browser hands a cookie to every program
    on 127.0.0.1, whatever its port. A word counts only at the address it was given for, a signature only for one run of
    the server, and the answer is signed too.

    Where other people have an account as well, a word ends with the run that gave it. While Daytag is not running, a
    program of theirs can take its address, and a page at the same address can read what the browser keeps for it. What all
    this cannot stop is said in docs/BLUEPRINT.md."""

    def __init__(self, folder, keep=None):
        self.path, self.lock = Path(folder) / "browsers.json", threading.Lock()
        self.keep, self.run, self.words = (not shared()) if keep is None else keep, secrets.token_hex(8), {}
        try:
            if self.keep:
                listed = json.loads(self.path.read_text(encoding="utf-8"))["browsers"]
                self.words = {str(b["id"]): (str(b["word"]), str(b["host"])) for b in listed}
            else:
                self.path.unlink()
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def write(self, words):
        self.words = words
        if self.keep:
            private_file(self.path, json.dumps({"browsers": [{"id": i, "word": w, "host": h} for i, (w, h) in words.items()]}, indent=1))

    def hold(self, keep):
        """Whether the words outlast a restart. The owner can decide that in the settings."""
        with self.lock:
            if keep == self.keep:
                return
            self.keep = keep
            if keep:
                self.write(self.words)
                return
            try:
                self.path.unlink()
            except OSError:
                pass

    def add(self, host, old=""):
        """A word for one browser. The one it had before is worth nothing from then on."""
        with self.lock:
            words = {i: w for i, w in self.words.items() if i != old}
            name, word = secrets.token_hex(6), secrets.token_hex(32)
            words[name] = (word, host)
            while len(words) > MAX_BROWSERS:
                words.pop(next(iter(words)))
            self.write(words)
            return {"id": name, "word": word, "run": self.run}

    def forget(self):
        with self.lock:
            if self.words:
                self.write({})

    def signed(self, header, method, path, host, now=None):
        """The hash of the body a request was signed with ('-' for none) and the signature of the answer, or None when the
        request's own signature does not hold. The address is part of it, so what another port overhears is of no use
        here, and so is the run, so what was overheard before a restart is not either."""
        parts = (header or "").split(".")
        if len(parts) != 5:
            return None
        name, stamp, body, run, given = parts
        word, at = self.words.get(name, ("", ""))
        if not word or at != host or run != self.run or not re.match(r"^\d{10,15}$", stamp):
            return None
        if abs((time.time() if now is None else now) * 1000 - int(stamp)) > SIGN_SECONDS * 1000:
            return None
        right = mac(word, "\n".join((method, path, host, stamp, body, run)))
        if not hmac.compare_digest(given.encode("utf-8"), right.encode("utf-8")):
            return None
        return body, mac(word, "answer\n" + right)


def peer_uid(client, here):
    """Whose program sits at the other end of a connection on this computer. Linux says it, elsewhere it is None."""
    if not sys.platform.startswith("linux"):
        return None

    def column(end, front):
        return "%s%08X:%04X" % (front, struct.unpack("=I", socket.inet_aton(end[0]))[0], end[1])
    # A program may come with an IPv6 socket to the same address. It then stands in the second list.
    mapped = "0" * 16 + "%08X" % struct.unpack("=I", b"\0\0\xff\xff")[0]
    for name, front in (("/proc/net/tcp", ""), ("/proc/net/tcp6", mapped)):
        try:
            ends = column(client, front), column(here, front)
            with open(name, encoding="ascii") as table:
                for line in table:
                    row = line.split()
                    if len(row) > 7 and (row[1], row[2]) == ends:
                        return int(row[7])
        except (OSError, ValueError):
            pass
    return None


def ask(path, number, secret="", data=None, timeout=2.0):
    """(status, answer, whether a Daytag gave it). Status 0 when nothing answers there. Whatever sits on the port, this
    comes back soon and without an error."""
    got = []
    worker = threading.Thread(target=lambda: got.append(_ask(path, number, secret, data, timeout)), daemon=True)
    worker.start()
    worker.join(timeout + 2)
    return got[0] if got else (0, {}, False)


def _ask(path, number, secret, data, timeout):
    headers = {"X-Daytag": "1"}
    if secret:
        headers[KEY_HEADER] = secret
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(page(number) + path, data=data, headers=headers)
    try:
        try:
            with DIRECT.open(request, timeout=timeout) as reply:
                status, raw, named = reply.status, reply.read(MAX_ANSWER), reply.headers.get("Server") or ""
        except urllib.error.HTTPError as exc:
            status, raw, named = exc.code, exc.read(MAX_ANSWER), exc.headers.get("Server") or ""
    except (OSError, ValueError, http.client.HTTPException):
        return 0, {}, False
    try:
        answer = json.loads(raw.decode("utf-8"))
    except ValueError:
        answer = {}
    return status, answer if isinstance(answer, dict) else {}, named.startswith("Daytag")


def whose(number=0, timeout=2.0):
    """'mine' for this person's Daytag, 'other' for someone else's, 'older' for one from before the key, and '' when no
    Daytag answers there. The key itself only ever goes to a server that has proved it already knows it."""
    number = number or port()
    nonce = secrets.token_urlsafe(24)
    status, answer, daytag = ask("api/whose?n=" + nonce, number, timeout=timeout)
    if not daytag:
        return ""
    if status == 200:
        mine = key()
        given = str(answer.get("proof") or "").encode("utf-8", "replace")
        good = mine and hmac.compare_digest(given, proof(mine, number, nonce).encode("ascii"))
        return "mine" if good else "other"
    return "older"


def entrance(number=0):
    """The address that opens this person's Daytag in a browser: with a ticket that works once, for two minutes.
    Addresses end up in histories and process lists, so the key is never part of one."""
    number = number or port()
    if whose(number) == "mine":
        status, answer, _ = ask("api/ticket", number, key(), data=b"{}", timeout=5.0)
        if status == 200 and answer.get("ticket"):
            return page(number) + "?ticket=" + str(answer["ticket"])
    return page(number)
