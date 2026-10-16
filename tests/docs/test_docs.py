"""Documentation checks for the user-facing guides (links, referenced paths, status vocabulary, invented commands).
Static only: it proves the documents are internally consistent with the repository, NOT that the described commands work."""
import re, unittest, pathlib
from common import ROOT, SKILLS
import yaml

DOCS = ["USER-GUIDE.md", "COMMAND-REFERENCE.md", "OWASP-COVERAGE.md", "EXAMPLES.md"]
COVERAGE = {"IMPLEMENTED_AND_TESTED", "IMPLEMENTED_NOT_VERIFIED", "GUIDANCE_ONLY", "PARTIAL", "MISSING", "NOT_APPLICABLE"}
CMD_LABELS = {"EXECUTED", "TESTED", "DOCUMENTED", "NOT-VERIFIED"}
AGENTS = {"security-orchestrator", "security-architect", "security-auditor", "security-implementer", "security-reviewer"}
TOP = ("skills/", "agents/", "adapters/", "adapters-runtime/", "core/", "contracts/", "policies/", "scripts/", "tests/", "docs/", ".github/")
ALLOWED_MISSING = {"policies/compiled"}          # default OUTPUT dir of compile-policies.py, created on demand
SLASH_OK = {"/agents"}                          # the only slash command mentioned (DOCUMENTED, not run)
FILE_EXT = {"yaml", "md", "json", "sh", "py", "ts", "php", "ps1", "yml", "txt", "js"}

def text(name): return (ROOT / "docs" / name).read_text()
def ticks(t): return re.findall(r"`([^`\n]+)`", t)
def slug(h):
    h = re.sub(r"[`*]", "", h.strip().lower())
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", h))
def tables(t):
    """yield (header_cells, [row_cells]) for each markdown table"""
    lines, i = t.splitlines(), 0
    while i < len(lines):
        if lines[i].startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            cells = lambda l: [c.strip() for c in l.strip().strip("|").split("|")]
            hdr, rows, i = cells(lines[i]), [], i + 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells(lines[i])); i += 1
            yield hdr, rows
        else: i += 1

class DocTests(unittest.TestCase):
    def test_documents_exist_and_readme_links_them(self):
        readme = (ROOT / "README.md").read_text()
        for d in DOCS:
            self.assertTrue((ROOT / "docs" / d).is_file(), d)
            self.assertIn(f"docs/{d}", readme, f"README.md must link docs/{d}")

    def test_relative_links_and_anchors_resolve(self):
        for d in DOCS + ["../README.md"]:
            p = (ROOT / "docs" / d).resolve()
            for target in re.findall(r"\]\(([^)\s]+)\)", p.read_text()):
                if re.match(r"^[a-z]+://", target) or target.startswith("mailto:"): continue
                path, _, anchor = target.partition("#")
                dest = (p.parent / path).resolve() if path else p
                self.assertTrue(dest.exists(), f"{d}: broken link {target}")
                if anchor and dest.suffix == ".md":
                    slugs = {slug(m) for m in re.findall(r"^#+\s+(.*)$", dest.read_text(), re.M)}
                    self.assertIn(anchor, slugs, f"{d}: broken anchor {target}")

    def test_referenced_repository_paths_exist(self):
        for d in DOCS:
            for tok in ticks(text(d)):
                first = tok.split()[0] if tok.split() else tok
                first = first.rstrip(".,;:)")
                if not first.startswith(TOP) or any(c in first for c in "*<>{}…$") or first in ALLOWED_MISSING: continue
                self.assertTrue((ROOT / first).exists(), f"{d}: `{tok}` -> {first} does not exist")

    def test_only_real_agents_and_skills_are_named(self):
        known = AGENTS | set(SKILLS)
        for d in DOCS:
            for tok in ticks(text(d)):
                for name in re.findall(r"\bsecurity-[a-z]+\b", tok):
                    if re.fullmatch(r"security-[a-z]+", tok):
                        self.assertIn(tok, known, f"{d}: unknown agent/skill `{tok}`")

    def test_no_invented_slash_commands(self):
        for d in DOCS:
            for tok in ticks(text(d)):
                if re.fullmatch(r"/[a-z][a-z-]*", tok):
                    self.assertIn(tok, SLASH_OK, f"{d}: slash command {tok} is not verified")

    def test_coverage_statuses_are_from_the_fixed_vocabulary(self):
        t = text("OWASP-COVERAGE.md"); seen = 0
        for hdr, rows in tables(t):
            if "Status" not in hdr or len(hdr) < 3: continue     # skip the legend table (Status | Meaning)
            col = hdr.index("Status")
            for r in rows:
                m = re.match(r"`([A-Z_]+)`", r[col])
                self.assertTrue(m and m.group(1) in COVERAGE, f"bad status cell: {r[0]} -> {r[col]!r}"); seen += 1
        self.assertGreaterEqual(seen, 60)
        for tok in re.findall(r"`([A-Z]+(?:_[A-Z]+)+)`", t):     # any UPPER_SNAKE token must be a valid status
            self.assertIn(tok, COVERAGE | {"APP_DEBUG", "PROJECT_RULES"}, tok)

    def test_coverage_cites_real_scenarios_and_rules(self):
        scen = {p.stem for p in (ROOT / "tests/fixtures/scenarios").glob("*.json")}
        rules = {r["id"] for r in yaml.safe_load((ROOT / "policies/detection-rules.yaml").read_text())["rules"]}
        t = text("OWASP-COVERAGE.md")
        for hdr, rows in tables(t):
            for r in rows:
                for cell in r:
                    if "scenario" in cell.lower():
                        for tok in ticks(cell):
                            if re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)+", tok) and tok not in SKILLS and tok not in AGENTS:
                                self.assertIn(tok, scen, f"unknown scenario `{tok}` in row {r[0]}")
        for tok in ticks(t):
            if re.fullmatch(r"[a-z]+\.[a-z0-9-]+", tok) and tok.rsplit(".", 1)[1] not in FILE_EXT:
                self.assertIn(tok, rules | {"x.request-rate"}, f"unknown rule id `{tok}`")

    def test_coverage_matrix_has_every_standard_entry(self):
        t = text("OWASP-COVERAGE.md")
        for i in range(1, 11):
            self.assertIn(f"A{i:02d}:2025", t); self.assertIn(f"API{i}:2023", t)
        for i in range(1, 18): self.assertRegex(t, rf"\|\s*V{i}\s")
        for c in ("INFO", "CONF", "IDNT", "ATHN", "ATHZ", "SESS", "INPV", "ERRH", "CRYP", "BUSL", "CLNT", "APIT"):
            self.assertIn(f"WSTG-{c}", t)

    def test_no_full_compliance_claim(self):
        for d in DOCS:
            self.assertNotRegex(text(d).lower(), r"(fully|100%)\s+(owasp\s+)?compliant|owasp[- ]compliant\b(?!.*not)", d)

    def test_command_reference_rows_carry_a_status_label(self):
        t = text("COMMAND-REFERENCE.md"); seen = 0
        for hdr, rows in tables(t):
            if hdr[-1] != "Status": continue
            for r in rows:
                self.assertTrue(any(re.search(rf"\b{l}\b", r[-1]) for l in CMD_LABELS), f"no status label: {r[0]}"); seen += 1
        self.assertGreaterEqual(seen, 30)

    def test_documented_scripts_support_the_flags_the_docs_use(self):
        t = text("COMMAND-REFERENCE.md")
        src = (ROOT / "scripts/install.sh").read_text()
        for flag in set(re.findall(r"`scripts/install\.sh[^`]*`", t)):
            for f in re.findall(r"(--[a-z-]+)", flag): self.assertIn(f, src, f"install.sh has no {f}")
        un = (ROOT / "scripts/uninstall.sh").read_text()
        for flag in set(re.findall(r"`scripts/uninstall\.sh[^`]*`", t)):
            for f in re.findall(r"(--[a-z-]+)", flag): self.assertIn(f, un, f"uninstall.sh has no {f}")

if __name__ == "__main__": unittest.main()
