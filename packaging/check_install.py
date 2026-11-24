"""Looks at a computer after an installer ran, and says whether Brento is really there, or really gone.

    python packaging/check_install.py up      installed, running from its own folder, starting at sign-in
    python packaging/check_install.py down    removed: nothing running, nothing left but the settings

The release workflow runs this on real Macs and Windows computers before anything is published. Exit code 0 is good.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import launcher  # noqa: E402

WINDOWS = sys.platform == "win32"
HOME = Path.home()
if WINDOWS:
    BASE = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Brento"
    PYTHON = BASE / "python" / "python.exe"
    SHORTCUTS = [Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Brento.lnk"]
else:
    BASE = HOME / "Library" / "Application Support" / "Brento"
    PYTHON = BASE / "python" / "bin" / "Brento"
    SHORTCUTS = [HOME / "Applications" / "Brento.app", HOME / "Applications" / "Uninstall Brento.app",
                 HOME / ".local" / "bin" / "brento", HOME / "Library" / "LaunchAgents" / "app.brento.server.plist"]
FAILED = []


def check(good, text):
    print("%s  %s" % ("ok  " if good else "FAIL", text), flush=True)
    if not good:
        FAILED.append(text)


def get(path):
    with launcher.DIRECT.open(launcher.PAGE + path, timeout=90) as reply:
        return reply.status, reply.read()


def autostart():
    if WINDOWS:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                return str(winreg.QueryValueEx(key, "Brento")[0])
        except OSError:
            return ""
    return launcher.output(["launchctl", "print", "gui/%d/app.brento.server" % os.getuid()])


def up():
    check((BASE / "app" / "server.py").is_file(), "the program is in %s" % BASE)
    for path in SHORTCUTS:
        check(path.exists(), "there is %s" % path)
    ends = time.monotonic() + 60
    while not launcher.answers() and time.monotonic() < ends:
        time.sleep(1)
    check(launcher.answers(), "Brento answers on %s" % launcher.PAGE)
    if FAILED:
        log = HOME / ".brento" / "server.log"
        print(log.read_text(encoding="utf-8", errors="replace")[-2000:] if log.is_file() else "no server.log")
        return
    pid = launcher.listener()
    running = launcher.program_of(pid)
    check(str(BASE) in running, "it runs from its own folder: %s" % running)
    status, page = get("")
    check(status == 200 and b"Brento" in page, "the page loads")
    status, body = get("api/wizard")
    view = json.loads(body.decode("utf-8"))
    check(view["needed"] is True, "a new owner gets the setup")
    check("not installed" not in view["gh"]["reason"], "the GitHub program came along: %s" % (view["gh"]["reason"] or "ready"))
    started = subprocess.run([str(PYTHON), "-c", "import ssl, sys, urllib.request; print(sys.version.split()[0], "
                              "urllib.request.urlopen('https://api.github.com/zen', timeout=30).status)"], capture_output=True, text=True, timeout=60)
    check(started.stdout.strip().endswith(" 200"), "its own Python opens https pages: %s%s" % (started.stdout.strip(), started.stderr[-300:]))
    entry = autostart()
    check("launcher.py" in entry and "--start" in entry if WINDOWS else "state = running" in entry, "it starts at sign-in")


def down():
    ends = time.monotonic() + 30
    while (launcher.answers() or BASE.exists()) and time.monotonic() < ends:
        time.sleep(1)
    check(not launcher.answers(), "Brento no longer answers")
    for path in [BASE / "app" / "server.py", PYTHON] + SHORTCUTS:
        check(not path.exists(), "gone: %s" % path)
    if WINDOWS:
        check(not BASE.exists(), "gone: %s" % BASE)
        check(not autostart(), "gone: the start at sign-in")
    else:
        check(not BASE.exists(), "gone: %s" % BASE)
        check("state = running" not in autostart(), "gone: the start at sign-in")
    check((HOME / ".brento").is_dir(), "the settings folder stays")


if __name__ == "__main__":
    {"up": up, "down": down}[sys.argv[1]]()
    sys.exit(1 if FAILED else 0)
