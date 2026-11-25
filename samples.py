"""A few example notes, for someone who wants to look around before choosing a folder of their own.

They are written into Daytag's own folder when the owner asks for them, with dates around today. Nothing in them is real.
"""
from datetime import timedelta
from pathlib import Path

FOLDER = "sample-notes"
# {0} is today, {3} is in three days.
NOTES = {
    "Start here.md": """---
tags: [start]
---
# Start here

These notes are examples. Nothing in them is real, and they lie in Daytag's own folder.

- Every open checkbox with a date becomes a card on Home once it is due within a week.
- Notes that link to each other find each other: [[Offer for the bakery]], [[Weekend in Hamburg]], [[Flat]].
- Your own notes instead: **Brain**, then **Sources and setup**, step 2.
""",
    "Work/Offer for the bakery.md": """---
tags: [work, offer]
---
# Offer for the bakery

The bakery on the corner wants a new website with an order form.

- [x] Meet the owner
- [ ] Send the offer to the bakery ⏫ 📅 {0}
- [ ] Ask whether the photos can be used 📅 {6}

Texts: [[Website texts]]. The price is in the table.

| What | Days |
|---|---|
| Design | 3 |
| Order form | 2 |
| Texts | 1 |
""",
    "Work/Website texts.md": """---
tags: [work, writing]
---
# Website texts

Short sentences. Say what there is, when it is fresh, and how to order.

- [ ] Rewrite the front page [due:: {4}]
- [ ] Opening hours for the holidays

Belongs to [[Offer for the bakery]].
""",
    "Work/Team meeting.md": """---
tags: [work, meeting]
---
# Team meeting

- [ ] Prepare three points for the team meeting 🔼 📅 {1}

1. What went well
2. What is stuck
3. Who needs help with [[Website texts]]
""",
    "Home/Flat.md": """---
tags: [home]
---
# Flat

- [ ] Call the landlord about the heating 📅 {2}
- [ ] Measure the window for the shelf

Bills are in [[Bills]].
""",
    "Home/Bills.md": """---
tags: [home, money]
---
# Bills

- [ ] Pay the electricity bill ⏫ 📅 {3}

| Bill | When |
|---|---|
| Electricity | every three months |
| Internet | every month |
| Insurance | once a year |
""",
    "Trips/Weekend in Hamburg.md": """---
tags: [trip]
---
# Weekend in Hamburg

- [ ] Book the train to Hamburg 📅 {5}
- [ ] Find a room near the harbor

Take along: rain jacket, camera, the book from [[Reading list]].
""",
    "Ideas/Reading list.md": """---
tags: [ideas, reading]
---
# Reading list

- A book about sleep
- A novel for the train, see [[Weekend in Hamburg]]
- Something about bread, for [[Offer for the bakery]]
""",
    "Ideas/Balcony.md": """---
tags: [ideas, home]
---
# Balcony

Tomatoes need the sunny corner, herbs do not.

- [ ] Ask the neighbor for seedlings

Belongs to [[Flat]].
""",
}


def folder(home):
    return Path(home) / FOLDER


def write(home, today):
    """Writes them anew, so the dates fit, and touches nothing else. Returns the folder."""
    days = [(today + timedelta(days=n)).isoformat() for n in range(8)]
    for name, text in NOTES.items():
        target = folder(home) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text.format(*days), encoding="utf-8")
    return folder(home)


def remove(home):
    """Takes away what write() made. A note that someone else put there stays."""
    for name in NOTES:
        try:
            (folder(home) / name).unlink()
        except OSError:
            pass
    for path in sorted({folder(home) / name for name in NOTES}, key=lambda p: -len(p.parts)):
        for place in (path.parent, folder(home)):
            try:
                place.rmdir()
            except OSError:
                pass
