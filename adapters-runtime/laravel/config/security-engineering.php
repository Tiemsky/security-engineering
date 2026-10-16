<?php
return [
    'policy_dir' => env('SE_POLICY_DIR'),   // compiled policy JSON (scripts/compile-policies.py)
    'mode' => null,                          // null = per-rule mode (observe by default); 'observe'|'alert'|'enforce' overrides all
    'trusted_proxies' => [],                 // CIDRs of YOUR proxies/CDN; empty = never trust X-Forwarded-For
    'allowlist_cidrs' => [],                 // approved infrastructure only
];
