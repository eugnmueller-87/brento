"""The vault as a library: an index of its notes and a Markdown renderer. Nothing here writes.

The vault stays the back end. This reads it and turns a note into safe HTML, so nobody has to
leave the app to read one. All text is escaped first and every link is checked, because a note
can hold anything that was ever pasted into it.
"""
import html
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

import settings
import sources

# Original assets, private material and tool folders stay out. Only notes people wrote or asked for.
HIDDEN = {"node_modules", "_private", "__pycache__"}
# These are ordinary names elsewhere. They stay out only for settings from before the choice, which always left folders out.
HIDDEN_BEFORE = {"raw", "memory", "_archive", "_archive_pending", "Screenshots", "Excalidraw"}
SECTIONS = [("MOCs", "Topics"), ("Notes", "Notes"), ("Projects", "Projects"), ("Companies", "Companies"),
            ("People", "People"), ("Calls", "Calls"), ("Decisions", "Decisions"), ("Chess Moves", "Chess Moves"),
            ("00 Inbox", "Inbox"), ("Skills", "Skills"), ("Reviews", "Reviews"), ("Milestones", "Milestones"),
            ("Journals", "Journals"), ("wiki", "Knowledge"), ("docs", "Docs"), ("reports", "Reports"),
            ("outputs", "Generated")]
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp"}
# Pages generated into the vault, such as the live cards for an interview. Served as they are, never edited.
PAGE_TYPES = {".html"}
WIKILINK = re.compile(r"(!?)\[\[([^\]\n]+?)\]\]")
BRIEF_PATH = "outputs/morning-brief-latest.md"


def note_href(path):
    return "#library/n/" + "/".join(quote(part, safe="") for part in path.split("/"))


def split_frontmatter(text):
    """Frontmatter as simple key/value pairs. Lists come back as lists. The body is the rest."""
    text = text.lstrip("﻿")
    m = re.match(r"---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.S)
    if not m:
        return {}, text
    props, key = {}, None
    for line in m.group(1).splitlines():
        item = re.match(r"\s+-\s+(.*)$", line)
        if item and key:
            if not isinstance(props.get(key), list):
                props[key] = []
            props[key].append(item.group(1).strip().strip("\"'"))
            continue
        pair = re.match(r"([\w .-]+):\s*(.*)$", line)
        if not pair:
            continue
        key, value = pair.group(1).strip(), pair.group(2).strip()
        if value.startswith("[") and value.endswith("]"):
            props[key] = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
        else:
            props[key] = value.strip("\"'")
    return props, text[m.end():]


def drop_private_lines(body):
    """A note can be fine while one line in it is not. That line goes, and the reader is told."""
    kept, hidden = [], 0
    for line in body.split("\n"):
        if sources.PRIVATE.search(line):
            hidden += 1
        else:
            kept.append(line)
    return "\n".join(kept), hidden


class Renderer:
    def __init__(self, find_note, find_asset, seal=None):
        self.find_note, self.find_asset, self.seal = find_note, find_asset, seal

    def asset_src(self, asset):
        """A picture's address. With a seal it loads on the computer, where nothing else goes along with it."""
        return "/api/library/asset?path=" + quote(asset, safe="") + ("&amp;s=" + self.seal(asset) if self.seal else "")

    # Inline ---------------------------------------------------------------------------------------

    def _wikilink(self, m, keep):
        embed, inner = m.group(1), m.group(2).replace("\x00", "|")
        target, _, alias = inner.partition("|")
        target = target.split("#")[0].strip()
        label = alias.strip() or inner.split("|")[0].split("#")[0].split("/")[-1].strip() or target
        if embed:
            asset = self.find_asset(target)
            if asset:
                return keep('<img class="note-img" loading="lazy" alt="%s" src="%s">'
                            % (html.escape(label, quote=True), self.asset_src(asset)))
            path = self.find_note(target)
            if not path:
                return keep('<span class="link-missing">%s</span>' % html.escape(label))
            return keep('<a class="wikilink" href="%s">%s</a>' % (note_href(path), html.escape(label)))
        path = self.find_note(target)
        if path:
            return keep('<a class="wikilink" href="%s">%s</a>' % (note_href(path), html.escape(label)))
        return keep('<span class="link-missing" title="No note with this name">%s</span>' % html.escape(label))

    def _md_link(self, m, keep):
        text, url = m.group(2), m.group(3).strip().split(' "')[0].strip("<> ")
        scheme = urlsplit(url).scheme.lower()
        if m.group(1):
            asset = self.find_asset(url) if not scheme else None
            if asset:
                return keep('<img class="note-img" loading="lazy" alt="%s" src="%s">'
                            % (html.escape(text, quote=True), self.asset_src(asset)))
            return keep(html.escape(text))
        if scheme in ("http", "https", "mailto"):
            return keep('<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
                        % (html.escape(url, quote=True), self.inline(text)))
        if not scheme and url.lower().endswith(".md"):
            path = self.find_note(url.replace("%20", " "))
            if path:
                return keep('<a class="wikilink" href="%s">%s</a>' % (note_href(path), self.inline(text)))
        return keep(self.inline(text))

    def inline(self, text):
        kept = []

        def keep(fragment):
            kept.append(fragment)
            return "\x01%d\x01" % (len(kept) - 1)

        text = re.sub(r"%%.*?%%", "", text)
        text = re.sub(r"(`+)(.+?)\1", lambda m: keep("<code>%s</code>" % html.escape(m.group(2).strip())), text)
        text = WIKILINK.sub(lambda m: self._wikilink(m, keep), text)
        text = re.sub(r"(!?)\[([^\]\n]*)\]\(([^)\n]+)\)", lambda m: self._md_link(m, keep), text)
        text = re.sub(r"https?://[^\s<>\"')\]]+", lambda m: keep(
            '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
            % (html.escape(m.group(0), quote=True), html.escape(m.group(0)))), text)
        text = html.escape(text, quote=False)
        text = re.sub(r"&lt;br\s*/?&gt;", "<br>", text)
        text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"__(?=\S)(.+?)(?<=\S)__", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])", r"<em>\1</em>", text)
        text = re.sub(r"(?<![\w_])_(?=\S)([^_\n]+?)(?<=\S)_(?![\w_])", r"<em>\1</em>", text)
        text = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<del>\1</del>", text)
        text = re.sub(r"==(?=\S)(.+?)(?<=\S)==", r"<mark>\1</mark>", text)
        return re.sub(r"\x01(\d+)\x01", lambda m: kept[int(m.group(1))], text)

    # Blocks ---------------------------------------------------------------------------------------

    LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
    TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")

    def _cells(self, line):
        # A pipe inside a wikilink belongs to the link, not to the table.
        flat = re.sub(r"\[\[[^\]]*\]\]", lambda m: m.group(0).replace("|", "\x00"), line.strip())
        flat = flat[1:] if flat.startswith("|") else flat
        flat = flat[:-1] if flat.endswith("|") else flat
        return [c.strip() for c in flat.split("|")]

    def _table(self, lines, i):
        head = self._cells(lines[i])
        out = ['<div class="table-wrap"><table><thead><tr>']
        out += ["<th>%s</th>" % self.inline(c) for c in head]
        out.append("</tr></thead><tbody>")
        i += 2
        while i < len(lines) and "|" in lines[i] and lines[i].strip():
            cells = self._cells(lines[i])
            out.append("<tr>" + "".join("<td>%s</td>" % self.inline(c) for c in cells) + "</tr>")
            i += 1
        out.append("</tbody></table></div>")
        return "".join(out), i

    def _item_html(self, text):
        task = re.match(r"\[( |x|X)\]\s+(.*)$", text)
        if task:
            done = task.group(1) != " "
            return ('<span class="task%s" aria-label="%s"></span><span%s>%s</span>'
                    % (" done" if done else "", "done" if done else "open", ' class="task-done"' if done else "",
                       self.inline(task.group(2))))
        return self.inline(text)

    def _list(self, lines, i, indent):
        ordered = bool(re.match(r"\d", self.LIST_ITEM.match(lines[i]).group(2)))
        items = []
        while i < len(lines):
            line = lines[i]
            m = self.LIST_ITEM.match(line)
            if not line.strip():
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                nxt = self.LIST_ITEM.match(lines[j]) if j < len(lines) else None
                if nxt and len(nxt.group(1).expandtabs(4)) >= indent:
                    i = j
                    continue
                break
            if not m:
                if items and len(line) - len(line.lstrip()) > indent:
                    items[-1][0] += " " + line.strip()
                    i += 1
                    continue
                break
            width = len(m.group(1).expandtabs(4))
            if width < indent or (width == indent and bool(re.match(r"\d", m.group(2))) != ordered):
                break
            if width > indent and items:
                nested, i = self._list(lines, i, width)
                items[-1][1] += nested
                continue
            items.append([m.group(3), ""])
            i += 1
        tag = "ol" if ordered else "ul"
        body = "".join("<li>%s%s</li>" % (self._item_html(text), nested) for text, nested in items)
        return "<%s>%s</%s>" % (tag, body, tag), i

    def _quote(self, lines, i):
        inner = []
        while i < len(lines) and lines[i].lstrip().startswith(">"):
            inner.append(re.sub(r"^\s*>\s?", "", lines[i]))
            i += 1
        callout = re.match(r"\[!(\w+)\][+-]?\s*(.*)$", inner[0]) if inner else None
        if callout:
            kind = re.sub(r"[^a-z]", "", callout.group(1).lower()) or "note"
            title = callout.group(2) or callout.group(1).capitalize()
            return ('<div class="callout callout-%s"><div class="callout-title">%s</div>%s</div>'
                    % (kind, self.inline(title), self.blocks(inner[1:]))), i
        return "<blockquote>%s</blockquote>" % self.blocks(inner), i

    def blocks(self, lines):
        out, i = [], 0
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            fence = re.match(r"^\s*(```+|~~~+)\s*([\w+-]*)", line)
            if fence:
                code, i = [], i + 1
                while i < len(lines) and not lines[i].lstrip().startswith(fence.group(1)):
                    code.append(lines[i])
                    i += 1
                i += 1
                out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code)))
                continue
            heading = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
            if heading:
                level = len(heading.group(1))
                out.append("<h%d>%s</h%d>" % (level, self.inline(heading.group(2)), level))
                i += 1
                continue
            if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", line):
                out.append("<hr>")
                i += 1
                continue
            if line.lstrip().startswith(">"):
                fragment, i = self._quote(lines, i)
                out.append(fragment)
                continue
            if "|" in line and i + 1 < len(lines) and "-" in lines[i + 1] and self.TABLE_RULE.match(lines[i + 1]):
                fragment, i = self._table(lines, i)
                out.append(fragment)
                continue
            item = self.LIST_ITEM.match(line)
            if item:
                fragment, i = self._list(lines, i, len(item.group(1).expandtabs(4)))
                out.append(fragment)
                continue
            para = []
            while i < len(lines) and lines[i].strip():
                nxt = lines[i]
                if para and (re.match(r"^\s*(#{1,6}\s|```|~~~|>)", nxt) or self.LIST_ITEM.match(nxt)):
                    break
                para.append(nxt.strip())
                i += 1
            out.append("<p>%s</p>" % self.inline(" ".join(para)))
        return "".join(out)


class Library:
    """Keeps every note in memory and rereads only files whose time changed."""

    def __init__(self, vault, ttl=60, seal=None):
        self.vault, self.ttl, self.seal = Path(vault), ttl, seal
        self.notes, self.assets, self.pages = {}, {}, set()
        self.by_title, self.by_path, self.backlinks = {}, {}, {}
        self.stamp = 0.0
        self.lock = threading.Lock()
        # Notes that lie only in a cloud are fetched in the background. When one last failed, and whether that is running.
        self.failed, self.fetching = {}, False
        # Notes that macOS 13 put into iCloud, so that only a stub is here.
        self.stubs = 0

    def missing(self):
        """How many notes are not on this computer yet, so that their text is not known."""
        return self.stubs + sum(1 for note in self.notes.values() if note["away"])

    def file(self, rel):
        return Path(sources.whole(str(self.vault / rel)))

    def _walk(self):
        """(file, its path among the notes, its name). The file's path is one that Windows does not cut off."""
        before = set(settings.OLD_SKIP) <= sources.EXTRA_SKIP
        root = sources.whole(str(self.vault))
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in HIDDEN and not sources.PRIVATE.search(d)
                       and not (before and d in HIDDEN_BEFORE)]
            base = folder[len(root):].replace(os.sep, "/").strip("/")
            for name in files:
                if sources.PRIVATE.search(name):
                    continue
                yield Path(folder) / name, base + "/" + name if base else name, name

    def refresh(self):
        with self.lock:
            if self.notes and time.time() - self.stamp < self.ttl:
                return
            notes, assets, pages, stubs = {}, {}, set(), 0
            for full, rel, name in self._walk():
                suffix = full.suffix.lower()
                stubs += 1 if sources.ICLOUD_STUB.match(name) else 0
                if suffix in IMAGE_TYPES:
                    assets.setdefault(name.lower(), rel)
                    continue
                if suffix in PAGE_TYPES:
                    pages.add(rel)
                    continue
                if suffix != ".md":
                    continue
                old = self.notes.get(rel)
                try:
                    stat = full.stat()
                except OSError:
                    continue
                mtime, away = stat.st_mtime, sources.elsewhere(stat)
                if old and old["mtime"] == mtime and (away or not old["away"]):
                    notes[rel] = old
                    continue
                try:
                    # A note that lies only in a cloud is listed by its name, and fetched when it is opened.
                    raw = "" if away else full.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    if old:
                        notes[rel] = old
                    continue
                notes[rel] = dict(self._load(rel, raw, mtime), away=away)
            by_title, by_path = {}, {}
            for rel in sorted(notes, key=lambda r: (r.count("/"), len(r))):
                by_path[rel[:-3].lower()] = rel
                by_title.setdefault(rel.rsplit("/", 1)[-1][:-3].lower(), []).append(rel)
            self.notes, self.assets, self.by_title, self.by_path = notes, assets, by_title, by_path
            self.pages, self.stubs = pages, stubs
            backlinks = {}
            for rel, note in notes.items():
                for target in note["links"]:
                    path = self.find_note(target, rel)
                    if path and path != rel:
                        backlinks.setdefault(path, set()).add(rel)
            self.backlinks = backlinks
            self.stamp = time.time()
            away = [rel for rel, note in notes.items() if note["away"]]
            if away and not self.fetching:
                self.fetching = True
                threading.Thread(target=self._fetch, args=(away,), daemon=True).start()

    def _fetch(self, away):
        sources.cloud_files(True)
        try:
            self._fetch_some(away)
        finally:
            self.fetching = False

    def _fetch_some(self, away):
        ends = time.monotonic() + sources.FETCH_SECONDS
        for rel in away:
            if time.monotonic() > ends:
                break
            if time.time() - self.failed.get(rel, 0.0) < sources.RETRY_AFTER:
                continue
            try:
                raw = self.file(rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                self.failed[rel] = time.time()
                continue
            with self.lock:
                if rel in self.notes:
                    self.notes[rel] = dict(self._load(rel, raw, self.notes[rel]["mtime"]), away=False)

    def _load(self, rel, raw, mtime):
        props, body = split_frontmatter(raw)
        body, hidden = drop_private_lines(body)
        tags = props.get("tags") or []
        tags = tags if isinstance(tags, list) else [tags]
        first = re.match(r"\s*#\s+(.+?)\s*\n", body + "\n")
        title = first.group(1) if first else rel.rsplit("/", 1)[-1][:-3]
        links = [m.group(2).split("|")[0].split("#")[0].strip() for m in WIKILINK.finditer(body) if not m.group(1)]
        return {"path": rel, "title": re.sub(r"[*_`]", "", title)[:160], "props": props, "body": body, "hidden": hidden,
                "tags": [str(t) for t in tags], "type": str(props.get("type") or ""), "mtime": mtime,
                "links": links, "lower": body.lower()}

    def find_note(self, target, near=""):
        target = (target or "").strip().replace("\\", "/")
        target = target[:-3] if target.lower().endswith(".md") else target
        if not target:
            return None
        hit = self.by_path.get(target.lower())
        if hit:
            return hit
        options = self.by_title.get(target.rsplit("/", 1)[-1].lower())
        if not options:
            return None
        # Same name in two folders: the one closest to the linking note wins, as in Obsidian.
        top = near.split("/", 1)[0]
        return next((o for o in options if near and o.split("/", 1)[0] == top), options[0])

    def find_asset(self, target):
        return self.assets.get((target or "").strip().replace("\\", "/").rsplit("/", 1)[-1].lower())

    def overview(self):
        self.refresh()
        counts = {}
        for rel in self.notes:
            head = rel.split("/", 1)[0] if "/" in rel else ""
            counts[head] = counts.get(head, 0) + 1
        known = dict(SECTIONS)
        sections = [{"folder": f, "label": label, "count": counts[f]} for f, label in SECTIONS if counts.get(f)]
        sections += [{"folder": f, "label": f, "count": n} for f, n in sorted(counts.items()) if f and f not in known]
        tags = {}
        entries = []
        for note in self.notes.values():
            entries.append({"path": note["path"], "title": note["title"], "type": note["type"], "tags": note["tags"],
                            "mtime": int(note["mtime"])})
            if not note["path"].startswith(("outputs/", "wiki/", "reports/")):
                for tag in note["tags"]:
                    tags[tag] = tags.get(tag, 0) + 1
        entries.sort(key=lambda e: e["title"].lower())
        return {"sections": sections, "rootCount": counts.get("", 0), "notes": entries, "problem": sources.folder_problem(self.vault),
                "away": self.missing(),
                "tags": sorted(tags.items(), key=lambda kv: -kv[1])[:40]}

    def note(self, path):
        self.refresh()
        note = self.notes.get(path)
        if note is None:
            return None
        if note["away"]:
            sources.cloud_files(True)
            try:
                raw = self.file(path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                raw = "This note is not on this computer, and its cloud does not deliver it at the moment."
            else:
                self.notes[path] = dict(self._load(path, raw, note["mtime"]), away=False)
            note = dict(self._load(path, raw, note["mtime"]), away=False)
        body, stamp = note["body"], note["mtime"]
        props, hidden = note["props"], note["hidden"]
        if path == BRIEF_PATH:
            # The brief job pushes from elsewhere, so the copy on this disk can be behind the page's card.
            newest = sources.newest_brief(self.vault)[0]
            if newest:
                props, body = split_frontmatter(newest)
                body, hidden = drop_private_lines(body)
        first = re.match(r"\s*#\s+.+?\s*(?:\n|$)", body)
        renderer = Renderer(lambda t: self.find_note(t, path), self.find_asset, self.seal)
        text = body[first.end():] if first else body
        links = sorted(self.backlinks.get(path, ()), key=lambda r: self.notes[r]["title"].lower())
        return {"path": path, "title": note["title"], "html": renderer.blocks(text.split("\n")), "props": props,
                "hiddenLines": hidden, "mtime": int(stamp),
                "backlinks": [{"path": r, "title": self.notes[r]["title"]} for r in links if r in self.notes][:60]}

    def search(self, query, limit=40):
        self.refresh()
        words = [w for w in query.lower().split() if w]
        if not words:
            return []
        hits = []
        for note in self.notes.values():
            lower = note["lower"]
            title = note["title"].lower()
            if not all(w in lower or w in title for w in words):
                continue
            score = sum(3 for w in words if w in title) + sum(min(lower.count(w), 5) for w in words)
            if note["path"].startswith(("outputs/", "wiki/", "reports/")):
                score -= 3
            at = lower.find(words[0])
            snippet = ""
            if at >= 0:
                start = max(0, at - 70)
                snippet = re.sub(r"[#*_`>|\[\]]+", " ", note["body"][start:at + 130])
                snippet = re.sub(r"\s+", " ", snippet).strip()
            hits.append((score, note["title"], {"path": note["path"], "title": note["title"], "snippet": snippet[:200]}))
        hits.sort(key=lambda h: (-h[0], h[1].lower()))
        return [h[2] for h in hits[:limit]]

    def asset(self, path):
        """Only images the index knows, so this can never hand out an arbitrary file."""
        self.refresh()
        if path not in self.assets.values():
            return None, None
        full = self.file(path)
        try:
            return full.read_bytes(), IMAGE_TYPES[full.suffix.lower()]
        except OSError:
            return None, None

    def page(self, path):
        """A generated HTML page the index knows, as it is. A page cannot be cut line by line like a note, so one
        word from the private list anywhere in it keeps the whole page back."""
        self.refresh()
        if path not in self.pages:
            return None
        try:
            data = self.file(path).read_bytes()
        except OSError:
            return None
        if sources.PRIVATE.search(data.decode("utf-8", errors="replace")):
            return None
        return data
