"""Environment-aware assessment: deterministic classification/gate, report validator, coverage topics, wiring into skills and agents.
Five quality-gate capacities (core/assessment-quality-gate.md): detection, coverage, evidence quality, operational safety, improvement guard."""
import copy, importlib.util, json, pathlib, subprocess, sys, tempfile, unittest
import yaml
from common import ROOT
from minischema import validate, load

spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts/assessment-gate.py"); gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
SCEN = json.loads((ROOT / "tests/fixtures/assessment/scenarios.json").read_text())
COV = yaml.safe_load((ROOT / "core/assessment-coverage.yaml").read_text())

def run_all():
    for s in SCEN:
        yield s, gate.classify(s["scope"]), [(c, gate.check(s["scope"], c["activity"], c["target"], c["now"])) for c in s["checks"]]

def report(mode, **over):
    """A minimal valid report for `mode`: one honest NOT_TESTED row per required topic."""
    env = {"code-only": "unknown"}.get(mode, mode)
    rows = [{"topic": t, "control": f"{t} control", "environment": "all", "verification_scope": "static", "method": "not performed", "evidence": [],
             "result": "NOT_TESTED", "severity": "none", "confidence": "high", "reason": "no access in this assessment", "remediation": "", "retest": ""}
            for t in COV["local" if mode == "code-only" else mode]]
    r = {"schema_version": "1.0.0", "mode": mode, "environment": {"determined": env, "confidence": "low" if env == "unknown" else "high", "evidence": ["x"],
         "limitations": ["code and configuration only"], **({"ambiguities": ["hostname only"]} if env == "unknown" else {})}, "matrix": rows,
         "summary": {"verified_secure": [], "confirmed_vulnerabilities": [], "partially_verified": [], "unverified": ["all topics"], "intentionally_not_performed": []}}
    r.update(over); return r

class Detection(unittest.TestCase):          # capacity 1: environment detection
    def test_scenarios_classify_as_expected(self):
        for s, cl, _ in run_all():
            with self.subTest(s["name"]):
                for k, v in s["classify"].items():
                    if k == "rules": self.assertTrue(set(v) <= set(cl["rules"]), (v, cl["rules"]))
                    else: self.assertEqual(cl[k], v, k)

    def test_hostnames_and_urls_never_change_the_classification(self):
        base = next(s for s in SCEN if s["name"] == "staging-confirmed-authorized")["scope"]
        noisy = copy.deepcopy(base)
        noisy["evidence"] += [{"kind": k, "detail": "production.example.org", "supports": "production"} for k in ("hostname", "url")] * 3
        self.assertEqual(gate.classify(noisy)["environment"], "staging")
        bare = copy.deepcopy(base); bare["evidence"] = [{"kind": "hostname", "detail": "staging.example.org", "supports": "staging"}]
        self.assertEqual(gate.classify(bare)["environment"], "unknown")

    def test_declaration_cannot_override_contrary_evidence(self):
        s = copy.deepcopy(next(x for x in SCEN if x["name"] == "staging-confirmed-authorized")["scope"]); s["declared_environment"] = "production"
        self.assertEqual(gate.classify(s)["environment"], "unknown")

    def test_deterministic(self):
        for s in SCEN:
            self.assertEqual(json.dumps(gate.classify(s["scope"]), sort_keys=True), json.dumps(gate.classify(copy.deepcopy(s["scope"])), sort_keys=True))

class Safety(unittest.TestCase):             # capacity 4: operational safety
    def test_gate_decisions_match_scenarios(self):
        for s, _, checks in run_all():
            for c, r in checks:
                with self.subTest(f"{s['name']}:{c['activity']}:{c['now']}"):
                    self.assertEqual(r["decision"], c["expect"], r["reasons"])
                    self.assertTrue(set(c["rules"]) <= set(r["rules"]), (c["rules"], r["rules"]))

    def test_every_gate_rule_is_exercised_by_a_scenario(self):       # improvement guard: a rule without a scenario cannot be changed unnoticed
        seen = {rule for _, cl, checks in run_all() for rule in cl["rules"] + [x for _, r in checks for x in r["rules"]]}
        self.assertEqual(set(gate.RULES) - seen, set(), "rules without scenario")
        self.assertEqual(seen - set(gate.RULES), set(), "undeclared rule ids")

    def test_exploitation_and_enforcement_are_denied_in_every_environment(self):
        for s in SCEN:
            for act in ("exploitation", "enforcement_action"):
                self.assertEqual(gate.check(s["scope"], act, "https://app.example.org/", "2026-10-20T09:00:00Z")["decision"], "deny", (s["name"], act))

    def test_passive_work_is_always_allowed_and_active_never_without_a_confirmed_environment(self):
        for s in SCEN:
            self.assertEqual(gate.check(s["scope"], "static_analysis")["decision"], "allow")
            if s["classify"]["environment"] == "unknown":
                for act in gate.ACTIVITIES:
                    if act not in gate.PASSIVE | gate.ALWAYS_DENIED:
                        self.assertNotEqual(gate.check(s["scope"], act, "https://app.example.org/", "2026-10-20T09:00:00Z")["decision"], "allow", (s["name"], act))

    def test_production_never_allows_heavy_activity_without_exception(self):
        prod = copy.deepcopy(next(x for x in SCEN if x["name"] == "production-readonly")["scope"])
        prod["authorization"]["allowed_activities"] = list(gate.ACTIVITIES)
        for act in gate.HEAVY:
            self.assertEqual(gate.check(prod, act, "https://app.example.org/", "2026-10-20T09:00:00Z")["decision"], "deny", act)

    def test_authorization_without_approver_or_with_accessible_target_only_is_not_enough(self):
        s = copy.deepcopy(next(x for x in SCEN if x["name"] == "staging-confirmed-authorized")["scope"]); del s["authorization"]["approver"]
        self.assertEqual(gate.check(s, "active_read_only", "https://app.example.org/", "2026-10-20T09:00:00Z")["rules"][-1], "G06-authorization-not-explicit")

    def test_scope_matching_is_exact(self):
        t = [{"kind": "domain", "value": "app.example.org"}, {"kind": "domain", "value": "*.api.example.org"}, {"kind": "ip_range", "value": "198.51.100.0/24"}]
        for target, ok in [("https://app.example.org/x", True), ("https://evil-app.example.org/", False), ("https://app.example.org.evil.net/", False),
                           ("https://v1.api.example.org/", True), ("https://api.example.org/", False), ("http://198.51.100.7:8080/", True), ("http://198.51.101.7/", False), ("", False), (None, False)]:
            self.assertEqual(gate.in_scope(target, t), ok, target)

    def test_cli_exit_codes_and_invalid_scope(self):
        d = pathlib.Path(tempfile.mkdtemp()); f = d / "scope.yaml"
        f.write_text(yaml.safe_dump(next(x for x in SCEN if x["name"] == "staging-confirmed-authorized")["scope"]))
        run = lambda *a: subprocess.run([sys.executable, str(ROOT / "scripts/assessment-gate.py"), *a], capture_output=True, text=True)
        self.assertEqual(run("check", str(f), "--activity", "active_read_only", "--target", "https://app.example.org/", "--now", "2026-10-20T09:00:00Z").returncode, 0)
        self.assertEqual(run("check", str(f), "--activity", "active_read_only", "--target", "https://other.example.org/", "--now", "2026-10-20T09:00:00Z").returncode, 1)
        self.assertEqual(run("classify", str(f)).returncode, 0)
        f.write_text("schema_version: '1.0.0'\n"); self.assertEqual(run("classify", str(f)).returncode, 1)
        self.assertEqual(run("check", str(f)).returncode, 2)
        self.assertEqual(run("check", str(f), "--activity", "static_analysis").returncode, 1, "invalid scope must not yield allow")

class Contracts(unittest.TestCase):
    def test_scope_scenarios_validate_and_extras_are_rejected(self):
        sch = load("assessment-scope.schema.json")
        for s in SCEN: self.assertEqual(validate(s["scope"], sch), [], s["name"])
        bad = copy.deepcopy(SCEN[0]["scope"]); bad["token"] = "x"; self.assertTrue(validate(bad, sch))
        bad = copy.deepcopy(SCEN[0]["scope"]); bad["evidence"][0]["kind"] = "gut_feeling"; self.assertTrue(validate(bad, sch))

    def test_committed_sample_report_is_valid(self):
        r = json.loads((ROOT / "tests/fixtures/assessment/report-code-only.json").read_text()); self.assertEqual(gate.validate_report(r), [])

class Evidence(unittest.TestCase):           # capacity 3: evidence quality
    def test_minimal_honest_reports_are_valid_for_every_mode(self):
        for m in ("code-only", "local", "staging", "production"): self.assertEqual(gate.validate_report(report(m)), [], m)

    def mut(self, mode, fn, needle):
        r = report(mode); fn(r); p = gate.validate_report(r); self.assertTrue(any(needle in x for x in p), (needle, p))

    def test_pass_requires_evidence_and_confidence(self):
        def ok(r): r["matrix"][0].update(result="PASS", reason="", evidence=["tests/Auth/LoginTest.php::test_throttle passed"]); r["summary"]["verified_secure"] = [r["matrix"][0]["control"]]
        r = report("local"); ok(r); self.assertEqual(gate.validate_report(r), [])
        self.mut("local", lambda r: (ok(r), r["matrix"][0].update(evidence=[])), "PASS without evidence")
        self.mut("local", lambda r: (ok(r), r["matrix"][0].update(confidence="low")), "low confidence")

    def test_runtime_and_operational_controls_cannot_pass_from_a_code_audit(self):
        for m in ("code-only", "local"):
            self.mut(m, lambda r: r["matrix"][0].update(result="PASS", reason="", evidence=["config file"], verification_scope="operational", environment="production"), "operational")
            self.mut(m, lambda r: r["matrix"][0].update(result="PASS", reason="", evidence=["curl output"], verification_scope="dynamic", environment="staging"), "dynamic")

    def test_missing_topic_is_a_coverage_failure(self):
        for m in ("code-only", "local", "staging", "production"):
            self.mut(m, lambda r: r["matrix"].pop(), "requires a matrix row")

    def test_fail_not_tested_and_partial_rules(self):
        self.mut("local", lambda r: r["matrix"][0].update(result="FAIL", severity="high", reason="", remediation="fix", retest=""), "retest")
        self.mut("local", lambda r: r["matrix"][0].update(result="FAIL", severity="none", reason="", remediation="fix", retest="rerun"), "needs a severity")
        self.mut("local", lambda r: r["matrix"][0].update(reason=""), "needs a reason")
        self.mut("local", lambda r: r["matrix"][0].update(result="PARTIAL", reason=""), "needs a reason")

    def test_summary_must_agree_with_matrix_and_never_claim_security(self):
        self.mut("local", lambda r: r["summary"].update(verified_secure=["something never tested"]), "not a PASS row")
        self.mut("local", lambda r: (r["matrix"][0].update(result="FAIL", severity="low", reason="", remediation="x", retest="y")), "confirmed_vulnerabilities is empty")
        self.mut("local", lambda r: r["summary"].update(unverified=[], intentionally_not_performed=[]), "absent from the summary")
        for claim in ("The application is completely secure.", "No vulnerabilities exist.", "It is 100% secure"):
            self.mut("local", lambda r, c=claim: r["summary"].update(statement=c), "claims the application is secure")
        self.assertTrue(gate.claims_security("Audit done. The application is secure.")); self.assertFalse(gate.claims_security("This is not a statement that the application is secure."))
        r = report("local"); r["summary"]["statement"] = "No vulnerability was found in the reviewed code; runtime controls were not verified."
        self.assertEqual(gate.validate_report(r), [])

    def test_environment_and_mode_must_agree(self):
        self.mut("staging", lambda r: r["environment"].update(determined="production"), "environment.determined")
        self.mut("code-only", lambda r: r["environment"].update(determined="staging"), "code-only mode requires")
        self.mut("code-only", lambda r: r["environment"].update(ambiguities=[]), "ambiguities")
        self.mut("local", lambda r: r["environment"].update(limitations=[]), "limitations")

class Installed(unittest.TestCase):          # the gate must work where the agents actually run: an installed project, not only this repository
    def test_gate_runs_standalone_from_a_project_install(self):
        proj = pathlib.Path(tempfile.mkdtemp()); (proj / ".git").mkdir()
        r = subprocess.run([str(ROOT / "scripts/install.sh"), "--mode", "project", "--project-dir", str(proj), "--tools", "claude"], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        g = proj / ".security-engineering/shared/scripts/assessment-gate.py"; self.assertTrue(g.is_file()); self.assertTrue((proj / ".security-engineering/shared/scripts/minischema.py").is_file())
        scope = proj / "scope.yaml"; scope.write_text(yaml.safe_dump(next(x for x in SCEN if x["name"] == "staging-confirmed-authorized")["scope"]))
        run = lambda *a: subprocess.run([sys.executable, "-I", str(g), *a], capture_output=True, text=True, cwd=proj)   # -I: no repo checkout on sys.path
        ok = run("check", str(scope), "--activity", "active_read_only", "--target", "https://app.example.org/", "--now", "2026-10-20T09:00:00Z"); self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(run("check", str(scope), "--activity", "active_load", "--target", "https://app.example.org/", "--now", "2026-10-20T09:00:00Z").returncode, 1)
        rep = run("validate-report", str(ROOT / "tests/fixtures/assessment/report-code-only.json")); self.assertEqual(rep.returncode, 0, rep.stdout + rep.stderr)
        bad = proj / "bad.json"; bad.write_text("{}"); self.assertEqual(run("validate-report", str(bad)).returncode, 1)

class Coverage(unittest.TestCase):           # capacity 2: assessment coverage
    def test_topic_lists_are_valid_and_unique(self):
        self.assertEqual(set(COV), {"local", "staging", "production"})
        for m, ts in COV.items(): self.assertEqual(len(ts), len(set(ts)), m); self.assertTrue(all(__import__("re").fullmatch(r"[a-z][a-z0-9_]{1,63}", t) for t in ts), m)

    def test_local_topics_include_the_required_vulnerability_classes(self):
        for t in ("authentication", "authorization_rbac", "session_management", "input_validation", "injection", "ssrf", "idor_bola", "deserialization_file_handling", "secrets", "dependencies", "container_iac", "cicd", "security_tests", "runtime_unverifiable"):
            self.assertIn(t, COV["local"])

    def test_production_topics_are_operational_and_staging_adds_dynamic_surface(self):
        for t in ("backups_recovery", "incident_response_readiness", "cloud_iam_network_segmentation", "source_runtime_correlation"): self.assertIn(t, COV["production"])
        for t in ("tls_certificates", "dast_api_testing", "rate_limiting_anti_automation", "finding_reproducibility", "recovery_controls"): self.assertIn(t, COV["staging"])

class Wiring(unittest.TestCase):             # the protocol must reach all three tools without new permissions
    def test_skill_states_every_gate_vocabulary_item(self):
        t = (ROOT / "skills/environment-assessment/SKILL.md").read_text()
        for a in gate.ACTIVITIES: self.assertIn(a, t, a)
        for w in ("PASS", "FAIL", "PARTIAL", "NOT_TESTED", "NOT_APPLICABLE", "code-only", "never", "scripts/assessment-gate.py", "core/assessment-coverage.yaml", "production_exception"): self.assertIn(w, t, w)
        for k, v in gate.RPS_CAP.items(): self.assertIn(f"{k} {v}", t, f"cap {k}")
        for a in gate.ALWAYS_DENIED: self.assertIn(a, t)

    def test_agents_that_report_load_the_skill_in_every_tool_and_gain_no_permission(self):
        m = json.loads((ROOT / "agents/manifest.json").read_text())["agents"]
        for a in ("security-orchestrator", "security-architect", "security-auditor", "security-reviewer"):
            self.assertIn("environment-assessment", m[a]["skills"], a)
            for tool, path in (("claude-code", "adapters/claude-code/agents/%s.md"), ("opencode", "adapters/opencode/agents/%s.md"), ("antigravity", "adapters/antigravity/agents/%s.md")):
                body = (ROOT / (path % a)).read_text()
                if tool != "opencode": self.assertIn("environment-assessment", body, (a, tool))   # OpenCode agents load skills on demand, via the procedure text
        for a in ("security-orchestrator", "security-auditor", "security-reviewer", "security-architect"):
            self.assertIn("environment-assessment", (ROOT / f"agents/{'orchestrator' if a.endswith('orchestrator') else a}.md").read_text(), a)
        self.assertNotIn("environment-assessment", m["security-implementer"]["skills"])

    def test_instruction_templates_and_rule_name_the_skill(self):
        for f in ("adapters/claude-code/CLAUDE.md.template", "adapters/opencode/AGENTS.md.template", "adapters/antigravity/rules/security-engineering.md"):
            self.assertIn("environment-assessment", (ROOT / f).read_text(), f)

    def test_security_audit_requires_environment_profile_first(self):
        t = (ROOT / "skills/security-audit/SKILL.md").read_text(); self.assertIn("environment-assessment", t); self.assertIn("Environment profile", t)

    def test_quality_gate_document_covers_the_five_capacities(self):
        t = (ROOT / "core/assessment-quality-gate.md").read_text()
        for c in ("Environment Detection", "Assessment Coverage", "Evidence Quality", "Operational Safety", "Continuous Improvement"): self.assertIn(c, t)

if __name__ == "__main__": unittest.main()
