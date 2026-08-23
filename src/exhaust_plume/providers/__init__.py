"""Plume provider lifecycle, static fixtures, and product adapters."""

from __future__ import annotations

from exhaust_plume.providers.adapters import (
    engineeringFluxSectionsFromCurvedPlume,
    sectionedTubeFromAxisymmetricZones,
    sectionedTubeFromCurvedPlume,
)
from exhaust_plume.providers.lifecycle import (
    ClosedSessionError,
    ExecutionBackend,
    PlumeProvider,
    PlumeSession,
    PlumeSnapshot,
    ProviderDescriptor,
    SessionRequest,
    TimeAccessMode,
    UnsupportedCapabilityError,
    requireProduct,
)
from exhaust_plume.providers.static import (
    StaticPlumeProvider,
    StaticPlumeSession,
    StaticPlumeSnapshot,
)

__all__ = (
    'ClosedSessionError',
    'ExecutionBackend',
    'PlumeProvider',
    'PlumeSession',
    'PlumeSnapshot',
    'ProviderDescriptor',
    'SessionRequest',
    'StaticPlumeProvider',
    'StaticPlumeSession',
    'StaticPlumeSnapshot',
    'TimeAccessMode',
    'UnsupportedCapabilityError',
    'engineeringFluxSectionsFromCurvedPlume',
    'requireProduct',
    'sectionedTubeFromAxisymmetricZones',
    'sectionedTubeFromCurvedPlume',
)
