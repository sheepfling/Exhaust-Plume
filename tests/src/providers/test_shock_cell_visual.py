from __future__ import annotations

import json
from pathlib import Path

import pytest

from exhaust_plume import (
  AmbientInput,
  CaloricallyPerfectGas,
  NozzleExitInput,
  VISUAL_SECTIONED_TUBE_V1,
  VisualSampling,
  VisualSectionedTubeRequest,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.contracts import (
  Pose,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
)
from exhaust_plume.contracts.errors import (
  InvalidProductRequestError,
  OperatingStateDomainError,
  ProviderClosedError,
)
from exhaust_plume.providers import (
  ShockCellVisualDefinition,
  ShockCellVisualProvider,
)

ROOT = Path(__file__).resolve().parents[3]
_POSE = Pose(
  frame_id='world',
  translation_m=(0.0, 0.0, 0.0),
  rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
)


def _state(exit_to_ambient_pressure_ratio: float):
  values = json.loads(
    (ROOT / 'tests/fixtures/physics/first_mvp_regression_v1.json').read_text(encoding='utf-8')
  )['gas']
  gas = CaloricallyPerfectGas.dry_air(gamma=values['gamma'])
  factor = 1.0 + (gas.gamma - 1.0) * values['mach']**2 / 2.0
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=values['mach'],
      total_pressure_Pa=values['ambient_pressure_Pa'] * exit_to_ambient_pressure_ratio * factor**(
        gas.gamma / (gas.gamma - 1.0)
      ),
      total_temperature_K=values['total_temperature_K'],
      exit_radius_m=values['exit_radius_m'],
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(
      pressure_Pa=values['ambient_pressure_Pa'],
      temperature_K=values['ambient_temperature_K'],
    ),
    gas,
  )
  return exit_state, ambient
####


def _request(*, maximum_axial_extent_m: float | None = 8.0) -> VisualSectionedTubeRequest:
  return VisualSectionedTubeRequest(
    output_frame_id='straight-axisymmetric-xr',
    sampling=VisualSampling(
      maximum_section_count=16,
      maximum_axial_extent_m=maximum_axial_extent_m,
    ),
    requested_channels=('core_radius_fraction', 'opacity_weight'),
  )
####


def _snapshot(ratio: float):
  exit_state, ambient = _state(ratio)
  session = ShockCellVisualProvider().create_session(
    definition=ShockCellVisualDefinition(nozzle_radius_m=1.0),
  )
  snapshot = session.create_snapshot(
    time_s=0.0,
    source_pose=_POSE,
    dynamic_state={'nozzle_exit': exit_state},
    ambient_state={'ambient': ambient},
  )
  return session, snapshot
####


def test_shock_cell_visual_provider_uses_only_the_canonical_visual_capability() -> None:
  provider = ShockCellVisualProvider()
  assert provider.descriptor.supported_capabilities == (VISUAL_SECTIONED_TUBE_CAPABILITY,)
  assert provider.descriptor.provider_id == 'plume.shock-cell-analytical'
####


@pytest.mark.parametrize(
  ('ratio', 'expected_radius'),
  ((1.0, 1.0), (1.2, None), (0.85, None)),
)
def test_shock_cell_visual_provider_returns_canonical_sections(
  ratio: float,
  expected_radius: float | None,
) -> None:
  _, snapshot = _snapshot(ratio)
  result = snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, _request())
  assert result.metadata.capability == VISUAL_SECTIONED_TUBE_CAPABILITY
  assert result.metadata.provenance.provider_id == 'plume.shock-cell-analytical'
  assert result.metadata.claims.radiation.value == 'appearance_only'
  assert len(result.sections) == 16
  if expected_radius is not None:
    assert {section.radius_major_m for section in result.sections} == {expected_radius}
  else:
    assert result.summary.length_m <= 8.0 + 1.0e-12
  ####
####


def test_shock_cell_matched_flow_requires_an_explicit_visual_extent() -> None:
  _, snapshot = _snapshot(1.0)
  with pytest.raises(InvalidProductRequestError, match='maximum_axial_extent_m'):
    snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, _request(maximum_axial_extent_m=None))
  ####
####


def test_shock_cell_visual_session_enforces_operating_state_and_close() -> None:
  session, _ = _snapshot(1.0)
  exit_state, ambient = _state(1.0)
  with pytest.raises(OperatingStateDomainError, match='radius'):
    session.create_snapshot(
      time_s=0.0,
      source_pose=_POSE,
      dynamic_state={'nozzle_exit': exit_state.model_copy(update={'radius_m': 2.0})},
      ambient_state={'ambient': ambient},
    )
  ####
  session.close()
  with pytest.raises(ProviderClosedError):
    session.create_snapshot(
      time_s=0.0,
      source_pose=_POSE,
      dynamic_state={'nozzle_exit': exit_state},
      ambient_state={'ambient': ambient},
    )
  ####
####


def test_shock_cell_visual_provider_rejects_outside_model_states() -> None:
  with pytest.raises(OperatingStateDomainError, match='exceeds attached maximum'):
    _snapshot(0.1)
  ####
####
