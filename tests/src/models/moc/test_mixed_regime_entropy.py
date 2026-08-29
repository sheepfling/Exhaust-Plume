from dataclasses import replace
from math import log

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocMixedRegimeEntropyHandoffStatus,
  MocMixedRegimePerimeterRequest,
  MocPostShockBoundaryState,
  build_mixed_regime_entropy_handoff,
  solve_normal_shock_terminal,
)
from exhaust_plume.validation.moc_measurements import (
  MocMixedRegimeEntropyHandoffMeasurementStatus,
  measure_mixed_regime_entropy_handoff,
)


def _request() -> MocMixedRegimePerimeterRequest:
  terminal = solve_normal_shock_terminal(
    CharacteristicState(
      x_m=1.0,
      y_m=0.0,
      theta_rad=0.0,
      mach=2.0,
      gamma=1.4,
    ),
    upstream_pressure_Pa=100000.0,
  )
  return MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal.shock_point_m,
    terminal_downstream_mach=terminal.downstream_mach,
    terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
    terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
    terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    terminal_total_pressure_ratio=terminal.total_pressure_ratio,
    supersonic_patch=(
      MocPostShockBoundaryState(
        point_m=(0.8, 0.2),
        state=CharacteristicState(
          x_m=0.8,
          y_m=0.2,
          theta_rad=0.1,
          mach=2.0,
          gamma=1.4,
        ),
        upstream_total_pressure_Pa=2.0e6,
        downstream_total_pressure_Pa=1.8e6,
      ),
      MocPostShockBoundaryState(
        point_m=(0.9, 0.1),
        state=CharacteristicState(
          x_m=0.9,
          y_m=0.1,
          theta_rad=0.05,
          mach=2.0,
          gamma=1.4,
        ),
        upstream_total_pressure_Pa=2.0e6,
        downstream_total_pressure_Pa=1.75e6,
      ),
    ),
  )


def test_entropy_handoff_carries_patch_and_terminal_loss_without_subsonic_state() -> None:
  request = _request()

  handoff = build_mixed_regime_entropy_handoff(request)

  assert handoff.status is MocMixedRegimeEntropyHandoffStatus.CONVERGED
  assert handoff.converged
  assert handoff.sample_count == 3
  assert handoff.terminal_sample_index == 2
  assert handoff.interface_geometry_verified
  assert handoff.terminal_seam_verified
  assert handoff.shock_loss_verified
  assert handoff.entropy_transport_verified
  assert handoff.physical_closure_verified is False
  assert handoff.canonical_free_boundary_verified is False
  assert handoff.chain_promotion_blocked
  assert handoff.production_claim_allowed is False
  assert all(
    second > first
    for first, second in zip(
      handoff.cumulative_arc_length_m[:-1],
      handoff.cumulative_arc_length_m[1:],
      strict=True,
    )
  )
  assert handoff.samples[0].entropy_production_nondimensional == pytest.approx(
    log(2.0e6 / 1.8e6)
  )
  assert handoff.total_pressure_at_arc_length(
    handoff.cumulative_arc_length_m[-1]
  ) == pytest.approx(request.terminal_downstream_total_pressure_Pa)
  with pytest.raises(ValueError, match='extrapolation'):
    handoff.total_pressure_at_arc_length(-1.0e-6)

  assert request.entropy_handoff() == handoff


def test_entropy_handoff_is_measured_from_the_exact_request() -> None:
  request = _request()
  handoff = build_mixed_regime_entropy_handoff(request)

  measurement = measure_mixed_regime_entropy_handoff(request, handoff)

  assert measurement.status is MocMixedRegimeEntropyHandoffMeasurementStatus.CONVERGED
  assert measurement.converged
  assert measurement.handoff_verified
  assert measurement.request_verified
  assert measurement.sample_count == 3
  assert measurement.expected_sample_count == 3
  assert measurement.interface_geometry_verified
  assert measurement.terminal_seam_verified
  assert measurement.shock_loss_verified
  assert measurement.entropy_profile_verified
  assert measurement.handoff_metrics_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_entropy_measurement_rejects_changed_pressure_lineage() -> None:
  request = _request()
  handoff = build_mixed_regime_entropy_handoff(request)
  changed_sample = replace(
    handoff.samples[0],
    downstream_total_pressure_Pa=1.7e6,
  )
  changed_handoff = replace(
    handoff,
    samples=(changed_sample, *handoff.samples[1:]),
  )

  measurement = measure_mixed_regime_entropy_handoff(request, changed_handoff)

  assert measurement.status is MocMixedRegimeEntropyHandoffMeasurementStatus.SAMPLE_FAILURE
  assert not measurement.converged
  assert not measurement.handoff_verified
