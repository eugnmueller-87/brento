"""The vault the older tests were written against: fixed-shape notes, every source on but tasks.

Since the setup exists, those paths live in a settings file instead of the code. These tests keep proving
the same behaviour, so they hand build_state the same paths a settings file would.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sources

PROFILE = {"name": "Alex", "tasks": {"home": "all"},
           "board": {"homeAreas": {"Jobs": "pipeline", "Money": "goals", "Clients": "brief", "Code": "board"}},
           "sources": {
    "library": {"on": True}, "tasks": {"on": False}, "calendar": {"on": True}, "board": {"on": True}, "ask": {"on": True},
    "openItems": {"on": True, "path": "Open matters.md"},
    "pipeline": {"on": True, "path": "Applications.md"},
    "goals": {"on": True, "path": "Goals.md"},
    "brief": {"on": True, "path": "outputs/morning-brief-latest.md"},
    "liveness": {"on": True, "path": "outputs/liveness-latest.md"}}}

sources.set_owner(PROFILE["name"])


def build_state(*args, **kwargs):
    kwargs.setdefault("profile", PROFILE)
    return sources.build_state(*args, **kwargs)
