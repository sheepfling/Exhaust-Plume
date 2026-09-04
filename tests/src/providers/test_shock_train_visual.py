from __future__ import annotations

import pytest

from exhaust_plume import (
  AmbientInput,
  CaloricallyPerfectGas,
  NozzleExitInput,
  Pose,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VISUAL_SECTIONED_TUBE_V1,
  VisualSampling,
  VisualSectionedTubeRequest,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.contracts.errors import InvalidProductRequestError, ProviderConfigurationError
from exhaust_plume.models.shock_train import ShockTrainCalibration, ShockTrainTerminationPolicy
from exhaust_plume.providers import (
  ShockTrainVisualConfiguration,
  ShockTrainVisualDefinition,
  ShockTrainVisualProvider,
)


_POSE = Pose(
  frame_id='world',
  translation_m=(0.0, 0.0, 0.0),
  rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
)


def _states(*, matched: bool = False):
  gas = CaloricallyPerfectGas.dry_air()
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=101325.0, temperature_K=300.0),
    gas,
  )
  mach = 1.000001
  pressure_factor = 1.0 + (gas.gamma - 1.0) * mach**2 / 2.0
  static_ratio = 1.0 if matched else 1.2
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=mach,
      total_pressure_Pa=ambient.pressure_Pa * static_ratio * pressure_factor ** (gas.gamma / (gas.gamma - 1.0)),
      total_temperature_K=300.0,
      exit_radius_m=0.019,
    ),
    gas,
  )
  return exit_state, ambient
####


def _configuration() -> ShockTrainVisualConfiguration:
  return ShockTrainVisualConfiguration(
    calibration=ShockTrainCalibration(
      calibration_id='provider-test-v1',
      source_description='provider unit-test engineering seed; not external calibration',
      applicable_mach_range=(1.0, 2.0),
      applicable_pressure_ratio_range=(1.0, 10.0),
      applicable_temperature_ratio_range=(0.1, 10.0),
      mixing_layer_growth_rate=0.01,
      pressure_amplitude_decay_coefficient=0.3,
      cell_spacing_coefficient=1.306,
      finite_shear_layer_spacing_correction=0.5,
      total_pressure_loss_coefficient=0.02,
      mean_pressure_relaxation_coefficient=0.2,
    ),
    termination_policy=ShockTrainTerminationPolicy(max_cells=100, max_axial_distance_m=10.0),
  )
####


def _snapshot(*, matched: bool = False):
  exit_state, ambient = _states(matched=matched)
  session = ShockTrainVisualProvider(configuration=_configuration()).create_session(
    definition=ShockTrainVisualDefinition(nozzle_radius_m=0.019),
  )
  snapshot = session.create_snapshot(
    time_s=0.0,
    source_pose=_POSE,
    dynamic_state={'nozzle_exit': exit_state},
    ambient_state={'ambient': ambient},
  )
  return session, snapshot
####


def _request(*, maximum_axial_extent_m: float | None = None) -> VisualSectionedTubeRequest:
  return VisualSectionedTubeRequest(
    output_frame_id='straight-axisymmetric-xr',
    sampling=VisualSampling(
      maximum_section_count=16,
      maximum_axial_extent_m=maximum_axial_extent_m,
    ),
    requested_channels=('core_radius_fraction', 'opacity_weight', 'shock_weight'),
  )
####


def test_reduced_order_provider_is_visual_only_and_requires_explicit_calibration() -> None:
  provider = ShockTrainVisualProvider()
  assert provider.descriptor.supported_capabilities == (VISUAL_SECTIONED_TUBE_CAPABILITY,)
  assert 'fidelity profile: shock-cell-reduced-order-v1' in provider.descriptor.notes
  session = provider.create_session(definition=ShockTrainVisualDefinition(nozzle_radius_m=0.019))
  exit_state, ambient = _states()
  with pytest.raises(ProviderConfigurationError, match='explicit ShockTrainCalibration'):
    session.create_snapshot(
      time_s=0.0,
      source_pose=_POSE,
      dynamic_state={'nozzle_exit': exit_state},
      ambient_state={'ambient': ambient},
    )
  ####
####


def test_reduced_order_provider_exposes_scaled_train_with_claim_ceiling() -> None:
  _, snapshot = _snapshot()
  result = snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, _request())
  assert result.metadata.capability == VISUAL_SECTIONED_TUBE_CAPABILITY
  assert result.metadata.provenance.provider_id == 'plume.shock-train-reduced-order'
  assert result.metadata.claims.geometry.value == 'engineering_approximate'
  assert result.metadata.claims.radiation.value == 'appearance_only'
  assert any('not resolved MOC' in warning for warning in result.metadata.warnings)
  assert len(result.sections) == 16
  assert result.summary.length_m > 0.0
  assert set(result.channels) == {'core_radius_fraction', 'opacity_weight', 'shock_weight'}
####


def test_visual_extent_clips_the_train_without_relabeling_termination() -> None:
  _, snapshot = _snapshot()
  result = snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, _request(maximum_axial_extent_m=0.05))
  assert result.summary.length_m <= 0.05 + 1.0e-12
  assert result.sections[-1].arc_length_m <= 0.05 + 1.0e-12
####


def test_matched_flow_requires_a_consumer_display_extent() -> None:
  _, snapshot = _snapshot(matched=True)
  with pytest.raises(InvalidProductRequestError, match='maximum_axial_extent_m'):
    snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, _request())
  ####
  result = snapshot.evaluate(
    VISUAL_SECTIONED_TUBE_V1,
    _request(maximum_axial_extent_m=0.1),
  )
  assert result.summary.length_m == pytest.approx(0.1)
  assert {section.radius_major_m for section in result.sections} == {0.019}
####
