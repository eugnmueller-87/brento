import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import library
import settings
import sources

sources.load_private(Path(__file__).resolve().parent / "stand-in-terms.txt")


def vault_with(files):
    root = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def render(text, notes=(), assets=()):
    r = library.Renderer(lambda t: t + ".md" if t in notes else None, lambda t: t if t in assets else None)
    return r.blocks(text.split("\n"))


class Safety(unittest.TestCase):
    def test_html_in_a_note_is_shown_as_text_never_run(self):
        out = render('<script>alert(1)</script> and <img src=x onerror=alert(1)>')
        self.assertNotIn("<script", out)
        self.assertNotIn("<img", out)
        self.assertIn("&lt;script&gt;", out)

    def test_dangerous_link_schemes_lose_the_link_and_keep_the_text(self):
        for url in ("javascript:alert(1)", "data:text/html,x", "obsidian://open?x", "file:///c:/x"):
            out = render("[click me](%s)" % url)
            self.assertNotIn("href", out, url)
            self.assertIn("click me", out)

    def test_a_quote_cannot_break_out_of_an_attribute(self):
        out = render('[a](https://x.example/"onmouseover="alert(1))')
        self.assertNotIn('"onmouseover="', out)

    def test_code_is_escaped_and_not_treated_as_markup(self):
        out = render("Use `<b>**x**</b>` here\n\n```\n<script>[[Note]]</script>\n```", notes=("Note",))
        self.assertIn("<code>&lt;b&gt;**x**&lt;/b&gt;</code>", out)
        self.assertIn("&lt;script&gt;[[Note]]&lt;/script&gt;", out)


class Markdown(unittest.TestCase):
    def test_wikilinks_stay_inside_the_app_and_missing_ones_do_not_pretend(self):
        out = render("[[Goals|my goals]] and [[Gone]]", notes=("Goals",))
        self.assertIn('href="#library/n/Goals.md"', out)
        self.assertIn(">my goals</a>", out)
        self.assertIn('<span class="link-missing"', out)
        self.assertNotIn("obsidian", out)

    def test_table_with_a_wikilink_alias_keeps_its_columns(self):
        out = render("| A | B |\n|---|---|\n| [[Note|alias]] | two |", notes=("Note",))
        self.assertEqual(out.count("<td>"), 2)
        self.assertIn(">alias</a>", out)

    def test_nested_lists_and_tasks(self):
        out = render("- one\n  - inner\n- [x] done\n- [ ] open\n\n1. first\n2. second")
        self.assertIn("<ul><li>one<ul><li>inner</li></ul></li>", out)
        self.assertEqual(out.count('class="task done"'), 1)
        self.assertEqual(out.count('class="task"'), 1)
        self.assertIn("<ol><li>first</li><li>second</li></ol>", out)

    def test_wrapped_lines_become_one_paragraph(self):
        self.assertEqual(render("one\ntwo\n\nthree"), "<p>one two</p><p>three</p>")

    def test_callouts_quotes_and_emphasis(self):
        out = render("> [!warning] Careful\n> **bold** *it*\n\n> plain")
        self.assertIn('<div class="callout callout-warning"><div class="callout-title">Careful</div>', out)
        self.assertIn("<strong>bold</strong> <em>it</em>", out)
        self.assertIn("<blockquote><p>plain</p></blockquote>", out)

    def test_a_star_in_a_sentence_is_not_emphasis(self):
        self.assertEqual(render("2 * 3 * 4"), "<p>2 * 3 * 4</p>")

    def test_image_embed_only_for_a_known_file(self):
        out = render("![[pic.png]]\n\n![[nope.png]]", assets=("pic.png",))
        self.assertIn('src="/api/library/asset?path=pic.png"', out)
        self.assertIn('<span class="link-missing">nope.png</span>', out)

    def test_frontmatter_reads_both_list_forms(self):
        props, body = library.split_frontmatter("---\ntype: note\ntags: [a, b]\nsources:\n  - one\n  - two\n---\nBody")
        self.assertEqual(props, {"type": "note", "tags": ["a", "b"], "sources": ["one", "two"]})
        self.assertEqual(body, "Body")


class Index(unittest.TestCase):
    FILES = {"Goals.md": "---\ntype: note\ntags: [x]\n---\n# My Goals\n\nSee [[Alpha]].\n",
             "Notes/Alpha.md": "Alpha text about budgets. [[Goals]]\n",
             "Projects/Alpha.md": "Other alpha.\n",
             "Projects/Beta.md": "[[Alpha]] from projects\n",
             "raw/Secret.md": "never\n", "memory/M.md": "never\n", ".claude/C.md": "never\n",
             "00 Inbox/Geheimsache 1/Akte.md": "never\n",
             "Notes/Mixed.md": "ok line\nGeheimsache Akte 999 details\nanother ok line\n",
             "Notes/pic.png": "x", "raw/hidden.png": "x", "Notes/page.pdf": "x",
             "Projects/Cards.html": "<!doctype html><p>live cards</p>", "raw/Hidden.html": "<p>never</p>",
             "Projects/Leak.html": "<p>Geheimsache Akte 999</p>"}

    def setUp(self):
        sources.set_skip(settings.OLD_SKIP)
        self.addCleanup(sources.set_skip, [])

    def lib(self):
        return library.Library(vault_with(self.FILES))

    def test_a_new_owner_has_no_folder_left_out(self):
        sources.set_skip(settings.blank()["skip"])
        paths = {n["path"] for n in self.lib().overview()["notes"]}
        self.assertLessEqual({"raw/Secret.md", "memory/M.md"}, paths)
        self.assertFalse(any(p.startswith(".claude") for p in paths))
        # Settings from before the choice keep what was always left out.
        self.assertEqual(settings.normalize({"name": "Alex"})["skip"], settings.OLD_SKIP)
        self.assertEqual(settings.normalize({"skip": ["Old", "a/b", ""]})["skip"], ["Old"])

    def test_a_folder_that_is_gone_says_so(self):
        self.assertEqual(self.lib().overview()["problem"], "")
        self.assertIn("not there", library.Library(Path(tempfile.gettempdir()) / "no such notes").overview()["problem"])

    def test_only_notes_people_wrote_are_listed(self):
        paths = {n["path"] for n in self.lib().overview()["notes"]}
        self.assertEqual(paths, {"Goals.md", "Notes/Alpha.md", "Projects/Alpha.md", "Projects/Beta.md", "Notes/Mixed.md"})

    def test_the_reader_refuses_anything_outside_the_index(self):
        lib = self.lib()
        for path in ("raw/Secret.md", "../x.md", "memory/M.md", "C:/Windows/win.ini", "00 Inbox/Geheimsache 1/Akte.md"):
            self.assertIsNone(lib.note(path), path)

    def test_title_comes_from_the_first_heading_and_is_not_shown_twice(self):
        note = self.lib().note("Goals.md")
        self.assertEqual(note["title"], "My Goals")
        self.assertNotIn("My Goals", note["html"])

    def test_private_lines_are_cut_and_counted_and_never_searchable(self):
        lib = self.lib()
        note = lib.note("Notes/Mixed.md")
        self.assertEqual(note["hiddenLines"], 1)
        self.assertNotIn("Akte 999", note["html"])
        self.assertEqual(lib.search("Geheimsache"), [])

    def test_a_link_prefers_the_note_in_its_own_folder(self):
        lib = self.lib()
        lib.refresh()
        self.assertEqual(lib.find_note("Alpha", "Projects/Beta.md"), "Projects/Alpha.md")
        self.assertEqual(lib.find_note("Notes/Alpha"), "Notes/Alpha.md")

    def test_backlinks_list_who_points_here(self):
        lib = self.lib()
        self.assertEqual([b["path"] for b in lib.note("Goals.md")["backlinks"]], ["Notes/Alpha.md"])

    def test_search_finds_words_in_the_text_with_a_snippet(self):
        hits = self.lib().search("budgets")
        self.assertEqual(hits[0]["path"], "Notes/Alpha.md")
        self.assertIn("budgets", hits[0]["snippet"])

    def test_assets_only_serve_known_images(self):
        lib = self.lib()
        self.assertEqual(lib.asset("Notes/pic.png")[1], "image/png")
        for path in ("raw/hidden.png", "Notes/page.pdf", "Goals.md", "../x.png"):
            self.assertEqual(lib.asset(path), (None, None), path)

    def test_pages_only_serve_known_html_files_without_private_words(self):
        lib = self.lib()
        self.assertIn(b"live cards", lib.page("Projects/Cards.html"))
        for path in ("raw/Hidden.html", "Projects/Leak.html", "Goals.md", "Notes/pic.png", "../x.html",
                     "C:/Windows/win.ini"):
            self.assertIsNone(lib.page(path), path)

    def test_a_changed_file_is_picked_up_and_an_unchanged_one_is_not_reread(self):
        root = vault_with(self.FILES)
        lib = library.Library(root, ttl=0)
        lib.refresh()
        before = lib.notes["Goals.md"]
        lib.refresh()
        self.assertIs(lib.notes["Goals.md"], before)
        import os
        (root / "Goals.md").write_text("# New\n", encoding="utf-8")
        os.utime(root / "Goals.md", (1, 1))
        lib.refresh()
        self.assertEqual(lib.notes["Goals.md"]["title"], "New")


if __name__ == "__main__":
    unittest.main()
