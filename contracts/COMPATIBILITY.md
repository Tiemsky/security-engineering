# Contract compatibility and migration rules
- Every event carries `schema_version` (SemVer). Current: **1.0.0**. Schemas are `additionalProperties: false`; framework-specific data goes in `extensions`.
- **PATCH**: clarifications/description changes, no validation change.
- **MINOR**: new *optional* fields, new enum values appended. Producers on 1.x remain valid for consumers on 1.y (y ≥ x) that ignore unknown enum values.
- **MAJOR**: removed/renamed/required fields, narrowed types. Requires a migration note here, dual-emit period of ≥ 1 minor release of the installer, and test fixtures for both versions.
- Consumers MUST reject events whose MAJOR is higher than supported and SHOULD tolerate higher MINOR.
- Timestamps UTC `Z`. IPs: IPv4 dotted or IPv6 RFC 5952 text; aggregate IPv6 by /64 for rate/blocks (`ip_prefix64`).
- Forbidden content (all events): passwords, OTPs, raw access/refresh tokens, cookies, Authorization headers, API secrets, payment credentials, complete sensitive bodies. Enforced by `policies/redaction.yaml` + tests.
- Validator subset used by tests (`tests/lib/minischema.py`): type, enum, const, required, properties, additionalProperties, items, minItems, minProperties, pattern, min/maxLength, minimum/maximum, format (date-time, ipv4, ipv6), anyOf, $ref. CI additionally validates schemas with the full `jsonschema` library.
## Migration log
- 1.0.0 — initial.
