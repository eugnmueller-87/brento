# Privacy

This page is about Daytag, the program, wherever you got it: the Microsoft Store, the installers on GitHub, or the source
code. As of 25 November 2026.

**In one sentence:** Daytag runs on your computer, and nothing it reads or saves goes to its author.

## What Daytag reads

Your notes folder, your GitHub board and your calendar, once you connect them, and nothing else of your files. Daytag only
reads them and keeps no copy. The exception is a click of yours: *Create a new board* and *Add the lanes* write to GitHub.

To make suggestions, the setup also looks at your first name (from GitHub, from git, or your sign-in name on this
computer), at the list of vaults that Obsidian keeps, and asks GitHub's and Claude's programs whether you are signed in.

## What Daytag saves, and how

Daytag keeps everything in one folder of your own account: `.daytag` in your user folder. It holds your first name, the
path of your notes folder, your board's address, the list of your dock apps, your options, and a log that says when
Daytag started, which folders it uses and where an error happened.

Some of it is secret: the private link of your calendar, your Slack link, the key that keeps Daytag closed to others, the
words that let your browsers in, and the marks of paired phones (of those only a hash). On Windows the calendar link and
the Slack link are encrypted for your account and this computer, if you connected them with version 0.3.0 or a newer one. On
a Mac or Linux these files are readable for your account only.

In the browser, Daytag keeps the word that let it in, and which cards it has already shown you today, not in words.

Your GitHub sign-in belongs to GitHub's own program. Windows or macOS keeps it where they keep all sign-ins, and the
program has a small folder of its own for its options (in the Daytag from the Microsoft Store, Windows removes that
together with Daytag). Daytag never sees the sign-in. The same goes for Claude: you sign in to Anthropic's own program.

## What leaves your computer, and only then

| To | What | When | How to stop it |
|---|---|---|---|
| GitHub | The questions for your name, your boards and their cards, your organizations and your list of repositories | When you are signed in to GitHub's program, in the setup or before | Settings, 3: switch the board off. Or take the sign-in back on GitHub |
| Your calendar provider | A request for your private calendar link | When you connected a calendar | Settings, 5: Disconnect |
| Slack | Your first name, the titles of tasks, cards and meetings, why they need you, how many meetings lack preparation and how many urgent cards lack a date, and the links to join a call, as messages to your own channel | When you connected Slack. The sample notes never go there | Settings, 8: Disconnect, or choose there what may go |
| Anthropic (Claude) | Your question, up to six earlier messages of that conversation, your first name, and what Claude Code reads in your notes folder to answer. Daytag switches off Claude Code's own usage statistics and error reports for this | When you switched the Ask box on, per question | Settings, 3: switch the Ask box off |
| Google's icon service | The web address of the well-known apps in your dock, to get their logos | When such an app is in your dock. An app you add yourself gets a letter, so nobody learns its address | Remove the app from the dock |
| Your own phone | What Daytag shows, over your home network or Tailscale. In the home network this is not encrypted, so use it only at home | When you switched the phone on and paired it. The Daytag from the Microsoft Store does not have this | Settings, 9: Switch off |
| Your own git server | A request whether there is something new | When your notes folder is a git folder and you switched the morning brief on | Settings, 3: switch the brief off |

Each of these services handles what it gets under its own privacy policy. Daytag has no server, no account, no
advertising, no tracking and no statistics.

**If you got Daytag from the Microsoft Store:** Microsoft shows every publisher numbers about installations, use and
crashes of an app. They come from Microsoft and Windows, depending on your Windows settings, and not from Daytag.

## Deleting

Remove Daytag like any other program. Your settings stay, so that Daytag finds them when you install it again. To delete
them too: the uninstallers from GitHub ask you, and in the Daytag from the Microsoft Store there is a button for it
(**Brain**, **Sources and setup**, **Starting and removing**). It deletes everything Daytag wrote into `.daytag`, except
for an empty log file, and what it kept in that browser. Files you put there yourself stay. Or delete the folder yourself.

You can take back the GitHub sign-in under [github.com/settings/applications](https://github.com/settings/applications).

## Children

Daytag is a tool for work and everyday life and is not made for children.

## Questions

Write to [eugnmueller@googlemail.com](mailto:eugnmueller@googlemail.com), also about a bad answer of the Ask box. Or open an
issue at [github.com/eugnmueller-87/daytag/issues](https://github.com/eugnmueller-87/daytag/issues): those are public, so
please put nothing private in there. Publisher: Eugen Mueller.
