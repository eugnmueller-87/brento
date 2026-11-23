# Changelog

What changed in each version, newest first. Every version is on the
[Releases](https://github.com/eugnmueller-87/brento/releases) page, with a ZIP to download.

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
