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
  solve_first_cell_from_exit_state,
)
from exhaust_plume.contracts import (
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VisualProviderConformanceReport,
  run_visual_provider_conformance,
)
from exhaust_plume.contracts.errors import (
  InvalidProductRequestError,
  OperatingStateDomainError,
  ProductOutsideApplicabilityError,
  ProviderClosedError,
)
from exhaust_plume.models.shock_cells import ShockCellSolveConfig, SolverStatus
from exhaust_plume.providers import (
  StraightAnalyticalDefinition,
  StraightAnalyticalOperatingState,
  StraightAnalyticalProvider,
)

ROOT = Path(__file__).resolve().parents[3]


def _fixture() -> dict:
  return json.loads((ROOT / 'tests/fixtures/physics/first_mvp_regression_v1.json').read_text(encoding='utf-8'))
####


def _state(exit_to_ambient_pressure_ratio: float) -> StraightAnalyticalOperatingState:
  values = _fixture()['gas']
  gas = CaloricallyPerfectGas.dry_air(gamma=values['gamma'])
  factor = 1.0 + (gas.gamma - 1.0) * values['mach']**2 / 2.0
  total_pressure = values['ambient_pressure_Pa'] * exit_to_ambient_pressure_ratio * factor**(
    gas.gamma / (gas.gamma - 1.0)
  )
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=values['mach'],
      total_pressure_Pa=total_pressure,
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
  return StraightAnalyticalOperatingState(nozzle_exit=exit_state, ambient=ambient)
####


def _request(*, maximum_axial_extent_m: float | None = 8.0) -> VisualSectionedTubeRequest:
  return VisualSectionedTubeRequest(
    output_frame_id='source-local',
    sampling=VisualSampling(
      maximum_section_count=16,
      maximum_axial_extent_m=maximum_axial_extent_m,
    ),
    requested_channels=('core_radius_fraction', 'opacity_weight'),
  )
####


def _snapshot(ratio: float):
  provider = StraightAnalyticalProvider()
  session = provider.create_session(definition=StraightAnalyticalDefinition(nozzle_radius_m=1.0))
  return provider, session, session.snapshot(_state(ratio))
####


def test_analytical_provider_advertises_visual_only_common_capability() -> None:
  provider = StraightAnalyticalProvider()
  assert provider.descriptor.supported_capabilities == (VISUAL_SECTIONED_TUBE_CAPABILITY,)
  assert provider.descriptor.provider_id == 'plume.straight-analytical'
  assert provider.descriptor.deterministic is True
####


def test_first_cell_boundary_uses_physically_classified_pressure_ratios() -> None:
  state = _state(1.2)
  solution = solve_first_cell_from_exit_state(
    state.nozzle_exit,
    state.ambient,
    ShockCellSolveConfig(exit=state.nozzle_exit, ambient=state.ambient, max_cells=1),
  )
  assert solution.regime.value == 'underexpanded'
  assert solution.zones
  assert solution.status is SolverStatus.CONVERGED_AT_BOUNDARY
####


@pytest.mark.parametrize('ratio, expected_regime', ((1.0, 'matched'), (1.2, 'underexpanded'), (0.85, 'overexpanded')))
def test_provider_returns_matched_underexpanded_and_overexpanded_visuals(
    ratio: float,
    expected_regime: str,
) -> None:
  _, _, snapshot = _snapshot(ratio)
  result = snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, _request())
  assert result.metadata.capability == VISUAL_SECTIONED_TUBE_CAPABILITY
  assert result.metadata.applicability.status.value == 'marginal'
  assert len(result.sections) == 16
  assert result.metadata.provenance.provider_id == 'plume.straight-analytical'
  assert result.metadata.claims.radiation.value == 'appearance_only'
  if expected_regime == 'matched':
    assert result.summary.length_m == pytest.approx(8.0)
    assert {section.radius_major_m for section in result.sections} == {1.0}
  else:
    assert result.summary.length_m <= 8.0 + 1.0e-12
  ####
####


def test_matched_flow_requires_an_explicit_visual_axial_domain() -> None:
  _, _, snapshot = _snapshot(1.0)
  with pytest.raises(InvalidProductRequestError, match='maximum_axial_extent_m'):
    snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, _request(maximum_axial_extent_m=None))
  ####
####


def test_analytical_provider_runs_the_reusable_conformance_harness() -> None:
  def snapshot_factory():
    return _snapshot(1.2)[2]
  ####

  provider = StraightAnalyticalProvider()
  report = run_visual_provider_conformance(provider.descriptor, snapshot_factory, _request())
  assert isinstance(report, VisualProviderConformanceReport)
  assert report.passed is True
  assert report.deterministic_serialization is True
  assert set(report.unsupported_capabilities) == {
    'plume.signature.spectral-radiant-intensity@1',
    'plume.optical.spectral-ray-transfer@1',
  }
####


def test_analytical_provider_rejects_strong_overexpanded_state_structurally() -> None:
  _, _, snapshot = _snapshot(0.1)
  with pytest.raises(ProductOutsideApplicabilityError, match='outside the visual provider applicability domain'):
    snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, _request())
  ####
####


def test_analytical_provider_enforces_definition_and_session_boundaries() -> None:
  _, session, _ = _snapshot(1.0)
  wrong_state = _state(1.0)
  wrong_state = StraightAnalyticalOperatingState(
    nozzle_exit=wrong_state.nozzle_exit.model_copy(update={'radius_m': 2.0}),
    ambient=wrong_state.ambient,
  )
  with pytest.raises(OperatingStateDomainError, match='radius'):
    session.snapshot(wrong_state)
  ####
  session.close()
  with pytest.raises(ProviderClosedError):
    session.snapshot(_state(1.0))
  ####
####
