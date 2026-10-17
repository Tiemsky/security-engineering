"""Detection benchmark (work package C, minimal).

The module unit tests prove each module works on one case. This benchmark answers the question the
reviews actually cared about: *does the tool detect the vulnerabilities that are present, and does it
stay quiet on the versions where they are fixed?* Every scenario is driven through the real runner
(subprocess) against an in-process fixture app, in BOTH a deliberately VULNERABLE and a CORRECTED
state, and we measure:

  - detection rate      = true positives / vulnerable scenarios   (must be 1.0)
  - false-positive rate = false positives / corrected scenarios   (must be 0.0)
  - repeatability       = identical verdicts across repeated runs
  - evidence quality    = every FAIL carries non-empty, reproducible evidence

Only stdlib modules are exercised (no nuclei/ffuf/nmap/testssl/sqlmap), so the benchmark is
deterministic and needs no external binary or network. The fixture app is synthetic — no real user
data, no production system.
"""
import json, pathlib, shutil, subprocess, sys, tempfile, threading, unittest, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from common import ROOT

RUNNER = str(ROOT / "scripts" / "pentest-runner.py")
GATE = str(ROOT / "scripts" / "assessment-gate.py")

# A loopback + confirmed-local scope: the gate allows active modules via G05, and the target-identity
# preflight's fail-closed carve-out lets an unverified loopback target run (work package A).
LOCAL_SCOPE = """schema_version: "1.0.0"
target: {name: bench, framework: generic}
declared_environment: local
evidence:
  - {kind: env_config, detail: "APP_ENV=local in .env", supports: local}
authorization: {status: none}
"""


class BenchHandler(BaseHTTPRequestHandler):
    """One synthetic app serving every scenario. Class flags flip it between vulnerable and corrected;
    the benchmark sets them before launching the runner subprocess (same process as this server)."""
    cookie_secure = False      # cookies: False = missing Secure/HttpOnly/SameSite (vulnerable)
    cors_reflect = False       # CORS: True = reflects Origin + credentials (vulnerable)
    bola_secure = False        # BOLA: False = foreign object readable (vulnerable)
    bfla_secure = False        # BFLA: False = low-priv account reaches the admin endpoint (vulnerable)
    dash_requires_auth = True  # dashboard: False = readable with no credential (vulnerable/broken auth)
    dash_secure = True         # dashboard: when authed, False = low-priv allowed in

    def log_message(self, *a): pass

    def _send(self, code, body=b"", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        auth = self.headers.get("Authorization")
        path = self.path
        if path == "/" or path.startswith("/?"):
            extra = []
            if self.cookie_secure:
                extra.append(("Set-Cookie", "session=abc; Path=/; Secure; HttpOnly; SameSite=Lax"))
            else:
                extra.append(("Set-Cookie", "session=abc; Path=/"))
            origin = self.headers.get("Origin")
            if self.cors_reflect and origin:
                extra += [("Access-Control-Allow-Origin", origin), ("Access-Control-Allow-Credentials", "true")]
            return self._send(200, b"<html>ok</html>", extra)
        m = re.match(r"/api/orders/(\d+)", path)
        if m:
            oid = int(m.group(1))
            if not auth:
                return self._send(401, b"no auth")
            if oid == 101:
                return self._send(200, b"own order")           # the test account's OWN object
            return self._send(403 if self.bola_secure else 200, b"forbidden" if self.bola_secure else b"FOREIGN data")
        if path == "/admin/metrics":                            # BFLA / function-level authz
            if not auth:
                return self._send(401, b"no auth")
            return self._send(403 if self.bfla_secure else 200, b"forbidden" if self.bfla_secure else b"ADMIN metrics")
        if path == "/admin/dashboard":                          # dashboard exposure / broken auth (Horizon-shape)
            if not auth:
                return self._send(401 if self.dash_requires_auth else 200, b"no auth" if self.dash_requires_auth else b"DASHBOARD")
            return self._send(403 if self.dash_secure else 200, b"forbidden" if self.dash_secure else b"DASHBOARD")
        return self._send(404, b"nope")


# Each scenario: the module, how to make the app vulnerable vs corrected (flags), and any probes file.
# `fail_substr` must appear in a FAIL finding's control for the detection to count as a true positive
# (so one scenario's detection cannot be credited to another scenario's noise).
BOLA_PROBES = 'auth: {header: Authorization}\nprobes:\n  - {path: "/api/orders/{id}", own: [101], foreign: [102, 103]}\n'
BFLA_PROBES = 'auth: {header: Authorization}\nprivileged_paths: ["/admin/metrics"]\n'
DASH_PROBES = 'auth: {header: Authorization}\nprivileged_paths: ["/admin/dashboard"]\n'

SCENARIOS = [
    {"name": "cookie-security", "module": "cookie-flags", "probes": None, "fail_substr": "cookie",
     "vuln": {"cookie_secure": False}, "ok": {"cookie_secure": True}},
    {"name": "cors", "module": "cors", "probes": None, "fail_substr": "cors",
     "vuln": {"cors_reflect": True}, "ok": {"cors_reflect": False}},
    {"name": "bola-idor", "module": "idor-bola", "probes": BOLA_PROBES, "fail_substr": "idor-bola",
     "vuln": {"bola_secure": False}, "ok": {"bola_secure": True}},
    {"name": "bfla-privesc", "module": "priv-esc", "probes": BFLA_PROBES, "fail_substr": "priv-esc",
     "vuln": {"bfla_secure": False}, "ok": {"bfla_secure": True}},
    {"name": "dashboard-exposure", "module": "priv-esc", "probes": DASH_PROBES, "fail_substr": "priv-esc",
     "vuln": {"dash_requires_auth": False}, "ok": {"dash_requires_auth": True, "dash_secure": True}},
]

DEFAULTS = {"cookie_secure": False, "cors_reflect": False, "bola_secure": False,
            "bfla_secure": False, "dash_requires_auth": True, "dash_secure": True}
AUTH_MODULES = {"idor-bola", "priv-esc"}


class DetectionBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), BenchHandler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls): cls.srv.shutdown()

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="se-bench-")); self.addCleanup(shutil.rmtree, self.tmp, True)

    def _configure(self, overrides):
        for k, v in DEFAULTS.items():
            setattr(BenchHandler, k, overrides.get(k, v))

    def _run(self, scenario, state):
        """Configure the app for (scenario, state), run the real runner, return its findings list."""
        self._configure(scenario[state])
        out = self.tmp / f"{scenario['name']}-{state}"
        scope = self.tmp / "scope.yaml"; scope.write_text(LOCAL_SCOPE)
        args = ["run", str(scope), "--target", self.url + "/", "--only", scenario["module"], "--out", str(out)]
        if scenario["probes"]:
            pf = self.tmp / f"{scenario['name']}-probes.yaml"; pf.write_text(scenario["probes"])
            args += ["--probes", str(pf)]
        env = {"PATH": "/usr/bin:/bin", "SE_GATE": GATE}
        if scenario["module"] in AUTH_MODULES:
            env["SE_AUTH_HEADER"] = "Bearer bench-low-priv-token"
        r = subprocess.run([sys.executable, "-I", RUNNER, *args], capture_output=True, text=True, env=env)
        self.assertIn(r.returncode, (0, 1), f"{scenario['name']}/{state}: runner crashed\n{r.stderr}")
        rec = json.loads((out / "pentest-run.jsonl").read_text().splitlines()[0])
        self.assertEqual(rec["status"], "ran", f"{scenario['name']}/{state}: module did not run — {rec.get('reason')}")
        return rec["findings"]

    def _verdict(self, scenario, state):
        """Return ('detected'|'clean'|'not_tested', findings). 'detected' = a FAIL whose control matches
        this scenario; 'clean' = ran with no matching FAIL; 'not_tested' = could not test."""
        findings = self._run(scenario, state)
        fails = [f for f in findings if f["result"] == "FAIL" and scenario["fail_substr"] in f["control"]]
        if fails:
            return "detected", fails
        if all(f["result"] == "NOT_TESTED" for f in findings):
            return "not_tested", findings
        return "clean", findings

    def test_detection_and_false_positive_rates(self):
        tp = fp = 0
        rows = []
        for sc in SCENARIOS:
            vuln_verdict, vuln_fails = self._verdict(sc, "vuln")
            ok_verdict, ok_findings = self._verdict(sc, "ok")

            # True positive: the vulnerable version is detected, with real evidence.
            self.assertEqual(vuln_verdict, "detected",
                             f"{sc['name']}: vulnerable version NOT detected (false negative)")
            for f in vuln_fails:
                self.assertTrue(f.get("evidence"), f"{sc['name']}: FAIL has no evidence")
                self.assertTrue(all(isinstance(e, str) and e.strip() for e in f["evidence"]),
                                f"{sc['name']}: evidence is empty/blank")
            tp += 1

            # No false positive: the corrected version raises no matching FAIL.
            if ok_verdict == "detected":
                fp += 1
            self.assertEqual(ok_verdict, "clean",
                             f"{sc['name']}: corrected version wrongly flagged (false positive): {ok_findings}")

            rows.append((sc["name"], vuln_verdict, ok_verdict))

        n = len(SCENARIOS)
        detection_rate = tp / n
        false_positive_rate = fp / n
        print("\n=== detection benchmark ===")
        for name, v, o in rows:
            print(f"  {name:20s} vulnerable={v:10s} corrected={o}")
        print(f"  detection_rate={detection_rate:.2f}  false_positive_rate={false_positive_rate:.2f}  (n={n})")
        self.assertEqual(detection_rate, 1.0)
        self.assertEqual(false_positive_rate, 0.0)

    def test_repeatability(self):
        """Same inputs, same verdicts, run to run (3x) — a benchmark that flickers is not a benchmark."""
        baseline = None
        for _ in range(3):
            run = {sc["name"]: (self._verdict(sc, "vuln")[0], self._verdict(sc, "ok")[0]) for sc in SCENARIOS}
            if baseline is None:
                baseline = run
            else:
                self.assertEqual(run, baseline, "verdicts are not repeatable across runs")


if __name__ == "__main__":
    unittest.main()
