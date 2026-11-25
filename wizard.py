"""What the first-start wizard needs: guesses, checks, and the few things it does on the owner's click.

It guesses what it can (name, vault, board fields), so the owner mostly clicks Next. Where something has to
happen outside Daytag (fetch the GitHub program, sign in), it runs the official program without any window, with a
fixed command, and the page shows what to do and checks again until it is done. Nothing here runs without a click.
"""
import getpass
import hashlib
import io
import json
import os
import platform
import re
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import settings
import sources

# The board Daytag makes for a new owner: its own lane field, because a project's built-in Status field
# cannot be given new options from the command line.
LANE_FIELD = "Lane"
LANES = "HIGH,MID,LOW,Done"
AREAS = "Work,Private"
DUE_FIELD = "Due"
# Field names a board often already uses, so an existing board maps without questions.
AREA_NAMES = ("area", "bereich", "category", "project", "team")
DUE_NAMES = ("due", "due date", "deadline", "frist", "target date", "date", "end date")
DONE_NAMES = ("done", "done date", "completed", "erledigt am", "closed")
# Programs the wizard may start, each with fixed arguments. "{gh}" and "{claude}" become the program's full path.
ACTIONS = {
    "gh-install": [],
    "gh-login": ["{gh}", "auth", "login", "--hostname", "github.com", "--web", "--git-protocol", "https", "-s", "project"],
    "gh-scope": ["{gh}", "auth", "refresh", "--hostname", "github.com", "-s", "project"],
    "claude-login": ["{claude}", "auth", "login"],
}
NO_WINDOW = sources.NO_WINDOW
# GitHub's program prints a one-time code, and the owner types it on GitHub's own page. The code is the only thing
# Daytag reads off a sign-in: the logins themselves stay inside the two programs.
GH_CODE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{4})\b")
GH_DEVICE = "https://github.com/login/device"
SIGN_IN_LIMIT = 15 * 60
# The installers bring the GitHub program along. Without it, Daytag fetches the official one from its own GitHub
# releases, checks it against the release's checksum list, and keeps the one program in its folder. No admin rights.
GH_RELEASE = "https://api.github.com/repos/cli/cli/releases/latest"
GH_HOSTS = ("api.github.com", "github.com")
INSTALL = {"running": False, "error": "", "done": False}
MAX_DOWNLOAD = 80 * 1024 * 1024


def run(args, timeout=60):
    try:
        out = subprocess.run(args, capture_output=True, timeout=timeout, encoding="utf-8", errors="replace",
                             creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if out.returncode != 0:
        return None, (out.stderr or out.stdout or "failed").strip()[:300]
    return out.stdout, ""


def gh_asset(names, system, machine):
    """The release file for this computer: a zip on a Mac or Windows, a tar.gz on Linux. None where there is none."""
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get((machine or "").lower())
    tail = {"darwin": "_macOS_%s.zip", "win32": "_windows_%s.zip", "linux": "_linux_%s.tar.gz"}.get(system)
    if not arch or not tail:
        return None
    return next((n for n in names if n.startswith("gh_") and n.endswith(tail % arch)), None)


def checksum_for(text, name):
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == name and re.match(r"^[0-9a-f]{64}$", parts[0]):
            return parts[0]
    return ""


def extract_gh(data, name, target):
    """Takes only bin/gh out of the archive and writes it where Daytag chose, never to a path the archive names."""
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            member = next((m for m in archive.namelist() if re.search(r"(^|/)bin/gh(\.exe)?$", m)), None)
            if not member:
                raise ValueError("The download has no gh program in it.")
            body = archive.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            member = next((m for m in archive.getmembers() if m.isfile() and m.name.endswith("/bin/gh")), None)
            if not member:
                raise ValueError("The download has no gh program in it.")
            body = archive.extractfile(member).read()
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    part.write_bytes(body)
    part.chmod(0o755)
    part.replace(target)
    return target


def fetch_https(url):
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname not in GH_HOSTS:
        raise ValueError("Daytag only downloads from github.com.")
    accept = "application/vnd.github+json" if "api.github.com" in url else "application/octet-stream"
    request = urllib.request.Request(url, headers={"User-Agent": "Daytag-setup", "Accept": accept})
    with urllib.request.urlopen(request, timeout=90) as answer:
        return answer.read(MAX_DOWNLOAD)


def install_gh(fetch=fetch_https, system=None, machine=None, target=None):
    """Downloads the GitHub CLI for this computer and checks it before it is kept. Returns the error, or ''."""
    INSTALL.update(running=True, error="", done=False)
    try:
        release = json.loads(fetch(GH_RELEASE).decode("utf-8"))
        assets = {a.get("name"): a.get("browser_download_url") for a in release.get("assets") or [] if isinstance(a, dict)}
        name = gh_asset(list(assets), system or settings.system(), machine or platform.machine())
        if not name:
            raise ValueError("There is no GitHub CLI download for this computer. Install it from cli.github.com.")
        sums = next((n for n in assets if str(n).endswith("_checksums.txt")), None)
        want = checksum_for(fetch(assets[sums]).decode("utf-8"), name) if sums else ""
        if not want:
            raise ValueError("The download comes without a checksum, so Daytag does not install it.")
        data = fetch(assets[name])
        if hashlib.sha256(data).hexdigest() != want:
            raise ValueError("The download did not match its checksum, so Daytag did not install it.")
        program = "gh.exe" if (system or settings.system()) == "win32" else "gh"
        extract_gh(data, name, target or settings.home() / "bin" / program)
        INSTALL["done"] = True
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, tarfile.TarError) as exc:
        text = str(exc)
        if "CERTIFICATE_VERIFY_FAILED" in text:
            text = ("This Python cannot check https certificates yet. Python from python.org: open Applications, "
                    "the Python folder, and double-click Install Certificates.command. Then click again.")
        INSTALL["error"] = text[:300]
    finally:
        INSTALL["running"] = False
    return INSTALL["error"]


def guess_name(gh_ready):
    """The owner's first name: GitHub knows it, git often does, the computer's login is the last guess."""
    gh = settings.find_exe("gh")
    if gh and gh_ready:
        text, _ = run([gh, "api", "user", "--jq", ".name"], 20)
        if text and text.strip():
            return text.strip().split()[0][:40]
    git = settings.find_exe("git")
    if git:
        text, _ = run([git, "config", "--global", "user.name"], 10)
        if text and text.strip():
            return text.strip().split()[0][:40]
    try:
        login = getpass.getuser()
    except (OSError, KeyError):
        return ""
    return re.sub(r"[^A-Za-zÀ-ÿ-]", "", login.split(".")[0]).capitalize()[:40]


def vault_stats(folder):
    """How much Daytag will find in a vault: notes and open tasks with a date. Counted, never read out."""
    # Not Path.expanduser, which raises for a ~name nobody has.
    root = Path(os.path.expanduser(folder))
    if not folder or not os.path.isdir(str(root)):
        return {"notes": 0, "tasks": 0, "error": "That folder does not exist."}
    try:
        os.listdir(str(root))
    except PermissionError:
        if settings.system() == "darwin":
            return {"notes": 0, "tasks": 0, "error": "macOS does not let Daytag read this folder yet. Open System Settings, "
                    "Privacy & Security, Files & Folders, and switch the folder on for %s. If %s is not in that list, add it "
                    "under Full Disk Access instead. Then choose the folder here again."
                    % ((os.path.basename(sys.executable) or "python3",) * 2)}
        return {"notes": 0, "tasks": 0, "error": "Daytag may not read this folder."}
    except OSError:
        return {"notes": 0, "tasks": 0, "error": "That folder cannot be read at the moment."}
    notes = 0
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not sources.skipped(d)]
        notes += sum(1 for name in files if name.endswith(".md") or sources.ICLOUD_STUB.match(name))
        if notes > 20000:
            break
    index = sources.TaskIndex(root)
    try:
        tasks = len(index.scan(wait=20))
    except (OSError, sources.StillReading):
        return {"notes": notes, "tasks": None, "missing": "", "error": ""}
    return {"notes": notes, "tasks": tasks, "missing": index.trouble(), "error": ""}


def projects():
    """The owner's own boards, newest first, for one click in the wizard."""
    gh = settings.find_exe("gh")
    if not gh:
        return [], "GitHub CLI is not installed."
    text, error = run([gh, "project", "list", "--owner", "@me", "--format", "json", "--limit", "50"])
    if error:
        return [], error
    try:
        rows = json.loads(text).get("projects") or []
    except ValueError:
        return [], "gh gave an answer Daytag could not read."
    out = [{"number": p.get("number"), "title": p.get("title") or "Untitled", "url": p.get("url"),
            "owner": (p.get("owner") or {}).get("login", ""), "ownerType": "org" if (p.get("owner") or {}).get("type") == "Organization" else "user",
            "cards": (p.get("items") or {}).get("totalCount", 0)} for p in rows if not p.get("closed")]
    return sorted(out, key=lambda p: -int(p["number"] or 0)), ""


def auto_fields(probe):
    """Maps a board's own fields to what Daytag reads, by their names and types. Returns the mapping and,
    when no field holds the lanes HIGH, MID and LOW, says so."""
    fields = probe.get("fields") or []
    singles = [f for f in fields if f.get("type") == "SINGLE_SELECT"]
    dates = [f for f in fields if f.get("type") == "DATE"]

    def named(pool, names):
        for wanted in names:
            for f in pool:
                if f["name"].strip().lower() == wanted:
                    return f["name"]
        return ""

    with_lanes = [f for f in singles if {"HIGH", "MID", "LOW"} <= set(f.get("options") or [])]
    status = (named(with_lanes, ("status", "lane")) or (with_lanes[0]["name"] if with_lanes else "")) or "Status"
    area = named([f for f in singles if f["name"] != status], AREA_NAMES)
    return {"statusField": status, "areaField": area, "dueField": named(dates, DUE_NAMES),
            "doneField": named(dates, DONE_NAMES), "lanesFound": bool(with_lanes)}


def orgs():
    """The organizations the signed-in owner belongs to: where a team board can live."""
    gh = settings.find_exe("gh")
    text, _ = run([gh, "api", "user/orgs", "--jq", ".[].login"], 20) if gh else (None, "")
    return [line.strip() for line in (text or "").splitlines() if settings.GH_LOGIN.match(line.strip())]


def create_board(title="Daytag", org=""):
    """A new board with the lanes, an area and a due date: the owner's own, or a team board in an organization."""
    gh = settings.find_exe("gh")
    if not gh:
        raise ValueError("GitHub CLI is not installed.")
    title = re.sub(r"[^\w .\-]", "", str(title or "Daytag"))[:60] or "Daytag"
    if org and not settings.GH_LOGIN.match(org):
        raise ValueError("Unknown organization.")
    text, error = run([gh, "project", "create", "--owner", org or "@me", "--title", title, "--format", "json"])
    if error:
        raise ValueError("GitHub did not create the board: %s" % error)
    try:
        made = json.loads(text)
        number = int(made["number"])
    except (ValueError, KeyError, TypeError):
        raise ValueError("The board was made, but its number could not be read. Pick it from the list.")
    owner = org or ((made.get("owner") or {}).get("login")) or login()
    add_fields(owner, number, lanes=True)
    return {"owner": owner, "ownerType": "org" if org else "user", "number": number, "lanesFound": True, "url": made.get("url", ""), "title": title,
            "statusField": LANE_FIELD, "areaField": "Area", "dueField": DUE_FIELD, "doneField": ""}


def add_fields(owner, number, lanes=True, area=True, due=True):
    """Adds Daytag's fields to a board. Only adds: no existing field or card is changed."""
    gh = settings.find_exe("gh")
    plan = []
    if lanes:
        plan.append(["--name", LANE_FIELD, "--data-type", "SINGLE_SELECT", "--single-select-options", LANES])
    if area:
        plan.append(["--name", "Area", "--data-type", "SINGLE_SELECT", "--single-select-options", AREAS])
    if due:
        plan.append(["--name", DUE_FIELD, "--data-type", "DATE"])
    for extra in plan:
        _, error = run([gh, "project", "field-create", str(number), "--owner", owner] + extra)
        if error and "already" not in error.lower():
            raise ValueError("GitHub did not add the field %s: %s" % (extra[1], error))


def login():
    gh = settings.find_exe("gh")
    text, _ = run([gh, "api", "user", "--jq", ".login"], 20) if gh else (None, "")
    return (text or "").strip()


class SignIn:
    """One sign-in at a time, without a window. A new click ends the old one, so a code that ran out gives way to a
    fresh one. GitHub's program is read for its one-time code; Claude's program is not read at all."""

    def __init__(self):
        self.lock = threading.Lock()
        self.proc, self.action, self.code, self.error = None, "", "", ""

    def view(self):
        with self.lock:
            return {"action": self.action, "running": self.proc is not None, "code": self.code, "url": GH_DEVICE,
                    "error": self.error}

    def end(self):
        """Daytag ends: a sign-in that waits for its code must not run on."""
        with self.lock:
            if self.proc is not None:
                self.proc.kill()

    def start(self, action, args):
        github = action.startswith("gh")
        env = dict(os.environ, GH_PROMPT_DISABLED="1", NO_COLOR="1")
        if github and settings.system() == "darwin" and not settings.find_exe("git"):
            # GitHub's program starts git when it finds one. On a Mac without developer tools that is only Apple's
            # placeholder, which offers a large download. So here it finds nothing but itself.
            env["PATH"] = os.path.dirname(args[0])
        with self.lock:
            if self.proc is not None:
                self.proc.kill()
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
                                    stdout=subprocess.PIPE if github else subprocess.DEVNULL,
                                    stderr=subprocess.STDOUT if github else subprocess.DEVNULL, env=env)
            self.proc, self.action, self.code, self.error = proc, action, "", ""
        threading.Thread(target=self._watch, args=(proc,), daemon=True).start()

    def _watch(self, proc):
        late = threading.Event()

        def end():
            late.set()
            proc.kill()
        timer = threading.Timer(SIGN_IN_LIMIT, end)
        timer.daemon = True
        timer.start()
        last = ""
        for raw in proc.stdout or ():
            line = raw.decode("utf-8", "replace").strip()
            last = line or last
            found = GH_CODE.search(line) if "code" in line.lower() else None
            with self.lock:
                if found and self.proc is proc:
                    self.code = found.group(1)
        if proc.stdout:
            proc.stdout.close()
        result = proc.wait()
        timer.cancel()
        with self.lock:
            # A newer click already took over: its own watcher speaks for it.
            if self.proc is not proc:
                return
            self.proc, self.code = None, ""
            self.error = "" if result == 0 else self.explain(last, late.is_set())

    @staticmethod
    def explain(last, late=False):
        low = last.lower()
        if late or "expired" in low or "deadline exceeded" in low:
            return "The sign-in ran out of time. Click the button to start again."
        if "denied" in low:
            return "The sign-in was cancelled. Click the button to start again."
        if not last:
            return "The sign-in did not work. Click the button to start again."
        return "The sign-in did not work: %s" % GH_CODE.sub("the code", last)[:200]


SIGNIN = SignIn()


def start_action(action, wait=5.0):
    """Starts one of the fixed programs without a window and returns at once. A GitHub sign-in waits a moment for its
    one-time code, so the page usually has it with the first answer."""
    if action not in ACTIONS:
        raise ValueError("Unknown action.")
    if action == "gh-install":
        if settings.STORE:
            # A Store version offers nothing that is not in the Store (policy 10.1.5), and brings the GitHub program along.
            raise ValueError("The GitHub program comes with Daytag.")
        # The download runs here, and the page asks every few seconds until gh is found.
        if not INSTALL["running"]:
            INSTALL.update(running=True, error="", done=False)
            threading.Thread(target=install_gh, daemon=True).start()
        return {"started": True, "signin": SIGNIN.view()}
    needs = {"{gh}": "gh", "{claude}": "claude"}
    names = {"gh": "The GitHub program", "claude": "Claude Code"}
    args = []
    for part in ACTIONS[action]:
        if part in needs:
            exe = settings.find_exe(needs[part])
            if not exe:
                raise ValueError("%s is not installed on this computer." % names[needs[part]])
            args.append(exe)
        else:
            args.append(part)
    SIGNIN.start(action, args)
    ends = time.monotonic() + (wait if action.startswith("gh") else 0)
    view = SIGNIN.view()
    while view["running"] and not view["code"] and time.monotonic() < ends:
        time.sleep(0.1)
        view = SIGNIN.view()
    return {"started": True, "signin": view}
