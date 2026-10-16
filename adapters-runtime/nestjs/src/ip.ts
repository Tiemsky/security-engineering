import { isIP } from 'node:net';

function toBytes(ip: string): number[] | null {
  const v = isIP(ip.trim());
  if (v === 4) return ip.trim().split('.').map(Number);
  if (v !== 6) return null;
  let s = ip.trim().toLowerCase();
  if (s.includes('%')) return null;   // zone identifiers are not valid client addresses (PHP inet_pton rejects them too)
  const m = s.match(/^(.*:)(\d+\.\d+\.\d+\.\d+)$/);
  if (m) { const q = m[2].split('.').map(Number); s = m[1] + ((q[0] << 8) | q[1]).toString(16) + ':' + ((q[2] << 8) | q[3]).toString(16); }
  const [head, tail] = s.split('::');
  const h = head ? head.split(':') : [], t = tail !== undefined && tail ? tail.split(':') : [];
  const groups = s.includes('::') ? [...h, ...Array(8 - h.length - t.length).fill('0'), ...t] : h;
  return groups.flatMap((g) => { const n = parseInt(g, 16); return [n >> 8, n & 255]; });
}

function fromBytes(b: number[]): string {
  if (b.length === 4) return b.join('.');
  if (b.slice(0, 10).every((x) => x === 0) && b[10] === 0xff && b[11] === 0xff) return `::ffff:${b.slice(12).join('.')}`;   // canonical IPv4-mapped form, as PHP inet_ntop
  const g: number[] = []; for (let i = 0; i < 16; i += 2) g.push((b[i] << 8) | b[i + 1]);
  let best = -1, bestLen = 0;
  for (let i = 0; i < 8;) { if (g[i] !== 0) { i++; continue; } let j = i; while (j < 8 && g[j] === 0) j++; if (j - i > bestLen) { best = i; bestLen = j - i; } i = j; }
  const hex = g.map((x) => x.toString(16));
  if (bestLen < 2) return hex.join(':');
  return hex.slice(0, best).join(':') + '::' + hex.slice(best + bestLen).join(':');
}

/** Normalized text form (RFC 5952 for IPv6); '' if invalid. */
export function normalize(ip: string): string { const b = toBytes(ip ?? ''); return b ? fromBytes(b) : ''; }

/** IPv6 → "<prefix>::/64"; IPv4 unchanged. */
export function prefix64(ip: string): string {
  const b = toBytes(ip)!; if (b.length === 4) return ip;
  return fromBytes([...b.slice(0, 8), ...Array(8).fill(0)]) + '/64';
}

export function cidrContains(cidr: string, ip: string): boolean {
  const [net, bitsStr] = cidr.split('/'); const a = toBytes(net), b = toBytes(ip);
  if (!a || !b || a.length !== b.length) return false;
  let bits = bitsStr === undefined ? a.length * 8 : Number(bitsStr);
  for (let i = 0; bits > 0; i++, bits -= 8) { const mask = bits >= 8 ? 255 : (255 << (8 - bits)) & 255; if ((a[i] & mask) !== (b[i] & mask)) return false; }
  return true;
}

/** X-Forwarded-For is honoured only when the direct peer is a trusted proxy. */
export function resolveClientIp(peer: string, xff: string | undefined, trusted: string[]): string {
  const p = normalize(peer); const isTrusted = (ip: string) => trusted.some((c) => cidrContains(c, ip));
  if (!xff || !isTrusted(p)) return p;
  for (const hop of xff.split(',').map((x) => x.trim()).reverse()) { const h = normalize(hop); if (h && !isTrusted(h)) return h; }
  return p;
}
