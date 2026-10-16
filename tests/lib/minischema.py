"""Minimal JSON Schema validator (stdlib only) for the subset used by contracts/ — see contracts/COMPATIBILITY.md.
Unsupported keywords raise, so a schema can never silently pass validation."""
import ipaddress, json, pathlib, re

CONTRACTS = pathlib.Path(__file__).resolve().parents[2] / "contracts"
IGNORED = {"$schema", "$id", "$defs", "title", "description", "type", "enum", "const", "required", "properties", "additionalProperties", "items",
           "minItems", "minProperties", "pattern", "minLength", "maxLength", "minimum", "maximum", "format", "anyOf", "$ref"}
TYPES = {"string": str, "object": dict, "array": list, "boolean": bool, "number": (int, float), "integer": int}

def load(name): return json.loads((CONTRACTS / name).read_text())

def _resolve(ref, root):
    file, _, frag = ref.partition("#")
    doc = load(file) if file else root
    for part in [p for p in frag.split("/") if p]: doc = doc[part]
    return doc, (doc if file else root) if not file else load(file)

def validate(inst, schema, root=None, path="$"):
    """Return list of error strings (empty = valid)."""
    root = root or schema
    bad = set(schema) - IGNORED
    if bad: raise ValueError(f"unsupported schema keywords {bad} at {path}")
    errs = []
    if "$ref" in schema:
        sub, subroot = _resolve(schema["$ref"], root)
        errs += validate(inst, sub, subroot, path)
    t = schema.get("type")
    if t:
        ok = isinstance(inst, TYPES[t]) and not (t in ("integer", "number") and isinstance(inst, bool)) and not (t == "integer" and isinstance(inst, float))
        if not ok: return errs + [f"{path}: expected {t}"]
    if "const" in schema and inst != schema["const"]: errs.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and inst not in schema["enum"]: errs.append(f"{path}: {inst!r} not in enum")
    if isinstance(inst, str):
        if "pattern" in schema and not re.search(schema["pattern"], inst): errs.append(f"{path}: pattern {schema['pattern']}")
        if len(inst) < schema.get("minLength", 0): errs.append(f"{path}: too short")
        if len(inst) > schema.get("maxLength", 10**9): errs.append(f"{path}: too long")
        f = schema.get("format")
        if f == "date-time" and not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d)", inst): errs.append(f"{path}: bad date-time")
        if f in ("ipv4", "ipv6"):
            try: ipaddress.ip_address(inst) if (f == "ipv4") == ("." in inst and ":" not in inst) else (_ for _ in ()).throw(ValueError())
            except ValueError: errs.append(f"{path}: not {f}")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]: errs.append(f"{path}: < minimum")
        if "maximum" in schema and inst > schema["maximum"]: errs.append(f"{path}: > maximum")
    if "anyOf" in schema and not any(not validate(inst, s, root, path) for s in schema["anyOf"]): errs.append(f"{path}: no anyOf branch matched")
    if isinstance(inst, dict):
        for r in schema.get("required", []):
            if r not in inst: errs.append(f"{path}: missing {r}")
        if len(inst) < schema.get("minProperties", 0): errs.append(f"{path}: too few properties")
        props = schema.get("properties", {})
        for k, v in inst.items():
            if k in props: errs += validate(v, props[k], root, f"{path}.{k}")
            elif schema.get("additionalProperties") is False: errs.append(f"{path}: unexpected property {k}")
    if isinstance(inst, list):
        if len(inst) < schema.get("minItems", 0): errs.append(f"{path}: too few items")
        if "items" in schema:
            for i, v in enumerate(inst): errs += validate(v, schema["items"], root, f"{path}[{i}]")
    return errs

def validate_event(ev):
    names = {"http_access": "http-access-event", "security_event": "security-event", "audit_event": "audit-event", "security_decision": "security-decision",
             "response_outcome": "response-outcome", "system_health": "system-health-event", "deployment": "deployment-event"}
    return validate(ev, load(names[ev["event_type"]] + ".schema.json"))
