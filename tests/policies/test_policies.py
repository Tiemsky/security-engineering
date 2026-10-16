import re, unittest, uuid
import yaml
from common import ROOT

P = lambda n: yaml.safe_load((ROOT / "policies" / n).read_text())

class PolicyTests(unittest.TestCase):
    def setUp(self): self.d, self.rules, self.act, self.red = P("defaults.yaml"), P("detection-rules.yaml")["rules"], P("response-actions.yaml"), P("redaction.yaml")

    def test_observe_is_the_default_everywhere(self):
        self.assertEqual(self.d["mode"], "observe"); self.assertFalse(self.d["enforcement"]["allow_llm_as_authority"])
        for r in self.rules: self.assertEqual(r["mode"], "observe", r["id"])

    def test_all_rule_actions_exist_and_ids_unique_versioned(self):
        ids = [r["id"] for r in self.rules]; self.assertEqual(len(ids), len(set(ids)))
        for r in self.rules: self.assertIn(r["action"], self.act["actions"]); self.assertRegex(r["version"], r"^\d+\.\d+\.\d+$")

    def test_destructive_or_broad_actions_need_approval_and_ttl_bounded(self):
        a = self.act["actions"]
        for name in ("account_lock", "session_revocation"): self.assertTrue(a[name]["requires_approval"], name)
        for name, s in a.items():
            if s["reversible"] and s["max_ttl_seconds"] == 0: continue
            if name not in ("session_revocation",): self.assertGreater(s["max_ttl_seconds"], 0, name); self.assertIn("rollback", s)
            self.assertLessEqual(s["max_ttl_seconds"], self.d["enforcement"]["max_block_ttl_seconds"])
        self.assertGreaterEqual(a["temp_ip_block"]["min_evidence"], 3); self.assertIn("scope_is_ip_prefix64", a["temp_ip_block"]["approval_if"])

    def test_no_rule_blocks_on_supporting_signals_alone(self):
        for r in self.rules:
            if r["action"] in ("temp_ip_block", "account_lock", "session_revocation"): self.assertIn("shared_ip_aware", r.get("exceptions", []), r["id"])
            self.assertTrue(set(r.get("supporting_only", [])) <= {"user_agent", "geo", "risk_score"})
            self.assertNotIn("user_agent", r["evidence_required"])
        self.assertEqual(set(self.d["enforcement"]["sole_signal_forbidden"]), {"user_agent", "geo", "risk_score"})

    def test_idempotency_key_format_contains_rule_scope_window(self):
        f = self.act["idempotency"]["key_format"]
        for part in ("rule_id", "rule_version", "scope_kind", "scope_value", "window_start_epoch"): self.assertIn(part, f)

    def test_failure_modes_safe(self):
        self.assertEqual(self.d["failure_mode"]["detector_error"], "fail_open"); self.assertEqual(self.d["failure_mode"]["rate_limit_store_error_credentials"], "fail_closed")

    def test_redaction_policy_blocks_forbidden_data_but_not_uuids(self):
        pats = [re.compile(p[4:], re.I) if p.startswith("(?i)") else re.compile(p) for p in self.red["forbidden_value_patterns"]]
        hit = lambda s: any(p.search(s) for p in pats)
        for bad in ["Bearer abcdefghij12345", "eyJhbGciOiJI.eyJzdWIiOiIx.SflKxwRJSMeKKF2QT4", "4111 1111 1111 1111", "4111111111111111", "sk_live_abcdef123456"]: self.assertTrue(hit(bad), bad)
        for ok in [str(uuid.uuid4()), "00000000-0000-4000-8000-000000000000", "2026-10-16T12:00:00Z", "203.0.113.9", "2001:db8::1", "1760000000"]: self.assertFalse(hit(ok), ok)
        keys = " ".join(self.red["forbidden_fields"])
        for k in ("password", "otp", "authorization", "cookie", "token", "api_key", "card", "secret"): self.assertIn(k, keys)
        self.assertEqual(self.red["body_capture"], "none")
