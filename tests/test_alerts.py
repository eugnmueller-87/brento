import sys
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import calendar_feed
import sources
from shape import build_state
import tools

sources.load_private(Path(__file__).resolve().parent / "stand-in-terms.txt")

TODAY = date(2026, 11, 4)

# The shape of the real calendar on 04.11.2026, as a private iCal link delivers it.
ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;TZID=Europe/Berlin:20261105T110000
SUMMARY:Northwind follow up
ATTENDEE;CN=a;PARTSTAT=ACCEPTED:mailto:a@example.com
ATTENDEE;CN=me;PARTSTAT=ACCEPTED:mailto:me@example.com
X-GOOGLE-CONFERENCE:https://meet.google.com/x
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Europe/Berlin:20261111T131500
SUMMARY:Zahnarzt
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Europe/Berlin:20261108T210000
RRULE:FREQ=WEEKLY
SUMMARY:Orion Weekly Maintenance
END:VEVENT
BEGIN:VEVENT
DTSTART:20261106T090000Z
SUMMARY:Abgesagter Termin
STATUS:CANCELLED
ATTENDEE:mailto:a@example.com
ATTENDEE:mailto:b@example.com
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261107
SUMMARY:Gespraech\\, wichtig mit Bewerbung
END:VEVENT
BEGIN:VEVENT
DTSTART:20261001T090000Z
SUMMARY:Vergangen
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Europe/Berlin:20261106T100000
SUMMARY:Steuer vorbereiten !
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Europe/Berlin:20261205T100000
SUMMARY:Interview weit weg
END:VEVENT
END:VCALENDAR
"""


class FakeFeed:
    def __init__(self, events, fetched=1793750000.0, error=""):
        self.events, self.when, self.error = events, fetched, error

    def connected(self):
        return True

    def snapshot(self, today, days=21):
        return self.events, self.when, self.error


class FakeBoard:
    number = 10

    def __init__(self, raw=None):
        self.raw = raw or []

    def snapshot(self, wait=False):
        return self.raw, 1793750000.0, ""


def vault_with(files):
    root = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


OPEN = """# Offene
> **Stand 03.11.2026.**

| Vorgang | Nächster Schritt | Frist | Wer ist dran | Akte |
|---|---|---|---|---|
| **Lindqvist** | Antworten | **Fr 06.11.** | Alex | [[Lindqvist]] |
| **Fjordwerk** | Abwarten | **Do 12.11.** | Fjordwerk | [[Fjordwerk]] |
| **Spaeter** | Machen | **Mo 30.11.** | Alex | [[Spaeter]] |
| **Verpasst** | Nachholen | **Mo 02.11.** | Alex | [[Verpasst]] |
"""


def state(files=None, cards=None, events=None):
    root = vault_with(dict({"Open matters.md": OPEN}, **(files or {})))
    return build_state(root, FakeBoard(cards), TODAY, (), FakeFeed(calendar_feed.parse_ics(ICS, TODAY) if events is None else events))


class Calendar(unittest.TestCase):
    def test_keeps_one_off_future_events_and_drops_the_rest(self):
        titles = [e["title"] for e in calendar_feed.parse_ics(ICS, TODAY)]
        self.assertIn("Northwind follow up", titles)
        self.assertIn("Zahnarzt", titles)
        for gone in ("Orion Weekly Maintenance", "Abgesagter Termin", "Vergangen", "Interview weit weg"):
            self.assertNotIn(gone, titles)

    def test_reads_time_people_and_all_day(self):
        events = {e["title"]: e for e in calendar_feed.parse_ics(ICS, TODAY)}
        meta = events["Northwind follow up"]
        self.assertEqual((meta["date"], meta["people"], meta["conference"]), ("2026-11-05", 2, True))
        self.assertEqual(events["Gespraech, wichtig mit Bewerbung"]["time"], "")

    def test_folded_lines_are_joined(self):
        text = "BEGIN:VEVENT\r\nDTSTART:20261105T100000Z\r\nSUMMARY:Lange\r\n  Zeile\r\nEND:VEVENT"
        self.assertEqual(calendar_feed.parse_ics(text, TODAY)[0]["title"], "Lange Zeile")

    def test_only_a_public_https_ics_link_is_accepted(self):
        good = "https://calendar.google.com/calendar/ical/x%40example.com/private-abc/basic.ics"
        self.assertEqual(calendar_feed.clean_url(good), good)
        for bad in ("http://calendar.google.com/x.ics", "https://calendar.google.com/x", "file:///c:/x.ics", "",
                    "https://127.0.0.1/x.ics", "https://192.168.1.20/x.ics", "https://u:p@example.com/x.ics"):
            with self.assertRaises(ValueError, msg=bad):
                calendar_feed.clean_url(bad)

    def test_the_link_stays_on_disk_and_out_of_errors_and_state(self):
        secret = "https://127.0.0.1:9/private-SECRET/basic.ics"
        path = Path(tempfile.mkdtemp()) / "sub" / "calendar-url"
        feed = calendar_feed.Feed(path)
        path.parent.mkdir(parents=True)
        path.write_text(secret, encoding="utf-8")
        feed.fetch()
        self.assertTrue(feed.connected())
        self.assertNotIn("SECRET", feed.error)
        self.assertEqual(feed.snapshot(TODAY)[0], [])
        root = vault_with({})
        self.assertNotIn("SECRET", str(build_state(root, FakeBoard(), TODAY, (), feed)))
        feed.disconnect()
        self.assertFalse(feed.connected())


class Gate(unittest.TestCase):
    """Home only shows what really needs preparing. The real calendar of 04.11.2026 is the test."""

    def titles(self, **kw):
        return [a["title"] for a in state(**kw)["alerts"]]

    def test_a_meeting_with_people_passes_and_routine_does_not(self):
        got = self.titles()
        self.assertIn("Northwind follow up", got)
        self.assertNotIn("Zahnarzt", got)
        self.assertNotIn("Orion Weekly Maintenance", got)

    def test_a_word_or_an_exclamation_mark_also_promotes_an_event(self):
        got = self.titles()
        self.assertIn("Gespraech, wichtig mit Bewerbung", got)
        self.assertIn("Steuer vorbereiten !", got)

    def test_my_own_deadline_inside_a_week_passes_others_and_later_ones_do_not(self):
        got = self.titles()
        self.assertIn("Lindqvist", got)
        self.assertNotIn("Fjordwerk", got)
        self.assertNotIn("Spaeter", got)

    def test_a_missed_deadline_of_mine_stays_until_someone_deals_with_it(self):
        self.assertIn("Verpasst", self.titles())

    def test_maintenance_stuff_never_gets_a_slide(self):
        files = {"Goals.md": "# G\n## Right now\n- [ ] Etwas\n## Next\n",
                 "outputs/liveness-latest.md": "# Lebenszeichen - 2026-11-04 04:00\n**1 lebt, 7 still, 8 ruht**\n",
                 "outputs/morning-brief-latest.md": "---\ncreated: 2026-11-04\n---\n## THE ONE THING TODAY\n\n**Etwas anderes tun.**\n"}
        cards = [{"title": "Termin 26.08", "status": "HIGH", "bereich": "Jobs", "createdAt": "2026-08-01T00:00:00Z"}]
        kinds = {a["id"] for a in state(files=files, cards=cards, events=[])["alerts"]}
        self.assertEqual(kinds, {"open-Lindqvist", "open-Verpasst"})

    def test_only_a_high_card_with_a_near_real_date_passes(self):
        cards = [{"title": "Workshop Di 10.11.", "status": "HIGH", "bereich": "x", "createdAt": "2026-10-01T00:00:00Z"},
                 {"title": "Workshop Mi 11.11.", "status": "MID", "bereich": "x", "createdAt": "2026-10-01T00:00:00Z"},
                 {"title": "Weit weg Mo 30.11.", "status": "HIGH", "bereich": "x", "createdAt": "2026-10-01T00:00:00Z"},
                 {"title": "Ohne Datum", "status": "HIGH", "bereich": "x"}]
        got = self.titles(cards=cards, events=[])
        self.assertIn("Workshop Di 10.11.", got)
        for gone in ("Workshop Mi 11.11.", "Weit weg Mo 30.11.", "Ohne Datum"):
            self.assertNotIn(gone, got)

    def test_a_card_and_an_event_for_the_same_thing_are_one_slide(self):
        cards = [{"title": "Northwind Call Do 05.11. vorbereiten", "status": "HIGH", "bereich": "x", "createdAt": "2026-10-01T00:00:00Z"}]
        got = self.titles(cards=cards)
        self.assertEqual(sum("Northwind" in t for t in got), 1)

    def test_soonest_comes_first_and_nothing_that_passed_is_dropped(self):
        alerts = state()["alerts"]
        self.assertEqual(len(alerts), 5)
        self.assertEqual(alerts[0]["title"], "Verpasst")
        self.assertEqual(alerts[1]["title"], "Northwind follow up")

    def test_a_private_event_never_reaches_the_screen(self):
        event = {"title": "Termin Geheimsache Akte 999", "date": "2026-11-05", "time": "10:00", "where": "", "people": 2, "conference": False}
        result = state(events=[event])
        self.assertNotIn("Akte 999", str(result))
        self.assertEqual(result["hidden"], 1)

    def test_an_event_opens_the_note_with_its_name_when_there_is_one(self):
        result = state(files={"Companies/Northwind.md": "x"})
        meta = next(a for a in result["alerts"] if a["title"] == "Northwind follow up")
        self.assertEqual(meta["note"], "Companies/Northwind.md")

    def test_events_join_the_week_and_the_source_reports_connected(self):
        result = state()
        self.assertIn("Northwind follow up", [d["name"] for d in result["deadlines"]])
        self.assertEqual(next(s for s in result["sources"] if s["id"] == "calendar")["state"], "fresh")
        self.assertTrue(result["calendarConnected"])

    def test_without_a_calendar_it_says_so_and_still_works(self):
        result = build_state(vault_with({"Open matters.md": OPEN}), FakeBoard(), TODAY)
        self.assertFalse(result["calendarConnected"])
        self.assertEqual(next(s for s in result["sources"] if s["id"] == "calendar")["state"], "unknown")
        self.assertIn("Lindqvist", [a["title"] for a in result["alerts"]])


def card(title, status="HIGH", area="Jobs", body="", cid=""):
    return {"id": cid, "title": title, "status": status, "bereich": area, "createdAt": "2026-10-01T00:00:00Z",
            "content": {"body": body}}


class Focus(unittest.TestCase):
    """Home: the gate first and uncut, then real to-dos up to ten. The real board of 04.11.2026 is the shape."""

    def focus(self, cards, **kw):
        return [f["title"] for f in state(cards=cards, events=kw.pop("events", []), **kw)["focus"]]

    def test_order_is_gate_then_my_matters_then_high_then_mid(self):
        cards = [card("Mid Sache", "MID"), card("High Sache")]
        got = self.focus(cards)
        self.assertEqual(got[:2], ["Verpasst", "Lindqvist"])
        self.assertEqual(got[2:], ["High Sache", "Mid Sache"])

    def test_alerts_stay_the_gate_so_the_pop_up_does_not_fire_ten_times(self):
        result = state(cards=[card("High Sache")], events=[])
        self.assertNotIn("High Sache", [a["title"] for a in result["alerts"]])
        self.assertIn("High Sache", [f["title"] for f in result["focus"]])

    def test_the_fill_stops_at_ten_and_high_goes_first(self):
        cards = [card("Mid %d" % i, "MID") for i in range(9)] + [card("High %d" % i) for i in range(9)]
        got = self.focus(cards)
        self.assertEqual(len(got), 10)
        self.assertEqual(got[2:], ["High %d" % i for i in range(8)])

    def test_the_gate_is_never_cut_even_past_ten(self):
        cards = [card("Workshop %d Di 10.11." % i) for i in range(12)]
        self.assertEqual(sum(t.startswith("Workshop") for t in self.focus(cards)), 12)

    def test_nothing_pads_the_deck(self):
        self.assertEqual(self.focus([]), ["Verpasst", "Lindqvist"])

    def test_goals_news_maintenance_and_low_stay_off(self):
        cards = [card("Q: Land the next role", "MID"), card("NEWS 03.11 Etwas", "MID", "News"), card("Hook reparieren", "MID", "Brain"),
                 card("Irgendwann", "LOW"), card("Q: Ein Ziel", "HIGH")]
        self.assertEqual(self.focus(cards), ["Verpasst", "Lindqvist"])

    def test_a_high_card_of_any_other_area_still_counts(self):
        self.assertIn("Hook reparieren", self.focus([card("Hook reparieren", "HIGH", "Brain")]))

    def test_job_hunt_goes_before_money_before_Clients_before_coding(self):
        cards = [card("Code", area="Code"), card("Kunde", area="Clients"), card("Steuer", area="Money"), card("Bewerben")]
        self.assertEqual(self.focus(cards)[2:], ["Bewerben", "Steuer", "Kunde", "Code"])

    def test_a_chain_shows_only_its_next_open_step(self):
        cards = [card("Distiller 2/5: Zwei"), card("Distiller 1/5: Eins", status="Done"), card("Distiller 3/5: Drei"), card("Distiller 4/5: Vier", "MID")]
        got = self.focus(cards)
        self.assertIn("Distiller 2/5: Zwei", got)
        for gone in ("Distiller 3/5: Drei", "Distiller 4/5: Vier", "Distiller 1/5: Eins"):
            self.assertNotIn(gone, got)

    def test_a_card_for_an_open_matter_is_not_a_second_slide(self):
        got = self.focus([card("Lindqvist AB-12-34: Rueckzahlung holen"), card("Fjordwerk: Rechnung", "MID")])
        self.assertEqual(sum("Lindqvist" in t for t in got), 1)
        self.assertEqual(sum("Fjordwerk" in t for t in got), 0)

    def test_a_card_for_a_meeting_on_the_deck_is_not_a_second_slide(self):
        event = {"title": "Northwind follow up", "date": "2026-11-05", "time": "11:00", "where": "", "people": 2, "conference": True}
        got = self.focus([card("Northwind: Deck fertig")], events=[event])
        self.assertEqual([t for t in got if "Northwind" in t], ["Northwind follow up"])

    def test_a_high_card_past_its_date_is_left_to_the_aging_job(self):
        self.assertNotIn("Termin Mo 02.11.", self.focus([card("Termin Mo 02.11.")]))

    def test_a_private_card_never_reaches_the_deck(self):
        result = state(cards=[card("Geheimsache Akte 999"), card("Harmlos", body="Geheimsache")], events=[])
        self.assertNotIn("Akte 999", str(result["focus"]))
        self.assertNotIn("Harmlos", str(result["focus"]))

    def test_a_card_says_what_is_left_and_opens_its_own_note_or_itself(self):
        files = {"Projects/Sample Project.md": "x"}
        cards = [card("Kopf", body="Stand 13.10. laeuft. OFFEN, damit Done geht: Einmal ins Mikro sprechen. Vault: Projects/Sample Project.md", cid="A"),
                 card("Ohne Note", cid="PVTI_b")]
        result = {f["title"]: f for f in state(files=files, cards=cards, events=[])["focus"]}
        self.assertEqual(result["Kopf"]["body"], "Einmal ins Mikro sprechen.")
        self.assertEqual((result["Kopf"]["note"], result["Kopf"]["route"]), ("Projects/Sample Project.md", None))
        self.assertEqual((result["Ohne Note"]["note"], result["Ohne Note"]["route"]), (None, "board/card:PVTI_b"))

    def test_links_in_a_card_body_do_not_reach_the_slide(self):
        body = "Keine Antwort. Faden: https://mail.google.com/x\n\n---\nFrueherer Kartentext"
        self.assertEqual(sources.card_text({"body": body}), "Keine Antwort.")

    def test_long_titles_split_where_the_title_pauses(self):
        self.assertEqual(sources.headline("Kurz"), ("Kurz", ""))
        self.assertEqual(sources.headline("Portfolio: SpendLens-Demo bereinigen (erfundene Reuters-Schlagzeilen, /api/zeus-Routen, Absturz)"),
                         ("Portfolio: SpendLens-Demo bereinigen", "erfundene Reuters-Schlagzeilen, /api/zeus-Routen, Absturz"))
        self.assertEqual(sources.headline("Steueragenten: Finanzamt-Erinnerung vom 12.10. an Lana, seitdem keine Antwort"),
                         ("Steueragenten: Finanzamt-Erinnerung vom 12.10. an Lana", "seitdem keine Antwort"))
        self.assertEqual(sources.headline("Notices: PR #22 (Mail-Drosselung 429) und #23 (Org-Name-Schwaerzung) seit 10.09. fertig, pruefen und mergen")[0], "Notices: PR #22")


class Agenda(unittest.TestCase):
    """The day strip and the day pages."""

    def on(self, result, day):
        return [a["title"] for a in result["agenda"] if a["date"] == day]

    def test_matters_events_and_dated_cards_land_on_their_day(self):
        cards = [card("Workshop Di 10.11. vorbereiten"), card("Spaeter im Lauf", "MID")]
        result = state(cards=cards)
        self.assertEqual(self.on(result, "2026-11-06"), ["Lindqvist", "Steuer vorbereiten !"])
        self.assertEqual(self.on(result, "2026-11-05"), ["Northwind follow up"])
        self.assertEqual(self.on(result, "2026-11-10"), ["Workshop Di 10.11. vorbereiten"])
        self.assertEqual(self.on(result, "2026-11-30"), ["Spaeter"])

    def test_the_past_stays_out_and_the_order_is_by_date(self):
        result = state()
        self.assertNotIn("Verpasst", [a["title"] for a in result["agenda"]])
        dates = [a["date"] for a in result["agenda"]]
        self.assertEqual(dates, sorted(dates))

    def test_it_reaches_three_months_but_today_keeps_its_short_list(self):
        event = {"title": "Weit weg", "date": "2027-01-20", "time": "", "where": "", "people": 0, "conference": False}
        result = state(events=[event])
        self.assertEqual(self.on(result, "2027-01-20"), ["Weit weg"])
        self.assertEqual(result["events"], [])
        self.assertEqual(result["agendaDays"], sources.AGENDA_DAYS)

    def test_the_feed_hands_over_as_far_as_it_is_asked(self):
        feed = calendar_feed.Feed(Path(tempfile.mkdtemp()) / "calendar-url")
        feed.text, feed.fetched = ICS, 1793750000.0
        self.assertNotIn("Interview weit weg", [e["title"] for e in feed.snapshot(TODAY)[0]])
        self.assertIn("Interview weit weg", [e["title"] for e in feed.snapshot(TODAY, sources.AGENDA_DAYS)[0]])

    def test_a_card_that_repeats_its_day_is_one_row_and_finished_cards_are_none(self):
        cards = [card("Northwind Call Do 05.11. vorbereiten"), card("Erledigt Fr 13.11.", status="Done")]
        result = state(cards=cards)
        self.assertEqual(self.on(result, "2026-11-05"), ["Northwind follow up"])
        self.assertEqual(self.on(result, "2026-11-13"), [])

    def test_an_appointment_in_the_tracker_shows_but_a_sent_date_does_not(self):
        files = {"Applications.md": "## Hot\n### [[Firma A]] · Rolle · Interview Mi 11.11.\n### [[Firma B]] · Rolle · ABGESCHICKT 12.11.\n"}
        result = state(files=files, events=[])
        self.assertEqual(self.on(result, "2026-11-11"), ["Firma A"])
        self.assertEqual(self.on(result, "2026-11-12"), ["Fjordwerk"])

    def test_private_rows_stay_off_the_days(self):
        event = {"title": "Termin Akte 999", "date": "2026-11-09", "time": "", "where": "", "people": 2, "conference": False}
        result = state(events=[event], cards=[card("Geheimsache Mo 09.11.")])
        self.assertEqual(self.on(result, "2026-11-09"), [])


class Refresh(unittest.TestCase):
    """The button has to read now and has to say when it could not."""

    def board(self, error=""):
        board = sources.Board("x", 1)
        board.calls = 0

        def fetch():
            board.calls += 1
            board.error = error
            board.busy = False
        board.fetch = fetch
        return board

    def test_it_reads_even_when_the_last_read_is_recent(self):
        board = self.board()
        board.raw, board.fetched = [], 9e12
        self.assertEqual(board.refresh(), "")
        self.assertEqual(board.calls, 1)

    def test_it_reports_a_failed_read(self):
        self.assertEqual(self.board("not logged in").refresh(), "not logged in")

    def test_it_waits_for_a_read_already_running_instead_of_starting_a_second(self):
        board = self.board()
        board.busy = True
        threading.Timer(0.2, lambda: setattr(board, "busy", False)).start()
        board.refresh()
        self.assertFalse(board.busy)
        self.assertEqual(board.calls, 0)

    def test_a_calendar_that_is_not_connected_is_not_an_error(self):
        self.assertEqual(calendar_feed.Feed(Path(tempfile.mkdtemp()) / "calendar-url").refresh(), "")



class RemovedByHand(unittest.TestCase):
    """A card I judged unimportant leaves Home and the alerts, and the Today page can put it back."""

    def build(self, removed, cards=None):
        root = vault_with({"Open matters.md": OPEN})
        return build_state(root, FakeBoard(cards), TODAY, (), FakeFeed([]), removed=removed)

    def test_a_removed_matter_leaves_home_and_the_alerts_and_is_offered_back(self):
        result = self.build({sources.card_key("open-Lindqvist")})
        self.assertNotIn("Lindqvist", [f["title"] for f in result["focus"]])
        self.assertNotIn("Lindqvist", [a["title"] for a in result["alerts"]])
        self.assertEqual([g["id"] for g in result["removedCards"]], ["open-Lindqvist"])

    def test_a_removed_board_card_makes_room_for_the_next_one(self):
        cards = [card("Angebot schreiben"), card("Rechnung pruefen")]
        result = self.build({sources.card_key("card-Angebot schreiben")}, cards)
        titles = [f["title"] for f in result["focus"]]
        self.assertNotIn("Angebot schreiben", titles)
        self.assertIn("Rechnung pruefen", titles)
        self.assertEqual(result["removedCards"], [{"id": "card-Angebot schreiben", "title": "Angebot schreiben"}])

    def test_nothing_removed_changes_nothing(self):
        cards = [card("Angebot schreiben")]
        self.assertEqual(self.build(set(), cards)["focus"], state(cards=cards, events=[])["focus"])
        self.assertEqual(self.build(set(), cards)["removedCards"], [])

    def test_the_file_holds_a_hash_never_the_title_and_put_back_undoes_it(self):
        root = Path(tempfile.mkdtemp())
        store = tools.ToolStore(root / "t.json", root / "none.json")
        store.apply({"action": "card", "id": "card-Angebot schreiben", "removed": True})
        self.assertNotIn("Angebot", store.path.read_text(encoding="utf-8"))
        self.assertEqual(store.load()["removedCards"], [sources.card_key("card-Angebot schreiben")])
        store.apply({"action": "card", "id": "card-Angebot schreiben", "removed": False})
        self.assertEqual(store.load()["removedCards"], [])
        with self.assertRaises(tools.ToolError):
            store.apply({"action": "card", "id": "", "removed": True})


# A Teams invite as Google's iCal link delivers it: the link sits in the invite text, folded over two lines.
CALLS = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART;TZID=Europe/Berlin:20261109T103000\r\nSUMMARY:Kennenlernen\r\n"
         "LOCATION:Microsoft Teams-Besprechung\r\nATTENDEE:mailto:a@example.com\r\nATTENDEE:mailto:me@example.com\r\n"
         "DESCRIPTION:Jetzt an der Besprechung teilnehmen<https://teams.microsoft.com/l/meetup-join/19%3ameeting_ab\r\n"
         " c%40thread.v2/0?context=%7b%22Tid%22%7d>\nBesprechungs-ID: 123\r\nEND:VEVENT\r\n"
         "BEGIN:VEVENT\r\nDTSTART;TZID=Europe/Berlin:20261110T090000\r\nSUMMARY:Sync\r\n"
         "X-GOOGLE-CONFERENCE:https://meet.google.com/abc-defg-hij\r\nEND:VEVENT\r\n"
         "BEGIN:VEVENT\r\nDTSTART;TZID=Europe/Berlin:20261111T131500\r\nSUMMARY:Friseur\r\nLOCATION:Hauptstrasse 1\r\nEND:VEVENT\r\n"
         "END:VCALENDAR\r\n")
TEAMS = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc%40thread.v2/0?context=%7b%22Tid%22%7d"


class JoinLinks(unittest.TestCase):
    def test_each_call_brings_its_own_link_and_a_plain_event_none(self):
        joins = {e["title"]: e["join"] for e in calendar_feed.parse_ics(CALLS, TODAY)}
        self.assertEqual(joins, {"Kennenlernen": TEAMS, "Sync": "https://meet.google.com/abc-defg-hij", "Friseur": ""})

    def test_the_link_reaches_the_home_card_and_the_day_page(self):
        result = state(events=calendar_feed.parse_ics(CALLS, TODAY))
        alert = next(a for a in result["alerts"] if a["title"] == "Kennenlernen")
        self.assertEqual(alert["join"], TEAMS)
        row = next(r for r in result["agenda"] if r["title"] == "Kennenlernen")
        self.assertEqual(row["join"], TEAMS)

    def test_a_link_to_anything_else_is_not_a_call(self):
        text = CALLS.replace("teams.microsoft.com/l/meetup-join", "example.com/l/meetup-join")
        joins = {e["title"]: e["join"] for e in calendar_feed.parse_ics(text, TODAY)}
        self.assertEqual(joins["Kennenlernen"], "")


class Levels(unittest.TestCase):
    """Each Home card carries how hot it is, from its date: red, orange, yellow, blue, green."""

    def test_days_map_to_the_five_levels(self):
        got = [sources.level_of(d) for d in (-3, 0, 1, 2, 3, 5, 7, 10, 14, 30)]
        self.assertEqual(got, ["critical", "critical", "critical", "high", "high", "medium", "medium", "low", "low", "calm"])

    def test_every_home_card_has_a_level_and_high_is_never_cooler_than_orange(self):
        result = state(cards=[card("High ohne Datum"), card("Mid Sache", "MID")], events=[])
        levels = {f["title"]: f["level"] for f in result["focus"]}
        self.assertEqual(levels["Verpasst"], "critical")
        self.assertEqual(levels["Lindqvist"], "high")
        self.assertEqual(levels["High ohne Datum"], "high")
        self.assertEqual(levels["Mid Sache"], "low")
        self.assertTrue(all(f.get("level") in sources.LEVEL_ORDER for f in result["focus"]))


if __name__ == "__main__":
    unittest.main()
