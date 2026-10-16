import json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/lib"))
import yaml

def frontmatter(path):
    t = pathlib.Path(path).read_text()
    assert t.startswith("---\n"), f"{path}: no frontmatter"
    return yaml.safe_load(t.split("---\n", 2)[1]), t.split("---\n", 2)[2]

SKILLS = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
