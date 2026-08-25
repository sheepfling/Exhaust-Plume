"""Reduced-order finite coherent shock-train solver.

The first cell remains the resolved input.  Downstream cells are explicitly
scaled reduced-order geometry with closure parameters and never masquerade as
new MOC solutions.
"""

from __future__ import annotations

from math import exp, isfinite, sqrt
from typing import Any

import numpy as np

from exhaust_plume.contracts.termination import TerminationReason, TerminationReport
from exhaust_plume.models.shock_cells.contracts import ClosedZone, ShockCellSolveResult, SolverStatus
from exhaust_plume.models.shock_train.contracts import (
  GeometryFidelity,
  ShockCellMetrics,
  ShockTrainCalibration,
  ShockTrainCell,
  ShockTrainResult,
  ShockTrainStatus,
  ShockTrainTerminationPolicy,
)
from exhaust_plume.util.aero.flow_state import FlowState

__all__ = ('solve_shock_train',)


def _expanded_mach(total_pressure_Pa: float, ambient_pressure_Pa: float, gamma: float) -> float:
  pressure_ratio = total_pressure_Pa / ambient_pressure_Pa
  if pressure_ratio <= 1.0:
    return 0.0
  term = 2.0 / (gamma - 1.0) * (
    pressure_ratio ** ((gamma - 1.0) / gamma) - 1.0
  )
  return sqrt(max(0.0, term))
####


def _first_cell_metrics(first_cell: ShockCellSolveResult) -> ShockCellMetrics | None:
  zones = first_cell.zones
  if not zones:
    return None
  start_x_m = min(float(zone.vertices_xr_m[:, 0].min()) for zone in zones)
  end_x_m = max(float(zone.vertices_xr_m[:, 0].max()) for zone in zones)
  length_m = end_x_m - start_x_m
  if length_m <= 0.0:
    return None
  pressures = [float(zone.flow.static_pressure) for zone in zones]
  maximum_pressure_Pa = max(pressures)
  minimum_pressure_Pa = min(pressures)
  mean_pressure_Pa = sum(pressures) / len(pressures)
  ambient_pressure_Pa = first_cell.ambient.pressure_Pa
  core_diameter_m = 2.0 * max(
    float(np.abs(zone.vertices_xr_m[:, 1]).max())
    for zone in zones
  )
  inlet_total_pressure_Pa = float(first_cell.exit_state.total_pressure_Pa)
  zone_total_pressures = [float(zone.flow.total_pressure) for zone in zones]
  outlet_total_pressure_Pa = min(inlet_total_pressure_Pa, min(zone_total_pressures))
  return ShockCellMetrics(
    cell_index=1,
    start_x_m=max(0.0, start_x_m),
    end_x_m=max(0.0, end_x_m),
    length_m=length_m,
    effective_core_diameter_m=core_diameter_m,
    # The train closure uses the fully-expanded core Mach derived from the
    # inlet total pressure.  This remains distinct from a near-sonic
    # convergent-nozzle exit surrogate used by the current first-cell solver.
    core_mach=_expanded_mach(
      inlet_total_pressure_Pa,
      ambient_pressure_Pa,
      first_cell.exit_state.gas.gamma,
    ),
    mean_pressure_Pa=mean_pressure_Pa,
    maximum_pressure_Pa=maximum_pressure_Pa,
    minimum_pressure_Pa=minimum_pressure_Pa,
    pressure_oscillation_ratio=(maximum_pressure_Pa - minimum_pressure_Pa) / (2.0 * ambient_pressure_Pa),
    mean_pressure_residual=(mean_pressure_Pa - ambient_pressure_Pa) / ambient_pressure_Pa,
    inlet_total_pressure_Pa=inlet_total_pressure_Pa,
    outlet_total_pressure_Pa=outlet_total_pressure_Pa,
    geometry_fidelity=GeometryFidelity.RESOLVED_FIRST_CELL,
  )
####


def _termination_result(
    *,
    cells: tuple[ShockTrainCell, ...],
    reason: TerminationReason,
    is_physical: bool,
    message: str,
    status: ShockTrainStatus,
    calibration: ShockTrainCalibration,
    was_domain_truncated: bool,
    diagnostics: dict[str, Any],
    shock_train_end_x_m: float | None,
    supersonic_core_end_x_m: float | None,
) -> ShockTrainResult:
  return ShockTrainResult(
    cells=cells,
    shock_train_end_x_m=shock_train_end_x_m,
    supersonic_core_end_x_m=supersonic_core_end_x_m,
    thermal_plume_end_x_m=None,
    termination=TerminationReport(
      reason=reason,
      is_physical=is_physical,
      message=message,
      diagnostics={
        key: value for key, value in diagnostics.items()
        if isinstance(value, (float, int, str)) and not isinstance(value, bool)
      },
    ),
    status=status,
    was_domain_truncated=was_domain_truncated,
    calibration_id=calibration.calibration_id,
    uncertainty={
      'parameter_covariance': calibration.parameter_covariance,
      'status': 'calibration-covariance-retained; response-propagation-not-implemented',
    },
    diagnostics=diagnostics,
  )
####


def _scaled_zones(
    template_zones: tuple[ClosedZone, ...],
    *,
    cell_index: int,
    start_x_m: float,
    length_m: float,
    first_metrics: ShockCellMetrics,
    metrics: ShockCellMetrics,
    first_cell: ShockCellSolveResult,
) -> tuple[ClosedZone, ...]:
  """Scale the first-cell template and recompute positive ideal-gas states."""

  first_length = first_metrics.length_m
  first_core_diameter = first_metrics.effective_core_diameter_m
  if first_length <= 0.0 or first_core_diameter <= 0.0:
    return ()
  radial_scale = metrics.effective_core_diameter_m / first_core_diameter
  axial_scale = length_m / first_length
  pressure_range = first_metrics.maximum_pressure_Pa - first_metrics.minimum_pressure_Pa
  template_total_temperature_K = first_cell.exit_state.total_temperature_K
  gas = first_cell.exit_state.gas
  scaled: list[ClosedZone] = []
  for zone_index, template in enumerate(template_zones, start=1):
    vertices = np.array(template.vertices_xr_m, dtype=float, copy=True)
    vertices[:, 0] = start_x_m + (vertices[:, 0] - first_metrics.start_x_m) * axial_scale
    vertices[:, 1] = vertices[:, 1] * radial_scale
    if pressure_range > 0.0:
      fraction = (template.flow.static_pressure - first_metrics.minimum_pressure_Pa) / pressure_range
    else:
      fraction = 0.5
    pressure = metrics.minimum_pressure_Pa + fraction * (
      metrics.maximum_pressure_Pa - metrics.minimum_pressure_Pa
    )
    template_mach_ratio = template.flow.mach / max(first_metrics.core_mach, 1.0e-12)
    mach = max(1.0e-6, metrics.core_mach * template_mach_ratio)
    temperature = gas.static_temperature_from_total(mach, template_total_temperature_K)
    density = gas.density_from_pressure_temperature(pressure, temperature)
    flow = FlowState(
      mach=mach,
      static_pressure=pressure,
      static_temperature=temperature,
      static_density=density,
      gamma=gas.gamma,
    )
    try:
      scaled.append(ClosedZone(
        zone_id=f'train-cell-{cell_index}-zone-{zone_index}',
        cell_index=cell_index,
        vertices_xr_m=vertices,
        flow=flow,
        composition_mass_fractions=template.composition_mass_fractions,
      ))
    except ValueError:
      return ()
  return tuple(scaled)
####


def _physical_termination(
    metrics: ShockCellMetrics,
    *,
    jet_diameter_m: float,
    policy: ShockTrainTerminationPolicy,
    weak_persistence_count: int,
) -> tuple[TerminationReason, str, int] | None:
  core_fraction = metrics.effective_core_diameter_m / jet_diameter_m
  if core_fraction <= policy.epsilon_diameter_fraction:
    return (
      TerminationReason.MIXING_LAYER_REACHED_AXIS,
      'coherent core diameter reached the configured axis threshold',
      weak_persistence_count,
    )
  if metrics.core_mach <= 1.0 + policy.epsilon_mach:
    return (
      TerminationReason.CORE_BECAME_SUBSONIC,
      'coherent core Mach number reached the configured supersonic threshold',
      weak_persistence_count,
    )
  weak = (
    metrics.pressure_oscillation_ratio <= policy.epsilon_oscillation
    and abs(metrics.mean_pressure_residual) <= policy.epsilon_mean_pressure
  )
  next_persistence_count = weak_persistence_count + 1 if weak else 0
  if next_persistence_count >= policy.persistence_cells:
    return (
      TerminationReason.PRESSURE_OSCILLATION_DECAYED,
      'pressure oscillation and mean pressure residual stayed below thresholds',
      next_persistence_count,
    )
  return None
####


def solve_shock_train(
    first_cell: ShockCellSolveResult,
    calibration: ShockTrainCalibration,
    policy: ShockTrainTerminationPolicy,
) -> ShockTrainResult:
  """Continue a resolved first cell with a bounded reduced-order train.

  ``policy.max_cells`` and ``policy.max_axial_distance_m`` are safety limits;
  neither is used as a physical answer.  The physical termination test runs
  before every downstream cell is generated.
  """

  if first_cell.status in {
      SolverStatus.INVALID_INPUT,
      SolverStatus.NUMERICAL_FAILURE,
      SolverStatus.OUTSIDE_MODEL_VALIDITY,
  }:
    status = (
      ShockTrainStatus.INVALID_INPUT
      if first_cell.status is SolverStatus.INVALID_INPUT
      else ShockTrainStatus.NUMERICAL_FAILURE
    )
    return _termination_result(
      cells=(),
      reason=TerminationReason.NUMERICAL_FAILURE,
      is_physical=False,
      message='first-cell result is not a usable train seed',
      status=status,
      calibration=calibration,
      was_domain_truncated=False,
      diagnostics={'first_cell_status': first_cell.status.value},
      shock_train_end_x_m=None,
      supersonic_core_end_x_m=None,
    )
  ####
  first_metrics = _first_cell_metrics(first_cell)
  if first_metrics is None:
    reason = (
      TerminationReason.NO_PRESSURE_MISMATCH
      if first_cell.termination_reason is TerminationReason.NO_PRESSURE_MISMATCH
      else TerminationReason.MODEL_VALIDITY_EXCEEDED
    )
    status = ShockTrainStatus.PHYSICALLY_TERMINATED if reason is TerminationReason.NO_PRESSURE_MISMATCH else ShockTrainStatus.MODEL_VALIDITY_EXCEEDED
    return _termination_result(
      cells=(),
      reason=reason,
      is_physical=reason is TerminationReason.NO_PRESSURE_MISMATCH,
      message='first-cell result contains no finite train seed',
      status=status,
      calibration=calibration,
      was_domain_truncated=False,
      diagnostics={'first_cell_termination': first_cell.termination_reason.value},
      shock_train_end_x_m=0.0 if reason is TerminationReason.NO_PRESSURE_MISMATCH else None,
      supersonic_core_end_x_m=0.0 if reason is TerminationReason.NO_PRESSURE_MISMATCH else None,
    )
  ####

  exit_state = first_cell.exit_state
  ambient = first_cell.ambient
  pressure_ratio = exit_state.total_pressure_Pa / ambient.pressure_Pa
  temperature_ratio = exit_state.total_temperature_K / ambient.temperature_K
  applicability = {
    'exit_mach': exit_state.mach,
    'total_pressure_ratio': pressure_ratio,
    'total_temperature_ratio': temperature_ratio,
  }
  if not (
      calibration.applicable_mach_range[0] <= exit_state.mach <= calibration.applicable_mach_range[1]
      and calibration.applicable_pressure_ratio_range[0] <= pressure_ratio <= calibration.applicable_pressure_ratio_range[1]
      and calibration.applicable_temperature_ratio_range[0] <= temperature_ratio <= calibration.applicable_temperature_ratio_range[1]
  ):
    return _termination_result(
      cells=(),
      reason=TerminationReason.MODEL_VALIDITY_EXCEEDED,
      is_physical=False,
      message='first-cell state is outside the supplied shock-train calibration domain',
      status=ShockTrainStatus.MODEL_VALIDITY_EXCEEDED,
      calibration=calibration,
      was_domain_truncated=False,
      diagnostics={'applicability': applicability},
      shock_train_end_x_m=None,
      supersonic_core_end_x_m=None,
    )
  ####

  first_zones = first_cell.zones
  cells = (ShockTrainCell(metrics=first_metrics, zones=first_zones),)
  jet_diameter_m = max(first_metrics.effective_core_diameter_m, 2.0 * exit_state.radius_m)
  weak_persistence_count = 0
  diagnostics: dict[str, Any] = {
    'applicability': applicability,
    'calibration_source_description': calibration.source_description,
    'geometry_fidelity_counts': {GeometryFidelity.RESOLVED_FIRST_CELL.value: 1},
    'pressure_amplitude_history': [first_metrics.pressure_oscillation_ratio],
    'core_diameter_history_m': [first_metrics.effective_core_diameter_m],
    'cell_spacing_history_m': [first_metrics.length_m],
    'weak_persistence_history': [],
  }

  while True:
    current = cells[-1].metrics
    physical = _physical_termination(
      current,
      jet_diameter_m=jet_diameter_m,
      policy=policy,
      weak_persistence_count=weak_persistence_count,
    )
    weak = (
      current.pressure_oscillation_ratio <= policy.epsilon_oscillation
      and abs(current.mean_pressure_residual) <= policy.epsilon_mean_pressure
    )
    weak_persistence_count = weak_persistence_count + 1 if weak else 0
    diagnostics['weak_persistence_history'].append(weak_persistence_count)
    if physical is not None:
      reason, message, weak_persistence_count = physical
      diagnostics['physical_termination_metrics'] = {
        'cell_index': current.cell_index,
        'core_diameter_fraction': current.effective_core_diameter_m / jet_diameter_m,
        'core_mach': current.core_mach,
        'pressure_oscillation_ratio': current.pressure_oscillation_ratio,
        'mean_pressure_residual': current.mean_pressure_residual,
        'weak_persistence_count': weak_persistence_count,
      }
      supersonic_end = (
        current.end_x_m
        if reason is TerminationReason.CORE_BECAME_SUBSONIC
        else None
      )
      return _termination_result(
        cells=cells,
        reason=reason,
        is_physical=True,
        message=message,
        status=ShockTrainStatus.PHYSICALLY_TERMINATED,
        calibration=calibration,
        was_domain_truncated=False,
        diagnostics=diagnostics,
        shock_train_end_x_m=current.end_x_m,
        supersonic_core_end_x_m=supersonic_end,
      )
    ####
    if len(cells) >= policy.max_cells:
      return _termination_result(
        cells=cells,
        reason=TerminationReason.MAX_CELL_LIMIT,
        is_physical=False,
        message='requested maximum cell count truncated the train before physical termination',
        status=ShockTrainStatus.TRUNCATED,
        calibration=calibration,
        was_domain_truncated=False,
        diagnostics={**diagnostics, 'safety_limit': 'max_cells'},
        shock_train_end_x_m=current.end_x_m,
        supersonic_core_end_x_m=None,
      )
    ####
    if policy.max_axial_distance_m is not None and current.end_x_m >= policy.max_axial_distance_m:
      return _termination_result(
        cells=cells,
        reason=TerminationReason.SPATIAL_DOMAIN_LIMIT,
        is_physical=False,
        message='configured axial domain truncated the train before physical termination',
        status=ShockTrainStatus.TRUNCATED,
        calibration=calibration,
        was_domain_truncated=True,
        diagnostics={**diagnostics, 'safety_limit': 'max_axial_distance_m'},
        shock_train_end_x_m=current.end_x_m,
        supersonic_core_end_x_m=None,
      )
    ####

    local_core_distance = max(0.0, current.end_x_m - first_metrics.end_x_m)
    shear_thickness = calibration.initial_shear_layer_thickness_m + calibration.mixing_layer_growth_rate * local_core_distance
    core_diameter = max(
      0.0,
      first_metrics.effective_core_diameter_m - 2.0 * shear_thickness,
    )
    local_total_pressure = current.outlet_total_pressure_Pa
    local_mach = _expanded_mach(local_total_pressure, ambient.pressure_Pa, exit_state.gas.gamma)
    if core_diameter <= 0.0 or local_mach <= 1.0 + policy.epsilon_mach:
      reason = TerminationReason.MIXING_LAYER_REACHED_AXIS if core_diameter <= 0.0 else TerminationReason.CORE_BECAME_SUBSONIC
      return _termination_result(
        cells=cells,
        reason=reason,
        is_physical=True,
        message='reduced-order continuation reached its physical core limit before another cell could be generated',
        status=ShockTrainStatus.PHYSICALLY_TERMINATED,
        calibration=calibration,
        was_domain_truncated=False,
        diagnostics={**diagnostics, 'continuation_core_diameter_m': core_diameter, 'continuation_core_mach': local_mach},
        shock_train_end_x_m=current.end_x_m,
        supersonic_core_end_x_m=current.end_x_m if local_mach <= 1.0 + policy.epsilon_mach else None,
      )
    ####
    spacing_correction = max(
      calibration.minimum_shear_layer_spacing_correction,
      1.0 - calibration.finite_shear_layer_spacing_correction * shear_thickness / jet_diameter_m,
    )
    length_m = (
      calibration.cell_spacing_coefficient
      * core_diameter
      * sqrt(local_mach**2 - 1.0)
      * spacing_correction
    )
    if not isfinite(length_m) or length_m <= 0.0:
      return _termination_result(
        cells=cells,
        reason=TerminationReason.MODEL_VALIDITY_EXCEEDED,
        is_physical=False,
        message='reduced-order closure produced a nonpositive cell spacing',
        status=ShockTrainStatus.MODEL_VALIDITY_EXCEEDED,
        calibration=calibration,
        was_domain_truncated=False,
        diagnostics={**diagnostics, 'spacing_correction': spacing_correction, 'local_core_mach': local_mach},
        shock_train_end_x_m=current.end_x_m,
        supersonic_core_end_x_m=None,
      )
    ####
    next_start_x_m = current.end_x_m
    next_end_x_m = next_start_x_m + length_m
    if policy.max_axial_distance_m is not None and next_end_x_m > policy.max_axial_distance_m:
      return _termination_result(
        cells=cells,
        reason=TerminationReason.SPATIAL_DOMAIN_LIMIT,
        is_physical=False,
        message='next reduced-order cell exceeded the configured axial domain',
        status=ShockTrainStatus.TRUNCATED,
        calibration=calibration,
        was_domain_truncated=True,
        diagnostics={**diagnostics, 'safety_limit': 'max_axial_distance_m', 'candidate_end_x_m': next_end_x_m},
        shock_train_end_x_m=current.end_x_m,
        supersonic_core_end_x_m=None,
      )
    ####
    mid_core_diameter = max(
      1.0e-12,
      first_metrics.effective_core_diameter_m - 2.0 * (
        calibration.initial_shear_layer_thickness_m
        + calibration.mixing_layer_growth_rate * (local_core_distance + length_m / 2.0)
      ),
    )
    amplitude = current.pressure_oscillation_ratio * exp(
      -calibration.pressure_amplitude_decay_coefficient * length_m / mid_core_diameter
    )
    mean_residual = current.mean_pressure_residual * exp(
      -calibration.mean_pressure_relaxation_coefficient * length_m / mid_core_diameter
    )
    outlet_total_pressure = local_total_pressure * exp(
      -calibration.total_pressure_loss_coefficient * length_m / mid_core_diameter
    )
    mean_pressure = ambient.pressure_Pa * (1.0 + mean_residual)
    maximum_pressure = mean_pressure + amplitude * ambient.pressure_Pa
    minimum_pressure = mean_pressure - amplitude * ambient.pressure_Pa
    if minimum_pressure <= 0.0 or outlet_total_pressure <= 0.0:
      return _termination_result(
        cells=cells,
        reason=TerminationReason.MODEL_VALIDITY_EXCEEDED,
        is_physical=False,
        message='reduced-order pressure closure produced a nonpositive state',
        status=ShockTrainStatus.MODEL_VALIDITY_EXCEEDED,
        calibration=calibration,
        was_domain_truncated=False,
        diagnostics={**diagnostics, 'minimum_pressure_Pa': minimum_pressure, 'outlet_total_pressure_Pa': outlet_total_pressure},
        shock_train_end_x_m=current.end_x_m,
        supersonic_core_end_x_m=None,
      )
    ####
    next_metrics = ShockCellMetrics(
      cell_index=current.cell_index + 1,
      start_x_m=next_start_x_m,
      end_x_m=next_end_x_m,
      length_m=length_m,
      effective_core_diameter_m=core_diameter,
      core_mach=local_mach,
      mean_pressure_Pa=mean_pressure,
      maximum_pressure_Pa=maximum_pressure,
      minimum_pressure_Pa=minimum_pressure,
      pressure_oscillation_ratio=amplitude,
      mean_pressure_residual=mean_residual,
      inlet_total_pressure_Pa=local_total_pressure,
      outlet_total_pressure_Pa=min(local_total_pressure, outlet_total_pressure),
      geometry_fidelity=GeometryFidelity.SCALED_REDUCED_ORDER,
    )
    next_zones = _scaled_zones(
      first_zones,
      cell_index=next_metrics.cell_index,
      start_x_m=next_start_x_m,
      length_m=length_m,
      first_metrics=first_metrics,
      metrics=next_metrics,
      first_cell=first_cell,
    )
    cells = cells + (ShockTrainCell(metrics=next_metrics, zones=next_zones),)
    diagnostics['geometry_fidelity_counts'][GeometryFidelity.SCALED_REDUCED_ORDER.value] = (
      diagnostics['geometry_fidelity_counts'].get(GeometryFidelity.SCALED_REDUCED_ORDER.value, 0) + 1
    )
    diagnostics['pressure_amplitude_history'].append(amplitude)
    diagnostics['core_diameter_history_m'].append(core_diameter)
    diagnostics['cell_spacing_history_m'].append(length_m)
  ####
