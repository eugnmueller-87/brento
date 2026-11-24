"""Goes through the whole setup in a real browser, the way a person does who skips everything, and checks where it ends.

    python packaging/walk_setup.py safari,chrome pictures      the first browser that can be driven, of safari, edge, chrome

The release workflow runs this against the Brento the installer has just started. It needs the package selenium, which
nothing else here does. Exit code 0 is good.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import address  # noqa: E402
from selenium import webdriver  # noqa: E402
from selenium.common.exceptions import WebDriverException  # noqa: E402

PAGES = ["Welcome to ", "Your notes", "Your to-do board", "Your calendar", "Slack", "Your apps", "Brento is ready"]
NAME = "Test Person"
HEADING = "const h = document.querySelector('#wz h2'); return h ? h.textContent : '';"
FAILED = []


def check(good, text):
    print("%s  %s" % ("ok  " if good else "FAIL", text), flush=True)
    if not good:
        FAILED.append(text)
    return good


def until(test, seconds):
    ends = time.monotonic() + seconds
    while time.monotonic() < ends:
        if test():
            return True
        time.sleep(0.25)
    return False


def walk(browser, pictures):
    def heading():
        return browser.execute_script(HEADING) or ""

    def click(selector):
        return browser.execute_script("const b = document.querySelector(arguments[0]); if (b) b.click(); return !!b;", selector)

    browser.set_window_size(1100, 820)
    browser.get(address.page())
    check(until(lambda: "Open Brento with its icon" in browser.page_source, 20), "a browser that was not let in sees a locked page")
    browser.save_screenshot(str(pictures / "setup-0-locked.png"))
    browser.get(address.entrance())
    check(until(lambda: browser.current_url.split("#")[0] == address.page(), 20), "the ticket is gone from the address: %s" % browser.current_url)
    browser.execute_script("window.brentoErrors = []; addEventListener('error', (e) => brentoErrors.push(e.message));")
    for n, page in enumerate(PAGES):
        if not check(until(lambda: heading().startswith(page), 60), "page %d is %r" % (n + 1, page)):
            print("      it shows %r" % heading())
            return
        browser.save_screenshot(str(pictures / ("setup-%d.png" % (n + 1))))
        if page == PAGES[0]:
            browser.execute_script("const i = document.querySelector('#wz-name'); i.value = arguments[0]; i.dispatchEvent(new Event('input'));", NAME)
        if page == "Your calendar":
            # Away for a moment to copy the link, and back, while something else has changed: neither the page nor what
            # was typed may be gone.
            browser.execute_script("""
                const real = window.fetch;
                window.fetch = (url, options) => real(url, options).then(async (r) => String(url).includes('/api/state')
                  ? new Response(JSON.stringify(Object.assign(await r.json(), { walk: Math.random() })), { status: 200 }) : r);
                document.querySelector('#wz-cal').value = 'half typed'; document.dispatchEvent(new Event('visibilitychange'));""")
            time.sleep(4)
            kept = browser.execute_script("const i = document.querySelector('#wz-cal'); return i ? i.value : '';")
            check(heading() == page and kept == "half typed", "coming back to the setup keeps the page and what was typed")
            # Next instead of Connect: the link is tried, and the reason is on the page.
            click("#wz-next")
            check(until(lambda: "https link" in browser.execute_script("return document.querySelector('#wz').innerText"), 20)
                  and heading() == page, "a pasted link is tried and not thrown away")
        if page != PAGES[-1]:
            click("#wz-skip") or click("#wz-next")
    time.sleep(10)
    check(heading() == PAGES[-1], "the last page stays")
    browser.refresh()
    check(until(lambda: heading() == PAGES[-1], 30), "also after a reload")
    browser.execute_script("window.brentoErrors = []; addEventListener('error', (e) => brentoErrors.push(e.message));")
    check(click("#wz-home"), "there is a button that opens Brento")
    check(until(lambda: browser.execute_script("return location.hash") == "#home", 10), "it leads to Home")
    check(until(lambda: "Nothing is connected yet" in browser.page_source, 10), "Home says that nothing is connected yet")
    check(not browser.execute_script("return window.brentoErrors"), "no script failed")
    browser.refresh()
    time.sleep(4)
    check(browser.execute_script("return location.hash") in ("", "#home"), "after a reload it is still Home")
    browser.get(address.page())
    check(until(lambda: browser.execute_script("return !!document.querySelector('#deck')"), 20), "the plain address opens too: %r" % browser.title)
    browser.save_screenshot(str(pictures / "home.png"))
    _, view, _ = address.ask("api/setup", address.port(), address.key(), timeout=90)
    check(view.get("needed") is False and view["profile"]["name"] == NAME, "the answers are saved")


def chrome():
    """Without a window, because a virtual Mac without a graphics chip stops drawing one after a while."""
    options = webdriver.ChromeOptions()
    for flag in ("--headless=new", "--disable-gpu", "--no-first-run"):
        options.add_argument(flag)
    return webdriver.Chrome(options=options)


def drive(names):
    """A browser that can be driven. Safari's automation needs a few tries on a slow computer, and it cannot take over a
    Safari that is already open."""
    kinds = {"safari": webdriver.Safari, "edge": webdriver.Edge, "chrome": chrome}
    for name in names:
        for _ in range(3):
            if name == "safari":
                for program in ("Safari", "safaridriver"):
                    subprocess.run(["pkill", "-x", program], check=False)
                time.sleep(5)
            try:
                browser = kinds[name]()
                print("ok    driving %s %s" % (name, browser.capabilities.get("browserVersion", "")), flush=True)
                return browser
            except WebDriverException as exc:
                print("      %s could not be driven: %s" % (name, str(exc).strip().splitlines()[0][:160]), flush=True)
    raise SystemExit("No browser could be driven.")


def main():
    pictures = Path(sys.argv[2])
    pictures.mkdir(parents=True, exist_ok=True)
    browser = drive(sys.argv[1].split(","))
    try:
        walk(browser, pictures)
    finally:
        browser.quit()
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
