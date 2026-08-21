# -*- coding: utf-8 -*-
from __future__ import annotations

from matplotlib import colormaps
from matplotlib.colors import Colormap
from matplotlib.pyplot import get_cmap as plt_get_cmap

__all__ = (
    'get_cmap',
)
#############################


def get_cmap(name: str) -> Colormap:
  if hasattr(colormaps, 'get_cmap'):
    # python >=3.8
    return colormaps.get_cmap(name)
  ##
  # fallback for python <=3.7
  return plt_get_cmap(name)
##
