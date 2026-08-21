"""Public package interface for the exhaust-plume study model."""

from __future__ import annotations

from exhaust_plume.constants import MODULE_NAME, VERSION
from exhaust_plume.models.plume import (
    EngineParameters,
    ExpansionFanState,
    FlowState,
    ObliqueShockState,
    ZoneCoordinates,
    ZoneResult,
    ZoneType,
    calcNozzleExitFlowState,
    calculatePlumeZones,
)

__version__ = VERSION

__all__ = (
    'MODULE_NAME',
    'VERSION',
    '__version__',
    'EngineParameters',
    'ExpansionFanState',
    'FlowState',
    'ObliqueShockState',
    'ZoneCoordinates',
    'ZoneResult',
    'ZoneType',
    'calcNozzleExitFlowState',
    'calculatePlumeZones',
)
