import re, unittest, pathlib
from common import ROOT, SKILLS, frontmatter

REQUIRED = ["Purpose", "When to invoke", "Preconditions", "Required discovery steps", "Detailed workflow", "Security constraints",
            "Implementation requirements", "Test requirements", "Failure handling", "Completion criteria", "Required report format"]
EXPECTED = {"security-audit", "threat-modeling", "auth-hardening", "api-security", "request-observability", "bot-detection", "rate-limiting",
            "audit-trail", "incident-response", "devsecops", "security-validation", "framework-adapter-development", "environment-assessment"}

class SkillTests(unittest.TestCase):
    def test_expected_skills_exist(self): self.assertEqual(set(SKILLS), EXPECTED)

    def test_metadata_and_naming(self):   # strictest of the 3 tools (OpenCode): name==dir, regex, <=64, description 1..1024
        for s in SKILLS:
            with self.subTest(skill=s):
                fm, _ = frontmatter(ROOT / "skills" / s / "SKILL.md")
                self.assertEqual(fm["name"], s); self.assertRegex(s, r"^[a-z0-9]+(-[a-z0-9]+)*$"); self.assertLessEqual(len(s), 64)
                self.assertTrue(1 <= len(fm["description"]) <= 1024)
                self.assertLessEqual(set(fm), {"name", "description", "metadata", "license", "compatibility"})   # portable subset
                for k, v in (fm.get("metadata") or {}).items(): self.assertIsInstance(v, str, "OpenCode requires string-to-string metadata")

    def test_required_sections_in_order_and_not_empty(self):
        for s in SKILLS:
            with self.subTest(skill=s):
                body = (ROOT / "skills" / s / "SKILL.md").read_text()
                heads = re.findall(r"^## \d+\. (.+)$", body, re.M)
                self.assertEqual(heads, REQUIRED)
                for sec in re.split(r"^## \d+\. ", body, flags=re.M)[1:]: self.assertGreater(len(sec.strip().splitlines()), 1)

    def test_relative_references_resolve_and_no_secrets(self):
        for s in SKILLS:
            text = (ROOT / "skills" / s / "SKILL.md").read_text()
            for ref in re.findall(r"`(references/[^`]+)`", text): self.assertTrue((ROOT / "skills" / s / ref).exists(), f"{s}: {ref}")
            self.assertNotRegex(text, r"(?i)(api[_-]?key|password)\s*[:=]\s*['\"][^'\"]{6,}")
            self.assertNotIn("/home/", text)

    def test_every_skill_mentions_testable_acceptance(self):
        for s in SKILLS:
            body = (ROOT / "skills" / s / "SKILL.md").read_text()
            self.assertIn("Completion criteria", body); self.assertRegex(body, r"(?i)test")
