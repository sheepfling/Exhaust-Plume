from __future__ import annotations

from dataclasses import replace

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocAmbientShockBoundaryMarchStatus,
  MocAmbientShockStripStatus,
  assemble_ambient_shock_characteristic_strip,
  march_post_shock_ambient_boundary,
  solve_marched_attached_shock_field,
)


def _shock_reference():
  result = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.1,
      mach=2.0,
      gamma=1.4,
    ),
    lambda _point: 2.0e6,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )
  assert result.converged
  assert result.shock_fit is not None
  return result.shock_fit


def _ambient_pressure(shock_fit) -> float:
  sample = shock_fit.boundary_states[0]
  state = sample.state
  return sample.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))


def test_shock_sourced_ambient_march_closes_the_boundary_conditions() -> None:
  shock_fit = _shock_reference()
  result = march_post_shock_ambient_boundary(
    shock_fit,
    _ambient_pressure(shock_fit),
  )

  assert result.status is MocAmbientShockBoundaryMarchStatus.CONVERGED
  assert result.converged
  assert len(result.boundary_samples) == 9
  assert result.ambient_boundary.converged
  assert result.maximum_absolute_pressure_residual is not None
  assert result.maximum_absolute_pressure_residual < 1.0e-8
  assert result.maximum_absolute_invariant_residual is not None
  assert result.maximum_absolute_invariant_residual < 1.0e-8


def test_shock_and_ambient_characteristic_strip_keeps_terminal_trace_open() -> None:
  shock_fit = _shock_reference()
  march = march_post_shock_ambient_boundary(
    shock_fit,
    _ambient_pressure(shock_fit),
  )
  strip = assemble_ambient_shock_characteristic_strip(
    shock_fit,
    march.boundary_samples,
    _ambient_pressure(shock_fit),
  )

  assert strip.status is MocAmbientShockStripStatus.CONVERGED_OPEN
  assert strip.converged
  assert strip.node_count == 45
  assert strip.cell_count == 44
  assert strip.topology.connected
  assert strip.topology.forms_closed_zone
  assert strip.topology.nonmanifold_edge_count == 0
  assert strip.physical_closure_verified is False
  assert strip.chain_promotion_blocked is True
  assert len(strip.terminal_trace_points_m) == 10
  assert strip.as_report()['source_families'] == {'shock': 'C+', 'ambient': 'C-'}


def test_ambient_strip_rejects_a_boundary_trace_with_wrong_family_geometry() -> None:
  shock_fit = _shock_reference()
  ambient_pressure = _ambient_pressure(shock_fit)
  march = march_post_shock_ambient_boundary(shock_fit, ambient_pressure)
  assert march.converged
  samples = list(march.boundary_samples)
  samples[3] = replace(
    samples[3],
    state=replace(samples[3].state, theta_rad=samples[3].state.theta_rad + 0.02),
  )

  result = assemble_ambient_shock_characteristic_strip(
    shock_fit,
    tuple(samples),
    ambient_pressure,
  )

  assert result.status is not MocAmbientShockStripStatus.CONVERGED_OPEN
  assert not result.converged
  assert 'ambient boundary' in result.message


def test_ambient_boundary_march_requires_a_compatible_attachment_state() -> None:
  shock_fit = _shock_reference()
  first = shock_fit.boundary_states[0].state
  result = march_post_shock_ambient_boundary(
    shock_fit,
    _ambient_pressure(shock_fit),
    seed_boundary_state=replace(first, theta_rad=first.theta_rad + 0.01),
  )

  assert result.status is MocAmbientShockBoundaryMarchStatus.SEED_FAILURE
  assert not result.converged
  assert 'attachment state' in result.message
