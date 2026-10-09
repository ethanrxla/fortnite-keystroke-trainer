"""Read KT| lines that the map Prints into the UEFN editor log (design doc section 5).

Verse Print output from a playtest lands in the editor log as `LogVerse: : KT|...`.
"""

import os
import time

DEFAULT_LOG = os.path.expandvars(r"%LOCALAPPDATA%\UnrealEditorFortnite\Saved\Logs\UnrealEditorFortnite.log")
FIELDS = ("event", "drill_id")


def parse_line(line):
    """Return a dict for a KT| line, or None. Unknown key=value pairs are kept."""
    i = line.find("KT|")
    if i < 0:
        return None
    parts = line[i:].strip().split("|")[1:]
    if len(parts) < 2:
        return None
    rec = dict(zip(FIELDS, parts[:2]))
    for p in parts[2:]:
        if "=" in p:
            k, v = p.split("=", 1)
            rec[k] = v
    for k in ("tempo", "rep", "step", "clean", "hits", "lat_ms"):
        if k in rec:
            try:
                rec[k] = int(rec[k])
            except ValueError:
                pass
    for k in ("t", "accuracy"):
        if k in rec:
            try:
                rec[k] = float(rec[k])
            except ValueError:
                pass
    return rec


def read_records(path=DEFAULT_LOG):
    with open(path, encoding="utf-8", errors="replace") as f:
        return [r for r in map(parse_line, f) if r]


def follow(path=DEFAULT_LOG, poll=0.25):
    """Yield KT records as they are appended (handles log rotation)."""
    offset = os.path.getsize(path) if os.path.exists(path) else 0
    pending = ""
    while True:
        size = os.path.getsize(path) if os.path.exists(path) else 0
        if size < offset:
            offset = 0
        if size > offset:
            with open(path, "rb") as f:
                f.seek(offset)
                pending += f.read(size - offset).decode("utf-8", errors="replace")
            offset = size
            *lines, pending = pending.split("\n")
            for line in lines:
                rec = parse_line(line)
                if rec:
                    yield rec
        time.sleep(poll)
