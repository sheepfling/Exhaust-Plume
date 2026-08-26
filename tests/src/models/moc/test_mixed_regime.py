from dataclasses import replace

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocMixedRegimeBoundaryStatus,
  MocMixedRegimeClosureStatus,
  MocMixedRegimeFieldStatus,
  MocMixedRegimeFieldSample,
  MocMixedRegimePerimeterRequest,
  MocPostShockBoundaryState,
  run_mixed_regime_closure_solver,
  solve_normal_shock_terminal,
  solve_mixed_regime_subsonic_field,
  validate_mixed_regime_boundary,
)


def _terminal():
  return solve_normal_shock_terminal(
    CharacteristicState(
      x_m=1.0,
      y_m=0.0,
      theta_rad=0.0,
      mach=2.0,
      gamma=1.4,
    ),
    upstream_pressure_Pa=100000.0,
  )


def _supersonic_patch():
  return (
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
      downstream_total_pressure_Pa=1.8e6,
    ),
  )


def _samples(terminal, *, interior_total_pressure: float | None = None):
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None
  gamma = terminal.upstream_state.gamma
  points = ((1.0, 0.0), (1.1, 0.1), (1.2, 0.1), (1.2, 0.0), (1.0, 0.0))
  return tuple(
    MocMixedRegimeFieldSample(
      point_m=point,
      mach=terminal.downstream_mach,
      flow_angle_rad=terminal.downstream_flow_angle_rad,
      static_pressure_Pa=terminal.downstream_pressure_Pa,
      total_pressure_Pa=(
        terminal.downstream_total_pressure_Pa
        if index in (0, len(points) - 1) or interior_total_pressure is None
        else interior_total_pressure
      ),
      gamma=gamma,
    )
    for index, point in enumerate(points)
  )


def test_scalar_mixed_regime_boundary_handoff_is_valid_but_not_field_closure() -> None:
  terminal = _terminal()
  result = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )

  assert result.status is MocMixedRegimeBoundaryStatus.CONVERGED_BOUNDARY_HANDOFF
  assert result.converged
  assert result.supersonic_patch_verified
  assert result.terminal_continuity_verified
  assert result.perimeter_geometry_verified
  assert result.total_pressure_lineage_verified
  assert result.mixed_regime_field_complete is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked


def test_elliptic_subsonic_reference_field_closes_only_its_declared_mesh_model() -> None:
  terminal = _terminal()
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )

  field = solve_mixed_regime_subsonic_field(boundary)

  assert field.status is MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD
  assert field.converged
  assert field.node_count == 5
  assert field.cell_count == 4
  assert field.topology.forms_closed_zone
  assert field.topology.nonmanifold_edge_count == 0
  assert field.physical_closure_verified
  assert field.mixed_regime_field_complete
  assert field.chain_promotion_blocked
  assert field.model == 'elliptic-isentropic-subsonic-reference'


def test_mixed_regime_closure_callback_requires_the_exact_terminal_seam() -> None:
  terminal = _terminal()
  boundary = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(terminal),
  )
  field = solve_mixed_regime_subsonic_field(boundary)
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  request = MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal.shock_point_m,
    terminal_downstream_mach=terminal.downstream_mach,
    terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
    terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
    terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
    terminal_total_pressure_ratio=terminal.total_pressure_ratio,
    supersonic_patch=_supersonic_patch(),
  )
  seen: list[MocMixedRegimePerimeterRequest] = []

  result = run_mixed_regime_closure_solver(
    request,
    lambda received: (seen.append(received) or field),
  )

  assert result.status is MocMixedRegimeClosureStatus.CONVERGED
  assert result.converged
  assert result.physical_closure_verified
  assert seen == [request]

  other_terminal = solve_normal_shock_terminal(
    CharacteristicState(2.0, 0.0, 0.0, 2.0, 1.4),
    upstream_pressure_Pa=100000.0,
  )
  other_boundary = validate_mixed_regime_boundary(
    other_terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(other_terminal),
  )
  mismatched = replace(field, boundary=other_boundary)
  mismatch_result = run_mixed_regime_closure_solver(request, lambda _request: mismatched)
  assert mismatch_result.status is MocMixedRegimeClosureStatus.SEAM_FAILURE
  assert not mismatch_result.converged


def test_mixed_regime_perimeter_request_rejects_inconsistent_terminal_scalars() -> None:
  terminal = _terminal()
  assert terminal.shock_point_m is not None
  assert terminal.downstream_mach is not None
  assert terminal.downstream_flow_angle_rad is not None
  assert terminal.downstream_pressure_Pa is not None
  assert terminal.downstream_total_pressure_Pa is not None
  assert terminal.total_pressure_ratio is not None

  with pytest.raises(ValueError, match='does not match the terminal shock result'):
    MocMixedRegimePerimeterRequest(
      terminal=terminal,
      terminal_point_m=terminal.shock_point_m,
      terminal_downstream_mach=terminal.downstream_mach,
      terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
      terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa + 1.0,
      terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
      terminal_total_pressure_ratio=terminal.total_pressure_ratio,
      supersonic_patch=_supersonic_patch(),
    )


def test_mixed_regime_boundary_rejects_missing_scalar_field() -> None:
  result = validate_mixed_regime_boundary(
    _terminal(),
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=(),
  )

  assert result.status is MocMixedRegimeBoundaryStatus.SUBSONIC_FIELD_FAILURE
  assert not result.converged
  assert result.supersonic_patch_verified
  assert result.chain_promotion_blocked


def test_mixed_regime_boundary_rejects_total_pressure_gain() -> None:
  terminal = _terminal()
  assert terminal.downstream_total_pressure_Pa is not None
  result = validate_mixed_regime_boundary(
    terminal,
    _supersonic_patch(),
    supersonic_patch_converged=True,
    subsonic_samples=_samples(
      terminal,
      interior_total_pressure=terminal.downstream_total_pressure_Pa * 1.1,
    ),
  )

  assert result.status is MocMixedRegimeBoundaryStatus.PRESSURE_FAILURE
  assert not result.converged
  assert result.terminal_continuity_verified
  assert not result.total_pressure_lineage_verified
