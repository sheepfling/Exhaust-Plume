# Loopback Sidecar Transport Specification

## Scope

Local process integration only. Bind to `127.0.0.1`; no remote access or authentication in v1.

## Protocol

```text
HTTP/1.1
UTF-8 JSON
Content-Type: application/json
optional Content-Encoding: gzip
strict JSON: NaN and infinity forbidden
```

## Endpoints

```text
GET    /v1/health
GET    /v1/version
GET    /v1/schemas
GET    /v1/providers
POST   /v1/sessions
DELETE /v1/sessions/{session_id}
POST   /v1/sessions/{session_id}/snapshots
POST   /v1/snapshots/{snapshot_id}/products/{capability_id}
```

## Resource behavior

- UUID session/snapshot identities.
- Explicit cleanup.
- Immutable snapshot reads.
- Deterministic product content hashes.
- Request body and response limits enforced before expensive allocation.
- Optional page tokens for ray products.
- No provider-private Python reprs in responses.

## Error response

```json
{
  "error": {
    "code": "UNSUPPORTED_CAPABILITY",
    "message": "...",
    "details": {},
    "request_id": "uuid"
  }
}
```

The exact error-code enum comes from the canonical API.

## Limits

Use the supplied final-decision limits:

- maximum visual sections: 2048;
- default visual sections: 256;
- maximum signature observers: 4096;
- maximum signature wavelengths: 2048;
- maximum rays per page: 4096;
- maximum ray wavelengths per page: 512;
- maximum uncompressed JSON response: 32 MiB.

## Implementation preference

Use the Python standard library for the first server unless the baseline proves a concrete need for another dependency. Keep routing independent from provider implementation and test with `http.client` against an ephemeral loopback port.
