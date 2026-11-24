"""Writes a macOS installer package (.pkg) on any computer, with the standard library only.

A .pkg is a xar archive: a header, a compressed XML table of contents, and the files one after the other. Inside it
are the Distribution file (what Apple's Installer shows and asks) and one component with its PackageInfo and its
Scripts. Scripts is a gzipped cpio archive. Brento's component has no payload of its own: its postinstall script
unpacks what lies next to it, so everything lands in the home folder of the person installing, without admin rights.
"""
import gzip
import hashlib
import io
import struct
import zlib
from pathlib import Path
from xml.sax.saxutils import escape

EPOCH = "2026-01-01T00:00:00Z"


def cpio(entries):
    """The old portable cpio format ("odc"), which Apple's Installer reads. entries: (name, mode, bytes)."""
    out = io.BytesIO()
    for number, (name, mode, data) in enumerate(list(entries) + [("TRAILER!!!", 0, b"")], 1):
        raw = name.encode("utf-8") + b"\0"
        links = 1 if name != "." else 2
        out.write(b"070707" + b"".join(b"%06o" % v for v in (0, number, mode, 0, 0, links, 0)))
        out.write(b"%011o%06o%011o" % (0, len(raw), len(data)))
        out.write(raw + data)
    return out.getvalue()


def scripts_archive(files):
    """files: {name: (bytes, executable)}. Compressed lightly, because the large parts inside already are."""
    entries = [(".", 0o040755, b"")]
    for name in sorted(files):
        data, executable = files[name]
        entries.append(("./" + name, 0o100755 if executable else 0o100644, data))
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=1, mtime=0) as packed:
        packed.write(cpio(entries))
    return out.getvalue()


def xar(tree):
    """tree: {path: bytes}, with "/" between folders. Returns the whole archive."""
    heap, offset, number = [], 20, [0]

    def build(prefix):
        nonlocal offset
        names = sorted({p[len(prefix):].split("/")[0] for p in tree if p.startswith(prefix)})
        xml = ""
        for name in names:
            number[0] += 1
            path = prefix + name
            head = '<file id="%d">' % number[0]
            common = ("<uid>0</uid><gid>0</gid><user>root</user><group>wheel</group>"
                      "<ctime>%s</ctime><mtime>%s</mtime><atime>%s</atime>" % (EPOCH, EPOCH, EPOCH))
            if path in tree:
                data = tree[path]
                digest = hashlib.sha1(data).hexdigest()
                xml += (head + '<data><archived-checksum style="sha1">%s</archived-checksum>'
                        '<extracted-checksum style="sha1">%s</extracted-checksum><size>%d</size><offset>%d</offset>'
                        '<encoding style="application/octet-stream"/><length>%d</length></data>%s'
                        "<mode>0644</mode><type>file</type><name>%s</name></file>"
                        % (digest, digest, len(data), offset, len(data), common, escape(name)))
                heap.append(data)
                offset += len(data)
            else:
                xml += "%s%s<mode>0755</mode><type>directory</type><name>%s</name>%s</file>" % (
                    head, common, escape(name), build(path + "/"))
        return xml

    files = build("")
    toc = ('<?xml version="1.0" encoding="UTF-8"?><xar><toc><creation-time>%s</creation-time>'
           '<checksum style="sha1"><offset>0</offset><size>20</size></checksum>%s</toc></xar>' % (EPOCH[:-1], files)).encode("utf-8")
    packed = zlib.compress(toc, 9)
    header = struct.pack(">4sHHQQI", b"xar!", 28, 1, len(packed), len(toc), 1)
    return header + packed + hashlib.sha1(packed).digest() + b"".join(heap)


def read_xar(data):
    """The files of a xar archive as {path: bytes}, with every checksum verified. For the tests and the build's own check."""
    import xml.etree.ElementTree as ET
    magic, size, _, packed_len, toc_len, _ = struct.unpack(">4sHHQQI", data[:28])
    if magic != b"xar!":
        raise ValueError("not a xar archive")
    packed = data[size:size + packed_len]
    toc = zlib.decompress(packed)
    if len(toc) != toc_len:
        raise ValueError("the table of contents has the wrong length")
    heap = data[size + packed_len:]
    if heap[:20] != hashlib.sha1(packed).digest():
        raise ValueError("the table of contents does not match its checksum")
    out = {}

    def walk(node, prefix):
        for item in node.findall("file"):
            name = prefix + item.findtext("name")
            if item.findtext("type") == "directory":
                walk(item, name + "/")
                continue
            part = item.find("data")
            start, length = int(part.findtext("offset")), int(part.findtext("length"))
            body = heap[start:start + length]
            if hashlib.sha1(body).hexdigest() != part.findtext("archived-checksum"):
                raise ValueError("%s does not match its checksum" % name)
            out[name] = body
    walk(ET.fromstring(toc).find("toc"), "")
    return out


def read_scripts(data):
    """The files of a Scripts archive as {name: (mode, bytes)}."""
    raw, at, out = gzip.decompress(data), 0, {}
    while True:
        if raw[at:at + 6] != b"070707":
            raise ValueError("not a cpio archive")
        mode, name_len = int(raw[at + 18:at + 24], 8), int(raw[at + 59:at + 65], 8)
        size = int(raw[at + 65:at + 76], 8)
        name = raw[at + 76:at + 76 + name_len - 1].decode("utf-8")
        if name == "TRAILER!!!":
            return out
        start = at + 76 + name_len
        out[name] = (mode, raw[start:start + size])
        at = start + size


def package_info(identifier, version, kbytes):
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<pkg-info overwrite-permissions="true" relocatable="false" identifier="%s" postinstall-action="none" version="%s" '
            'format-version="2" auth="none">\n    <payload numberOfFiles="0" installKBytes="%d"/>\n    <scripts>\n'
            '        <postinstall file="./postinstall"/>\n    </scripts>\n</pkg-info>\n' % (identifier, version, kbytes)).encode("utf-8")


def write(target, distribution, resources, component, info, scripts):
    """distribution: bytes. resources: {path: bytes} under Resources/. component: the component's folder name."""
    tree = {"Distribution": distribution, component + "/PackageInfo": info, component + "/Scripts": scripts}
    tree.update({"Resources/" + path: data for path, data in resources.items()})
    Path(target).write_bytes(xar(tree))
