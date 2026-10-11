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
    if schema is None:
        name = value.get("schema", "edit_attempt.v1") if isinstance(value, dict) else "edit_attempt.v1"
        if name not in ("edit_attempt.v1", "edit_attempt.v2"):
            return [f"{path}: unsupported schema"]
        schema = load(name)
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
    if path=="$" and isinstance(value,dict) and value.get("schema")=="edit_attempt.v2":
        opened,closed=value.get('t_edit_open'),value.get('t_close')
        if _TYPES['number'](opened) and _TYPES['number'](closed):
            if closed<opened:out.append('$: close precedes open')
            for name in ('t_first_select','t_confirm','t_reset'):
                at=value.get(name)
                if _TYPES['number'](at) and not opened<=at<=closed+.15:out.append('$.'+name+': outside attempt')
        bound=9 if value.get('piece')=='wall' else 4 if value.get('piece') in ('floor','cone','ramp') else 0
        trace=value.get('selection_trace')
        selections=[value.get('final_tiles',[])]+[s.get('tiles',[]) for s in (trace if isinstance(trace,list) else []) if isinstance(s,dict)]
        if any(any(type(t) is not int or not 0<=t<bound for t in s) or len(s)!=len(set(s)) for s in selections if isinstance(s,list)):
            out.append('$: selection outside piece topology or repeated')
        if value.get('outcome')=='result_verified' and not (value.get('result_confirmed') is True and value.get('result_evidence') in ('authored','reviewed')):
            out.append('$: verified outcome needs result evidence')
    return out


def valid(value, name=None):
    return not errors(value, load(name) if name else None)
