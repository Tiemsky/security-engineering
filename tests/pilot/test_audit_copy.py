import os, pathlib, shutil, subprocess, tempfile, unittest
from common import ROOT

SCRIPT = str(ROOT / "scripts" / "audit-copy.sh")
# secret-shaped values are assembled at run time so this file itself holds no secret-shaped literal
AWS = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
GOOGLE = "GOC" + "SPX-" + "a" * 28

def run(*a): return subprocess.run([SCRIPT, *a], capture_output=True, text=True)
def git(repo, *a): return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True,
    env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

class AuditCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="se-copy-")); self.repo = self.tmp / "my app"; self.out = self.tmp / "out"
        self.repo.mkdir(); git(self.repo, "init", "-q")
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def w(self, rel, content="x\n"):
        p = self.repo / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content); return p
    def commit(self): git(self.repo, "add", "-A"); git(self.repo, "commit", "-q", "-m", "c")
    def status(self): return git(self.repo, "status", "--porcelain", "--ignored").stdout

    def clean_repo(self):
        self.w("app/Http/Controller.php", "<?php // code\n"); self.w(".env.example", "APP_KEY=\n"); self.commit()

    def test_clean_repo_copies_committed_state_exit_0(self):
        self.clean_repo(); r = run("--repo", str(self.repo), "--out", str(self.out))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.out / "app/Http/Controller.php").exists()); self.assertTrue((self.out / ".env.example").exists())
        self.assertFalse((self.out / ".git").exists()); self.assertIn("excluded: 0", (self.out / "AUDIT-COPY.txt").read_text())

    def test_export_ignore_does_not_drop_files(self):   # pilot defect H1
        self.w(".gitattributes", "/.github export-ignore\n"); self.w(".github/workflows/ci.yml", "name: ci\n"); self.commit()
        self.assertEqual(run("--repo", str(self.repo), "--out", str(self.out)).returncode, 0)
        self.assertTrue((self.out / ".github/workflows/ci.yml").exists())

    def test_uncommitted_changes_are_not_copied(self):
        self.clean_repo(); (self.repo / "app/Http/Controller.php").write_text("<?php // MODIFIED\n"); self.w("untracked.txt")
        before = self.status(); self.assertEqual(run("--repo", str(self.repo), "--out", str(self.out)).returncode, 0)
        self.assertIn("// code", (self.out / "app/Http/Controller.php").read_text()); self.assertFalse((self.out / "untracked.txt").exists())
        self.assertEqual(before, self.status(), "source repository must be untouched")

    def test_secret_files_excluded_by_name_and_content_exit_5_no_values_printed(self):
        self.clean_repo(); self.w(".env.testing", "KEY=abc\n"); self.w("certs/server.pem", "pem\n")
        self.w("config/aws.php", f"<?php return ['k' => '{AWS}'];\n"); self.w("config/g.php", f"'{GOOGLE}'\n"); self.commit()
        r = run("--repo", str(self.repo), "--out", str(self.out)); self.assertEqual(r.returncode, 5, r.stderr)
        for gone in (".env.testing", "certs/server.pem", "config/aws.php", "config/g.php"): self.assertFalse((self.out / gone).exists(), gone)
        self.assertTrue((self.out / "app/Http/Controller.php").exists())
        report = (self.out / "AUDIT-COPY.txt").read_text()
        for needle in (".env.testing", "certs/server.pem", "aws-access-key", "google-oauth-secret"): self.assertIn(needle, report)
        for secret in (AWS, GOOGLE): self.assertNotIn(secret, report + r.stdout + r.stderr)

    def test_symlinks_are_removed(self):
        self.clean_repo(); os.symlink("/etc/passwd", self.repo / "link"); self.commit()
        run("--repo", str(self.repo), "--out", str(self.out)); self.assertFalse((self.out / "link").exists() or (self.out / "link").is_symlink())
        self.assertIn("symlink", (self.out / "AUDIT-COPY.txt").read_text())

    def test_refuses_out_inside_repo_or_non_empty_or_unknown_ref(self):
        self.clean_repo()
        self.assertEqual(run("--repo", str(self.repo), "--out", str(self.repo / "inside")).returncode, 1)
        self.out.mkdir(); (self.out / "f").write_text("x"); self.assertEqual(run("--repo", str(self.repo), "--out", str(self.out)).returncode, 1)
        shutil.rmtree(self.out); self.assertEqual(run("--repo", str(self.repo), "--out", str(self.out), "--ref", "nope").returncode, 1)

    def test_dry_run_writes_nothing(self):
        self.clean_repo(); self.w(".env", "a=b\n"); self.commit()
        r = run("--repo", str(self.repo), "--out", str(self.out), "--dry-run"); self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(".env", r.stdout); self.assertEqual(list(self.out.iterdir()), [])

if __name__ == "__main__": unittest.main()

class ExtractReportJsonTests(unittest.TestCase):
    EXTRACT = str(ROOT / "scripts" / "extract-report-json.py")
    def run_on(self, text):
        d = pathlib.Path(tempfile.mkdtemp(prefix="se-ext-")); self.addCleanup(shutil.rmtree, d, True)
        (d / "r.md").write_text(text); return subprocess.run(["python3", "-I", self.EXTRACT, str(d / "r.md")], capture_output=True, text=True)
    def test_takes_last_block(self):
        r = self.run_on('x\n```json\n{"a": 1}\n```\ntext\n```json\n{"b": 2}\n```\n'); self.assertEqual(r.returncode, 0); self.assertIn('"b"', r.stdout); self.assertNotIn('"a"', r.stdout)
    def test_fixture_roundtrip_passes_the_gate(self):
        fx = (ROOT / "tests/fixtures/assessment/report-code-only.json").read_text()
        r = self.run_on(f"# report\n```json\n{fx}\n```\n"); self.assertEqual(r.returncode, 0)
        d = pathlib.Path(tempfile.mkdtemp(prefix="se-ext-")); self.addCleanup(shutil.rmtree, d, True); (d / "m.json").write_text(r.stdout)
        g = subprocess.run(["python3", "-I", str(ROOT / "scripts/assessment-gate.py"), "validate-report", str(d / "m.json")], capture_output=True, text=True)
        self.assertEqual(g.returncode, 0, g.stdout)
    def test_missing_or_invalid_block_fails(self):
        self.assertEqual(self.run_on("no block").returncode, 1); self.assertEqual(self.run_on("```json\n{bad\n```\n").returncode, 1)
