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
const NIL_ID = '00000000-0000-4000-8000-000000000000';
const iso = (s: number) => new Date(s * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z');

/** Deterministic rule engine: pure function of (policies, event stream, clock). Mirrors the Laravel engine semantics. */
export class DecisionEngine {
  private windows = new Map<string, [number, string][]>();
  private legit = new Map<string, Map<string, number>>();
  private seen = new Set<string>();
  private active = new Map<string, { expires: number; key: string; action: string; decisionId: string }>();
  storeFailure = false;
  constructor(private rules: Rule[], private defaults: any, private actions: any, private events: EventFactory, private sink: Sink, private clock: () => number, private modeOverride: string | null = null) {}

  observe(e: Record<string, any>): any[] {
    const now = this.clock(); const emitted: any[] = [];
    e = { ...e, ip: normalize(e.ip ?? '') };
    if (e.kind === 'login_success' && e.account) { if (!this.legit.has(e.ip)) this.legit.set(e.ip, new Map()); this.legit.get(e.ip)!.set(e.account, now); }
    for (const rule of this.rules) {
      if (rule.enabled === false) continue;
      const [kind, groupField, distinctField] = SIGNALS[rule.signal];
      if (e.kind !== kind) continue;
      const scope = this.scope(rule, groupField, e); if (!scope) continue;
      const wk = `${rule.id}|${scope.value}`;
      const win = (this.windows.get(wk) ?? []).filter((x) => x[0] > now - rule.window_seconds);
      win.push([now, distinctField ? String(e[distinctField] ?? '') : '']); this.windows.set(wk, win);
      const count = win.length; const distinct = distinctField ? new Set(win.map((x) => x[1])).size : null;
      if (count < rule.threshold || (rule.min_distinct !== undefined && (distinct ?? 0) < rule.min_distinct)) continue;
      for (const ev of this.decide(rule, scope, count, distinct, now, e)) { this.sink.emit(ev); emitted.push(ev); }
    }
    return emitted;
  }

  isActive(kind: string, value: string): boolean { const a = this.active.get(`${kind}:${value}`); return !!a && a.expires > this.clock(); }

  sweep(): any[] {
    const now = this.clock(); const out: any[] = [];
    for (const [k, a] of [...this.active]) if (a.expires <= now) { this.active.delete(k); const ev = this.outcome(a.decisionId, a.action, 'expired', a.key); this.sink.emit(ev); out.push(ev); }
    return out;
  }

  rollback(kind: string, value: string): any | null {
    const a = this.active.get(`${kind}:${value}`); if (!a) return null;
    this.active.delete(`${kind}:${value}`); const ev = this.outcome(a.decisionId, a.action, 'rolled_back', a.key); this.sink.emit(ev); return ev;
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
    if (this.seen.has(key)) return [this.outcome(null, rule.action, 'skipped_duplicate', key)];
    this.seen.add(key);
    const evidence: Record<string, any> = { group: scope.value, count, window_seconds: rule.window_seconds };
    if (distinct !== null) evidence.distinct = distinct;
    let action = rule.action, decision = 'act', needsApproval = false;
    const ex: string[] = rule.exceptions ?? []; let spec = this.actions.actions[action];
    if (ex.includes('allowlist_cidrs') && this.defaults.exceptions.allowlist_cidrs.some((c: string) => cidrContains(c, scope.ip))) { decision = 'suppressed_exception'; action = 'observe'; }
    else if (ex.includes('shared_ip_aware') && ['ip', 'ip_prefix64'].includes(scope.kind) && (this.legit.get(scope.ip)?.size ?? 0) >= this.defaults.exceptions.shared_ip_min_distinct_accounts) { decision = 'manual_review'; action = 'manual_review'; }
    else if (!spec || Object.keys(evidence).length < (spec.min_evidence ?? 1)) { decision = 'manual_review'; action = 'manual_review'; }
    else if (spec.requires_approval || (scope.kind === 'ip_prefix64' && (spec.approval_if ?? []).includes('scope_is_ip_prefix64'))) { decision = 'manual_review'; needsApproval = true; }
    else if (mode === 'observe') decision = 'would_act';
    else if (mode === 'alert') action = 'alert';
    spec = this.actions.actions[action];
    const ttl = spec.max_ttl_seconds > 0 ? Math.min(spec.max_ttl_seconds, this.defaults.enforcement.default_block_ttl_seconds) : 0;
    const fields: Record<string, any> = { request_id: e.request_id ?? 'n/a', rule_id: rule.id, rule_version: rule.version, mode, decision, action, evidence, scope: { kind: scope.kind, value: scope.value }, idempotency_key: key, requires_approval: needsApproval };
    if (decision === 'act' && ttl > 0) fields.expires_at = iso(now + ttl);
    const dev = this.events.make('security_decision', fields, 'standard', this.defaults.retention_days.security);
    return [dev, this.execute(dev, mode, ttl, now)];
  }

  private execute(d: any, mode: string, ttl: number, now: number): any {
    let status = 'skipped_observe_only', err: string | undefined;
    if (d.decision === 'act' && mode !== 'observe') {
      try {
        if (this.storeFailure) throw new Error('action store unavailable');
        if (ttl > 0) this.active.set(`${d.scope.kind}:${d.scope.value}`, { expires: now + ttl, key: d.idempotency_key, action: d.action, decisionId: d.event_id });
        status = 'applied';
      } catch (t: any) { status = 'failed'; err = t.message; }
    }
    return this.outcome(d.event_id, d.action, status, d.idempotency_key, d.expires_at, err);
  }

  private outcome(decisionId: string | null, action: string, status: string, key: string, exp?: string, err?: string): any {
    const f: Record<string, any> = { decision_event_id: decisionId ?? NIL_ID, action, status, idempotency_key: key };
    if (exp) f.expires_at = exp; if (err) f.error = err;
    return this.events.make('response_outcome', f, 'standard', this.defaults.retention_days.security);
  }
}
