"""Daytag for a new owner: settings, Obsidian tasks, the schedule check and the setup's save."""
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import settings
import sources
import tools

sources.load_private(Path(__file__).resolve().parent / "stand-in-terms.txt")
TODAY = date(2026, 11, 23)


def vault_with(files):
    root = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def newcomer(vault, **sources_on):
    """A new owner who switched on only what is named."""
    data = {"name": "Alex", "vault": str(vault), "sources": {sid: {"on": sid in sources_on} for sid in settings.SOURCE_IDS}}
    return settings.normalize(data)


class FakeFeed:
    def __init__(self, events):
        self.events = events

    def connected(self):
        return True

    def snapshot(self, today, days):
        return self.events, 1795400000.0, ""


def event(day, title, people=3, clock="10:00"):
    return {"date": day, "time": clock, "title": title, "where": "", "people": people, "conference": True, "join": ""}


class Settings(unittest.TestCase):
    def test_a_blank_profile_has_the_general_sources_and_no_vault_sources(self):
        blank = settings.blank()
        self.assertEqual(blank["vault"], "")
        self.assertTrue(blank["sources"]["calendar"]["on"])
        self.assertTrue(blank["sources"]["board"]["on"])
        # No vault, so nothing that reads notes can be on.
        for sid in ("library", "tasks", "ask", "openItems", "pipeline"):
            self.assertFalse(blank["sources"][sid]["on"], sid)

    def test_refuses_what_cannot_be_meant(self):
        for bad in ({"board": {"owner": "a b"}}, {"board": {"owner": "x", "number": "ten"}},
                    {"board": {"areaField": 'Area"){ x }'}}, {"vault": "/no/such/folder/anywhere"},
                    {"sources": {"goals": {"on": True, "path": "../outside.md"}}},
                    {"sources": {"goals": {"on": True, "path": "C:/Windows/x.md"}}},
                    {"sources": {"goals": {"on": True, "path": "Goals.txt"}}}, {"name": "<script>"}):
            with self.assertRaises(ValueError, msg=bad):
                settings.normalize(bad)

    def test_save_and_load_round_trip_in_its_own_folder(self):
        folder = Path(tempfile.mkdtemp())
        old = os.environ.get("DAYTAG_HOME")
        os.environ["DAYTAG_HOME"] = str(folder)
        try:
            vault = vault_with({})
            settings.save({"name": "Alex", "vault": str(vault), "board": {"owner": "alex-dev", "number": 3, "areaField": "Bereich"}})
            loaded = settings.load()
            self.assertEqual(loaded["name"], "Alex")
            self.assertEqual(loaded["board"]["areaField"], "Bereich")
            self.assertEqual(Path(loaded["vault"]), vault.resolve())
            self.assertTrue((folder / "daytag.json").is_file())
        finally:
            if old is None:
                os.environ.pop("DAYTAG_HOME")
            else:
                os.environ["DAYTAG_HOME"] = old

    def test_board_query_uses_the_owners_field_names_and_kind(self):
        query = sources.board_query("org", {"areaField": "Bereich", "dueField": "Due date", "doneField": ""})
        self.assertIn("organization(login:$owner)", query)
        self.assertIn('fieldValueByName(name:"Bereich")', query)
        self.assertIn('fieldValueByName(name:"Due date")', query)
        self.assertNotIn("erledigt:", query)
        self.assertIn("user(login:$owner)", sources.board_query())

    def test_a_missing_privacy_list_only_stops_the_start_when_asked_for(self):
        missing = Path(tempfile.mkdtemp()) / "none.txt"
        try:
            self.assertEqual(sources.load_private(missing, required=False), 0)
            self.assertIsNone(sources.PRIVATE.search("anything at all"))
            with self.assertRaises(SystemExit):
                sources.load_private(missing, required=True)
        finally:
            sources.load_private(Path(__file__).resolve().parent / "stand-in-terms.txt")


class Tasks(unittest.TestCase):
    def test_reads_the_three_ways_to_write_a_due_date(self):
        lines = {"- [ ] Send the offer 📅 2026-11-25 ⏫": ("Send the offer", "2026-11-25", "high"),
                 "* [ ] Call the bank [due:: 2026-11-24] [priority:: low]": ("Call the bank", "2026-11-24", "low"),
                 "- [/] Draft the deck @due(2026-11-30)": ("Draft the deck", "2026-11-30", ""),
                 "1. [ ] Pay rent 📅 2026-12-01 🔁 every month ^abc123": ("Pay rent", "2026-12-01", "")}
        for line, (title, due, priority) in lines.items():
            task = sources.task_from(line, TODAY)
            self.assertEqual((task["title"], task["due"], task["priority"]), (title, due, priority), line)

    def test_done_undated_and_scheduled_tasks(self):
        self.assertIsNone(sources.task_from("- [x] Done already 📅 2026-11-25", TODAY))
        self.assertIsNone(sources.task_from("- [ ] No date here", TODAY))
        self.assertIsNone(sources.task_from("Plain line 📅 2026-11-25", TODAY))
        task = sources.task_from("- [ ] Sort receipts ⏳ 2026-11-26", TODAY)
        self.assertEqual((task["kind"], task["due"]), ("scheduled", "2026-11-26"))

    def test_index_skips_hidden_folders_and_private_rows_and_rereads_changes(self):
        root = vault_with({"Work/todo.md": "- [ ] Ship it 📅 2026-11-24\n- [ ] Geheimsache reply 📅 2026-11-24\n",
                           ".obsidian/x.md": "- [ ] Not a note 📅 2026-11-24\n", "raw/y.md": "- [ ] Raw 📅 2026-11-24\n"})
        self.assertEqual(len(sources.TaskIndex(root, ttl=0).scan()), 3)
        sources.set_skip(["raw"])
        self.addCleanup(sources.set_skip, [])
        index = sources.TaskIndex(root, ttl=0)
        data, src = sources.read_tasks(index, TODAY)
        self.assertEqual([t["title"] for t in data["items"]], ["Ship it"])
        self.assertEqual(data["hidden"], 1)
        self.assertEqual(src["state"], "fresh")
        (root / "Work/todo.md").write_text("- [ ] Ship it later 📅 2026-11-27\n", encoding="utf-8")
        os.utime(root / "Work/todo.md", (1, 1))
        self.assertEqual([t["title"] for t in sources.read_tasks(index, TODAY)[0]["items"]], ["Ship it later"])


class Newcomer(unittest.TestCase):
    def test_tasks_and_calendar_only(self):
        root = vault_with({"Inbox.md": "- [ ] Send the offer 📅 2026-11-25\n- [ ] Far away 📅 2027-01-10\n"})
        profile = newcomer(root, tasks=1, calendar=1, library=1)
        state = sources.build_state(root, None, TODAY, (), FakeFeed([event("2026-11-24", "Pitch with Fjordwerk")]), profile=profile)
        self.assertEqual({s["id"] for s in state["sources"]}, {"tasks", "calendar"})
        self.assertEqual(sorted(state["pagesOff"]), ["ask", "board", "pipeline"])
        titles = [a["title"] for a in state["alerts"]]
        self.assertEqual(titles, ["Pitch with Fjordwerk", "Send the offer"])
        task = next(a for a in state["alerts"] if a["title"] == "Send the offer")
        self.assertEqual((task["eyebrow"], task["note"]), ("Your task", "Inbox.md"))
        self.assertIn("Far away", [r["title"] for r in state["agenda"]])
        self.assertEqual(state["projects"]["rows"], [])

    def test_priority_mode_keeps_unmarked_tasks_off_home(self):
        root = vault_with({"a.md": "- [ ] Plain 📅 2026-11-25\n- [ ] Marked 📅 2026-11-25 🔼\n"})
        profile = dict(newcomer(root, tasks=1), tasks={"home": "priority"})
        state = sources.build_state(root, None, TODAY, profile=profile)
        self.assertEqual([a["title"] for a in state["alerts"]], ["Marked"])

    def test_a_source_switched_off_reads_nothing(self):
        root = vault_with({"Open matters.md": "| Matter | Next step | Owner | Due | Note |\n|---|---|---|---|---|\n| X | Y | Alex | 24.11. | |\n"})
        state = sources.build_state(root, None, TODAY, profile=newcomer(root))
        self.assertEqual(state["open"]["items"], [])
        self.assertEqual(state["sources"], [])
        keep = sources.ME
        try:
            sources.set_owner("Alex")
            state = sources.build_state(root, None, TODAY, profile=newcomer(root, openItems=1))
            self.assertTrue(state["open"]["items"][0]["mine"])
        finally:
            sources.ME = keep

    def test_board_areas_become_projects_without_a_list(self):
        class Board:
            number = 1

            def snapshot(self, wait=False):
                return [{"title": "Fix login", "status": "HIGH", "bereich": "App"},
                        {"title": "Write post", "status": "MID", "bereich": "Blog"}], 1795400000.0, ""
        root = vault_with({})
        state = sources.build_state(root, Board(), TODAY, profile=newcomer(root, board=1))
        self.assertEqual([p["name"] for p in state["projects"]["rows"]], ["App", "Blog"])


class Schedule(unittest.TestCase):
    def state(self, events, cards=(), files=None):
        class Board:
            number = 1

            def snapshot(self, wait=False):
                return list(cards), 1795400000.0, ""
        root = vault_with(files or {})
        return sources.build_state(root, Board(), TODAY, (), FakeFeed(events), profile=newcomer(root, board=1, calendar=1, library=1, tasks=1))

    def test_a_meeting_nobody_prepared_for_is_named_with_a_suggestion(self):
        found = self.state([event("2026-11-26", "Pitch with Fjordwerk")])["schedule"]["items"]
        self.assertEqual([f["kind"] for f in found], ["prep"])
        self.assertEqual(found[0]["suggest"], {"title": "Prepare: Pitch with Fjordwerk", "due": "2026-11-25"})

    def test_a_card_a_task_or_a_note_covers_the_meeting(self):
        meeting = [event("2026-11-26", "Pitch with Fjordwerk")]
        card = [{"title": "Fjordwerk deck", "status": "MID", "bereich": "Sales"}]
        self.assertEqual(self.state(meeting, card)["schedule"]["counts"]["prep"], 0)
        self.assertEqual(self.state(meeting, files={"x.md": "- [ ] Fjordwerk numbers 📅 2026-11-25\n"})["schedule"]["counts"]["prep"], 0)
        self.assertEqual(self.state(meeting, files={"Fjordwerk.md": "# Fjordwerk\n"})["schedule"]["counts"]["prep"], 0)

    def test_only_generic_words_in_common_do_not_cover(self):
        meeting = [event("2026-11-26", "Interview Fjordwerk")]
        card = [{"title": "Interview prep for Lindbergh", "status": "HIGH", "bereich": "Jobs", "dueField": "2026-11-30"}]
        self.assertEqual(self.state(meeting, card)["schedule"]["counts"]["prep"], 1)

    def test_clash_undated_high_and_routine(self):
        events = [event("2026-11-24", "Call one"), event("2026-11-24", "Call two"), event("2026-11-25", "Dentist", people=1, clock="09:00")]
        events[2]["conference"] = False
        cards = [{"title": "Taxes", "status": "HIGH", "bereich": "Home"}]
        counts = self.state(events, cards)["schedule"]["counts"]
        self.assertEqual((counts["clash"], counts["undated"]), (1, 1))
        # A dentist slot with nobody else is routine, not a meeting to prepare.
        self.assertEqual(counts["prep"], 2)


class SetupSave(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.old = os.environ.get("DAYTAG_HOME")
        os.environ["DAYTAG_HOME"] = str(self.folder)
        self.me = sources.ME

    def tearDown(self):
        sources.ME = self.me
        if self.old is None:
            os.environ.pop("DAYTAG_HOME", None)
        else:
            os.environ["DAYTAG_HOME"] = self.old
        sources.load_private(Path(__file__).resolve().parent / "stand-in-terms.txt")

    def test_first_start_opens_the_setup_and_a_save_adds_tools_only(self):
        import server
        app = server.App(None, "127.0.0.1", [], "sonnet")
        self.assertTrue(app.needs_setup)
        self.assertTrue(app.state()["setupNeeded"])
        app.tools.apply({"action": "add", "name": "Mine", "url": "https://mine.example/", "pinned": True})
        vault = vault_with({"a.md": "- [ ] Thing 📅 2026-11-25\n"})
        result = app.save_setup({"profile": {"name": "Alex", "vault": str(vault), "sources": {
            "tasks": {"on": True}, "library": {"on": True}, "calendar": {"on": True}, "ask": {"on": False}},
            "board": {"owner": "alex-dev", "number": 4}}, "tools": ["gmail", "slack", "nonsense"]})
        self.assertFalse(app.needs_setup)
        self.assertEqual(sorted(result["added"]), ["Board", "Gmail", "Slack"])
        names = [t["name"] for t in app.tools.load()["tools"]]
        self.assertEqual(names[0], "Mine")
        board = next(t for t in app.tools.load()["tools"] if t["name"] == "Board")
        self.assertEqual(board["url"], "https://github.com/users/alex-dev/projects/4")
        saved = json.loads((self.folder / "daytag.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["board"]["owner"], "alex-dev")
        self.assertTrue(saved["sources"]["tasks"]["on"])
        # Saving again adds nothing twice.
        again = app.save_setup({"profile": {}, "tools": ["gmail"]})
        self.assertEqual(again["added"], [])

    def test_a_save_keeps_board_settings_the_form_does_not_show(self):
        import server
        vault = vault_with({})
        settings.save({"vault": str(vault), "board": {"owner": "alex-dev", "number": 4, "aging": {
            "repo": "alex-dev/brain", "workflow": "aging.yml", "script": "scripts/aging.py"}}})
        app = server.App(None, "127.0.0.1", [], "sonnet")
        self.assertFalse(app.needs_setup)
        app.save_setup({"profile": {"board": {"owner": "alex-dev", "number": 5, "areaField": "Area"}}})
        saved = json.loads((self.folder / "daytag.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["board"]["number"], 5)
        self.assertEqual(saved["board"]["aging"]["repo"], "alex-dev/brain")


class Catalog(unittest.TestCase):
    def test_catalog_links_are_valid_and_ids_unique(self):
        entries = json.loads((Path(tools.__file__).parent / "tools.catalog.json").read_text(encoding="utf-8"))
        ids = [e["id"] for e in entries]
        self.assertEqual(len(ids), len(set(ids)))
        for e in entries:
            url = e["url"].replace("{vault}", "My%20Vault")
            self.assertEqual(tools.clean_url(url), url)
            self.assertTrue(e["group"])


if __name__ == "__main__":
    unittest.main()
