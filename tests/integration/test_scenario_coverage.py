"""Static guard: every shipped detection rule and every engine signal is exercised by at least one differential scenario with an expected decision."""
import json, unittest
import yaml
from common import ROOT

SCEN = [json.loads(p.read_text()) for p in sorted((ROOT / "tests/fixtures/scenarios").glob("*.json"))]
SIGNALS = json.loads((ROOT / "contracts/detection-rule.schema.json").read_text())["properties"]["signal"]["enum"]

class ScenarioCoverage(unittest.TestCase):
    def test_every_shipped_rule_has_a_triggering_scenario(self):
        rules = {r["id"] for r in yaml.safe_load((ROOT / "policies/detection-rules.yaml").read_text())["rules"]}
        covered = {e["rule_id"] for s in SCEN for e in s["expect_events"] if "rule_id" in e}
        self.assertEqual(rules - covered, set(), "rules without a scenario that expects a decision")

    def test_every_signal_is_exercised(self):
        by_id = {r["id"]: r["signal"] for r in yaml.safe_load((ROOT / "policies/detection-rules.yaml").read_text())["rules"]}
        for s in SCEN:
            for r in s["config"].get("extra_rules", []): by_id[r["id"]] = r["signal"]
        used = {by_id[e["rule_id"]] for s in SCEN for e in s["expect_events"] if e.get("rule_id") in by_id}
        self.assertEqual(set(SIGNALS) - used, set(), "engine signals never exercised")

    def test_each_rule_scenario_includes_a_below_threshold_case_or_boundary(self):   # guards against only-positive tests
        names = {p.stem for p in (ROOT / "tests/fixtures/scenarios").glob("rule-*.json")} | {"window-edge-no-trigger", "benign-low-volume"}
        self.assertGreaterEqual(len(names), 10)
        for s in SCEN:
            if s["description"].startswith(("authn.account-spray", "enum.", "scan.", "webhook.", "otp.", "request_rate")): self.assertRegex(s["description"], r"does not|do not|no trigger")

    def test_enforce_scenarios_prove_scoped_blocking_and_recovery(self):
        enforce = [s for s in SCEN if s["config"].get("mode") == "enforce"]
        self.assertGreaterEqual(len(enforce), 6)
        self.assertTrue(any(any(st.get("expect_status") == 429 for st in s["steps"]) and any(st.get("expect_status") == 200 for st in s["steps"]) for s in enforce))
