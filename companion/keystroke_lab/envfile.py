"""Load the workspace .env (one folder above the repo, outside git) into os.environ without overriding real
environment variables, and map the names this project's code expects.

Keys and model ids live only in that file. Nothing here prints or stores a value.
"""

import os
import pathlib

ENV_FILES = [pathlib.Path(__file__).resolve().parents[3] / ".env", pathlib.Path.cwd() / ".env"]
ALIASES = {"CLAUDE_API_KEY": "ANTHROPIC_API_KEY", "CLAUDE_MODEL": "KT_COACH_MODEL"}


def parse(text):
    out = {}
    for line in text.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        name, sep, value = entry.partition("=")
        if not sep:
            continue
        value = value.split(" #", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[name.strip()] = value
    return out


def load():
    for path in ENV_FILES:
        if path.is_file():
            for name, value in parse(path.read_text(encoding="utf-8-sig")).items():
                if value:
                    os.environ.setdefault(name, value)
    for source, target in ALIASES.items():
        if source in os.environ:
            os.environ.setdefault(target, os.environ[source])


load()
