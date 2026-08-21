# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from itertools import chain
from typing import Dict, Hashable, List, Mapping, Optional, Sequence, Set, TypeVar

__all__ = (
    'reverseDict',
    'lod2dol',
    'dol2lod',
)
#######################

K = TypeVar('K', bound=Hashable)
V = TypeVar('V', bound=Hashable)


def reverseDict(data: Mapping[K, V]) -> Dict[V, Set[K]]:
  out: Dict[V, Set[K]] = {}
  for k, v in data.items():
    if v not in out:
      out[v] = {k, }
    else:
      out[v].add(k)
    ##
  ##
  return out
##


def lod2dol(lod: Sequence[Mapping[K, V]]) -> Dict[K, List[Optional[V]]]:
  # DOCME
  keys = frozenset(chain(*(d for d in lod)))
  N = len(lod)
  dol: Dict[K, List[Optional[V]]] = {k: [None, ] * N for k in keys}
  for row_idx, row in enumerate(lod):
    for k, v in row.items():
      dol[k][row_idx] = v
    ##
  ##
  return dol
##


def dol2lod(dol: Mapping[K, Sequence[V]]) -> List[Dict[K, Optional[V]]]:
  # DOCME
  if not dol:
    return []
  ##
  N = max(len(v) for v in dol.values())
  if N == 0:
    return []
  ##
  keys = dol.keys()
  out: List[Dict[K, Optional[V]]] = [{k: None for k in keys} for _ in range(N)]
  for k, vv in dol.items():
    for idx, v in enumerate(vv):
      out[idx][k] = v
    ##
  ##
  return out
##
