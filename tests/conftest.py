from __future__ import annotations

from collections.abc import Callable

import pytest

from exhaust_plume.products import (
    Applicability,
    CapabilityId,
    CoordinateFrame,
    Fidelity,
    ProductMetadata,
    Provenance,
)


@pytest.fixture
def metadata_factory() -> Callable[[CapabilityId, str, str, float], ProductMetadata]:
  def makeMetadata(
      capability: CapabilityId,
      product_id: str = 'product-1',
      snapshot_id: str = 'snapshot-1',
      time_s: float = 0.,
  ) -> ProductMetadata:
    return ProductMetadata(
        product_id=product_id,
        capability=capability,
        snapshot_id=snapshot_id,
        time_s=time_s,
        frame=CoordinateFrame(
            frame_id='world',
            axis_convention='+x forward, +y right, +z up',
        ),
        provenance=Provenance(
            provider_id='test-provider',
            provider_version='0.1.0',
            model_name='test-model',
            model_revision='test-revision',
        ),
        fidelity=Fidelity(
            morphology='prescribed',
            flow='prescribed',
            radiation='none',
            time='static',
            validation='unit-test',
        ),
        applicability=Applicability(minimum_time_s=time_s, maximum_time_s=time_s),
    )
  ####
  return makeMetadata
####
