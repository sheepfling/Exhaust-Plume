# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Mapping, Optional, Sequence, Tuple, Union

import matplotlib.axes
import matplotlib.figure

from exhaust_plume.hub import ChannelType, NameType
from exhaust_plume.uid import Uid
from exhaust_plume.util.color_util import ColorRGB
from exhaust_plume.util.error_util import ExceptionInfo

__all__ = (
    'AxesSubplotType',
    'FigureType',
    'PlotColorType',
    'PlotResults',
    'PostPlotCallback',
    'Topic2PublisherGraph',
    'Topic2SubscriberGraph',
    'UidToNameType',
)
##########################
FigureType = matplotlib.figure.Figure
AxesSubplotType = matplotlib.axes.Subplot
Topic2PublisherGraph = Mapping[ChannelType, FrozenSet[NameType]]
Topic2SubscriberGraph = Topic2PublisherGraph
UidToNameType = Mapping[Uid, str]
PostPlotCallback = Callable[[matplotlib.figure.Figure, Mapping[str, Any]], Tuple[Optional[matplotlib.figure.Figure], Dict[str, Any]]]
# ^ unable to use TypeAlias because it doesn't exist until. python>3.10


PlotColorType = Union[str, Tuple[float, float, float], Tuple[float, float, float, float], ColorRGB]


@dataclass(frozen=True)
class PlotResults:
  # DOCME
  figures: Sequence[matplotlib.figure.Figure]
  exceptions_raised: Sequence[ExceptionInfo]
##
