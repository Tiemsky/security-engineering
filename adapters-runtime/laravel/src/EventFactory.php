<?php
namespace SecurityEngineering;

/** Builds contract-conformant envelopes (contracts/*.schema.json, schema_version 1.0.0). */
final class EventFactory
{
    public function __construct(private \Closure $clock, private Redactor $redactor, private string $service, private string $environment, private string $policyVersion) {}

    public function make(string $type, array $fields, string $retentionClass, int $days): array
    {
        $fields = $this->redactor->redact($fields);
        return array_merge([
            'schema_version' => '1.0.0',
            'event_id' => self::uuid(),
            'event_type' => $type,
            'timestamp' => gmdate('Y-m-d\TH:i:s\Z', ($this->clock)()),
            'trace_id' => bin2hex(random_bytes(16)),
            'source' => ['framework' => 'laravel', 'service' => $this->service, 'environment' => $this->environment],
            'retention' => ['class' => $retentionClass, 'days' => $days],
            'redaction' => ['applied' => true, 'policy_version' => $this->policyVersion],
        ], $fields);
    }

    public static function uuid(): string
    {
        $b = random_bytes(16); $b[6] = chr((ord($b[6]) & 0x0f) | 0x40); $b[8] = chr((ord($b[8]) & 0x3f) | 0x80);
        return vsprintf('%s%s-%s-%s-%s-%s%s%s', str_split(bin2hex($b), 4));
    }
}
