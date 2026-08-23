"""Straight analytical shock-cell provider backed by the shared solver core."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite, pi
from exhaust_plume.contracts import (
    AxisymmetricZone,
    AxisymmetricZoneField,
    CapabilityId,
    PlumeMorphology,
    PlumeProvenance,
    PlumeProviderDescriptor,
    PlumeSnapshot,
    ProjectedAreaCapability,
    ProviderApplicability,
    ProviderClosedError,
    ProviderConfigurationError,
    ProviderExecutionProfile,
    ProviderFidelity,
    SnapshotRetention,
    SpatialSupport,
    TerminationReason,
    TerminationReport,
    TimeAccessMode,
    ConcurrencyMode,
    OperatingStateDomainError,
    PlumeFluxSection,
)
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.models.shock_cells.contracts import ShockCellSolveConfig, SolverStatus
from exhaust_plume.models.shock_cells.solve import solve_shock_cells

__all__ = (
    "ShockCellConfiguration",
    "ShockCellDefinition",
    "ShockCellAnalyticalConfiguration",
    "ShockCellAnalyticalDefinition",
    "ShockCellAnalyticalOperatingState",
    "ShockCellAnalyticalProvider",
    "ShockCellAnalyticalSession",
    "ShockCellOperatingState",
)
###########################################


@dataclass(frozen=True, slots=True)
class ShockCellAnalyticalDefinition:
  nozzle_radius_m: float
  plume_frame_id: str = "straight-axisymmetric-xr"

  def __post_init__(self) -> None:
    if not isfinite(self.nozzle_radius_m) or self.nozzle_radius_m <= 0.0:
      raise ProviderConfigurationError("nozzle_radius_m must be finite and positive")
    if not self.plume_frame_id:
      raise ProviderConfigurationError("plume_frame_id must not be empty")
  ####


@dataclass(frozen=True, slots=True)
class ShockCellAnalyticalConfiguration:
  num_expansion_lines: int = 2
  num_compression_lines: int = 1
  maximum_construction_passes: int = 1
  pressure_match_rtol: float = 1.0e-4
  permit_strong_shock_branch: bool = False
  permit_legacy_parabola_fallback: bool = False

  def __post_init__(self) -> None:
    if isinstance(self.num_expansion_lines, bool) or self.num_expansion_lines < 2:
      raise ProviderConfigurationError("num_expansion_lines must be an integer >= 2")
    if isinstance(self.num_compression_lines, bool) or self.num_compression_lines < 1:
      raise ProviderConfigurationError("num_compression_lines must be an integer >= 1")
    if isinstance(self.maximum_construction_passes, bool) or self.maximum_construction_passes < 0:
      raise ProviderConfigurationError("maximum_construction_passes must be an integer >= 0")
    if not isfinite(self.pressure_match_rtol) or self.pressure_match_rtol <= 0.0:
      raise ProviderConfigurationError("pressure_match_rtol must be finite and positive")
  ####


@dataclass(frozen=True, slots=True)
class ShockCellAnalyticalOperatingState:
  nozzle_exit: NozzleExitState
  ambient: AmbientState
  time_s: float = 0.0

  @property
  def exit_state(self) -> NozzleExitState:
    return self.nozzle_exit
  ####

  def __post_init__(self) -> None:
    if not isfinite(self.time_s):
      raise OperatingStateDomainError("time_s must be finite")
  ####


ShockCellDefinition = ShockCellAnalyticalDefinition
ShockCellConfiguration = ShockCellAnalyticalConfiguration
ShockCellOperatingState = ShockCellAnalyticalOperatingState


def _descriptor() -> PlumeProviderDescriptor:
  return PlumeProviderDescriptor(
      provider_id="shock-cell-analytical",
      provider_version="0.1.0",
      core_contract_major_version=1,
      capability_versions={
          CapabilityId.SPATIAL_SUPPORT: 1,
          CapabilityId.AXISYMMETRIC_ZONE_FIELD: 1,
          CapabilityId.PROJECTED_AREA: 1,
      },
      definition_schema_id="shock-cell-analytical-definition-v1",
      configuration_schema_id="shock-cell-analytical-configuration-v1",
      operating_state_schema_id="shock-cell-analytical-operating-state-v1",
      morphology=PlumeMorphology.STRAIGHT,
      fidelity=ProviderFidelity(
          geometry_model="planar-analytical-zone-approximation",
          spatial_dimensionality="axisymmetric-looking-xr",
          temporal_model="steady-operating-state",
          flow_model="calorically-perfect-inviscid-shock-expansion",
          mixing_model="none",
          thermochemistry_model="frozen-calorically-perfect-gas",
          radiation_model="none",
          environmental_coupling="uniform-ambient-pressure",
          validation_level="foundation-regression-only",
      ),
      execution=ProviderExecutionProfile(
          time_access=TimeAccessMode.RANDOM_ACCESS,
          concurrency=ConcurrencyMode.SERIAL,
          deterministic=True,
          supports_direction_batching=False,
          maximum_direction_batch_size=None,
          checkpointable=False,
          preferred_device="cpu",
          snapshot_retention=SnapshotRetention.INDEPENDENT,
      ),
      applicability=ProviderApplicability(
          summary="Straight, steady, uniform-exit analytical shock-cell geometry; no mixing, chemistry, radiation, or curved flow",
          bounds={"mach": (1.0, None), "gamma": (1.0, None), "flow_angle_rad": (-pi / 6.0, pi / 6.0)},
      ),
  )


class ShockCellAnalyticalProvider:
  """Provider wrapper for the corrected simple straight plume path."""

  def __init__(self) -> None:
    self._descriptor = _descriptor()
  ####

  @property
  def descriptor(self) -> PlumeProviderDescriptor:
    return self._descriptor
  ####

  def create_session(self, definition: ShockCellAnalyticalDefinition, configuration: ShockCellAnalyticalConfiguration) -> ShockCellAnalyticalSession:
    if not isinstance(definition, ShockCellAnalyticalDefinition):
      raise ProviderConfigurationError("definition must be ShockCellAnalyticalDefinition")
    if not isinstance(configuration, ShockCellAnalyticalConfiguration):
      raise ProviderConfigurationError("configuration must be ShockCellAnalyticalConfiguration")
    return ShockCellAnalyticalSession(self._descriptor, definition, configuration)
  ####


class ShockCellAnalyticalSession:
  def __init__(self, descriptor: PlumeProviderDescriptor, definition: ShockCellAnalyticalDefinition, configuration: ShockCellAnalyticalConfiguration) -> None:
    self._descriptor = descriptor
    self._definition = definition
    self._configuration = configuration
    self._closed = False
  ####

  def close(self) -> None:
    self._closed = True
  ####

  def conservative_handoff(self, operating_state: ShockCellAnalyticalOperatingState) -> PlumeFluxSection:
    """Return a conservative exit-section handoff for a straight continuation."""

    if self._closed:
      raise ProviderClosedError("shock-cell analytical session is closed")
    if not isinstance(operating_state, ShockCellAnalyticalOperatingState):
      raise OperatingStateDomainError("operating_state must be ShockCellAnalyticalOperatingState")
    return PlumeFluxSection.from_nozzle_exit(
        operating_state.nozzle_exit,
        ambient_pressure_Pa=operating_state.ambient.pressure_Pa,
    )
  ####

  def snapshot(self, operating_state: ShockCellAnalyticalOperatingState) -> PlumeSnapshot:
    if self._closed:
      raise ProviderClosedError("shock-cell analytical session is closed")
    if not isinstance(operating_state, ShockCellAnalyticalOperatingState):
      raise OperatingStateDomainError("operating_state must be ShockCellAnalyticalOperatingState")
    if abs(operating_state.nozzle_exit.radius_m - self._definition.nozzle_radius_m) > max(1.0e-12, self._definition.nozzle_radius_m * 1.0e-10):
      raise OperatingStateDomainError("operating-state nozzle radius does not match the provider definition")
    if abs(operating_state.nozzle_exit.flow_angle_rad) > pi / 6.0:
      raise OperatingStateDomainError("exit flow angle is outside the straight-provider applicability domain")
    result = solve_shock_cells(ShockCellSolveConfig(
        exit=operating_state.nozzle_exit,
        ambient=operating_state.ambient,
        expansion_characteristics=self._configuration.num_expansion_lines,
        compression_characteristics=self._configuration.num_compression_lines,
        pressure_match_rtol=self._configuration.pressure_match_rtol,
        max_cells=self._configuration.maximum_construction_passes,
        permit_strong_shock_branch=self._configuration.permit_strong_shock_branch,
        permit_legacy_parabola_fallback=self._configuration.permit_legacy_parabola_fallback,
    ))
    if result.status is SolverStatus.NUMERICAL_FAILURE or result.status is SolverStatus.OUTSIDE_MODEL_VALIDITY:
      raise OperatingStateDomainError(str(result.details.get("solver_diagnostics_v1", "analytical solver failed")))
    zones = tuple(
        AxisymmetricZone(
            zone_id=zone.zone_id,
            polygon_xr_m=zone.vertices_xr_m,
            static_pressure_Pa=zone.flow.static_pressure,
            static_temperature_K=zone.flow.static_temperature,
            density_kgpm3=zone.flow.static_density,
            mach=zone.flow.mach,
            phase="closed-zone",
            cell_index=zone.cell_index,
        ) for zone in result.zones
    )
    field = AxisymmetricZoneField(zones=zones)
    support = self._spatial_support(zones)
    projected_area = ProjectedAreaCapability(
        reference_area_m2=pi * self._definition.nozzle_radius_m**2,
        closed_zone_count=len(zones),
    )
    provenance_id = sha256(repr((operating_state, self._configuration, self._definition)).encode()).hexdigest()[:24]
    termination_reason = TerminationReason.NO_PRESSURE_MISMATCH if result.termination_reason.value == "no-pressure-mismatch" else TerminationReason.REQUESTED_CONSTRUCTION_LIMIT
    termination = TerminationReport(
        reason=termination_reason,
        is_physical=False,
        message="Matched exit and ambient pressure" if termination_reason is TerminationReason.NO_PRESSURE_MISMATCH else "Requested construction-pass limit reached; no physical plume endpoint inferred",
        diagnostics={"pressure_residual": result.pressure_residual, "closed_zone_count": len(zones)},
    )
    provenance = PlumeProvenance(
        provider_id=self._descriptor.provider_id,
        provider_version=self._descriptor.provider_version,
        source_references=("calculatePlumeZonesFromExitState", "foundation-straight-plume"),
        metadata={"provenance_id": provenance_id, "regime": result.regime.value},
    )
    return PlumeSnapshot(
        descriptor=self._descriptor,
        provenance=provenance,
        capabilities={
            CapabilityId.SPATIAL_SUPPORT: support,
            CapabilityId.AXISYMMETRIC_ZONE_FIELD: field,
            CapabilityId.PROJECTED_AREA: projected_area,
        },
        termination=termination,
        snapshot_id=provenance_id,
    )
  ####

  @staticmethod
  def _spatial_support(zones: tuple[AxisymmetricZone, ...]) -> SpatialSupport:
    if not zones:
      return SpatialSupport(
          plume_frame_aabb_min_m=(0.0, -1.0, 0.0),
          plume_frame_aabb_max_m=(0.0, 1.0, 0.0),
          characteristic_extent_m=1.0,
          support_definition="no-pressure-mismatch exit-plane support",
          is_conservative=True,
      )
    points = [zone.polygon_xr_m for zone in zones]
    import numpy as np
    all_points = np.vstack(points)
    x_min = float(all_points[:, 0].min())
    x_max = float(all_points[:, 0].max())
    r_max = float(np.abs(all_points[:, 1]).max())
    return SpatialSupport(
        plume_frame_aabb_min_m=(x_min, -r_max, 0.0),
        plume_frame_aabb_max_m=(x_max, r_max, 0.0),
        characteristic_extent_m=max(1.0e-12, x_max - x_min, 2.0 * r_max),
        support_definition="finite union of validated straight analytical x-r zone polygons",
        is_conservative=True,
    )
  ####
