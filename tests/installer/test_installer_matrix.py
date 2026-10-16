"""Phase C matrix: ownership, upgrade, downgrade, uninstall safety, dry-run, odd paths. All in temp dirs; the real HOME is never touched."""
import json, os, pathlib, shutil, subprocess, tempfile, unittest
from common import ROOT

def sh(args, home, cwd=None):
    env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, env=env, cwd=cwd)

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="se-mx-")); self.home = self.tmp / "home"; self.home.mkdir(); self.proj = self.tmp / "proj"; self.proj.mkdir()
        self.I, self.U, self.V = (ROOT / "scripts" / n for n in ("install.sh", "uninstall.sh", "validate-installation.sh"))
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def snap(self, root): return {str(p.relative_to(root)): p.read_bytes() for p in pathlib.Path(root).rglob("*") if p.is_file()}

class OwnershipAndUninstall(Base):
    def test_preexisting_identical_file_is_never_removed(self):
        t = self.home / ".claude/agents/security-auditor.md"; t.parent.mkdir(parents=True); shutil.copy(ROOT / "adapters/claude-code/agents/security-auditor.md", t)
        r = sh([self.I, "--mode", "global", "--tools", "claude"], self.home); self.assertIn("adopted", r.stdout)
        sh([self.U, "--mode", "global"], self.home); self.assertTrue(t.exists(), "user's pre-existing file must survive uninstall")

    def test_uninstall_dry_run_changes_nothing(self):
        sh([self.I, "--mode", "global", "--tools", "claude,antigravity"], self.home); before = self.snap(self.home)
        r = sh([self.U, "--mode", "global", "--dry-run"], self.home); self.assertEqual(r.returncode, 0); self.assertEqual(self.snap(self.home), before)

    def test_uninstall_twice_is_safe(self):
        sh([self.I, "--mode", "global", "--tools", "claude"], self.home); sh([self.U, "--mode", "global"], self.home)
        r = sh([self.U, "--mode", "global"], self.home); self.assertEqual(r.returncode, 0); self.assertIn("nothing to uninstall", r.stdout)

    def test_project_uninstall_removes_only_what_it_created(self):
        (self.proj / "CLAUDE.md").write_text("# mine\n"); (self.proj / "opencode.json").write_text('{"model":"x/y"}')
        P = ["--mode", "project", "--project-dir", self.proj, "--tools", "claude,opencode"]
        sh([self.I, *P], self.home); sh([self.U, *P[:4]], self.home)
        self.assertEqual((self.proj / "CLAUDE.md").read_text().strip(), "# mine"); self.assertEqual(json.loads((self.proj / "opencode.json").read_text()), {"model": "x/y"})
        self.assertFalse((self.proj / "AGENTS.md").exists(), "AGENTS.md was created by the installer and is now empty -> removed")

    def test_project_created_files_are_cleaned(self):
        P = ["--mode", "project", "--project-dir", self.proj, "--tools", "claude,opencode"]; sh([self.I, *P], self.home); sh([self.U, *P[:4]], self.home)
        left = sorted(str(p.relative_to(self.proj)) for p in self.proj.rglob("*") if p.is_file())
        self.assertEqual(left, [".security-engineering/PROJECT_RULES.md", ".security-engineering/config.yaml"], "only the documented user-owned files remain")

    def test_global_and_project_manifests_are_independent(self):
        sh([self.I, "--mode", "global", "--tools", "claude"], self.home); sh([self.I, "--mode", "project", "--project-dir", self.proj, "--tools", "claude"], self.home)
        sh([self.U, "--mode", "project", "--project-dir", self.proj], self.home)
        self.assertTrue((self.home / ".claude/agents/security-auditor.md").exists()); self.assertEqual(sh([self.V, "--mode", "global"], self.home).returncode, 0)

    def test_foreign_skill_dir_with_same_name_conflicts(self):
        d = self.home / ".claude/skills/security-audit"; d.mkdir(parents=True); (d / "SKILL.md").write_text("---\nname: security-audit\n---\nuser skill\n")
        r = sh([self.I, "--mode", "global", "--tools", "claude"], self.home); self.assertEqual(r.returncode, 3); self.assertEqual((d / "SKILL.md").read_text().splitlines()[-1], "user skill")

    def test_uninstall_never_prunes_user_or_tool_root_dirs(self):
        (self.home / ".claude/commands").mkdir(parents=True); (self.home / "keepme").mkdir()
        sh([self.I, "--mode", "global", "--tools", "claude"], self.home); sh([self.U, "--mode", "global"], self.home)
        self.assertTrue((self.home / ".claude/commands").is_dir()); self.assertTrue((self.home / ".claude").is_dir()); self.assertTrue((self.home / "keepme").is_dir())
        self.assertFalse((self.home / ".claude/skills/security-audit").exists())

class UpgradePath(Base):
    def fake_old_source(self, version="0.0.9"):
        src = self.tmp / "old-src"; shutil.copytree(ROOT, src, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__")); (src / "VERSION").write_text(version + "\n")
        sk = src / "skills/security-audit/SKILL.md"; sk.write_text(sk.read_text() + "\n<!-- old release marker -->\n"); return src

    def test_upgrade_updates_unmodified_files_and_validates(self):
        old = self.fake_old_source(); self.assertEqual(sh([old / "scripts/install.sh", "--mode", "global", "--tools", "claude"], self.home).returncode, 0)
        f = self.home / ".claude/skills/security-audit/SKILL.md"; self.assertIn("old release marker", f.read_text())
        r = sh([self.I, "--mode", "global", "--tools", "claude"], self.home); self.assertEqual(r.returncode, 0, r.stdout); self.assertIn("upgrading 0.0.9 -> 0.1.0", r.stdout)
        self.assertNotIn("old release marker", f.read_text()); self.assertEqual(json.loads((self.home / ".security-engineering/manifest-global.json").read_text())["version"], "0.1.0")
        self.assertEqual(sh([self.V, "--mode", "global"], self.home).returncode, 0)

    def test_upgrade_keeps_user_modified_file_and_reports_conflict(self):
        old = self.fake_old_source(); sh([old / "scripts/install.sh", "--mode", "global", "--tools", "claude"], self.home)
        f = self.home / ".claude/skills/security-audit/SKILL.md"; f.write_text(f.read_text() + "\nUSER EDIT\n")
        r = sh([self.I, "--mode", "global", "--tools", "claude"], self.home); self.assertEqual(r.returncode, 3); self.assertIn("USER EDIT", f.read_text())
        r = sh([self.I, "--mode", "global", "--tools", "claude", "--force"], self.home); self.assertEqual(r.returncode, 0)
        self.assertEqual(len(list(f.parent.glob("SKILL.md.bak.*"))), 1); self.assertIn("USER EDIT", list(f.parent.glob("SKILL.md.bak.*"))[0].read_text())

    def test_downgrade_refused_then_allowed_and_project_pin(self):
        sh([self.I, "--mode", "global", "--tools", "claude"], self.home); old = self.fake_old_source("0.0.5")
        r = sh([old / "scripts/install.sh", "--mode", "global", "--tools", "claude"], self.home); self.assertEqual(r.returncode, 4)
        sh([self.I, "--mode", "project", "--project-dir", self.proj, "--tools", "claude"], self.home)
        r = sh([old / "scripts/install.sh", "--mode", "project", "--project-dir", self.proj, "--tools", "claude"], self.home); self.assertEqual(r.returncode, 4, "pin 0.1.0 vs source 0.0.5 refused")

class Robustness(Base):
    def test_paths_with_spaces(self):
        home = self.tmp / "my home dir"; home.mkdir(); proj = self.tmp / "my project (test)"; proj.mkdir()
        self.assertEqual(sh([self.I, "--mode", "global", "--tools", "claude,antigravity"], home).returncode, 0); self.assertEqual(sh([self.V, "--mode", "global"], home).returncode, 0)
        P = ["--mode", "project", "--project-dir", proj, "--tools", "claude,opencode,antigravity", "--vendor-skills"]
        self.assertEqual(sh([self.I, *P], home).returncode, 0); self.assertEqual(sh([self.V, *P[:4]], home).returncode, 0)
        self.assertEqual(sh([self.U, *P[:4]], home).returncode, 0)

    def test_project_dry_run_writes_nothing(self):
        r = sh([self.I, "--mode", "project", "--project-dir", self.proj, "--tools", "claude,opencode,antigravity", "--vendor-skills", "--dry-run"], self.home)
        self.assertEqual(r.returncode, 0); self.assertEqual(self.snap(self.proj), {}); self.assertEqual(self.snap(self.home), {})

    def test_usage_errors(self):
        self.assertEqual(sh([self.I], self.home).returncode, 2); self.assertEqual(sh([self.I, "--mode", "global", "--bogus"], self.home).returncode, 2)
        self.assertNotEqual(sh([self.I, "--mode", "project"], self.home).returncode, 0)

    def test_installer_never_touches_permission_settings(self):
        (self.home / ".claude").mkdir(); s = self.home / ".claude/settings.json"; s.write_text('{"permissions":{"allow":["Bash(*)"],"deny":[]},"x":1}')
        (self.home / ".gemini/config").mkdir(parents=True); g = self.home / ".gemini/config/config.json"; g.write_text('{"userSettings":{"toolPermission":"always-proceed"}}')
        sh([self.I, "--mode", "global", "--tools", "claude,antigravity"], self.home)
        self.assertEqual(s.read_text(), '{"permissions":{"allow":["Bash(*)"],"deny":[]},"x":1}'); self.assertEqual(g.read_text(), '{"userSettings":{"toolPermission":"always-proceed"}}')
