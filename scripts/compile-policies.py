#!/usr/bin/env python3
"""Compile policies/*.yaml to JSON so runtimes (PHP/TS) need no YAML parser.
Usage: compile-policies.py [OUT_DIR]   (default: policies/compiled)"""
import json, sys, pathlib, yaml
ROOT = pathlib.Path(__file__).resolve().parent.parent
out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "policies/compiled"
out.mkdir(parents=True, exist_ok=True)
for f in sorted((ROOT / "policies").glob("*.yaml")):
    (out / (f.stem + ".json")).write_text(json.dumps(yaml.safe_load(f.read_text()), indent=2) + "\n")
print(f"compiled to {out}")
