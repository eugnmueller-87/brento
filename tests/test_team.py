"""A team on one board: each person's Home shows their own cards, and the team file holds nothing personal."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import settings
import sources

sources.load_private(Path(__file__).resolve().parent / "stand-in-terms.txt")
TODAY = date(2026, 11, 23)


class Board:
    number = 3

    def __init__(self, cards):
        self.cards = cards

    def snapshot(self, wait=False):
        return self.cards, 1795400000.0, ""


def card(title, who=(), status="HIGH", due="2026-11-25"):
    return {"id": title, "title": title, "status": status, "bereich": "Work", "dueField": due, "assignees": list(who)}


class Mine(unittest.TestCase):
    def setUp(self):
        self.keep = sources.ME_LOGIN

    def tearDown(self):
        sources.ME_LOGIN = self.keep

    def state(self, cards):
        root = Path(tempfile.mkdtemp())
        profile = settings.normalize({"vault": str(root), "sources": {"board": {"on": True}}})
        return sources.build_state(root, Board(cards), TODAY, profile=profile)

    def test_a_teammates_card_stays_off_my_home_but_on_the_board(self):
        sources.set_login("alex-dev")
        state = self.state([card("Mine", ["alex-dev"]), card("Nobody's"), card("Sam's", ["sam-ops"])])
        self.assertEqual(sorted(a["title"] for a in state["alerts"]), ["Mine", "Nobody's"])
        self.assertEqual(sorted(c["title"] for c in state["board"]["items"]), ["Mine", "Nobody's", "Sam's"])
        sam = next(c for c in state["board"]["items"] if c["title"] == "Sam's")
        self.assertEqual((sam["mine"], sam["assignees"]), (False, ["sam-ops"]))

    def test_without_a_login_everything_is_mine(self):
        sources.set_login("")
        state = self.state([card("Sam's", ["sam-ops"])])
        self.assertEqual([a["title"] for a in state["alerts"]], ["Sam's"])

    def test_a_teammates_undated_card_is_not_my_loose_end(self):
        sources.set_login("alex-dev")
        state = self.state([card("Sam's", ["sam-ops"], due=None), card("Mine", ["alex-dev"], due=None)])
        self.assertEqual([f["title"] for f in state["schedule"]["items"]], ["Mine"])

    def test_the_query_asks_for_assignees(self):
        self.assertEqual(sources.board_query().count("assignees(first:10)"), 3)


class TeamFile(unittest.TestCase):
    def test_round_trip_and_nothing_personal(self):
        folder = Path(tempfile.mkdtemp())
        saved = settings.save_team(folder, {"team": "Acme", "board": {"owner": "acme", "ownerType": "org", "number": 7,
                                                                       "statusField": "Lane", "me": "alex-dev"},
                                            "tools": ["outlook", "teams", "../x"], "calendar": "outlook",
                                            "slack": {"digest": "07:30"}})
        self.assertNotIn("me", saved["board"])
        self.assertEqual(saved["tools"], ["outlook", "teams"])
        loaded = settings.load_team(folder)
        self.assertEqual((loaded["team"], loaded["board"]["owner"], loaded["board"]["statusField"], loaded["slack"]["digest"]),
                         ("Acme", "acme", "Lane", "07:30"))
        text = (folder / "team.json").read_text(encoding="utf-8")
        self.assertNotIn("vault", text)
        self.assertNotIn("hooks.slack.com", text)

    def test_unknown_keys_are_refused_so_nothing_slips_in(self):
        for bad in ({"vault": "C:/x"}, {"webhook": "https://hooks.slack.com/services/a/b/c"}, {"team": "<b>"}):
            with self.assertRaises(ValueError, msg=bad):
                settings.clean_team(bad)

    def test_no_team_file_means_none(self):
        self.assertIsNone(settings.load_team(Path(tempfile.mkdtemp())))

    def test_a_broken_team_file_stops_the_start_with_a_reason(self):
        folder = Path(tempfile.mkdtemp())
        (folder / "team.json").write_text(json.dumps({"secret": 1}), encoding="utf-8")
        with self.assertRaises(SystemExit):
            settings.load_team(folder)


if __name__ == "__main__":
    unittest.main()
