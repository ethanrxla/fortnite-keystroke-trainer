"""Validate records against the shared JSON Schemas (shared/schemas/*.json) without third-party packages.

Supports exactly the keywords those schemas use: type (incl. lists and null), enum, const, required, properties,
additionalProperties:false, items, minItems, maxItems, minimum, maximum, maxLength, format:uuid. The ingest Edge
Function validates the same file server-side, so a record that passes here is accepted there.
"""
import json
import math
import pathlib
import re

SCHEMAS = pathlib.Path(__file__).resolve().parents[2] / "shared" / "schemas"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}
_CACHE = {}


def load(name="edit_attempt.v1"):
    if name not in _CACHE:
        _CACHE[name] = json.loads((SCHEMAS / f"{name}.json").read_text(encoding="utf-8"))
    return _CACHE[name]


def errors(value, schema=None, path="$"):
    """List of human-readable problems; empty means valid."""
    schema = load() if schema is None else schema
    out = []
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if not any(_TYPES[k](value) for k in kinds):
            return [f"{path}: expected {'/'.join(kinds)}"]
    if "const" in schema and value != schema["const"]:
        out.append(f"{path}: must be {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path}: {value!r} not one of {schema['enum']}")
    if isinstance(value, str):
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            out.append(f"{path}: longer than {schema['maxLength']}")
        if schema.get("format") == "uuid" and not UUID.match(value):
            out.append(f"{path}: not a lowercase uuid")
    if _TYPES["number"](value):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{path}: below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{path}: above {schema['maximum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            out.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, item in enumerate(value):
                out += errors(item, schema["items"], f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                out.append(f"{path}: missing {key}")
        if schema.get("additionalProperties") is False:
            out += [f"{path}: unexpected field {k}" for k in value if k not in props]
        for key, sub in props.items():
            if key in value:
                out += errors(value[key], sub, f"{path}.{key}")
    return out


def valid(value, name="edit_attempt.v1"):
    return not errors(value, load(name))
