"""Read-only adapters over the vault. Nothing in this file writes anything.

Every adapter answers two questions: what does the source say, and how old is it.
A source that cannot be read reports "unknown", never an empty success. The code
ranks the cards; no model decides what comes first.
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from settings import find_exe
from tools import card_key

# Rows that match never reach the screen, so the page can be shown to someone. The words are private
# too, so they stay out of the code. Until load_private runs this matches everything and hides it all.
PRIVATE = re.compile("")


def load_private(path, required=True):
    """One word or phrase per line. A filter without words would hide nothing and say nothing, so the start stops
    when the owner asked for a list (privacy "required" in the setup). Returns the number of words."""
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        lines = []
    terms = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    if not terms and required:
        raise SystemExit("Brento did not start: the privacy list is missing or empty: %s" % path)
    global PRIVATE
    # No words, no filter: allowed only when the owner chose it. (?!) never matches anything.
    PRIVATE = re.compile("|".join(re.escape(term) for term in terms), re.I) if terms else re.compile(r"(?!)")
    return len(terms)


# Who "me" is in an Owner column: the setup's first name, plus the words a table uses for its owner.
ME = re.compile(r"\b(?:me|myself|ich)\b", re.I)


# The owner's GitHub login. On a team board, a card assigned to someone else is theirs, not mine.
ME_LOGIN = ""


def set_login(login):
    global ME_LOGIN
    ME_LOGIN = str(login or "").strip()


def set_owner(name):
    global ME
    words = ["me", "myself", "ich"] + [w for w in str(name or "").split()[:1] if len(w) > 1]
    ME = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(w) for w in words), re.I)


# Folders that hold no notes of their own: programs, trash, copies. Those with a dot in front count as well.
SKIP_DIRS = {"node_modules", "_private", "__pycache__"}
# More folders the owner wants left out, from the settings.
EXTRA_SKIP = set()


def set_skip(names):
    global EXTRA_SKIP
    EXTRA_SKIP = set(names or [])


def skipped(folder):
    return folder in SKIP_DIRS or folder in EXTRA_SKIP or folder.startswith(".")


def folder_problem(folder):
    """Why the notes folder cannot be read, in plain words, or ''. Walking through a folder says nothing about that:
    one that is gone or locked looks just like an empty one."""
    try:
        os.listdir(str(folder))
    except PermissionError:
        return "Brento may not read the notes folder"
    except OSError:
        return "the notes folder is not there"
    return ""


DATE_RE = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})(\.(\d{4}|\d{2})?)?(?!\d)")
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
NEWS_TITLE = re.compile(r"^NEWS\s+(\d{1,2})\.(\d{1,2})")
LANES = ("HIGH", "MID", "LOW")
# What really needs you. How long ahead a thing starts to count:
ALERT_DAYS = 7
# Slides on Home: everything above, then the next real to-dos until there are this many.
HOME_SLOTS = 10
# Which board cards come first, and the picture each area gets. Other areas fill a slide only from HIGH.
# Which board areas may fill Home with MID cards, and the picture each gets. Set per owner in the settings
# (board.homeAreas); empty means only HIGH cards and real deadlines reach Home.
AREA_KIND = {}
GOAL_TITLE = re.compile(r"^Q:\s")
SERIES_TITLE = re.compile(r"^(.+?)\s+(\d{1,2})/\d{1,2}:")
OPEN_PART = re.compile(r"\bOFFEN\b[^:]*:\s*(.+)", re.S)
# How far the day pages reach. The strip pages through this in weeks.
AGENDA_DAYS = 91
# The Today page's list of dates stays shorter than the day pages.
TODAY_EVENT_DAYS = 21
SENT_STATUS = re.compile(r"ABGESCHICKT|beworben|applied", re.I)
MUST_PREPARE = re.compile(r"interview|gespr(?:ä|ae|a)ch|\brunde\b|assessment|fallstudie|case study|pr(?:ä|ae|a)sentation|pitch|"
                          r"verhandlung|anwalt|gericht|notar", re.I)
REFERENCE_WORD = re.compile(r"(?:seit|stand|vom|ausgef\w*)\s*$", re.I)
REPORT_TITLE = re.compile(r"^Nachtaudit\s")
FIELDS = {"statusField": "Status", "areaField": "Area", "doneField": "", "dueField": ""}


def board_query(owner_type="user", fields=None):
    """The board read, with the owner's own field names. Names pass settings.FIELD, and json.dumps quotes them
    the way GraphQL reads a string, so no name can change the query."""
    f = dict(FIELDS, **(fields or {}))
    root = "organization" if owner_type == "org" else "user"

    def single(alias, name, extra=""):
        return '%s: fieldValueByName(name:%s){ ... on ProjectV2ItemFieldSingleSelectValue { name %s } }' % (
            alias, json.dumps(name), extra) if name else ""

    def day(alias, name):
        return '%s: fieldValueByName(name:%s){ ... on ProjectV2ItemFieldDateValue { date } }' % (
            alias, json.dumps(name)) if name else ""

    return ("query($owner:String!,$num:Int!,$after:String){ %s(login:$owner){ projectV2(number:$num){\n"
            "  items(first:100,after:$after){ totalCount pageInfo{hasNextPage endCursor} nodes{ id\n    %s\n    %s\n    %s\n    %s\n"
            "    content { ... on DraftIssue { title body createdAt %s } ... on Issue { title body url createdAt %s }\n"
            "              ... on PullRequest { title body url createdAt %s } } } } } } }") % (
        root, single("status", f["statusField"] or "Status", "updatedAt"), single("bereich", f["areaField"]),
        day("erledigt", f["doneField"]), day("due", f["dueField"]), WHO, WHO, WHO)


# Who a card is assigned to. A team shares one board; each member's Home shows their own cards.
WHO = "assignees(first:10){ nodes{ login } }"

PROBE_QUERY = """query($owner:String!,$num:Int!){ %s(login:$owner){ projectV2(number:$num){ title url
  fields(first:50){ nodes{ ... on ProjectV2FieldCommon { name dataType }
    ... on ProjectV2SingleSelectField { options { name } } } } } } }"""
# The tracker's own capitals for an application that is over, wherever the entry still sits.
ENDED = re.compile(r"\b(ABSAGE|GESCHLOSSEN|GESTRICHEN|BEENDET|ABGESAGT|REJECTED|CLOSED)\b")


def closest_year(day, month, today):
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if best is None or abs((candidate - today).days) < abs((best - today).days):
            best = candidate
    return best


def parse_dates(text, today):
    """German dates in the order they appear. "5.1" alone is a version number, not a date."""
    found = []
    for m in DATE_RE.finditer(text or ""):
        day, month, tail, year = m.group(1), m.group(2), m.group(3), m.group(4)
        if len(month) == 1 and not tail:
            continue
        try:
            if year:
                full = int(year) if len(year) == 4 else 2000 + int(year)
                found.append(date(full, int(month), int(day)))
            else:
                candidate = closest_year(int(day), int(month), today)
                if candidate:
                    found.append(candidate)
        except ValueError:
            continue
    return found


def clean_md(text):
    s = text or ""
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", lambda m: m.group(1).split("/")[-1], s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = s.replace("**", "").replace("__", "").replace("~~", "").replace("`", "")
    s = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", s)
    s = re.sub(r"^[^\w(„\"]+", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


def first_sentence(text, limit=110):
    """Split a long line into a headline and the rest."""
    text = text.strip()
    m = re.search(r"(?<=[\w)])[.!?:]\s+(?=[A-ZÄÖÜ\"„])", text)
    if m and m.start() <= limit:
        return text[:m.start()], text[m.end():].strip()
    if len(text) <= limit:
        return text, ""
    cut = text.rfind(" ", 0, limit)
    return text[:cut] + " …", text[cut + 1:]


def md_table(lines):
    """The first markdown table in lines, as dicts keyed by header."""
    rows, header = [], None
    for line in lines:
        if not line.lstrip().startswith("|"):
            if header:
                break
            continue
        flat = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"[[\1]]", line)
        cells = [c.strip() for c in flat.strip().strip("|").split("|")]
        if header is None:
            header = cells
        elif not all(re.fullmatch(r":?-+:?", c) for c in cells):
            rows.append(dict(zip(header, cells)))
    return rows


def frontmatter(text):
    m = re.match(r"﻿?---\n(.*?)\n---", text or "", re.S)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                key, value = line.split(":", 1)
                out[key.strip()] = value.strip().strip('"')
    return out


def iso_date(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def read(vault, rel):
    try:
        return (Path(vault) / rel).read_text(encoding="utf-8", errors="replace").lstrip("﻿")
    except OSError:
        return None


def git(vault, *args):
    exe = find_exe("git")
    if not exe:
        return ""
    try:
        out = subprocess.run([exe, "-C", str(vault)] + list(args), capture_output=True, timeout=15,
                             encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout if out.returncode == 0 else ""


def fetch_remote(vault):
    """For the refresh button: moves origin/master so a brief pushed from elsewhere shows. No file in the vault changes."""
    exe = find_exe("git")
    if not exe:
        return False
    try:
        out = subprocess.run([exe, "-C", str(vault), "fetch", "--quiet", "--no-auto-maintenance", "origin", "master"],
                             capture_output=True, timeout=30, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0


# How old the last good read of a calendar or a board may be. They are read again within minutes, so one this old has
# stopped answering or has not been read yet since the computer woke up.
LOST_AFTER = 3600


def lost(fetched, error):
    """'' while the last read is recent, else why nothing may be concluded from it."""
    if time.time() - fetched <= LOST_AFTER:
        return ""
    return "%s, last read %s" % (error, datetime.fromtimestamp(fetched).strftime("%d.%m. %H:%M")) if error else "still loading"


def source(sid, label, rel, as_of, max_age, today, note=""):
    if as_of is None:
        state, age = "unknown", None
    else:
        age = (today - as_of).days
        state = "fresh" if age <= max_age else "stale"
    return {"id": sid, "label": label, "path": rel, "asOf": as_of.isoformat() if as_of else None,
            "ageDays": age, "maxAge": max_age, "state": state, "note": note}


def off(sid, label):
    """A source the owner switched off. It never shows, so it can never look like a source that went quiet."""
    return {"id": sid, "label": label, "path": "", "asOf": None, "ageDays": None, "maxAge": 0, "state": "off", "note": "off"}


# The open matters table in English or German. The first name found for a column wins.
COLUMNS = {"name": ("Matter", "Vorgang"), "next": ("Next step", "Nächster Schritt"), "owner": ("Owner", "Wer ist dran"),
           "due": ("Due", "Frist"), "note": ("Note", "Akte")}


def column(row, key):
    return next((row[name] for name in COLUMNS[key] if name in row), "")


def read_open_items(vault, today, rel="Open matters.md"):
    text = read(vault, rel)
    if text is None:
        return {"items": [], "hidden": 0}, source("open-items", "Open matters", rel, None, 7, today, "file not found")
    stand = re.search(r"(?:Stand|As of) (\d{1,2}\.\d{1,2}\.\d{4})", text)
    as_of = parse_dates(stand.group(1), today)[0] if stand else None
    items, hidden = [], 0
    for row in md_table(text.splitlines()):
        if PRIVATE.search(" ".join(row.values())):
            hidden += 1
            continue
        dates = parse_dates(column(row, "due"), today)
        due = dates[0] if dates else None
        owner = clean_md(column(row, "owner"))
        items.append({
            "name": clean_md(column(row, "name")),
            "next": clean_md(column(row, "next")),
            "owner": owner,
            "mine": bool(ME.search(owner)),
            "due": due.isoformat() if due else None,
            "daysLeft": (due - today).days if due else None,
            "note": clean_md(column(row, "note")),
        })
    return {"items": items, "hidden": hidden}, source("open-items", "Open matters", rel, as_of, 7, today)


def read_pipeline(vault, today, rel="Applications.md"):
    text = read(vault, rel)
    empty = {"hot": [], "warm": [], "ended": [], "closed": 0, "closedFirms": [], "lastSent": None, "daysSince": None, "hidden": 0}
    if text is None:
        return empty, source("pipeline", "Pipeline", rel, None, 7, today, "file not found")
    fm = frontmatter(text)
    as_of = iso_date(fm.get("updated", "")) or iso_date(git(vault, "log", "-1", "--format=%cs", "--", rel).strip())
    out = dict(empty, hot=[], warm=[], ended=[], closedFirms=[])
    sent = []
    for section in re.split(r"^## ", text, flags=re.M)[1:]:
        head = section.split("\n", 1)[0]
        bucket = "hot" if "Hot" in head else "warm" if "Warm" in head else "closed" if "Closed" in head else None
        if bucket is None:
            continue
        for m in re.finditer(r"^### (.+)$", section, re.M):
            raw = m.group(1)
            if PRIVATE.search(raw):
                out["hidden"] += 1
                continue
            # Older entries in the tracker separate their parts with a dash, newer ones with a dot.
            parts = [p.strip() for p in re.split(r"\s+[·—]\s+", raw)]
            status = clean_md(" · ".join(parts[2:]))
            dates = parse_dates(status, today)
            ended = bool(ENDED.search(status))
            # "ABSAGE 01.10. (beworben 07.08.)" is a rejection date, not a day something was sent.
            if not ended and SENT_STATUS.search(status) and dates:
                sent.append(max(dates))
            target = re.search(r"\[\[([^\]|#]+)", parts[0])
            link = target.group(1).split("/")[-1] if target else clean_md(parts[0])
            if bucket == "closed":
                out["closed"] += 1
                out["closedFirms"].append(link)
                continue
            out["ended" if ended else bucket].append({
                "link": link,
                "firm": clean_md(parts[0]),
                "role": clean_md(parts[1]) if len(parts) > 1 else "",
                "status": status,
                "date": max(dates).isoformat() if dates else None,
            })
    added = parse_dates(fm.get("last_added", ""), today)
    sent += added
    past = [d for d in sent if d <= today]
    if past:
        out["lastSent"] = max(past).isoformat()
        out["daysSince"] = (today - max(past)).days
    return out, source("pipeline", "Pipeline", rel, as_of, 7, today)


def read_goals(vault, today, rel="Goals.md"):
    text = read(vault, rel)
    if text is None:
        return {"now": ""}, source("goals", "Goals", rel, None, 14, today, "file not found")
    as_of = iso_date(git(vault, "log", "-1", "--format=%cs", "--", rel).strip())
    now = ""
    m = re.search(r"^## [^\n]*Right now[^\n]*$(.*?)^## ", text, re.M | re.S)
    if m:
        task = re.search(r"^- \[ \] (.+)$", m.group(1), re.M)
        if task:
            now = clean_md(task.group(1))
    return {"now": now}, source("goals", "Goals", rel, as_of, 14, today)


def newest_brief(vault, rel="outputs/morning-brief-latest.md"):
    """The brief job pushes from elsewhere, so the newest copy can be on the remote branch."""
    best, best_date = None, None
    for copy in (read(vault, rel), git(vault, "show", "origin/master:" + rel)):
        fm = frontmatter(copy or "")
        when = iso_date(fm.get("date") or fm.get("created") or "")
        if when and (best_date is None or when > best_date):
            best, best_date = copy, when
    return best, best_date


def read_brief(vault, today, rel="outputs/morning-brief-latest.md"):
    best, best_date = newest_brief(vault, rel)
    if best is None:
        return {"oneThing": ""}, source("brief", "Morning brief", rel, None, 1, today, "no brief found")
    m = re.search(r"THE ONE THING TODAY(?::\*\*)?\s*(.+)", best)
    line = clean_md(m.group(1)) if m else ""
    hidden = bool(PRIVATE.search(line))
    return {"oneThing": "" if hidden else line, "hidden": hidden}, source("brief", "Morning brief", rel, best_date, 1, today)


def read_liveness(vault, today, rel="outputs/liveness-latest.md"):
    text = read(vault, rel)
    empty = {"alive": None, "still": None, "resting": None, "stillRows": [], "aliveRows": []}
    if text is None:
        return empty, source("liveness", "Brain health", rel, None, 2, today, "file not found")
    stamp = re.search(r"Lebenszeichen - (\d{4}-\d{2}-\d{2})", text)
    counts = re.search(r"(\d+) lebt, (\d+) still, (\d+) ruht", text)
    out = dict(empty, stillRows=[], aliveRows=[])
    if counts:
        out.update(alive=int(counts.group(1)), still=int(counts.group(2)), resting=int(counts.group(3)))
    for section in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = section.splitlines()
        if lines[0].strip() == "Still":
            for row in md_table(lines[1:]):
                out["stillRows"].append({"name": clean_md(row.get("Wachposten")), "verdict": clean_md(row.get("Urteil")),
                                         "age": row.get("Alter", ""), "limit": row.get("Frist", ""),
                                         "proof": clean_md(row.get("Beleg")),
                                         "why": clean_md(row.get("Warum es zaehlt"))})
        elif lines[0].strip() == "Lebt":
            for row in md_table(lines[1:]):
                out["aliveRows"].append({"name": clean_md(row.get("Wachposten")), "age": row.get("Alter", "")})
    return out, source("liveness", "Brain health", rel, iso_date(stamp.group(1)) if stamp else None, 2, today)


# Obsidian tasks: an open checkbox ("[ ]", or "[/]" for started) with a date. Three common ways to write the date.
TASK_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([ /])\]\s+(.+)$")
TASK_DUE = re.compile(r"📅\s*(\d{4}-\d{2}-\d{2})|\[due::\s*(\d{4}-\d{2}-\d{2})\s*\]|\(due::\s*(\d{4}-\d{2}-\d{2})\s*\)"
                      r"|@due\((\d{4}-\d{2}-\d{2})\)")
TASK_SCHEDULED = re.compile(r"⏳\s*(\d{4}-\d{2}-\d{2})|\[scheduled::\s*(\d{4}-\d{2}-\d{2})\s*\]")
TASK_PRIORITY = (("🔺", "highest"), ("⏫", "high"), ("🔼", "medium"), ("🔽", "low"), ("⏬", "lowest"))
# A recurrence ("🔁 every month") runs to the next field. Every other field is one word after its sign.
TASK_NOISE = re.compile(r"🔁[^📅⏳🛫➕✅❌🆔⛔🏁🔺⏫🔼🔽⏬\[\(^#]*|(?:📅|⏳|🛫|➕|✅|❌|🆔|⛔|🏁)\s*[^\s📅⏳🛫➕✅❌🔁🆔⛔🏁#]*|[🔺⏫🔼🔽⏬]"
                        r"|\[\w+::[^\]]*\]|\(\w+::[^)]*\)|@due\([^)]*\)|\^[\w-]+\s*$|#task\b")
TASK_FILE_LIMIT = 512 * 1024


def task_from(line, today):
    """One line as a task, or None. Only open tasks with a due or scheduled date count."""
    m = TASK_LINE.match(line)
    if not m:
        return None
    text = m.group(2)
    due = TASK_DUE.search(text)
    kind = "due"
    if not due:
        due, kind = TASK_SCHEDULED.search(text), "scheduled"
    if not due:
        return None
    when = iso_date(next(g for g in due.groups() if g))
    if when is None:
        return None
    priority = next((name for mark, name in TASK_PRIORITY if mark in text), "")
    words = re.search(r"\[priority::\s*(\w+)\s*\]", text)
    if words and not priority:
        priority = words.group(1).lower()
    title = clean_md(re.sub(r"\s{2,}", " ", TASK_NOISE.sub(" ", text))).strip(" -·")
    return {"title": title or "Untitled task", "due": when.isoformat(), "daysLeft": (when - today).days, "kind": kind,
            "priority": priority, "started": m.group(1) == "/"}


class TaskIndex:
    """Every dated open task in the vault. Each file is read again only when it changed, so a large vault stays quick."""

    def __init__(self, vault, ttl=60):
        self.vault, self.ttl = Path(vault), ttl
        self.files, self.walked, self.found = {}, 0.0, []
        # Notes that could not be opened on the last round, for example ones a cloud folder has not brought here yet.
        self.unread = 0
        self.lock = threading.Lock()

    def scan(self, today=None):
        with self.lock:
            if self.walked and time.time() - self.walked < self.ttl:
                return self.found
            # Raises when the folder is gone or locked, so the caller says N/A and never "no tasks".
            os.listdir(str(self.vault))
            seen, out, unread = {}, [], 0
            for folder, dirs, files in os.walk(self.vault):
                dirs[:] = [d for d in dirs if not skipped(d) and not PRIVATE.search(d)]
                for name in files:
                    if not name.endswith(".md") or PRIVATE.search(name):
                        continue
                    full = Path(folder) / name
                    try:
                        stat = full.stat()
                    except OSError:
                        continue
                    rel = full.relative_to(self.vault).as_posix()
                    hit = self.files.get(rel)
                    if not hit or hit[0] != stat.st_mtime:
                        lines = []
                        if stat.st_size <= TASK_FILE_LIMIT:
                            try:
                                text = full.read_text(encoding="utf-8", errors="replace")
                            except OSError:
                                # Tried again on the next round. What was known about it stays until then.
                                unread += 1
                                for n, line in hit[1] if hit else ():
                                    out.append((rel, n, line))
                                if hit:
                                    seen[rel] = hit
                                continue
                            # Cheap first test: a file without a checkbox has no task.
                            if "[ ]" in text or "[/]" in text:
                                lines = [(n, line) for n, line in enumerate(text.splitlines(), 1)
                                         if TASK_LINE.match(line) and (TASK_DUE.search(line) or TASK_SCHEDULED.search(line))]
                        hit = (stat.st_mtime, lines)
                    seen[rel] = hit
                    for n, line in hit[1]:
                        out.append((rel, n, line))
            self.files, self.walked, self.found, self.unread = seen, time.time(), out, unread
            return out


def read_tasks(index, today):
    """Dated open tasks from the vault, soonest first. Rows on the privacy list are counted, never shown."""
    if index is None:
        return {"items": [], "hidden": 0}, source("tasks", "Obsidian tasks", "", None, 1, today, "no vault chosen")
    items, hidden = [], 0
    try:
        found = index.scan(today)
    except OSError as exc:
        why = folder_problem(index.vault) or str(exc)[:120]
        return {"items": [], "hidden": 0}, source("tasks", "Obsidian tasks", "", None, 1, today, why)
    for rel, n, line in found:
        task = task_from(line, today)
        if task is None:
            continue
        if PRIVATE.search(task["title"]):
            hidden += 1
            continue
        task.update(path=rel, line=n, id="task-%s-%d" % (rel, n))
        task["daysLeft"] = (iso_date(task["due"]) - today).days
        items.append(task)
    items.sort(key=lambda t: (t["due"], t["title"].lower()))
    note = ("%d note%s could not be read" % (index.unread, "" if index.unread == 1 else "s")) if index.unread else ""
    return {"items": items, "hidden": hidden}, source("tasks", "Obsidian tasks", "Vault checkboxes", None if note else today, 1, today, note)


class Board:
    """The owner's GitHub Project, read in the background so a slow gh call never blocks the page.

    aging names the repo whose workflow ages the cards ({"repo", "workflow", "script"}). Without it the board
    page shows no aging rules, which is the truth for a board that nothing ages."""

    def __init__(self, owner, number, ttl=300, owner_type="user", fields=None, aging=None):
        self.owner, self.number, self.ttl = owner, number, ttl
        self.owner_type, self.fields, self.aging = owner_type, dict(FIELDS, **(fields or {})), aging
        self.query = board_query(owner_type, self.fields)
        self.url = "https://github.com/%s/%s/projects/%s" % ("orgs" if owner_type == "org" else "users", owner, number)
        self.raw, self.fetched, self.error = None, 0.0, ""
        self.job, self.aging_source = None, ""
        self.repos, self.health = {}, {}
        self.watch = set()
        self.busy = False
        self.lock = threading.Lock()

    def last_pushes(self, gh):
        try:
            run = subprocess.run([gh, "repo", "list", self.owner, "--limit", "200", "--json", "name,pushedAt"],
                                 capture_output=True, timeout=30, encoding="utf-8", errors="replace",
                                 creationflags=NO_WINDOW)
            rows = json.loads(run.stdout) if run.returncode == 0 else []
        except (OSError, ValueError, subprocess.SubprocessError):
            return self.repos
        return {r["name"]: (r.get("pushedAt") or "")[:10] for r in rows}

    def pushed_job(self, gh):
        """The job as GitHub runs it. A merge shows up here within minutes, with no fetch on this disk."""
        if not self.aging:
            return ""
        try:
            run = subprocess.run([gh, "api", "repos/%s/contents/%s" % (self.aging["repo"], self.aging["script"]),
                                  "-H", "Accept: application/vnd.github.raw"], capture_output=True, timeout=30,
                                 encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            return self.aging_source
        return run.stdout if run.returncode == 0 else self.aging_source

    @staticmethod
    def answers(url):
        try:
            with urllib.request.urlopen(url, timeout=8) as res:
                return res.status < 400
        except (OSError, ValueError):
            return False

    def last_job(self, gh):
        """Did the daily aging job run? GitHub knows, because that is where it runs."""
        if not self.aging:
            return None
        try:
            run = subprocess.run([gh, "run", "list", "-R", self.aging["repo"], "--workflow", self.aging["workflow"], "--limit", "1",
                                  "--json", "conclusion,createdAt"], capture_output=True, timeout=30,
                                 encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
            runs = json.loads(run.stdout) if run.returncode == 0 else []
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        return {"conclusion": runs[0].get("conclusion"), "date": (runs[0].get("createdAt") or "")[:10]} if runs else None

    def fetch(self):
        try:
            gh = find_exe("gh")
            if not gh:
                raise RuntimeError("gh is not installed here")
            items, cursor, total = [], None, 0
            for _ in range(30):
                cmd = [gh, "api", "graphql", "-f", "query=" + self.query, "-f", "owner=" + self.owner,
                       "-F", "num=%s" % self.number]
                run = subprocess.run(cmd + (["-f", "after=" + cursor] if cursor else []), capture_output=True,
                                     timeout=60, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
                if run.returncode != 0:
                    raise RuntimeError((run.stderr or "gh failed").strip()[:200])
                root = json.loads(run.stdout)["data"]["organization" if self.owner_type == "org" else "user"]
                if not root or not root.get("projectV2"):
                    raise RuntimeError("No project %s for %s" % (self.number, self.owner))
                page = root["projectV2"]["items"]
                total = page["totalCount"]
                for n in page["nodes"]:
                    status, content = n.get("status") or {}, n.get("content") or {}
                    items.append({"id": n["id"], "title": content.get("title") or "", "status": status.get("name"),
                                  "statusSet": status.get("updatedAt"), "createdAt": content.get("createdAt"),
                                  "bereich": (n.get("bereich") or {}).get("name"),
                                  "erledigt am": (n.get("erledigt") or {}).get("date"),
                                  "dueField": (n.get("due") or {}).get("date"), "content": content,
                                  "assignees": [a["login"] for a in ((content.get("assignees") or {}).get("nodes") or []) if a]})
                if not page["pageInfo"]["hasNextPage"]:
                    break
                cursor = page["pageInfo"]["endCursor"]
            # A partly read board looks like a board with fewer cards, and nothing would say so.
            if len(items) != total:
                raise RuntimeError("Board reports %d cards, read %d" % (total, len(items)))
            self.raw, self.fetched, self.error = items, time.time(), ""
            self.job = self.last_job(gh)
            self.aging_source = self.pushed_job(gh)
            self.repos = self.last_pushes(gh)
            self.health = {url: self.answers(url) for url in self.watch}
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
            self.error = str(exc)
        finally:
            self.busy = False

    def snapshot(self, wait=False):
        with self.lock:
            due = time.time() - self.fetched > self.ttl and not self.busy
            if due:
                self.busy = True
        if due:
            worker = threading.Thread(target=self.fetch, daemon=True)
            worker.start()
            if wait or self.raw is None:
                worker.join(wait and 70 or 12)
        return self.raw, self.fetched, self.error

    def refresh(self, timeout=70):
        """For the refresh button: read now, whatever the age of the last read. Returns the error, if any."""
        with self.lock:
            running, self.busy = self.busy, True
        if not running:
            self.fetch()
            return self.error
        # A read is already under way, and that one is as fresh as a second would be.
        end = time.time() + timeout
        while self.busy and time.time() < end:
            time.sleep(0.1)
        return self.error


def gh_status():
    """For the setup: is gh here, signed in, and allowed to read projects? Each answer with the command that fixes it."""
    gh = find_exe("gh")
    if not gh:
        return {"ready": False, "reason": "The GitHub program is not installed yet."}
    try:
        run = subprocess.run([gh, "auth", "status"], capture_output=True, timeout=20, encoding="utf-8", errors="replace",
                             creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ready": False, "reason": "Could not ask gh: %s" % exc}
    text = (run.stdout or "") + (run.stderr or "")
    if run.returncode != 0 or "Logged in" not in text:
        return {"ready": False, "reason": "GitHub is not signed in yet."}
    login = re.search(r"account (\S+)", text)
    scopes = re.search(r"Token scopes:\s*(.+)", text)
    found = {s.strip(" '\"") for s in scopes.group(1).split(",")} if scopes else set()
    if scopes and "project" not in found and "read:project" not in found:
        return {"ready": False, "login": login.group(1) if login else "",
                "reason": "GitHub does not let Brento read your boards yet."}
    return {"ready": True, "login": login.group(1) if login else "", "reason": ""}


def probe_board(owner, number, owner_type="user"):
    """The project's title and its fields, so the setup can offer the real field names instead of asking for them."""
    gh = find_exe("gh")
    if not gh:
        return {"error": "GitHub CLI is not installed."}
    root = "organization" if owner_type == "org" else "user"
    try:
        run = subprocess.run([gh, "api", "graphql", "-f", "query=" + PROBE_QUERY % root, "-f", "owner=" + owner,
                              "-F", "num=%d" % int(number)], capture_output=True, timeout=30, encoding="utf-8",
                             errors="replace", creationflags=NO_WINDOW)
        node = ((json.loads(run.stdout or "{}").get("data") or {}).get(root) or {}).get("projectV2")
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        return {"error": "Could not read the project: %s" % exc}
    if not node:
        return {"error": "No project %s for %s. Check the number at the end of its address, and user or organization."
                         % (number, owner)}
    fields = [{"name": f.get("name"), "type": f.get("dataType"), "options": [o["name"] for o in f.get("options") or []]}
              for f in (node.get("fields") or {}).get("nodes") or [] if f.get("name")]
    return {"title": node.get("title"), "url": node.get("url"), "fields": fields}


def aging_rules(vault, pushed="", script=None):
    """The limits come from the job's own file, so this page cannot disagree with what the job does.

    The job runs on GitHub from the pushed branch, so that copy counts before the one on this disk.
    Without a script there are no rules, and the board page says nothing ages the cards.
    """
    if not script and not pushed:
        return None
    text = pushed or (script and (git(vault, "show", "origin/master:" + script) or read(vault, script))) or ""
    found = dict(re.findall(r"^(NEWS_MAX_TAGE|OLD_MAX_TAGE|DONE_MAX_TAGE|DATUM_MAX_TAGE) = (\d+)", text, re.M))
    if not {"NEWS_MAX_TAGE", "OLD_MAX_TAGE", "DONE_MAX_TAGE"} <= set(found):
        return None
    rules = {"news": int(found["NEWS_MAX_TAGE"]), "old": int(found["OLD_MAX_TAGE"]), "done": int(found["DONE_MAX_TAGE"])}
    if "DATUM_MAX_TAGE" in found:
        rules["passed"] = int(found["DATUM_MAX_TAGE"])
    return rules


def deadline_of(title, created, status_set, today):
    """The date on this card that really is a deadline, else None. Mirrors frist_im_titel() in the job.

    A date older than the card itself describes the past ("Stand 17.06."), and a status set after
    the date means someone placed the card there on purpose. Neither is a missed deadline.
    """
    dates = []
    for m in DATE_RE.finditer(title):
        if not REFERENCE_WORD.search(title[:m.start()]):
            dates += parse_dates(m.group(0), created or today)
    if not dates:
        return None
    due = max(dates)
    if REPORT_TITLE.match(title):
        return due
    if (created and due <= created) or (status_set and status_set > due):
        return None
    return due


def news_date(title, today):
    m = NEWS_TITLE.match(title.strip())
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    try:
        return date(today.year if month <= today.month else today.year - 1, month, day)
    except ValueError:
        return None


def next_step(status, area, title, stamped, rules, today, due=None):
    """Where the aging job sends this card next and from which day. Mirrors main() in board_aging.py.

    Returns (target, iso date). A date of None with a target means the job stamps the card first
    and its clock starts then. (None, None) means no rule applies: the card stays until someone moves it.
    """
    if not rules:
        return None, None

    def after(start, limit):
        # The job compares with "older than", so the first eligible day is one past the limit.
        return (start + timedelta(days=limit + 1)).isoformat() if start else None

    if area == "News" and status not in ("Old", "Archive"):
        start = news_date(title, today)
        return ("Old", after(start, rules["news"])) if start else (None, None)
    if area == "News" and status == "Old":
        start = news_date(title, today)
        return ("Archive", after(start, rules["old"])) if start else (None, None)
    if status == "Done":
        return "Archive", after(iso_date(stamped or ""), rules["done"])
    if status == "Old":
        return "Archive", after(iso_date(stamped or ""), rules["old"])
    if due and "passed" in rules and status in LANES + ("No status", "NEW"):
        return "Old", after(due, rules["passed"])
    return None, None


def read_board(board, today, rules=None):
    raw, fetched, error = board.snapshot()
    rel = "GitHub Project #%s" % board.number
    aging = {"rules": rules, "job": getattr(board, "job", None), "on": bool(getattr(board, "aging", None))}
    empty = {"items": [], "archived": [], "counts": {}, "bereiche": [], "passed": 0, "hidden": 0, "error": error, "aging": aging}
    if raw is None:
        return empty, source("board", "Board", rel, None, 1, today, error or "still loading")
    items, archived, counts, hidden = [], [], {}, 0
    for item in raw:
        status = item.get("status") or "No status"
        counts[status] = counts.get(status, 0) + 1
        title = item.get("title") or ""
        content = item.get("content") or {}
        body = content.get("body") or ""
        if PRIVATE.search(title + " " + body):
            hidden += 1
            continue
        area = item.get("bereich") or "No area"
        # A date field says what it means. A date in the title only counts when it reads as a deadline.
        due = iso_date(item.get("dueField") or "") or deadline_of(title, iso_date(item.get("createdAt") or ""),
                                                                   iso_date(item.get("statusSet") or ""), today)
        target, on = next_step(status, area, title, item.get("erledigt am"), rules, today, due)
        who = item.get("assignees") or []
        entry = {"id": item.get("id") or "", "title": title, "status": status, "bereich": area, "body": body[:700],
                 "assignees": who, "mine": not ME_LOGIN or not who or ME_LOGIN.lower() in {w.lower() for w in who},
                 "url": content.get("url") or "", "agesTo": target, "agesOn": on, "due": due.isoformat() if due else None,
                 "passed": status in LANES and due is not None and due < today}
        (archived if status == "Archive" else items).append(entry)
    out = {"items": items, "archived": archived, "counts": counts,
           "bereiche": sorted({i["bereich"] for i in items + archived}),
           "passed": sum(1 for i in items if i["passed"]), "hidden": hidden, "error": error, "aging": aging}
    gone = lost(fetched, error)
    return out, source("board", "Board", rel, None if gone else date.fromtimestamp(fetched), 1, today, gone or error)


FINISHED = ("Done", "Old", "Archive")
_note_dates = {}


def note_date(vault, rel):
    """When a note last changed in git. Cached, because a page holds many of these."""
    key = (str(vault), rel)
    hit = _note_dates.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    value = iso_date(git(vault, "log", "-1", "--format=%cs", "--", rel).strip())
    if value is None:
        # Never committed, so git knows nothing. The file's own time is the only evidence left.
        try:
            value = date.fromtimestamp((Path(vault) / rel).stat().st_mtime)
        except OSError:
            value = None
    _note_dates[key] = (time.time(), value)
    return value


def build_projects(vault, registry, board_data, open_items, pipeline, board, today, tracker_date=None):
    """One row per project, measured from the board, the repo and the note. Nothing is estimated.

    A project without cards has no progress figure, and that shows as N/A. Cards that no project
    claims are counted, so a gap in the list stays visible.
    """
    cards = board_data["items"] + board_data["archived"]
    repos = getattr(board, "repos", {}) or {}
    health = getattr(board, "health", {}) or {}
    claimed, rows = set(), []
    for p in registry:
        pattern = re.compile(p["match"], re.I) if p.get("match") else None
        idx = [n for n, c in enumerate(cards)
               if (p.get("bereich") and c["bereich"] == p["bereich"]) or (pattern and pattern.search(c["title"]))]
        claimed.update(idx)
        open_idx = [n for n in idx if cards[n]["status"] not in FINISHED]
        done_idx = [n for n in idx if cards[n]["status"] in FINISHED]
        matters = open_items["items"] if p.get("matters") else []
        dates = [d for n in open_idx for d in parse_dates(cards[n]["title"], today) if d >= today]
        dates += [iso_date(m["due"]) for m in matters if m["due"] and iso_date(m["due"]) >= today]
        note = p.get("note") if p.get("note") and os.path.isfile(str(Path(vault) / p["note"])) else None
        pushed = iso_date(repos.get(p.get("repo"), "") or "")
        changed = pushed or (note_date(vault, note) if note else None)
        if p.get("pipeline") and tracker_date and (changed is None or tracker_date > changed):
            changed = tracker_date
        high = sum(1 for n in open_idx if cards[n]["status"] == "HIGH")
        if p.get("health") and health.get(p["health"]) is False:
            state, why = "down", "%s does not answer" % p["health"]
        elif p.get("state"):
            state, why = p["state"], p.get("why", "")
        elif changed and (today - changed).days <= 14 or high:
            state, why = "active", ""
        elif changed or open_idx:
            state, why = "quiet", "no change in 14 days and no HIGH card"
        else:
            state, why = "unknown", "no repo, no note and no cards to measure"
        detail = p.get("area") or p.get("bereich") or ""
        if p.get("pipeline"):
            detail = "%d hot, %d warm" % (len(pipeline["hot"]), len(pipeline["warm"]))
        total = len(open_idx) + len(done_idx)
        rows.append({"id": p["id"], "name": p["name"], "detail": detail, "state": state, "stateWhy": why,
                     "done": len(done_idx), "total": total, "high": high,
                     "next": min(dates).isoformat() if dates else None,
                     "changed": changed.isoformat() if changed else None,
                     "note": note, "repo": p.get("repo") if p.get("repo") in repos else None, "tool": p.get("tool"),
                     "openIdx": open_idx, "doneIdx": done_idx, "matters": [m["name"] for m in matters]})
    unclaimed = [n for n, c in enumerate(cards) if n not in claimed and c["status"] not in FINISHED]
    return {"rows": rows, "cards": cards, "unclaimedIdx": unclaimed}


def read_notes(vault):
    """Note titles for the jump palette. Private folders and generated ones stay out."""
    notes = []
    root = Path(vault)
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not skipped(d) and not PRIVATE.search(d)]
        for name in files:
            if name.endswith(".md") and not PRIVATE.search(name):
                rel = (Path(folder) / name).relative_to(root).as_posix()
                notes.append({"title": name[:-3], "path": rel})
    notes.sort(key=lambda n: n["title"].lower())
    return notes


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def weekday_label(iso):
    d = iso_date(iso)
    return "%s %s" % (WEEKDAYS[d.weekday()], d.strftime("%d.%m."))


def age_words(src):
    if src["state"] == "unknown":
        return "age unknown"
    return "today" if src["ageDays"] == 0 else "%dd old" % src["ageDays"]


def finished_in_tracker(line, pipeline):
    """The application a goal line names, if the tracker says it is over. A live entry for the same firm wins."""
    live = {e["link"].lower() for e in pipeline["hot"] + pipeline["warm"]}
    ended = [(e["link"], e["status"]) for e in pipeline.get("ended", [])]
    ended += [(name, "") for name in pipeline.get("closedFirms", [])]
    for name, status in ended:
        if name.lower() not in live and re.search(r"\b%s\b" % re.escape(name), line, re.I):
            return name, status
    return None


def build_cards(data, sources_by_id):
    """Fixed rules, highest score first. Each card says why it is on the screen."""
    cards = []

    def add(cid, kind, score, eyebrow, title, body, why, src_id, route=None, note=None, heat=0.2, tag=""):
        src = sources_by_id[src_id]
        fog = {"fresh": 0.08, "stale": 0.7, "unknown": 1.0}[src["state"]]
        cards.append({"id": cid, "kind": kind, "score": score, "eyebrow": eyebrow, "tag": tag, "title": title,
                      "body": body, "why": why, "source": src["label"], "sourceState": src["state"],
                      "sourceAge": age_words(src), "route": route, "note": note, "heat": round(heat, 2),
                      "fog": fog})

    brief = data["brief"]
    brief_taken = False
    for item in data["open"]["items"]:
        days = item["daysLeft"]
        if days is None or days > 14:
            continue
        if days < 0:
            why = "Deadline passed %d days ago." % -days
        elif item["mine"]:
            why = "Due in %d days and the next step is yours." % days
        else:
            why = "Not yours yet. It becomes yours if nothing arrives before the deadline."
        # Two sources naming the same thing are one card with a stronger reason.
        if item["mine"] and sources_by_id["brief"]["state"] == "fresh" and brief.get("oneThing"):
            if re.split(r"[:\s]", item["name"])[0].lower() in brief["oneThing"].lower():
                why += " Today's morning brief says the same."
                brief_taken = True
        add("open-" + item["name"], "deadline", (1000 if item["mine"] else 600) - days * 10,
            "Your move" if item["mine"] else "Waiting on " + item["owner"], item["name"], item["next"], why,
            "open-items", note=item.get("notePath"), heat=clamp(1 - days / 14.0), tag="due " + weekday_label(item["due"]))

    # A dated task weighs like an open matter that is yours: it is your own deadline.
    for task in (data.get("tasks") or {}).get("items", []):
        days = task["daysLeft"]
        if task["kind"] != "due" or days > 14:
            continue
        why = ("Your task was due %d days ago." % -days) if days < 0 else "Your own deadline, %s." % in_days(days)
        add(task["id"], "deadline", 1000 - days * 10, "Your task", task["title"], "From " + Path(task["path"]).stem, why,
            "tasks", note=task.get("notePath"), heat=clamp(1 - days / 14.0), tag="due " + weekday_label(task["due"]))

    if brief.get("oneThing") and not brief_taken:
        head, rest = first_sentence(brief["oneThing"])
        fresh = sources_by_id["brief"]["state"] == "fresh"
        add("brief", "brief", 700 if fresh else 120, "Morning brief", head, rest,
            "The morning job's one thing for today." if fresh else "Older than a day. Read it as history, not as today.",
            "brief")

    pipe = data["pipeline"]
    if pipe["hot"] or pipe["warm"]:
        newest = (pipe["hot"] or pipe["warm"])[0]
        since = pipe["daysSince"]
        sent = "" if since is None else " Last application went out %s." % (
            "today" if since == 0 else "1 day ago" if since == 1 else "%d days ago" % since)
        role = (", " + newest["role"]) if newest["role"] else ""
        add("pipeline", "pipeline", 650 if (since or 0) > 7 else 400, "Job hunt",
            "%d hot, %d warm in the pipeline" % (len(pipe["hot"]), len(pipe["warm"])),
            "Newest: %s%s.%s%s" % (newest["firm"], role, sent, " %d finished applications still sit under Hot or Warm." % len(pipe["ended"]) if pipe["ended"] else ""),
            "A week without a new application is the gap to watch." if (since or 0) <= 7
            else "No new application for more than a week.", "pipeline", route="pipeline")

    board = data["board"]
    if board["items"]:
        high = [i for i in board["items"] if i["status"] == "HIGH"]
        dead = [i for i in high if i["passed"]]
        if dead:
            title = "%d of %d HIGH cards name a date that has passed" % (len(dead), len(high))
            body = "Oldest on the list: %s" % dead[0]["title"]
            live = "passed" in ((board.get("aging") or {}).get("rules") or {})
            why = ("The daily job moves these to Old a week after the date. Put one back and it stays." if live
                   else "No rule ages these yet, so they stay until someone moves them.")
            route = "board/passed"
        else:
            title = "%d HIGH cards on the board" % len(high)
            body = high[0]["title"] if high else ""
            why = "Everything marked urgent, in one place."
            route = "board"
        add("board", "board", 550, "Board", title, body, why, "board", route=route)

    brain = data["liveness"]
    if brain["still"]:
        top = brain["stillRows"][0] if brain["stillRows"] else None
        body = ""
        if top:
            body = ("%s has never reported in (limit %s)." % (top["name"], top["limit"]) if top["age"] == "nie"
                    else "%s has been silent for %s (limit %s)." % (top["name"], top["age"], top["limit"]))
        add("brain", "brain", 500, "Brain health", "%d background systems went silent" % brain["still"], body,
            "Silence counts as dead until something proves otherwise.", "liveness", route="brain")

    goals = data["goals"]
    if goals["now"]:
        src = sources_by_id["goals"]
        over = finished_in_tracker(goals["now"], pipe)
        if over:
            # A goal the tracker says is finished is not a goal. What is true is that the list is behind.
            name, status = over
            add("goals", "goals", 450, "Goals are out of date", "\"Right now\" still says %s" % name,
                "%s is finished%s. Nothing has replaced it as your one thing." % (name, ": " + status if status else ""),
                "Goals.md has not caught up with your tracker, so this is not shown as a goal.", "goals", note="Goals.md")
        else:
            head, rest = first_sentence(goals["now"], 90)
            stale = src["state"] != "fresh"
            add("goals", "goals", 450 if stale else 200, "Goals, Right now", head, rest,
                "This line was last edited %s days ago. Does it still hold?" % src["ageDays"] if stale
                else "Your own pick for the one thing.", "goals",
                note="Goals.md")

    cards.sort(key=lambda c: -c["score"])
    return cards[:8]


def read_calendar(feed, today):
    rel = "Your calendar's link"
    if feed is None or not feed.connected():
        return [], 0, source("calendar", "Calendar", rel, None, 1, today, "not connected yet")
    events, fetched, error = feed.snapshot(today, AGENDA_DAYS)
    if fetched is None:
        return [], 0, source("calendar", "Calendar", rel, None, 1, today, error or "still loading")
    kept = [e for e in events if not PRIVATE.search(e["title"] + " " + e.get("where", ""))]
    gone = lost(fetched, error)
    return kept, len(events) - len(kept), source("calendar", "Calendar", rel, None if gone else date.fromtimestamp(fetched), 1, today, gone or error)


def event_matters(event):
    """Someone else is expecting you, or you marked it. A dentist slot or a weekly job is routine. Outlook's link names
    no guests, so there the link to a call is what tells."""
    return (event["people"] >= 2 or event["conference"] or bool(event.get("call")) or "!" in event["title"]
            or bool(MUST_PREPARE.search(event["title"])))


def in_days(days):
    if days < 0:
        return "%d days ago" % -days if days < -1 else "yesterday"
    return "today" if days == 0 else "tomorrow" if days == 1 else "in %d days" % days


def title_words(title):
    return {w.lower() for w in re.findall(r"[^\W\d_]{5,}", title)}


def spaced(text):
    return " %s " % " ".join(re.findall(r"\w+", text.lower()))


def event_note(event, titles):
    """The note an event opens. First its prep note: a title that starts with a name from the event and holds
    the event's date ("Fjordrun Spickzettel 2026-11-17"). Then the longest note title inside the event title
    ("Fjordrun"), then a single word of four letters or more.
    The prep note may use a short name the vault has no note for: "Nordlic Spickzettel 2026-11-19" belongs to
    "Nordlic, 1. Interview ..." although the company note is "NORDLICHT X". Its first word must be in the event."""
    name = spaced(event["title"])
    phrases = sorted((t for t in titles if " " in t and spaced(t) in name), key=len, reverse=True)
    words = [w.lower() for w in re.findall(r"[^\W\d_]{4,}", event["title"]) if w.lower() in titles]
    names = phrases + words
    day = event.get("date") or ""

    def leads(t):
        first = re.match(r"[^\W\d_]{4,}", t)
        return bool(first) and " %s " % first.group(0) in name

    dated = sorted(t for t in titles if day and day in t and (any(t.startswith(n + " ") for n in names) or leads(t)))
    if dated:
        return titles[dated[-1]]
    return titles[names[0]] if names else None


def card_route(card):
    return "board/card:" + card["id"] if card.get("id") else "board"


# How hot a Home card is. Its picture and colour follow: red, orange, yellow, blue, green.
LEVEL_ORDER = ("critical", "high", "medium", "low", "calm")


def level_of(days):
    """From the days left: today, tomorrow or missed is on fire, three days burns, a week is warm, two weeks calm."""
    if days is None:
        return "medium"
    for limit, level in ((1, "critical"), (3, "high"), (7, "medium"), (14, "low")):
        if days <= limit:
            return level
    return "calm"


def hotter(a, b):
    return min(a, b, key=LEVEL_ORDER.index)


def build_alerts(data, cards, events, titles, srcs, today):
    """What gets the first slides on Home and the pop-up elsewhere. build_focus adds the rest of the deck.

    Three things pass: my own deadline inside a week (or one I missed), a HIGH card whose real date
    is inside a week, and an event inside a week where other people are expecting me.
    """
    found = []

    def alert(days, cid, eyebrow, tag, title, body, why, src, note=None, route=None, join=""):
        found.append((days, {"id": cid, "kind": "deadline", "score": 0, "eyebrow": eyebrow, "tag": tag, "title": title, "body": body,
                             "why": why, "source": src["label"], "sourceState": src["state"], "sourceAge": age_words(src),
                             "route": route, "note": note, "heat": round(clamp(1 - max(days, 0) / float(ALERT_DAYS)), 2), "fog": 0.08,
                             "join": join, "level": level_of(days)}))

    for event in events:
        days = (iso_date(event["date"]) - today).days
        if days <= ALERT_DAYS and event_matters(event):
            people = event["people"] - 1
            note = event_note(event, titles)
            alert(days, "event-%s-%s" % (event["date"], event["title"]), "Prepare",
                  "%s %s" % (weekday_label(event["date"]), event["time"]) if event["time"] else weekday_label(event["date"]),
                  event["title"], event["where"] or ("With %d other%s" % (people, "" if people == 1 else "s") if people > 0 else ""),
                  ("%s, and other people are expecting you." % in_days(days).capitalize()) if people > 0 or event["conference"]
                  else ("%s, with a link to a call." % in_days(days).capitalize()) if event.get("call")
                  else "%s. You marked this as important." % in_days(days).capitalize(), srcs["calendar"], note=note,
                  join=event.get("join", ""))

    def same_as_event(card, due):
        words = title_words(card["title"])
        return any(e["date"] == due.isoformat() and words & title_words(e["title"]) for e in events)

    for card in data["board"]["items"]:
        due = iso_date(card.get("due") or "")
        if card.get("mine", True) and card["status"] == "HIGH" and due and 0 <= (due - today).days <= ALERT_DAYS and not same_as_event(card, due):
            days = (due - today).days
            alert(days, "card-" + card["title"], "Marked HIGH", "due " + weekday_label(due.isoformat()), card["title"], card["body"][:220],
                  "You marked this HIGH and it is due %s." % in_days(days), srcs["board"], route="board",
                  note=card_note(card, titles))

    for item in data["open"]["items"]:
        days = item["daysLeft"]
        if item["mine"] and days is not None and -14 <= days <= ALERT_DAYS:
            ready = next((c for c in cards if c["id"] == "open-" + item["name"]), None)
            found.append((days, dict(ready, kind="deadline", level=level_of(days)) if ready else {}))

    # A dated task is the owner's own deadline. "priority" lets only medium and up through, for vaults that date everything.
    tasks = data.get("tasks") or {}
    strict = tasks.get("home") == "priority"
    for task in tasks.get("items", []):
        days = task["daysLeft"]
        if task["kind"] != "due" or not -14 <= days <= ALERT_DAYS:
            continue
        if strict and task["priority"] not in ("highest", "high", "medium"):
            continue
        where = Path(task["path"]).stem
        alert(days, task["id"], "Your task", "due " + weekday_label(task["due"]), task["title"], "From " + where,
              ("Your own deadline, %s." % in_days(days)) if days >= 0 else "Your own deadline passed %s." % in_days(days),
              srcs["tasks"], note=task.get("notePath"))
    found = [f for f in found if f[1]]
    # No cap. What passes the gate is important, and quietly dropping the fifth one would be the worst outcome.
    found.sort(key=lambda f: f[0])
    return [f[1] for f in found]


def headline(title, limit=64):
    """A long board title as a headline and the rest, cut where the title itself pauses."""
    if len(title) <= limit:
        return title, ""
    for mark in (" (", ", "):
        cut = title.find(mark)
        if 0 < cut <= limit:
            rest = title[cut + len(mark) - (1 if mark == " (" else 0):].strip()
            if rest.startswith("(") and rest.endswith(")") and rest.count("(") == 1:
                rest = rest[1:-1]
            return title[:cut], rest
    return first_sentence(title, limit)


def card_text(card, rest=""):
    """The sentence worth reading on a card. "OFFEN: ..." is the card saying what is left to do."""
    plain = clean_md(re.sub(r"https?://\S+", "", (card.get("body") or "").split("\n---")[0]))
    # Where a card lives belongs on the button, not in the sentence. A link's label goes with the link.
    plain = re.sub(r"\s\w+:$", "", re.split(r"\s(?:Vault|Repo):", plain)[0])
    left = OPEN_PART.search(plain)
    if left:
        return left.group(1)
    return "%s. %s" % (rest, plain) if rest and plain else rest or plain


def card_note(card, titles, vault=None):
    """The note a card points at: named in its text ("Vault: Projects/X.md"), or by the words before its colon.
    Without the vault at hand, a named note counts when it is among the known notes."""
    named = re.search(r"Vault:\s*([^\n]+?\.md)", card.get("body") or "")
    if named and (os.path.isfile(str(Path(vault) / named.group(1))) if vault else named.group(1) in titles.values()):
        return named.group(1)
    return titles.get(re.sub(r"\s+\d{1,2}/\d{1,2}$", "", card["title"].split(":")[0]).strip().lower())


def build_focus(data, cards, alerts, titles, srcs, vault, removed=frozenset(), gone=None, today=None):
    """The slides on Home: what the gate let through, then the next to-dos until there are HOME_SLOTS.

    The gate is never cut, and nothing pads the deck. The fill is my own dated matters, then HIGH
    cards, then MID cards in the order of the owner's homeAreas. Goals, news and a MID card from any other area
    (maintenance, mostly) stay off, and a numbered chain of cards shows only its next step.
    A card I took off Home by hand stays off, and lands in gone so the Today page can offer it back.
    """
    gone = [] if gone is None else gone
    today = today or date.today()

    def off(cid, title):
        if card_key(cid) not in removed:
            return False
        if all(g["id"] != cid for g in gone):
            gone.append({"id": cid, "title": title})
        return True

    focus = list(alerts)
    taken = {a["id"] for a in focus}
    matters = data["open"]["items"]
    for item in sorted((m for m in matters if m["mine"] and m["daysLeft"] is not None), key=lambda m: m["daysLeft"]):
        ready = next((c for c in cards if c["id"] == "open-" + item["name"]), None)
        if ready and ready["id"] not in taken and not off(ready["id"], ready["title"]) and len(focus) < HOME_SLOTS:
            focus.append(dict(ready, level=level_of(item["daysLeft"])))
            taken.add(ready["id"])

    # A matter or a meeting already says what its card would say, and a matter waiting on someone is not a to-do.
    names = [m["name"] for m in matters] + [a["title"] for a in alerts if not a["id"].startswith("card-")]
    names = [re.split(r"[:\s]", n.strip())[0] for n in names]
    items = [c for c in data["board"]["items"] if c["status"] in LANES and c.get("mine", True)]
    first_open = {}
    for card in items:
        chain = SERIES_TITLE.match(card["title"])
        if chain:
            first_open[chain.group(1)] = min(first_open.get(chain.group(1), 99), int(chain.group(2)))

    def wanted(card):
        chain = SERIES_TITLE.match(card["title"])
        return (card["bereich"] != "News" and not card["passed"] and not GOAL_TITLE.match(card["title"])
                and "card-" + card["title"] not in taken
                and not any(n and re.search(r"\b%s\b" % re.escape(n), card["title"], re.I) for n in names)
                and (not chain or int(chain.group(2)) == first_open[chain.group(1)])
                and not off("card-" + card["title"], headline(card["title"])[0]))

    kinds = data.get("homeAreas") or AREA_KIND
    order = list(kinds)
    rank = lambda c: order.index(c["bereich"]) if c["bereich"] in order else len(order)
    high = sorted((c for c in items if c["status"] == "HIGH" and wanted(c)), key=rank)
    mid = sorted((c for c in items if c["status"] == "MID" and c["bereich"] in kinds and wanted(c)), key=rank)
    src = srcs["board"]
    for card in (high + mid)[:max(0, HOME_SLOTS - len(focus))]:
        head, rest = headline(card["title"])
        note = card_note(card, titles, vault)
        is_high = card["status"] == "HIGH"
        if is_high and card["due"]:
            why = "You marked this HIGH and it is due on %s." % weekday_label(card["due"])
        elif is_high:
            why = "You marked this HIGH. No date on it, so nothing else will remind you."
        else:
            why = "Next in line on your board: MID, %s." % card["bereich"]
        if SERIES_TITLE.match(card["title"]):
            why += " The later steps of this chain wait behind it."
        # The colour says what the card says: HIGH is orange at least, red when its date is close. MID is blue.
        due = iso_date(card["due"] or "")
        level = (hotter(level_of((due - today).days), "high") if due else "high") if is_high else "low"
        focus.append({"id": "card-" + card["title"], "kind": kinds.get(card["bereich"], "board"), "score": 0, "level": level,
                      "eyebrow": "Marked HIGH" if is_high else "Next up",
                      "tag": "due " + weekday_label(card["due"]) if card["due"] else card["bereich"],
                      "title": head, "body": card_text(card, rest)[:260], "why": why, "source": src["label"],
                      "sourceState": src["state"], "sourceAge": age_words(src), "route": None if note else card_route(card),
                      "note": note, "heat": 0.4 if is_high else 0.15, "fog": 0.08})
    return focus


def build_agenda(data, events, titles, today):
    """Everything with a date from today on. The day strip and the day pages read this."""
    last = today + timedelta(days=AGENDA_DAYS)
    rows = []

    def add(day, clock, label, title, sub, mine, note=None, route=None, url="", join=""):
        if day and today <= day <= last:
            rows.append({"date": day.isoformat(), "time": clock, "label": label, "title": title, "sub": sub,
                         "mine": mine, "note": note, "route": route, "url": url, "join": join})

    for item in data["open"]["items"]:
        add(iso_date(item["due"] or ""), "", "Your move" if item["mine"] else "Waiting on " + item["owner"], item["name"],
            item["next"], item["mine"], note=item.get("notePath"))
    for event in events:
        others = event["people"] - 1
        add(iso_date(event["date"]), event["time"], "Calendar", event["title"],
            event["where"] or ("With %d other%s" % (others, "" if others == 1 else "s") if others > 0 else ""),
            event_matters(event), note=event_note(event, titles), join=event.get("join", ""))
    for entry in data["pipeline"]["hot"] + data["pipeline"]["warm"]:
        # A date ahead in a live application is an appointment. "ABGESCHICKT 01.02." only ever looks like one.
        if not SENT_STATUS.search(entry["status"]) and (iso_date(entry["date"] or "") or today) > today:
            add(iso_date(entry["date"]), "", "Application", entry["firm"], entry["status"], True, note=entry.get("notePath"))
    for task in (data.get("tasks") or {}).get("items", []):
        add(iso_date(task["due"]), "", "Task" if task["kind"] == "due" else "Scheduled", task["title"],
            Path(task["path"]).stem, task["kind"] == "due", note=task.get("notePath"))
    # A card repeats what is already listed on its day when the two share a word.
    known = {}
    for row in rows:
        known.setdefault(row["date"], set()).update(title_words(row["title"]))
    for card in data["board"]["items"]:
        if (card["due"] and card["status"] in LANES + ("NEW", "No status") and card["bereich"] != "News"
                and not REPORT_TITLE.match(card["title"]) and not title_words(card["title"]) & known.get(card["due"], set())):
            add(iso_date(card["due"]), "", card["status"], headline(card["title"])[0], card_text(card)[:200],
                card["status"] == "HIGH", route=card_route(card), url=card.get("url") or "")
    rows.sort(key=lambda r: (r["date"], r["time"], r["title"]))
    return rows


# Words that say what kind of appointment it is, not which one. Two events can share them and be different things.
GENERIC_WORDS = {"interview", "meeting", "termin", "follow", "review", "weekly", "update", "gespräch", "gespraech",
                 "runde", "vorbereiten", "prepare", "online", "teams", "zoom", "google", "kickoff", "check", "abstimmung"}
# How far the schedule check looks ahead.
SCHEDULE_DAYS = 14
SCHEDULE_ORDER = ("prep", "clash", "overdue", "passed", "undated")
PIPE_EMPTY = {"hot": [], "warm": [], "ended": [], "closed": 0, "closedFirms": [], "lastSent": None, "daysSince": None, "hidden": 0}
LIVE_EMPTY = {"alive": None, "still": None, "resting": None, "stillRows": [], "aliveRows": []}
BOARD_EMPTY = {"items": [], "archived": [], "counts": {}, "bereiche": [], "passed": 0, "hidden": 0, "error": "",
               "aging": {"rules": None, "job": None}}


def build_schedule(data, events, titles, today):
    """Is every appointment covered, and does every urgent thing have a date? The code checks, nothing is written.

    Five findings, each with its reason: a meeting where others expect you that no card, task or prep note names;
    two such meetings at the same start; a task whose date passed; a board card whose date passed; a HIGH card
    without any date.
    """
    found = []
    plans = [c["title"] for c in data["board"]["items"] if c["status"] in LANES]
    plans += [t["title"] for t in (data.get("tasks") or {}).get("items", [])]
    plan_words = [title_words(p) - GENERIC_WORDS for p in plans]
    starts = {}
    for event in events:
        day = iso_date(event["date"])
        days = (day - today).days
        if not (0 <= days <= SCHEDULE_DAYS and event_matters(event)):
            continue
        if event["time"]:
            starts.setdefault((event["date"], event["time"]), []).append(event["title"])
        words = title_words(event["title"]) - GENERIC_WORDS
        if event_note(event, titles) or (words and any(words & w for w in plan_words)):
            continue
        prep = day - timedelta(days=1) if days > 1 else day
        found.append({"kind": "prep", "date": event["date"], "time": event["time"], "title": event["title"],
                      "why": ("Other people expect you %s, and no card, task or note names it." if event["people"] >= 2 or event["conference"]
                              else "This is %s, and no card, task or note names it.") % in_days(days),
                      "suggest": {"title": "Prepare: %s" % event["title"], "due": prep.isoformat()}})
    for (day, clock), names in sorted(starts.items()):
        if len(names) > 1:
            found.append({"kind": "clash", "date": day, "time": clock, "title": " and ".join(names),
                          "why": "%d meetings start at %s on the same day." % (len(names), clock)})
    for task in (data.get("tasks") or {}).get("items", []):
        if task["kind"] == "due" and task["daysLeft"] < 0:
            found.append({"kind": "overdue", "date": task["due"], "time": "", "title": task["title"],
                          "why": "Your task was due %s." % in_days(task["daysLeft"]), "note": task.get("notePath")})
    for card in data["board"]["items"]:
        if not card.get("mine", True):
            continue
        if card["passed"]:
            found.append({"kind": "passed", "date": card["due"], "time": "", "title": headline(card["title"])[0],
                          "why": "%s card, its date passed %s." % (card["status"], in_days((iso_date(card["due"]) - today).days)),
                          "route": card_route(card)})
        elif card["status"] == "HIGH" and not card["due"] and card["bereich"] != "News" and not REPORT_TITLE.match(card["title"]):
            found.append({"kind": "undated", "date": None, "time": "", "title": headline(card["title"])[0],
                          "why": "Marked HIGH with no date, so nothing will remind you.", "route": card_route(card)})
    found.sort(key=lambda f: (SCHEDULE_ORDER.index(f["kind"]), f["date"] or "9999", f["time"]))
    counts = {kind: sum(1 for f in found if f["kind"] == kind) for kind in SCHEDULE_ORDER}
    return {"items": found, "counts": counts, "days": SCHEDULE_DAYS}


def areas_as_projects(board_data):
    """No project list yet: every area on the board is a project, so the Projects page is never empty by accident."""
    names = [a for a in board_data["bereiche"] if a not in ("No area", "News")]
    return [{"id": re.sub(r"[^a-z0-9]+", "-", a.lower()).strip("-") or "area", "name": a, "bereich": a} for a in names]


def build_state(vault, board, today=None, registry=(), calendar=None, removed=frozenset(), profile=None, tasks=None):
    """Everything the page shows, from the sources the owner switched on. profile None reads every source but tasks."""
    today = today or date.today()

    def on(sid):
        if profile is None:
            return sid != "tasks"
        return bool(((profile.get("sources") or {}).get(sid) or {}).get("on"))

    def rel(sid, default):
        return (((profile or {}).get("sources") or {}).get(sid) or {}).get("path") or default

    open_items, s_open = (read_open_items(vault, today, rel("openItems", "Open matters.md")) if on("openItems")
                          else ({"items": [], "hidden": 0}, off("open-items", "Open matters")))
    pipeline, s_pipe = (read_pipeline(vault, today, rel("pipeline", "Applications.md")) if on("pipeline")
                        else (dict(PIPE_EMPTY, hot=[], warm=[], ended=[], closedFirms=[]), off("pipeline", "Pipeline")))
    goals, s_goals = read_goals(vault, today, rel("goals", "Goals.md")) if on("goals") else ({"now": ""}, off("goals", "Goals"))
    brief, s_brief = (read_brief(vault, today, rel("brief", "outputs/morning-brief-latest.md")) if on("brief")
                      else ({"oneThing": ""}, off("brief", "Morning brief")))
    liveness, s_live = (read_liveness(vault, today, rel("liveness", "outputs/liveness-latest.md")) if on("liveness")
                        else (dict(LIVE_EMPTY, stillRows=[], aliveRows=[]), off("liveness", "Brain health")))
    if on("board") and board is not None:
        script = (getattr(board, "aging", None) or {}).get("script")
        board_data, s_board = read_board(board, today, aging_rules(vault, getattr(board, "aging_source", ""), script))
    else:
        board_data, s_board = json.loads(json.dumps(BOARD_EMPTY)), off("board", "Board")
    if on("calendar"):
        events, hidden_events, s_cal = read_calendar(calendar, today)
    else:
        events, hidden_events, s_cal = [], 0, off("calendar", "Calendar")
    if on("tasks"):
        task_data, s_tasks = read_tasks(tasks if tasks is not None else TaskIndex(vault), today)
    else:
        task_data, s_tasks = {"items": [], "hidden": 0}, off("tasks", "Obsidian tasks")
    task_data["home"] = ((profile or {}).get("tasks") or {}).get("home", "all")
    srcs = [s_open, s_brief, s_pipe, s_board, s_live, s_goals, s_cal, s_tasks]

    # A link is only offered when its target exists, so nothing on the page leads nowhere. Without the
    # library there is nowhere for a note link to lead.
    library_on = on("library")
    titles = {}
    for note in (read_notes(vault) if library_on else []):
        titles.setdefault(note["title"].lower(), note["path"])
    for item in open_items["items"]:
        item["notePath"] = titles.get(item["note"].split("/")[-1].lower())
    for entry in pipeline["hot"] + pipeline["warm"] + pipeline["ended"]:
        company = "Companies/%s.md" % entry["link"]
        entry["notePath"] = (company if library_on and os.path.isfile(str(Path(vault) / company)) else titles.get(entry["link"].lower()))
    for task in task_data["items"]:
        task["notePath"] = task["path"] if library_on else None
    for src in srcs:
        if src["id"] == "board":
            src["route"] = "board"
            src["url"] = getattr(board, "url", "")
        elif src["id"] not in ("calendar", "tasks") and src["path"] and library_on and os.path.isfile(str(Path(vault) / src["path"])):
            src["notePath"] = src["path"]

    data = {"open": open_items, "pipeline": pipeline, "goals": goals, "brief": brief, "liveness": liveness,
            "board": board_data, "tasks": task_data,
            "homeAreas": dict(((profile or {}).get("board") or {}).get("homeAreas") or AREA_KIND)}
    by_id = {s["id"]: s for s in srcs}
    cards = build_cards(data, by_id)
    alerts = build_alerts(data, cards, events, titles, by_id, today)
    # A card taken off Home by hand leaves the alerts too: it was judged not important.
    gone = [{"id": a["id"], "title": a["title"]} for a in alerts if card_key(a["id"]) in removed]
    alerts = [a for a in alerts if card_key(a["id"]) not in removed]
    focus = build_focus(data, cards, alerts, titles, by_id, vault, removed, gone, today)
    deadlines = [{"name": i["name"], "due": i["due"], "mine": i["mine"]} for i in open_items["items"] if i["due"]]
    deadlines += [{"name": e["title"], "due": e["date"], "mine": event_matters(e)} for e in events]
    deadlines += [{"name": t["title"], "due": t["due"], "mine": True} for t in task_data["items"] if t["kind"] == "due"]
    hidden = (open_items["hidden"] + pipeline["hidden"] + board_data["hidden"] + (1 if brief.get("hidden") else 0)
              + hidden_events + task_data["hidden"])
    if not registry and on("board"):
        registry = areas_as_projects(board_data)
    projects = build_projects(vault, registry, board_data, open_items, pipeline, board, today, iso_date(s_pipe["asOf"] or ""))
    pages_off = [page for page, sid in (("library", "library"), ("pipeline", "pipeline"), ("board", "board"), ("ask", "ask"))
                 if not on(sid) or (sid == "board" and board is None)]
    return {"today": today.isoformat(), "vaultName": os.path.basename(os.path.abspath(str(vault))), "cards": cards,
            "deadlines": deadlines, "sources": [s for s in srcs if s["state"] != "off"], "hidden": hidden,
            "projects": projects, "alerts": alerts, "focus": focus, "removedCards": gone,
            "agenda": build_agenda(data, events, titles, today), "agendaDays": AGENDA_DAYS,
            "events": [e for e in events if (iso_date(e["date"]) - today).days <= TODAY_EVENT_DAYS],
            "calendarConnected": bool(calendar and calendar.connected()), "pagesOff": pages_off,
            "vaultProblem": folder_problem(vault) if (profile or {}).get("vault") else "",
            "owner": (profile or {}).get("name", ""), "schedule": build_schedule(data, events, titles, today), **data}
