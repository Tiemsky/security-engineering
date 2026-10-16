#!/usr/bin/env python3
"""Validate runtime outputs: schema-valid events, scenario expectations, no secret leakage, and cross-framework equality.
Usage: compare.py <outdir> <framework> [<framework> ...]   (reads <outdir>/<fw>-<scenario>.jsonl)"""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/lib"))
from minischema import validate_event

def load(p): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

def normalize(lines):
    evs = [l["event"] for l in lines if l["type"] == "event"]
    decisions = {e["event_id"] for e in evs if e["event_type"] == "security_decision"}
    first = {}
    for e in evs:
        if e["event_type"] == "response_outcome" and e["decision_event_id"] in decisions: first.setdefault(e["decision_event_id"], e["event_id"])
    out = []
    for e in evs:
        if e["event_type"] == "security_decision":
            o = next((x for x in evs if x["event_id"] == first.get(e["event_id"])), None)
            out.append({"rule_id": e["rule_id"], "decision": e["decision"], "action": e["action"], "scope_kind": e["scope"]["kind"],
                        "scope_value": e["scope"]["value"], "mode": e["mode"], "status": o["status"] if o else None})
        elif e["event_type"] == "response_outcome" and e["event_id"] not in first.values():
            out.append({"outcome_only": e["status"]})
    return out

def main(outdir, fws):
    outdir = pathlib.Path(outdir); failures = []
    for scen in sorted((ROOT / "tests/fixtures/scenarios").glob("*.json")):
        sc = json.loads(scen.read_text()); results = {}
        for fw in fws:
            lines = load(outdir / f"{fw}-{scen.stem}.jsonl"); tag = f"{fw}/{scen.stem}"
            for l in lines:
                if l["type"] == "event":
                    errs = validate_event(l["event"])
                    if errs: failures.append(f"{tag}: schema {l['event']['event_type']}: {errs[:3]}")
                    if l["event"].get("source", {}).get("framework") != fw: failures.append(f"{tag}: wrong framework tag")
            blob = json.dumps(lines)
            for s in sc.get("forbidden_substrings", []):
                if s in blob: failures.append(f"{tag}: LEAKED {s}")
            http = [l for l in lines if l["type"] == "http"]
            for h in http:
                s = sc["steps"][h["step"]]
                if "expect_status" in s and h["status"] != s["expect_status"]: failures.append(f"{tag}: step {h['step']} status {h['status']} != {s['expect_status']}")
                if "expect_client_ip" in s and h["client_ip"] != s["expect_client_ip"]: failures.append(f"{tag}: step {h['step']} client_ip {h['client_ip']} != {s['expect_client_ip']}")
            if sc.get("expect_http_status", {}).get("all") and any(h["status"] != sc["expect_http_status"]["all"] for h in http): failures.append(f"{tag}: unexpected http status")
            for a in [l for l in lines if l["type"] == "assert"]:
                exp = sc["steps"][a["step"]]["expect"]; got = a["got"]
                ok = (got >= exp["min"] if "min" in exp else got <= exp["max"]) if isinstance(exp, dict) else got == exp
                if not ok: failures.append(f"{tag}: assert step {a['step']} {a['what']}: got {got!r}, expected {exp!r}")
            if sc.get("expect_requires_approval"):
                ds = [l["event"] for l in lines if l["type"] == "event" and l["event"]["event_type"] == "security_decision"]
                if not ds or not all(x["requires_approval"] for x in ds): failures.append(f"{tag}: every decision here must require approval")
            if "expect_health" in sc:
                nh = sum(1 for l in lines if l["type"] == "event" and l["event"]["event_type"] == "system_health")
                if nh != sc["expect_health"]: failures.append(f"{tag}: system_health events {nh} != {sc['expect_health']}")
            norm = normalize(lines); results[fw] = norm
            if norm != sc["expect_events"]: failures.append(f"{tag}: events differ\n  got      {norm}\n  expected {sc['expect_events']}")
            print(f"{'ok  ' if not [f for f in failures if f.startswith(tag)] else 'FAIL'} {tag}  ({len(lines)} lines)")
        if len(fws) > 1 and len({json.dumps(v, sort_keys=True) for v in results.values()}) != 1: failures.append(f"{scen.stem}: frameworks disagree")
    for f in failures: print("FAILURE:", f)
    sys.exit(1 if failures else 0)
main(sys.argv[1], sys.argv[2:])
