import json, os, pathlib, shutil, subprocess, tempfile, unittest
from common import ROOT, SKILLS

INSTALL, UNINSTALL, VALIDATE = (str(ROOT / "scripts" / n) for n in ("install.sh", "uninstall.sh", "validate-installation.sh"))

def sh(args, home, **kw):
    env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}
    return subprocess.run(args, capture_output=True, text=True, env=env, **kw)

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="se-inst-")); self.home = self.tmp / "home"; self.home.mkdir(); self.proj = self.tmp / "proj"; self.proj.mkdir()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def snap(self, root): return {str(p.relative_to(root)): p.read_bytes() for p in pathlib.Path(root).rglob("*") if p.is_file()}
    G = ["--mode", "global", "--tools", "claude,opencode,antigravity"]

    def test_dry_run_writes_nothing(self):
        r = sh([INSTALL, *self.G, "--dry-run"], self.home); self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("dry-run", r.stdout); self.assertEqual(self.snap(self.home), {})

    def test_global_install_layout_and_tool_paths(self):
        self.assertEqual(sh([INSTALL, *self.G], self.home).returncode, 0)
        for s in SKILLS: self.assertTrue((self.home / ".claude/skills" / s / "SKILL.md").exists()); self.assertTrue((self.home / ".gemini/config/skills" / s / "SKILL.md").exists())
        self.assertFalse((self.home / ".config/opencode/skills").exists(), "opencode skills skipped when Claude-compatible path is installed (no duplicates)")
        self.assertTrue((self.home / ".claude/agents/security-reviewer.md").exists()); self.assertTrue((self.home / ".config/opencode/agents/security-reviewer.md").exists())
        self.assertTrue((self.home / ".gemini/config/rules/security-engineering.md").exists()); self.assertTrue((self.home / ".security-engineering/shared/contracts/COMPATIBILITY.md").exists())

    def test_opencode_alone_gets_own_skills(self):
        sh([INSTALL, "--mode", "global", "--tools", "opencode"], self.home); self.assertTrue((self.home / ".config/opencode/skills/security-audit/SKILL.md").exists())

    def test_idempotent_second_run_changes_nothing(self):
        sh([INSTALL, *self.G], self.home); before = self.snap(self.home)
        r = sh([INSTALL, *self.G], self.home); self.assertIn("0 action(s)", r.stdout); self.assertEqual(self.snap(self.home), before)

    def test_existing_unrelated_config_preserved(self):
        (self.home / ".claude").mkdir(); (self.home / ".claude/settings.json").write_text('{"permissions":{"allow":["Bash(ls)"]}}'); (self.home / ".claude/CLAUDE.md").write_text("# mine\n")
        sh([INSTALL, *self.G], self.home)
        self.assertEqual(json.loads((self.home / ".claude/settings.json").read_text()), {"permissions": {"allow": ["Bash(ls)"]}}); self.assertEqual((self.home / ".claude/CLAUDE.md").read_text(), "# mine\n")

    def test_foreign_file_conflict_then_force_backs_up(self):
        t = self.home / ".claude/agents/security-reviewer.md"; t.parent.mkdir(parents=True); t.write_text("USER VERSION")
        r = sh([INSTALL, *self.G], self.home); self.assertEqual(r.returncode, 3); self.assertIn("CONFLICT", r.stdout); self.assertEqual(t.read_text(), "USER VERSION")
        r = sh([INSTALL, *self.G, "--force"], self.home); self.assertEqual(r.returncode, 0); baks = list(t.parent.glob("security-reviewer.md.bak.*")); self.assertEqual(len(baks), 1); self.assertEqual(baks[0].read_text(), "USER VERSION")

    def test_duplicate_skill_name_elsewhere_warns(self):
        d = self.home / ".agents/skills/security-audit"; d.mkdir(parents=True); (d / "SKILL.md").write_text("---\nname: security-audit\n---\n")
        self.assertIn("WARNING duplicate skill name 'security-audit'", sh([INSTALL, "--mode", "global", "--tools", "claude"], self.home).stdout)

    def test_downgrade_refused_without_flag(self):
        sh([INSTALL, *self.G], self.home); mp = self.home / ".security-engineering/manifest-global.json"; m = json.loads(mp.read_text()); m["version"] = "9.9.9"; mp.write_text(json.dumps(m))
        r = sh([INSTALL, *self.G], self.home); self.assertEqual(r.returncode, 4); self.assertIn("REFUSED", r.stdout)
        self.assertEqual(sh([INSTALL, *self.G, "--allow-version-change"], self.home).returncode, 0)

    def test_locally_modified_managed_file_is_not_overwritten_on_update(self):
        sh([INSTALL, *self.G], self.home); f = self.home / ".claude/agents/security-auditor.md"; f.write_text(f.read_text() + "\n# local tweak\n")
        r = sh([INSTALL, *self.G], self.home); self.assertEqual(r.returncode, 3); self.assertIn("local tweak", f.read_text())
        self.assertNotEqual(sh([VALIDATE, "--mode", "global"], self.home).returncode, 0)

    def test_validate_ok_and_detects_missing(self):
        sh([INSTALL, *self.G], self.home); r = sh([VALIDATE, "--mode", "global"], self.home); self.assertEqual(r.returncode, 0, r.stdout); self.assertIn("static verification only", r.stdout)
        (self.home / ".claude/skills/security-audit/SKILL.md").unlink(); self.assertEqual(sh([VALIDATE, "--mode", "global"], self.home).returncode, 1)

    def test_uninstall_removes_only_unmodified_and_keeps_user_files(self):
        sh([INSTALL, *self.G], self.home); (self.home / ".claude/mine.txt").write_text("x"); mod = self.home / ".claude/agents/security-auditor.md"; mod.write_text("changed")
        r = sh([UNINSTALL, "--mode", "global"], self.home); self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("KEEP", r.stdout)
        self.assertTrue(mod.exists()); self.assertTrue((self.home / ".claude/mine.txt").exists()); self.assertFalse((self.home / ".claude/skills/security-audit").exists()); self.assertFalse((self.home / ".security-engineering/manifest-global.json").exists())

    def test_uninstall_restore_backups(self):
        t = self.home / ".claude/agents/security-reviewer.md"; t.parent.mkdir(parents=True); t.write_text("USER VERSION")
        sh([INSTALL, *self.G, "--force"], self.home); sh([UNINSTALL, "--mode", "global", "--restore-backups"], self.home); self.assertEqual(t.read_text(), "USER VERSION")

    def test_project_mode_minimal_package_and_preservation(self):
        (self.proj / "composer.json").write_text('{"require":{"laravel/framework":"^12.0"}}'); (self.proj / "AGENTS.md").write_text("# Team rules\nkeep\n")
        (self.proj / "opencode.json").write_text('{"model":"x/y","permission":{"edit":"ask"}}')
        P = ["--mode", "project", "--project-dir", str(self.proj), "--tools", "claude,opencode,antigravity"]
        r = sh([INSTALL, *P], self.home); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.proj / ".claude/skills").exists(), "project mode must not vendor skills by default"); self.assertIn('security_engineering_version: "0.1.0"', (self.proj / ".security-engineering/config.yaml").read_text())
        self.assertIn('framework: "laravel"', (self.proj / ".security-engineering/config.yaml").read_text())
        self.assertTrue((self.proj / "AGENTS.md").read_text().startswith("# Team rules\nkeep\n")); oc = json.loads((self.proj / "opencode.json").read_text())
        self.assertEqual(oc["model"], "x/y"); self.assertEqual(oc["permission"], {"edit": "ask"}); self.assertIn(".security-engineering/PROJECT_RULES.md", oc["instructions"])
        before = self.snap(self.proj); r = sh([INSTALL, *P], self.home); self.assertIn("0 action(s)", r.stdout); self.assertEqual(self.snap(self.proj), before)
        self.assertEqual(sh([VALIDATE, "--mode", "project", "--project-dir", str(self.proj)], self.home).returncode, 0)

    def test_project_pin_mismatch_refused_and_update_with_flag(self):
        P = ["--mode", "project", "--project-dir", str(self.proj), "--tools", "claude"]; sh([INSTALL, *P], self.home)
        c = self.proj / ".security-engineering/config.yaml"; c.write_text(c.read_text().replace('"0.1.0"', '"0.0.9"'))
        self.assertEqual(sh([INSTALL, *P], self.home).returncode, 4)
        self.assertEqual(sh([INSTALL, *P, "--allow-version-change"], self.home).returncode, 0); self.assertIn('"0.1.0"', c.read_text())

    def test_project_vendor_skills_and_uninstall_cleans_blocks(self):
        P = ["--mode", "project", "--project-dir", str(self.proj), "--tools", "claude", "--vendor-skills"]; (self.proj / "CLAUDE.md").write_text("# mine\n")
        sh([INSTALL, *P], self.home); self.assertTrue((self.proj / ".claude/skills/security-audit/SKILL.md").exists())
        sh([UNINSTALL, "--mode", "project", "--project-dir", str(self.proj)], self.home); self.assertEqual((self.proj / "CLAUDE.md").read_text().strip(), "# mine"); self.assertFalse((self.proj / ".claude/skills/security-audit").exists())

    def test_no_secrets_copied(self):
        sh([INSTALL, *self.G], self.home)
        for p in self.home.rglob("*"):
            if p.is_file() and p.suffix in (".md", ".json", ".yaml"): self.assertNotRegex(p.read_text(), r"(?i)(BEGIN [A-Z ]*PRIVATE KEY|sk_live_|AKIA[0-9A-Z]{16})")
