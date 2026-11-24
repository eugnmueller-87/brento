# Brento

[![tests](https://github.com/eugnmueller-87/brento/actions/workflows/tests.yml/badge.svg)](https://github.com/eugnmueller-87/brento/actions/workflows/tests.yml)
[![release](https://img.shields.io/github/v/release/eugnmueller-87/brento?style=flat)](https://github.com/eugnmueller-87/brento/releases/latest)
![Mac and Windows](https://img.shields.io/badge/Mac_and_Windows-one_file-2ea44f?style=flat)
![Nothing to pay for](https://img.shields.io/badge/running_costs-none-555?style=flat)
![License: MIT](https://img.shields.io/badge/license-MIT-555?style=flat)

One screen that tells you what needs you today. Brento reads your Obsidian notes and their dated tasks, your
GitHub Project board and your calendar, and puts only what really needs you on its home screen: your own
deadlines, meetings where people wait for you, urgent cards with a date. Your everyday apps sit in its dock.

It runs on your own computer (Windows or Mac), shows on your phone too, only reads your data, and costs nothing
to run. It opens only for you, also on a computer you share. It works for one person or for a whole team sharing one
board. And it is a blueprint: take this repository and build your own.

---

## Install

| Your computer | One file |
|---|---|
| **Mac** (macOS 13 or newer, Apple chip or Intel) | [**Download Brento-Mac.pkg**](https://github.com/eugnmueller-87/brento/releases/latest/download/Brento-Mac.pkg) |
| **Windows** 10 or 11 | [**Download Brento-Windows.exe**](https://github.com/eugnmueller-87/brento/releases/latest/download/Brento-Windows.exe) |

Open the file and click through. Then Brento opens in your browser and asks one question per page, and you can skip
every one of them. The file brings everything along, so there is nothing else to install and no Terminal to open.
Brento starts when you log in, and you open it like any other app.

### The first time on a Mac

macOS stops programs from the internet that Apple has not checked. Brento has no paid Apple certificate, so you allow
the file yourself ([Apple's own description](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac)):

1. Open **Brento-Mac.pkg**. macOS says *"Brento-Mac.pkg" Not Opened*. Click **Done**, not the blue *Move to Trash*.
2. Open **System Settings**, then **Privacy & Security**, and scroll down to *Security*. Next to *"Brento-Mac.pkg" was
   blocked to protect your Mac* click **Open Anyway**. The warning comes back: click **Open Anyway** again, and confirm
   with the password of an administrator of this Mac (yours, if the Mac is yours). That is macOS asking, not Brento. The
   button is there for about an hour. On macOS 13 and 14 it is shorter: hold **Control**, click the file, **Open**, **Open**.
3. The installer opens: **Continue**, **Install**, **Close**. Should it ask for an administrator, click **Change Install
   Location** and choose **Install for me only**.

### The first time on Windows

1. Your browser may hold the file back. In **Edge**: point at the download, click the three dots, **Keep**, **Show more**,
   **Keep anyway**. In another browser choose to keep it, if it asks.
2. Open **Brento-Windows.exe**. If Windows says that it protected your PC, click **More info**, then **Run anyway**.
3. The installer opens: **Next**, **Install**, **Finish**.

Some newer PCs have **Smart App Control** switched on. Windows then blocks every unknown program without a certificate,
and [offers no exception for a single one](https://support.microsoft.com/topic/285ea03d-fa88-4d56-882e-6698afdb7003).
Brento does not have that certificate yet, so it cannot be installed on such a PC.

### Updating and removing

**Update:** download the new file and open it. Your computer asks the same questions again for each new version. Your
setup stays, because it lives in your home folder (`.brento`). What changed is in [CHANGELOG.md](CHANGELOG.md).

**Remove:** on a Mac, open **Uninstall Brento** (press Cmd and Space and type it). On Windows, **Settings, Apps**, Brento,
**Uninstall**. Your notes, board and calendar stay as they are, and Brento asks whether its own settings should go too.
Your GitHub sign-in stays on the computer; take it back under
[github.com/settings/applications](https://github.com/settings/applications).

### Linux, or from the source code

Linux: `sh install.sh` adds a `brento` command and opens the wizard, `sh install.sh --remove` takes it out again. On a
Mac, the same script runs Brento with the Mac's own Python. On Windows, *Install Brento.cmd* does that with Python from
python.org. How the two
installers are built: [packaging/build.py](packaging/build.py).

## On your phone (iPhone, iPad, Android)

Brento shows on your phone through your computer, so there is no app store and nothing to install on the phone.

1. On the computer: **Brain, Sources and setup**, then **Phone**, then **Use Brento on my phone**. Brento shows an
   address and a six-digit code. Windows asks about Python then: that is Brento, click **Allow** (an administrator is
   needed for that once, and your Wi-Fi has to be set to *Private network*).
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
| Board | *Sign in to GitHub* shows a one-time code and a button that copies it and opens GitHub. GitHub asks you to authorize *GitHub CLI*, its own program: it always asks for your repositories and gists (to read and write) and to see your organizations, and Brento adds your project boards. Then click your board, or *Create a new board for me* |
| Calendar | Pick Google, Outlook or Apple, follow four short steps, paste the link. Brento checks it at once |
| Slack (optional) | *Create the Brento app* opens Slack with everything filled in. Add a webhook, paste it, a test message arrives |
| Apps | The apps for your dock, already ticked from what you connected |

Change anything later under **Brain, Sources and setup**.

## Working as a team

Everyone runs their own Brento with their own notes and calendar, and the team shares one GitHub Project board.

1. **The team lead** clicks **Use this template** on GitHub to get the team's own copy, installs it, and in the
   wizard picks **Create a team board in *your organization***. On the last screen: **Save as team setup**. That
   writes `team.json` (board, field names, apps, calendar kind, Slack timing; nothing personal, no secrets).
   Commit it to the team's copy and [make a release](docs/RELEASING.md): the installers built there carry the team's
   setup.
2. **Everyone else** downloads the installer from the team's own Releases page. The wizard already knows the board, the
   apps and the settings; they confirm and connect their own calendar.

On a team board, each person's home screen shows the cards assigned to them and the cards nobody has taken yet.
The board page shows everyone's cards with their names. A template for the team file is in `team.example.json`.

## What it reads

| Source | How |
|---|---|
| Obsidian notes | Read inside Brento: topics, folders, tags, full-text search, backlinks |
| Obsidian tasks with a date | `- [ ] Send the offer 📅 2026-11-30` (Tasks plugin), `[due:: 2026-11-30]` (Dataview) or `@due(2026-11-30)` |
| GitHub Project board | Lanes HIGH, MID and LOW; a person's or an organization's board; your own field names |
| Calendar | An iCal link from Google, Outlook or Apple; meetings with others reach Home with a *Join call* button. Repeating appointments are left out |
| Ask box | Questions about your notes, answered by Claude Code on your computer under your own Claude plan. Off until you switch it on. It can read your notes folder and nothing else. The privacy list does not cover it |

**On track?** on the Today page checks the next two weeks: a meeting nobody prepared for, two meetings at the same
time, a task or card whose date has passed, an urgent card without a date.

## Principles

- **Local and read-only.** Brento never changes a note, a card or an appointment. It writes to its own folder
  (`~/.brento`), and creates a board, its lanes or `team.json` only when you click the button for it.
- **What leaves the computer:** Brento asks GitHub and your calendar. Parts of your notes go to Claude when you ask the
  Ask box, and messages go to Slack when you connect it. The logos of the known apps in the dock come from Google's
  icon service. Nothing goes to the author of Brento.
- **Only for you.** Brento opens only for the person it belongs to. Another account on the same computer sees a locked
  page, and gets a Brento of its own.
- **Nothing to type.** Installing, signing in, updating and removing work without a Terminal.
- **Nothing to pay for.** No server, no database, no paid API. GitHub, the calendar link and the Slack webhook are free.
- **Silence is not success.** A source that cannot be read shows *N/A*, never an empty, calm screen.
- **The code decides what comes first, not a model.** Every card on Home says why it is there and how old its source is.
- **Private stays private.** An optional privacy list keeps matching rows off the screen and out of Slack.
- **A phone looks and asks.** It pairs with a code that lives ten minutes and dies after five wrong tries, and it can
  never change the setup or start a program on the computer.

## Use it as a blueprint

Everything is plain Python (standard library only) and plain JavaScript, with no build step. How it is built, how
to add your own source, how to change what reaches the home screen: [docs/BLUEPRINT.md](docs/BLUEPRINT.md).

Run the tests with `python -m unittest discover -s tests`.

## About the Ask box and Claude

The Ask box starts the unmodified `claude` program on your computer. You sign in to it yourself, through Anthropic's
own sign-in; Brento never sees, stores or passes on that login. It refuses to run on an API key, so questions count
against your Claude plan (extra usage costs money only if you have switched that on at Anthropic). It starts it so that
only your notes folder can be read, and no settings files or hooks count: a shared vault cannot start a program on your
computer. Anthropic's terms
([legal and compliance](https://code.claude.com/docs/en/legal-and-compliance), read 23.11.2026) do not prevent "an
end user from signing in to the unmodified Claude Code binary with their own Claude subscription". They do not
name a local app that starts `claude -p` either, so if you plan to offer Brento commercially, ask Anthropic first.
The Ask box is optional and can stay off.

## Status

Version 0.2.0, see [CHANGELOG.md](CHANGELOG.md). Brento grew out of a dashboard its author uses every day on
Windows. Before a version is published, GitHub's computers install it, open it, go through the whole setup in a
browser, update it and remove it: macOS 15 and 26 (Apple chip and Intel), macOS 27, Windows 11 (on Arm) and Windows
Server 2022 and 2025. What no automatic test covers: the password question of macOS after *Open Anyway*, the warning of
SmartScreen, macOS 13 and 14, and the pairing of a real phone. If something fails, please open an issue.

## Credits and license

Code: MIT, see [LICENSE](LICENSE). The photos in `web/photos/` come from Wikimedia Commons under their own licenses
(CC BY-SA, CC BY, public domain); authors and licenses are listed in
[web/photos/CREDITS.md](web/photos/CREDITS.md).

Built by Eugen Mueller with the help of Claude Code (Anthropic). Every change runs through the automated tests;
what has not been tried on real devices yet is listed under Status.
