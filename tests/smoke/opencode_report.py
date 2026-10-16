"""Parses `opencode agent list` / `opencode debug skill` output into effective permissions (last matching rule wins)."""
import json, re, sys
d = sys.argv[1]
t = open(f"{d}/opencode-agent-list.txt").read(); parts = re.split(r"^(\S+) \((primary|subagent|all)\)\n", t, flags=re.M)
def eff(rules, perm): return ([x["action"] for x in rules if x["permission"] == perm and x["pattern"] == "*"] or ["(none)"])[-1]
for i in range(1, len(parts), 3):
    if parts[i].startswith("security-"):
        r = json.loads(parts[i + 2])
        print(f"{parts[i]:24} mode={parts[i+1]:9} edit={eff(r,'edit'):5} bash(*)={eff(r,'bash'):5} webfetch={eff(r,'webfetch'):5} task={eff(r,'task')}")
print("skills:", sorted(x["name"] for x in json.load(open(f"{d}/opencode-skills.json")) if x["name"] != "customize-opencode"))
