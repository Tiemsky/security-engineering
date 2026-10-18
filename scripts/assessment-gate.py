#!/usr/bin/env python3
"""Deterministic environment/scope gate for security assessments. No LLM involved; same input => same output.

Usage:
  assessment-gate.py classify SCOPE.yaml
  assessment-gate.py check SCOPE.yaml --activity ACTIVITY [--target T] [--now ISO-UTC]
  assessment-gate.py validate-report REPORT.json
Exit codes: classify/validate-report 0 ok, 1 invalid; check: 0 allow, 3 needs_confirmation, 1 deny; 2 usage error.
The gate never contacts any target. It only decides whether an activity is permitted by the recorded evidence and authorization."""
import argparse, datetime, ipaddress, json, pathlib, re, sys
from urllib.parse import urlparse
try: import yaml
except ImportError: sys.exit('assessment-gate.py needs PyYAML: pip install pyyaml (in a virtualenv or container)')

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))      # installed copy: minischema.py sits next to this file
sys.path.insert(0, str(ROOT / "tests/lib"))                              # repository checkout
STRONG = {"deployment_manifest", "ci_config", "infra_definition", "env_config", "runtime_metadata"}   # verifiable artefacts
DECLARATION = "declared_by_owner"        # counts only as corroboration, never alone
WEAK = {"hostname", "url"}               # never evidence: a name or URL proves nothing (kept in the record, ignored by the gate)
ACTIVITIES = ("static_analysis", "passive_observation", "active_read_only", "active_authenticated", "active_fuzzing", "active_load",
              "active_state_changing", "sensitive_data_collection", "exploitation", "enforcement_action")
PASSIVE = {"static_analysis", "passive_observation"}
ALWAYS_DENIED = {"exploitation", "enforcement_action"}          # destructive / live enforcement: never initiated by an agent
HEAVY = {"active_fuzzing", "active_load", "active_state_changing", "sensitive_data_collection"}
NEEDS_TEST_ACCOUNTS = {"active_authenticated", "active_state_changing"}
RPS_CAP = {"staging": 50, "production": 5, "local": 200}
MODE = {"local": "local", "staging": "staging", "production": "production", "unknown": "code-only"}
# every rule id below must be exercised by a scenario in tests/fixtures/assessment (tests/assessment enforces it)
RULES = ["E01-weak-evidence-ignored", "E02-declaration-alone", "E03-conflicting-evidence", "E04-single-source-low-confidence", "E05-confirmed",
         "G00-unknown-activity", "G01-never-by-agent", "G02-passive-allowed", "G03-unknown-env-production-suspected-heavy", "G04-unknown-env-confirm",
         "G05-local-loopback", "G06-authorization-not-explicit", "G07-target-out-of-scope", "G08-activity-not-authorized", "G09-outside-window",
         "G10-limits-missing", "G11-rate-over-cap", "G12-test-accounts-missing", "G13-production-exception-valid", "G14-production-heavy-denied", "G15-allowed"]

def norm(o):
    if isinstance(o, dict): return {k: norm(v) for k, v in o.items()}
    if isinstance(o, list): return [norm(v) for v in o]
    if isinstance(o, (datetime.datetime, datetime.date)):
        d = o if isinstance(o, datetime.datetime) else datetime.datetime(o.year, o.month, o.day)
        return d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d.tzinfo else d.strftime("%Y-%m-%dT%H:%M:%SZ")
    return o

def ts(s): return datetime.datetime.strptime(s.replace("+00:00", "Z"), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)

def load_scope(path):
    from minischema import validate, load
    scope = norm(yaml.safe_load(pathlib.Path(path).read_text()))
    errs = validate(scope, load("assessment-scope.schema.json"))
    return scope, errs

def classify(scope):
    """Environment profile from VERIFIABLE evidence only. Returns environment, mode, confidence, reasons, rules."""
    ev = scope.get("evidence", [])
    strong = [e for e in ev if e["kind"] in STRONG]
    ignored = [e for e in ev if e["kind"] in WEAK]
    decl = scope.get("declared_environment", "unknown")
    reasons, rules = [], []
    if ignored:
        rules.append("E01-weak-evidence-ignored")
        reasons.append(f"{len(ignored)} hostname/URL hint(s) ignored: a name or URL is not evidence of the environment")
    supported = {e["supports"] for e in strong}
    owner = {e["supports"] for e in ev if e["kind"] == DECLARATION}
    prod_suspect = "production" in supported or "production" in owner or decl == "production"
    out = {"environment": "unknown", "mode": MODE["unknown"], "confidence": "low", "reasons": reasons, "rules": rules, "production_suspected": prod_suspect}
    if not supported:
        rules.append("E02-declaration-alone")
        reasons.append("no verifiable evidence (deployment manifest, CI config, infrastructure definition, env config, runtime metadata); declarations and names do not count")
        return out
    if len(supported) > 1 or (decl != "unknown" and decl not in supported) or (owner and not owner <= supported):
        rules.append("E03-conflicting-evidence")
        reasons.append(f"conflicting environment signals: evidence={sorted(supported)} declared={decl} owner_declarations={sorted(owner)}")
        return out
    env = next(iter(supported)); kinds = {e["kind"] for e in strong if e["supports"] == env}
    agrees = decl == env
    if len(kinds) >= 2 and agrees: conf = "high"
    elif len(kinds) >= 2 or agrees: conf = "medium"
    else: conf = "low"
    if conf == "low":
        rules.append("E04-single-source-low-confidence")
        reasons.append("a single verifiable source and no matching declaration: confidence too low to unlock active testing")
        out["production_suspected"] = prod_suspect or env == "production"
        return out
    rules.append("E05-confirmed")
    reasons.append(f"{env} confirmed by {sorted(kinds)}" + (" and matching declaration" if agrees else ""))
    out.update(environment=env, mode=MODE[env], confidence=conf, production_suspected=env == "production")
    return out

def host_of(t):
    t = t.strip()
    return (urlparse(t if "://" in t else "//" + t).hostname or "").lower()

def in_scope(target, targets):
    if not target: return False
    h = host_of(target)
    for t in targets:
        v = t["value"].strip().lower()
        if t["kind"] == "domain":
            if v.startswith("*.") and h.endswith(v[1:]) and h != v[2:]: return True
            if h == v: return True
        elif t["kind"] == "ip_range":
            try:
                if ipaddress.ip_address(h) in ipaddress.ip_network(v, strict=False): return True
            except ValueError: pass
        elif t["kind"] == "url" and target.strip().lower().startswith(v): return True
    return False

def is_loopback(target):
    h = host_of(target or "")
    if h == "localhost": return True
    try: return ipaddress.ip_address(h).is_loopback
    except ValueError: return False

def check(scope, activity, target=None, now=None):
    c = classify(scope); env = c["environment"]; rules = list(c["rules"]); reasons = list(c["reasons"])
    def done(decision, rule, why, conditions=None):
        rules.append(rule); reasons.append(why)
        return {"decision": decision, "environment": env, "mode": c["mode"], "confidence": c["confidence"], "activity": activity,
                "rules": rules, "reasons": reasons, "conditions": conditions or []}
    if activity not in ACTIVITIES: return done("deny", "G00-unknown-activity", f"unknown activity class {activity!r}")
    if activity in ALWAYS_DENIED: return done("deny", "G01-never-by-agent", f"{activity} is never initiated by an agent; a human owner must do it through a controlled process")
    if activity in PASSIVE: return done("allow", "G02-passive-allowed", "no request is sent to any target")
    auth = scope.get("authorization", {}); now_dt = ts(now) if now else datetime.datetime.now(datetime.timezone.utc)
    if env == "unknown":
        if c["production_suspected"] and activity in HEAVY:
            return done("deny", "G03-unknown-env-production-suspected-heavy", "environment unresolved and some evidence points to production: heavy activity denied")
        return done("needs_confirmation", "G04-unknown-env-confirm", "environment cannot be established from verifiable evidence; stay in code-only mode and ask the owner")
    if env == "local" and is_loopback(target) and activity in {"active_read_only", "active_authenticated", "active_fuzzing", "active_load", "active_state_changing"}:
        return done("allow", "G05-local-loopback", "confirmed local environment and a loopback target", ["target must be your own local instance with synthetic data"])
    if auth.get("status") != "explicit" or not auth.get("approver"):
        return done("deny", "G06-authorization-not-explicit", "no explicit, attributed authorization; technical accessibility is never authorization")
    if not in_scope(target, auth.get("targets", [])):
        return done("deny", "G07-target-out-of-scope", f"target {target!r} is not in the authorized scope")
    if activity not in auth.get("allowed_activities", []):
        return done("deny", "G08-activity-not-authorized", f"{activity} is not in allowed_activities")
    w = auth.get("window")
    if env != "local" and (not w or not (ts(w["start"]) <= now_dt <= ts(w["end"]))):
        return done("deny", "G09-outside-window", "outside the authorized test window (or no window recorded)")
    lim = auth.get("limits", {}); missing = [k for k in ("max_requests_per_second", "stop_conditions", "rollback") if not lim.get(k) and lim.get(k) != 0] if env != "local" else []
    if missing: return done("needs_confirmation", "G10-limits-missing", f"limits missing: {missing}")
    if lim.get("max_requests_per_second", 0) > RPS_CAP[env]:
        return done("deny", "G11-rate-over-cap", f"max_requests_per_second {lim['max_requests_per_second']} exceeds the {env} cap {RPS_CAP[env]}")
    if activity in NEEDS_TEST_ACCOUNTS and not auth.get("test_accounts"):
        return done("needs_confirmation", "G12-test-accounts-missing", "dedicated test accounts must be recorded; real user accounts are never used")
    if env == "production" and activity in HEAVY:
        exc = [e for e in auth.get("production_exceptions", []) if e["activity"] == activity and ts(e["expires"]) > now_dt]
        if exc: return done("allow", "G13-production-exception-valid", f"specific, attributed, unexpired exception by {exc[0]['approver']}", ["follow the recorded safety plan", "stop on any stop condition"])
        return done("deny", "G14-production-heavy-denied", f"{activity} in production needs a specific unexpired production_exception with approver and safety plan")
    return done("allow", "G15-allowed", "evidence, scope, activity, window and limits satisfied", ["respect limits.stop_conditions", "use synthetic data / test accounts only"])

FORBIDDEN_CLAIM = re.compile(r"completely secure|fully secure|100% secure|guaranteed secure|no (remaining )?vulnerabilit(y|ies) (exist|remain)|\bis secure\b", re.I)
NEGATION = re.compile(r"\b(not|cannot|can't|never|no claim|without claiming)\b[^.]{0,60}$", re.I)

def claims_security(text):
    """True if the text asserts the application is secure; a negated mention ('this is not a statement that it is secure') is fine."""
    return any(not NEGATION.search(text[:m.start()]) for m in FORBIDDEN_CLAIM.finditer(text))

def validate_report(report):
    """Schema + cross-field rules. Returns a list of problems (empty = acceptable)."""
    from minischema import validate, load
    errs = validate(report, load("assessment-report.schema.json"))
    if errs: return errs
    cov = yaml.safe_load((ROOT / "core/assessment-coverage.yaml").read_text())
    mode, rows, problems = report["mode"], report["matrix"], []
    topics = {r["topic"] for r in rows}
    required = cov["local" if mode == "code-only" else mode]
    for t in required:
        if t not in topics: problems.append(f"coverage: mode {mode} requires a matrix row for topic {t!r}")
    for r in rows:
        who = f"{r['topic']}/{r['control'][:40]}"
        if r["result"] == "PASS":
            if not r["evidence"]: problems.append(f"{who}: PASS without evidence")
            if r["confidence"] == "low": problems.append(f"{who}: PASS with low confidence is not a pass")
            if r["verification_scope"] == "dynamic" and mode in ("code-only", "local") and r["environment"] != "local":
                problems.append(f"{who}: a dynamic check cannot PASS in {mode} mode against a non-local environment")
            if r["verification_scope"] == "operational" and mode in ("code-only", "local"):
                problems.append(f"{who}: an operational/infrastructure control cannot PASS from a code-only or local assessment")
        if r["result"] == "FAIL":
            if r["severity"] == "none": problems.append(f"{who}: FAIL needs a severity")
            if not r.get("remediation") or not r.get("retest"): problems.append(f"{who}: FAIL needs remediation and a retest procedure")
        if r["result"] in ("NOT_TESTED", "PARTIAL", "NOT_APPLICABLE") and not r.get("reason"): problems.append(f"{who}: {r['result']} needs a reason")
        if r.get("execution") in ("error", "timeout") and r["result"] == "PASS": problems.append(f"{who}: execution {r['execution']!r} cannot be a PASS (a failed or timed-out test is not a pass)")
        if r.get("remediation_status") == "fixed" and r.get("retest_status") == "failed": problems.append(f"{who}: remediation_status 'fixed' contradicts retest_status 'failed'")
    env = report["environment"]
    if mode == "code-only" and env["determined"] != "unknown": problems.append("code-only mode requires environment.determined == unknown")
    if mode != "code-only" and env["determined"] != mode: problems.append(f"mode {mode} but environment.determined is {env['determined']}")
    if env["determined"] == "unknown" and not env.get("ambiguities"): problems.append("unknown environment must list its ambiguities")
    if not env["limitations"]: problems.append("environment.limitations must not be empty")
    s = report["summary"]; passed = {r["control"] for r in rows if r["result"] == "PASS"}
    for c in s["verified_secure"]:
        if c not in passed: problems.append(f"summary.verified_secure lists {c!r} which is not a PASS row")
    if any(r["result"] == "FAIL" for r in rows) and not s["confirmed_vulnerabilities"]: problems.append("FAIL rows exist but summary.confirmed_vulnerabilities is empty")
    if any(r["result"] == "NOT_TESTED" for r in rows) and not (s["unverified"] or s["intentionally_not_performed"]): problems.append("NOT_TESTED rows exist but are absent from the summary")
    if claims_security(s.get("statement", "")): problems.append("summary.statement claims the application is secure; audits cannot certify that")
    return problems

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("classify"); a.add_argument("scope")
    b = sub.add_parser("check"); b.add_argument("scope"); b.add_argument("--activity", required=True); b.add_argument("--target"); b.add_argument("--now")
    c = sub.add_parser("validate-report"); c.add_argument("report")
    args = ap.parse_args(argv)
    if args.cmd == "validate-report":
        p = validate_report(json.loads(pathlib.Path(args.report).read_text()))
        print(json.dumps({"valid": not p, "problems": p}, indent=2)); return 1 if p else 0
    scope, errs = load_scope(args.scope)
    if errs: print(json.dumps({"valid": False, "problems": errs}, indent=2)); return 1
    if args.cmd == "classify": print(json.dumps(classify(scope), indent=2)); return 0
    r = check(scope, args.activity, args.target, args.now); print(json.dumps(r, indent=2))
    return {"allow": 0, "needs_confirmation": 3, "deny": 1}[r["decision"]]

if __name__ == "__main__": sys.exit(main())
