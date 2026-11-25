"""Pictures for the Store listing: the installed Daytag in its own window, with the window's frame, showing the sample notes.

    python packaging/store/shots.py <folder>

Run after "try_store.py samples", on a screen of 1920 x 1080. The Store wants pictures of the program itself, not drawings.
"""
import ctypes
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import address  # noqa: E402
from selenium import webdriver  # noqa: E402

PAGES = (("1-home", "#home", 9), ("2-today", "#today", 3), ("3-note", "#library/n/Work/Offer%20for%20the%20bakery.md", 4), ("4-library", "#library", 4),
         ("5-setup", "#setup/3", 4), ("6-settings", "#settings", 5))
ROOT = Path(__file__).resolve().parent.parent.parent
PHOTOS = {p["id"]: p for p in json.loads((ROOT / "web" / "photos" / "credits.json").read_text(encoding="utf-8"))}
GRAB = """Add-Type -AssemblyName System.Drawing
$i = New-Object System.Drawing.Bitmap %(w)d, %(h)d
[System.Drawing.Graphics]::FromImage($i).CopyFromScreen(%(x)d, %(y)d, 0, 0, $i.Size)
$i.Save('%(to)s')
"""


def main():
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    options = webdriver.EdgeOptions()
    options.add_argument("--app=" + address.entrance())
    options.add_argument("--no-first-run")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    browser = webdriver.Edge(options=options)
    try:
        browser.set_window_rect(60, 30, 1500, 940)
        time.sleep(6)
        size = browser.execute_script("return [screen.width, screen.height, devicePixelRatio]")
        print("screen", size)
        for name, page, wait in PAGES:
            browser.execute_script("location.hash = arguments[0]", page)
            # The mouse away from the page, where it would point at something.
            ctypes.windll.user32.SetCursorPos(1900, 1060)
            time.sleep(wait)
            r = browser.get_window_rect()
            # Windows counts an invisible border of 7 points on three sides, and draws a line of one point inside it.
            spot = {"x": r["x"] + 8, "y": r["y"], "w": r["width"] - 16, "h": r["height"] - 8, "to": str(out / (name + ".png"))}
            subprocess.run(["powershell", "-NoProfile", "-Command", GRAB % spot], check=True)
            print("ok   ", name, browser.title.encode("ascii", "replace").decode())
            for seen in browser.execute_script("return [...document.querySelectorAll('img.photo')].map((i) => i.src.split('/').pop().replace('.webp', ''))"):
                # For the caption: most of the photos may be shown only with their author's name.
                print("      photo:", PHOTOS[seen]["author"].encode("ascii", "replace").decode(), PHOTOS[seen]["license"], PHOTOS[seen]["source"])
    finally:
        browser.quit()


if __name__ == "__main__":
    main()
