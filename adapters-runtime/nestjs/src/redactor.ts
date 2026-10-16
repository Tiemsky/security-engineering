export interface RedactionPolicy { policy_version: string; forbidden_fields: string[]; forbidden_value_patterns: string[]; replacement: string; max_string_length: number }

export class Redactor {
  private res: RegExp[];
  constructor(private p: RedactionPolicy) {
    this.res = p.forbidden_value_patterns.map((r) => (r.startsWith('(?i)') ? new RegExp(r.slice(4), 'gi') : new RegExp(r, 'g')));
  }
  redact(v: any, key = ''): any {
    if (key && this.p.forbidden_fields.some((f) => key.toLowerCase().includes(f))) return this.p.replacement;
    if (Array.isArray(v)) return v.map((x) => this.redact(x));
    if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, this.redact(x, k)]));
    if (typeof v === 'string') return this.res.reduce((s, re) => s.replace(re, this.p.replacement), v).slice(0, this.p.max_string_length);
    return v;
  }
}
