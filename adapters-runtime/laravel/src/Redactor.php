<?php
namespace SecurityEngineering;

final class Redactor
{
    public function __construct(private array $policy) {}

    public function redact(mixed $value, string $key = ''): mixed
    {
        if ($key !== '' && $this->forbiddenKey($key)) return $this->policy['replacement'];
        if (is_array($value)) {
            $out = [];
            foreach ($value as $k => $v) $out[$k] = $this->redact($v, is_string($k) ? $k : '');
            return $out;
        }
        if (is_string($value)) {
            foreach ($this->policy['forbidden_value_patterns'] as $re) {
                $value = preg_replace('~' . str_replace('~', '\~', $this->stripInline($re)) . '~' . $this->flags($re), $this->policy['replacement'], $value);
            }
            return mb_substr($value, 0, $this->policy['max_string_length']);
        }
        return $value;
    }

    private function forbiddenKey(string $key): bool
    {
        $k = strtolower($key);
        foreach ($this->policy['forbidden_fields'] as $f) if (str_contains($k, $f)) return true;
        return false;
    }
    private function flags(string $re): string { return str_starts_with($re, '(?i)') ? 'i' : ''; }
    private function stripInline(string $re): string { return str_starts_with($re, '(?i)') ? substr($re, 4) : $re; }
}
