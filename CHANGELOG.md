# Changelog

What changed in each version, newest first. Every version is on the
[Releases](https://github.com/eugnmueller-87/brento/releases) page, with its installers.

## 0.2.0 (2026-11-24)

One file to install, on Mac and Windows. **If you use 0.1.0, please update:** this version also closes four security
holes, see *Safer*.

Updating from 0.1.0: open the new installer. It keeps your setup and takes over the start at login. After that you can
delete the unpacked 0.1.0 folder. From now on Brento opens with its icon: a browser has to be let in by it once, and
bookmarks in that browser work after that. On a computer with several accounts it is once after each start, unless you
decide otherwise in the settings.

**New**

- **Mac:** `Brento-Mac.pkg` opens Apple's own installer. **Windows:** `Brento-Windows.exe` opens a short guide. Both bring
  everything along, Python and the GitHub program included. No Terminal.
- **Signing in happens on the page.** For GitHub, Brento shows a one-time code and a button that copies it and opens
  GitHub, and says beforehand what GitHub will ask for. The Claude sign-in opens in your browser by itself. No Terminal
  or console window opens any more.
- **Removing:** on a Mac through the app *Uninstall Brento*, on Windows through Settings, Apps. Both ask whether the
  settings with your private links should go too.
- **Two people on one computer** each get a Brento of their own.

**Safer**

- Brento opens only for the person it belongs to. In 0.1.0 another account on the same computer could open it as well.
  A browser is let in by the icon, gets a word of its own, and signs every request with it without ever sending it. The
  page checks in turn that it is Brento that answers.
- A link on a web page can no longer make Brento look into a folder. In 0.1.0 it could, and on Windows a folder on a
  stranger's server would have received an encrypted form of your Windows password.
- The Ask box reads your notes folder and nothing else, and no settings files or hooks count. In 0.1.0 a notes folder from
  someone else could start a program, and a question could read other files. It is off until you switch it on; the setup
  no longer does that by itself.
- A web page that lies among your notes gets none of Brento's rights. In 0.1.0 its scripts had them.
- Addresses of apps you add to the dock yourself no longer go to Google's icon service, and GitHub's program is told not
  to send its usage reports.

**Fixed**

- The last page of the setup stays. In 0.1.0 it jumped back to the first one after a few seconds, and so did the setup
  after a break.
- A notes folder that was renamed or is on a drive that is not connected no longer keeps Brento from starting. Brento
  says so, and you can choose the folder again.
- *Connect* with an empty field no longer reports success, and a wrong calendar or Slack link no longer replaces one
  that works.
- A source that could not be read, or that stopped answering, is never called quiet any more, neither on Home nor in the
  Slack summary. The summary waits a moment for it and then names it. Nothing goes to Slack before the setup is finished.
- Coming back to the setup for one thing, such as the calendar, shows and saves only that. The settings lead to each
  question step by step.
- With nothing connected, Home says so instead of *All quiet*.
- A folder that does not exist is said on the spot, and a copied path works with the quotes Windows puts around it.
- A calendar or Slack link that was pasted is no longer lost when you click *Next* instead of *Connect*.
- Notes that lie only in a cloud hold nothing up. Brento reads what is here, says how many are missing and fetches them
  in the background. On a Mac it may fetch them from iCloud at all, which macOS does not allow a program that starts at
  login unless it asks for it.
- A folder among the notes that cannot be opened is said, not skipped in silence.
- A calendar that breaks off on its way counts as not read, and a date before 1970 in it no longer takes Brento down on
  Windows.
- Meetings from other time zones show the right hour on Windows, and everywhere for Outlook calendars.
- Outlook meetings with a link to a call reach Home, although Outlook's link names no guests.
- On a Mac the start no longer waits for the network, up to 35 seconds in some places, and no longer raises the question
  about devices on the local network. The setup no longer makes macOS offer its developer tools.
- The Board page belongs to your board: no foreign project number, and an empty board says that it is empty.
- Claude Code is found on Windows where its own installer puts it.
- Notes and tasks in folders called `raw`, `wiki`, `outputs` or `memory` are no longer left out in a new setup.
- The Ask box is ready as soon as you have signed in to Claude for it at the end of the setup, and team boards show right
  after the GitHub sign-in.
- When Brento refuses something a phone asks for, the phone always gets the reason.

Known gaps:

- The installers are not signed, so macOS and Windows ask whether you trust them, for each new version (the first page
  shows the clicks). On a PC with Smart App Control switched on, Windows blocks the installer.
- Repeating appointments are left out.
- The phone pairing has not been tried on a real phone.
- The settings pages are made for a computer screen. On a phone they show a note instead.

## 0.1.0 (2026-11-23)

The first public version.

- **Home** shows what needs you today, taken from your Obsidian notes and their dated tasks, your GitHub Project
  board and your calendar. Every card says why it is there and how old its source is.
- **Setup wizard:** one question per screen, with buttons for the GitHub sign-in, a new board, the calendar link and
  Slack.
- **Windows installer:** double-click *Install Brento*. It finds or installs Python without admin rights and starts
  Brento at every sign-in. Run it again from a newer version and it restarts Brento from there.
- **Mac installer:** double-click *Install Brento.command*. Brento starts at every login and appears in Spotlight
  and Launchpad. The GitHub program is downloaded from github.com and checked against its published checksums.
- **Phone:** pair an iPhone, iPad or Android phone with a six-digit code and add Brento to its home screen. The
  phone reads and asks; it cannot change the setup.
- **Teams:** one shared board, everyone with their own notes and calendar. `team.json` carries the shared setup.
- **Slack (optional):** a morning summary at the time you choose and a reminder before meetings.

Known gaps:

- The Mac installer and the phone pairing pass the automated tests, but have not yet run on a real Mac or phone.
- The settings pages are made for a computer screen. On a phone they show a note instead.
