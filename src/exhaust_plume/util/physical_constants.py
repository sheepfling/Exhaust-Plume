"""Physical constants used by the compressible-flow model, in SI units."""

from __future__ import annotations

R_GAS_CONSTANT = 8.31446261815324  # J/(mol K)
PASCAL_PER_ATM = 101325.0
ATM_PER_PASCAL = 1.0 / PASCAL_PER_ATM

__all__ = ('R_GAS_CONSTANT', 'PASCAL_PER_ATM', 'ATM_PER_PASCAL')
