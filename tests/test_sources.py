import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sources
from shape import build_state
import tools

TERMS = Path(__file__).resolve().parent / "stand-in-terms.txt"
sources.load_private(TERMS)

TODAY = date(2026, 11, 3)


class FakeBoard:
    number = 10

    def __init__(self, raw=None, error=""):
        self.raw, self.error = raw, error

    def snapshot(self, wait=False):
        return self.raw, 1793750000.0, self.error


def vault_with(files):
    root = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


OPEN = """---
type: moc
---
# Open matters

> **Stand 02.11.2026.** Eine Zeile je Vorgang.

| Vorgang | Nächster Schritt | Frist | Wer ist dran | Akte |
|---|---|---|---|---|
| **Lindqvist: Rueckzahlung** | Antworten | **Fr 06.11.** | Alex | [[Lindqvist Rueckzahlung|Akte L]] |
| **Fjordwerk** | Abwarten | **Do 12.11.** | Fjordwerk | [[Fjordwerk]] |
| **Geheimsache Akte 999** | Warten | keine | Jemand | [[Übergabe]] |
"""


class PrivateList(unittest.TestCase):
    def tearDown(self):
        sources.load_private(TERMS)

    def test_a_missing_or_empty_list_stops_the_start(self):
        root = Path(tempfile.mkdtemp())
        (root / "empty.txt").write_text("# only a comment\n\n", encoding="utf-8")
        for name in ("empty.txt", "not-there.txt"):
            with self.assertRaises(SystemExit):
                sources.load_private(root / name)

    def test_a_failed_load_keeps_the_words_it_had(self):
        with self.assertRaises(SystemExit):
            sources.load_private(Path(tempfile.mkdtemp()) / "not-there.txt")
        self.assertTrue(sources.PRIVATE.search("Geheimsache"))

    def test_words_match_literally_in_any_case_and_comments_do_not_count(self):
        path = Path(tempfile.mkdtemp()) / "terms.txt"
        path.write_text("﻿A.B (c)\n# skip\n", encoding="utf-8")
        sources.load_private(path)
        self.assertTrue(sources.PRIVATE.search("x a.b (C) y"))
        self.assertFalse(sources.PRIVATE.search("axb c"))
        self.assertFalse(sources.PRIVATE.search("skip"))


class Dates(unittest.TestCase):
    def test_german_forms(self):
        self.assertEqual(sources.parse_dates("Fr 06.11.", TODAY), [date(2026, 11, 6)])
        self.assertEqual(sources.parse_dates("Mi 26.08 15:00", TODAY), [date(2026, 8, 26)])
        self.assertEqual(sources.parse_dates("Stand 02.11.2026", TODAY), [date(2026, 11, 2)])

    def test_next_january_is_ahead_not_behind(self):
        self.assertEqual(sources.parse_dates("13.01.", TODAY), [date(2027, 1, 13)])

    def test_numbers_that_are_not_dates(self):
        for text in ("Fable 5.1", "2.500 EUR", "3.5%", "12.50 EUR", "99.99"):
            self.assertEqual(sources.parse_dates(text, TODAY), [], text)


class Parsing(unittest.TestCase):
    def test_pipe_inside_a_wikilink_does_not_split_the_cell(self):
        rows = sources.md_table(["| A | B |", "|---|---|", "| [[x|y]] | z |"])
        self.assertEqual(rows[0]["B"], "z")

    def test_headline_stops_at_the_first_sentence_even_after_capitals(self):
        self.assertEqual(sources.first_sentence("Brightway, FINALE RUNDE. Das ist die Nummer eins."),
                         ("Brightway, FINALE RUNDE", "Das ist die Nummer eins."))

    def test_clean_md(self):
        self.assertEqual(sources.clean_md("🏁 **Brightway** [[People/Tom|Tom]] and [[Notes/Foo]]"), "Brightway Tom and Foo")


class Rules(unittest.TestCase):
    def test_private_row_is_hidden_and_counted(self):
        data, src = sources.read_open_items(vault_with({"Open matters.md": OPEN}), TODAY, "Open matters.md")
        self.assertEqual([i["name"] for i in data["items"]], ["Lindqvist: Rueckzahlung", "Fjordwerk"])
        self.assertEqual(data["hidden"], 1)
        self.assertEqual(src["state"], "fresh")

    def test_missing_file_is_unknown_not_empty_success(self):
        _, src = sources.read_open_items(vault_with({}), TODAY)
        self.assertEqual(src["state"], "unknown")

    def test_old_source_is_stale(self):
        src = sources.source("x", "X", "x", date(2026, 10, 1), 7, TODAY)
        self.assertEqual((src["state"], src["ageDays"]), ("stale", 33))

    def test_my_deadline_outranks_everything_and_says_why(self):
        state = build_state(vault_with({"Open matters.md": OPEN}), FakeBoard([]), TODAY)
        first = state["cards"][0]
        self.assertEqual(first["title"], "Lindqvist: Rueckzahlung")
        self.assertIn("3 days", first["why"])
        self.assertEqual(first["tag"], "due Fri 06.11.")

    def test_board_failure_is_reported_and_keeps_no_fake_zero(self):
        state = build_state(vault_with({}), FakeBoard(None, "not logged in"), TODAY)
        board = next(s for s in state["sources"] if s["id"] == "board")
        self.assertEqual((board["state"], board["note"]), ("unknown", "not logged in"))

    def test_passed_date_on_a_high_card_is_flagged(self):
        raw = [{"title": "Harrowgates Runde 2 Mi 26.08 15:00", "status": "HIGH", "bereich": "Jobs"},
               {"title": "Lindqvist antworten bis 06.11.", "status": "HIGH", "bereich": "Money"},
               {"title": "Alt", "status": "Archive", "bereich": "Jobs"}]
        data, _ = sources.read_board(FakeBoard(raw), TODAY)
        self.assertEqual([i["passed"] for i in data["items"]], [True, False])
        self.assertEqual(data["counts"]["Archive"], 1)

    def test_brief_reads_both_formats_and_merges_into_the_same_deadline(self):
        new = "---\ncreated: 2026-11-03\n---\n## THE ONE THING TODAY\n\n**Anruf an Lindqvist.** Heute.\n"
        old = "---\ndate: 2026-11-03\n---\n> **THE ONE THING TODAY:** Anruf an Lindqvist.\n"
        for text in (new, old):
            root = vault_with({"outputs/morning-brief-latest.md": text, "Open matters.md": OPEN})
            state = build_state(root, FakeBoard([]), TODAY)
            self.assertIn("Anruf an Lindqvist", state["brief"]["oneThing"])
            self.assertIn("morning brief says the same", state["cards"][0]["why"])
            self.assertEqual([c for c in state["cards"] if c["kind"] == "brief"], [])

    def test_pipeline_reads_headings_with_a_dot_or_a_dash(self):
        text = ("---\nupdated: 2026-11-02\n---\n## 🔴 Hot\n### [[KORA]] · *Manager KI* · ✅ **ABGESCHICKT 02.11.2026**\n"
                "### Vantor AI — Senior Consultant ⭐ — ⚠️ SILENT\n")
        data, _ = sources.read_pipeline(vault_with({"Applications.md": text}), TODAY, "Applications.md")
        self.assertEqual([(x["firm"], x["role"]) for x in data["hot"]],
                         [("KORA", "Manager KI"), ("Vantor AI", "Senior Consultant ⭐")])
        self.assertEqual(data["hot"][1]["status"], "SILENT")

    def test_a_rejection_under_hot_does_not_count_as_live_or_as_sent(self):
        text = ("---\nupdated: 2026-11-02\n---\n## 🔴 Hot\n### [[A]] · *x* · ✅ **ABGESCHICKT 02.10.2026**\n"
                "### [[B]] · *y* · ❌ **ABSAGE 20.10.2026** (beworben 07.08.)\n## 🟡 Warm\n### [[C]] · *z* · GESTRICHEN 18.09.\n")
        data, _ = sources.read_pipeline(vault_with({"Applications.md": text}), TODAY, "Applications.md")
        self.assertEqual([x["firm"] for x in data["hot"]], ["A"])
        self.assertEqual(data["warm"], [])
        self.assertEqual([x["firm"] for x in data["ended"]], ["B", "C"])
        self.assertEqual(data["lastSent"], "2026-10-02")

    def test_a_date_is_only_a_deadline_if_it_was_ahead_when_the_card_was_made(self):
        made = date(2026, 10, 13)
        self.assertIsNone(sources.deadline_of("Worker deployen (Stand 17.06., 6 Commits)", made, None, TODAY))
        self.assertIsNone(sources.deadline_of("Beworben 05.08", date(2026, 8, 12), None, TODAY))
        self.assertEqual(sources.deadline_of("Interview Di 20.10.", made, None, TODAY), date(2026, 10, 20))
        # Reference words count even when the date is later than the card.
        self.assertIsNone(sources.deadline_of("Anker-Code (SQL ausgefuehrt 20.10.)", made, None, TODAY))
        self.assertIsNone(sources.deadline_of("Antwort offen seit 20.10.", made, None, TODAY))

    def test_a_status_set_after_the_date_is_a_decision_and_stays(self):
        made = date(2026, 8, 1)
        self.assertIsNone(sources.deadline_of("Termin 26.08", made, date(2026, 9, 2), TODAY))
        self.assertEqual(sources.deadline_of("Termin 26.08", made, date(2026, 8, 2), TODAY), date(2026, 8, 26))

    def test_daily_reports_age_by_their_date_alone(self):
        self.assertEqual(sources.deadline_of("Nachtaudit 17.10: 59 Befunde", date(2026, 10, 17), None, TODAY), date(2026, 10, 17))

    def test_passed_rule_runs_only_when_the_job_has_it_and_page_says_which(self):
        raw = [{"title": "Termin 26.08", "status": "HIGH", "bereich": "Jobs", "createdAt": "2026-08-01T00:00:00Z"}]
        off, _ = sources.read_board(FakeBoard(raw), TODAY, {"news": 14, "old": 30, "done": 30})
        on, _ = sources.read_board(FakeBoard(raw), TODAY, {"news": 14, "old": 30, "done": 30, "passed": 7})
        self.assertEqual((off["items"][0]["agesTo"], off["items"][0]["passed"]), (None, True))
        self.assertEqual((on["items"][0]["agesTo"], on["items"][0]["agesOn"]), ("Old", "2026-09-03"))
        src = {s: sources.source(s, s, s, TODAY, 1, TODAY) for s in ("board", "brief", "pipeline", "liveness", "goals", "open-items")}
        base = {"open": {"items": []}, "brief": {}, "pipeline": {"hot": [], "warm": [], "ended": []}, "liveness": {"still": 0}, "goals": {"now": ""}}
        self.assertIn("No rule ages", sources.build_cards(dict(base, board=off), src)[0]["why"])
        self.assertIn("daily job moves", sources.build_cards(dict(base, board=on), src)[0]["why"])

    def test_a_goal_the_tracker_says_is_over_is_not_shown_as_a_goal(self):
        apps = ("---\nupdated: 2026-11-02\n---\n## 🔴 Hot\n### ~~[[Brightway]] — *Head of Procurement*~~ — ❌ **ABSAGE 21.10.2026** nach dem AC\n"
                "### [[KORA]] · *KI* · ✅ **ABGESCHICKT 02.11.2026**\n## ⚪ Closed\n### [[Volta]] · *x* · out\n")
        goals = "# G\n## Right now\n- [ ] **%s — FINALE RUNDE.** Nummer eins\n## Next\n"
        def cards(firm):
            root = vault_with({"Applications.md": apps, "Goals.md": goals % firm})
            return next(c for c in build_state(root, FakeBoard([]), TODAY)["cards"] if c["id"] == "goals")
        brightway = cards("Brightway")
        self.assertEqual(brightway["title"], '"Right now" still says Brightway')
        self.assertIn("ABSAGE 21.10.2026", brightway["body"])
        self.assertIn("not shown as a goal", brightway["why"])
        self.assertEqual(cards("Volta")["title"], '"Right now" still says Volta')
        self.assertEqual(cards("KORA")["eyebrow"], "Goals, Right now")
        self.assertEqual(cards("Neue Firma")["eyebrow"], "Goals, Right now")

    def test_a_live_entry_for_the_same_firm_wins_over_an_old_finished_one(self):
        pipe = {"hot": [{"link": "Halvor"}], "warm": [], "ended": [{"link": "Halvor", "status": "ABSAGE"}], "closedFirms": ["Halvor"]}
        self.assertIsNone(sources.finished_in_tracker("Halvor anrufen", pipe))

    def test_rules_are_read_from_the_job_itself(self):
        script = "NEWS_MAX_TAGE = 14\nOLD_MAX_TAGE = 30\nDONE_MAX_TAGE = 21\n"
        root = vault_with({".claude/scripts/board_aging.py": script})
        self.assertEqual(sources.aging_rules(root, script=".claude/scripts/board_aging.py"), {"news": 14, "old": 30, "done": 21})
        self.assertIsNone(sources.aging_rules(vault_with({})))

    def test_next_step_mirrors_the_job(self):
        rules = {"news": 14, "old": 30, "done": 30}
        step = lambda status, area, title, stamped=None: sources.next_step(status, area, title, stamped, rules, TODAY)
        # "Older than" means the first eligible day is one past the limit.
        self.assertEqual(step("Done", "Jobs", "x", "2026-10-21"), ("Archive", "2026-11-21"))
        self.assertEqual(step("Old", "Jobs", "x", "2026-10-21"), ("Archive", "2026-11-21"))
        self.assertEqual(step("No status", "News", "NEWS 01.11 · y"), ("Old", "2026-11-16"))
        self.assertEqual(step("Old", "News", "NEWS 01.11 · y"), ("Archive", "2026-12-02"))
        # A December headline read in January belongs to last year, same as in the job.
        self.assertEqual(sources.news_date("NEWS 28.12 · y", date(2027, 1, 5)), date(2026, 12, 28))
        # Done without a date: the job stamps it first, so its clock has not started.
        self.assertEqual(step("Done", "Code", "x"), ("Archive", None))
        # These have no rule and stay until someone moves them.
        for status in ("HIGH", "MID", "LOW", "No status"):
            self.assertEqual(step(status, "Brain", "Nachtaudit 17.10"), (None, None))

    def test_nothing_is_dropped_and_passed_only_counts_in_the_lanes(self):
        raw = [{"title": "Nachtaudit 17.10", "bereich": "Brain"},
               {"title": "Alt 01.08", "status": "Done", "bereich": "Code", "erledigt am": "2026-10-21"},
               {"title": "Weg", "status": "Archive", "bereich": "News"},
               {"title": "Termin 26.08", "status": "HIGH", "bereich": "Jobs"}]
        data, _ = sources.read_board(FakeBoard(raw), TODAY, {"news": 14, "old": 30, "done": 30})
        self.assertEqual(len(data["items"]) + len(data["archived"]), len(raw))
        self.assertEqual([i["title"] for i in data["items"] if i["passed"]], ["Termin 26.08"])
        self.assertEqual(data["bereiche"], ["Brain", "Code", "Jobs", "News"])

    def test_links_are_only_offered_when_the_target_exists(self):
        root = vault_with({"Open matters.md": OPEN, "00 Inbox/Lindqvist Rueckzahlung.md": "x", "Goals.md": "# G\n",
                           "Companies/KORA.md": "x",
                           "Applications.md": "## 🔴 Hot\n### [[KORA]] · *KI* · x\n### [[Nowhere]] · *y* · x\n"})
        state = build_state(root, FakeBoard([]), TODAY)
        by_name = {i["name"]: i["notePath"] for i in state["open"]["items"]}
        self.assertEqual(by_name, {"Lindqvist: Rueckzahlung": "00 Inbox/Lindqvist Rueckzahlung.md", "Fjordwerk": None})
        self.assertEqual([x["notePath"] for x in state["pipeline"]["hot"]], ["Companies/KORA.md", None])
        links = {s["id"]: s.get("notePath") for s in state["sources"]}
        self.assertEqual((links["goals"], links["calendar"], links["liveness"]), ("Goals.md", None, None))

    def test_private_text_in_a_card_body_hides_the_whole_card(self):
        raw = [{"title": "Anruf erledigen", "status": "HIGH", "content": {"body": "wegen Akte 999"}},
               {"title": "Normal", "status": "HIGH", "content": {"body": "Details"}}]
        data, _ = sources.read_board(FakeBoard(raw), TODAY)
        self.assertEqual([i["title"] for i in data["items"]], ["Normal"])
        self.assertEqual((data["hidden"], data["items"][0]["body"]), (1, "Details"))

    def test_goals_reads_the_first_open_line_of_right_now(self):
        text = "# Goals\n## 🎯 Right now (ONE thing)\nIntro\n- [x] done\n- [ ] 🏁 **Finish it.** More\n## Next\n- [ ] other\n"
        data, _ = sources.read_goals(vault_with({"Goals.md": text}), TODAY)
        self.assertEqual(data["now"], "Finish it. More")

    def test_notes_index_skips_private_and_generated_folders(self):
        root = vault_with({"Notes/a.md": "x", "raw/b.md": "x", "00 Inbox/Geheimsache 1/c.md": "x",
                           "Notes/Akte 999.md": "x", ".trash/d.md": "x"})
        self.assertEqual([n["path"] for n in sources.read_notes(root)], ["Notes/a.md", "raw/b.md"])
        sources.set_skip(["raw"])
        self.addCleanup(sources.set_skip, [])
        self.assertEqual([n["path"] for n in sources.read_notes(root)], ["Notes/a.md"])


class EventNotes(unittest.TestCase):
    TITLES = {"fjordwerk ag": "Companies/Fjordwerk AG.md",
              "fjordwerk ag spickzettel 2026-11-17": "Projects/Jobs/Fjordwerk AG/Fjordwerk AG Spickzettel 2026-11-17.md",
              "fjordwerk ag spickzettel 2026-10-01": "Projects/Jobs/Fjordwerk AG/Fjordwerk AG Spickzettel 2026-10-01.md",
              "lindqvist": "People/Lindqvist.md"}

    def event(self, title, day="2026-11-17"):
        return {"title": title, "date": day}

    def test_the_prep_note_with_the_event_date_wins(self):
        self.assertEqual(sources.event_note(self.event("Alex - Fjordwerk AG Call - 10566"), self.TITLES),
                         "Projects/Jobs/Fjordwerk AG/Fjordwerk AG Spickzettel 2026-11-17.md")

    def test_a_prep_note_under_the_short_name_is_found(self):
        # The company note is "Fjordwerk AG", the event and the prep note only say "Fjordwerk".
        titles = dict(self.TITLES, **{"fjordwerk spickzettel 2026-11-19": "Projects/Jobs/Fjordwerk AG/Fjordwerk Spickzettel 2026-11-19.md"})
        self.assertEqual(sources.event_note(self.event("Fjordwerk, 1. Interview Lead Buyer (Teams)", "2026-11-19"), titles),
                         "Projects/Jobs/Fjordwerk AG/Fjordwerk Spickzettel 2026-11-19.md")

    def test_a_dated_note_whose_first_word_is_not_in_the_event_stays_out(self):
        titles = dict(self.TITLES, **{"journal 2026-11-19": "Journals/Journal 2026-11-19.md"})
        self.assertIsNone(sources.event_note(self.event("Dentist", "2026-11-19"), titles))

    def test_without_a_prep_note_for_that_day_the_company_note(self):
        self.assertEqual(sources.event_note(self.event("Fjordwerk AG Call", "2026-12-01"), self.TITLES), "Companies/Fjordwerk AG.md")

    def test_a_name_counts_only_as_whole_words(self):
        self.assertIsNone(sources.event_note(self.event("Fjordwerkag Call"), self.TITLES))

    def test_a_single_word_still_finds_its_note(self):
        self.assertEqual(sources.event_note(self.event("Lunch with Lindqvist"), self.TITLES), "People/Lindqvist.md")

    def test_a_card_names_its_note_without_the_vault_at_hand(self):
        card = {"title": "Fjordwerk AG Erstgespraech: Di 17.11.",
                "body": "Vault: Projects/Jobs/Fjordwerk AG/Fjordwerk AG Spickzettel 2026-11-17.md"}
        self.assertEqual(sources.card_note(card, self.TITLES),
                         "Projects/Jobs/Fjordwerk AG/Fjordwerk AG Spickzettel 2026-11-17.md")
        self.assertIsNone(sources.card_note(dict(card, body="Vault: Notes/gone.md"), self.TITLES))


class Projects(unittest.TestCase):
    RAW = [{"title": "ORION Keys rotieren bis 20.11.", "status": "HIGH", "bereich": "Code"},
           {"title": "ORION alter Termin 01.08", "status": "MID", "bereich": "Code"},
           {"title": "ORION fertig", "status": "Archive", "bereich": "Code"},
           {"title": "Niemandes Karte", "status": "LOW", "bereich": "Code"},
           {"title": "Bewerbung", "status": "MID", "bereich": "Jobs"}]

    def build(self, registry, board=None, files=None):
        root = vault_with(files or {})
        board = board or FakeBoard(self.RAW)
        return build_state(root, board, TODAY, registry)["projects"]

    def test_progress_and_next_date_come_from_the_cards(self):
        row = self.build([{"id": "i", "name": "ORION", "match": "orion"}])["rows"][0]
        self.assertEqual((row["done"], row["total"], row["high"]), (1, 3, 1))
        self.assertEqual(row["next"], "2026-11-20")

    def test_a_project_without_cards_reports_zero_total_not_a_made_up_percent(self):
        row = self.build([{"id": "x", "name": "X", "match": "nichts"}])["rows"][0]
        self.assertEqual((row["total"], row["next"], row["state"]), (0, None, "unknown"))

    def test_cards_no_project_claims_stay_visible(self):
        data = self.build([{"id": "i", "name": "ORION", "match": "orion"}, {"id": "j", "name": "J", "bereich": "Jobs"}])
        self.assertEqual([data["cards"][n]["title"] for n in data["unclaimedIdx"]], ["Niemandes Karte"])

    def test_a_service_that_does_not_answer_outranks_every_other_state(self):
        board = FakeBoard(self.RAW)
        board.health = {"https://x/health": False}
        row = self.build([{"id": "i", "name": "I", "match": "orion", "health": "https://x/health", "state": "demo"}], board)["rows"][0]
        self.assertEqual(row["state"], "down")

    def test_a_human_state_is_kept_and_recent_work_counts_as_active(self):
        board = FakeBoard([])
        board.repos = {"new": "2026-11-01", "old": "2026-08-01"}
        rows = self.build([{"id": "a", "name": "A", "repo": "new"}, {"id": "b", "name": "B", "repo": "old"},
                           {"id": "c", "name": "C", "repo": "old", "state": "demo", "why": "paused"}], board)["rows"]
        self.assertEqual([r["state"] for r in rows], ["active", "quiet", "demo"])
        self.assertEqual(rows[2]["stateWhy"], "paused")


class Tools(unittest.TestCase):
    def store(self):
        root = Path(tempfile.mkdtemp())
        (root / "d.json").write_text('{"version":1,"tools":[{"id":"a","name":"A","url":"https://a.example/","group":"G"}]}', encoding="utf-8")
        return tools.ToolStore(root / "sub" / "t.json", root / "d.json")

    def test_defaults_load_until_something_changes_and_the_change_survives(self):
        s = self.store()
        self.assertFalse(s.path.exists())
        s.apply({"action": "pin", "id": "a", "pinned": True})
        self.assertTrue(s.path.exists())
        self.assertTrue(s.load()["tools"][0]["pinned"])

    def test_adding_keeps_what_is_there(self):
        s = self.store()
        s.apply({"action": "add", "name": "B Tool", "url": "https://b.example/", "group": "G"})
        self.assertEqual([t["name"] for t in s.load()["tools"]], ["A", "B Tool"])

    def test_order_moves_docked_tools_and_leaves_the_rest_in_place(self):
        s = self.store()
        s.apply({"action": "pin", "id": "a", "pinned": True})
        s.apply({"action": "add", "name": "B", "url": "https://b.example/"})
        s.apply({"action": "add", "name": "C", "url": "https://c.example/", "pinned": True})
        c = next(t["id"] for t in s.load()["tools"] if t["name"] == "C")
        s.apply({"action": "order", "tools": [c, "a"], "pages": ["today", "home"]})
        data = s.load()
        self.assertEqual([t["name"] for t in data["tools"]], ["C", "B", "A"])
        self.assertEqual(data["pageOrder"], ["today", "home"])
        with self.assertRaises(tools.ToolError):
            s.apply({"action": "order", "tools": ["a"]})
        with self.assertRaises(tools.ToolError):
            s.apply({"action": "order", "pages": ["home", "home"]})

    def test_pages_leave_and_rejoin_the_dock_but_home_stays(self):
        s = self.store()
        s.apply({"action": "page", "id": "brain", "docked": False})
        s.apply({"action": "page", "id": "ask", "docked": False})
        s.apply({"action": "page", "id": "brain", "docked": True})
        self.assertEqual(s.load()["hiddenPages"], ["ask"])
        with self.assertRaises(tools.ToolError):
            s.apply({"action": "page", "id": "home", "docked": False})
        with self.assertRaises(tools.ToolError):
            s.apply({"action": "page", "id": "../x", "docked": False})

    def test_added_tool_keeps_whether_we_built_it(self):
        s = self.store()
        s.apply({"action": "add", "name": "Ours", "url": "https://ours.example/", "own": True})
        s.apply({"action": "add", "name": "Theirs", "url": "https://theirs.example/"})
        self.assertEqual([t.get("own") for t in s.load()["tools"]], [None, True, False])

    def test_remove_takes_only_that_tool(self):
        s = self.store()
        s.apply({"action": "add", "name": "B", "url": "https://b.example/"})
        s.apply({"action": "remove", "id": "a"})
        self.assertEqual([t["name"] for t in s.load()["tools"]], ["B"])

    def test_refuses_links_that_are_unsafe_or_hold_secrets(self):
        s = self.store()
        for url in ("javascript:alert(1)", "file:///c:/x", "https://u:p@x.example/", "https://x.example/?key=abc",
                    "http://100.1.1.1/?a=1&token=abc", "https://x.example/#key=abc", "", "https://"):
            with self.assertRaises(tools.ToolError, msg=url):
                s.apply({"action": "add", "name": "X", "url": url})

    def test_shipped_tool_list_is_valid_and_holds_no_secret(self):
        data = tools.json.loads((Path(tools.__file__).parent / "tools.default.json").read_text(encoding="utf-8"))
        ids = [t["id"] for t in data["tools"]]
        self.assertEqual(len(ids), len(set(ids)))
        for t in data["tools"]:
            self.assertEqual(tools.clean_url(t["url"]), t["url"])

    def test_every_tool_a_project_names_exists(self):
        here = Path(tools.__file__).parent
        ids = {t["id"] for t in tools.json.loads((here / "tools.default.json").read_text(encoding="utf-8"))["tools"]}
        for p in tools.json.loads((here / "projects.default.json").read_text(encoding="utf-8")):
            if p.get("tool"):
                self.assertIn(p["tool"], ids, p["id"])



class NewApps(unittest.TestCase):
    def store(self):
        root = Path(tempfile.mkdtemp())
        return tools.ToolStore(root / "t.json", root / "none.json", Path(tools.__file__).parent / "tools.catalog.json")

    def test_a_well_known_app_gets_its_own_logo_and_everything_else_stays_lettered(self):
        s = self.store()
        s.apply({"action": "add", "name": "WhatsApp", "url": "https://web.whatsapp.com/", "group": "Daily", "pinned": True, "own": False})
        s.apply({"action": "add", "name": "My page", "url": "https://claude.ai/artifact/x", "group": "Mine", "own": True})
        # A logo is asked for at Google, which must never learn of an address inside a company.
        s.apply({"action": "add", "name": "Intranet", "url": "https://intranet.mycompany.example/", "group": "Daily", "own": False})
        wa, mine, inside = s.load()["tools"]
        self.assertEqual((wa["icon"], wa["pinned"], wa["own"]), ("web.whatsapp.com", True, False))
        self.assertNotIn("icon", mine)
        self.assertNotIn("icon", inside)
        # An entry saved by an older version keeps its place and is shown without the logo.
        data = s.load()
        data["tools"][2]["icon"] = "intranet.mycompany.example"
        s.save(data)
        self.assertNotIn("intranet.mycompany.example", str([t.get("icon") for t in s.shown()["tools"]]))
        self.assertEqual(len(s.shown()["tools"]), 3)


class PhotoPaths(unittest.TestCase):
    """The photo folder answers only to photo names, so no request reaches another file."""

    def test_only_photo_names_pass(self):
        import server
        for path in ("/photos/critical-01.webp", "/photos/calm-17.webp", "/photos/credits.json"):
            self.assertTrue(server.PHOTO.match(path), path)
        for path in ("/photos/../server.py", "/photos/critical-01.webp/../../tools.json", "/photos/x.webp",
                     "/photos/critical-1.webp", "/photos/CREDITS.md", "/photos/%2e%2e/server.py", "/photos/"):
            self.assertIsNone(server.PHOTO.match(path), path)


class OpenTool(unittest.TestCase):
    """The server opens a tool as an app window only from its own list, never an address a page sends."""

    def fake(self):
        root = Path(tempfile.mkdtemp())
        (root / "d.json").write_text('{"tools": [{"id": "gm", "name": "Gmail", "url": "https://mail.google.com/"},'
                                     ' {"id": "ob", "name": "Obsidian", "url": "obsidian://open"}]}', encoding="utf-8")
        app = type("FakeApp", (), {})()
        app.tools = tools.ToolStore(root / "t.json", root / "d.json")
        return app

    def test_only_listed_web_tools_open_with_the_listed_address(self):
        import server
        from unittest import mock
        app = self.fake()
        with mock.patch.object(server, "app_browser", return_value=Path("C:/chrome.exe")), mock.patch.object(server.subprocess, "Popen") as popen:
            self.assertTrue(server.App.open_tool(app, {"id": "gm", "x": 10, "y": 20, "w": 900, "h": 800, "url": "https://evil.example"}))
            args = popen.call_args[0][0]
            self.assertIn("--app=https://mail.google.com/", args)
            self.assertIn("--window-size=900,800", args)
            self.assertNotIn("evil", " ".join(args))
            for body in ({"id": "ob"}, {"id": "nope"}, {}):
                with self.assertRaises(ValueError):
                    server.App.open_tool(app, body)


if __name__ == "__main__":
    unittest.main()
