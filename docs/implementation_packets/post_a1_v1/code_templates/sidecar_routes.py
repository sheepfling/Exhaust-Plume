"""Reference-only route inventory for the loopback sidecar."""

from __future__ import annotations

ROUTES: tuple[tuple[str, str], ...] = (
    ('GET', '/v1/health'),
    ('GET', '/v1/version'),
    ('GET', '/v1/schemas'),
    ('GET', '/v1/providers'),
    ('POST', '/v1/sessions'),
    ('DELETE', '/v1/sessions/{session_id}'),
    ('POST', '/v1/sessions/{session_id}/snapshots'),
    ('POST', '/v1/snapshots/{snapshot_id}/products/{capability_id}'),
)
####
