"""Explicit mappings for the legacy ``plume`` terminology."""

from __future__ import annotations

from numbers import Integral
from warnings import warn

__all__ = ("legacy_num_plumes_to_max_cells", "legacy_plume_index_to_cell_index")


def legacy_num_plumes_to_max_cells(num_plumes: int) -> int:
  """Map the legacy construction-pass count to the canonical safety limit."""

  if isinstance(num_plumes, bool) or not isinstance(num_plumes, Integral) or num_plumes < 1:
    raise ValueError(f"num_plumes must be an integer >= 1; got {num_plumes!r}")
  ####
  warn("num_plumes is a legacy alias for max_cells", DeprecationWarning, stacklevel=2)
  return int(num_plumes)
####


def legacy_plume_index_to_cell_index(plume_index: int) -> int:
  """Preserve the legacy one-based index while exposing its cell meaning."""

  if isinstance(plume_index, bool) or not isinstance(plume_index, Integral) or plume_index < 1:
    raise ValueError(f"plume_index must be an integer >= 1; got {plume_index!r}")
  ####
  return int(plume_index)
####
