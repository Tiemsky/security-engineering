#!/usr/bin/env python3
"""Extract the LAST fenced ```json block of an audit report (the assessment matrix) so that
`assessment-gate.py validate-report` can check it.  Usage: extract-report-json.py REPORT.md [OUT.json]
Exit 0 ok · 1 no JSON block or invalid JSON.  Reads REPORT.md only; writes OUT.json (or stdout)."""
import json, re, sys

def main(argv):
    if not 2 <= len(argv) <= 3: print(__doc__.split("\n")[1], file=sys.stderr); return 2
    blocks = re.findall(r"```json\s*\n(.*?)\n```", open(argv[1], encoding="utf-8").read(), re.S)
    if not blocks: print("no ```json block found", file=sys.stderr); return 1
    try: data = json.loads(blocks[-1])
    except ValueError as e: print(f"last json block is invalid: {e}", file=sys.stderr); return 1
    out = json.dumps(data, indent=2, ensure_ascii=False)
    if len(argv) == 3: open(argv[2], "w", encoding="utf-8").write(out + "\n")
    else: print(out)
    return 0

if __name__ == "__main__": sys.exit(main(sys.argv))
