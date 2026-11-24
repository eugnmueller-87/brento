"""The wizard's guesses and Slack's timing: what goes out, when, and what never does."""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import calendar_feed
import settings
import slack_notify
import wizard

CFG = {"digest": "08:00", "alerts": True, "remind": 10, "sources": ["calendar", "board", "tasks"]}
SOURCES = [{"id": "calendar", "label": "Calendar"}, {"id": "board", "label": "Board"}, {"id": "open-items", "label": "Open matters"}]


def alert(cid, title, source="Board", tag="due Tue 24.11.", join=""):
    return {"id": cid, "title": title, "source": source, "tag": tag, "why": "You marked this HIGH.", "join": join}


def state(alerts=(), events=(), schedule=None):
    return {"sources": SOURCES, "alerts": list(alerts), "events": list(events), "schedule": schedule or {"counts": {}}}


class SlackPlan(unittest.TestCase):
    def test_first_run_only_learns_then_new_alerts_go_out_once(self):
        now = datetime(2026, 11, 23, 14, 0)
        texts, memory = slack_notify.plan(state([alert("a", "Old card")]), CFG, {}, now)
        self.assertEqual(texts, [])
        texts, memory = slack_notify.plan(state([alert("a", "Old card"), alert("b", "Send <offer> & invoice")]), CFG, memory, now)
        self.assertEqual(len(texts), 1)
        self.assertIn("Send &lt;offer&gt; &amp; invoice", texts[0])
        self.assertNotIn("Old card", texts[0])
        texts, memory = slack_notify.plan(state([alert("a", "Old card"), alert("b", "x")]), CFG, memory, now)
        self.assertEqual(texts, [])

    def test_open_matters_stay_home_unless_chosen(self):
        now = datetime(2026, 11, 23, 14, 0)
        _, memory = slack_notify.plan(state(), CFG, {}, now)
        texts, _ = slack_notify.plan(state([alert("m", "Private matter", source="Open matters")]), CFG, memory, now)
        self.assertEqual(texts, [])
        texts, _ = slack_notify.plan(state([alert("m", "Private matter", source="Open matters")]),
                                     dict(CFG, sources=["open-items"]), memory, now)
        self.assertEqual(len(texts), 1)

    def test_morning_summary_once_in_its_window(self):
        early = slack_notify.plan(state([alert("a", "Card")]), CFG, {"seeded": True, "seen": []}, datetime(2026, 11, 23, 7, 59))
        self.assertFalse(any(t.startswith("Good morning") for t in early[0]))
        texts, memory = slack_notify.plan(state([alert("a", "Card")], schedule={"counts": {"prep": 1, "undated": 2}}), CFG,
                                          {"seeded": True, "seen": ["x"]}, datetime(2026, 11, 23, 8, 5), "Alex")
        summary = next(t for t in texts if t.startswith("Good morning"))
        self.assertIn("Good morning, Alex.", summary)
        self.assertIn("1 meeting without prep, 2 high cards without a date", summary.lower())
        again, _ = slack_notify.plan(state(), CFG, memory, datetime(2026, 11, 23, 9, 0))
        self.assertFalse(any(t.startswith("Good morning") for t in again))
        # A computer switched on in the afternoon does not send the morning's summary.
        late, memory = slack_notify.plan(state(), CFG, {"seeded": True}, datetime(2026, 11, 24, 15, 0))
        self.assertEqual(late, [])
        self.assertEqual(memory["digest"], "2026-11-24")

    def test_reminder_before_a_meeting_with_people_and_its_join_link(self):
        meeting = {"date": "2026-11-23", "time": "11:00", "title": "Pitch", "people": 3, "conference": True,
                   "join": "https://teams.microsoft.com/l/meetup-join/abc"}
        solo = {"date": "2026-11-23", "time": "11:00", "title": "Dentist", "people": 0, "conference": False, "join": ""}
        texts, memory = slack_notify.plan(state(events=[meeting, solo]), CFG, {"seeded": True, "digest": "2026-11-23"}, datetime(2026, 11, 23, 10, 52))
        self.assertEqual(len(texts), 1)
        self.assertIn("In 8 min:", texts[0])
        self.assertIn("<https://teams.microsoft.com/l/meetup-join/abc|Join call>", texts[0])
        again, _ = slack_notify.plan(state(events=[meeting]), CFG, memory, datetime(2026, 11, 23, 10, 55))
        self.assertEqual(again, [])
        too_early, _ = slack_notify.plan(state(events=[meeting]), CFG, {"seeded": True, "digest": "2026-11-23"}, datetime(2026, 11, 23, 10, 30))
        self.assertEqual(too_early, [])

    def test_only_a_real_webhook_link_is_kept_and_never_shown(self):
        good = "https://hooks.slack.com/services/T0ABCDEF/B0ABCDEF/abcdefABCDEF123456"
        self.assertEqual(slack_notify.clean_hook(good), good)
        for bad in ("http://hooks.slack.com/services/T/B/x", "https://hooks.slack.com.evil.example/services/T/B/x",
                    "https://example.com/hook", "", "https://hooks.slack.com/services/T/B"):
            with self.assertRaises(ValueError, msg=bad):
                slack_notify.clean_hook(bad)
        folder = Path(tempfile.mkdtemp())
        s = slack_notify.Slack(folder)
        s.connect(good)
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down " + good)):
            error = s.send("hello")
        self.assertNotIn("hooks.slack.com", error)
        s.disconnect()
        self.assertFalse(s.connected())

    def test_the_create_link_carries_only_documented_keys(self):
        self.assertTrue(slack_notify.CREATE_URL.startswith("https://api.slack.com/apps?new_app=1&manifest_json="))
        self.assertEqual(set(slack_notify.MANIFEST), {"display_information", "settings"})


class Fields(unittest.TestCase):
    def test_an_existing_board_maps_by_name_and_type(self):
        probe = {"fields": [{"name": "Status", "type": "SINGLE_SELECT", "options": ["HIGH", "MID", "LOW", "Done"]},
                            {"name": "Bereich", "type": "SINGLE_SELECT", "options": ["Jobs"]},
                            {"name": "Erledigt am", "type": "DATE", "options": []},
                            {"name": "Title", "type": "TITLE", "options": []}]}
        self.assertEqual(wizard.auto_fields(probe), {"statusField": "Status", "areaField": "Bereich", "dueField": "",
                                                      "doneField": "Erledigt am", "lanesFound": True})

    def test_a_board_without_lanes_says_so(self):
        probe = {"fields": [{"name": "Status", "type": "SINGLE_SELECT", "options": ["Todo", "In Progress", "Done"]},
                            {"name": "Due date", "type": "DATE", "options": []}]}
        found = wizard.auto_fields(probe)
        self.assertFalse(found["lanesFound"])
        self.assertEqual((found["statusField"], found["dueField"]), ("Status", "Due date"))

    def test_brentos_own_lane_field_wins_over_a_plain_status(self):
        probe = {"fields": [{"name": "Status", "type": "SINGLE_SELECT", "options": ["Todo", "Done"]},
                            {"name": "Lane", "type": "SINGLE_SELECT", "options": ["HIGH", "MID", "LOW", "Done"]},
                            {"name": "Area", "type": "SINGLE_SELECT", "options": ["Work"]}]}
        found = wizard.auto_fields(probe)
        self.assertEqual((found["statusField"], found["areaField"]), ("Lane", "Area"))

    def test_only_fixed_programs_can_be_opened(self):
        with self.assertRaises(ValueError):
            wizard.start_action("rm -rf /")
        for action, args in wizard.ACTIONS.items():
            # The download is Brento's own code; every other action is one of the two known programs.
            self.assertTrue(args[0] in ("{gh}", "{claude}") if args else action == "gh-install", action)


class Links(unittest.TestCase):
    def test_apple_and_outlook_links_and_webcal(self):
        self.assertEqual(calendar_feed.clean_url("webcal://p52-caldav.icloud.com/published/2/abc"),
                         "https://p52-caldav.icloud.com/published/2/abc")
        self.assertTrue(calendar_feed.clean_url("https://outlook.office365.com/owa/calendar/x/y/calendar.html"))
        with self.assertRaises(ValueError):
            calendar_feed.clean_url("https://evil-icloud.com/x")

    def test_slack_settings_have_safe_defaults(self):
        self.assertEqual(settings.clean_slack(None), {"digest": "08:00", "alerts": True, "remind": 10,
                                                      "sources": ["calendar", "board", "tasks"]})
        self.assertEqual(settings.clean_slack({"remind": 999, "sources": ["calendar", "everything"]})["remind"], 120)
        self.assertEqual(settings.clean_slack({"sources": ["calendar", "everything"]})["sources"], ["calendar"])
        with self.assertRaises(ValueError):
            settings.clean_slack({"digest": "8 o'clock"})


if __name__ == "__main__":
    unittest.main()
