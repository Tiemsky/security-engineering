"""PowerShell installer checks, run with pwsh (host) or the official PowerShell Docker image. NOTE: executes PowerShell 7 on Linux;
native Windows PowerShell 5.1 is NOT covered (unverified)."""
import json, os, pathlib, shutil, subprocess, tempfile, unittest
from common import ROOT

PWSH = shutil.which("pwsh")
DOCKER = not os.environ.get("SE_SKIP_DOCKER") and shutil.which("docker") and subprocess.run(["docker", "info"], capture_output=True).returncode == 0

def run(tmp, script):
    if PWSH: cmd = [PWSH, "-NoProfile", "-c", script.replace("/repo", str(ROOT)).replace("/t", str(tmp))]; env = {**os.environ, "HOME": f"{tmp}/home"}
    else: cmd = ["docker", "run", "--rm", "-v", f"{ROOT}:/repo:ro", "-v", f"{tmp}:/t", "-e", "HOME=/t/home", "mcr.microsoft.com/powershell:7.4-ubuntu-22.04", "pwsh", "-NoProfile", "-c", script]; env = None
    return subprocess.run(cmd, capture_output=True, text=True, env=env)

@unittest.skipUnless(PWSH or DOCKER, "neither pwsh nor docker available: install.ps1 NOT executed")
class PowerShellInstaller(unittest.TestCase):
    def test_project_install_idempotent_and_preserves_config(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="se-ps-")); (tmp / "home").mkdir(); proj = tmp / "proj"; proj.mkdir()
        (proj / "opencode.json").write_text('{"keep":"me"}'); (proj / "AGENTS.md").write_text("# mine\n")
        try:
            base = "/repo/scripts/install.ps1 -Mode project -ProjectDir /t/proj -Tools claude,opencode"
            r = run(tmp, base + " -DryRun | Select-Object -Last 1"); self.assertIn("dry-run", r.stdout, r.stderr); self.assertFalse((proj / ".security-engineering").exists())
            r = run(tmp, base + " | Select-Object -Last 1"); self.assertIn("conflict(s)", r.stdout, r.stdout + r.stderr)
            self.assertEqual(json.loads((proj / "opencode.json").read_text())["keep"], "me"); self.assertTrue((proj / "AGENTS.md").read_text().startswith("# mine"))
            r = run(tmp, base + " | Select-Object -Last 1"); self.assertIn("0 action(s)", r.stdout, r.stdout + r.stderr)
            for f in ("assessment-gate.py", "minischema.py"): self.assertTrue((proj / ".security-engineering/shared/scripts" / f).is_file(), f)   # gate shipped by install.ps1 too
        finally: shutil.rmtree(tmp, ignore_errors=True)

    def test_uninstall_restores_original_state_and_keeps_user_files(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="se-ps-")); (tmp / "home").mkdir(); proj = tmp / "my proj"; proj.mkdir()
        (proj / "opencode.json").write_text('{"keep":"me"}'); (proj / "CLAUDE.md").write_text("# mine\n")
        pre = proj / ".claude/agents"; pre.mkdir(parents=True); shutil.copy(ROOT / "adapters/claude-code/agents/security-auditor.md", pre / "security-auditor.md")
        try:
            args = "-Mode project -ProjectDir '/t/my proj' -Tools claude,opencode"
            run(tmp, f"/repo/scripts/install.ps1 {args} | Out-Null")
            r = run(tmp, f"/repo/scripts/uninstall.ps1 -Mode project -ProjectDir '/t/my proj' | Select-Object -Last 1"); self.assertIn("done:", r.stdout, r.stdout + r.stderr)
            self.assertEqual(json.loads((proj / "opencode.json").read_text()), {"keep": "me"}); self.assertEqual((proj / "CLAUDE.md").read_text().strip(), "# mine")
            self.assertTrue((pre / "security-auditor.md").exists(), "pre-existing identical file must survive"); self.assertFalse((proj / ".claude/agents/security-reviewer.md").exists())
            self.assertFalse((proj / ".security-engineering/manifest-project.json").exists())
        finally: shutil.rmtree(tmp, ignore_errors=True)
