# Making a new version

People install Brento from the [Releases](https://github.com/eugnmueller-87/brento/releases) page, so a version is
what reaches them. Brento is developed in a separate working copy; each new version arrives here as one commit.

1. Bring the code up to date and run the tests: `python -m unittest discover -s tests`.
2. Put the new number in `VERSION`.
3. Add a heading `## <number> (<date>)` at the top of `CHANGELOG.md` and write what changed, for the people who use
   Brento: what they will notice, and any step they have to take after updating.
4. Commit, then tag and push both:

   ```sh
   git tag v0.2.0
   git push origin main v0.2.0
   ```

5. The release workflow (`.github/workflows/release.yml`) runs the tests, checks that the tag matches `VERSION` and
   that the changelog has a section for it, and publishes the release with that section as its text.

## Numbers

`0.2.0` for new things, `0.1.1` for fixes only. Before `1.0.0`, an update can still need a new step in the setup;
the changelog then says so at the top of its section.
