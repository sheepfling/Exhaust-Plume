# -*- coding: utf-8 -*-
# DOCME
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence, Tuple, Union

from numpy import ndarray

try:
  from typing import ParamSpec  # type: ignore[attr-defined]
except ImportError:
  from typing_extensions import ParamSpec
##

try:
  from typing import TypeAlias  # type: ignore[attr-defined]
except ImportError:
  from typing_extensions import TypeAlias
##

try:
  from typing import Protocol  # type: ignore[attr-defined]
except ImportError:
  from typing_extensions import Protocol  # type: ignore[assignment,misc]
##

__all__ = (
    'ArrayLike',
    'ArrayOrNumberLike',
    'ComplexArrayLike',
    'ComplexArrayOrComplexNumberLike',
    'ComplexNumberLike',
    'ExtensionsType',
    'NumberLike',
    'ParamSpec',
    'PathLike',
    'Protocol',
    'TypeAlias',
    'VoidCallback',
    'FullComparable',
)
################

ExtensionsType = Tuple[str, ...]
PathLike = Union[str, Path]
VoidCallback = Callable[[], None]

NumberLike = Union[float, int]
ArrayLike = Union[ndarray, Sequence[NumberLike]]
ArrayOrNumberLike = Union[NumberLike, ArrayLike]
ComplexNumberLike = Union[int, float, complex]
ComplexArrayLike = Union[ndarray, Sequence[ComplexNumberLike]]
ComplexArrayOrComplexNumberLike = Union[ComplexNumberLike, ComplexArrayLike]


class FullComparable(Protocol):
  """ Definition for protocol """

  def __lt__(self, rhs: Any) -> bool:
    ...

  def __le__(self, rhs: Any) -> bool:
    ...
  ##

  def __gt__(self, rhs: Any) -> bool:
    ...

  def __ge__(self, rhs: Any) -> bool:
    ...

##
