from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from exhaust_plume import (
  AmbientInput,
  NozzleValidityCase,
  ThroatConfiguration,
  NozzleGeometry,
  StudyValidityEnvelope,
  default_pressure_sweep,
  default_validity_cases,
  evaluate_nozzle_case,
  evaluate_validity_matrix,
  write_validity_report_csv,
  write_validity_report_json,
)
from exhaust_plume.contracts import ApplicabilityStatus
from exhaust_plume.models.gas import CaloricallyPerfectGas


def _case(*, ambient_pressure_Pa: float = 101325.0, case_id: str = 'case') -> NozzleValidityCase:
  return NozzleValidityCase(
    case_id=case_id,
    geometry=NozzleGeometry(
      geometry_id='test-geometry',
      throat=ThroatConfiguration(area_m2=1.0e-2, profile_id='test-throat'),
      exit_area_m2=9.0e-2,
    ),
    total_pressure_Pa=20.0 * 101325.0,
    total_temperature_K=800.0,
    ambient_pressure_Pa=ambient_pressure_Pa,
    ambient_temperature_K=300.0,
    gas=CaloricallyPerfectGas.dry_air(gamma=1.4),
  )


@pytest.mark.parametrize('ambient_pressure_Pa', default_pressure_sweep())
def test_pressure_sweep_is_explicit_and_near_vacuum_is_not_silently_valid(ambient_pressure_Pa: float) -> None:
  result = evaluate_nozzle_case(_case(ambient_pressure_Pa=ambient_pressure_Pa, case_id=f'p-{ambient_pressure_Pa:g}'))
  assert result.ambient_pressure_Pa == ambient_pressure_Pa
  assert result.exit_mach is not None
  if ambient_pressure_Pa <= 1.0:
    assert result.validity_status is ApplicabilityStatus.OUTSIDE
    assert result.solver_status is not None
  else:
    assert result.validity_status in (ApplicabilityStatus.MARGINAL, ApplicabilityStatus.OUTSIDE)


def test_exact_vacuum_is_rejected_by_continuum_ambient_contract() -> None:
  with pytest.raises(ValidationError):
    AmbientInput(pressure_Pa=0.0, temperature_K=300.0)


def test_default_matrix_varies_geometry_pressure_gamma_and_temperature() -> None:
  cases = default_validity_cases()
  results = evaluate_validity_matrix(cases)
  assert len(cases) == 15
  assert len(results) == len(cases)
  assert {result.geometry_id for result in results} == {
    'small-throat-area-ratio-4',
    'medium-throat-area-ratio-9',
    'large-throat-area-ratio-25',
  }
  assert {result.ambient_pressure_Pa for result in results} == set(default_pressure_sweep())
  assert {result.gamma for result in results} == {1.2, 1.4, 1.67}
  assert {result.total_temperature_K for result in results} == {500.0, 800.0, 1500.0}
  assert any(result.validity_status is ApplicabilityStatus.MARGINAL for result in results)
  assert any(result.validity_status is ApplicabilityStatus.OUTSIDE for result in results)


def test_validity_matrix_rejects_duplicate_case_ids_and_writes_reports(tmp_path: Path) -> None:
  case = _case(case_id='duplicate')
  with pytest.raises(ValueError, match='unique'):
    evaluate_validity_matrix((case, case))
  result = evaluate_nozzle_case(case)
  json_path = write_validity_report_json((result,), tmp_path / 'validity.json')
  csv_path = write_validity_report_csv((result,), tmp_path / 'validity.csv')
  assert 'plume.study-validity-report@1' in json_path.read_text(encoding='utf-8')
  assert csv_path.read_text(encoding='utf-8').count('\n') == 2


def test_custom_envelope_can_make_a_boundary_explicit() -> None:
  envelope = StudyValidityEnvelope(
    min_ambient_pressure_Pa=100.0,
    marginal_ambient_pressure_low_Pa=200.0,
    marginal_ambient_pressure_high_Pa=900000.0,
  )
  result = evaluate_nozzle_case(_case(ambient_pressure_Pa=101325.0), envelope=envelope)
  assert result.validity_status in (ApplicabilityStatus.MARGINAL, ApplicabilityStatus.OUTSIDE)
