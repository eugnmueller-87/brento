# Building your own Brento

Brento is small on purpose: about ten files, the Python standard library, plain JavaScript, no build step. This page
is the map for changing it.

## How a request flows

```
browser (web/app.js)  --GET /api/state-->  server.py  -->  sources.build_state()
                                                             |-- one reader per source, each returns (data, source)
                                                             |-- build_cards / build_alerts / build_focus / build_schedule
                                                             '-- the page draws what comes back, nothing more
```

The page never decides what is important. The server sends finished cards, each with its reason (`why`) and the
age of its source, and the page draws them.

## Where things are

| File | What it does |
|---|---|
| `server.py` | Local web server on 127.0.0.1:8770. Serves the page and the JSON API; refuses foreign hosts and cross-site posts |
| `settings.py` | The owner's settings (`~/.brento/brento.json`), the list of sources, the team file (`team.json`) |
| `sources.py` | One reader per source, and the rules that rank cards for Home, Today and the schedule check |
| `wizard.py` | The first-start wizard's guesses and its few actions: create a board, run a sign-in without a window, fetch the GitHub program where the installer did not bring it |
| `launcher.py` | Starts, stops and opens Brento without a window. Every shortcut the installers make points here |
| `phone.py` | The phone door on port 8771: pairing codes, device tokens (only their hashes are saved), the routes a phone may use |
| `slack_notify.py` | Morning summary, new-card note and meeting reminder through an incoming webhook |
| `calendar_feed.py` | Reads a private iCal link; the link never goes back to a page |
| `library.py` | Reads the vault's notes for the Library page: titles, links, backlinks, search |
| `tools.py` | The dock: the only list the owner edits inside Brento |
| `tools.catalog.json` | The apps the wizard offers for the dock |
| `web/` | The page: `app.js` (all pages), `art.js` (drawn pictures), `style.css`, `photos/` |
| `packaging/` | Builds the two installers: `build.py`, the pinned downloads in `runtimes.json`, `mac/`, `windows/`, and the check that runs after an install |
| `install.sh`, `install.ps1` | Sets up the start at login and the app on a Mac (the Mac installer runs it too) or Linux; the same for a copy of the source code on Windows |
| `tests/` | `python -m unittest discover -s tests`; GitHub runs them on every push |

## Add a source

Say you want open pull requests that wait for your review.

1. **Reader** in `sources.py`: `read_reviews(today)` returns `(data, source("reviews", "Reviews", "GitHub", as_of, 1, today))`.
   Return `source(..., None, ...)` when it cannot read, never an empty success.
2. **Switch** in `settings.py`: add `{"id": "reviews", "label": "Pull requests to review", "group": "Schedule",
   "new": False, "about": "..."}` to `SOURCES`. The setup and the settings page show it by themselves.
3. **Wire it** in `build_state()`: call the reader when `on("reviews")`, else `off("reviews", "Reviews")`; add its
   source to `srcs` and its data to `data`.
4. **Decide where it shows.** Home only takes what really needs the owner (`build_alerts`); everything else belongs
   on Today (`build_cards`) or its own page.
5. **Test it** in `tests/`: one test that it reads, one that a broken source says N/A.

## Change what reaches Home

`build_alerts()` is the gate: your own deadline within a week, a meeting where others expect you, a HIGH card with a
real date. It has no cap on purpose; quietly dropping the fifth urgent thing is the worst outcome. `build_focus()`
fills the rest of the home screen with HIGH cards, then MID cards from the areas named in `board.homeAreas`.

## Teams

A team shares one board; every person runs their own Brento. A card counts as yours when it is assigned to your
GitHub login (`board.me`, set by the wizard) or to nobody. `team.json` next to the code presets the board, its field
names, the apps and Slack timing for everyone who installs from the team's copy. It is checked on load: unknown keys
stop the start, so no secret or personal path can slip in.

## Rules worth keeping

- Read, never write: no note, card or appointment is changed. The only writes are Brento's own files in `~/.brento`,
  plus a board or field the owner asks the wizard to create.
- Secrets live in their own files (`calendar-url`, `slack-webhook`) and never travel back to a page or into a log.
- Only fixed programs can be started from the page (`wizard.ACTIONS`, the dock's own list), never anything a page sends.
- A phone gets a shorter list of routes (`phone.allowed`). A new route is closed to phones until you add it there.
- Every new cost is a design change: Brento runs without servers and paid APIs, and that is a feature.
