from __future__ import annotations

import pytest

from exhaust_plume.compat import legacy_num_plumes_to_max_cells, legacy_plume_index_to_cell_index


def test_legacy_num_plumes_maps_to_max_cells_with_warning() -> None:
  with pytest.warns(DeprecationWarning):
    assert legacy_num_plumes_to_max_cells(3) == 3
  ####


def test_legacy_plume_index_is_the_canonical_cell_index() -> None:
  assert legacy_plume_index_to_cell_index(1) == 1
  with pytest.raises(ValueError):
    legacy_plume_index_to_cell_index(0)
  ####
