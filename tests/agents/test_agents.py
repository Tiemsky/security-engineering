import json, subprocess, sys, unittest
from common import ROOT, SKILLS, frontmatter

M = json.loads((ROOT / "agents/manifest.json").read_text())["agents"]
WRITE_CLAUDE = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
VERIFIED_AG_READ_TOOLS = {"view_file", "grep_search", "run_command"}
AG_CATALOG = set(json.loads((ROOT / "tests/fixtures/antigravity-tool-catalog.json").read_text())["tools"])   # real agy 1.3.4 session catalog

class AgentTests(unittest.TestCase):
    def test_five_agents_and_specs_exist(self):
        self.assertEqual(set(M), {"security-architect", "security-implementer", "security-auditor", "security-reviewer", "security-orchestrator"})
        for n, c in M.items(): self.assertEqual(frontmatter(ROOT / "agents" / c.get("source", f"{n}.md"))[0]["name"], n)

    def test_generated_adapters_are_up_to_date(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts/build-adapters.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_manifest_skills_exist(self):
        for n, c in M.items():
            for s in c["skills"]: self.assertIn(s, SKILLS, f"{n} references unknown skill {s}")

    def test_readonly_agents_have_no_write_capability_in_any_tool(self):
        for n, c in M.items():
            if c["access"] != "read-only": continue
            with self.subTest(agent=n):
                cl = frontmatter(ROOT / f"adapters/claude-code/agents/{n}.md")[0]
                self.assertFalse(WRITE_CLAUDE & {t.strip() for t in cl["tools"].split(",")})
                self.assertEqual(frontmatter(ROOT / f"adapters/opencode/agents/{n}.md")[0]["permission"]["edit"], "deny")
                ag = frontmatter(ROOT / f"adapters/antigravity/agents/{n}.md")[0]
                self.assertTrue(set(ag["tools"]) <= VERIFIED_AG_READ_TOOLS | ({"invoke_subagent"} if n == "security-orchestrator" else set()), ag["tools"])

    def test_no_agent_gets_broad_shell_or_bypass(self):
        for n in M:
            cl = frontmatter(ROOT / f"adapters/claude-code/agents/{n}.md")[0]
            self.assertNotIn(cl.get("permissionMode"), {"bypassPermissions", "dontAsk", "auto", "acceptEdits"})
            oc = frontmatter(ROOT / f"adapters/opencode/agents/{n}.md")[0]["permission"]
            self.assertNotEqual(oc.get("bash"), "allow"); self.assertNotEqual(oc.get("webfetch"), "allow")
            if isinstance(oc.get("bash"), dict): self.assertNotEqual(oc["bash"].get("*"), "allow")
            self.assertEqual(oc.get("edit") in ("deny", "ask"), True)
            self.assertNotIn(frontmatter(ROOT / f"adapters/antigravity/agents/{n}.md")[0]["commandExecutionPolicy"], {"auto", "eager"})

    def test_opencode_agents_are_deny_by_default(self):   # regression: B2 smoke found `websearch` allowed via OpenCode's implicit '*': allow
        for n in M:
            perm = frontmatter(ROOT / f"adapters/opencode/agents/{n}.md")[0]["permission"]
            self.assertEqual(list(perm)[0], "*", "'*' must come first (last matching rule wins)"); self.assertEqual(perm["*"], "deny")
            self.assertNotIn("websearch", perm); self.assertNotIn("webfetch", {k for k, v in perm.items() if v == "allow"})
            self.assertEqual(perm.get("task", "deny") == "allow", n == "security-orchestrator")

    def test_antigravity_tool_names_exist_in_real_catalog(self):   # regression: `edit_file` did not exist (found by agy smoke test)
        for n in M:
            ag = frontmatter(ROOT / f"adapters/antigravity/agents/{n}.md")[0]
            self.assertTrue(set(ag["tools"]) <= AG_CATALOG, f"{n}: unknown tools {set(ag['tools']) - AG_CATALOG}")
        self.assertIn("invoke_subagent", frontmatter(ROOT / "adapters/antigravity/agents/security-orchestrator.md")[0]["tools"])

    def test_only_implementer_can_write_and_it_asks_first(self):
        w = [n for n, c in M.items() if c["access"] == "write"]; self.assertEqual(w, ["security-implementer"])
        self.assertEqual(frontmatter(ROOT / "adapters/opencode/agents/security-implementer.md")[0]["permission"]["edit"], "ask")

    def test_native_format_requirements(self):
        for n, c in M.items():
            cl = frontmatter(ROOT / f"adapters/claude-code/agents/{n}.md")[0]; self.assertEqual(cl["name"], n); self.assertNotIn(":", n); self.assertTrue(cl["description"])
            oc = frontmatter(ROOT / f"adapters/opencode/agents/{n}.md")[0]; self.assertIn(oc["mode"], {"primary", "subagent", "all"}); self.assertTrue(oc["description"])
            ag = frontmatter(ROOT / f"adapters/antigravity/agents/{n}.md")[0]; self.assertEqual(ag["name"], n); self.assertIsInstance(ag["tools"], list)

    def test_antigravity_rule_frontmatter_valid_and_small(self):
        p = ROOT / "adapters/antigravity/rules/security-engineering.md"; fm = frontmatter(p)[0]
        self.assertIn(fm["trigger"], {"always_on", "model_decision", "glob", "manual"}); self.assertTrue(fm["description"]); self.assertLess(p.stat().st_size, 24000)
        self.assertFalse((ROOT / "adapters/antigravity/workflows").exists(), "workflows are deprecated by Antigravity (2026-10-19)")

    def test_opencode_template_is_valid_json(self):
        j = json.loads((ROOT / "adapters/opencode/opencode.json.template").read_text()); self.assertEqual(j["$schema"], "https://opencode.ai/config.json")
