#!/usr/bin/env bash
# Replays the shared scenarios through a REAL Laravel app inside Docker (php 8.4 + composer; no host PHP extensions needed).
# Usage: run_laravel.sh <outdir>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; OUT="$(mkdir -p "$1" && cd "$1" && pwd)"
docker build -q -t se-laravel-it -f "$ROOT/tests/integration/docker/Dockerfile.laravel" "$ROOT/tests/integration/docker" >/dev/null
docker run --rm -v "$ROOT:/repo:ro" -v "$OUT:/out" se-laravel-it sh -ec '
  cp -r /repo/adapters-runtime/laravel/src vendor/security-engineering-src
  mkdir vendor/security-engineering-examples && cp /repo/adapters-runtime/laravel/examples/* vendor/security-engineering-examples/
  php -r "\$f=\"composer.json\";\$j=json_decode(file_get_contents(\$f),true);\$j[\"autoload\"][\"psr-4\"][\"SecurityEngineering\\\\\"]=\"vendor/security-engineering-src/\";file_put_contents(\$f,json_encode(\$j));"
  composer dump-autoload -q
  python3 /repo/scripts/compile-policies.py /tmp/policies >/dev/null
  php -v | head -1; php artisan --version
  for f in /repo/tests/fixtures/scenarios/*.json; do n=$(basename $f .json)
    SE_POLICY_DIR=/tmp/policies php /repo/adapters-runtime/laravel/tests/run_scenario.php $f /out/laravel-$n.jsonl && echo "laravel ok: $n"; done'
