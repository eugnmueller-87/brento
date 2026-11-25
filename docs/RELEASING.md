# Making a new version

People install Daytag from the [Releases](https://github.com/eugnmueller-87/daytag/releases) page, so a version is
what reaches them. Daytag is developed in a separate working copy; each new version arrives here as one commit.

1. Bring the code up to date and run the tests: `python -m unittest discover -s tests`.
2. Put the new number in `VERSION`.
3. Add a heading `## <number> (<date>)` at the top of `CHANGELOG.md` and write what changed, for the people who use
   Daytag: what they will notice, and any step they have to take after updating.
4. Commit, then tag and push both:

   ```sh
   git tag v0.4.0
   git push origin main v0.4.0
   ```

5. The release workflow (`.github/workflows/release.yml`) runs the tests and builds both installers. It then installs
   each of them on fresh computers, goes through the whole setup in a browser, updates, crashes and removes it: macOS 15
   and 26 (Apple chip and Intel), macOS 27, Windows Server 2022 and 2025, Windows 11 on Arm. The package for the Microsoft
   Store goes through the same on Windows Server 2025 and Windows 11. Only when all of that worked, it publishes the
   release with the installers, their checksums and the changelog section as its text, and compares what the download
   links give with what was tested. The Store package is not part of the release, because only Microsoft can sign it.

To try all of this without publishing, open **Actions**, **release**, **Run workflow**, or push to a branch called
`try/something`. Either way it keeps pictures of every step. Look at them before you tag.

## What goes into the installers

`packaging/runtimes.json` names the Python, the GitHub program and the time zone data that go along, by address and
SHA-256. To update one, change its address, compare the new checksum with the publisher's list, and write it down there.
A file that differs stops the build. A new GitHub program can need a newer macOS: check it, and keep the number in
`packaging/mac/Distribution.xml` and on the front page. A new Mac Python brings its own libraries: take their license texts
along (`packaging/mac/licenses`, from the same tag of python-build-standalone). Build by hand with `python packaging/build.py mac` (any computer) or `windows` (Windows with Inno
Setup 6).

The installers are not signed. A signature is what ends the security question on the first start: on a Mac through Apple's
paid Developer Program. On Windows, Microsoft signs the package for its Store without cost: [STORE.md](STORE.md). A
certificate of one's own costs money, shows one's name, and the warning still stays until enough people have installed it.

## Numbers

`0.2.0` for new things, `0.1.1` for fixes only. Before `1.0.0`, an update can still need a new step in the setup;
the changelog then says so at the top of its section.
