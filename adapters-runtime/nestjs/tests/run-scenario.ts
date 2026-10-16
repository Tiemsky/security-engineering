/** Boots a REAL NestJS app (Express adapter), replays one shared scenario over actual HTTP, writes JSONL.
 *  Usage: tsx run-scenario.ts <scenario.json> <out.jsonl>   Env: SE_POLICY_DIR */
import 'reflect-metadata';
import { readFileSync, writeFileSync } from 'node:fs';
import { MiddlewareConsumer, Module, NestModule } from '@nestjs/common';
import { APP_FILTER, APP_INTERCEPTOR, NestFactory } from '@nestjs/core';
import { AuthProbeController } from '../examples/auth-probe.controller';
import { AccessExceptionFilter, AccessInterceptor, DecisionEngine, EventFactory, MemorySink, Redactor, SecurityMiddleware, SecurityModule } from '../src';

const sc = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const dir = process.env.SE_POLICY_DIR!; const load = (n: string) => JSON.parse(readFileSync(`${dir}/${n}.json`, 'utf8'));
let now = 1760000000; const clock = () => now;
const defaults = load('defaults'); defaults.exceptions.allowlist_cidrs = [...defaults.exceptions.allowlist_cidrs, ...(sc.config.allowlist_cidrs ?? [])];
const redaction = load('redaction'); const memory = new MemorySink();
const sink = sc.config.sink_failure ? ({ emit() { throw new Error('sink down'); } } as any) : memory;   // every sink write throws: engine + middleware must survive
const factory = new EventFactory(clock, new Redactor(redaction), 'nest-sample', 'local', redaction.policy_version);
const engine = new DecisionEngine([...load('detection-rules').rules, ...(sc.config.extra_rules ?? [])], defaults, load('response-actions'), factory, sink, clock, sc.config.mode ?? null);
engine.storeFailure = !!sc.config.store_failure;
const options = { trustedProxies: sc.config.trusted_proxies ?? [], retentionDaysHttp: defaults.retention_days.http_access, testPeerHeader: 'x-test-peer' };

@Module({
  imports: [SecurityModule.register({ options, engine, factory, sink })],
  controllers: [AuthProbeController],
  providers: [{ provide: APP_INTERCEPTOR, useClass: AccessInterceptor }, { provide: APP_FILTER, useClass: AccessExceptionFilter }],
})
class AppModule implements NestModule { configure(c: MiddlewareConsumer) { c.apply(SecurityMiddleware).forRoutes('*'); } }

(async () => {
  const app = await NestFactory.create(AppModule, { logger: false }); await app.listen(0, '127.0.0.1');
  const base = await app.getUrl(); const lines: any[] = [];
  const tpl = (v: any, i: number): any => Array.isArray(v) ? v.map((x) => tpl(x, i)) : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, tpl(x, i)]))
    : typeof v === 'string' ? v.replace(/\{i(?:%(\d+))?\}/g, (_m, mod) => String(mod ? i % Number(mod) : i)) : v;
  for (const [i, s] of sc.steps.entries()) {
    now = 1760000000 + s.t;
    const op = s.op ?? 'http';
    if (op === 'sweep') { engine.sweep(); continue; }
    if (op === 'signal') { engine.observe(s.event); continue; }
    if (op === 'burst') { for (let k = 0; k < s.n; k++) { now = 1760000000 + s.t + Math.floor(k / (s.per_second ?? 1)); engine.observe(tpl(s.event, k)); } continue; }
    if (op === 'rollback') { engine.rollback(s.kind, s.value); continue; }
    if (op === 'store_failure') { engine.storeFailure = !!s.value; continue; }
    if (op === 'assert') { const st: any = engine.stats(); lines.push({ type: 'assert', step: i, what: s.what, got: s.what === 'active' ? engine.isActive(s.kind, s.value) : st[s.what] }); continue; }
    const headers: Record<string, string> = { 'content-type': 'application/json', 'x-test-peer': s.peer ?? s.ip, ...(s.headers ?? {}) };
    if (s.xff) headers['x-forwarded-for'] = s.xff;
    const before = memory.events.length;
    const r = await fetch(base + s.path, { method: s.method, headers, body: s.json ? JSON.stringify(s.json) : undefined });
    await r.text();
    const access = memory.events.slice(before).filter((e) => e.event_type === 'http_access');
    lines.push({ type: 'http', step: i, status: r.status, client_ip: access[0]?.client_ip ?? null, route: access[0]?.route ?? null });
  }
  for (const e of memory.events) lines.push({ type: 'event', event: e });
  writeFileSync(process.argv[3], lines.map((l) => JSON.stringify(l)).join('\n') + '\n');
  await app.close();
})();
