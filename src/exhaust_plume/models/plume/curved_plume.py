"""Conservative integral model for pressure-matched curved exhaust plumes."""

from __future__ import annotations

from exhaust_plume.models.plume.curved_plume_ambient import (
    ActuatorDiskWakeField,
    AmbientVelocityField,
    CompositeVelocityField,
    UniformVelocityField,
    VelocityAugmentedAmbientField,
)
from exhaust_plume.models.plume.curved_plume_closures import (
    ConstantEntrainment,
    CurvedPlumeOptions,
    CurvedPlumeResult,
    CurvedPlumeSourceTermModel,
    CurvedPlumeSourceTerms,
    CurvedPlumeTermination,
    DevelopingShearForcedEntrainment,
    EntrainmentModel,
    ZeroCurvedPlumeSourceTermModel,
)
from exhaust_plume.models.plume.curved_plume_exact import (
    ConstantDensityFreeJetExactSolution,
    OrthogonalUniformCrossflowExactSolution,
    calculateConstantDensityFreeJetExact,
    calculateOrthogonalUniformCrossflowExact,
)
from exhaust_plume.models.plume.curved_plume_solver import solveCurvedPlume
from exhaust_plume.models.plume.curved_plume_state import (
    AmbientState,
    AmbientStateField,
    ConstantDensityMixtureThermodynamics,
    CurvedPlumeSource,
    CurvedPlumeStation,
    IdealGasMixtureThermodynamics,
    MixtureState,
    MixtureThermodynamics,
    UniformAmbientField,
)

__all__ = (
    'ActuatorDiskWakeField',
    'AmbientState',
    'AmbientStateField',
    'AmbientVelocityField',
    'CompositeVelocityField',
    'ConstantDensityFreeJetExactSolution',
    'ConstantDensityMixtureThermodynamics',
    'ConstantEntrainment',
    'CurvedPlumeOptions',
    'CurvedPlumeResult',
    'CurvedPlumeSource',
    'CurvedPlumeSourceTermModel',
    'CurvedPlumeSourceTerms',
    'CurvedPlumeStation',
    'CurvedPlumeTermination',
    'DevelopingShearForcedEntrainment',
    'EntrainmentModel',
    'IdealGasMixtureThermodynamics',
    'MixtureState',
    'MixtureThermodynamics',
    'OrthogonalUniformCrossflowExactSolution',
    'UniformAmbientField',
    'UniformVelocityField',
    'VelocityAugmentedAmbientField',
    'ZeroCurvedPlumeSourceTermModel',
    'calculateConstantDensityFreeJetExact',
    'calculateOrthogonalUniformCrossflowExact',
    'solveCurvedPlume',
)
