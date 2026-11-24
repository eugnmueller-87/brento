"""Brento on a phone: the computer opens a second door on the home network, and only paired phones get in.

Nothing runs on the phone. It shows this computer's Brento, so an iPhone or an Android phone needs no app store, only
an icon on its home screen. A phone pairs once with a six-digit code that the computer shows for ten minutes, and
then keeps a long random token in a cookie. Only a hash of each token is saved. A paired phone reads Home, the
board, the calendar and the notes, may ask the Ask box and remove a card from Home. It can never change the setup,
start a program on the computer, or pair another phone.
"""
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

FILE = "phone.json"
COOKIE = "brento_phone"
CODE_TTL = 600
CODE_TRIES = 5
MAX_DEVICES = 20
TOKEN = re.compile(r"^[0-9a-f]{64}$")
TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
INET = re.compile(r"\binet (?:addr:)?(\d+\.\d+\.\d+\.\d+)")
# Before pairing, a phone gets the pairing page and the icons for its home screen, nothing else.
OPEN_PATHS = {"/icon.svg", "/apple-touch-icon.png", "/icon-512.png", "/manifest.webmanifest"}
# After pairing: the page and what it reads. Anything else stays on the computer.
READ_PATHS = {"/", "/app.js", "/art.js", "/sign.js", "/style.css", "/manifest.webmanifest", "/icon.svg", "/apple-touch-icon.png",
              "/icon-512.png", "/api/state", "/api/tools", "/api/ask/status"}
WRITE_PATHS = {"/api/ask", "/api/refresh", "/api/tools"}


def allowed(method, path):
    """What a paired phone may reach. /api/tools is limited again by its handler to removing a card from Home."""
    if method == "POST":
        return path in WRITE_PATHS
    return path in READ_PATHS or path.startswith("/photos/") or path.startswith("/api/library")


def digest(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def kind(ip):
    """'home' for an address on the home network, 'tailscale' for one that also works away from home, '' for others."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ""
    if addr.version != 4 or addr.is_loopback or addr.is_link_local or addr.is_unspecified:
        return ""
    if addr in TAILSCALE:
        return "tailscale"
    return "home" if addr.is_private else ""


def own_addresses():
    """This computer's addresses on all its adapters. Windows gives them for its own name at once. Elsewhere looking
    the name up goes out to the network: it can take half a minute, and on a Mac it raises the question whether Brento
    may find devices on the local network. So there the system's own list is read."""
    if sys.platform == "win32":
        try:
            return [info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
        except OSError:
            return []
    for args in (["/sbin/ifconfig"], ["ip", "-4", "-o", "addr"], ["hostname", "-I"]):
        try:
            text = subprocess.run(args, capture_output=True, timeout=5, stdin=subprocess.DEVNULL).stdout.decode("utf-8", "replace")
        except (OSError, subprocess.SubprocessError):
            continue
        if args[0] == "hostname":
            return text.split()
        if INET.search(text):
            return INET.findall(text)
    return []


def lan_addresses():
    """The addresses a phone can type. The one this computer uses to reach the internet comes first; virtual
    adapters (WSL, Hyper-V, Docker) also carry private addresses, so they are left out when that one is known."""
    primary = ""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Nothing is sent: connecting a UDP socket only picks the outgoing interface.
            probe.connect(("192.0.2.1", 9))
            primary = probe.getsockname()[0]
        finally:
            probe.close()
    except OSError:
        primary = ""
    found = []
    for ip in [primary] + own_addresses():
        k = kind(ip)
        if not k or any(f["ip"] == ip for f in found):
            continue
        if k == "home" and primary and kind(primary) == "home" and ip != primary:
            continue
        found.append({"ip": ip, "kind": k})
    return sorted(found, key=lambda f: f["kind"] != "home")


def host_ok(host, names):
    """A phone types an address, so the Host header is an IP. A name is fine only if it is allowed by hand
    (for example a Tailscale name), which keeps DNS rebinding out."""
    host = (host or "").strip().lower()
    if host.startswith("["):
        host = host[1:].split("]", 1)[0]
    else:
        host = host.rsplit(":", 1)[0]
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return host in names


class Phones:
    def __init__(self, folder):
        self.path = Path(folder) / FILE
        self.lock = threading.Lock()
        self.code, self.until, self.tries = "", 0.0, 0
        data = self._read()
        self.on = bool(data.get("on"))
        self.devices = [d for d in data.get("devices") or [] if isinstance(d, dict) and TOKEN.match(str(d.get("hash") or ""))]

    def _read(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"on": self.on, "devices": self.devices}, indent=2), encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(self.path)

    def switch(self, on):
        with self.lock:
            self.on = bool(on)
            if not self.on:
                self.code = ""
            self._write()

    def new_code(self, now=None):
        with self.lock:
            now = time.time() if now is None else now
            self.code = "%06d" % secrets.randbelow(1000000)
            self.until, self.tries = now + CODE_TTL, 0
            return self.code

    def pair(self, given, now=None):
        """A new token for the right code, None for a wrong one. Five wrong tries end the code, so it cannot be
        guessed; the right code works for every phone that types it while it is shown."""
        with self.lock:
            now = time.time() if now is None else now
            if not self.on or not self.code or now > self.until:
                return None
            typed = re.sub(r"\D", "", str(given or ""))[:6]
            if not hmac.compare_digest(typed.encode("ascii"), self.code.encode("ascii")):
                self.tries += 1
                if self.tries >= CODE_TRIES:
                    self.code = ""
                return None
            token = secrets.token_urlsafe(32)
            self.devices.append({"hash": digest(token), "added": time.strftime("%Y-%m-%d %H:%M", time.localtime(now))})
            self.devices = self.devices[-MAX_DEVICES:]
            self._write()
            return token

    def known(self, token):
        if not token or not self.on:
            return False
        mine = digest(token)
        return any(hmac.compare_digest(mine, d["hash"]) for d in self.devices)

    def forget_all(self):
        with self.lock:
            self.devices = []
            self._write()

    def view(self, port, error="", now=None):
        now = time.time() if now is None else now
        live = bool(self.code) and now <= self.until
        return {"on": self.on, "port": port, "addresses": lan_addresses() if self.on else [], "error": error,
                "code": self.code if live else "", "codeLeft": int(self.until - now) if live else 0,
                "phones": len(self.devices)}


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b0e15">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Brento">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="manifest" href="/manifest.webmanifest">
<title>Brento</title>
<style>
:root { color-scheme: dark; --bg: #0b0e15; --fg: #e8ecf4; --dim: #9aa3b5; --line: #232a38; --accent: #6cf5bf; --warn: #ffb86b; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--fg); font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  display: grid; place-items: center; padding: max(24px, env(safe-area-inset-top)) max(20px, env(safe-area-inset-right)) max(24px, env(safe-area-inset-bottom)) max(20px, env(safe-area-inset-left)); }
main { width: 100%; max-width: 380px; display: grid; gap: 18px; }
.mark { width: 44px; height: 44px; border-radius: 12px; background: var(--accent); transform: rotate(45deg) scale(.72); }
h1 { margin: 0; font-size: 26px; letter-spacing: -.01em; }
p { margin: 0; color: var(--dim); }
form { display: grid; gap: 12px; }
input { width: 100%; padding: 14px 16px; font: 600 28px/1 ui-monospace, "SF Mono", Menlo, monospace; letter-spacing: .3em; text-align: center;
  color: var(--fg); background: #12161f; border: 1px solid var(--line); border-radius: 14px; }
input:focus { outline: 2px solid var(--accent); outline-offset: 2px; }
button { padding: 14px; font-family: inherit; font-size: 17px; font-weight: 600; color: #06231a; background: var(--accent); border: 0; border-radius: 14px; }
.err { color: var(--warn); }
ol { margin: 0; padding-left: 20px; color: var(--dim); display: grid; gap: 6px; font-size: 15px; }
b { color: var(--fg); }
</style>
</head>
<body>
<main>
<div class="mark" aria-hidden="true"></div>
<h1>Connect this phone</h1>
<p>Type the code your computer shows in Brento under <b>Settings, Phone</b>.</p>
<!--error-->
<form method="post" action="/pair">
<input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="7" pattern="[0-9 ]*" placeholder="000000" aria-label="Six-digit code" autofocus required>
<button type="submit">Connect</button>
</form>
<ol>
<li>iPhone: tap <b>Share</b>, then <b>Add to Home Screen</b>, and open Brento from its new icon. Then type the code there.</li>
<li>Android: open the menu, then <b>Add to Home screen</b>.</li>
</ol>
</main>
</body>
</html>
"""
WRONG = "That code is not right, or it has run out. On your computer: Brento, Settings, Phone, New code."


def page(error=""):
    note = '<p class="err" role="alert">%s</p>' % error if error else ""
    return PAGE.replace("<!--error-->", note).encode("utf-8")
