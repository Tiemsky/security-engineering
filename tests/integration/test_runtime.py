"""Executes the shared scenarios on real Laravel + real NestJS inside Docker, then validates and cross-compares.
Skipped (explicitly) when Docker is unavailable unless SE_REQUIRE_DOCKER=1."""
import os, shutil, subprocess, tempfile, unittest
from common import ROOT

DOCKER = not os.environ.get("SE_SKIP_DOCKER") and shutil.which("docker") and subprocess.run(["docker", "info"], capture_output=True).returncode == 0

@unittest.skipUnless(DOCKER or os.environ.get("SE_REQUIRE_DOCKER"), "docker not available: runtime integration NOT executed")
class RuntimeIntegration(unittest.TestCase):
    def test_laravel_and_nestjs_conform_and_agree(self):
        out = tempfile.mkdtemp(prefix="se-it-")
        for fw in ("laravel", "nestjs"):
            r = subprocess.run([str(ROOT / f"tests/integration/run_{fw}.sh"), out], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        r = subprocess.run(["python3", str(ROOT / "tests/integration/compare.py"), out, "laravel", "nestjs"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:]); print(r.stdout)
