"""Where Brento answers on this computer, and whose Brento answers there.

127.0.0.1 belongs to everyone who is signed in to a computer at the same time. So every Brento has its owner's key, a
file only that person can read, and opens for nobody else. The second person's Brento takes the next free port.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import urllib.error
import urllib.request

import settings

FIRST = 8770
# The phone's door is always one above, so the steps are two wide.
PORTS = range(FIRST, FIRST + 60, 2)
KEY_HEADER = "X-Brento-Key"
NONCE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
# Brento is on this computer, so it is never asked through a proxy.
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def port():
    """The port this person's Brento uses: the usual one, or the one it had to move to."""
    forced = os.environ.get("BRENTO_PORT")
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
        with os.fdopen(os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as out:
            out.write(key)
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
    return hmac.new(secret.encode("utf-8"), ("brento %d %s" % (number, nonce)).encode("utf-8"), hashlib.sha256).hexdigest()


def ask(path, number, secret="", data=None, timeout=2.0):
    """(status, answer, whether a Brento gave it). Status 0 when nothing answers there."""
    headers = {"X-Leitstand": "1"}
    if secret:
        headers[KEY_HEADER] = secret
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(page(number) + path, data=data, headers=headers)
    try:
        with DIRECT.open(request, timeout=timeout) as reply:
            status, raw, named = reply.status, reply.read(), reply.headers.get("Server") or ""
    except urllib.error.HTTPError as exc:
        status, raw, named = exc.code, exc.read(), exc.headers.get("Server") or ""
    except (OSError, ValueError):
        return 0, {}, False
    try:
        answer = json.loads(raw.decode("utf-8"))
    except ValueError:
        answer = {}
    return status, answer if isinstance(answer, dict) else {}, named.startswith("Brento")


def whose(number=0, timeout=2.0):
    """'mine' for this person's Brento, 'other' for someone else's, 'older' for one from before the key, and '' when no
    Brento answers there. The key itself only ever goes to a server that has proved it already knows it."""
    number = number or port()
    nonce = secrets.token_urlsafe(24)
    status, answer, brento = ask("api/whose?n=" + nonce, number, timeout=timeout)
    if not brento:
        return ""
    if status == 200:
        mine = key()
        good = mine and hmac.compare_digest(str(answer.get("proof") or ""), proof(mine, number, nonce))
        return "mine" if good else "other"
    return "older"


def entrance(number=0):
    """The address that opens this person's Brento in a browser: with a ticket that works once, for two minutes.
    Addresses end up in histories and process lists, so the key is never part of one."""
    number = number or port()
    if whose(number) == "mine":
        status, answer, _ = ask("api/ticket", number, key(), data=b"{}", timeout=5.0)
        if status == 200 and answer.get("ticket"):
            return page(number) + "?ticket=" + str(answer["ticket"])
    return page(number)
