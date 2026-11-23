# Brento

[![tests](https://github.com/eugnmueller-87/brento/actions/workflows/tests.yml/badge.svg)](https://github.com/eugnmueller-87/brento/actions/workflows/tests.yml)
[![release](https://img.shields.io/github/v/release/eugnmueller-87/brento?style=flat)](https://github.com/eugnmueller-87/brento/releases/latest)
![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat&logo=python&logoColor=white)
![No build step](https://img.shields.io/badge/build-none-555?style=flat)
![License: MIT](https://img.shields.io/badge/license-MIT-555?style=flat)

One screen that tells you what needs you today. Brento reads your Obsidian notes and their dated tasks, your
GitHub Project board and your calendar, and puts only what really needs you on its home screen: your own
deadlines, meetings where people wait for you, urgent cards with a date. Your everyday apps sit in its dock.

It runs on your own computer (Windows or Mac), shows on your phone too, only reads your data, and costs nothing
to run. It works for one person or for a whole team sharing one board. And it is a blueprint: take this repository
and build your own.

---

## Install (Windows)

1. Download the [latest version](https://github.com/eugnmueller-87/brento/releases/latest) (**Source code (zip)**)
   and unpack it where it can stay.
2. Double-click **Install Brento**.

That is all. The installer finds Python or installs it for you (no admin rights), puts **Brento** in the Start menu,
starts it whenever you sign in, and opens the setup wizard.

## Install (Mac)

1. Download the [latest version](https://github.com/eugnmueller-87/brento/releases/latest) (**Source code (zip)**)
   and open the ZIP where it can stay.
2. Double-click **Install Brento.command**.

The installer finds Python. If the Mac has none, macOS offers Apple's free command line tools in one click; after
that, double-click again. Brento then starts at every login, **Brento** appears in Spotlight and Launchpad, and the
setup wizard opens. In Safari, **File, Add to Dock** keeps it in the Dock.

If macOS refuses the downloaded file, open System Settings, Privacy & Security, and click **Open Anyway**. Or open
Terminal, type `sh ` (with a space), drag `install.sh` from the folder into the window, and press Return.

To take it out again: `sh install.sh --remove`. **Linux:** `sh install.sh` adds a `brento` command and opens the wizard.

## Updating

Download the new version the same way, unpack it next to the old one, and double-click the installer in the new
folder. Brento restarts from there and keeps your setup, which lives in your home folder (`.brento`), not in the
program folder. Then delete the old folder. What changed, and any step an update needs, is in
[CHANGELOG.md](CHANGELOG.md).

## On your phone (iPhone, iPad, Android)

Brento shows on your phone through your computer, so there is no app store and nothing to install on the phone.

1. On the computer: **Brain, Sources and setup**, then **Phone**, then **Use Brento on my phone**. Brento shows an
   address and a six-digit code.
2. On the phone, on the same Wi-Fi: open Safari (or Chrome) and type the address.
3. iPhone: **Share, Add to Home Screen**. Open Brento from its new icon and type the code.

The phone reads Home, the board, the calendar and your notes, and can use the Ask box. It cannot change the setup.
The computer has to be on. Away from home it works over [Tailscale](https://tailscale.com/), with the second address
Brento shows. Use it on your home Wi-Fi or over Tailscale, not on public Wi-Fi.

## The wizard

One question per screen, most answers already filled in, a button for everything that has to happen elsewhere:

| Step | What you do |
|---|---|
| Welcome | Check your first name (taken from GitHub or git) |
| Notes | Your Obsidian vault is already chosen. Brento shows how many notes and dated tasks it found |
| Board | *Install it for me* and *Sign in to GitHub* if needed, then click your board, or *Create a new board for me*. On a Mac the GitHub program is downloaded from github.com and checked before it is kept |
| Calendar | Pick Google, Outlook or Apple, follow four short steps, paste the private link. Brento checks it at once |
| Slack (optional) | *Create the Brento app* opens Slack with everything filled in. Add a webhook, paste it, a test message arrives |
| Apps | The apps for your dock, already ticked from what you connected |

Change anything later under **Brain, Sources and setup**.

## Working as a team

Everyone runs their own Brento with their own notes and calendar, and the team shares one GitHub Project board.

1. **The team lead** clicks **Use this template** on GitHub to get the team's own copy, installs it, and in the
   wizard picks **Create a team board in *your organization***. On the last screen: **Save as team setup**. That
   writes `team.json` (board, field names, apps, calendar kind, Slack timing; nothing personal, no secrets).
   Commit and push it.
2. **Everyone else** downloads the team's copy and double-clicks **Install Brento**. The wizard already knows the
   board, the apps and the settings; they confirm and connect their own calendar.

On a team board, each person's home screen shows the cards assigned to them and the cards nobody has taken yet.
The board page shows everyone's cards with their names. A template for the team file is in `team.example.json`.

## What it reads

| Source | How |
|---|---|
| Obsidian notes | Read inside Brento: topics, folders, tags, full-text search, backlinks |
| Obsidian tasks with a date | `- [ ] Send the offer 📅 2026-11-30` (Tasks plugin), `[due:: 2026-11-30]` (Dataview) or `@due(2026-11-30)` |
| GitHub Project board | Lanes HIGH, MID and LOW; a person's or an organization's board; your own field names |
| Calendar | A private iCal link from Google, Outlook or Apple; meetings with others reach Home with a *Join call* button |
| Ask box | Questions about your notes, answered by Claude Code on your computer under your own Claude login |

**On track?** on the Today page checks the next two weeks: a meeting nobody prepared for, two meetings at the same
time, a task or card whose date has passed, an urgent card without a date.

## Principles

- **Local and read-only.** Brento never changes a note, a card or an appointment. It writes to its own folder
  (`~/.brento`), and creates a board or `team.json` only when you click the button for it.
- **Nothing to pay for.** No server, no database, no paid API. GitHub, the calendar link and the Slack webhook are free.
- **Silence is not success.** A source that cannot be read shows *N/A*, never an empty, calm screen.
- **The code decides what comes first, not a model.** Every card on Home says why it is there and how old its source is.
- **Private stays private.** An optional privacy list keeps matching rows off the screen and out of Slack.
- **A phone only looks.** It pairs with a code that lives ten minutes and dies after five wrong tries, and it can
  never change the setup or start a program on the computer.

## Use it as a blueprint

Everything is plain Python (standard library only) and plain JavaScript, with no build step. How it is built, how
to add your own source, how to change what reaches the home screen: [docs/BLUEPRINT.md](docs/BLUEPRINT.md).

Run the tests with `python -m unittest discover -s tests`.

## About the Ask box and Claude

The Ask box starts the unmodified `claude` program on your computer. You sign in to it yourself, through Anthropic's
own sign-in; Brento never sees, stores or passes on that login, and it refuses to run on an API key, so it cannot
cause a bill. Anthropic's terms
([legal and compliance](https://code.claude.com/docs/en/legal-and-compliance), read 23.11.2026) do not prevent "an
end user from signing in to the unmodified Claude Code binary with their own Claude subscription". They do not
name a local app that starts `claude -p` either, so if you plan to offer Brento commercially, ask Anthropic first.
The Ask box is optional and can stay off.

## Status

Version 0.1.0, see [CHANGELOG.md](CHANGELOG.md). Brento grew out of a dashboard its author uses every day on
Windows. This first public version adds the installers, the setup wizard and the phone pairing. They pass the
automated tests on every change, but none of them has been through a first install on someone else's computer
yet, and the Mac installer and the phone pairing have not run on a real Mac or phone. If something fails, please
open an issue.

## Credits and license

Code: MIT, see [LICENSE](LICENSE). The photos in `web/photos/` come from Wikimedia Commons under their own licenses
(CC BY-SA, CC BY, public domain); authors and licenses are listed in
[web/photos/CREDITS.md](web/photos/CREDITS.md).

Built by Eugen Mueller with the help of Claude Code (Anthropic). Every change runs through the automated tests;
what has not been tried on real devices yet is listed under Status.
