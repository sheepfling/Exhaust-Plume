"""Core plume model and its flow-state result types."""

from __future__ import annotations

from exhaust_plume.models.plume.motor_parameters import EngineParameters
from exhaust_plume.models.plume.plume_solve import (
    ZoneCoordinates,
    ZoneResult,
    ZoneType,
    calcNozzleExitFlowState,
    calculatePlumeZones,
    calculatePlumeZonesFromExitState,
)
from exhaust_plume.util.aero.expansion_fan import ExpansionFanState
from exhaust_plume.util.aero.flow_state import FlowState
from exhaust_plume.util.aero.oblique_shock import ObliqueShockState

__all__ = (
    'EngineParameters',
    'ExpansionFanState',
    'FlowState',
    'ObliqueShockState',
    'ZoneCoordinates',
    'ZoneResult',
    'ZoneType',
    'calcNozzleExitFlowState',
    'calculatePlumeZones',
    'calculatePlumeZonesFromExitState',
)
