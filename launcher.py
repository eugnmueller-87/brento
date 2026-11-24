#!/usr/bin/env python3
"""Opens Brento: makes sure it runs, then shows it. Every shortcut the installers make points here.

    launcher.py             start Brento when it is not running, then open it
    launcher.py --start     only start it (at sign-in)
    launcher.py --stop      stop the Brento that runs from this folder
    launcher.py --replace   stop whichever Brento this person has running first (after an install or an update)

There is no window and no terminal. What goes wrong is said in an ordinary message box, and the details are in
server.log in Brento's settings folder.
"""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import address  # noqa: E402
import settings  # noqa: E402

LABEL = "app.brento.server"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
MAX_LOG = 1024 * 1024


def output(args):
    try:
        return subprocess.run(args, capture_output=True, timeout=20, creationflags=NO_WINDOW,
                              stdin=subprocess.DEVNULL).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return ""


def listener():
    """The process that holds Brento's port, or 0. On a Mac or Linux only this person's own processes are seen."""
    number = address.port()
    if sys.platform == "win32":
        for line in output(["netstat", "-ano", "-p", "TCP"]).splitlines():
            part = line.split()
            # A listening socket has no remote end. Matching that instead of a word works in any Windows language.
            if len(part) >= 4 and part[1] == "127.0.0.1:%d" % number and part[2].endswith(":0") and part[-1].isdigit():
                return int(part[-1])
        return 0
    found = output(["/usr/sbin/lsof" if os.path.exists("/usr/sbin/lsof") else "lsof", "-nP", "-iTCP:%d" % number, "-sTCP:LISTEN", "-t"])
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


def installed():
    """The folder an installer made, or None for a copy of the source code."""
    base = HERE.parent
    return base if HERE.name == "app" and (base / "python").is_dir() else None


def ours(pid):
    """Whether a process belongs to this copy of Brento: a program of its own on Windows, its server file elsewhere."""
    program = program_of(pid)
    if sys.platform == "win32":
        base = installed()
        # The uninstaller lies in the same folder and must never count.
        return bool(base and program) and os.path.normcase(program).startswith(
            tuple(os.path.normcase(str(base / part)) + os.sep for part in ("python", "app")))
    return str(HERE / "server.py") in program


def every_pid():
    """All processes on Windows."""
    import ctypes
    from ctypes import wintypes
    psapi = ctypes.WinDLL("psapi")
    size = 2048
    while True:
        pids, used = (wintypes.DWORD * size)(), wintypes.DWORD()
        if not psapi.EnumProcesses(ctypes.byref(pids), ctypes.sizeof(pids), ctypes.byref(used)):
            return []
        count = used.value // ctypes.sizeof(wintypes.DWORD)
        if count < size:
            return [pid for pid in pids[:count] if pid]
        size *= 2


def end_helpers():
    """Ends what else still runs from this folder, such as a GitHub sign-in that waits for its code. On Windows a
    program that runs cannot be replaced or removed, so an update or a removal would fail on it."""
    if sys.platform != "win32" or not installed():
        return
    for pid in every_pid():
        if pid != os.getpid() and ours(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass


def agent():
    """The Mac's login service for Brento, when install.sh has set one up."""
    path = Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")
    return path if sys.platform == "darwin" and path.is_file() and not os.environ.get("BRENTO_PORT") else None


def launchctl(*args):
    try:
        return subprocess.run(["launchctl"] + list(args), capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def until(check, seconds):
    ends = time.monotonic() + seconds
    while time.monotonic() < ends:
        if check():
            return True
        time.sleep(0.3)
    return check()


def stop(any_brento=False):
    """Stops this person's Brento. Without any_brento only the one from this folder, so removing one copy never stops
    another. Someone else's Brento on the same computer is never touched."""
    if agent() and (any_brento or str(HERE / "server.py") in agent().read_text(encoding="utf-8", errors="replace")):
        # The service first, or it starts Brento again right away.
        launchctl("bootout", "gui/%d/%s" % (os.getuid(), LABEL))
    pid = listener()
    gone = True
    if pid and (ours(pid) or (any_brento and address.whose() in ("mine", "older"))):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return False
        gone = until(lambda: listener() != pid, 8)
    end_helpers()
    return gone


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
    forced = os.environ.get("BRENTO_PORT")
    args = [str(exe), "-X", "utf8", str(HERE / "server.py")] + (["--port", forced] if forced else [])
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
    """Makes sure this person's Brento runs. Returns '' or, in plain words, why it does not."""
    def mine():
        # Asked anew each time: a server that finds the usual port taken moves to the next free one and writes it down.
        return address.whose() == "mine"
    if mine():
        return ""
    if not agent() or not start_service(agent()):
        spawn()
    if until(mine, 60):
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
    page = address.entrance()
    if sys.platform == "win32":
        browser = app_window()
        if browser:
            subprocess.Popen([browser, "--app=" + page], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            os.startfile(page)
    elif sys.platform == "darwin":
        subprocess.run(["/usr/bin/open", page], check=False)
    else:
        subprocess.Popen(["xdg-open", page], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
    parser.add_argument("--replace", action="store_true", help="stop whichever Brento this person has running first")
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
