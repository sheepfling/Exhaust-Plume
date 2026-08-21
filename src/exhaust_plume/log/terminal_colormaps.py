# -*- coding: utf-8 -*-
from __future__ import annotations

from functools import partial
from typing import Callable, List, Mapping

from matplotlib import pyplot as plt
from numpy import linspace

from exhaust_plume.log.terminal_format import determineClosestVisualColor
from exhaust_plume.util.color_util import ColorRGB

__all__ = (
    'ColorMap', 'viridis', 'Accent', 'Blues', 'BrBG', 'BuGn', 'BuPu', 'CMRmap',
    'Dark2', 'GnBu', 'Greens', 'Greys', 'OrRd', 'Oranges', 'PRGn', 'Paired',
    'Pastel1', 'Pastel2', 'PiYG', 'PuBu', 'PuBuGn', 'PuOr', 'PuRd', 'Purples',
    'RdBu', 'RdGy', 'RdPu', 'RdYlBu', 'RdYlGn', 'Reds', 'Set1', 'Set2',
    'Set3', 'Spectral', 'Wistia', 'YlGn', 'YlGnBu', 'YlOrBr', 'YlOrRd', 'afmhot',
    'autumn', 'binary', 'bone', 'brg', 'bwr', 'cividis', 'cool', 'coolwarm',
    'copper', 'cubehelix', 'flag', 'gist_earth', 'gist_gray', 'gist_heat', 'gist_ncar', 'gist_rainbow',
    'gist_stern', 'gist_yarg', 'gnuplot', 'gnuplot2', 'gray', 'hot', 'hsv', 'inferno',
    'jet', 'magma', 'nipy_spectral', 'ocean', 'pink', 'plasma', 'prism', 'rainbow',
    'seismic', 'spring', 'summer', 'tab10', 'tab20', 'tab20b', 'tab20c', 'terrain',
    'turbo', 'twilight', 'twilight_shifted', 'winter',
    'getPerceptuallyUniformMaps', 'getSequentialMaps',
    'getSequential2Maps', 'getDivergingMaps',
    'getCyclicalMaps', 'getQualitativeMaps',
    'getMiscellaneousMaps', 'getAllMaps',
    'getColorMapByName',
    'getConstantColorMap',
)

#######################

cm_viridis = plt.get_cmap('viridis')
cm_Accent = plt.get_cmap('Accent')
cm_Blues = plt.get_cmap('Blues')
cm_BrBG = plt.get_cmap('BrBG')
cm_BuGn = plt.get_cmap('BuGn')
cm_BuPu = plt.get_cmap('BuPu')
cm_CMRmap = plt.get_cmap('CMRmap')
cm_Dark2 = plt.get_cmap('Dark2')
cm_GnBu = plt.get_cmap('GnBu')
cm_Greens = plt.get_cmap('Greens')
cm_Greys = plt.get_cmap('Greys')
cm_OrRd = plt.get_cmap('OrRd')
cm_Oranges = plt.get_cmap('Oranges')
cm_PRGn = plt.get_cmap('PRGn')
cm_Paired = plt.get_cmap('Paired')
cm_Pastel1 = plt.get_cmap('Pastel1')
cm_Pastel2 = plt.get_cmap('Pastel2')
cm_PiYG = plt.get_cmap('PiYG')
cm_PuBu = plt.get_cmap('PuBu')
cm_PuBuGn = plt.get_cmap('PuBuGn')
cm_PuOr = plt.get_cmap('PuOr')
cm_PuRd = plt.get_cmap('PuRd')
cm_Purples = plt.get_cmap('Purples')
cm_RdBu = plt.get_cmap('RdBu')
cm_RdGy = plt.get_cmap('RdGy')
cm_RdPu = plt.get_cmap('RdPu')
cm_RdYlBu = plt.get_cmap('RdYlBu')
cm_RdYlGn = plt.get_cmap('RdYlGn')
cm_Reds = plt.get_cmap('Reds')
cm_Set1 = plt.get_cmap('Set1')
cm_Set2 = plt.get_cmap('Set2')
cm_Set3 = plt.get_cmap('Set3')
cm_Spectral = plt.get_cmap('Spectral')
cm_Wistia = plt.get_cmap('Wistia')
cm_YlGn = plt.get_cmap('YlGn')
cm_YlGnBu = plt.get_cmap('YlGnBu')
cm_YlOrBr = plt.get_cmap('YlOrBr')
cm_YlOrRd = plt.get_cmap('YlOrRd')
cm_afmhot = plt.get_cmap('afmhot')
cm_autumn = plt.get_cmap('autumn')
cm_binary = plt.get_cmap('binary')
cm_bone = plt.get_cmap('bone')
cm_brg = plt.get_cmap('brg')
cm_bwr = plt.get_cmap('bwr')
cm_cividis = plt.get_cmap('cividis')
cm_cool = plt.get_cmap('cool')
cm_coolwarm = plt.get_cmap('coolwarm')
cm_copper = plt.get_cmap('copper')
cm_cubehelix = plt.get_cmap('cubehelix')
cm_flag = plt.get_cmap('flag')
cm_gist_earth = plt.get_cmap('gist_earth')
cm_gist_gray = plt.get_cmap('gist_gray')
cm_gist_heat = plt.get_cmap('gist_heat')
cm_gist_ncar = plt.get_cmap('gist_ncar')
cm_gist_rainbow = plt.get_cmap('gist_rainbow')
cm_gist_stern = plt.get_cmap('gist_stern')
cm_gist_yarg = plt.get_cmap('gist_yarg')
cm_gnuplot = plt.get_cmap('gnuplot')
cm_gnuplot2 = plt.get_cmap('gnuplot2')
cm_gray = plt.get_cmap('gray')
cm_hot = plt.get_cmap('hot')
cm_hsv = plt.get_cmap('hsv')
cm_inferno = plt.get_cmap('inferno')
cm_jet = plt.get_cmap('jet')
cm_magma = plt.get_cmap('magma')
cm_nipy_spectral = plt.get_cmap('nipy_spectral')
cm_ocean = plt.get_cmap('ocean')
cm_pink = plt.get_cmap('pink')
cm_plasma = plt.get_cmap('plasma')
cm_prism = plt.get_cmap('prism')
cm_rainbow = plt.get_cmap('rainbow')
cm_seismic = plt.get_cmap('seismic')
cm_spring = plt.get_cmap('spring')
cm_summer = plt.get_cmap('summer')
cm_tab10 = plt.get_cmap('tab10')
cm_tab20 = plt.get_cmap('tab20')
cm_tab20b = plt.get_cmap('tab20b')
cm_tab20c = plt.get_cmap('tab20c')
cm_terrain = plt.get_cmap('terrain')
cm_turbo = plt.get_cmap('turbo')
cm_twilight = plt.get_cmap('twilight')
cm_twilight_shifted = plt.get_cmap('twilight_shifted')
cm_winter = plt.get_cmap('winter')

ColorMap = Callable[[int], List[ColorRGB]]


def viridis(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_viridis(linspace(0., 1., num_points))]
##


def Accent(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Accent(linspace(0., 1., num_points))]
##


def Blues(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Blues(linspace(0., 1., num_points))]
##


def BrBG(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_BrBG(linspace(0., 1., num_points))]
##


def BuGn(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_BuGn(linspace(0., 1., num_points))]
##


def BuPu(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_BuPu(linspace(0., 1., num_points))]
##


def CMRmap(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_CMRmap(linspace(0., 1., num_points))]
##


def Dark2(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Dark2(linspace(0., 1., num_points))]
##


def GnBu(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_GnBu(linspace(0., 1., num_points))]
##


def Greens(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Greens(linspace(0., 1., num_points))]
##


def Greys(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Greys(linspace(0., 1., num_points))]
##


def OrRd(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_OrRd(linspace(0., 1., num_points))]
##


def Oranges(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Oranges(linspace(0., 1., num_points))]
##


def PRGn(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_PRGn(linspace(0., 1., num_points))]
##


def Paired(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Paired(linspace(0., 1., num_points))]
##


def Pastel1(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Pastel1(linspace(0., 1., num_points))]
##


def Pastel2(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Pastel2(linspace(0., 1., num_points))]
##


def PiYG(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_PiYG(linspace(0., 1., num_points))]
##


def PuBu(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_PuBu(linspace(0., 1., num_points))]
##


def PuBuGn(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_PuBuGn(linspace(0., 1., num_points))]
##


def PuOr(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_PuOr(linspace(0., 1., num_points))]
##


def PuRd(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_PuRd(linspace(0., 1., num_points))]
##


def Purples(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Purples(linspace(0., 1., num_points))]
##


def RdBu(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_RdBu(linspace(0., 1., num_points))]
##


def RdGy(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_RdGy(linspace(0., 1., num_points))]
##


def RdPu(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_RdPu(linspace(0., 1., num_points))]
##


def RdYlBu(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_RdYlBu(linspace(0., 1., num_points))]
##


def RdYlGn(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_RdYlGn(linspace(0., 1., num_points))]
##


def Reds(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Reds(linspace(0., 1., num_points))]
##


def Set1(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Set1(linspace(0., 1., num_points))]
##


def Set2(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Set2(linspace(0., 1., num_points))]
##


def Set3(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Set3(linspace(0., 1., num_points))]
##


def Spectral(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Spectral(linspace(0., 1., num_points))]
##


def Wistia(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_Wistia(linspace(0., 1., num_points))]
##


def YlGn(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_YlGn(linspace(0., 1., num_points))]
##


def YlGnBu(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_YlGnBu(linspace(0., 1., num_points))]
##


def YlOrBr(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_YlOrBr(linspace(0., 1., num_points))]
##


def YlOrRd(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_YlOrRd(linspace(0., 1., num_points))]
##


def afmhot(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_afmhot(linspace(0., 1., num_points))]
##


def autumn(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_autumn(linspace(0., 1., num_points))]
##


def binary(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_binary(linspace(0., 1., num_points))]
##


def bone(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_bone(linspace(0., 1., num_points))]
##


def brg(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_brg(linspace(0., 1., num_points))]
##


def bwr(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_bwr(linspace(0., 1., num_points))]
##


def cividis(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_cividis(linspace(0., 1., num_points))]
##


def cool(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_cool(linspace(0., 1., num_points))]
##


def coolwarm(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_coolwarm(linspace(0., 1., num_points))]
##


def copper(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_copper(linspace(0., 1., num_points))]
##


def cubehelix(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_cubehelix(linspace(0., 1., num_points))]
##


def flag(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_flag(linspace(0., 1., num_points))]
##


def gist_earth(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_gist_earth(linspace(0., 1., num_points))]
##


def gist_gray(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_gist_gray(linspace(0., 1., num_points))]
##


def gist_heat(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_gist_heat(linspace(0., 1., num_points))]
##


def gist_ncar(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_gist_ncar(linspace(0., 1., num_points))]
##


def gist_rainbow(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_gist_rainbow(linspace(0., 1., num_points))]
##


def gist_stern(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_gist_stern(linspace(0., 1., num_points))]
##


def gist_yarg(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_gist_yarg(linspace(0., 1., num_points))]
##


def gnuplot(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_gnuplot(linspace(0., 1., num_points))]
##


def gnuplot2(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_gnuplot2(linspace(0., 1., num_points))]
##


def gray(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_gray(linspace(0., 1., num_points))]
##


def hot(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_hot(linspace(0., 1., num_points))]
##


def hsv(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_hsv(linspace(0., 1., num_points))]
##


def inferno(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_inferno(linspace(0., 1., num_points))]
##


def jet(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_jet(linspace(0., 1., num_points))]
##


def magma(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_magma(linspace(0., 1., num_points))]
##


def nipy_spectral(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_nipy_spectral(linspace(0., 1., num_points))]
##


def ocean(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_ocean(linspace(0., 1., num_points))]
##


def pink(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_pink(linspace(0., 1., num_points))]
##


def plasma(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_plasma(linspace(0., 1., num_points))]
##


def prism(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_prism(linspace(0., 1., num_points))]
##


def rainbow(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_rainbow(linspace(0., 1., num_points))]
##


def seismic(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_seismic(linspace(0., 1., num_points))]
##


def spring(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_spring(linspace(0., 1., num_points))]
##


def summer(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_summer(linspace(0., 1., num_points))]
##


def tab10(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_tab10(linspace(0., 1., num_points))]
##


def tab20(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_tab20(linspace(0., 1., num_points))]
##


def tab20b(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_tab20b(linspace(0., 1., num_points))]
##


def tab20c(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_tab20c(linspace(0., 1., num_points))]
##


def terrain(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_terrain(linspace(0., 1., num_points))]
##


def turbo(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_turbo(linspace(0., 1., num_points))]
##


def twilight(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_twilight(linspace(0., 1., num_points))]
##


def twilight_shifted(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_twilight_shifted(linspace(0., 1., num_points))]
##


def winter(num_points: int) -> List[ColorRGB]:
  return [determineClosestVisualColor(ColorRGB.fromSequence(color)) for color in cm_winter(linspace(0., 1., num_points))]
##


def _partialConstantColorMap(num_points: int, color: ColorRGB) -> List[ColorRGB]:
  return [color, ] * num_points
##


def getConstantColorMap(color: ColorRGB) -> ColorMap:
  closest_color = determineClosestVisualColor(color)
  return partial(_partialConstantColorMap, color=closest_color)
##


_perceptually_uniform = {fn.__name__: fn for fn in (viridis, plasma, inferno, magma, cividis,)}
_sequential_maps = {fn.__name__: fn for fn in (
    Greys, Purples, Blues, Greens, Oranges, Reds,
    YlOrBr, YlOrRd, OrRd, PuRd, RdPu, BuPu,
    GnBu, PuBu, YlGnBu, PuBuGn, BuGn, YlGn,
)}
_sequential2_maps = {fn.__name__: fn for fn in (
    binary, gist_yarg, gist_gray, gray, bone,
    pink, spring, summer, autumn, winter, cool,
    Wistia, hot, afmhot, gist_heat, copper,
)}
_diverging_maps = {fn.__name__: fn for fn in (
    PiYG, PRGn, BrBG, PuOr, RdGy, RdBu, RdYlBu,
    RdYlGn, Spectral, coolwarm, bwr, seismic,
)}
_cyclical_maps = {fn.__name__: fn for fn in (twilight, twilight_shifted, hsv,)}
_qualitative_maps = {fn.__name__: fn for fn in (
    Pastel1, Pastel2, Paired, Accent, Dark2,
    Set1, Set2, Set3, tab10, tab20, tab20b,
    tab20c,
)}
_miscellaneous_maps = {fn.__name__: fn for fn in (
    flag, prism, ocean, gist_earth, terrain,
    gist_stern, gnuplot, gnuplot2, CMRmap,
    cubehelix, brg, gist_rainbow, rainbow, jet,
    turbo, nipy_spectral, gist_ncar,
)}
_all_maps = {
    **{k.lower(): v for k, v in _perceptually_uniform.items()},
    **{k.lower(): v for k, v in _sequential_maps.items()},
    **{k.lower(): v for k, v in _sequential2_maps.items()},
    **{k.lower(): v for k, v in _diverging_maps.items()},
    **{k.lower(): v for k, v in _cyclical_maps.items()},
    **{k.lower(): v for k, v in _qualitative_maps.items()},
    **{k.lower(): v for k, v in _miscellaneous_maps.items()},
}


def getPerceptuallyUniformMaps() -> Mapping[str, ColorMap]:
  return _perceptually_uniform
##


def getSequentialMaps() -> Mapping[str, ColorMap]:
  return _sequential_maps
##


def getSequential2Maps() -> Mapping[str, ColorMap]:
  return _sequential2_maps


def getDivergingMaps() -> Mapping[str, ColorMap]:
  return _diverging_maps
##


def getCyclicalMaps() -> Mapping[str, ColorMap]:
  return _cyclical_maps
##


def getQualitativeMaps() -> Mapping[str, ColorMap]:
  return _qualitative_maps
##


def getMiscellaneousMaps() -> Mapping[str, ColorMap]:
  return _miscellaneous_maps
##


def getAllMaps() -> Mapping[str, ColorMap]:
  return _all_maps
##


def getColorMapByName(name: str) -> ColorMap:
  return _all_maps[name.lower()]
##
