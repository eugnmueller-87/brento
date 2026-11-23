"""Whose Brento this is and what it reads. One JSON file in the owner's home folder, nothing in the repo.

A fresh install has no file, so the page opens the setup. Every source can be switched off. A source that is
off is not shown at all; a source that is on but cannot be read still shows N/A, never an empty success.
"""
import json
import os
import re
import shutil
import sys
import threading
from pathlib import Path

VERSION = 1
NAME = re.compile(r"^[^\x00-\x1f<>\"\\]{1,40}$")
GH_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
FIELD = re.compile(r"^[\w .\-äöüÄÖÜß]{1,40}$")
REPO = re.compile(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")
WORKFLOW = re.compile(r"^[A-Za-z0-9._-]{1,100}\.ya?ml$")

# What Brento can read. "path" is a note inside the vault, for sources whose notes have a fixed shape.
SOURCES = [
    {"id": "library", "label": "Obsidian notes", "group": "Obsidian", "vault": True, "new": True,
     "about": "Every note readable inside Brento, with topics, folders, tags, search and backlinks. Read only."},
    {"id": "tasks", "label": "Obsidian tasks with a date", "group": "Obsidian", "vault": True, "new": True,
     "about": "Open checkboxes with a due date become your deadlines: Tasks plugin (📅 2026-11-30), "
              "Dataview ([due:: 2026-11-30]) or @due(2026-11-30)."},
    {"id": "calendar", "label": "Calendar", "group": "Schedule", "new": True,
     "about": "Your calendar's private iCal link (Google, Outlook, iCloud). Meetings where other people "
              "expect you reach Home, with their join link."},
    {"id": "board", "label": "GitHub Project board", "group": "Schedule", "new": True,
     "about": "Cards in the lanes HIGH, MID and LOW. A HIGH card with a date inside a week reaches Home."},
    {"id": "ask", "label": "Ask box (Claude Code)", "group": "Assistant", "vault": True, "new": True,
     "about": "Questions about your notes, answered by the claude program on this computer under your own "
              "Claude login. Brento never sees or stores that login."},
    {"id": "openItems", "label": "Open matters table", "group": "Notes with a fixed shape", "vault": True, "new": False,
     "path": "Open matters.md",
     "about": "A table with the columns Matter, Next step, Owner, Due, Note. Rows where you are the owner "
              "and the date is near reach Home."},
    {"id": "pipeline", "label": "Job applications tracker", "group": "Notes with a fixed shape", "vault": True,
     "new": False, "path": "Applications.md",
     "about": "Sections Hot, Warm and Closed, one ### line per application: Company · Role · Status with dates."},
    {"id": "goals", "label": "Goals note", "group": "Notes with a fixed shape", "vault": True, "new": False,
     "path": "Goals.md", "about": "The first open checkbox under a heading that contains \"Right now\"."},
    {"id": "brief", "label": "Morning brief", "group": "Notes with a fixed shape", "vault": True, "new": False,
     "path": "outputs/morning-brief-latest.md",
     "about": "A daily note with a date in its frontmatter and a line \"THE ONE THING TODAY: ...\"."},
    {"id": "liveness", "label": "Background jobs report", "group": "Notes with a fixed shape", "vault": True,
     "new": False, "path": "outputs/liveness-latest.md",
     "about": "A report on which scheduled jobs went silent. The shape is the one liveness.py writes."},
]
SOURCE_IDS = [s["id"] for s in SOURCES]
BY_ID = {s["id"]: s for s in SOURCES}
# Pages that only make sense while their source is on.
PAGE_SOURCE = {"library": "library", "pipeline": "pipeline", "board": "board", "ask": "ask"}

_lock = threading.Lock()


def home():
    """An install from before the setup keeps its folder, ~/.leitstand. A new install gets ~/.brento."""
    forced = os.environ.get("BRENTO_HOME")
    if forced:
        return Path(forced).expanduser()
    old = Path.home() / ".leitstand"
    return old if old.is_dir() else Path.home() / ".brento"


def path():
    return home() / "brento.json"


def blank():
    """A new owner: the general sources on, the fixed-shape notes off, no vault yet."""
    return normalize({"sources": {s["id"]: {"on": s["new"]} for s in SOURCES}})


def legacy(vault):
    """Started with --vault and no settings file: everything as before the setup existed, tasks aside."""
    data = {"vault": str(vault), "privacy": "required",
            "sources": {sid: {"on": sid != "tasks"} for sid in SOURCE_IDS}}
    return normalize(data)


def clean_rel(value, default):
    rel = str(value or default).strip().replace("\\", "/").lstrip("/")
    parts = rel.split("/")
    if not rel.lower().endswith(".md") or ".." in parts or ":" in rel or len(rel) > 200:
        raise ValueError("A note path is relative to the vault and ends in .md: %s" % rel)
    return rel


def normalize(data):
    """Fills every gap with its default and refuses what could not be meant. Raises ValueError with a reason."""
    data = dict(data or {})
    out = {"version": VERSION}
    name = str(data.get("name") or "").strip()
    if name and not NAME.match(name):
        raise ValueError("Use a plain name of up to 40 characters.")
    out["name"] = name
    vault = str(data.get("vault") or "").strip()
    if vault:
        folder = Path(vault).expanduser()
        if not folder.is_dir():
            raise ValueError("That vault folder does not exist: %s" % vault)
        vault = str(folder.resolve())
    out["vault"] = vault
    out["privacy"] = "required" if data.get("privacy") == "required" else "optional"
    given = data.get("sources") or {}
    out["sources"] = {}
    for spec in SOURCES:
        sid = spec["id"]
        entry = given.get(sid) if isinstance(given.get(sid), dict) else {}
        row = {"on": bool(entry.get("on", spec["new"]))}
        if "path" in spec:
            row["path"] = clean_rel(entry.get("path"), spec["path"])
        # Without a vault there is nothing for a note source to read, so it cannot be on.
        if spec.get("vault") and not vault:
            row["on"] = False
        out["sources"][sid] = row
    board = data.get("board") if isinstance(data.get("board"), dict) else {}
    owner = str(board.get("owner") or "").strip()
    if owner and not GH_LOGIN.match(owner):
        raise ValueError("A GitHub login has letters, digits and dashes only.")
    try:
        number = int(board.get("number") or 0)
    except (TypeError, ValueError):
        raise ValueError("The project number is the number at the end of the project's address.")
    if number < 0 or number > 1000000:
        raise ValueError("The project number is the number at the end of the project's address.")
    fields = {}
    for key, default in (("statusField", "Status"), ("areaField", "Area"), ("doneField", ""), ("dueField", "")):
        value = str(board.get(key, default) or "").strip()
        if value and not FIELD.match(value):
            raise ValueError("A field name has letters, digits, spaces and . - _ only.")
        fields[key] = value
    out["board"] = dict({"owner": owner, "number": number,
                         "ownerType": "org" if board.get("ownerType") == "org" else "user"}, **fields)
    me = str(board.get("me") or "").strip()
    if me and not GH_LOGIN.match(me):
        raise ValueError("A GitHub login has letters, digits and dashes only.")
    out["board"]["me"] = me
    out["board"]["homeAreas"] = clean_areas(board.get("homeAreas"))
    aging = board.get("aging") if isinstance(board.get("aging"), dict) else None
    if aging:
        if not (REPO.match(str(aging.get("repo") or "")) and WORKFLOW.match(str(aging.get("workflow") or ""))):
            raise ValueError("board.aging needs repo (owner/name) and workflow (a .yml file).")
        out["board"]["aging"] = {"repo": aging["repo"], "workflow": aging["workflow"],
                                 "script": clean_script(aging.get("script"))}
    tasks = data.get("tasks") if isinstance(data.get("tasks"), dict) else {}
    out["tasks"] = {"home": "priority" if tasks.get("home") == "priority" else "all"}
    out["slack"] = clean_slack(data.get("slack"))
    return out


KINDS = ("pipeline", "goals", "brief", "board")


def clean_areas(value):
    """Board areas whose MID cards may fill Home, each with the picture its slides get."""
    value = value if isinstance(value, dict) else {}
    out = {}
    for area, kind in list(value.items())[:12]:
        if not FIELD.match(str(area)) or kind not in KINDS:
            raise ValueError("board.homeAreas maps an area name to one of: %s." % ", ".join(KINDS))
        out[str(area)] = kind
    return out


# The team file: what a team lead fixes once for everyone who installs from the team's copy of this repo.
# It holds no secret and nothing personal, so it can be committed: no vault, no links with keys, no names.
TEAM_FILE = "team.json"
CALENDARS = ("google", "outlook", "apple")


def clean_team(data):
    data = data if isinstance(data, dict) else {}
    unknown = set(data) - {"team", "board", "tools", "calendar", "slack"}
    if unknown:
        raise ValueError("team.json knows team, board, tools, calendar and slack, not: %s" % ", ".join(sorted(unknown)))
    name = str(data.get("team") or "").strip()
    if name and not NAME.match(name):
        raise ValueError("team.json: the team name is plain text of up to 40 characters.")
    board = normalize({"board": data.get("board") or {}})["board"]
    board.pop("me", None)
    tools = [str(t) for t in data.get("tools") or [] if re.match(r"^[a-z0-9-]{1,30}$", str(t))]
    calendar = data.get("calendar") if data.get("calendar") in CALENDARS else ""
    return {"team": name, "board": board, "tools": tools, "calendar": calendar,
            "slack": clean_slack(data.get("slack")) if data.get("slack") else None}


def load_team(folder):
    """The team file next to the code, or None. A broken file is said out loud, never silently ignored."""
    target = Path(folder) / TEAM_FILE
    if not target.is_file():
        return None
    try:
        return clean_team(json.loads(target.read_text(encoding="utf-8-sig")))
    except ValueError as exc:
        raise SystemExit("Brento did not start: %s cannot be used: %s" % (target, exc))


def save_team(folder, data):
    clean = clean_team(data)
    target = Path(folder) / TEAM_FILE
    target.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return clean


SLACK_SOURCES = ("calendar", "board", "tasks", "open-items", "pipeline")


def clean_slack(value):
    """What goes to Slack and when. The webhook link itself is a secret and lives in its own file, not here.
    Open matters and the job pipeline stay off by default: they are often private."""
    value = value if isinstance(value, dict) else {}
    digest = str(value.get("digest", "08:00") or "").strip()
    if digest and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", digest):
        raise ValueError("The summary time looks like 08:00.")
    try:
        remind = int(value.get("remind", 10))
    except (TypeError, ValueError):
        remind = 10
    chosen = value.get("sources")
    chosen = [s for s in chosen if s in SLACK_SOURCES] if isinstance(chosen, list) else ["calendar", "board", "tasks"]
    return {"digest": digest, "alerts": bool(value.get("alerts", True)), "remind": max(0, min(120, remind)), "sources": chosen}


# Where a Mac or Linux keeps programs that a login service's short PATH does not list: Homebrew, the native
# Claude Code installer, npm, and Brento's own folder for the GitHub CLI it downloads.
EXTRA_BIN = ("/opt/homebrew/bin", "/usr/local/bin", "~/.local/bin", "~/.claude/local", "~/.npm-global/bin", "~/bin")


def system():
    """The operating system, behind one name, so a test can play a Mac without changing sys for everyone."""
    return sys.platform


def find_exe(name):
    """A program on the PATH. On Windows the PATH is read fresh from the registry as well, so a program the setup
    just installed is found without restarting Brento. On a Mac or Linux the usual folders are searched too."""
    found = shutil.which(name)
    if found:
        return found
    if system() != "win32":
        folders = [str(home() / "bin")] + [os.path.expanduser(d) for d in EXTRA_BIN]
        return shutil.which(name, path=os.pathsep.join(folders))
    try:
        import winreg
        parts = []
        for root, key in ((winreg.HKEY_CURRENT_USER, "Environment"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
            try:
                with winreg.OpenKey(root, key) as handle:
                    parts.append(os.path.expandvars(winreg.QueryValueEx(handle, "Path")[0]))
            except OSError:
                continue
        return shutil.which(name, path=os.pathsep.join(parts)) if parts else None
    except ImportError:
        return None


def clean_script(value):
    rel = str(value or "").strip().replace("\\", "/").lstrip("/")
    if not rel.endswith(".py") or ".." in rel.split("/") or len(rel) > 200:
        raise ValueError("board.aging.script is a .py path inside the repo.")
    return rel


def load():
    """The saved settings, or None when there are none yet. A broken file is an error, never a silent default."""
    target = path()
    try:
        text = target.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None
    try:
        return normalize(json.loads(text))
    except ValueError as exc:
        raise SystemExit("Brento did not start: %s cannot be used: %s" % (target, exc))


def save(data):
    clean = normalize(data)
    with _lock:
        target = path()
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(temp), str(target))
    return clean


def on(profile, sid):
    return bool(((profile or {}).get("sources") or {}).get(sid, {}).get("on"))


def rel(profile, sid):
    return ((profile or {}).get("sources") or {}).get(sid, {}).get("path") or BY_ID[sid].get("path")


def obsidian_vaults():
    """The vaults Obsidian itself knows, from its own list. Only folders that exist."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    try:
        known = json.loads((base / "obsidian" / "obsidian.json").read_text(encoding="utf-8")).get("vaults") or {}
    except (OSError, ValueError, AttributeError):
        return []
    found = []
    for entry in known.values():
        folder = Path(str((entry or {}).get("path") or ""))
        if folder.is_dir():
            found.append({"path": str(folder), "name": folder.name, "open": bool(entry.get("open"))})
    return sorted(found, key=lambda v: (not v["open"], v["name"].lower()))


def public(profile):
    """What the setup page may see. Nothing secret lives in this file, but the page only gets what it shows."""
    return json.loads(json.dumps(profile or blank()))
