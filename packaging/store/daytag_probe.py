"""Only in test builds: measures, from inside the package, what a packaged Daytag can and cannot do. Writes one JSON file."""
import ctypes
import json
import os
import subprocess
import sys
import time
import traceback
import winreg
from ctypes import wintypes
from pathlib import Path

OUT = Path(os.environ["USERPROFILE"]) / ".daytag-probe"
NO_WINDOW, SUSPENDED = 0x08000000, 0x4
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.GetPackageFullName.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR)
k32.GetPackageFullName.restype = wintypes.LONG
k32.OpenProcess.argtypes, k32.OpenProcess.restype = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE
k32.CloseHandle.argtypes = (wintypes.HANDLE,)
k32.GetCurrentProcess.restype = wintypes.HANDLE
R = {}


def package(handle):
    n = wintypes.UINT(0)
    rc = k32.GetPackageFullName(handle, ctypes.byref(n), None)
    if rc == 15700:
        return ""
    buf = ctypes.create_unicode_buffer(max(n.value, 1))
    rc = k32.GetPackageFullName(handle, ctypes.byref(n), buf)
    return buf.value if rc == 0 else "error %d" % rc


def package_of(pid):
    handle = k32.OpenProcess(0x1000, False, pid)
    if not handle:
        return "cannot open"
    try:
        return package(handle)
    finally:
        k32.CloseHandle(handle)


def processes():
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, creationflags=NO_WINDOW).stdout.decode("utf-8", "replace")
    found = []
    for line in out.splitlines():
        part = [p.strip('"') for p in line.split('","')]
        if len(part) > 1 and part[1].isdigit():
            found.append((part[0].strip('"').lower(), int(part[1])))
    return found


def named(*names):
    return {pid: package_of(pid) for name, pid in processes() if name in names}


def step(name):
    def run(f):
        try:
            R[name] = f()
        except Exception:  # noqa: BLE001
            R[name] = "FAILED " + traceback.format_exc()[-400:]
        (OUT / "result.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
        return f
    return run


def held(args):
    """A child, stopped before its first instruction: which package is it in?"""
    proc = subprocess.Popen(args, creationflags=NO_WINDOW | SUSPENDED, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        return package(int(proc._handle))
    finally:
        proc.kill()


class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("r", wintypes.LPWSTR), ("d", wintypes.LPWSTR), ("t", wintypes.LPWSTR)] + [
        (n, wintypes.DWORD) for n in ("x", "y", "xs", "ys", "xc", "yc", "fill", "flags")] + [
        ("show", wintypes.WORD), ("cr2", wintypes.WORD), ("lr2", ctypes.c_void_p), ("i", wintypes.HANDLE), ("o", wintypes.HANDLE), ("e", wintypes.HANDLE)]


class StartupInfoEx(ctypes.Structure):
    _fields_ = [("base", StartupInfo), ("attributes", ctypes.c_void_p)]


class ProcInfo(ctypes.Structure):
    _fields_ = [("p", wintypes.HANDLE), ("t", wintypes.HANDLE), ("pid", wintypes.DWORD), ("tid", wintypes.DWORD)]


def breakaway(command, flags=0x01):
    """Started with the attribute that puts what IT starts outside of the package. Returns a handle and a pid."""
    size = ctypes.c_size_t(0)
    k32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    listed = ctypes.create_string_buffer(size.value)
    if not k32.InitializeProcThreadAttributeList(listed, 1, 0, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    policy = wintypes.DWORD(flags)
    k32.UpdateProcThreadAttribute.argtypes = (ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p)
    if not k32.UpdateProcThreadAttribute(listed, 0, 0x00020012, ctypes.byref(policy), 4, None, None):
        raise ctypes.WinError(ctypes.get_last_error())
    info = StartupInfoEx()
    info.base.cb = ctypes.sizeof(info)
    info.attributes = ctypes.cast(listed, ctypes.c_void_p)
    proc = ProcInfo()
    line = ctypes.create_unicode_buffer(command)
    if not k32.CreateProcessW(None, line, None, None, False, 0x00080000 | NO_WINDOW, None, None, ctypes.byref(info), ctypes.byref(proc)):
        raise ctypes.WinError(ctypes.get_last_error())
    return proc


def main():
    OUT.mkdir(exist_ok=True)

    @step("self")
    def _():
        return {"package": package(k32.GetCurrentProcess()), "exe": sys.executable, "cwd": os.getcwd(), "file": __file__, "path": sys.path,
                "resolved": str(Path(__file__).resolve()), "cached": __cached__ if "__cached__" in globals() else None}

    root = Path(__file__).resolve().parent
    gh = str(root / "bin" / "gh.exe")
    ping = os.path.join(os.environ["SystemRoot"], "System32", "PING.EXE")

    @step("child: gh.exe of the package")
    def _():
        return held([gh, "--version"])

    @step("gh runs")
    def _():
        return subprocess.run([gh, "--version"], capture_output=True, creationflags=NO_WINDOW, timeout=60).stdout.decode()[:80]

    @step("https")
    def _():
        import urllib.request
        return urllib.request.urlopen("https://github.com/robots.txt", timeout=30).status

    @step("time zones")
    def _():
        import datetime
        import zoneinfo
        return datetime.datetime(2026, 11, 26, 10, tzinfo=zoneinfo.ZoneInfo("America/New_York")).astimezone(datetime.timezone.utc).hour

    @step("gh config")
    def _():
        env = dict(os.environ, GH_PROMPT_DISABLED="1", GH_TELEMETRY="false")
        run = subprocess.run([gh, "config", "set", "prompt", "disabled"], capture_output=True, creationflags=NO_WINDOW, timeout=60, env=env)
        return run.returncode

    @step("child: ping.exe of Windows")
    def _():
        return held([ping, "-n", "3", "127.0.0.1"])

    @step("child of cmd: ping.exe")
    def _():
        subprocess.Popen(["cmd.exe", "/d", "/c", "ping -n 12 127.0.0.1"], creationflags=NO_WINDOW, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        time.sleep(2)
        return named("ping.exe")

    @step("breakaway: cmd itself and its ping")
    def _():
        before = set(named("ping.exe"))
        proc = breakaway("cmd.exe /d /c ping -n 12 127.0.0.1")
        time.sleep(2)
        return {"cmd": package(proc.p), "ping": {p: v for p, v in named("ping.exe").items() if p not in before}}

    @step("breakaway with cmd start: ping")
    def _():
        before = set(named("ping.exe"))
        breakaway('cmd.exe /d /c start "" /b ping -n 12 127.0.0.1')
        time.sleep(2)
        return {p: v for p, v in named("ping.exe").items() if p not in before}

    for label, flags in (("0x02 disable", 0x02), ("0x04 override", 0x04), ("0x05", 0x05)):
        @step("direct child with policy " + label)
        def _(flags=flags):
            proc = breakaway("ping.exe -n 6 127.0.0.1", flags)
            time.sleep(1)
            return package(proc.p)

    @step("browsers before")
    def _():
        return named("chrome.exe", "msedge.exe", "firefox.exe", "iexplore.exe")

    for rel in ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe"):
        for key in ("ProgramFiles", "ProgramFiles(x86)"):
            exe = Path(os.environ.get(key) or "") / rel
            if exe.is_file():
                @step("direct child: " + exe.name)
                def _(exe=exe):
                    return held([str(exe), "--app=about:blank"])

                @step("started like the icon does: " + exe.name)
                def _(exe=exe):
                    before = set(named(exe.name))
                    subprocess.Popen([str(exe), "--user-data-dir=" + str(OUT / exe.stem), "--no-first-run", "--app=about:blank"],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(8)
                    return {p: v for p, v in named(exe.name).items() if p not in before}

                @step("with its usual profile: " + exe.name)
                def _(exe=exe):
                    before = set(named(exe.name))
                    subprocess.Popen([str(exe), "--no-first-run", "--app=http://127.0.0.1:9/"],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(8)
                    return {p: v for p, v in named(exe.name).items() if p not in before}
                break

    @step("explorer.exe with an address")
    def _():
        names = ("chrome.exe", "msedge.exe", "firefox.exe")
        before = set(named(*names))
        subprocess.Popen(["explorer.exe", "http://127.0.0.1:9/explorer"], stdin=subprocess.DEVNULL)
        time.sleep(8)
        return {p: v for p, v in named(*names).items() if p not in before}

    @step("os.startfile with an address")
    def _():
        names = ("chrome.exe", "msedge.exe", "firefox.exe")
        before = set(named(*names))
        os.startfile("http://127.0.0.1:9/startfile")
        time.sleep(8)
        return {p: v for p, v in named(*names).items() if p not in before}

    @step("files written")
    def _():
        done = {}
        for label, path in (("new folder in Roaming", Path(os.environ["APPDATA"]) / "DaytagProbeSelf" / "a.txt"),
                            ("new folder in Local", Path(os.environ["LOCALAPPDATA"]) / "DaytagProbeSelf" / "a.txt"),
                            ("existing folder in Roaming", Path(os.environ["APPDATA"]) / "Microsoft" / "daytag-probe.txt"),
                            ("temp", Path(os.environ["TEMP"]) / "daytag-probe.txt"),
                            ("home", OUT / "a.txt")):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")
                done[label] = str(path)
            except OSError as exc:
                done[label] = "FAILED %s" % exc
        return done

    @step("files written by a child outside the package folder")
    def _():
        folder = Path(os.environ["APPDATA"]) / "DaytagProbeChild"
        run = subprocess.run('cmd.exe /d /c mkdir "%s" & echo x> "%s\\a.txt"' % (folder, folder), capture_output=True, creationflags=NO_WINDOW)
        return {"code": run.returncode, "path": str(folder), "said": (run.stdout + run.stderr).decode("utf-8", "replace")[-200:]}

    @step("registry")
    def _():
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\DaytagProbe") as key:
            winreg.SetValueEx(key, "a", 0, winreg.REG_SZ, "x")
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList") as listed:
            return {"profiles": winreg.QueryInfoKey(listed)[0]}

    @step("credentials")
    def _():
        class Cred(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                        ("LastWritten", wintypes.FILETIME), ("Size", wintypes.DWORD), ("Blob", ctypes.c_char_p), ("Persist", wintypes.DWORD),
                        ("Count", wintypes.DWORD), ("Attributes", ctypes.c_void_p), ("Alias", wintypes.LPWSTR), ("User", wintypes.LPWSTR)]
        cred = Cred(Type=1, TargetName="daytag-probe", Size=1, Blob=b"x", Persist=2, User="probe")
        return bool(ctypes.WinDLL("advapi32", use_last_error=True).CredWriteW(ctypes.byref(cred), 0))

    @step("RegisterApplicationRestart")
    def _():
        return k32.RegisterApplicationRestart(None, 0)

    @step("in the package now")
    def _():
        return {"%s %d" % (n, p): package_of(p) for n, p in processes() if package_of(p) not in ("", "cannot open")}

    R["done"] = True
    (OUT / "result.json").write_text(json.dumps(R, indent=1), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        OUT.mkdir(exist_ok=True)
        (OUT / "crash.txt").write_text(traceback.format_exc(), encoding="utf-8")
