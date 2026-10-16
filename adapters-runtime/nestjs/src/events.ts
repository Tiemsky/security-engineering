import { randomBytes, randomUUID } from 'node:crypto';
import { Redactor } from './redactor';

export interface Sink { emit(event: any): void }
export class MemorySink implements Sink { events: any[] = []; emit(e: any) { this.events.push(e); } }
/** Never lets sink failures reach the request. */
export class SafeSink implements Sink { dropped = 0; constructor(private inner: Sink) {} emit(e: any) { try { this.inner.emit(e); } catch { this.dropped++; } } }

export class EventFactory {
  constructor(private clock: () => number, private redactor: Redactor, private service: string, private environment: string, private policyVersion: string) {}
  make(type: string, fields: Record<string, any>, retentionClass: string, days: number) {
    return {
      schema_version: '1.0.0', event_id: randomUUID(), event_type: type,
      timestamp: new Date(this.clock() * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z'), trace_id: randomBytes(16).toString('hex'),
      source: { framework: 'nestjs', service: this.service, environment: this.environment },
      retention: { class: retentionClass, days }, redaction: { applied: true, policy_version: this.policyVersion },
      ...this.redactor.redact(fields),
    };
  }
}
