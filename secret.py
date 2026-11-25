"""Keeps a private link in a file that only this person's Windows account can read, also when the file is copied elsewhere.

Windows does the encrypting (DPAPI) and holds the key. On a Mac or Linux the file is readable for its owner only.
"""
import base64
import ctypes
import sys

MARK = "dpapi:"


class Blob(ctypes.Structure):
    _fields_ = [("size", ctypes.c_uint32), ("data", ctypes.c_void_p)]


def _windows(name, raw):
    """What CryptProtectData or CryptUnprotectData makes of it, or None."""
    try:
        held = ctypes.create_string_buffer(raw, len(raw))
        given, out = Blob(len(raw), ctypes.cast(held, ctypes.c_void_p)), Blob()
        # 1: never ask the person anything.
        if not getattr(ctypes.windll.crypt32, name)(ctypes.byref(given), None, None, None, None, 1, ctypes.byref(out)):
            return None
        try:
            return ctypes.string_at(out.data, out.size)
        finally:
            ctypes.windll.kernel32.LocalFree(ctypes.c_void_p(out.data))
    except (AttributeError, OSError):
        return None


def hidden(text):
    """The text as it goes into a file."""
    if sys.platform != "win32":
        return text
    raw = _windows("CryptProtectData", text.encode("utf-8"))
    if raw is None:
        raise ValueError("Windows could not encrypt the link, so Daytag did not keep it.")
    return MARK + base64.b64encode(raw).decode("ascii")


def shown(text):
    """The text out of a file. An older Daytag wrote it as it is. '' when another account, or another computer, hid it."""
    text = text.strip()
    if not text.startswith(MARK):
        return text
    try:
        raw = _windows("CryptUnprotectData", base64.b64decode(text[len(MARK):]))
    except ValueError:
        raw = None
    return "" if raw is None else raw.decode("utf-8", "replace")
