from __future__ import annotations

from math import exp

import pytest

from exhaust_plume import (
  Pose,
  SPECTRAL_RADIANT_INTENSITY_V1,
  SPECTRAL_RAY_TRANSFER_V1,
  SpectralSignatureRequest,
  SpectralRayTransferRequest,
)
from exhaust_plume.contracts.errors import (
  ProductOutsideApplicabilityError,
  ProviderConfigurationError,
  UnsupportedProductCapabilityError,
)
from exhaust_plume.geometry import SectionedTubeSupport
from exhaust_plume.providers import (
  GrayRayTransferDefinition,
  GrayRayTransferProvider,
)


def _definition() -> GrayRayTransferDefinition:
  return GrayRayTransferDefinition(
    frame_id='sensor',
    support=SectionedTubeSupport(
      frame_id='sensor',
      centers_m=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
      radii_m=(1.0, 1.0),
    ),
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    source_function_w_sr_m=(2.0, 4.0, 8.0),
    absorption_coefficient_per_m=(0.5, 1.0, 2.0),
  )


def _snapshot():
  return GrayRayTransferProvider().create_session(definition=_definition()).create_snapshot(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )


def test_gray_provider_solves_cylinder_chord_and_interpolates_wavelengths() -> None:
  result = _snapshot().evaluate(
    SPECTRAL_RAY_TRANSFER_V1,
    SpectralRayTransferRequest(
      ray_frame_id='sensor',
      ray_origins_m=((-2.0, 0.0, 0.0),),
      ray_directions=((1.0, 0.0, 0.0),),
      ray_t_min_m=(0.0,),
      ray_t_max_m=(10.0,),
      wavelengths_m=(1.5e-6, 2.5e-6),
    ),
  )

  assert result.hit_mask == (True,)
  assert result.plume_intersection_t_m == ((2.0, 4.0),)
  assert result.optical_depth[0] == pytest.approx((1.5, 3.0))
  assert result.background_transmittance[0] == pytest.approx((exp(-1.5), exp(-3.0)))
  assert result.source_spectral_radiance[0] == pytest.approx((3.0 * (1.0 - exp(-1.5)), 6.0 * (1.0 - exp(-3.0))))
  assert result.metadata.claims.radiation.value == 'gray_approximate'


def test_gray_provider_distinguishes_miss_and_unsupported_capability() -> None:
  snapshot = _snapshot()
  miss = snapshot.evaluate(
    SPECTRAL_RAY_TRANSFER_V1,
    SpectralRayTransferRequest(
      ray_frame_id='sensor',
      ray_origins_m=((-2.0, 2.0, 0.0),),
      ray_directions=((1.0, 0.0, 0.0),),
      ray_t_min_m=(0.0,),
      ray_t_max_m=(10.0,),
      wavelengths_m=(1.0e-6, 2.0e-6),
    ),
  )

  assert miss.hit_mask == (False,)
  assert miss.source_spectral_radiance == ((0.0, 0.0),)
  assert miss.background_transmittance == ((1.0, 1.0),)
  with pytest.raises(UnsupportedProductCapabilityError):
    snapshot.evaluate(
      SPECTRAL_RADIANT_INTENSITY_V1,
      SpectralSignatureRequest(
        direction_frame_id='sensor',
        source_to_observer_directions=((1.0, 0.0, 0.0),),
        wavelengths_m=(1.0e-6, 2.0e-6),
      ),
    )


def test_gray_provider_rejects_frame_and_wavelength_outside_domain() -> None:
  snapshot = _snapshot()
  request = SpectralRayTransferRequest(
    ray_frame_id='wrong-frame',
    ray_origins_m=((-2.0, 0.0, 0.0),),
    ray_directions=((1.0, 0.0, 0.0),),
    ray_t_min_m=(0.0,),
    ray_t_max_m=(10.0,),
    wavelengths_m=(1.0e-6, 2.0e-6),
  )
  with pytest.raises(ProductOutsideApplicabilityError):
    snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)

  outside = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0),),
    ray_directions=((1.0, 0.0, 0.0),),
    ray_t_min_m=(0.0,),
    ray_t_max_m=(10.0,),
    wavelengths_m=(4.0e-6,),
  )
  with pytest.raises(ProductOutsideApplicabilityError):
    snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, outside)


def test_gray_provider_rejects_curved_support_until_curve_transfer_gate_exists() -> None:
  definition = GrayRayTransferDefinition(
      frame_id='sensor',
      support=SectionedTubeSupport(
        frame_id='sensor',
        centers_m=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
        radii_m=(1.0, 1.0, 1.0),
      ),
      wavelengths_m=(1.0e-6, 2.0e-6),
      source_function_w_sr_m=(1.0, 1.0),
      absorption_coefficient_per_m=(1.0, 1.0),
  )
  with pytest.raises(ProviderConfigurationError, match='straight support'):
    GrayRayTransferProvider().create_session(definition=definition)


def test_gray_provider_composes_section_varying_properties_in_ray_order() -> None:
  definition = GrayRayTransferDefinition(
    frame_id='sensor',
    support=SectionedTubeSupport(
      frame_id='sensor',
      centers_m=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
      radii_m=(1.0, 1.0, 1.0),
    ),
    wavelengths_m=(1.0e-6, 2.0e-6),
    source_function_w_sr_m_by_section=((2.0, 2.0), (4.0, 4.0)),
    absorption_coefficient_per_m_by_section=((1.0, 1.0), (1.0, 1.0)),
  )
  snapshot = GrayRayTransferProvider().create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
  request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0), (4.0, 0.0, 0.0)),
    ray_directions=((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
    ray_t_min_m=(0.0, 0.0),
    ray_t_max_m=(10.0, 10.0),
    wavelengths_m=(1.0e-6, 2.0e-6),
  )

  result = snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
  transmission = exp(-1.0)
  assert result.optical_depth == ((2.0, 2.0), (2.0, 2.0))
  assert result.source_spectral_radiance[0] == pytest.approx(
    ((2.0 + 4.0 * transmission) * (1.0 - transmission),) * 2,
  )
  assert result.source_spectral_radiance[1] == pytest.approx(
    ((4.0 + 2.0 * transmission) * (1.0 - transmission),) * 2,
  )
  assert result.metadata.provenance.metadata['optical_property_mode'] == 'piecewise-axial-section'
  assert result.metadata.provenance.metadata['optical_property_section_count'] == '2'


def test_gray_definition_rejects_incomplete_section_properties() -> None:
  support = SectionedTubeSupport(
    frame_id='sensor',
    centers_m=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
    radii_m=(1.0, 1.0),
  )
  with pytest.raises(ProviderConfigurationError, match='either homogeneous or section-varying'):
    GrayRayTransferDefinition(
      frame_id='sensor',
      support=support,
      wavelengths_m=(1.0e-6, 2.0e-6),
    )
  with pytest.raises(ProviderConfigurationError, match='require 1 support sections'):
    GrayRayTransferDefinition(
      frame_id='sensor',
      support=support,
      wavelengths_m=(1.0e-6, 2.0e-6),
      source_function_w_sr_m_by_section=((1.0, 1.0), (2.0, 2.0)),
      absorption_coefficient_per_m_by_section=((1.0, 1.0), (1.0, 1.0)),
    )
  with pytest.raises(ProviderConfigurationError, match='advance along the support axis'):
    GrayRayTransferDefinition(
      frame_id='sensor',
      support=SectionedTubeSupport(
        frame_id='sensor',
        centers_m=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.0, 0.0)),
        radii_m=(1.0, 1.0, 1.0),
      ),
      wavelengths_m=(1.0e-6, 2.0e-6),
      source_function_w_sr_m_by_section=((1.0, 1.0), (2.0, 2.0)),
      absorption_coefficient_per_m_by_section=((1.0, 1.0), (1.0, 1.0)),
    )
