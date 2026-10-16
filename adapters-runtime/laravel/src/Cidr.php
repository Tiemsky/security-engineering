<?php
namespace SecurityEngineering;

final class Cidr
{
    /** True if $ip is inside $cidr (IPv4 or IPv6); a bare address is treated as /32 or /128. */
    public static function contains(string $cidr, string $ip): bool
    {
        [$net, $bits] = array_pad(explode('/', $cidr, 2), 2, null);
        $a = @inet_pton($net); $b = @inet_pton($ip);
        if ($a === false || $b === false || strlen($a) !== strlen($b)) return false;
        $bits = $bits === null ? strlen($a) * 8 : (int) $bits;
        $full = intdiv($bits, 8); $rem = $bits % 8;
        if ($full && substr($a, 0, $full) !== substr($b, 0, $full)) return false;
        if ($rem === 0) return true;
        $mask = (0xFF << (8 - $rem)) & 0xFF;
        return (ord($a[$full]) & $mask) === (ord($b[$full]) & $mask);
    }
}
