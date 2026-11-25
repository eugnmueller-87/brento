"""Looks at a computer after an installer ran, and says whether Daytag is really there, or really gone.

    python packaging/check_install.py up      installed, running from its own folder, starting at sign-in, setup still to do
    python packaging/check_install.py kept    the same, and the setup someone has already done is still there
    python packaging/check_install.py down    removed: nothing running, nothing left but the settings

The release workflow runs this on real Macs and Windows computers before anything is published. Exit code 0 is good.
"""
import json
import os
import plistlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import address  # noqa: E402
import launcher  # noqa: E402

WINDOWS = sys.platform == "win32"
HOME = Path.home()
if WINDOWS:
    BASE = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Daytag"
    PYTHON = BASE / "python" / "python.exe"
    SHORTCUTS = [Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Daytag.lnk"]
else:
    BASE = HOME / "Library" / "Application Support" / "Daytag"
    PYTHON = BASE / "python" / "bin" / "Daytag"
    SHORTCUTS = [HOME / "Applications" / "Daytag.app", HOME / "Applications" / "Uninstall Daytag.app",
                 HOME / ".local" / "bin" / "daytag", HOME / "Library" / "LaunchAgents" / "app.daytag.server.plist"]
FAILED = []
# False for a Store package: nobody but Windows may start the programs inside it.
RUNNABLE = True


def check(good, text):
    print("%s  %s" % ("ok  " if good else "FAIL", text), flush=True)
    if not good:
        FAILED.append(text)


def get(path, key=True):
    """What the server sends to its owner, or without the key to anyone else on this computer."""
    headers = {"X-Daytag": "1"}
    if key:
        headers[address.KEY_HEADER] = address.key()
    try:
        with address.DIRECT.open(urllib.request.Request(address.page() + path, headers=headers), timeout=90) as reply:
            return reply.status, reply.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def output(program, *args):
    """What a program of the installed Daytag says. Nothing from this computer's own PATH is asked."""
    try:
        done = subprocess.run([str(program)] + list(args), capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.SubprocessError) as exc:
        return "did not run: %s" % exc
    return done.stdout.strip() if done.returncode == 0 else "ended with %d: %s" % (done.returncode, done.stderr.strip()[-300:])


def autostart():
    if WINDOWS:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                return str(winreg.QueryValueEx(key, "Daytag")[0])
        except OSError:
            return ""
    return launcher.output(["launchctl", "print", "gui/%d/app.daytag.server" % os.getuid()])


def programs():
    pinned = json.loads((ROOT / "packaging" / "runtimes.json").read_text(encoding="utf-8"))
    wanted = pinned["gh-windows-x64" if WINDOWS else "gh-mac-arm64"]["version"]
    said = output(BASE / "app" / "bin" / ("gh.exe" if WINDOWS else "gh"), "--version")
    check(wanted in said.split("\n")[0], "the GitHub program that came along runs: %s" % said.split("\n")[0])
    said = output(PYTHON, "-c", "import ssl, sys, urllib.request; print(sys.version.split()[0], "
                  "urllib.request.urlopen('https://github.com/robots.txt', timeout=30).status)")
    check(said.endswith(" 200"), "its own Python opens https pages: %s" % said)
    said = output(PYTHON, "-c", "import datetime, zoneinfo; print(datetime.datetime(2026, 11, 26, 10, "
                  "tzinfo=zoneinfo.ZoneInfo('America/New_York')).astimezone(datetime.timezone.utc).hour)")
    check(said == "15", "its own Python knows other time zones: %s" % said)


def up(kept=False):
    check((BASE / "app" / "server.py").is_file(), "the program is in %s" % BASE)
    for path in SHORTCUTS:
        check(path.exists(), "there is %s" % path)
    ends = time.monotonic() + 60
    while address.whose() != "mine" and time.monotonic() < ends:
        time.sleep(1)
    check(address.whose() == "mine", "this person's Daytag answers on %s" % address.page())
    if FAILED:
        log = HOME / ".daytag" / "server.log"
        print(log.read_text(encoding="utf-8", errors="replace")[-2000:] if log.is_file() else "no server.log")
        return
    pid = launcher.listener()
    running = launcher.program_of(pid)
    check(str(BASE) in running, "it runs from its own folder: %s" % running)
    status, page = get("")
    check(status == 200 and b'id="view"' in page, "the page loads")
    for name in ("app.js", "art.js", "sign.js", "style.css"):
        status, body = get(name)
        check(status == 200 and body == (BASE / "app" / "web" / name).read_bytes(), "%s is the installed one" % name)
    status, body = get("api/state", key=False)
    check(status == 401 and sorted(json.loads(body.decode("utf-8"))) == ["error", "locked"], "without the key there is nothing to see")
    for path in ("api/setup", "api/tools", "api/wizard", "api/library", "api/library/seal?path=x"):
        check(get(path, key=False)[0] == 401, "without the key: %s is locked" % path)
    check(re.match(re.escape(address.page()) + r"\?ticket=[\w-]{20,}$", address.entrance()), "the icon gets a ticket that lets the browser in")
    status, body = get("api/wizard")
    view = json.loads(body.decode("utf-8"))
    if kept:
        check(view["needed"] is False and view["profile"]["name"] == "Test Person", "the setup is kept: %r" % view["profile"]["name"])
    else:
        check(view["needed"] is True, "a new owner gets the setup")
    check("not installed" not in view["gh"]["reason"], "the setup finds the GitHub program: %s" % (view["gh"]["reason"] or "ready"))
    if RUNNABLE:
        programs()
    entry = autostart()
    check("launcher.py" in entry and "--start" in entry if WINDOWS else "state = running" in entry, "it starts at sign-in")
    if not WINDOWS:
        check(plistlib.loads(SHORTCUTS[-1].read_bytes()).get("MaterializeDatalessFiles") is True, "it may fetch notes that lie only in iCloud")


def down():
    ends = time.monotonic() + 30
    while (address.whose() or BASE.exists()) and time.monotonic() < ends:
        time.sleep(1)
    check(not address.whose(), "Daytag no longer answers")
    for path in [BASE / "app" / "server.py", PYTHON] + SHORTCUTS:
        check(not path.exists(), "gone: %s" % path)
    left = sorted(str(p) for p in BASE.rglob("*") if p.is_file())[:8] if BASE.exists() else []
    check(not BASE.exists(), "gone: %s %s" % (BASE, left or ""))
    check(not autostart() if WINDOWS else "state = running" not in autostart(), "gone: the start at sign-in")
    check((HOME / ".daytag").is_dir(), "the settings folder stays")


if __name__ == "__main__":
    {"up": up, "kept": lambda: up(kept=True), "down": down}[sys.argv[1]]()
    sys.exit(1 if FAILED else 0)
