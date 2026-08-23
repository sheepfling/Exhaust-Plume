from __future__ import annotations

import pytest

from exhaust_plume.api import v1
from exhaust_plume.contracts.errors import UnsupportedProductCapabilityError

from .harness import run_provider_conformance
from .registrations import (
  CURRENT_PROVIDER_SYMBOLS,
  PROVIDER_REGISTRATION_TABLE,
  fake_provider_fixtures,
  failure_provider_fixture,
  registered_provider_fixtures,
)


@pytest.mark.parametrize(
  'fixture',
  registered_provider_fixtures(),
  ids=lambda fixture: fixture.name,
)
def test_registered_providers_pass_the_common_canonical_harness(fixture) -> None:
  report = run_provider_conformance(fixture)
  assert report.passed is True
  assert report.deterministic_serialization is True
  assert report.immutable_snapshot is True
  assert report.session_closure is True
  assert report.unsupported_versions_checked


@pytest.mark.parametrize(
  'fixture',
  fake_provider_fixtures(),
  ids=lambda fixture: fixture.name,
)
def test_fake_product_providers_pass_product_specific_checks(fixture) -> None:
  report = run_provider_conformance(fixture)
  assert report.passed is True
  assert report.result_ids


def test_failure_provider_is_rejected_at_descriptor_snapshot_boundary() -> None:
  with pytest.raises(AssertionError, match='advertises .* but its snapshot does not support'):
    run_provider_conformance(failure_provider_fixture())


def test_registration_table_covers_every_current_provider_or_records_a_waiver() -> None:
  registered_symbols = {
    symbol
    for registration in PROVIDER_REGISTRATION_TABLE
    for symbol in registration.provider_symbols
  }
  assert registered_symbols == set(CURRENT_PROVIDER_SYMBOLS)
  for registration in PROVIDER_REGISTRATION_TABLE:
    if not registration.is_registered:
      assert registration.waiver_reason


def test_unsupported_capability_failure_is_structured() -> None:
  fixture = fake_provider_fixtures()[0]
  provider = fixture.provider_factory()
  session = fixture.session_factory(provider)
  snapshot = fixture.snapshot_factory(session, 0.0)
  unsupported_capability = fixture.unsupported_capabilities[0]
  specification = v1.get_product_capability_spec(unsupported_capability)
  with pytest.raises(UnsupportedProductCapabilityError):
    snapshot.evaluate(
      specification,
      v1.SpectralSignatureRequest(
        direction_frame_id='source-local',
        source_to_observer_directions=((0.0, 1.0, 0.0),),
        wavelengths_m=(1.0e-6,),
      ),
    )
  assert not snapshot.supports(specification.capability)
