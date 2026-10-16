import { EventFactory, Sink } from './events';
import { cidrContains, normalize, prefix64 } from './ip';

type Rule = Record<string, any>;
const SIGNALS: Record<string, [string, string, string | null]> = {
  failed_logins_per_ip_distinct_accounts: ['login_failed', 'ip', 'account'],
  failed_logins_per_account_distinct_ips: ['login_failed', 'account', 'ip'],
  otp_failures_per_identifier: ['otp_failed', 'account', null],
  sequential_id_walk: ['id_deny', 'token', 'object_id'],
  not_found_burst: ['not_found', 'ip', 'path'],
  honeypot_hit: ['honeypot', 'ip', null],
  signature_failures_per_source: ['signature_failed', 'ip', null],
  request_rate_per_key: ['request', 'ip', null],
};
const KINDS: Record<string, string[]> = {   // signal kind => required string fields
  login_failed: ['ip', 'account'], login_success: ['ip', 'account'], otp_failed: ['account'], id_deny: ['token', 'object_id'],
  not_found: ['ip', 'path'], honeypot: ['ip'], signature_failed: ['ip'], request: ['ip'],
};
export const EXECUTABLE = ['observe', 'alert', 'rate_limit', 'temp_ip_block', 'manual_review'];
const NIL_ID = '00000000-0000-4000-8000-000000000000';
const MAX_ATTEMPTS = 3, MAX_WINDOW_ENTRIES = 10000, MAX_WINDOWS = 50000, HEALTH_INTERVAL = 60, LEGIT_TTL = 86400;
const iso = (s: number) => new Date(s * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z');

/** Deterministic rule engine: pure function of (policies, event stream, clock). Mirrors the Laravel engine semantics
 *  (see adapters-runtime/laravel/src/DecisionEngine.php for the hardening rationale). */
export class DecisionEngine {
  private windows = new Map<string, { w: number; e: [number, string][] }>();
  private legit = new Map<string, Map<string, number>>();
  private seen = new Map<string, number>();
  private dupNotified = new Set<string>();
  private attempts = new Map<string, number>();
  private active = new Map<string, { expires: number; key: string; action: string; decisionId: string }>();
  private lastHealth = new Map<string, number>();
  storeFailure = false; rejected = 0; dropped = 0; duplicatesSuppressed = 0;
  constructor(private rules: Rule[], private defaults: any, private actions: any, private events: EventFactory, private sink: Sink, private clock: () => number, private modeOverride: string | null = null) {}

  observe(e0: any): any[] {
    const now = this.clock(); const emitted: any[] = [];
    const reason = this.validate(e0); if (reason) return this.reject(reason, now);
    const e: Record<string, any> = { ...e0 }; e.ip = e.ip !== undefined ? normalize(String(e.ip)) : '';
    for (const k of Object.keys(e)) if (typeof e[k] === 'number') e[k] = String(e[k]);
    if (e.kind === 'login_success') { if (!this.legit.has(e.ip)) this.legit.set(e.ip, new Map()); this.legit.get(e.ip)!.set(e.account, now); }
    for (const rule of this.rules) {
      if (rule.enabled === false) continue;
      const [kind, groupField, distinctField] = SIGNALS[rule.signal];
      if (e.kind !== kind) continue;
      const scope = this.scope(rule, groupField, e); if (!scope) continue;
      const wk = `${rule.id}|${scope.value}`;
      let entries = (this.windows.get(wk)?.e ?? []).filter((x) => x[0] > now - rule.window_seconds);
      entries.push([now, distinctField ? String(e[distinctField] ?? '') : '']);
      if (entries.length > MAX_WINDOW_ENTRIES) entries = entries.slice(-MAX_WINDOW_ENTRIES);   // bounded memory under flood
      this.windows.set(wk, { w: rule.window_seconds, e: entries });
      const count = entries.length; const distinct = distinctField ? new Set(entries.map((x) => x[1])).size : null;
      if (count < rule.threshold || (rule.min_distinct !== undefined && (distinct ?? 0) < rule.min_distinct)) continue;
      for (const ev of this.decide(rule, scope, count, distinct, now, e)) emitted.push(ev);   // decide() emits
    }
    if (this.windows.size > MAX_WINDOWS) this.prune(now);
    return emitted;
  }

  isActive(kind: string, value: string): boolean { const a = this.active.get(`${kind}:${value}`); return !!a && a.expires > this.clock(); }

  sweep(): any[] {
    const now = this.clock(); const out: any[] = [];
    for (const [k, a] of [...this.active]) if (a.expires <= now) { this.active.delete(k); const ev = this.outcome(a.decisionId, a.action, 'expired', a.key); this.emit(ev); out.push(ev); }
    this.prune(now);
    return out;
  }

  rollback(kind: string, value: string): any | null {
    const a = this.active.get(`${kind}:${value}`); if (!a) return null;
    this.active.delete(`${kind}:${value}`); const ev = this.outcome(a.decisionId, a.action, 'rolled_back', a.key); this.emit(ev); return ev;
  }

  stats() {
    return { windows: this.windows.size, max_window_entries: Math.max(0, ...[...this.windows.values()].map((w) => w.e.length)), legit_ips: this.legit.size, idempotency_keys: this.seen.size,
             active: this.active.size, rejected: this.rejected, dropped: this.dropped, duplicates_suppressed: this.duplicatesSuppressed };
  }

  private validate(e: any): string | null {
    if (e === null || typeof e !== 'object' || Array.isArray(e)) return 'not_an_object';
    if (typeof e.kind !== 'string' || !Object.prototype.hasOwnProperty.call(KINDS, e.kind)) return 'unknown_kind';
    for (const f of KINDS[e.kind]) {
      let v = e[f]; if (typeof v === 'number' && Number.isInteger(v)) v = String(v);
      if (typeof v !== 'string' || v === '' || Buffer.byteLength(v) > 256 || /[\x00-\x1f]/.test(v)) return `bad_field_${f}`;
      if (f === 'ip' && normalize(v) === '') return 'bad_field_ip';
    }
    return null;
  }

  private reject(reason: string, now: number): any[] {
    this.rejected++;
    if (now - (this.lastHealth.get(reason) ?? -Infinity) < HEALTH_INTERVAL) return [];
    this.lastHealth.set(reason, now);
    const ev = this.events.make('system_health', { component: 'detector', status: 'degraded', detail: `malformed signal rejected: ${reason}` }, 'short', this.defaults.retention_days.system_health);
    this.emit(ev); return [ev];
  }

  private emit(ev: any) { try { this.sink.emit(ev); } catch { this.dropped++; } }   // observability must never break the caller

  private prune(now: number) {
    for (const [k, w] of this.windows) if (!w.e.length || w.e[w.e.length - 1][0] <= now - w.w) this.windows.delete(k);
    for (const [k, exp] of this.seen) if (exp <= now) { this.seen.delete(k); this.dupNotified.delete(k); this.attempts.delete(k); }
    for (const [ip, m] of this.legit) { for (const [a, ts] of m) if (ts <= now - LEGIT_TTL) m.delete(a); if (!m.size) this.legit.delete(ip); }
  }

  private scope(rule: Rule, field: string, e: Record<string, any>) {
    const v = e[field]; if (v === undefined || v === null || v === '') return null;
    const by = rule.group_by ?? field;
    if (field === 'ip') { const p = prefix64(v); return by === 'ip_prefix64' && p.endsWith('/64') ? { kind: 'ip_prefix64', value: p, ip: v } : { kind: 'ip', value: v, ip: v }; }
    return { kind: by, value: String(v), ip: e.ip ?? '' };
  }

  private decide(rule: Rule, scope: any, count: number, distinct: number | null, now: number, e: Record<string, any>): any[] {
    const mode = this.modeOverride ?? rule.mode ?? this.defaults.mode;
    const bucket = Math.floor(now / rule.window_seconds) * rule.window_seconds;
    const key = [rule.id, rule.version, scope.kind, scope.value, bucket].join(':');
    if (this.seen.has(key)) {
      this.duplicatesSuppressed++;
      if (this.dupNotified.has(key)) return [];
      this.dupNotified.add(key);
      const dup = this.outcome(null, rule.action, 'skipped_duplicate', key); this.emit(dup); return [dup];
    }
    this.seen.set(key, bucket + rule.window_seconds);
    const evidence: Record<string, any> = { group: scope.value, count, window_seconds: rule.window_seconds };
    if (distinct !== null) evidence.distinct = distinct;
    let action = rule.action, decision = 'act', needsApproval = false;
    const ex: string[] = rule.exceptions ?? []; let spec = this.actions.actions[action];
    if (ex.includes('allowlist_cidrs') && this.defaults.exceptions.allowlist_cidrs.some((c: string) => cidrContains(c, scope.ip))) { decision = 'suppressed_exception'; action = 'observe'; }
    else if (ex.includes('shared_ip_aware') && ['ip', 'ip_prefix64'].includes(scope.kind) && (this.legit.get(scope.ip)?.size ?? 0) >= this.defaults.exceptions.shared_ip_min_distinct_accounts) { decision = 'manual_review'; action = 'manual_review'; }
    else if (!spec || Object.keys(evidence).length < (spec.min_evidence ?? 1)) { decision = 'manual_review'; action = 'manual_review'; }
    else if (!EXECUTABLE.includes(action) || spec.requires_approval || (scope.kind === 'ip_prefix64' && (spec.approval_if ?? []).includes('scope_is_ip_prefix64'))) { decision = 'manual_review'; needsApproval = true; }
    else if (mode === 'observe') decision = 'would_act';
    else if (mode === 'alert') action = 'alert';
    spec = this.actions.actions[action];
    const ttl = spec.max_ttl_seconds > 0 ? Math.min(spec.max_ttl_seconds, this.defaults.enforcement.default_block_ttl_seconds) : 0;
    const fields: Record<string, any> = { request_id: e.request_id ?? 'n/a', rule_id: rule.id, rule_version: rule.version, mode, decision, action, evidence, scope: { kind: scope.kind, value: scope.value }, idempotency_key: key, requires_approval: needsApproval };
    if (decision === 'act' && ttl > 0) fields.expires_at = iso(now + ttl);
    const dev = this.events.make('security_decision', fields, 'standard', this.defaults.retention_days.security);
    this.emit(dev);
    const out = this.execute(dev, scope, mode, ttl, now);   // RAW scope: the emitted event is redacted, enforcement state must not be
    if (out.status === 'failed') {   // retry policy: release the key until MAX_ATTEMPTS
      const n = (this.attempts.get(key) ?? 0) + 1; this.attempts.set(key, n);
      if (n < MAX_ATTEMPTS) this.seen.delete(key);
    }
    return [dev, out];
  }

  private execute(d: any, scope: any, mode: string, ttl: number, now: number): any {
    let status = ({ manual_review: 'pending_approval', suppressed_exception: 'skipped_exception' } as Record<string, string>)[d.decision] ?? 'skipped_observe_only', err: string | undefined;
    if (d.decision === 'act' && mode !== 'observe') {
      try {
        if (this.storeFailure) throw new Error('action store unavailable');
        if (!EXECUTABLE.includes(d.action)) throw new Error('refusing to execute non-executable action');
        if (ttl > 0) this.active.set(`${scope.kind}:${scope.value}`, { expires: now + ttl, key: d.idempotency_key, action: d.action, decisionId: d.event_id });
        status = 'applied';
      } catch (t: any) { status = 'failed'; err = t.message; }
    }
    const ev = this.outcome(d.event_id, d.action, status, d.idempotency_key, d.expires_at, err); this.emit(ev); return ev;
  }

  private outcome(decisionId: string | null, action: string, status: string, key: string, exp?: string, err?: string): any {
    const f: Record<string, any> = { decision_event_id: decisionId ?? NIL_ID, action, status, idempotency_key: key };
    if (exp) f.expires_at = exp; if (err) f.error = err;
    return this.events.make('response_outcome', f, 'standard', this.defaults.retention_days.security);
  }
}
