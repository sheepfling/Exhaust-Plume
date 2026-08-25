"""Reference-only provider conformance outline."""

from __future__ import annotations


def assert_provider_conformance(provider: object) -> None:
  """Check discovery, static time, immutability, determinism, and errors."""
  assert provider is not None
  # TODO: construct session from provider-specific fixture.
  # TODO: request the same snapshot twice and compare canonical hashes.
  # TODO: request an unsupported capability and assert the canonical error code.
  # TODO: verify concurrent reads do not mutate snapshot state.
  ####
####
