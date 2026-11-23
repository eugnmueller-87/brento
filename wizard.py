"""What the first-start wizard needs: guesses, checks, and the few things it does on the owner's click.

It guesses what it can (name, vault, board fields), so the owner mostly clicks Next. Where something has to
happen outside Brento (install the GitHub CLI, sign in), it opens the official program in its own window,
with a fixed command, and the page checks again until it is done. Nothing here runs without a click.
"""
import getpass
import hashlib
import io
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import tarfile
import threading
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import settings
import sources

# The board Brento makes for a new owner: its own lane field, because a project's built-in Status field
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
    "gh-install": ["{winget}", "install", "--id", "GitHub.cli", "-e", "--source", "winget",
                   "--accept-package-agreements", "--accept-source-agreements"],
    "gh-login": ["{gh}", "auth", "login", "--web", "--clipboard", "--git-protocol", "https", "-s", "project"],
    "gh-scope": ["{gh}", "auth", "refresh", "-s", "project"],
    "claude-login": ["{claude}", "auth", "login"],
}
NO_WINDOW = sources.NO_WINDOW
# On a Mac or Linux there is no winget. Brento fetches the official GitHub CLI from its own GitHub releases instead,
# checks it against the release's checksum list, and keeps the one program in its folder. No admin rights.
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
    """The release file for this computer: a zip on a Mac, a tar.gz on Linux. None where there is none."""
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get((machine or "").lower())
    tail = {"darwin": "_macOS_%s.zip", "linux": "_linux_%s.tar.gz"}.get(system)
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
    """Takes only bin/gh out of the archive and writes it where Brento chose, never to a path the archive names."""
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            member = next((m for m in archive.namelist() if m.endswith("/bin/gh")), None)
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
        raise ValueError("Brento only downloads from github.com.")
    accept = "application/vnd.github+json" if "api.github.com" in url else "application/octet-stream"
    request = urllib.request.Request(url, headers={"User-Agent": "Brento-setup", "Accept": accept})
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
            raise ValueError("The download comes without a checksum, so Brento does not install it.")
        data = fetch(assets[name])
        if hashlib.sha256(data).hexdigest() != want:
            raise ValueError("The download did not match its checksum, so Brento did not install it.")
        extract_gh(data, name, target or settings.home() / "bin" / "gh")
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
    """How much Brento will find in a vault: notes and open tasks with a date. Counted, never read out."""
    root = Path(folder)
    if not root.is_dir():
        return {"notes": 0, "tasks": 0, "error": "That folder does not exist."}
    notes = 0
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in sources.SKIP_DIRS]
        notes += sum(1 for name in files if name.endswith(".md"))
        if notes > 20000:
            break
    try:
        os.listdir(root)
    except PermissionError:
        if settings.system() == "darwin":
            return {"notes": 0, "tasks": 0, "error": "macOS does not let Brento read this folder yet. Open System Settings, "
                    "Privacy & Security, Full Disk Access, and switch on python3. Then choose the folder again."}
        return {"notes": 0, "tasks": 0, "error": "Brento may not read this folder."}
    tasks = len(sources.TaskIndex(root).scan())
    return {"notes": notes, "tasks": tasks, "error": ""}


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
        return [], "gh gave an answer Brento could not read."
    out = [{"number": p.get("number"), "title": p.get("title") or "Untitled", "url": p.get("url"),
            "owner": (p.get("owner") or {}).get("login", ""), "ownerType": "org" if (p.get("owner") or {}).get("type") == "Organization" else "user",
            "cards": (p.get("items") or {}).get("totalCount", 0)} for p in rows if not p.get("closed")]
    return sorted(out, key=lambda p: -int(p["number"] or 0)), ""


def auto_fields(probe):
    """Maps a board's own fields to what Brento reads, by their names and types. Returns the mapping and,
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


def create_board(title="Brento", org=""):
    """A new board with the lanes, an area and a due date: the owner's own, or a team board in an organization."""
    gh = settings.find_exe("gh")
    if not gh:
        raise ValueError("GitHub CLI is not installed.")
    title = re.sub(r"[^\w .\-]", "", str(title or "Brento"))[:60] or "Brento"
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
    """Adds Brento's fields to a board. Only adds: no existing field or card is changed."""
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


def open_window(action):
    """Starts one of the fixed programs in a window the owner can see, and returns at once.
    On macOS and Linux it returns the command instead, for the owner to run in a terminal."""
    if action not in ACTIONS:
        raise ValueError("Unknown action.")
    if action == "gh-install" and settings.system() != "win32":
        # No window needed: the download runs here, and the page asks every few seconds until gh is found.
        if not INSTALL["running"]:
            threading.Thread(target=install_gh, daemon=True).start()
        return {"opened": True, "command": "download from github.com/cli/cli"}
    needs = {"{gh}": "gh", "{claude}": "claude", "{winget}": "winget"}
    args = []
    for part in ACTIONS[action]:
        if part in needs:
            exe = settings.find_exe(needs[part])
            if not exe:
                names = {"gh": "GitHub CLI", "claude": "Claude Code", "winget": "winget (App Installer)"}
                raise ValueError("%s is not installed on this computer." % names[needs[part]])
            args.append(exe)
        else:
            args.append(part)
    shown = " ".join(a if " " not in a else '"%s"' % a for a in [needs.get(ACTIONS[action][0], args[0])] + args[1:])
    if settings.system() == "darwin":
        # A small script in Brento's folder, opened by Terminal. Made here, so macOS has nothing to block.
        script = settings.home() / ("run-%s.command" % action)
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("#!/bin/sh\n# Started by Brento's setup. Safe to delete.\n%s\necho\n"
                          "echo 'Done. Close this window and go back to Brento.'\n" % " ".join(shlex.quote(a) for a in args),
                          encoding="utf-8")
        script.chmod(0o700)
        subprocess.Popen(["open", "-a", "Terminal", str(script)])
        return {"opened": True, "command": shown}
    if settings.system() != "win32":
        return {"opened": False, "command": shown}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 1
    subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
    return {"opened": True, "command": shown}
