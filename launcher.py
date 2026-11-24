#!/usr/bin/env python3
"""Opens Brento: makes sure it runs, then shows it. Every shortcut the installers make points here.

    launcher.py             start Brento when it is not running, then open it
    launcher.py --start     only start it (at sign-in)
    launcher.py --stop      stop the Brento that runs from this folder
    launcher.py --replace   stop whichever Brento answers on this computer first (after an install or an update)

There is no window and no terminal. What goes wrong is said in an ordinary message box, and the details are in
server.log in Brento's settings folder.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import settings  # noqa: E402

PORT = int(os.environ.get("BRENTO_PORT") or 8770)
PAGE = "http://127.0.0.1:%d/" % PORT
LABEL = "app.brento.server"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
MAX_LOG = 1024 * 1024
# The page never goes through a proxy: it is on this computer.
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def answers(timeout=2.0):
    """True when a Brento answers here. Another program on the same port does not count."""
    try:
        with DIRECT.open(PAGE + "api/tools", timeout=timeout) as reply:
            return isinstance(json.loads(reply.read().decode("utf-8")).get("tools"), list)
    except (OSError, ValueError, AttributeError):
        return False


def output(args):
    try:
        return subprocess.run(args, capture_output=True, timeout=20, creationflags=NO_WINDOW,
                              stdin=subprocess.DEVNULL).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return ""


def listener():
    """The process that holds Brento's port, or 0."""
    if sys.platform == "win32":
        for line in output(["netstat", "-ano", "-p", "TCP"]).splitlines():
            part = line.split()
            # A listening socket has no remote end. Matching that instead of a word works in any Windows language.
            if len(part) >= 4 and part[1] == "127.0.0.1:%d" % PORT and part[2].endswith(":0") and part[-1].isdigit():
                return int(part[-1])
        return 0
    found = output(["/usr/sbin/lsof" if os.path.exists("/usr/sbin/lsof") else "lsof", "-nP", "-iTCP:%d" % PORT, "-sTCP:LISTEN", "-t"])
    return int(found.split()[0]) if found.split() and found.split()[0].isdigit() else 0


def program_of(pid):
    """What a process runs: the program's path on Windows, its whole command line elsewhere."""
    if sys.platform != "win32":
        return output(["ps", "-ww", "-p", str(pid), "-o", "command="]).strip()
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                  ctypes.POINTER(wintypes.DWORD))
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        name = ctypes.create_unicode_buffer(size.value)
        return name.value if kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)) else ""
    finally:
        kernel.CloseHandle(handle)


def ours(pid):
    """Whether a process belongs to this copy of Brento: its Python on Windows, its server file elsewhere."""
    program = program_of(pid)
    if sys.platform == "win32":
        return bool(program) and os.path.normcase(program).startswith(os.path.normcase(str(HERE.parent)) + os.sep)
    return str(HERE / "server.py") in program


def agent():
    """The Mac's login service for Brento, when install.sh has set one up."""
    path = Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")
    return path if sys.platform == "darwin" and path.is_file() and PORT == 8770 else None


def launchctl(*args):
    try:
        return subprocess.run(["launchctl"] + list(args), capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def wait(for_answer, seconds):
    ends = time.monotonic() + seconds
    while time.monotonic() < ends:
        if answers() == for_answer and (for_answer or not listener()):
            return True
        time.sleep(0.3)
    return answers() == for_answer


def stop(any_brento=False):
    """Stops the Brento on this port. Without any_brento only the one from this folder, so removing one copy never
    stops another."""
    if agent() and (any_brento or str(HERE / "server.py") in agent().read_text(encoding="utf-8", errors="replace")):
        # The service first, or it starts Brento again right away.
        launchctl("bootout", "gui/%d/%s" % (os.getuid(), LABEL))
    pid = listener()
    if pid and (ours(pid) or (any_brento and answers())):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return False
    return not pid or wait(False, 8)


def spawn():
    home = settings.home()
    home.mkdir(parents=True, exist_ok=True)
    log = home / "server.log"
    mode = "ab" if log.is_file() and log.stat().st_size < MAX_LOG else "wb"
    exe = Path(sys.executable)
    if sys.platform == "win32" and exe.name.lower() == "pythonw.exe":
        # The server writes to its log, which the windowless Python has no way to.
        exe = exe.with_name("python.exe")
    # UTF-8 whatever the computer's language, so a folder name with any letter in it can be written to the log.
    args = [str(exe), "-X", "utf8", str(HERE / "server.py")] + ([] if PORT == 8770 else ["--port", str(PORT)])
    extra = {"creationflags": NO_WINDOW | 0x200} if sys.platform == "win32" else {"start_new_session": True}
    with open(str(log), mode) as out:
        subprocess.Popen(args, cwd=str(HERE), stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, **extra)


def start_service(plist):
    """Starts the Mac's login service. Right after a stop, macOS needs a moment before it takes the service back."""
    target = "gui/%d" % os.getuid()
    for _ in range(10):
        if launchctl("kickstart", "%s/%s" % (target, LABEL)) or launchctl("bootstrap", target, str(plist)):
            return True
        time.sleep(0.5)
    return False


def start():
    """Makes sure Brento runs. Returns '' or, in plain words, why it does not."""
    if answers():
        return ""
    if listener():
        return ("Another program on this computer uses the connection Brento needs (port %d). "
                "Close that program, or restart the computer, and open Brento again." % PORT)
    if not agent() or not start_service(agent()):
        spawn()
    if wait(True, 30):
        return ""
    return "Brento did not start. What went wrong is in this file:\n%s" % (settings.home() / "server.log")


def app_window():
    """A browser that shows Brento as its own window. Chrome first, because it holds the sign-ins of the dock's apps."""
    for rel in ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe"):
        for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            path = Path(os.environ.get(key) or "") / rel
            if os.environ.get(key) and path.is_file():
                return str(path)
    return ""


def show():
    if os.environ.get("BRENTO_NO_BROWSER"):
        return
    if sys.platform == "win32":
        browser = app_window()
        if browser:
            subprocess.Popen([browser, "--app=" + PAGE], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            os.startfile(PAGE)
    elif sys.platform == "darwin":
        subprocess.run(["/usr/bin/open", PAGE], check=False)
    else:
        subprocess.Popen(["xdg-open", PAGE], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def tell(text):
    """An ordinary message box. Nothing is asked."""
    if sys.stderr:
        print(text, file=sys.stderr)
    if os.environ.get("BRENTO_NO_BROWSER"):
        return
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "Brento", 0x30)
    elif sys.platform == "darwin":
        script = ('on run argv\ntell current application to activate\ndisplay dialog (item 1 of argv) with title "Brento" '
                  'buttons {"OK"} default button 1 with icon caution\nend run')
        subprocess.run(["/usr/bin/osascript", "-e", script, text], check=False, capture_output=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Opens Brento")
    parser.add_argument("--start", action="store_true", help="only start it, do not open it")
    parser.add_argument("--stop", action="store_true", help="stop the one from this folder")
    parser.add_argument("--replace", action="store_true", help="stop whichever Brento runs first")
    args = parser.parse_args(argv)
    if args.stop:
        return 0 if stop() else 1
    if args.replace:
        stop(any_brento=True)
    problem = start()
    if problem:
        # At sign-in nobody asked for anything, so nothing pops up.
        if not args.start:
            tell(problem)
        return 1
    if not args.start:
        show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
