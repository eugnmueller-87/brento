"""Upcoming events from a calendar's private iCal link. Free, no login flow, read-only.

The link itself is a secret: whoever has it can read the calendar. So it lives in one file in the
home folder with owner-only rights, is never sent to the page, and never appears in a log or error.
"""
import ipaddress
import json
import re
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


# Outlook names time zones its own way. The list is Unicode's: https://cldr.unicode.org, windowsZones, territory 001.
try:
    WINDOWS_ZONES = json.loads((Path(__file__).resolve().parent / "windows-zones.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    WINDOWS_ZONES = {}
# Calendar services whose shared links need not end in .ics. Apple's public link, for one, carries no ending.
ICS_HOSTS = ("icloud.com", "outlook.office365.com", "outlook.office.com", "outlook.live.com")


def clean_url(url):
    url = str(url or "").strip()
    if not url:
        raise ValueError("Paste the link first.")
    # Apple and Outlook hand out webcal:// links. They are the same address over https.
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    parts = urlsplit(url)
    if parts.scheme.lower() != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Use the https link from your calendar's settings.")
    host = parts.hostname.lower()
    if not parts.path.lower().endswith(".ics") and not any(host == h or host.endswith("." + h) for h in ICS_HOSTS):
        raise ValueError("That is not a calendar link. It should end in .ics.")
    try:
        if not ipaddress.ip_address(parts.hostname).is_global:
            raise ValueError("Use the public link from your calendar's settings.")
    except ValueError as exc:
        if "public link" in str(exc):
            raise
    return url


# A video call's join link. Teams, Meet, Zoom and Webex put it in different places: Meet in its own field,
# Teams in the invite text, Zoom often in the location.
JOIN_LINK = re.compile(r"https://(?:teams\.microsoft\.com/(?:l/meetup-join|meet)/|teams\.live\.com/meet/|meet\.google\.com/[a-z]"
                       r"|[\w.-]*zoom\.us/(?:j|my|w)/|[\w.-]*webex\.com/)[^\s<>\"'\\]+", re.I)


# Of these, the ones that are a meeting, not a webinar or a recording.
CALL_LINK = re.compile(r"^https://(?:teams\.microsoft\.com/|teams\.live\.com/|meet\.google\.com/|[\w.-]*zoom\.us/(?:j|my)/"
                       r"|[\w.-]*webex\.com/(?:meet|join|[\w.-]+/j\.php))", re.I)
# A line's name ends at the first colon that is not inside quotes. Outlook writes TZID="tzone://Microsoft/Utc".
ICS_LINE = re.compile(r'^((?:[^":]|"[^"]*")*):(.*)$')


def _join(*texts):
    for text in texts:
        found = JOIN_LINK.search(_text(text))
        if found:
            return found.group(0).rstrip(".,;)")
    return ""


def _text(value):
    return value.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def _start(params, value):
    """Returns (date, 'HH:MM' or '', the zone's name when the time could not be put into this computer's own).
    All-day events have no time."""
    if len(value) == 8:
        return datetime.strptime(value, "%Y%m%d").date(), "", ""
    unknown = ""
    stamp = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        stamp = stamp.replace(tzinfo=timezone.utc).astimezone()
    else:
        tz = re.search(r'TZID=(?:"([^"]+)"|([^;:]+))', params)
        if tz:
            zone = (tz.group(1) or tz.group(2)).strip()
            try:
                stamp = stamp.replace(tzinfo=ZoneInfo(WINDOWS_ZONES.get(zone, zone))).astimezone()
            except Exception:
                # The sender's clock time is still worth showing, with the name of the place it belongs to.
                unknown = zone
    return stamp.date(), stamp.strftime("%H:%M"), unknown


def parse_ics(text, today, days=21):
    """One-off events from today on. Series are left out on purpose: a recurring slot is routine."""
    unfolded = re.sub(r"\r?\n[ \t]", "", text)
    # Outlook's link names no guests at all. Only in such a calendar does the link to a call stand for them.
    guests = re.search(r"^ATTENDEE[;:]", unfolded, re.M) is not None
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, re.S):
        fields, people, conference, meet = {}, 0, False, ""
        for line in block.splitlines():
            found = ICS_LINE.match(line)
            if not found:
                continue
            name, value = found.groups()
            key, _, params = name.partition(";")
            key = key.upper()
            if key == "ATTENDEE":
                people += 1
            elif key == "X-GOOGLE-CONFERENCE":
                conference, meet = True, value
            elif key not in fields:
                fields[key] = (params, value)
        if "RRULE" in fields or "DTSTART" not in fields or "SUMMARY" not in fields:
            continue
        if fields.get("STATUS", ("", ""))[1].strip().upper() == "CANCELLED":
            continue
        try:
            day, clock, zone = _start(*fields["DTSTART"])
        except ValueError:
            continue
        if not today <= day <= today + timedelta(days=days):
            continue
        where = _text(fields.get("LOCATION", ("", ""))[1])
        if zone:
            where = "%s is the time in %s. %s" % (clock, zone, where)
        join = _join(meet, *(fields.get(k, ("", ""))[1] for k in ("LOCATION", "URL", "DESCRIPTION")))
        events.append({"title": _text(fields["SUMMARY"][1]), "date": day.isoformat(), "time": clock, "zone": zone,
                       "where": where.strip(), "people": people, "conference": conference, "join": join,
                       "call": not guests and bool(CALL_LINK.match(join))})
    events.sort(key=lambda e: (e["date"], e["time"]))
    return events


class Feed:
    def __init__(self, path, ttl=900):
        self.path, self.ttl = Path(path), ttl
        self.text, self.fetched, self.error = None, 0.0, ""
        self.busy = False
        self.lock = threading.Lock()

    def url(self):
        try:
            return self.path.read_text(encoding="utf-8-sig").strip()
        except OSError:
            return ""

    def connected(self):
        return bool(self.url())

    def connect(self, url):
        """Keeps a link only after it has answered with a calendar, so a wrong one never replaces one that works."""
        url = clean_url(url)
        try:
            body = self.read(url)
        except (OSError, ValueError):
            # The message stays generic, because a network error can quote the secret link.
            raise ValueError("Brento could not read that link. Copy it again from your calendar's settings.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(url, encoding="utf-8")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        self.text, self.fetched, self.error = body, time.time(), ""

    def disconnect(self):
        try:
            self.path.unlink()
        except OSError:
            pass
        self.text, self.fetched, self.error = None, 0.0, ""

    @staticmethod
    def read(url):
        request = urllib.request.Request(url, headers={"User-Agent": "Brento"})
        with urllib.request.urlopen(request, timeout=20) as res:
            body = res.read(8 * 1024 * 1024).decode("utf-8", errors="replace")
        if "BEGIN:VCALENDAR" not in body:
            raise ValueError("not a calendar")
        return body

    def fetch(self):
        try:
            self.text, self.fetched, self.error = self.read(self.url()), time.time(), ""
        except (OSError, ValueError):
            # The message stays generic, because a network error can quote the secret link.
            self.error = "the calendar link did not answer"
        finally:
            self.busy = False

    def refresh(self):
        """For the refresh button: ask the calendar now. Returns the error, if any."""
        if not self.connected():
            return ""
        self.fetch()
        return self.error

    def snapshot(self, today, days=21):
        """Returns (events, fetched time or None, error). Refreshes in the background."""
        with self.lock:
            due = time.time() - self.fetched > self.ttl and not self.busy and self.connected()
            if due:
                self.busy = True
        if due:
            threading.Thread(target=self.fetch, daemon=True).start()
        if self.text is None:
            return [], None, self.error
        return parse_ics(self.text, today, days), self.fetched, self.error
