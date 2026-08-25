"""Numerical arc-length integration for the curved-plume kernel."""

from __future__ import annotations

from math import pi, sqrt
from typing import Callable

import numpy as np
from numpy import ndarray
from numpy.typing import ArrayLike
from scipy.integrate import solve_ivp

from exhaust_plume.models.plume._curved_plume_common import (
    FloatArray,
    _asReadOnlyVector3,
    _validateNonnegativeFinite,
    _validatePositiveFinite,
)
from exhaust_plume.models.plume.curved_plume_closures import (
    CurvedPlumeOptions,
    CurvedPlumeResult,
    CurvedPlumeSourceTermModel,
    CurvedPlumeTermination,
    EntrainmentModel,
    ZeroCurvedPlumeSourceTermModel,
)
from exhaust_plume.models.plume.curved_plume_state import (
    AmbientState,
    AmbientStateField,
    CurvedPlumeSource,
    CurvedPlumeStation,
    IdealGasMixtureThermodynamics,
    MixtureThermodynamics,
    _validateAmbientCaloricProperties,
)

_POSITION = slice(0, 3)
_MASS_FLOW = 3
_MOMENTUM = slice(4, 7)
_TOTAL_ENERGY_FLOW = 7
_EXHAUST_MASS_FLOW = 8
_STATE_SIZE = 9


def _reconstructStation(
    *,
    arc_length_m: float,
    state: FloatArray,
    source: CurvedPlumeSource,
    ambient_field: AmbientStateField,
    thermodynamics: MixtureThermodynamics,
    entrainment_kgpspm: float,
    momentum_derivative_Npm: ArrayLike,
    minimum_speed_mps: float,
    ambient_caloric_reference: AmbientState,
) -> CurvedPlumeStation:
  if state.shape != (_STATE_SIZE,):
    raise ValueError(f'Expected conserved state shape ({_STATE_SIZE},). Got:{state.shape}')
  ####
  position = _asReadOnlyVector3('position_m', state[_POSITION])
  mass_flow = _validatePositiveFinite('mass_flow_kgps', state[_MASS_FLOW])
  momentum = _asReadOnlyVector3('momentum_flux_N', state[_MOMENTUM])
  velocity = _asReadOnlyVector3('velocity_mps', momentum / mass_flow)
  speed = float(np.linalg.norm(velocity))
  if speed < minimum_speed_mps:
    raise ValueError(f'Plume speed fell below the supported minimum:{speed}')
  ####
  total_energy_flow = _validatePositiveFinite('total_energy_flow_W', state[_TOTAL_ENERGY_FLOW])
  exhaust_mass_flow = _validateNonnegativeFinite('exhaust_mass_flow_kgps', state[_EXHAUST_MASS_FLOW])
  exhaust_mass_fraction = exhaust_mass_flow / mass_flow
  ambient = ambient_field.sample(position)
  _validateAmbientCaloricProperties(
      ambient=ambient,
      reference=ambient_caloric_reference,
  )
  mixture = thermodynamics.reconstruct(
      source=source,
      ambient=ambient,
      mass_flow_kgps=mass_flow,
      velocity_mps=velocity,
      total_energy_flow_W=total_energy_flow,
  )
  area = mass_flow / (mixture.density_kgpm3 * speed)
  radius = sqrt(area / pi)
  relative_velocity = _asReadOnlyVector3('relative_velocity_mps', velocity - ambient.velocity_mps)
  tangent = velocity / speed
  momentum_derivative = _asReadOnlyVector3('momentum_derivative_Npm', momentum_derivative_Npm)
  normal_momentum_derivative = momentum_derivative - float(momentum_derivative @ tangent) * tangent
  curvature = float(np.linalg.norm(normal_momentum_derivative)) / float(np.linalg.norm(momentum))
  return CurvedPlumeStation(
      arc_length_m=arc_length_m,
      position_m=position,
      mass_flow_kgps=mass_flow,
      momentum_flux_N=momentum,
      momentum_derivative_Npm=momentum_derivative,
      velocity_mps=velocity,
      total_energy_flow_W=total_energy_flow,
      exhaust_mass_flow_kgps=exhaust_mass_flow,
      exhaust_mass_fraction=exhaust_mass_fraction,
      temperature_K=mixture.temperature_K,
      pressure_Pa=ambient.pressure_Pa,
      density_kgpm3=mixture.density_kgpm3,
      specific_heat_JpkgK=mixture.specific_heat_JpkgK,
      gas_constant_JpkgK=mixture.gas_constant_JpkgK,
      area_m2=area,
      radius_m=radius,
      ambient_velocity_mps=ambient.velocity_mps,
      ambient_temperature_K=ambient.temperature_K,
      ambient_density_kgpm3=ambient.density_kgpm3,
      relative_velocity_mps=relative_velocity,
      entrainment_kgpspm=entrainment_kgpspm,
      curvature_per_m=curvature,
      slenderness_ratio=curvature * radius,
  )
####


def _calculateInitialConservedState(source: CurvedPlumeSource) -> FloatArray:
  state = np.empty((_STATE_SIZE,), dtype=float)
  state[_POSITION] = source.position_m
  state[_MASS_FLOW] = source.mass_flow_kgps
  state[_MOMENTUM] = source.mass_flow_kgps * source.velocity_mps
  state[_TOTAL_ENERGY_FLOW] = source.mass_flow_kgps * (
      source.specific_heat_JpkgK * source.temperature_K + .5 * float(source.velocity_mps @ source.velocity_mps)
  )
  state[_EXHAUST_MASS_FLOW] = source.exhaust_mass_flow_kgps
  return state
####


def _calculateEquilibriumResidual(station: CurvedPlumeStation, options: CurvedPlumeOptions) -> float:
  """Return a signed residual whose first non-positive crossing is equilibrium."""
  return (
      max(
          station.exhaust_mass_fraction / options.equilibrium_exhaust_mass_fraction - 1.,
          abs(station.temperature_K - station.ambient_temperature_K)
          / options.equilibrium_temperature_excess_K - 1.,
          station.relative_speed_mps / options.equilibrium_relative_speed_mps - 1.,
      )
  )
####


def solveCurvedPlume(
    *,
    source: CurvedPlumeSource,
    ambient_field: AmbientStateField,
    entrainment_model: EntrainmentModel,
    options: CurvedPlumeOptions,
    thermodynamics: MixtureThermodynamics | None = None,
    source_term_model: CurvedPlumeSourceTermModel | None = None,
) -> CurvedPlumeResult:
  """Integrate the conservative curved-plume equations along arc length."""
  thermodynamic_model = thermodynamics if thermodynamics is not None else IdealGasMixtureThermodynamics()
  external_source_model = source_term_model if source_term_model is not None else ZeroCurvedPlumeSourceTermModel()
  source_ambient = ambient_field.sample(source.position_m)
  pressure_relative_error = abs(source.static_pressure_Pa - source_ambient.pressure_Pa) / source_ambient.pressure_Pa
  if pressure_relative_error > options.pressure_match_relative_tolerance:
    raise ValueError(
        'The curved-plume source must be pressure matched to the local ambient. '
        f'Relative error:{pressure_relative_error}'
    )
  ####
  initial_state = _calculateInitialConservedState(source)

  def derivative(arc_length_m: float, state: ndarray) -> ndarray:
    provisional = _reconstructStation(
        arc_length_m=arc_length_m,
        state=np.asarray(state, dtype=float),
        source=source,
        ambient_field=ambient_field,
        thermodynamics=thermodynamic_model,
        entrainment_kgpspm=0.,
        momentum_derivative_Npm=np.zeros(3),
        minimum_speed_mps=options.minimum_speed_mps,
        ambient_caloric_reference=source_ambient,
    )
    entrainment = entrainment_model.calculateMassEntrainmentPerLength(
        arc_length_m=arc_length_m,
        station=provisional,
        source=source,
    )
    entrainment = _validateNonnegativeFinite('entrainment_kgpspm', entrainment)
    ambient = ambient_field.sample(provisional.position_m)
    _validateAmbientCaloricProperties(
        ambient=ambient,
        reference=source_ambient,
    )
    external_source_terms = external_source_model.calculateSourceTerms(
        arc_length_m=arc_length_m,
        station=provisional,
        source=source,
    )
    tangent = provisional.tangent
    derivative_state = np.zeros((_STATE_SIZE,), dtype=float)
    derivative_state[_POSITION] = tangent
    derivative_state[_MASS_FLOW] = entrainment
    derivative_state[_MOMENTUM] = entrainment * ambient.velocity_mps + external_source_terms.force_Npm
    derivative_state[_TOTAL_ENERGY_FLOW] = (
        entrainment * (
            ambient.specific_heat_JpkgK * ambient.temperature_K
            + .5 * float(ambient.velocity_mps @ ambient.velocity_mps)
        )
        + external_source_terms.energy_source_Wpm
    )
    derivative_state[_EXHAUST_MASS_FLOW] = 0.
    return derivative_state
  ####

  output_arc_lengths = np.linspace(0., options.max_arc_length_m, options.number_of_stations)
  equilibrium_event: Callable[[float, ndarray], float] | None = None
  if options.enable_equilibrium_termination:
    def equilibrium_event_function(arc_length_m: float, state: ndarray) -> float:
      station = _reconstructStation(
          arc_length_m=arc_length_m,
          state=np.asarray(state, dtype=float),
          source=source,
          ambient_field=ambient_field,
          thermodynamics=thermodynamic_model,
          entrainment_kgpspm=0.,
          momentum_derivative_Npm=np.zeros(3),
          minimum_speed_mps=options.minimum_speed_mps,
          ambient_caloric_reference=source_ambient,
      )
      return _calculateEquilibriumResidual(station, options)
    ####
    setattr(equilibrium_event_function, 'terminal', True)
    setattr(equilibrium_event_function, 'direction', -1.)
    equilibrium_event = equilibrium_event_function
  ####

  solution = solve_ivp(
      derivative,
      (0., options.max_arc_length_m),
      initial_state,
      t_eval=output_arc_lengths,
      rtol=options.relative_tolerance,
      atol=options.absolute_tolerance,
      max_step=options.max_step_m,
      events=equilibrium_event,
  )
  event_arc_length: float | None = None
  event_state: ndarray | None = None
  event_states = solution.y_events
  if (
      equilibrium_event is not None
      and solution.t_events
      and event_states is not None
      and len(solution.t_events[0]) > 0
  ):
    event_arc_length = float(solution.t_events[0][0])
    event_state = np.asarray(event_states[0][0], dtype=float)
  ####

  solution_samples = [
      (float(arc_length_m), np.asarray(state, dtype=float))
      for arc_length_m, state in zip(solution.t, solution.y.T)
  ]
  if event_arc_length is not None and event_state is not None:
    if not solution_samples or not np.isclose(
        solution_samples[-1][0],
        event_arc_length,
        rtol=0.,
        atol=1.e-12,
    ):
      solution_samples.append((event_arc_length, event_state))
    ####
  ####

  stations: list[CurvedPlumeStation] = []
  for arc_length_m, state in solution_samples:
    provisional = _reconstructStation(
        arc_length_m=arc_length_m,
        state=state,
        source=source,
        ambient_field=ambient_field,
        thermodynamics=thermodynamic_model,
        entrainment_kgpspm=0.,
        momentum_derivative_Npm=np.zeros(3),
        minimum_speed_mps=options.minimum_speed_mps,
        ambient_caloric_reference=source_ambient,
    )
    entrainment = entrainment_model.calculateMassEntrainmentPerLength(
        arc_length_m=arc_length_m,
        station=provisional,
        source=source,
    )
    external_source_terms = external_source_model.calculateSourceTerms(
        arc_length_m=float(arc_length_m),
        station=provisional,
        source=source,
    )
    ambient = ambient_field.sample(provisional.position_m)
    _validateAmbientCaloricProperties(
        ambient=ambient,
        reference=source_ambient,
    )
    momentum_derivative = entrainment * ambient.velocity_mps + external_source_terms.force_Npm
    station = _reconstructStation(
        arc_length_m=arc_length_m,
        state=state,
        source=source,
        ambient_field=ambient_field,
        thermodynamics=thermodynamic_model,
        entrainment_kgpspm=_validateNonnegativeFinite('entrainment_kgpspm', entrainment),
        momentum_derivative_Npm=momentum_derivative,
        minimum_speed_mps=options.minimum_speed_mps,
        ambient_caloric_reference=source_ambient,
    )
    stations.append(station)
  ####

  if not solution.success:
    termination = CurvedPlumeTermination.NUMERICAL_FAILURE
  elif event_arc_length is not None:
    termination = CurvedPlumeTermination.EQUILIBRIUM
  else:
    termination = CurvedPlumeTermination.DOMAIN_LIMIT
  ####
  return CurvedPlumeResult(
      stations=tuple(stations),
      termination=termination,
      solver_message=str(solution.message),
      function_evaluations=int(solution.nfev),
  )
####
