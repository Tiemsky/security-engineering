<?php
namespace SecurityEngineering;

final class ClientIp
{
    /** Resolve the client IP. X-Forwarded-For is honoured only when the direct peer is a trusted proxy. */
    public static function resolve(string $peer, ?string $xff, array $trustedCidrs): string
    {
        $peer = self::normalize($peer);
        if (!$xff || !self::trusted($peer, $trustedCidrs)) return $peer;
        $hops = array_reverse(array_map('trim', explode(',', $xff)));
        foreach ($hops as $hop) {
            $hop = self::normalize($hop);
            if ($hop === '') continue;
            if (!self::trusted($hop, $trustedCidrs)) return $hop;
        }
        return $peer;
    }

    public static function normalize(string $ip): string
    {
        $p = @inet_pton(trim($ip));
        return $p === false ? '' : inet_ntop($p);
    }

    /** IPv6 → /64 prefix (as "xxxx:xxxx:xxxx:xxxx::/64"), IPv4 unchanged. */
    public static function prefix64(string $ip): string
    {
        $p = inet_pton($ip);
        if (strlen($p) === 4) return $ip;
        return inet_ntop(substr($p, 0, 8) . str_repeat("\0", 8)) . '/64';
    }

    private static function trusted(string $ip, array $cidrs): bool
    {
        foreach ($cidrs as $c) if (Cidr::contains($c, $ip)) return true;
        return false;
    }
}
