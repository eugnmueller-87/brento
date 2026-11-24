"""The owner's tool list. The only thing Brento ever writes, and it lives outside the vault."""
import hashlib
import json
import os
import re
import threading
from pathlib import Path
from urllib.parse import urlsplit

SCHEMES = {"https", "http", "obsidian"}
# A link holding a secret would sit in a plain file and in the browser history of every window it opens.
SECRET_IN_URL = re.compile(r"[?&#;](key|token|password|passwd|secret|auth|apikey|api_key)=", re.I)
MAX_TOOLS = 80
PAGE_ID = re.compile(r"^[a-z]{1,20}$")
# Home stays in the dock whatever else moves out, so the way back never disappears.
FIXED_PAGES = {"home"}
# Cards taken off Home by hand. The oldest drop out first.
MAX_REMOVED = 200


def card_key(card_id):
    """A card's id as a short hash, so the list of removed cards never holds a card's title."""
    return hashlib.sha1(str(card_id).encode("utf-8")).hexdigest()[:12]


class ToolError(ValueError):
    pass


def clean_url(url):
    url = str(url or "").strip()
    parts = urlsplit(url)
    if parts.scheme.lower() not in SCHEMES:
        raise ToolError("Use a link starting with https://, http:// or obsidian://.")
    if parts.scheme.lower() != "obsidian" and not parts.hostname:
        raise ToolError("That link has no address.")
    if parts.username or parts.password:
        raise ToolError("Leave the login out of the link. The window opens signed in as you.")
    if SECRET_IN_URL.search(url):
        raise ToolError("That link holds a key or password. Remove it first, this list is a plain file.")
    return url


class ToolStore:
    def __init__(self, path, defaults, catalog=None):
        self.path, self.defaults = Path(path), Path(defaults)
        self.lock = threading.Lock()
        try:
            listed = json.loads(Path(catalog).read_text(encoding="utf-8")) if catalog else []
        except (OSError, ValueError):
            listed = []
        self.known = {urlsplit(entry["url"]).hostname for entry in listed if str(entry.get("url", "")).startswith("https://")}

    def load(self):
        for source in (self.path, self.defaults):
            try:
                return json.loads(source.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
        return {"version": 1, "tools": []}

    def shown(self):
        """The list as a page gets it: a logo only for a well-known service, also for entries of an older version."""
        data = self.load()
        for tool in data.get("tools", []):
            if tool.get("icon") and tool["icon"] not in self.known:
                tool.pop("icon")
        return data

    def save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(temp), str(self.path))

    def apply(self, body):
        """Add, remove or pin one tool, dock one page, set the dock's order, or take one card off Home.
        Everything else stays as it is."""
        action = body.get("action")
        with self.lock:
            data = self.load()
            tools = data["tools"]
            if action == "add":
                name = str(body.get("name") or "").strip()[:40]
                url = clean_url(body.get("url"))
                if not name:
                    raise ToolError("Give the tool a name.")
                if len(tools) >= MAX_TOOLS:
                    raise ToolError("The list is full at %d tools." % MAX_TOOLS)
                if any(t["url"] == url for t in tools):
                    raise ToolError("That link is already on the list.")
                tid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "tool"
                tid += "-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:6]
                own = bool(body.get("own"))
                entry = {"id": tid, "name": name, "url": url, "group": str(body.get("group") or "Added").strip()[:30] or "Added",
                         "pinned": bool(body.get("pinned")), "own": own}
                # A well-known service shows its own logo, which the page gets from Google's icon service. Every other
                # address stays lettered, so nobody learns of it: an internal host, or one of ours.
                host = urlsplit(url).hostname
                if not own and host in self.known:
                    entry["icon"] = host
                tools.append(entry)
            elif action in ("remove", "pin"):
                tid = str(body.get("id") or "")
                match = next((t for t in tools if t["id"] == tid), None)
                if match is None:
                    raise ToolError("That tool is no longer on the list.")
                if action == "remove":
                    tools.remove(match)
                else:
                    match["pinned"] = bool(body.get("pinned"))
            elif action == "order":
                # The dock after a drag. Docked tools take the dock's slots in the new order, every other tool
                # keeps its place in the list.
                if "tools" in body:
                    ids = [str(i) for i in body.get("tools") or []]
                    slots = [i for i, t in enumerate(tools) if t.get("pinned")]
                    by_id = {t["id"]: t for t in tools}
                    if sorted(ids) != sorted(tools[i]["id"] for i in slots):
                        raise ToolError("The dock changed in another window. Try again.")
                    for slot, tid in zip(slots, ids):
                        tools[slot] = by_id[tid]
                if "pages" in body:
                    order = [str(p) for p in body.get("pages") or []]
                    if len(order) != len(set(order)) or not all(PAGE_ID.match(p) for p in order):
                        raise ToolError("Unknown page.")
                    data["pageOrder"] = order
            elif action == "page":
                pid = str(body.get("id") or "")
                if not PAGE_ID.match(pid):
                    raise ToolError("Unknown page.")
                hidden = [p for p in data.get("hiddenPages", []) if p != pid]
                if not body.get("docked"):
                    if pid in FIXED_PAGES:
                        raise ToolError("Home stays in the dock, so the way back never disappears.")
                    hidden.append(pid)
                data["hiddenPages"] = hidden
            elif action == "card":
                # Off Home until it is put back. A card whose title changes counts as a new card and shows again.
                cid = str(body.get("id") or "")
                if not cid:
                    raise ToolError("Unknown card.")
                key = card_key(cid)
                removed = [k for k in data.get("removedCards", []) if k != key]
                if body.get("removed"):
                    removed.append(key)
                data["removedCards"] = removed[-MAX_REMOVED:]
            else:
                raise ToolError("Unknown action.")
            self.save(data)
            return data
