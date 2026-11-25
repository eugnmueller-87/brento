"""Looks, from outside, at a Daytag that was installed as a Store package. The release workflow runs it on real Windows.

    python packaging/try_store.py up <folder>        installed, opened from the Start menu, setup still to do
    python packaging/try_store.py kept <folder>      the same, and the setup someone has already done is still there
    python packaging/try_store.py samples            the sample notes work without any account
    python packaging/try_store.py probe              what the test entry measured inside the package
    python packaging/try_store.py twice <folder>     the Daytag from GitHub runs too: the one that was opened took over
    python packaging/try_store.py other              "Remove that one" opens the uninstaller of the Daytag from GitHub
    python packaging/try_store.py quit               "Quit Daytag" ends it, so that a waiting update can come
    python packaging/try_store.py forget             "Delete what Daytag saved" leaves nothing and ends Daytag
    python packaging/try_store.py gone               removed: nothing running, nothing left

Exit code 0 is good.
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import time
import winreg
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_install  # noqa: E402
import address  # noqa: E402
import launcher  # noqa: E402

NAME = "DaytagTest.Daytag"
HOME = Path.home() / ".daytag"
check = check_install.check
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.GetPackageFullName.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR)
k32.GetPackageFullName.restype = wintypes.LONG
k32.OpenProcess.argtypes, k32.OpenProcess.restype = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE
k32.CloseHandle.argtypes = (wintypes.HANDLE,)


def package_of(pid):
    """The package a process runs in, '' for none."""
    handle = k32.OpenProcess(0x1000, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.UINT(0)
        if k32.GetPackageFullName(handle, ctypes.byref(size), None) == 15700:
            return ""
        text = ctypes.create_unicode_buffer(max(size.value, 1))
        return text.value if k32.GetPackageFullName(handle, ctypes.byref(size), text) == 0 else ""
    finally:
        k32.CloseHandle(handle)


def inside():
    """The programs that run in the package."""
    return {pid: launcher.program_of(pid) for pid in launcher.every_pid() if package_of(pid).startswith(NAME)}


def family():
    return subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-AppxPackage %s).PackageFamilyName" % NAME],
                          capture_output=True, text=True).stdout.strip()


def startup():
    path = r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\SystemAppData\%s\DaytagStart" % family()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return winreg.QueryValueEx(key, "State")[0]
    except OSError:
        return None


def up(kept=False):
    base = Path(sys.argv[2])
    check_install.BASE, check_install.SHORTCUTS, check_install.RUNNABLE = base, [], False
    # 2 is switched on.
    check_install.autostart = lambda: "launcher.py --start" if startup() == 2 else ""
    check_install.up(kept)
    pid = launcher.listener()
    check(package_of(pid).startswith(NAME), "the server runs inside the package: %s" % package_of(pid))
    check((base / "AppxManifest.xml").is_file() and (base / "resources.pri").is_file(), "the package has its manifest and its logos")
    setup = address.ask("api/setup", address.port(), address.key(), timeout=90)[1]
    check(setup.get("store") is True, "Daytag knows that it came from the Store")
    check(setup["profile"]["autostart"] is kept, "it starts at sign-in only after a yes: %s" % setup["profile"]["autostart"])
    status, answer, _ = address.ask("api/phone", address.port(), address.key(), data=b'{"action": "on"}', timeout=30)
    check(status == 400, "there is no phone door: %s %s" % (status, answer))


def samples():
    status, answer, _ = address.ask("api/wizard/sample", address.port(), address.key(), data=b"{}", timeout=30)
    check(status == 200 and os.path.isdir(answer.get("path", "")), "the sample notes are written: %s" % answer)
    profile = {"profile": {"name": "Test Person", "vault": answer.get("path", ""),
                           "sources": {"library": {"on": True}, "tasks": {"on": True}, "calendar": {"on": True}, "board": {"on": False}}}}
    status, _, _ = address.ask("api/setup", address.port(), address.key(), data=json.dumps(profile).encode("utf-8"), timeout=90)
    check(status == 200, "they can be chosen")
    ends, cards = time.monotonic() + 60, []
    while time.monotonic() < ends and len(cards) < 6:
        time.sleep(1)
        state = address.ask("api/state", address.port(), address.key(), timeout=60)[1]
        cards = [c.get("title", "") for c in state.get("alerts") or []]
    check(any("bakery" in c for c in cards) and len(cards) >= 6, "Home shows what is due: %s" % cards)


def probe():
    folder = Path.home() / ".daytag-probe"
    ends, seen = time.monotonic() + 180, {}
    while time.monotonic() < ends and not seen.get("done"):
        time.sleep(2)
        try:
            seen = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    print(json.dumps(seen, indent=1))
    check(seen.get("done"), "the test entry went through")
    pinned = json.loads((check_install.ROOT / "packaging" / "runtimes.json").read_text(encoding="utf-8"))
    check(pinned["gh-windows-x64"]["version"] in str(seen.get("gh runs")), "the GitHub program that came along runs")
    check(seen.get("https") == 200, "its own Python opens https pages")
    check(seen.get("time zones") == 15, "its own Python knows other time zones")
    outside = [seen.get(k) for k in ("child: ping.exe of Windows", "direct child: msedge.exe", "direct child: chrome.exe")]
    check(outside == ["", "", ""], "browsers and other programs run outside the package: %r" % outside)
    check(str(seen.get("child: gh.exe of the package")).startswith(NAME), "the GitHub program runs inside")
    private = Path(os.environ["LOCALAPPDATA"]) / "Packages" / family() / "LocalCache"
    real = Path(os.environ["APPDATA"]) / "GitHub CLI" / "config.yml"
    check((private / "Roaming" / "GitHub CLI" / "config.yml").is_file() and not real.is_file(), "what it keeps lies in the package's own folder")
    rules = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules") as key:
        rules = [winreg.EnumValue(key, n)[1] for n in range(winreg.QueryInfoKey(key)[1])]
    rules = [r for r in rules if NAME in str(r) and "Action=Allow" in r]
    check(not rules, "the firewall stays closed: %s" % rules)
    found = ctypes.c_void_p()
    check(ctypes.windll.advapi32.CredReadW("daytag-probe", 1, 0, ctypes.byref(found)), "a sign-in is kept where Windows keeps all of them")


def twice():
    base, ends = sys.argv[2], time.monotonic() + 60
    while time.monotonic() < ends and base not in launcher.program_of(launcher.listener()):
        time.sleep(1)
    check(base in launcher.program_of(launcher.listener()), "the one from the Store answers: %s" % launcher.program_of(launcher.listener()))
    setup = address.ask("api/setup", address.port(), address.key(), timeout=90)[1]
    check(setup.get("store") is True and setup.get("twice") is True, "and it knows about the other one")


def other():
    status, answer, _ = address.ask("api/remove-other", address.port(), address.key(), data=b"{}", timeout=30)
    check((status, answer) == (200, {"opened": True}), "it answers: %s %s" % (status, answer))
    ends, seen = time.monotonic() + 40, {}
    while time.monotonic() < ends and not seen:
        time.sleep(1)
        seen = {pid: launcher.program_of(pid) for pid in launcher.every_pid()}
        seen = {pid: path for pid, path in seen.items() if re.search(r"[\\/](unins\d{3}\.exe|_iu\w+\.tmp)$", path, re.I)}
    check(bool(seen) and not any(package_of(pid) for pid in seen), "the uninstaller asks, outside the package: %s" % seen)


def ended():
    ends = time.monotonic() + 20
    while time.monotonic() < ends and (address.whose() or inside()):
        time.sleep(1)
    check(not address.whose() and not inside(), "Daytag has ended")


def quit_():
    status, answer, _ = address.ask("api/quit", address.port(), address.key(), data=b"{}", timeout=30)
    check((status, answer) == (200, {"ended": True}), "it answers: %s %s" % (status, answer))
    ended()


def forget():
    status, answer, _ = address.ask("api/forget", address.port(), address.key(), data=b'{"delete": true}', timeout=30)
    check((status, answer) == (200, {"deleted": True, "left": []}), "it answers: %s %s" % (status, answer))
    ended()
    left = sorted(str(p.relative_to(HOME)) for p in HOME.rglob("*") if p.is_file()) if HOME.is_dir() else []
    check(left in ([], ["server.log"]), "nothing is left but an empty log: %s" % left)
    check(not left or (HOME / "server.log").stat().st_size == 0, "and it is empty")


def gone():
    ends = time.monotonic() + 30
    while (address.whose() or inside()) and time.monotonic() < ends:
        time.sleep(2)
    check(not address.whose(), "Daytag no longer answers")
    check(not inside(), "nothing runs in the package any more")
    check(HOME.is_dir(), "the settings folder stays")
    left = [str(p) for p in (Path(os.environ["LOCALAPPDATA"]) / "Packages").glob(NAME + "*")]
    check(not left, "gone: the package's own folder %s" % (left or ""))


if __name__ == "__main__":
    {"up": up, "kept": lambda: up(True), "samples": samples, "probe": probe, "twice": twice, "other": other, "quit": quit_,
     "forget": forget, "gone": gone}[sys.argv[1]]()
    sys.exit(1 if check_install.FAILED else 0)
