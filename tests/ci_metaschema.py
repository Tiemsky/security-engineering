"""CI-only: validate every schema against the JSON Schema 2020-12 metaschema and every sample with the real `jsonschema` library."""
import json, pathlib, sys
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "tests/lib")); sys.path.insert(0, str(ROOT / "tests/contracts"))
schemas = {p.name: json.loads(p.read_text()) for p in (ROOT / "contracts").glob("*.schema.json")}
for n, s in schemas.items(): Draft202012Validator.check_schema(s)
reg = Registry().with_resources([(n, Resource.from_contents(s)) for n, s in schemas.items()])
import test_contracts as tc
names = {"http_access": "http-access-event", "security_event": "security-event", "audit_event": "audit-event", "security_decision": "security-decision", "response_outcome": "response-outcome", "system_health": "system-health-event", "deployment": "deployment-event"}
for k, ev in tc.SAMPLES.items():
    Draft202012Validator(schemas[names[k] + ".schema.json"], registry=reg, format_checker=FormatChecker()).validate(ev)
print(f"{len(schemas)} schemas valid; {len(tc.SAMPLES)} samples valid under jsonschema")
