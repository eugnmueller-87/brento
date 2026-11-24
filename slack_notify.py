"""Brento in Slack: a morning summary, a note when something new needs you, a reminder before a meeting.

Through an incoming webhook the owner makes in their own Slack: free, one channel, nothing hosted. The link
is a secret, so it lives in one file in Brento's folder, is never sent back to a page and never appears in
an error. What goes out has passed the privacy list already, and open matters stay home unless chosen.
"""
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from tools import card_key

HOOK = re.compile(r"^https://hooks\.slack\.com/services/[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+$")
# The app the owner creates from one link. Only keys Slack documents: a name and incoming webhooks switched on.
MANIFEST = {"display_information": {"name": "Brento", "description": "Your day from Brento: what needs you, and when."},
            "settings": {"incoming_webhooks": {"incoming_webhooks_enabled": True}}}
CREATE_URL = "https://api.slack.com/apps?new_app=1&manifest_json=" + urllib.parse.quote(json.dumps(MANIFEST))
# How late a morning summary may still go out, for a computer that was off at the set time.
DIGEST_WINDOW = timedelta(hours=3)
# How long it waits for a source that has not been read yet, such as a calendar right after the computer starts.
DIGEST_WAIT = timedelta(minutes=15)
MAX_LINES = 8
MAX_SEEN = 300


def clean_hook(url):
    url = str(url or "").strip()
    if not url:
        raise ValueError("Paste the link first.")
    if not HOOK.match(url):
        raise ValueError("That is not a Slack webhook link. It starts with https://hooks.slack.com/services/")
    return url


def esc(text):
    """Slack reads &, < and > as markup."""
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def link(url, label):
    url = str(url or "")
    return "<%s|%s>" % (url, esc(label)) if re.match(r"^https://[^\s|<>]+$", url) else ""


def event_matters(event):
    return event.get("people", 0) >= 2 or event.get("conference") or event.get("join") or "!" in event.get("title", "")


def unread(state, allowed):
    """The sources a summary stands on that could not be read. One the owner never connected does not count."""
    return [s["label"] for s in state.get("sources", []) if s["id"] in allowed and s.get("state") == "unknown"
            and s.get("note") != "not connected yet"]


def plan(state, cfg, memory, now, name=""):
    """What to send now, as message texts, and the memory to keep. Pure: no network, no clock of its own."""
    memory = dict(memory or {})
    labels = {s["label"]: s["id"] for s in state.get("sources", [])}
    allowed = set(cfg.get("sources") or [])
    alerts = [a for a in state.get("alerts", []) if labels.get(a.get("source")) in allowed]
    today = now.date().isoformat()
    out = []

    seen = list(memory.get("seen") or [])
    keys = [card_key(a["id"]) for a in alerts]
    if not memory.get("seeded"):
        # The first run only learns what is there, so connecting Slack does not flood the channel.
        memory.update(seeded=True, seen=keys[-MAX_SEEN:])
    else:
        fresh = [a for a, k in zip(alerts, keys) if k not in seen]
        if cfg.get("alerts") and fresh:
            head = "*New in Brento*" if len(fresh) == 1 else "*%d new things in Brento*" % len(fresh)
            out.append("\n".join([head] + [line(a) for a in fresh[:MAX_LINES]]))
        memory["seen"] = (seen + [k for k in keys if k not in seen])[-MAX_SEEN:]

    digest = cfg.get("digest") or ""
    if digest and memory.get("digest") != today:
        at = datetime.combine(now.date(), datetime.strptime(digest, "%H:%M").time())
        if at <= now <= at + DIGEST_WINDOW:
            missing = unread(state, allowed)
            try:
                since = datetime.fromisoformat(str(memory.get("waiting") or ""))
            except ValueError:
                since = None
            if missing and (since is None or since.date() != now.date()):
                memory["waiting"] = now.isoformat()
            elif not missing or now - since >= DIGEST_WAIT:
                out.append(summary(state, alerts, name, missing))
                memory["digest"] = today
        elif now > at + DIGEST_WINDOW:
            memory["digest"] = today

    remind = int(cfg.get("remind") or 0)
    reminded = list(memory.get("reminded") or [])
    if remind and "calendar" in allowed:
        for event in state.get("events", []):
            if event.get("date") != today or not event.get("time") or not event_matters(event):
                continue
            start = datetime.combine(now.date(), datetime.strptime(event["time"], "%H:%M").time())
            key = card_key("%s %s %s" % (event["date"], event["time"], event["title"]))
            if key in reminded or not timedelta(0) <= start - now <= timedelta(minutes=remind):
                continue
            minutes = max(1, int((start - now).total_seconds() // 60))
            text = "*In %d min:* %s" % (minutes, esc(event["title"]))
            join = link(event.get("join"), "Join call")
            out.append(text + ("  " + join if join else ""))
            reminded.append(key)
        memory["reminded"] = reminded[-100:]
    return out, memory


def line(alert):
    tag = (" (%s)" % esc(alert["tag"])) if alert.get("tag") else ""
    join = link(alert.get("join"), "Join call")
    return "• *%s*%s: %s%s" % (esc(alert["title"]), tag, esc(alert.get("why", "")), ("  " + join) if join else "")


def summary(state, alerts, name, missing=()):
    hello = "Good morning%s." % (", " + esc(name) if name else "")
    if missing:
        hello += " N/A: %s could not be read, so something may be missing." % esc(", ".join(missing))
    if not alerts:
        body = ["In what could be read, nothing needs you today." if missing else "Nothing needs you today. Enjoy the calm."]
    else:
        body = ["%d thing%s need%s you:" % (len(alerts), "" if len(alerts) == 1 else "s", "s" if len(alerts) == 1 else "")]
        body += [line(a) for a in alerts[:MAX_LINES]]
        if len(alerts) > MAX_LINES:
            body.append("…and %d more in Brento." % (len(alerts) - MAX_LINES))
    counts = (state.get("schedule") or {}).get("counts") or {}
    loose = []
    if counts.get("prep"):
        loose.append("%d meeting%s without prep" % (counts["prep"], "" if counts["prep"] == 1 else "s"))
    if counts.get("undated"):
        loose.append("%d HIGH card%s without a date" % (counts["undated"], "" if counts["undated"] == 1 else "s"))
    if loose:
        body.append("On track? %s." % ", ".join(loose).capitalize())
    return "\n".join([hello] + body)


class Slack:
    def __init__(self, folder):
        self.hook_path = Path(folder) / "slack-webhook"
        self.memory_path = Path(folder) / "slack-state.json"
        self.lock = threading.Lock()
        self.error = ""

    def url(self):
        try:
            return self.hook_path.read_text(encoding="utf-8-sig").strip()
        except OSError:
            return ""

    def connected(self):
        return bool(self.url())

    def connect(self, url, hello):
        """Keeps a link only after a first message has gone through it, so a wrong one never replaces one that works."""
        url = clean_hook(url)
        error = self.send(hello, url)
        if error:
            raise ValueError(error)
        self.hook_path.parent.mkdir(parents=True, exist_ok=True)
        self.hook_path.write_text(url, encoding="utf-8")
        try:
            self.hook_path.chmod(0o600)
        except OSError:
            pass
        try:
            self.memory_path.unlink()
        except OSError:
            pass

    def disconnect(self):
        for path in (self.hook_path, self.memory_path):
            try:
                path.unlink()
            except OSError:
                pass

    def send(self, text, url=""):
        """Posts one message. Returns "" or a reason, never the link itself."""
        url = url or self.url()
        if not url:
            return "Slack is not connected."
        body = json.dumps({"text": text}).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "Brento"})
        try:
            with urllib.request.urlopen(request, timeout=15) as res:
                ok = res.status == 200
        except OSError as exc:
            code = getattr(exc, "code", None)
            self.error = ("Slack refused the message (%s). Make a new webhook link." % code) if code in (403, 404, 410) \
                else "Slack did not answer."
            return self.error
        self.error = "" if ok else "Slack did not take the message."
        return self.error

    def tick(self, state, cfg, name="", now=None):
        """Called about every half minute. Sends what plan() says and keeps its memory on disk."""
        if not self.connected():
            return []
        with self.lock:
            try:
                memory = json.loads(self.memory_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                memory = {}
            before = memory
            texts, memory = plan(state, cfg, memory, now or datetime.now(), name)
            sent = []
            for text in texts:
                if not self.send(text):
                    sent.append(text)
            if texts and not sent:
                # Nothing got through, for example on a Wi-Fi that is still waking up. The next round tries again.
                memory = before
            temp = self.memory_path.with_suffix(".tmp")
            temp.write_text(json.dumps(memory), encoding="utf-8")
            temp.replace(self.memory_path)
            return sent
