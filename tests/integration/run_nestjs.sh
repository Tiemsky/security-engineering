#!/usr/bin/env bash
# Replays the shared scenarios through a REAL NestJS app inside Docker. Usage: run_nestjs.sh <outdir>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; OUT="$(mkdir -p "$1" && cd "$1" && pwd)"
docker build -q -t se-nest-it -f "$ROOT/tests/integration/docker/Dockerfile.nestjs" "$ROOT/tests/integration/docker" >/dev/null
docker run --rm -v "$ROOT:/repo:ro" -v "$OUT:/out" se-nest-it sh -ec '
  cp -r /repo/adapters-runtime/nestjs/src /repo/adapters-runtime/nestjs/examples /repo/adapters-runtime/nestjs/tests . 
  printf "{\"compilerOptions\":{\"experimentalDecorators\":true,\"target\":\"ES2022\",\"module\":\"commonjs\",\"strict\":false,\"skipLibCheck\":true,\"esModuleInterop\":true}}" > tsconfig.json
  python3 /repo/scripts/compile-policies.py /tmp/policies >/dev/null
  node -v; node -e "console.log(\"nest core\", require(\"@nestjs/core/package.json\").version)"
  for f in /repo/tests/fixtures/scenarios/*.json; do n=$(basename $f .json)
    SE_POLICY_DIR=/tmp/policies npx tsx tests/run-scenario.ts $f /out/nestjs-$n.jsonl && echo "nestjs ok: $n"; done'
