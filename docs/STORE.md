# Daytag in the Microsoft Store

In the Store, Microsoft signs Daytag. People then get no security question, also where Smart App Control is on, and
Windows updates it. This page holds what has to be done once, what each version needs, and the texts of the Store page.

## Once

The account, the name and the mail address are there since 25 November 2026. The name is lost if no version is submitted
until 25 February 2027.

1. Open a developer account at [storedeveloper.microsoft.com](https://storedeveloper.microsoft.com), **Get started for
   free**. The free way starts only there. A person has to do this: it takes a photo of an identity document and a selfie.
2. In [Partner Center](https://aka.ms/submitwindowsapp): **New product, MSIX or PWA app**, and reserve the name.
3. Under **Product management, Product identity** stand three values that the package needs: Package/Identity/Name,
   Package/Identity/Publisher and Package/Properties/PublisherDisplayName. They are no secret, every package shows them, but
   they belong to one account, so they are given when the package is built and do not lie in this repository.
4. Choose a mail address that may be public. The Store asks for a way to report a bad answer of the Ask box that needs
   no account (policy 11.16). It goes into `CONTACT` in `settings.py`, under *Questions* in [PRIVACY.md](../PRIVACY.md), and
   into the Store page as the support contact.

## Each version

1. Push to a branch `try/<version>`. The release workflow builds the package with test names, installs it on Windows 11 and
   Windows Server, goes through the setup, updates and removes it, and keeps new pictures.
2. Tag the version ([RELEASING.md](RELEASING.md)). Microsoft opens the privacy page at its public address, so it has to be on
   `main` before step 4.
3. Build the package with the real names, from the tag:

   ```sh
   gh workflow run release.yml --ref v0.3.0 -f identity='{"name": "...", "publisher": "CN=...", "display": "..."}'
   ```

   The run keeps it as `store-package`.
4. In Partner Center, open a new submission, put `Daytag-Store.msix` under **Packages**, write what is new, submit.
   Microsoft's check takes up to three working days. Do not cancel it while it runs.

The Store wants four numbers, the first not 0 and the last 0. Daytag 0.3.0 is 1.3.0.0 there, 1.0.0 is 2.0.0.0.

## The texts of the Store page

**Name:** Daytag. **Price:** free. **Category:** Productivity. **Website:** `https://github.com/eugnmueller-87/daytag`.
**Support:** `eugnmueller@googlemail.com`. **Privacy policy:**
`https://github.com/eugnmueller-87/daytag/blob/main/PRIVACY.md`. **Personal information:** yes, it reads some, on the
computer. **License terms:** the text of [LICENSE](../LICENSE), otherwise Microsoft's own terms apply, and those forbid
passing it on. **Copyright:** Copyright (c) 2026 Eugen Mueller. **This product incorporates generative AI features:** yes (the
optional Ask box, provided by a third party, Anthropic).

**Short description**

> One screen that tells you what needs you today: your deadlines, your meetings and your urgent cards, from your own
> notes, board and calendar. Runs on your computer, only reads, costs nothing.

**Description**

> Needs nothing but Windows 10 or 11 with Edge or Chrome, whose window it uses. You can connect, if you like: Obsidian
> notes on this computer, a free GitHub account for a to-do board, a Google, Outlook or Apple calendar, Slack, and for the
> Ask box Claude Code with your own Claude plan.
>
> ONE SCREEN THAT TELLS YOU WHAT NEEDS YOU TODAY
> Daytag reads your notes, your to-do board and your calendar, and puts only what really needs you on its home screen:
> your own deadlines, meetings where people wait for you, urgent cards with a date. Each card says why it is there and
> how old its source is.
>
> Not sure yet? Look around with sample notes first. No account needed.
>
> • Home: one card for each thing that needs you, soonest first
> • Today: what to do next, in a fixed order that does not move by itself
> • Library: your Obsidian notes with folders, tags, search and backlinks
> • Dock: the apps you use every day, each in its own window
> • Slack, if you want: a short message in the morning and before meetings
> • Ask, if you want: questions about your notes, answered by Claude
>
> PRIVATE
> Daytag runs on your computer and only reads. It never changes a note, a card or an appointment. It has no account, no
> server, no advertising and no tracking. What leaves your computer, and only when you connect something, is listed in
> the privacy policy.
>
> LIVE GENERATIVE AI
> The optional Ask box answers with live generative AI: Claude by Anthropic, through Claude Code on your computer and
> under your own plan. It is off until you switch it on. Answers can be wrong, and a link under them lets you report one.
>
> GOOD TO KNOW
> The setup asks whether Daytag may start when you sign in to Windows. In Daytag's settings there are buttons that quit it
> and that delete what it saved. The surface is in English. Daytag is free and open source.

**Features** (one line each): Only what needs you, with the reason · Reads Obsidian notes and dated tasks · Reads a GitHub
Project board · Reads your calendar through a private link · Runs on your computer, nothing goes to the author · Free and
open source

**Search terms** (no names of other products): daily planner · to-do · dashboard · tasks · calendar · notes · focus

**Why runFullTrust** (the field silently cuts long texts, so keep it under 300 characters)

> A classic desktop program: a local Python server that reads the notes folder the user picked anywhere on the disk,
> starts the bundled GitHub CLI and the user's own Claude Code, and opens the user's browser. A sandboxed app cannot.

**Notes for certification**

> No account is needed, every step of the setup can be skipped.
> 1. Start Daytag. A window of Chrome or Edge opens with the setup. The page comes from a local server on 127.0.0.1:8770.
> 2. Let's go. On "Your notes" choose "Look around with sample notes", Next. On the next pages "Skip for now", on "Your
> apps" Finish, then Open Daytag.
> 3. Home shows seven cards from the sample notes. The dock at the bottom leads to Today, Projects, Library and Brain.
> Optional, not needed for the test: GitHub (gh.exe is GitHub's own signed program), a calendar link, Slack, and the Ask
> box, which starts the user's own Claude Code if it is installed (live generative AI, with a link to report answers).
> Start at sign-in: the setup asks on "Your apps". Without a yes the startup task ends at once. Settings, 9, changes it and
> links to Windows Settings. It is needed for the Slack messages.
> Network: Daytag listens on 127.0.0.1 only and adds no firewall rule.
> Settings, 9, has a button that deletes what Daytag saved (folder .daytag in the user's folder) before uninstalling, and
> one that quits Daytag. Settings, 6, and the Ask page have the link to report an answer.

## Pictures

`packaging/store/shots.py` takes them from the installed program in its own window, on a GitHub computer, with the sample
notes. Take new ones when the pages change. The Store refuses drawn pictures (policy 10.1.1). The photos on the cards come
from Wikimedia Commons; name their authors in the caption of a picture that shows one (they stand in `web/photos/CREDITS.md`).

## What the Store version leaves out

The phone door, because it speaks plain http in the home network, and the Store wants what is personal encrypted on its way
(policy 10.5.4). And *Save as team setup*, because a team's copy has installers of its own and the Store's package is the
same for everyone.
