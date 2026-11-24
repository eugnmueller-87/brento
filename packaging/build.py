"""Builds the installers: one file per system, with everything inside.

    python packaging/build.py mac        dist/Brento-Mac.pkg, on any computer
    python packaging/build.py windows    dist/Brento-Windows.exe, on Windows with Inno Setup 6
    python packaging/build.py windows --iscc "<path to ISCC.exe>"
    python packaging/build.py windows --preview    a test build with its own name and folder, without start at sign-in

Each one holds Brento, its own Python and the GitHub program, so the computer needs nothing beforehand. The downloads
are pinned in runtimes.json by address and SHA-256, and a file that differs stops the build.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import macpkg  # noqa: E402

DIST = ROOT / "dist"
CACHE = Path(os.environ.get("BRENTO_BUILD_CACHE") or HERE / "cache")
RUNTIMES = json.loads((HERE / "runtimes.json").read_text(encoding="utf-8"))
MTIME = 1767225600  # one fixed date on every packed file, so the same input gives the same output
# What belongs to the program itself. Everything else in the repository is for people who change it.
SKIP_DIRS = ("tests/", "docs/", "packaging/", "scripts/", "design/", "desktop/", ".github/")
KEEP_PLAIN = {"LICENSE", "VERSION", "install.sh", "tools.catalog.json", "tools.default.json", "projects.default.json",
              "ask-settings.json", "windows-zones.json", "team.json", "team.example.json"}
# Parts of Python that Brento never uses.
PYTHON_DROP = re.compile(r"^python/(include|share)/|^python/lib/(tcl|tk|itcl|thread|lib(tcl|tk|python))|^python/lib/pkgconfig/|"
                         r"^python/lib/python3\.\d+/(site-packages|ensurepip|idlelib|tkinter|turtledemo|test|pydoc_data|lib2to3|"
                         r"config-[^/]*|__pycache__)/|^python/lib/python3\.\d+/lib-dynload/_tkinter|^python/lib/python3\.\d+/turtle\.py$|/__pycache__/")
THIRD_PARTY = """Brento's installer brings these programs along, each under its own license. From Python it leaves out
what Brento does not use:

Python {python}          https://www.python.org/             license: python/{python_license}
{more}GitHub CLI {gh}        https://cli.github.com/             license: app/bin/LICENSE-gh.txt
Photos on the cards    Wikimedia Commons                   authors and licenses: app/web/photos/CREDITS.md
Time zone names        https://cldr.unicode.org/           license: licenses/LICENSE.unicode.txt

Brento itself: app/LICENSE
"""
# Libraries inside the Mac's Python, whose publisher keeps the license texts beside it and not in it.
MORE_MAC = """Inside that Python: OpenSSL, libffi, expat, mpdecimal, zstd, bzip2, liblzma, SQLite and libuuid
                       https://github.com/astral-sh/python-build-standalone     licenses: licenses/
"""
MORE_WINDOWS = """Time zones {tzdata}      https://pypi.org/project/tzdata/    license: python/tzdata/LICENSE.txt
"""


def fetch(key):
    """A pinned download, kept in the cache and checked every time."""
    entry = RUNTIMES[key]
    name = unquote(entry["url"].rsplit("/", 1)[1])
    target = CACHE / name
    if not target.is_file():
        CACHE.mkdir(parents=True, exist_ok=True)
        print("downloading", name)
        request = urllib.request.Request(entry["url"], headers={"User-Agent": "Brento-build"})
        with urllib.request.urlopen(request, timeout=300) as answer:
            part = target.with_name(name + ".part")
            part.write_bytes(answer.read())
            part.replace(target)
    data = target.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise SystemExit("%s does not match its checksum. Delete %s and look at the publisher's list before changing runtimes.json." % (name, target))
    return data


def program_files(root=ROOT):
    """The tracked files that make up the program, as {path: bytes}. Windows line endings never reach a shell script."""
    listed = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
    out = {}
    for rel in listed.decode("utf-8").split("\0"):
        if not rel or rel.startswith(SKIP_DIRS):
            continue
        if not (rel in KEEP_PLAIN or rel.startswith("web/") or re.match(r"^[a-z_]+\.py$", rel)):
            continue
        data = (Path(root) / rel).read_bytes()
        if Path(rel).suffix in (".py", ".sh", ".js", ".css", ".html", ".json", ".md", ".svg", ".webmanifest", ""):
            data = data.replace(b"\r\n", b"\n")
        out[rel] = data
    for needed in ("server.py", "launcher.py", "web/index.html", "VERSION", "LICENSE"):
        if needed not in out:
            raise SystemExit("%s is missing from the program files, so nothing is built." % needed)
    return out


def version(files):
    text = files["VERSION"].decode("utf-8").strip()
    if not re.match(r"^\d+\.\d+\.\d+$", text):
        raise SystemExit("VERSION is not a number like 0.2.0: %r" % text)
    return text


def gh_parts(key, program):
    """The GitHub program and its license out of the publisher's zip."""
    with zipfile.ZipFile(io.BytesIO(fetch(key))) as archive:
        names = archive.namelist()
        body = archive.read(next(n for n in names if n.endswith("bin/" + program)))
        license_text = archive.read(next(n for n in names if n.endswith("LICENSE")))
    return body, license_text


def targz(entries):
    """entries: (path, mode, bytes or None, link target). One fixed date and owner on everything."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as out:
        for path, mode, data, link in entries:
            info = tarfile.TarInfo(path)
            info.mode, info.mtime, info.uid, info.gid, info.uname, info.gname = mode, MTIME, 0, 0, "", ""
            if link:
                info.type, info.linkname = tarfile.SYMTYPE, link
                out.addfile(info)
            else:
                info.size = len(data)
                out.addfile(info, io.BytesIO(data))
    return gzip.compress(raw.getvalue(), 9, mtime=0)


def mac_runtime(chip, files):
    """Python for one chip, without what Brento never uses, plus the GitHub program.

    The Python program is called Brento here, because macOS shows a program's file name when it asks for access to a
    folder and when it lists what runs in the background. "python3.14" would tell nobody what that is."""
    entries = []
    with tarfile.open(fileobj=io.BytesIO(fetch("python-mac-" + chip)), mode="r:gz") as source:
        members = {m.name: m for m in source.getmembers()}
        program = next(n for n in members if re.match(r"^python/bin/python3\.\d+$", n) and members[n].isfile())
        entries.append(("python/bin/Brento", 0o755, source.extractfile(members[program]).read(), ""))
        entries.append(("python/bin/python3", 0o777, None, "Brento"))
        for name in sorted(members):
            member = members[name]
            if not name.startswith("python/lib/") or PYTHON_DROP.search(name) or member.isdir():
                continue
            if member.issym():
                entries.append((name, 0o777, None, member.linkname))
            elif member.isfile():
                entries.append((name, 0o755 if member.mode & 0o100 else 0o644, source.extractfile(member).read(), ""))
    gh, license_text = gh_parts("gh-mac-" + chip, "gh")
    entries.append(("app/bin/gh", 0o755, gh, ""))
    entries.append(("app/bin/LICENSE-gh.txt", 0o644, license_text, ""))
    stdlib = next(n.split("/")[2] for n in members if re.match(r"^python/lib/python3\.\d+/LICENSE\.txt$", n))
    notice = THIRD_PARTY.format(python=RUNTIMES["python-mac-" + chip]["version"], gh=RUNTIMES["gh-mac-" + chip]["version"],
                                python_license="lib/%s/LICENSE.txt" % stdlib, more=MORE_MAC)
    entries.append(("THIRD-PARTY.txt", 0o644, notice.encode("utf-8"), ""))
    for path in sorted((HERE / "mac" / "licenses").glob("*.txt")) + sorted((HERE / "licenses").glob("*.txt")):
        entries.append(("licenses/" + path.name, 0o644, path.read_bytes().replace(b"\r\n", b"\n"), ""))
    return targz(entries), sum(len(e[2]) for e in entries if e[2])


def build_mac():
    files = program_files()
    ver = version(files)
    program = targz([("app/" + rel, 0o755 if rel == "install.sh" else 0o644, data, "") for rel, data in sorted(files.items())])
    size = sum(len(d) for d in files.values())
    scripts = {"postinstall": ((HERE / "mac" / "postinstall").read_bytes().replace(b"\r\n", b"\n"), True),
               "brento.tar.gz": (program, False)}
    largest = 0
    for chip in ("arm64", "x86_64"):
        packed, unpacked = mac_runtime(chip, files)
        scripts["runtime-%s.tar.gz" % chip] = (packed, False)
        largest = max(largest, unpacked)
        print("  %s: %.1f MB" % (chip, len(packed) / 1048576.0))
    kbytes = (size + largest) // 1024
    distribution = (HERE / "mac" / "Distribution.xml").read_text(encoding="utf-8").replace("{version}", ver).replace("{kbytes}", str(kbytes))
    resources = {}
    for path in sorted((HERE / "mac").rglob("*.html")):
        resources[path.relative_to(HERE / "mac").as_posix()] = path.read_bytes().replace(b"\r\n", b"\n")
    DIST.mkdir(exist_ok=True)
    target = DIST / "Brento-Mac.pkg"
    macpkg.write(target, distribution.encode("utf-8"), resources, "brento.pkg",
                 macpkg.package_info("app.brento.pkg", ver, kbytes), macpkg.scripts_archive(scripts))
    # Read back what was written: every checksum, and the script Apple's Installer will start.
    inside = macpkg.read_xar(target.read_bytes())
    unpacked = macpkg.read_scripts(inside["brento.pkg/Scripts"])
    if unpacked["./postinstall"][0] != 0o100755 or set(unpacked) != {"."} | {"./" + n for n in scripts}:
        raise SystemExit("The package does not read back as written.")
    return target, ver


def find_iscc(given):
    places = [given, os.environ.get("ISCC"), shutil.which("ISCC"),
              os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Inno Setup 6", "ISCC.exe"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe")]
    for place in places:
        if place and Path(place).is_file():
            return place
    raise SystemExit("Inno Setup 6 is needed to build the Windows installer: https://jrsoftware.org/isdl.php")


def stage_windows(stage):
    """The folder Inno Setup packs: app, python and the license notes."""
    files = program_files()
    ver = version(files)
    if stage.exists():
        shutil.rmtree(str(stage))
    for rel, data in files.items():
        if rel == "install.sh":
            continue
        target = stage / "app" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    python = stage / "python"
    python.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(fetch("python-windows-x64"))) as archive:
        for name in archive.namelist():
            if "/" in name or "\\" in name or name.startswith("."):
                raise SystemExit("Unexpected file in the Python download: %s" % name)
            (python / name).write_bytes(archive.read(name))
    # Windows itself has no time zone data in the form Python reads.
    with zipfile.ZipFile(io.BytesIO(fetch("tzdata"))) as archive:
        for name in archive.namelist():
            if name.startswith("tzdata/") and not name.endswith("/") and ".." not in name:
                target = python / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
        texts = [archive.read(n) for n in sorted(archive.namelist()) if re.search(r"dist-info/licenses/.*LICENSE[^/]*$", n)]
        if not texts or not (python / "tzdata" / "zoneinfo" / "America" / "New_York").is_file():
            raise SystemExit("The time zone data does not look as expected.")
        (python / "tzdata" / "LICENSE.txt").write_bytes(b"\n\n".join(texts))
    paths = next(python.glob("python3*._pth"))
    # This Python looks for modules in these places only, so nothing else on the computer can get in its way.
    paths.write_text("%s.zip\n.\n..\\app\n" % paths.stem, encoding="ascii")
    gh, license_text = gh_parts("gh-windows-x64", "gh.exe")
    (stage / "app" / "bin").mkdir()
    (stage / "app" / "bin" / "gh.exe").write_bytes(gh)
    (stage / "app" / "bin" / "LICENSE-gh.txt").write_bytes(license_text)
    notice = THIRD_PARTY.format(python=RUNTIMES["python-windows-x64"]["version"], gh=RUNTIMES["gh-windows-x64"]["version"],
                                python_license="LICENSE.txt", more=MORE_WINDOWS.format(tzdata=RUNTIMES["tzdata"]["version"]))
    (stage / "THIRD-PARTY.txt").write_text(notice, encoding="utf-8")
    shutil.copytree(str(HERE / "licenses"), str(stage / "licenses"))
    shutil.copyfile(str(HERE / "windows" / "brento.ico"), str(stage / "brento.ico"))
    return ver


def build_windows(iscc, preview):
    compiler = find_iscc(iscc)
    stage = DIST / "stage-windows"
    ver = stage_windows(stage)
    args = [compiler, "/Qp", "/DAppVersion=" + ver, "/DStage=" + str(stage), "/DOutput=" + str(DIST)]
    if preview:
        args.append("/DPreview")
    subprocess.run(args + [str(HERE / "windows" / "brento.iss")], check=True)
    return DIST / ("Brento-Windows-Preview.exe" if preview else "Brento-Windows.exe"), ver


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("system", choices=("mac", "windows"))
    parser.add_argument("--iscc", help="the path to Inno Setup's ISCC.exe")
    parser.add_argument("--preview", action="store_true", help="a Windows test build that leaves an installed Brento alone")
    args = parser.parse_args()
    target, ver = build_mac() if args.system == "mac" else build_windows(args.iscc, args.preview)
    data = target.read_bytes()
    print("%s  %s  %.1f MB\nsha256 %s" % (target, ver, len(data) / 1048576.0, hashlib.sha256(data).hexdigest()))


if __name__ == "__main__":
    main()
