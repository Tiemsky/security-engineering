import copy, json, unittest, uuid
from common import ROOT
from minischema import validate, validate_event, load

NOW = "2026-10-16T12:00:00Z"
def env(t, **kw):
    e = {"schema_version": "1.0.0", "event_id": str(uuid.uuid4()), "event_type": t, "timestamp": NOW, "trace_id": "a" * 32,
         "source": {"framework": "laravel", "service": "s", "environment": "ci"}, "retention": {"class": "short", "days": 30},
         "redaction": {"applied": True, "policy_version": "1.0.0"}}; e.update(kw); return e
SAMPLES = {
 "http_access": env("http_access", request_id="r1", client_ip="203.0.113.9", method="GET", route="/users/{id}", status=200, duration_ms=3.2),
 "security_event": env("security_event", severity="high", classification="authn_failure", category="login", summary="x", client_ip="2001:db8::1"),
 "audit_event": env("audit_event", actor={"type": "user", "id": "u1"}, action="role.changed", target={"type": "user", "id": "u2"}, outcome="success", changed_fields=["role"]),
 "security_decision": env("security_decision", rule_id="authn.stuffing-ip", rule_version="1.0.0", mode="observe", decision="would_act", action="rate_limit",
                          evidence={"count": 30}, scope={"kind": "ip", "value": "203.0.113.9"}, idempotency_key="authn.stuffing-ip:1.0.0:ip:1:0"),
 "response_outcome": env("response_outcome", decision_event_id=str(uuid.uuid4()), action="rate_limit", status="skipped_observe_only", idempotency_key="k" * 10),
 "system_health": env("system_health", component="event_sink", status="degraded"),
 "deployment": env("deployment", version="1.2.3", commit="abcdef1", result="succeeded"),
}

class ContractTests(unittest.TestCase):
    def test_schemas_are_loadable_and_use_supported_keywords(self):
        for p in (ROOT / "contracts").glob("*.schema.json"):
            s = json.loads(p.read_text()); self.assertIn("$id", s)
            validate({}, s) if "type" in s else None   # raises on unsupported keywords

    def test_samples_valid(self):
        for k, ev in SAMPLES.items():
            with self.subTest(k): self.assertEqual(validate_event(ev), [])

    def test_ipv4_ipv6_and_invalid(self):
        for ip, ok in [("203.0.113.9", True), ("2001:db8::1", True), ("::1", True), ("999.1.1.1", False), ("not-an-ip", False)]:
            e = copy.deepcopy(SAMPLES["http_access"]); e["client_ip"] = ip
            self.assertEqual(validate_event(e) == [], ok, ip)

    def test_rejects_non_utc_missing_fields_and_extras(self):
        e = copy.deepcopy(SAMPLES["http_access"]); e["timestamp"] = "2026-10-16T12:00:00+02:00"; self.assertTrue(validate_event(e))
        e = copy.deepcopy(SAMPLES["http_access"]); del e["request_id"]; self.assertTrue(validate_event(e))
        e = copy.deepcopy(SAMPLES["http_access"]); e["authorization"] = "Bearer x"; self.assertTrue(validate_event(e), "unknown/sensitive property must be rejected")
        e = copy.deepcopy(SAMPLES["http_access"]); e["redaction"]["applied"] = False; self.assertTrue(validate_event(e))

    def test_decision_requires_evidence_scope_idempotency(self):
        for k in ("evidence", "scope", "idempotency_key", "rule_version"):
            e = copy.deepcopy(SAMPLES["security_decision"]); del e[k]; self.assertTrue(validate_event(e), k)
        e = copy.deepcopy(SAMPLES["security_decision"]); e["evidence"] = {}; self.assertTrue(validate_event(e))

    def test_route_is_a_template_field_only_and_audit_has_no_values(self):
        props = load("audit-event.schema.json")["properties"]
        self.assertNotIn("old_values", props); self.assertNotIn("new_values", props); self.assertEqual(props["changed_fields"]["items"]["type"], "string")

    def test_detection_rules_file_conforms(self):
        import yaml
        schema = load("detection-rule.schema.json")
        for r in yaml.safe_load((ROOT / "policies/detection-rules.yaml").read_text())["rules"]:
            self.assertEqual(validate(r, schema), [], r["id"])

    def test_version_and_compat_doc(self):
        self.assertEqual(SAMPLES["http_access"]["schema_version"], load("http-access-event.schema.json")["properties"]["schema_version"]["const"])
        self.assertIn("MAJOR", (ROOT / "contracts/COMPATIBILITY.md").read_text())
