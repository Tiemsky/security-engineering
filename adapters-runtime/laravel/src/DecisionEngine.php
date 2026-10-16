<?php
namespace SecurityEngineering;

/**
 * Deterministic rule engine. Pure function of (policies, event stream, clock): no LLM, no I/O besides the injected sink.
 * Default mode is observe: decisions are recorded, nothing is enforced.
 *
 * Hardening (v0.1.0 validation, Phase D):
 *  - malformed/unknown signals are rejected (counted, one rate-limited system_health event per reason), never counted toward rules
 *  - sink failures never propagate to the caller (dropped counter)
 *  - duplicate suppression emits ONE skipped_duplicate outcome per key, then counts silently (no log amplification under flood)
 *  - a FAILED action releases its idempotency key so the next qualifying signal retries it (max MAX_ATTEMPTS), no partial state is left behind
 *  - only EXECUTABLE actions ever run; account_lock / session_revocation / challenge are never executed (manual_review + pending_approval)
 *  - in-memory windows, idempotency keys and shared-IP records are pruned in sweep() and capped (bounded memory)
 */
final class DecisionEngine
{
    private const SIGNALS = [
        'failed_logins_per_ip_distinct_accounts' => ['login_failed', 'ip', 'account'],
        'failed_logins_per_account_distinct_ips' => ['login_failed', 'account', 'ip'],
        'otp_failures_per_identifier'            => ['otp_failed', 'account', null],
        'sequential_id_walk'                     => ['id_deny', 'token', 'object_id'],
        'not_found_burst'                        => ['not_found', 'ip', 'path'],
        'honeypot_hit'                           => ['honeypot', 'ip', null],
        'signature_failures_per_source'          => ['signature_failed', 'ip', null],
        'request_rate_per_key'                   => ['request', 'ip', null],
    ];
    private const KINDS = [   // signal kind => required string fields
        'login_failed' => ['ip', 'account'], 'login_success' => ['ip', 'account'], 'otp_failed' => ['account'], 'id_deny' => ['token', 'object_id'],
        'not_found' => ['ip', 'path'], 'honeypot' => ['ip'], 'signature_failed' => ['ip'], 'request' => ['ip'],
    ];
    public const EXECUTABLE = ['observe', 'alert', 'rate_limit', 'temp_ip_block', 'manual_review'];
    private const NIL_ID = '00000000-0000-4000-8000-000000000000';
    private const MAX_ATTEMPTS = 3;
    private const MAX_WINDOW_ENTRIES = 10000;
    private const MAX_WINDOWS = 50000;
    private const HEALTH_INTERVAL = 60;
    private const LEGIT_TTL = 86400;

    private array $windows = [];   // rule|group => ['w'=>int,'e'=>[[ts, distinct], ...]]
    private array $legit = [];     // ip => [account => ts]
    private array $seen = [];      // idempotency key => expiry ts
    private array $dupNotified = [];
    private array $attempts = [];
    private array $active = [];    // scopeKey => ['expires','key','action','decision_id']
    private array $lastHealth = [];
    public bool $storeFailure = false; // test hook: simulate action-store outage
    public int $rejected = 0, $dropped = 0, $duplicatesSuppressed = 0;

    public function __construct(
        private array $rules, private array $defaults, private array $actions,
        private EventFactory $events, private Sink $sink, private \Closure $clock, private ?string $modeOverride = null,
    ) {}

    /** Feed one signal event ['kind','ip','account','token','path','object_id','request_id']. Returns emitted events. */
    public function observe(mixed $e): array
    {
        $now = ($this->clock)(); $emitted = [];
        if (($reason = $this->validate($e)) !== null) return $this->reject($reason, $now);
        $e['ip'] = isset($e['ip']) ? ClientIp::normalize((string) $e['ip']) : '';
        foreach ($e as $k => $v) if (is_int($v)) $e[$k] = (string) $v;
        if ($e['kind'] === 'login_success') $this->legit[$e['ip']][$e['account']] = $now;
        foreach ($this->rules as $rule) {
            if (!($rule['enabled'] ?? true)) continue;
            [$kind, $groupField, $distinctField] = self::SIGNALS[$rule['signal']];
            if ($e['kind'] !== $kind) continue;
            $scope = $this->scope($rule, $groupField, $e);
            if ($scope === null) continue;
            $wk = $rule['id'] . '|' . $scope['value'];
            $entries = array_values(array_filter($this->windows[$wk]['e'] ?? [], fn($x) => $x[0] > $now - $rule['window_seconds']));
            $entries[] = [$now, $distinctField ? ($e[$distinctField] ?? '') : ''];
            if (count($entries) > self::MAX_WINDOW_ENTRIES) $entries = array_slice($entries, -self::MAX_WINDOW_ENTRIES);   // bounded memory under flood
            $this->windows[$wk] = ['w' => $rule['window_seconds'], 'e' => $entries];
            $count = count($entries);
            $distinct = $distinctField ? count(array_unique(array_column($entries, 1))) : null;
            if ($count < $rule['threshold'] || (isset($rule['min_distinct']) && ($distinct ?? 0) < $rule['min_distinct'])) continue;
            foreach ($this->decide($rule, $scope, $count, $distinct, $now, $e) as $ev) $emitted[] = $ev;   // decide() emits
        }
        if (count($this->windows) > self::MAX_WINDOWS) $this->prune($now);
        return $emitted;
    }

    public function isActive(string $scopeKind, string $scopeValue): bool
    {
        $a = $this->active["$scopeKind:$scopeValue"] ?? null;
        return $a !== null && $a['expires'] > ($this->clock)();
    }

    /** Expire timed actions (emits `expired` outcomes) and prune stale in-memory state. */
    public function sweep(): array
    {
        $now = ($this->clock)(); $out = [];
        foreach ($this->active as $k => $a) if ($a['expires'] <= $now) {
            unset($this->active[$k]);
            $out[] = $ev = $this->outcome($a['decision_id'], $a['action'], 'expired', $a['key'], null);
            $this->emit($ev);
        }
        $this->prune($now);
        return $out;
    }

    /** Human rollback of an active action. Idempotent: unknown/already-rolled-back scope returns null and emits nothing. */
    public function rollback(string $scopeKind, string $scopeValue): ?array
    {
        $a = $this->active["$scopeKind:$scopeValue"] ?? null;
        if (!$a) return null;
        unset($this->active["$scopeKind:$scopeValue"]);
        $ev = $this->outcome($a['decision_id'], $a['action'], 'rolled_back', $a['key'], null);
        $this->emit($ev);
        return $ev;
    }

    public function stats(): array
    {
        return ['windows' => count($this->windows), 'max_window_entries' => $this->windows ? max(array_map(fn($w) => count($w['e']), $this->windows)) : 0,
                'legit_ips' => count($this->legit), 'idempotency_keys' => count($this->seen), 'active' => count($this->active),
                'rejected' => $this->rejected, 'dropped' => $this->dropped, 'duplicates_suppressed' => $this->duplicatesSuppressed];
    }

    private function validate(mixed $e): ?string
    {
        if (!is_array($e) || ($e !== [] && array_is_list($e))) return 'not_an_object';
        $kind = $e['kind'] ?? null;
        if (!is_string($kind) || !isset(self::KINDS[$kind])) return 'unknown_kind';
        foreach (self::KINDS[$kind] as $f) {
            $v = $e[$f] ?? null;
            if (is_int($v)) $v = (string) $v;
            if (!is_string($v) || $v === '' || strlen($v) > 256 || preg_match('/[\x00-\x1f]/', $v)) return "bad_field_$f";
            if ($f === 'ip' && ClientIp::normalize($v) === '') return 'bad_field_ip';
        }
        return null;
    }

    private function reject(string $reason, int $now): array
    {
        $this->rejected++;
        if ($now - ($this->lastHealth[$reason] ?? -PHP_INT_MAX) < self::HEALTH_INTERVAL) return [];
        $this->lastHealth[$reason] = $now;
        $ev = $this->events->make('system_health', ['component' => 'detector', 'status' => 'degraded', 'detail' => "malformed signal rejected: $reason"], 'short', $this->defaults['retention_days']['system_health']);
        $this->emit($ev);
        return [$ev];
    }

    private function emit(array $ev): void
    {
        try { $this->sink->emit($ev); } catch (\Throwable) { $this->dropped++; }   // observability must never break the caller
    }

    private function prune(int $now): void
    {
        foreach ($this->windows as $k => $w) if (empty($w['e']) || end($w['e'])[0] <= $now - $w['w']) unset($this->windows[$k]);
        foreach ($this->seen as $k => $exp) if ($exp <= $now) { unset($this->seen[$k], $this->dupNotified[$k], $this->attempts[$k]); }
        foreach ($this->legit as $ip => $accts) {
            foreach ($accts as $a => $ts) if ($ts <= $now - self::LEGIT_TTL) unset($this->legit[$ip][$a]);
            if (!$this->legit[$ip]) unset($this->legit[$ip]);
        }
    }

    private function scope(array $rule, string $field, array $e): ?array
    {
        $v = $e[$field] ?? null;
        if ($v === null || $v === '') return null;
        $by = $rule['group_by'] ?? $field;
        if ($field === 'ip') {
            $p = ClientIp::prefix64($v);
            return $by === 'ip_prefix64' && str_ends_with($p, '/64') ? ['kind' => 'ip_prefix64', 'value' => $p, 'ip' => $v] : ['kind' => 'ip', 'value' => $v, 'ip' => $v];
        }
        return ['kind' => $by, 'value' => (string) $v, 'ip' => $e['ip'] ?? ''];
    }

    private function decide(array $rule, array $scope, int $count, ?int $distinct, int $now, array $e): array
    {
        $mode = $this->modeOverride ?? ($rule['mode'] ?? $this->defaults['mode']);
        $bucket = intdiv($now, $rule['window_seconds']) * $rule['window_seconds'];
        $key = implode(':', [$rule['id'], $rule['version'], $scope['kind'], $scope['value'], $bucket]);
        if (isset($this->seen[$key])) {
            $this->duplicatesSuppressed++;
            if (isset($this->dupNotified[$key])) return [];                       // already recorded once: count silently
            $this->dupNotified[$key] = true;
            $dup = $this->outcome(null, $rule['action'], 'skipped_duplicate', $key, null); $this->emit($dup);
            return [$dup];
        }
        $this->seen[$key] = $bucket + $rule['window_seconds'];

        $evidence = ['group' => $scope['value'], 'count' => $count, 'window_seconds' => $rule['window_seconds']];
        if ($distinct !== null) $evidence['distinct'] = $distinct;
        $action = $rule['action']; $decision = 'act'; $needsApproval = false;
        $ex = $rule['exceptions'] ?? [];
        $spec = $this->actions['actions'][$action] ?? null;

        if (in_array('allowlist_cidrs', $ex, true) && $this->allowlisted($scope)) { $decision = 'suppressed_exception'; $action = 'observe'; }
        elseif (in_array('shared_ip_aware', $ex, true) && in_array($scope['kind'], ['ip', 'ip_prefix64'], true) && $this->sharedIp($scope['ip'])) { $decision = 'manual_review'; $action = 'manual_review'; }
        elseif ($spec === null || count($evidence) < ($spec['min_evidence'] ?? 1)) { $decision = 'manual_review'; $action = 'manual_review'; }
        elseif (!in_array($action, self::EXECUTABLE, true) || ($spec['requires_approval'] ?? false) || ($scope['kind'] === 'ip_prefix64' && in_array('scope_is_ip_prefix64', $spec['approval_if'] ?? [], true))) { $decision = 'manual_review'; $needsApproval = true; }
        elseif ($mode === 'observe') { $decision = 'would_act'; }
        elseif ($mode === 'alert') { $action = 'alert'; }

        $spec = $this->actions['actions'][$action];
        $ttl = $spec['max_ttl_seconds'] > 0 ? min($spec['max_ttl_seconds'], $this->defaults['enforcement']['default_block_ttl_seconds']) : 0;
        $fields = [
            'request_id' => $e['request_id'] ?? 'n/a', 'rule_id' => $rule['id'], 'rule_version' => $rule['version'], 'mode' => $mode,
            'decision' => $decision, 'action' => $action, 'evidence' => $evidence,
            'scope' => ['kind' => $scope['kind'], 'value' => $scope['value']], 'idempotency_key' => $key, 'requires_approval' => $needsApproval,
        ];
        if ($decision === 'act' && $ttl > 0) $fields['expires_at'] = gmdate('Y-m-d\TH:i:s\Z', $now + $ttl);
        $dev = $this->events->make('security_decision', $fields, 'standard', $this->defaults['retention_days']['security']);
        $this->emit($dev);
        $out = $this->execute($dev, $scope, $mode, $ttl, $now);   // RAW scope: the emitted event is redacted, enforcement state must not be
        if ($out['status'] === 'failed') {                                         // retry policy: release the key until MAX_ATTEMPTS
            $this->attempts[$key] = ($this->attempts[$key] ?? 0) + 1;
            if ($this->attempts[$key] < self::MAX_ATTEMPTS) { unset($this->seen[$key]); }
        }
        return [$dev, $out];
    }

    private function execute(array $d, array $scope, string $mode, int $ttl, int $now): array
    {
        $err = null;
        $status = match ($d['decision']) { 'manual_review' => 'pending_approval', 'suppressed_exception' => 'skipped_exception', default => 'skipped_observe_only' };
        if ($d['decision'] === 'act' && $mode !== 'observe') {
            try {
                if ($this->storeFailure) throw new \RuntimeException('action store unavailable');
                if (!in_array($d['action'], self::EXECUTABLE, true)) throw new \LogicException('refusing to execute non-executable action');
                if ($ttl > 0) $this->active[$scope['kind'] . ':' . $scope['value']] = ['expires' => $now + $ttl, 'key' => $d['idempotency_key'], 'action' => $d['action'], 'decision_id' => $d['event_id']];
                $status = 'applied';
            } catch (\Throwable $t) { $status = 'failed'; $err = $t->getMessage(); }
        }
        $ev = $this->outcome($d['event_id'], $d['action'], $status, $d['idempotency_key'], $d['expires_at'] ?? null, $err);
        $this->emit($ev);
        return $ev;
    }

    private function outcome(?string $decisionId, string $action, string $status, string $key, ?string $exp, ?string $err = null): array
    {
        $f = ['decision_event_id' => $decisionId ?? self::NIL_ID, 'action' => $action, 'status' => $status, 'idempotency_key' => $key];
        if ($exp) $f['expires_at'] = $exp;
        if ($err) $f['error'] = $err;
        return $this->events->make('response_outcome', $f, 'standard', $this->defaults['retention_days']['security']);
    }

    private function allowlisted(array $scope): bool
    {
        foreach ($this->defaults['exceptions']['allowlist_cidrs'] as $c) if (Cidr::contains($c, $scope['ip'])) return true;
        return false;
    }
    private function sharedIp(string $ip): bool
    {
        return count($this->legit[$ip] ?? []) >= $this->defaults['exceptions']['shared_ip_min_distinct_accounts'];
    }
}
