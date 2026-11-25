"""Builds the Microsoft Store package: dist/Daytag-Store.msix. It is not signed, because Microsoft signs it.

    python packaging/store.py                       with the names the Store gave to Daytag (packaging/store/identity.json)
    python packaging/store.py --test                a package with test names, which only a test computer takes
    python packaging/store.py --test --version 0.2.1 --out dist/newer.msix --probe

It holds the same as the Windows installer. Needs Windows with the Windows SDK, as GitHub's Windows computers have it.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402

STORE = HERE / "store"
TEST = {"name": "DaytagTest.Daytag", "publisher": "CN=Daytag Test", "display": "Daytag Test"}
# Only in test builds: a second entry that measures what a package may do (packaging/store/daytag_probe.py).
PROBE = """    <Application Id="Probe" Executable="python\\pythonw.exe" EntryPoint="Windows.FullTrustApplication" uap10:Parameters="-m daytag_probe">
      <uap:VisualElements DisplayName="Daytag probe" Description="Measures" BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png" />
    </Application>
"""


def sdk(tool):
    """The newest one the Windows SDK on this computer has."""
    base = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits" / "10" / "bin"
    found = sorted(base.glob("10.*/x64/" + tool), key=lambda p: [int(n) for n in p.parts[-3].split(".")])
    if not found:
        raise SystemExit("%s is missing. It comes with the Windows SDK." % tool)
    return str(found[-1])


def store_version(text):
    """The Store wants four numbers, the first not 0 and the last 0: Daytag 0.2.0 is 1.2.0.0 there, 1.0.0 is 2.0.0.0."""
    major, minor, patch = (int(n) for n in text.split("."))
    return "%d.%d.%d.0" % (major + 1, minor, patch)


def identity(test):
    """The names the Store gave to Daytag when its name was reserved. They are in every published package anyway."""
    if test:
        return TEST
    path = STORE / "identity.json"
    if not path.is_file():
        raise SystemExit("%s is missing: the three names from Partner Center, Product identity. Or build with --test." % path)
    given = json.loads(path.read_text(encoding="utf-8"))
    if not re.match(r"^[A-Za-z0-9.-]{3,50}$", given.get("name", "")) or not given.get("publisher", "").startswith("CN=") or not given.get("display"):
        raise SystemExit("%s needs name, publisher (CN=...) and display." % path)
    return given


def manifest(names, version, probe):
    text = (STORE / "AppxManifest.xml").read_text(encoding="utf-8")
    quoted = {key: value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;") for key, value in names.items()}
    for key, value in (("{name}", quoted["name"]), ("{publisher}", quoted["publisher"]), ("{display}", quoted["display"]),
                       ("{version}", version), ("{probe}", PROBE if probe else "")):
        if text.count(key) != 1:
            raise SystemExit("%s is not once in the manifest." % key)
        text = text.replace(key, value)
    return text


def stage(folder, names, version, probe):
    """The folder makeappx packs: what the installer brings, the compiled program, the logos and the manifest."""
    build.stage_windows(folder)
    (folder / "daytag.ico").unlink()
    if probe:
        shutil.copyfile(str(STORE / "daytag_probe.py"), str(folder / "app" / "daytag_probe.py"))
    # Nobody can write into an installed package, so Python cannot keep its compiled files there later.
    subprocess.run([str(folder / "python" / "python.exe"), "-I", "-m", "compileall", "-q", "--invalidation-mode", "unchecked-hash",
                    "-s", str(folder), "-p", "daytag", str(folder / "app")], check=True)
    shutil.copytree(str(STORE / "Assets"), str(folder / "Assets"))
    (folder / "AppxManifest.xml").write_bytes(manifest(names, version, probe).encode("utf-8"))


def pri(folder):
    """The list of logos. Made from the logos alone: the other files are no resources."""
    only = folder.with_name(folder.name + "-logos")
    if only.exists():
        shutil.rmtree(str(only))
    shutil.copytree(str(folder / "Assets"), str(only / "Assets"))
    shutil.copyfile(str(folder / "AppxManifest.xml"), str(only / "AppxManifest.xml"))
    subprocess.run([sdk("makepri.exe"), "new", "/o", "/pr", str(only), "/cf", str(STORE / "priconfig.xml"), "/mn", str(only / "AppxManifest.xml"),
                    "/of", str(folder / "resources.pri")], check=True, stdout=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=str(build.DIST / "Daytag-Store.msix"))
    parser.add_argument("--test", action="store_true", help="with test names")
    parser.add_argument("--version", help="instead of the one in VERSION, as 0.2.0")
    parser.add_argument("--probe", action="store_true", help="with the entry that measures")
    args = parser.parse_args()
    if args.probe and not args.test:
        parser.error("--probe is for --test only")
    version = store_version(args.version or build.version(build.program_files()))
    folder = build.DIST / "stage-store"
    stage(folder, identity(args.test), version, args.probe)
    pri(folder)
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sdk("makeappx.exe"), "pack", "/o", "/h", "SHA256", "/d", str(folder), "/p", str(out)], check=True, stdout=subprocess.DEVNULL)
    print("%s  %s  %.1f MB" % (out, version, out.stat().st_size / 1048576.0))


if __name__ == "__main__":
    main()
