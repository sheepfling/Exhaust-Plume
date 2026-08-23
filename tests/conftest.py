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
def metadata_factory() -> Callable[[CapabilityId, str], ProductMetadata]:
  def make(capability: CapabilityId, product_id: str = 'product-1') -> ProductMetadata:
    return ProductMetadata(
        product_id=product_id,
        capability=capability,
        snapshot_id='snapshot-1',
        time_s=0.,
        frame=CoordinateFrame(
            frame_id='plume',
            axis_convention='+x downstream, +y right, +z up',
        ),
        provenance=Provenance(
            provider_id='test-provider',
            provider_version='0.1.0',
            model_name='test-model',
            model_revision='test-revision',
        ),
        fidelity=Fidelity(
            morphology='prescribed',
            flow='none',
            radiation='none',
            time='static',
            validation='contract-test',
        ),
        applicability=Applicability(minimum_time_s=0., maximum_time_s=0.),
    )
  ####
  return make
