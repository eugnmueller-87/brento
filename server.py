#!/usr/bin/env python3
"""Brento: a local, read-only face on the vault. Standard library only, no build step.

Only the unmodified `claude` program talks to a model, under the owner's own login. API
credentials are stripped from its environment and the call is refused unless the login
is a claude.ai subscription, so this server has no way to cause a per-token bill.
"""
import argparse
import hmac
import json
import os
import re
import secrets
import shutil
import socketserver
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import sys

import address
import calendar_feed
import library
import phone
import settings
import slack_notify
import sources
import tools
import wizard

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/art.js": ("art.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
          "/icon.svg": ("icon.svg", "image/svg+xml"),
          "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
          "/icon-512.png": ("icon-512.png", "image/png")}
# Browsers that can open a tool as an app window, without an address strip. Chrome first: it holds the sign-ins.
APP_BROWSERS = ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe")


def app_browser():
    roots = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    for rel in APP_BROWSERS:
        for root in filter(None, roots):
            path = Path(root) / rel
            if path.is_file():
                return path
    return None


# Card photos: one folder, and only names of this exact shape, so no request can reach another file.
PHOTO = re.compile(r"^/photos/((?:critical|high|medium|low|calm)-\d{2}\.webp|credits\.json)$")
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: https://www.google.com https://*.gstatic.com; "
       "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
# A generated page from the vault brings its own inline script and style, and may reach nothing else.
# The sandbox takes Brento's own rights away from it: it cannot reach another Brento window either.
CSP_PAGE = ("sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
BILLING_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_OAUTH_TOKEN",
               "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
ASK_TOOLS = "Read,Grep,Glob"
# No settings of the notes folder count and no hooks run, so a folder that other people also write to cannot start a
# program. What is not allowed is refused instead of asked for, and reading ends at the notes folder.
ASK_LOCK = ["--setting-sources", "user", "--settings", str(HERE / "ask-settings.json"), "--permission-mode", "dontAsk"]
ASK_SYSTEM = ("You are the ask box of Brento, %s local dashboard over this vault. You can only read. "
              "Answer from the vault and name the note path behind each claim. If the vault does not say, reply "
              "'I don't know yet'. Lead with the one thing that matters, then at most five short bullets. Reply in "
              "the language of the question. No em dashes.")
CATALOG = HERE / "tools.catalog.json"
ASK_TIMEOUT = 240
MAX_BODY = 64 * 1024
# Board, calendar and library reread themselves within minutes. The remote brief has no timer of its own.
REMOTE_EVERY = 6 * 3600
TICKET_SECONDS = 120
# Pictures and pages of the vault are loaded by address. Every other question to the server carries a header that a
# link, a redirect or a foreign page cannot send.
PLAIN_GETS = {"/api/library/asset", "/api/library/page", "/api/whose"}
LOCKED = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0b0e15">
<title>Brento</title>
<style>
:root { color-scheme: dark; }
body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #0b0e15; color: #f1f3f8;
  font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width: 430px; padding: 24px; display: grid; gap: 16px; }
.mark { width: 44px; height: 44px; border-radius: 12px; background: #6cf5bf; transform: rotate(45deg) scale(.72); }
h1 { margin: 0; font-size: 25px; letter-spacing: -.01em; }
p { margin: 0; color: #a3a9bd; }
b { color: #f1f3f8; }
a { justify-self: start; padding: 11px 18px; border-radius: 12px; background: #6cf5bf; color: #06231a; font-weight: 600; text-decoration: none; }
</style>
</head>
<body>
<main>
<div class="mark" aria-hidden="true"></div>
<h1>Open Brento with its icon</h1>
<p>Brento opens only for the person it belongs to, and this browser has not been let in yet.</p>
<p>On Windows press the <b>Windows key</b>, on a Mac <b>Cmd</b> and <b>Space</b>. Type <b>Brento</b> and press <b>Enter</b>.
After that, this address works here too.</p>
<a href="/">Try again</a>
</main>
</body>
</html>
""".encode("utf-8")


class App:
    def __init__(self, vault, host, allow_hosts, model):
        self.vault_arg, self.model = vault, model
        self.home = settings.home()
        self.tools = tools.ToolStore(self.home / "tools.json", HERE / "tools.default.json", CATALOG)
        self.calendar = calendar_feed.Feed(self.home / "calendar-url")
        self.slack = slack_notify.Slack(self.home)
        # The phone door: a second listener on the home network, only for paired phones. Off until switched on.
        self.phones = phone.Phones(self.home)
        self.port, self.phone_server, self.phone_error = 8770, None, ""
        self.phone_lock = threading.Lock()
        self.state_cache, self.state_at = None, 0.0
        self.remote_at = 0.0
        self.auth_cache, self.auth_at = None, 0.0
        self.lock = threading.Lock()
        self.ask_lock = threading.Lock()
        self.hosts = LOOPBACK | {host.lower()} | {h.lower() for h in allow_hosts}
        # 127.0.0.1 belongs to everyone who is signed in to this computer, so the owner's key is asked for here too.
        self.key, self.tickets = address.load_key(self.home), {}
        # A team's copy of this repo can carry team.json: the shared board, apps and Slack settings.
        self.team = settings.load_team(HERE)
        saved = settings.load()
        # No settings yet: a start with --vault keeps working as it always did, a start without one opens the setup.
        self.needs_setup = saved is None and vault is None
        self.apply_profile(saved or (settings.legacy(vault) if vault else settings.blank()), first=True)

    def apply_profile(self, profile, first=False):
        """Reads the settings into the running server, so a saved setup shows without a restart."""
        vault = Path(profile["vault"]) if profile.get("vault") else (self.vault_arg or self.home / "notes")
        if not profile.get("vault"):
            # Only Brento's own empty folder is made. A chosen folder that is gone must not come back as an empty one.
            vault.mkdir(parents=True, exist_ok=True)
        words = sources.load_private(self.home / "private-terms.txt", required=profile["privacy"] == "required")
        sources.set_owner(profile.get("name", ""))
        sources.set_skip(profile.get("skip"))
        sources.set_login(profile["board"].get("me", ""))
        b = profile["board"]
        board = None
        if settings.on(profile, "board") and b["owner"] and b["number"]:
            board = sources.Board(b["owner"], b["number"], owner_type=b["ownerType"],
                                  fields={k: b[k] for k in sources.FIELDS}, aging=b.get("aging"))
        custom = self.home / "projects.json"
        try:
            registry = json.loads((custom if custom.is_file() else HERE / "projects.default.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            registry = []
        if board:
            board.watch = {p["health"] for p in registry if p.get("health")}
        lib = library.Library(vault)
        with self.lock:
            self.profile, self.vault, self.board, self.registry, self.library = profile, vault, board, registry, lib
            self.tasks = sources.TaskIndex(vault)
            self.privacy_words = words
            self.state_cache, self.state_at = None, 0.0
        if settings.on(profile, "library"):
            threading.Thread(target=lib.refresh, daemon=True).start()

    def state(self):
        with self.lock:
            if settings.on(self.profile, "brief") and time.time() - self.remote_at > REMOTE_EVERY:
                self.remote_at = time.time()
                threading.Thread(target=self.fetch_remote, daemon=True).start()
            if self.state_cache is None or time.time() - self.state_at > 20:
                removed = set(self.tools.load().get("removedCards", []))
                self.state_cache = sources.build_state(self.vault, self.board, registry=self.registry, calendar=self.calendar,
                                                       removed=removed, profile=self.profile, tasks=self.tasks)
                self.state_cache["setupNeeded"] = self.needs_setup
                self.state_cache["githubOwner"] = self.profile["board"]["owner"]
                self.state_at = time.time()
            return self.state_cache

    def fetch_remote(self):
        """A brief pushed from elsewhere shows without anyone pressing refresh."""
        if sources.fetch_remote(self.vault):
            self.state_at = 0.0

    def refresh(self):
        """The refresh button: ask GitHub and the calendar now, not at the next timer. Returns what could not be read."""
        problems = []
        self.remote_at = time.time()
        if settings.on(self.profile, "brief") and not sources.fetch_remote(self.vault):
            problems.append("The remote copy of the morning brief could not be checked.")
        if self.board:
            error = self.board.refresh()
            if error:
                problems.append("Board: %s." % error)
        if settings.on(self.profile, "calendar"):
            error = self.calendar.refresh()
            if error:
                problems.append("Calendar: %s." % error)
        if settings.on(self.profile, "library"):
            threading.Thread(target=self.library.refresh, daemon=True).start()
        self.state_at = 0.0
        return problems

    def catalog(self):
        try:
            entries = json.loads(CATALOG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            entries = []
        have = {t.get("url") for t in self.tools.load().get("tools", [])}
        vault_name = Path(self.vault).name
        out = []
        for entry in entries:
            if "{vault}" in entry["url"] and not self.profile.get("vault"):
                # No vault chosen, so there is no Obsidian vault for the link to open.
                continue
            url = entry["url"].replace("{vault}", quote(vault_name)) if "{vault}" in entry["url"] else entry["url"]
            out.append(dict(entry, url=url, added=url in have))
        return out

    def setup_view(self):
        """Everything the setup page shows. Checks run here, so the page can say what is missing and how to fix it."""
        return {"needed": self.needs_setup, "profile": settings.public(self.profile), "sources": settings.SOURCES,
                "vaults": settings.obsidian_vaults(), "home": str(self.home), "gh": sources.gh_status(),
                "platform": sys.platform, "vaultMissing": bool(self.profile.get("vault")) and not os.path.isdir(self.profile["vault"]),
                "claude": self.auth() if settings.on(self.profile, "ask") else None,
                "calendarConnected": self.calendar.connected(), "privacyWords": self.privacy_words,
                "catalog": self.catalog(), "slackConnected": self.slack.connected(), "slackError": self.slack.error,
                "slackCreate": slack_notify.CREATE_URL}

    def save_setup(self, body):
        """Saves the settings and adds the chosen tools. Tools only ever get added here, never removed:
        the dock's own menu removes one, so nothing set up by hand disappears with a setup save."""
        given = body.get("profile") if isinstance(body.get("profile"), dict) else {}
        merged = dict(self.profile, **{k: v for k, v in given.items() if k in ("name", "vault", "sources", "tasks", "slack")})
        # The board's form fields replace their own values only. A setting the form does not show, such as
        # the aging job, stays as it was.
        if isinstance(given.get("board"), dict):
            merged["board"] = dict(self.profile["board"], **given["board"])
        profile = settings.save(merged)
        added = []
        wanted = {str(t) for t in body.get("tools") or []}
        board = profile["board"]
        extra = []
        if settings.on(profile, "board") and board["owner"] and board["number"]:
            extra.append({"id": "board", "name": "Board", "group": "Daily",
                          "url": "https://github.com/%s/%s/projects/%d" % ("orgs" if board["ownerType"] == "org" else "users",
                                                                             board["owner"], board["number"])})
        self.apply_profile(profile)
        for entry in [c for c in self.catalog() if c["id"] in wanted] + extra:
            try:
                self.tools.apply({"action": "add", "name": entry["name"], "url": entry["url"],
                                  "group": entry.get("group", "Daily"), "pinned": True})
                added.append(entry["name"])
            except tools.ToolError:
                pass
        self.needs_setup = False
        return dict(self.setup_view(), added=added)

    def wizard_view(self):
        """The first-start wizard's starting point: every guess and check it can make before the owner clicks."""
        gh = sources.gh_status()
        found, error = wizard.projects() if gh["ready"] else ([], "")
        vaults = settings.obsidian_vaults()
        return dict(self.setup_view(), name=self.profile.get("name") or wizard.guess_name(gh["ready"]), gh=gh,
                    projects=found, projectsError=error, claude=self.auth(even_off=True), vaults=vaults,
                    team=self.team, orgs=wizard.orgs() if gh["ready"] else [],
                    slackConnected=self.slack.connected(), slackCreate=slack_notify.CREATE_URL,
                    platform=sys.platform, signin=wizard.SIGNIN.view(),
                    canInstall=sys.platform in ("darwin", "linux", "win32"))

    def phone_listen(self):
        """Opens or closes the phone door to match the setting. The computer's own page stays on loopback."""
        with self.phone_lock:
            if self.phones.on and not self.phone_server:
                try:
                    srv = PhoneServer(("0.0.0.0", self.port + 1), PhoneHandler)
                except OSError:
                    self.phone_error = "Port %d is taken by another program, so phones cannot connect." % (self.port + 1)
                    return
                self.phone_error, self.phone_server = "", srv
                threading.Thread(target=srv.serve_forever, daemon=True).start()
            elif not self.phones.on and self.phone_server:
                srv, self.phone_server = self.phone_server, None

                def close():
                    srv.shutdown()
                    srv.server_close()
                threading.Thread(target=close, daemon=True).start()

    def phone_view(self):
        return self.phones.view(self.port + 1, self.phone_error)

    def phone_action(self, action):
        if action == "on":
            self.phones.switch(True)
            self.phone_listen()
            if not self.phone_error:
                self.phones.new_code()
        elif action == "off":
            self.phones.switch(False)
            self.phone_listen()
        elif action == "code":
            if not self.phones.on:
                raise ValueError("Switch the phone on first.")
            self.phones.new_code()
        elif action == "forget":
            self.phones.forget_all()
        else:
            raise ValueError("Unknown action.")
        return self.phone_view()

    def wizard_board(self, body):
        """Create a board, or read one the owner picked, and map its fields. Nothing is saved until Finish."""
        action = body.get("action")
        if action == "create":
            return wizard.create_board(body.get("title") or "Brento", str(body.get("org") or ""))
        owner, kind = str(body.get("owner") or "").strip(), "org" if body.get("ownerType") == "org" else "user"
        try:
            number = int(body.get("number") or 0)
        except (TypeError, ValueError):
            number = 0
        if not settings.GH_LOGIN.match(owner) or number <= 0:
            raise ValueError("Pick a board from the list.")
        if action == "lanes":
            # The owner asked for Brento's lane field on their own board. Only adds a field.
            wizard.add_fields(owner, number, lanes=True, area=False, due=False)
        probe = sources.probe_board(owner, number, kind)
        if probe.get("error"):
            raise ValueError(probe["error"])
        return dict(wizard.auto_fields(probe), owner=owner, ownerType=kind, number=number, title=probe.get("title"),
                    url=probe.get("url"))

    def notify_loop(self):
        """Slack, about every half minute. A failure is kept for the setup page and never stops the server."""
        while True:
            time.sleep(30)
            try:
                # Before the setup is finished nothing has been read, and a message would say that all is calm.
                if self.slack.connected() and not self.needs_setup:
                    self.slack.tick(self.state(), self.profile.get("slack") or settings.clean_slack(None),
                                    self.profile.get("name", ""))
            except Exception as exc:  # the loop must outlive any one bad tick
                self.slack.error = "Slack: %s" % type(exc).__name__

    def ticket(self):
        """A word that lets one browser in, once and soon. It goes into an address, so the key never has to."""
        with self.lock:
            now = time.monotonic()
            self.tickets = {word: ends for word, ends in self.tickets.items() if ends > now}
            word = secrets.token_urlsafe(24)
            self.tickets[word] = now + TICKET_SECONDS
            return word

    def redeem(self, word):
        with self.lock:
            return self.tickets.pop(word, 0.0) > time.monotonic()

    def open_tool(self, body):
        """A tool from the dock list as a Chrome app window: no address strip, signed in with what Chrome keeps.

        Only addresses already on the list open, so no page can make this server start anything else."""
        tid = str(body.get("id") or "")
        tool = next((t for t in self.tools.load().get("tools", []) if t.get("id") == tid), None)
        if not tool or not re.match(r"^https?://", tool.get("url", ""), re.I):
            raise ValueError("Unknown tool.")
        exe = app_browser()
        if not exe:
            raise ValueError("Neither Chrome nor Edge is installed.")

        def num(key, low, high):
            try:
                return max(low, min(high, int(body.get(key))))
            except (TypeError, ValueError):
                return None
        args = [str(exe), "--app=" + tool["url"]]
        x, y, w, h = num("x", -20000, 20000), num("y", -20000, 20000), num("w", 300, 8000), num("h", 300, 8000)
        if x is not None and y is not None:
            args.append("--window-position=%d,%d" % (x, y))
        if w is not None and h is not None:
            args.append("--window-size=%d,%d" % (w, h))
        startup = None
        if os.name == "nt":
            # This server runs without a window. Told nothing, a browser started by it would open hidden too.
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 1
        subprocess.Popen(args, startupinfo=startup, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    def auth(self, even_off=False, fresh=False):
        """Ask the program itself which login it would use. Anything but a subscription blocks Ask.
        The wizard asks even while the box is off, to know whether it can switch it on."""
        if not even_off and not settings.on(self.profile, "ask"):
            return {"ready": False, "plan": None, "model": self.model, "reason": "The Ask box is switched off in the setup."}
        with self.lock:
            if not fresh and self.auth_cache and time.time() - self.auth_at < 60:
                return self.auth_cache
        claude = settings.find_exe("claude")
        result = {"ready": False, "plan": None, "model": self.model, "reason": "Claude Code is not installed here."}
        if claude:
            try:
                run = subprocess.run([claude, "auth", "status"], capture_output=True, timeout=20, env=locked_env(),
                                     encoding="utf-8", errors="replace", creationflags=sources.NO_WINDOW)
                info = json.loads(run.stdout)
                if info.get("loggedIn") and info.get("authMethod") == "claude.ai":
                    result.update(ready=True, plan=info.get("subscriptionType"), reason="")
                else:
                    result["reason"] = "Not signed in with a Claude plan on this computer yet."
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                result["reason"] = "Could not read the login state: %s" % exc
        with self.lock:
            self.auth_cache, self.auth_at = result, time.time()
        return result


def time_today():
    from datetime import date
    return date.today()


def ask_command(exe, model, name):
    """The Ask box's one command. The question itself goes over stdin, never into an argument."""
    return [exe, "-p", "--model", model, "--tools", ASK_TOOLS] + ASK_LOCK + [
        "--strict-mcp-config", "--no-session-persistence", "--output-format", "stream-json", "--verbose",
        "--include-partial-messages", "--append-system-prompt", ASK_SYSTEM % (("%s's" % name) if name else "the owner's")]


def locked_env():
    env = dict(os.environ)
    for name in BILLING_ENV:
        env.pop(name, None)
    return env


def same(given, secret):
    return bool(given) and bool(secret) and hmac.compare_digest(given.encode("utf-8"), secret.encode("utf-8"))


def cookie(header, name):
    """One cookie out of the header. Other programs on 127.0.0.1 set cookies too, whatever their port, and one of them
    in an odd shape must not hide this one."""
    for part in (header or "").split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key == name:
            return value.strip().strip('"')
    return ""


def web_version():
    """An open tab reloads itself when this changes, so nobody keeps clicking on old code. The installers give every
    file the same date, so the version's number is part of it."""
    try:
        number = (HERE / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        number = ""
    return "%s-%d" % (number, max(int((WEB / name).stat().st_mtime) for name, _ in STATIC.values()))


class Handler(BaseHTTPRequestHandler):
    server_version = "Brento"
    sys_version = ""
    app = None
    # True on the phone door. The same page, with less it may do.
    phone = False

    def log_message(self, *args):
        pass

    def send_common(self, status, ctype, cache="no-store", csp=CSP):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Security-Policy", csp)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_common(status, "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def host_allowed(self):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in self.app.hosts

    def authorized(self):
        return (same(cookie(self.headers.get("Cookie"), "leitstand"), self.app.key)
                or same(self.headers.get(address.KEY_HEADER), self.app.key))

    def gate(self, url):
        """Refuses foreign Host headers (DNS rebinding) and anything without the owner's key."""
        if self.phone:
            return self.phone_gate(url)
        if not self.host_allowed():
            self.send_json({"error": "host not allowed"}, 403)
            return False
        query = parse_qs(url.query)
        front = self.command == "GET" and url.path == "/"
        if front and ("ticket" in query or "key" in query):
            self.enter(query)
            return False
        if self.authorized() or (self.command == "GET" and url.path == "/api/whose"):
            return True
        if front:
            self.send_page(LOCKED, 401)
        else:
            self.send_json({"error": "Open Brento with its icon first."}, 401)
        return False

    def enter(self, query):
        """The way in: the launcher's ticket, or the key itself from another computer. The address is cleaned at once."""
        good = self.app.redeem((query.get("ticket") or [""])[0]) or same((query.get("key") or [""])[0], self.app.key)
        self.send_response(303)
        self.send_header("Location", "/")
        if good:
            self.send_header("Set-Cookie", "leitstand=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000" % self.app.key)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def phone_gate(self, url):
        """The phone door: the pairing page for a phone that is not paired yet, a shorter list of routes for one that is."""
        if not phone.host_ok(self.headers.get("Host"), self.app.hosts):
            self.send_json({"error": "host not allowed"}, 403)
            return False
        if not self.app.phones.on:
            self.send_json({"error": "Phone access is switched off on the computer."}, 403)
            return False
        if self.app.phones.known(cookie(self.headers.get("Cookie"), phone.COOKIE)):
            if phone.allowed(self.command, url.path):
                return True
            self.send_json({"error": "Only on the computer. Change this in Brento there."}, 403)
            return False
        if self.command == "GET" and url.path in phone.OPEN_PATHS:
            return True
        if self.command == "POST" and url.path == "/pair":
            self.pair()
            return False
        if self.command == "GET" and url.path in ("/", "/pair"):
            self.send_page(phone.page())
            return False
        self.send_json({"error": "Pair this phone first."}, 401)
        return False

    def send_page(self, body, status=200):
        self.send_common(status, "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def pair(self):
        """The pairing form. A right code gives this phone its own token, a wrong one counts against the code."""
        origin = urlsplit(self.headers.get("Origin") or "").netloc
        if origin and origin != self.headers.get("Host"):
            self.send_json({"error": "cross-site request refused"}, 403)
            return
        try:
            length = min(int(self.headers.get("Content-Length") or 0), 200)
        except ValueError:
            length = 0
        typed = (parse_qs(self.rfile.read(length).decode("utf-8", "replace")).get("code") or [""])[0]
        token = self.app.phones.pair(typed)
        if not token:
            self.send_page(phone.page(phone.WRONG), 401)
            return
        self.send_response(303)
        self.send_header("Location", "/#home")
        self.send_header("Set-Cookie", "%s=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000" % (phone.COOKIE, token))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        url = urlsplit(self.path)
        if not self.gate(url):
            return
        # Not asked of a phone: its short list of routes does nothing on the computer, and an older page may be open there.
        if url.path.startswith("/api/") and url.path not in PLAIN_GETS and not self.phone and self.headers.get("X-Leitstand") != "1":
            self.send_json({"error": "cross-site request refused"}, 403)
            return
        if url.path in STATIC:
            name, ctype = STATIC[url.path]
            body = (WEB / name).read_bytes()
            self.send_common(200, ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif PHOTO.match(url.path):
            path = WEB / "photos" / PHOTO.match(url.path).group(1)
            if not path.is_file():
                self.send_json({"error": "not found"}, 404)
                return
            body = path.read_bytes()
            # A photo never changes under its name, so the window keeps it instead of reading 400 KB on every card.
            photo = path.suffix == ".webp"
            self.send_common(200, "image/webp" if photo else "application/json; charset=utf-8", "max-age=604800" if photo else "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/api/state":
            self.send_json(dict(self.app.state(), webVersion=web_version(), phone=self.phone))
        elif url.path == "/api/whose":
            # Only the owner's launcher can tell a right answer from a wrong one.
            nonce = (parse_qs(url.query).get("n") or [""])[0]
            if address.NONCE.match(nonce):
                self.send_json({"proof": address.proof(self.app.key, self.app.port, nonce)})
            else:
                self.send_json({"error": "bad request"}, 400)
        elif url.path == "/api/phone":
            self.send_json(self.app.phone_view())
        elif url.path == "/api/setup":
            self.send_json(self.app.setup_view())
        elif url.path == "/api/wizard":
            self.send_json(self.app.wizard_view())
        elif url.path == "/api/wizard/gh":
            # Polled while a sign-in runs, so the page moves on by itself once it is done.
            gh = sources.gh_status()
            found, error = wizard.projects() if gh["ready"] else ([], "")
            self.send_json({"gh": gh, "projects": found, "projectsError": error, "install": dict(wizard.INSTALL),
                            "orgs": wizard.orgs() if gh["ready"] else [], "signin": wizard.SIGNIN.view()})
        elif url.path == "/api/wizard/claude":
            self.send_json(dict(self.app.auth(even_off=True, fresh=True), signin=wizard.SIGNIN.view()))
        elif url.path == "/api/wizard/vault":
            self.send_json(wizard.vault_stats((parse_qs(url.query).get("path") or [""])[0][:500]))
        elif url.path.startswith("/api/library") and not settings.on(self.app.profile, "library"):
            self.send_json({"error": "The library is switched off in the setup."}, 404)
        elif url.path == "/api/library":
            self.send_json(self.app.library.overview())
        elif url.path == "/api/library/note":
            note = self.app.library.note((parse_qs(url.query).get("path") or [""])[0])
            self.send_json(note if note else {"error": "No such note"}, 200 if note else 404)
        elif url.path == "/api/library/search":
            self.send_json({"hits": self.app.library.search((parse_qs(url.query).get("q") or [""])[0][:200])})
        elif url.path == "/api/library/asset":
            data, ctype = self.app.library.asset((parse_qs(url.query).get("path") or [""])[0])
            if data is None:
                self.send_json({"error": "No such image"}, 404)
            else:
                self.send_common(200, ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        elif url.path == "/api/library/page":
            data = self.app.library.page((parse_qs(url.query).get("path") or [""])[0])
            if data is None:
                self.send_json({"error": "No such page"}, 404)
            else:
                self.send_common(200, "text/html; charset=utf-8", csp=CSP_PAGE)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        elif url.path == "/api/ask/status":
            self.send_json(self.app.auth())
        elif url.path == "/api/tools":
            self.send_json(self.app.tools.shown())
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        self.body_read = False
        self.handle_post()
        if not self.body_read:
            self.drain()

    def drain(self):
        """Takes in what a refused request still has to say. Closing with it unread can cut off the answer on its way."""
        try:
            left = min(int(self.headers.get("Content-Length") or 0), MAX_BODY)
            if left > 0:
                self.connection.settimeout(2)
                self.rfile.read(left)
        except (OSError, ValueError):
            pass

    def handle_post(self):
        url = urlsplit(self.path)
        if not self.gate(url):
            return
        if url.path not in ("/api/ask", "/api/tools", "/api/calendar", "/api/refresh", "/api/open", "/api/setup",
                            "/api/setup/board", "/api/wizard/board", "/api/wizard/open", "/api/slack", "/api/team",
                            "/api/phone", "/api/ticket"):
            self.send_json({"error": "not found"}, 404)
            return
        origin = urlsplit(self.headers.get("Origin") or "").netloc
        if self.headers.get("X-Leitstand") != "1" or (origin and origin != self.headers.get("Host")):
            self.send_json({"error": "cross-site request refused"}, 403)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self.send_json({"error": "too long"}, 413)
            return
        self.body_read = True
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            self.send_json({"error": "bad request"}, 400)
            return
        if url.path == "/api/refresh":
            self.send_json({"problems": self.app.refresh()})
            return
        if url.path == "/api/ticket":
            self.send_json({"ticket": self.app.ticket()})
            return
        if url.path == "/api/phone":
            try:
                self.send_json(self.app.phone_action(str(body.get("action") or "")))
            except (ValueError, OSError) as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if url.path == "/api/setup":
            try:
                self.send_json(self.app.save_setup(body if isinstance(body, dict) else {}))
            except (ValueError, OSError) as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if url.path == "/api/wizard/board":
            try:
                self.send_json(self.app.wizard_board(body if isinstance(body, dict) else {}))
            except (ValueError, OSError) as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if url.path == "/api/team":
            # The team lead's setup as team.json next to the code: board, apps, calendar kind, Slack timing.
            # Nothing personal goes in: no vault, no name, no link with a key.
            try:
                p = self.app.profile
                board = {k: v for k, v in p["board"].items() if k not in ("me", "aging")}
                self.app.team = settings.save_team(HERE, {"team": str(body.get("team") or "")[:40], "board": board,
                                                          "tools": body.get("tools") or [], "calendar": body.get("calendar") or "",
                                                          "slack": p.get("slack")})
                self.send_json({"saved": settings.TEAM_FILE, "team": self.app.team})
            except (ValueError, OSError) as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if url.path == "/api/wizard/open":
            # Only the fixed programs in wizard.ACTIONS, so no page can make this server run anything else.
            try:
                self.send_json(wizard.start_action(str(body.get("action") or "")))
            except (ValueError, OSError) as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if url.path == "/api/slack":
            # The link goes one way, onto the disk. A test message proves that it works before it is kept.
            try:
                if body.get("disconnect"):
                    self.app.slack.disconnect()
                elif body.get("test"):
                    error = self.app.slack.send("A test from Brento. All good.")
                    if error:
                        raise ValueError(error)
                else:
                    self.app.slack.connect(body.get("url"), "Brento is connected. Your morning summary and reminders come to this channel.")
                self.send_json({"connected": self.app.slack.connected()})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if url.path == "/api/setup/board":
            # Reads one project's title and fields for the form. The answer is only shown, nothing is saved.
            owner, kind = str(body.get("owner") or "").strip(), "org" if body.get("ownerType") == "org" else "user"
            try:
                number = int(body.get("number") or 0)
            except (TypeError, ValueError):
                number = 0
            if not settings.GH_LOGIN.match(owner) or number <= 0:
                self.send_json({"error": "Give the owner's GitHub login and the project's number."}, 400)
                return
            self.send_json(sources.probe_board(owner, number, kind))
            return
        if url.path == "/api/open":
            try:
                self.send_json({"opened": self.app.open_tool(body)})
            except (ValueError, OSError) as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if url.path == "/api/calendar":
            # The link goes one way: onto the disk. Nothing ever sends it back to a page.
            try:
                found = None
                if body.get("disconnect"):
                    self.app.calendar.disconnect()
                else:
                    # Read at once, so a wrong link is caught while the owner is still there, and never replaces a good one.
                    self.app.calendar.connect(body.get("url"))
                    found = len(calendar_feed.parse_ics(self.app.calendar.text or "", time_today(), 90))
                self.app.state_at = 0.0
                self.send_json({"connected": self.app.calendar.connected(), "events": found})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if url.path == "/api/tools":
            if self.phone and body.get("action") != "card":
                # From a phone only "remove this card from Home". The dock is changed on the computer.
                self.send_json({"error": "Only on the computer. Change the dock in Brento there."}, 403)
                return
            try:
                result = self.app.tools.apply(body)
                if body.get("action") == "card":
                    # Home shows the change on the next read, not up to 20 seconds later.
                    self.app.state_at = 0.0
                self.send_json(result)
            except tools.ToolError as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        question = str(body.get("q") or "").strip()[:4000]
        history = body.get("history") if isinstance(body.get("history"), list) else []
        if not question:
            self.send_json({"error": "empty question"}, 400)
            return
        auth = self.app.auth()
        if not auth["ready"]:
            self.send_json({"error": auth["reason"]}, 409)
            return
        problem = sources.folder_problem(self.app.vault)
        if problem:
            self.send_json({"error": "Ask cannot answer: %s." % problem}, 409)
            return
        if not self.app.ask_lock.acquire(blocking=False):
            self.send_json({"error": "One question at a time. The last answer is still running."}, 429)
            return
        try:
            self.stream_answer(question, history)
        finally:
            self.app.ask_lock.release()

    def emit(self, **event):
        self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
        self.wfile.flush()

    def stream_answer(self, question, history):
        parts = []
        for turn in history[-6:]:
            if isinstance(turn, dict):
                parts.append("%s: %s" % ((self.app.profile.get("name") or "User") if turn.get("role") == "user" else "You",
                                         str(turn.get("text") or "")[:1500]))
        prompt = ("Earlier in this conversation:\n%s\n\nNew question: %s" % ("\n".join(parts), question)
                  if parts else question)
        cmd = ask_command(settings.find_exe("claude"), self.app.model, self.app.profile.get("name", ""))
        self.send_common(200, "application/x-ndjson; charset=utf-8")
        self.end_headers()
        started = time.time()
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                cwd=str(self.app.vault), env=locked_env(), encoding="utf-8", errors="replace",
                                creationflags=sources.NO_WINDOW)
        timer = threading.Timer(ASK_TIMEOUT, proc.kill)
        timer.start()
        wrote_text = False
        finished = False
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
            for line in proc.stdout:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                kind = ev.get("type")
                if kind == "stream_event":
                    inner = ev.get("event") or {}
                    if inner.get("type") == "message_start" and wrote_text:
                        self.emit(t="delta", text="\n\n")
                    delta = inner.get("delta") or {}
                    if inner.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                        wrote_text = True
                        self.emit(t="delta", text=delta.get("text", ""))
                elif kind == "assistant":
                    for block in (ev.get("message") or {}).get("content") or []:
                        if block.get("type") == "tool_use":
                            detail = block.get("input") or {}
                            target = detail.get("file_path") or detail.get("pattern") or ""
                            self.emit(t="status", text="%s %s" % (block.get("name"), Path(str(target)).name if detail.get("file_path") else target))
                elif kind == "result":
                    finished = True
                    if ev.get("is_error"):
                        self.emit(t="error", text=str(ev.get("result") or "The run failed.")[:400])
                    else:
                        self.emit(t="done", ms=int((time.time() - started) * 1000), turns=ev.get("num_turns"))
            if not finished:
                self.emit(t="error", text="The run ended without an answer (timeout or login problem).")
        except (BrokenPipeError, ConnectionError, OSError):
            pass
        finally:
            timer.cancel()
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=10)


class PhoneHandler(Handler):
    phone = True


class Server(ThreadingHTTPServer):
    # On Windows this flag would let a second program take the same port, so it stays off there.
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True

    def server_bind(self):
        # Python's own version also looks this computer's name up before it listens. Nothing here needs the name, and
        # on a computer whose network does not answer, Brento would not open until the lookup gives up.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


class PhoneServer(Server):
    """The second door, on the home network, only for paired phones."""


def main():
    parser = argparse.ArgumentParser(description="Brento")
    parser.add_argument("--vault", default=os.environ.get("BRENTO_VAULT") or os.environ.get("LEITSTAND_VAULT"),
                        help="only needed before the setup has run; the setup's vault wins once it is saved")
    parser.add_argument("--host", default="127.0.0.1", help="anything but loopback requires the access key")
    parser.add_argument("--port", type=int, default=0, help="only this port; without it, the usual one or the next free one")
    parser.add_argument("--allow-host", action="append", default=[], help="extra Host header to accept, for example a Tailscale name")
    parser.add_argument("--model", default=os.environ.get("LEITSTAND_MODEL", "sonnet"))
    args = parser.parse_args()
    vault = None
    if args.vault:
        vault = Path(args.vault).expanduser().resolve()
        if not vault.is_dir():
            raise SystemExit("Vault not found: %s" % vault)
    app = App(vault, args.host, args.allow_host, args.model)
    Handler.app = app
    server = None
    for number in address.candidates(args.port):
        try:
            server = Server((args.host, number), Handler)
            break
        except OSError as exc:
            # Ending cleanly keeps a login service from starting it again and again.
            if args.port or address.whose(number, timeout=10) == "mine":
                print("Port %d is in use, so this Brento is not started (%s)." % (number, exc), flush=True)
                return
            # Another person on this computer, or another program: the next port.
    if server is None:
        print("No port from %d on is free, so Brento is not started." % address.FIRST, flush=True)
        return
    app.port = number
    if not args.port and number != address.port():
        address.keep(number)
    threading.Thread(target=app.notify_loop, daemon=True).start()
    app.phone_listen()
    way = "?ticket=" + app.ticket() if args.host in LOOPBACK else "?key=" + app.key
    print("Brento reads %s (settings in %s)\nOpen http://%s:%d/%s" % (app.vault, app.home, args.host, number, way), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
