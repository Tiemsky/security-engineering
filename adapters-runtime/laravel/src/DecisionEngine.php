<?php
namespace SecurityEngineering;

/**
 * Deterministic rule engine. Pure function of (policies, event stream, clock): no LLM, no I/O besides the injected sink.
 * Default mode is observe: decisions are recorded, nothing is enforced.
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

    private const NIL_ID = '00000000-0000-4000-8000-000000000000';
    private array $windows = [];   // rule|group => [[ts, distinct], ...]
    private array $legit = [];     // ip => [account => ts]  (successful logins, shared-IP awareness)
    private array $seen = [];      // idempotency keys
    private array $active = [];    // scopeKey => ['expires'=>int,'key'=>string,'action'=>string]
    public bool $storeFailure = false; // test hook: simulate action-store outage

    public function __construct(
        private array $rules, private array $defaults, private array $actions,
        private EventFactory $events, private Sink $sink, private \Closure $clock, private ?string $modeOverride = null,
    ) {}

    /** Feed one signal event ['kind','ip','account','token','path','object_id','request_id']. Returns emitted events. */
    public function observe(array $e): array
    {
        $now = ($this->clock)(); $emitted = [];
        $e['ip'] = ClientIp::normalize($e['ip'] ?? '');
        if (($e['kind'] ?? '') === 'login_success' && isset($e['account'])) $this->legit[$e['ip']][$e['account']] = $now;
        foreach ($this->rules as $rule) {
            if (!($rule['enabled'] ?? true)) continue;
            [$kind, $groupField, $distinctField] = self::SIGNALS[$rule['signal']];
            if (($e['kind'] ?? '') !== $kind) continue;
            $scope = $this->scope($rule, $groupField, $e);
            if ($scope === null) continue;
            $wk = $rule['id'] . '|' . $scope['value'];
            $win = array_values(array_filter($this->windows[$wk] ?? [], fn($x) => $x[0] > $now - $rule['window_seconds']));
            $win[] = [$now, $distinctField ? ($e[$distinctField] ?? '') : ''];
            $this->windows[$wk] = $win;
            $count = count($win);
            $distinct = $distinctField ? count(array_unique(array_column($win, 1))) : null;
            if ($count < $rule['threshold'] || (isset($rule['min_distinct']) && ($distinct ?? 0) < $rule['min_distinct'])) continue;
            foreach ($this->decide($rule, $scope, $count, $distinct, $now, $e) as $ev) { $this->sink->emit($ev); $emitted[] = $ev; }
        }
        return $emitted;
    }

    public function isActive(string $scopeKind, string $scopeValue): bool
    {
        $a = $this->active["$scopeKind:$scopeValue"] ?? null;
        return $a !== null && $a['expires'] > ($this->clock)();
    }

    /** Expire timed actions; emits `expired` outcomes. */
    public function sweep(): array
    {
        $now = ($this->clock)(); $out = [];
        foreach ($this->active as $k => $a) if ($a['expires'] <= $now) {
            unset($this->active[$k]);
            $out[] = $ev = $this->outcome($a['decision_id'], $a['action'], 'expired', $a['key'], null);
            $this->sink->emit($ev);
        }
        return $out;
    }

    public function rollback(string $scopeKind, string $scopeValue): ?array
    {
        $a = $this->active["$scopeKind:$scopeValue"] ?? null;
        if (!$a) return null;
        unset($this->active["$scopeKind:$scopeValue"]);
        $ev = $this->outcome($a['decision_id'], $a['action'], 'rolled_back', $a['key'], null);
        $this->sink->emit($ev);
        return $ev;
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
        if (isset($this->seen[$key])) return [$this->outcome(null, $rule['action'], 'skipped_duplicate', $key, null)];
        $this->seen[$key] = true;

        $evidence = ['group' => $scope['value'], 'count' => $count, 'window_seconds' => $rule['window_seconds']];
        if ($distinct !== null) $evidence['distinct'] = $distinct;
        $action = $rule['action']; $decision = 'act'; $needsApproval = false;
        $ex = $rule['exceptions'] ?? [];
        $spec = $this->actions['actions'][$action] ?? null;

        if (in_array('allowlist_cidrs', $ex, true) && $this->allowlisted($scope)) { $decision = 'suppressed_exception'; $action = 'observe'; }
        elseif (in_array('shared_ip_aware', $ex, true) && in_array($scope['kind'], ['ip', 'ip_prefix64'], true) && $this->sharedIp($scope['ip'])) { $decision = 'manual_review'; $action = 'manual_review'; }
        elseif ($spec === null || count($evidence) < ($spec['min_evidence'] ?? 1)) { $decision = 'manual_review'; $action = 'manual_review'; }
        elseif (($spec['requires_approval'] ?? false) || ($scope['kind'] === 'ip_prefix64' && in_array('scope_is_ip_prefix64', $spec['approval_if'] ?? [], true))) { $decision = 'manual_review'; $needsApproval = true; }
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
        return [$dev, $this->execute($dev, $mode, $ttl, $now)];
    }

    private function execute(array $d, string $mode, int $ttl, int $now): array
    {
        $status = 'skipped_observe_only'; $err = null;
        if ($d['decision'] === 'act' && $mode !== 'observe') {
            try {
                if ($this->storeFailure) throw new \RuntimeException('action store unavailable');
                if ($ttl > 0) $this->active[$d['scope']['kind'] . ':' . $d['scope']['value']] = ['expires' => $now + $ttl, 'key' => $d['idempotency_key'], 'action' => $d['action'], 'decision_id' => $d['event_id']];
                $status = 'applied';
            } catch (\Throwable $t) { $status = 'failed'; $err = $t->getMessage(); }
        }
        return $this->outcome($d['event_id'], $d['action'], $status, $d['idempotency_key'], $d['expires_at'] ?? null, $err);
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
