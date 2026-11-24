# Changelog

What changed in each version, newest first. Every version is on the
[Releases](https://github.com/eugnmueller-87/brento/releases) page, with its installers.

## 0.2.0 (2026-11-24)

One file to install, on Mac and Windows.

- **Mac:** `Brento-Mac.pkg` opens Apple's own installer. **Windows:** `Brento-Windows.exe` opens a short guide. Both bring
  everything along, Python and the GitHub program included. No Terminal and no administrator password.
- **Signing in happens on the page.** For GitHub, Brento shows a one-time code and a button that copies it and opens
  GitHub. The Claude sign-in opens in your browser by itself. No Terminal or console window opens any more.
- **Removing:** on a Mac through the app *Uninstall Brento*, on Windows through Settings, Apps.
- The Ask box switches on as soon as you have signed in to Claude at the end of the setup. Before, it stayed off until
  you saved the settings again.
- Team boards show right after the GitHub sign-in. Before, only after a reload.
- When Brento refuses something a phone asks for, the phone now always gets the reason. On Windows it was cut off now
  and then.

Updating from 0.1.0: open the new installer. It keeps your setup and takes over the start at login. After that you can
delete the unpacked 0.1.0 folder.

Known gaps:

- The installers are not signed, so macOS and Windows ask once whether you trust them (the first page shows the clicks).
  On a PC with Smart App Control switched on, Windows blocks the installer.
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
