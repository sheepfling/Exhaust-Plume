"""Explicit nozzle and ambient state contracts."""

from __future__ import annotations

from exhaust_plume.models.nozzle.area_mach import (
    MachBranch,
    calc_area_mach_ratio,
    calc_choked_throat_area,
    calc_mass_flow_parameter,
    calc_mass_flow_rate,
    solve_mach_from_area_ratio,
)
from exhaust_plume.models.nozzle.contracts import (
    AmbientInput,
    AmbientState,
    NozzleExitInput,
    NozzleExitState,
    NozzleStateSourceKind,
)
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit
from exhaust_plume.models.nozzle.geometry import (
    NozzleGeometry,
    NozzleGeometryFamily,
    ThroatConfiguration,
    ThroatShape,
    derive_nozzle_exit_from_geometry,
)

__all__ = (
    'AmbientInput',
    'AmbientState',
    'MachBranch',
    'NozzleExitInput',
    'NozzleExitState',
    'NozzleGeometry',
    'NozzleGeometryFamily',
    'NozzleStateSourceKind',
    'ThroatConfiguration',
    'ThroatShape',
    'derive_ambient_state',
    'derive_nozzle_exit_from_geometry',
    'derive_uniform_nozzle_exit',
    'calc_area_mach_ratio',
    'calc_choked_throat_area',
    'calc_mass_flow_parameter',
    'calc_mass_flow_rate',
    'solve_mach_from_area_ratio',
)
