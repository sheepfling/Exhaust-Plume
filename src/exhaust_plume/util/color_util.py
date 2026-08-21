# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from math import inf
from typing import Dict, Iterator, Optional, Sequence, Tuple

from numpy import array, asarray, clip, ndarray
from numpy.linalg import norm

from exhaust_plume.util.type_hints import ArrayLike

__all__ = (
    'ALL_XYZ_REFERENCES',
    'STANDARD_XYZ_REFERENCE',
    'XyzTristimulusReference',
    'lookupXyzByNameDegree',
    'ColorRGB',
    'StandardRGB',
    'ColorXYZ', 'ColorCMYK', 'ColorCMY', 'ColorHSL', 'ColorHSV', 'ColorCieLab',
)
#############################

StandardRGB = namedtuple('StandardRGB', 'r g b')
ColorCMY = namedtuple('ColorCMY', 'c m y')
ColorCMYK = namedtuple('ColorCMYK', 'c m y k')
ColorHSV = namedtuple('ColorHSV', 'h s v')
ColorHSL = namedtuple('ColorHSL', 'h s l')
ColorCieLab = namedtuple('ColorCieLab', 'L a b')
ColorXYZ = namedtuple('ColorXYZ', 'x y z')
ColorITP_scaled = namedtuple('ColorITP_scaled', 'i t p')


@dataclass(frozen=True)
class XyzTristimulusReference:
  # DOCME
  illuminant_name: str
  observer_degree: float
  XYZ: ColorXYZ
  illuminant_comment: str
##


ALL_XYZ_REFERENCES: Tuple[XyzTristimulusReference, ...] = (
    XyzTristimulusReference(illuminant_name="A", observer_degree=2., XYZ=ColorXYZ(109.850, 100.000, 35.585), illuminant_comment="Incandescent/tungsten"),
    XyzTristimulusReference(illuminant_name="A", observer_degree=10., XYZ=ColorXYZ(111.144, 100.000, 35.200), illuminant_comment="Incandescent/tungsten"),
    XyzTristimulusReference(illuminant_name="B", observer_degree=2., XYZ=ColorXYZ(99.0927, 100.000, 85.313), illuminant_comment="Old direct sunlight at noon"),
    XyzTristimulusReference(illuminant_name="B", observer_degree=10., XYZ=ColorXYZ(99.178, 100.000, 84.3493), illuminant_comment="Old direct sunlight at noon"),
    XyzTristimulusReference(illuminant_name="C", observer_degree=2., XYZ=ColorXYZ(98.074, 100.000, 118.232), illuminant_comment="Old daylight"),
    XyzTristimulusReference(illuminant_name="C", observer_degree=10., XYZ=ColorXYZ(97.285, 100.000, 116.145), illuminant_comment="Old daylight"),
    XyzTristimulusReference(illuminant_name="D50", observer_degree=2., XYZ=ColorXYZ(96.422, 100.000, 82.521), illuminant_comment="ICC profile PCS"),
    XyzTristimulusReference(illuminant_name="D50", observer_degree=10., XYZ=ColorXYZ(96.720, 100.000, 81.427), illuminant_comment="ICC profile PCS"),
    XyzTristimulusReference(illuminant_name="D55", observer_degree=2., XYZ=ColorXYZ(95.682, 100.000, 92.149), illuminant_comment="Mid-morning daylight"),
    XyzTristimulusReference(illuminant_name="D55", observer_degree=10., XYZ=ColorXYZ(95.799, 100.000, 90.926), illuminant_comment="Mid-morning daylight"),
    XyzTristimulusReference(illuminant_name="D65", observer_degree=2., XYZ=ColorXYZ(95.047, 100.000, 108.883), illuminant_comment="Daylight, sRGB, Adobe-RGB"),
    XyzTristimulusReference(illuminant_name="D65", observer_degree=10., XYZ=ColorXYZ(94.811, 100.000, 107.304), illuminant_comment="Daylight, sRGB, Adobe-RGB"),
    XyzTristimulusReference(illuminant_name="D75", observer_degree=2., XYZ=ColorXYZ(94.972, 100.000, 122.638), illuminant_comment="North sky daylight"),
    XyzTristimulusReference(illuminant_name="D75", observer_degree=10., XYZ=ColorXYZ(94.416, 100.000, 120.641), illuminant_comment="North sky daylight"),
    XyzTristimulusReference(illuminant_name="E", observer_degree=2., XYZ=ColorXYZ(100.000, 100.000, 100.000), illuminant_comment="Equal energy"),
    XyzTristimulusReference(illuminant_name="E", observer_degree=10., XYZ=ColorXYZ(100.000, 100.000, 100.000), illuminant_comment="Equal energy"),
    XyzTristimulusReference(illuminant_name="F1", observer_degree=2., XYZ=ColorXYZ(92.834, 100.000, 103.665), illuminant_comment="Daylight Fluorescent"),
    XyzTristimulusReference(illuminant_name="F1", observer_degree=10., XYZ=ColorXYZ(94.791, 100.000, 103.191), illuminant_comment="Daylight Fluorescent"),
    XyzTristimulusReference(illuminant_name="F2", observer_degree=2., XYZ=ColorXYZ(99.187, 100.000, 67.395), illuminant_comment="Cool fluorescent"),
    XyzTristimulusReference(illuminant_name="F2", observer_degree=10., XYZ=ColorXYZ(103.280, 100.000, 69.026), illuminant_comment="Cool fluorescent"),
    XyzTristimulusReference(illuminant_name="F3", observer_degree=2., XYZ=ColorXYZ(103.754, 100.000, 49.861), illuminant_comment="White Fluorescent"),
    XyzTristimulusReference(illuminant_name="F3", observer_degree=10., XYZ=ColorXYZ(108.968, 100.000, 51.965), illuminant_comment="White Fluorescent"),
    XyzTristimulusReference(illuminant_name="F4", observer_degree=2., XYZ=ColorXYZ(109.147, 100.000, 38.813), illuminant_comment="Warm White Fluorescent"),
    XyzTristimulusReference(illuminant_name="F4", observer_degree=10., XYZ=ColorXYZ(114.961, 100.000, 40.963), illuminant_comment="Warm White Fluorescent"),
    XyzTristimulusReference(illuminant_name="F5", observer_degree=2., XYZ=ColorXYZ(90.872, 100.000, 98.723), illuminant_comment="Daylight Fluorescent"),
    XyzTristimulusReference(illuminant_name="F5", observer_degree=10., XYZ=ColorXYZ(93.369, 100.000, 98.636), illuminant_comment="Daylight Fluorescent"),
    XyzTristimulusReference(illuminant_name="F6", observer_degree=2., XYZ=ColorXYZ(97.309, 100.000, 60.191), illuminant_comment="Lite White Fluorescent"),
    XyzTristimulusReference(illuminant_name="F6", observer_degree=10., XYZ=ColorXYZ(102.148, 100.000, 62.074), illuminant_comment="Lite White Fluorescent"),
    XyzTristimulusReference(illuminant_name="F7", observer_degree=2., XYZ=ColorXYZ(95.044, 100.000, 108.755), illuminant_comment="Daylight fluorescent, D65 simulator"),
    XyzTristimulusReference(illuminant_name="F7", observer_degree=10., XYZ=ColorXYZ(95.792, 100.000, 107.687), illuminant_comment="Daylight fluorescent, D65 simulator"),
    XyzTristimulusReference(illuminant_name="F8", observer_degree=2., XYZ=ColorXYZ(96.413, 100.000, 82.333), illuminant_comment="Sylvania F40, D50 simulator"),
    XyzTristimulusReference(illuminant_name="F8", observer_degree=10., XYZ=ColorXYZ(97.115, 100.000, 81.135), illuminant_comment="Sylvania F40, D50 simulator"),
    XyzTristimulusReference(illuminant_name="F9", observer_degree=2., XYZ=ColorXYZ(100.365, 100.000, 67.868), illuminant_comment="Cool White Fluorescent"),
    XyzTristimulusReference(illuminant_name="F9", observer_degree=10., XYZ=ColorXYZ(102.116, 100.000, 67.826), illuminant_comment="Cool White Fluorescent"),
    XyzTristimulusReference(illuminant_name="F10", observer_degree=2., XYZ=ColorXYZ(96.174, 100.000, 81.712), illuminant_comment="Ultralume 50, Philips TL85"),
    XyzTristimulusReference(illuminant_name="F10", observer_degree=10., XYZ=ColorXYZ(99.001, 100.000, 83.134), illuminant_comment="Ultralume 50, Philips TL85"),
    XyzTristimulusReference(illuminant_name="F11", observer_degree=2., XYZ=ColorXYZ(100.966, 100.000, 64.370), illuminant_comment="Ultralume 40, Philips TL84"),
    XyzTristimulusReference(illuminant_name="F11", observer_degree=10., XYZ=ColorXYZ(103.866, 100.000, 65.627), illuminant_comment="Ultralume 40, Philips TL84"),
    XyzTristimulusReference(illuminant_name="F12", observer_degree=2., XYZ=ColorXYZ(108.046, 100.000, 39.228), illuminant_comment="Ultralume 30, Philips TL83"),
    XyzTristimulusReference(illuminant_name="F12", observer_degree=10., XYZ=ColorXYZ(111.428, 100.000, 40.353), illuminant_comment="Ultralume 30, Philips TL83"),
)
_xyz_lookup: Dict[Tuple[str, float], XyzTristimulusReference] = {(ref.illuminant_name, ref.observer_degree,): ref for ref in ALL_XYZ_REFERENCES}
STANDARD_XYZ_REFERENCE: XyzTristimulusReference = _xyz_lookup[('D65', 2.)]


def lookupXyzByNameDegree(name: str, degree: float) -> Optional[XyzTristimulusReference]:
  # DOCME
  try:
    return _xyz_lookup[(name, degree,)]
  except KeyError:
    return None
  ##
##


# def _clip(x, mn, mx):
#   # DOCME
#   if x < mn:
#     return mn
#   elif x > mx:
#     return mx
#   else:
#     return x
#   ##
# ##


def _hue2rgb(v1: float, v2: float, vH: float) -> float:
  # DOCME
  if vH < 0.:
    vH += 1.
  elif vH > 1.:
    vH -= 1.
  ##
  if vH < (1. / 6.):
    return v1 + (v2 - v1) * 6. * vH
  elif vH < 0.5:
    return v2
  elif vH < (2. / 3.):
    return v1 + (v2 - v1) * ((2. / 3.) - vH) * 6.
  else:
    return v1
  ##
##

##############


class _PerceptualQuantizer:
  """
  Perceptual Quantizer (PQ) Function Definition:
  quote: The PQ specification achieves a very wide range of brightness levels for a given bit depth
  using a non-linear transfer function that is finely tuned to match the human visual system.

  quote: ICTCP is defined such that the entire BT.2020 space fits into
  the range [0, 1] for I and
  the range [-0.5, +0.5] for the two chroma components

  Links:
    - reference: https://en.wikipedia.org/wiki/Perceptual_quantizer
      archives:
       - https://archive.is/ktaN2
       - https://web.archive.org/web/20220205195228/https://en.wikipedia.org/wiki/Perceptual_quantizer

  ICtCp / ITP (REc. ITU-R BT.2100) (Newer Perceptual Uniform space)
  Links:
    - reference: https://en.wikipedia.org/wiki/ICtCp
      archives:
       - https://archive.is/b7SIu
       - https://web.archive.org/web/20220205195021/https://en.wikipedia.org/wiki/ICtCp
    - reference: https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.2100-2-201807-I!!PDF-E.pdf
      archives:
       - https://web.archive.org/web/20220131201431/https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.2100-2-201807-I%21%21PDF-E.pdf
       - https://web.archive.org/web/20220127081947/https://www.itu.int/rec/R-REC-BT.2100
  """
  # Table 4.
  _m1 = 2610. / 16384.
  _inv_m1 = 1. / _m1
  _m2 = 2523. / 32.
  _inv_m2 = 1. / _m2
  _c2 = 2413. / 128.
  _c3 = 2392. / 128.
  _c1 = _c3 - _c2 + 1.

  # Table 7.
  _rgb2lms_M = 1. / 4096. * array([
      [1688., 2146., 262., ],
      [683., 2951., 462., ],
      [99., 309., 3688., ],
  ], dtype='float')

  _lms_prime2ictcp_pq = 1. / 4096. * array([
      [2048., 2048., 0., ],
      [6610., -13613., 7003., ],
      [17933., -17390., -543., ],
  ], dtype='float')

  _ictcp2itp = array([
      [1., 0., 0.],
      [0., .5, 0.],
      [0., 0., 1.]
  ])

  @classmethod
  def EOTF(cls, Ep: ArrayLike) -> ndarray:
    """ Electro-Optical Transfer function """
    Ep = asarray(Ep, dtype='float')
    Ep_inv_m2 = Ep**cls._inv_m2
    Fd = 10000. * (clip(Ep_inv_m2 - cls._c1, 0., inf) / (cls._c2 - cls._c3 * Ep_inv_m2))**cls._inv_m1
    return asarray(Fd, 'float')
  ##

  @classmethod
  def EOTF_inv(cls, Fd: ArrayLike) -> ndarray:
    """ Electro-Optical Transfer function Inverse """
    Fd = asarray(Fd, dtype='float')
    Ym1 = (Fd / 10000.)**cls._m1
    Ep = ((cls._c1 + cls._c2 * Ym1) / (1 + cls._c3 * Ym1))**cls._m2
    return Ep
  ##

  @classmethod
  def rgb2lms(cls, rgb: ArrayLike) -> ndarray:
    # DOCME
    # Table 7 & Table 10
    # Linear RGB
    # Primary Red   (R): 630 nm
    # Primary Green (G): 532 nm
    # Primary Blue  (B): 467 nm
    # R = G = B = 1.0 represents 1.0 cd/m^2 on reference display & Maximum diffuse white level
    rgb = asarray(rgb, 'float')
    return asarray(cls._rgb2lms_M @ rgb, 'float')
  ##

  @classmethod
  def lms_prime2ictcp(cls, lms_prime: ArrayLike) -> ndarray:
    # DOCME
    # Table 7
    lms_prime = asarray(lms_prime, dtype='float')
    return asarray(cls._lms_prime2ictcp_pq @ lms_prime, 'float')
  ##

  @classmethod
  def lms2lms_prime(cls, lms: ArrayLike) -> ndarray:
    # DOCME
    # Table 7
    lms_prime = cls.EOTF_inv(lms)
    return lms_prime
  ##

  @classmethod
  def rgb2ictcp(cls, rgb: ArrayLike) -> ndarray:
    # DOCME
    # Heading 2. Step 4.
    lms = cls.rgb2lms(rgb)
    lms_prime = cls.lms2lms_prime(lms)
    ictcp = cls.lms_prime2ictcp(lms_prime)
    return ictcp
  ##

  @classmethod
  def rgb2itp(cls, rgb: ArrayLike) -> ndarray:
    # DOCME
    ictcp = cls.rgb2ictcp(rgb)
    itp = asarray(cls._ictcp2itp @ ictcp, 'float')
    return itp
  ##

  @classmethod
  def rgb2scaled_itp(cls, rgb: ArrayLike) -> ndarray:
    # DOCME
    # 720*sqrt((I-I)^2 + (T-T)^2 + (P-P)^2) >= 1
    # -> means a JND (just noticeable difference)
    return 720. * cls.rgb2itp(rgb)
  ##
##


##########################################

@dataclass(frozen=True)
class ColorRGB:
  # DOCME
  # Colors as floats [0,1]
  r: float
  g: float
  b: float

  def asTuple(self) -> Tuple[float, float, float]:
    # DOCME
    out = (self.r, self.g, self.b,)
    return out
  ##

  @classmethod
  def fromTuple(cls, color_tuple: Tuple[float, ...]) -> ColorRGB:
    # DOCME
    out = ColorRGB(
        r=color_tuple[0],
        g=color_tuple[1],
        b=color_tuple[2],
    )
    return out
  ##

  @classmethod
  def fromSequence(cls, color_seq: Sequence[float]) -> ColorRGB:
    # DOCME
    out = ColorRGB(
        r=color_seq[0],
        g=color_seq[1],
        b=color_seq[2],
    )
    return out
  ##

  def asStandardRgb(self) -> StandardRGB:
    # DOCME
    r, g, b = (int(c * 255.) for c in self.asTuple())
    return StandardRGB(r, g, b)
  ##

  @classmethod
  def fromStandardRgb(cls, sRGB: StandardRGB) -> ColorRGB:
    # DOCME
    out = ColorRGB(
        r=float(sRGB[0] / 255.),
        g=float(sRGB[1] / 255.),
        b=float(sRGB[2] / 255.),
    )
    return out
  ##

  def asXYZ(self) -> ColorXYZ:
    # DOCME
    # X, Y and Z output refer to a D65 / 2° standard illuminant.
    var_rgb = (self.r, self.g, self.b,)
    var_R, var_G, var_B = [(((c + 0.055) / 1.055)**2.4 if c > 0.04045 else (c / 12.92)) * 100. for c in var_rgb]
    X = var_R * 0.4124 + var_G * 0.3576 + var_B * 0.1805
    Y = var_R * 0.2126 + var_G * 0.7152 + var_B * 0.0722
    Z = var_R * 0.0193 + var_G * 0.1192 + var_B * 0.9505
    out = ColorXYZ(X, Y, Z)
    return out
  ##

  @classmethod
  def fromXYZ(cls, XYZ: ColorXYZ) -> ColorRGB:
    # DOCME
    var_X, var_Y, var_Z = [c / 100. for c in XYZ]
    var_R = var_X * 3.2406 + var_Y * -1.5372 + var_Z * -0.4986
    var_G = var_X * -0.9689 + var_Y * 1.8758 + var_Z * 0.0415
    var_B = var_X * 0.0557 + var_Y * -0.2040 + var_Z * 1.0570
    r, g, b = [(1.055 * (c**(1. / 2.4)) - 0.055) if c > 0.0031308 else (12.92 * c) for c in (var_R, var_G, var_B,)]
    out = ColorRGB(
        r=float(clip(r, 0., 1.)),
        g=float(clip(g, 0., 1.)),
        b=float(clip(b, 0., 1.)),
    )
    return out
  ##

  def asCielab(self, reference_XYZ: Optional[ColorXYZ] = None) -> ColorCieLab:
    # DOCME
    if reference_XYZ is None:
      reference_XYZ = STANDARD_XYZ_REFERENCE.XYZ
    ##
    XYZ = self.asXYZ()
    var_XYZ = [(c**(1. / 3.)) if c > .008856 else ((7.787 * c) + (16. / 116.)) for c in (c / s for c, s in zip(XYZ, reference_XYZ))]
    var_X, var_Y, var_Z = var_XYZ
    L = (116. * var_Y) - 16.
    a = 500. * (var_X - var_Y)
    b = 200. * (var_Y - var_Z)
    out = ColorCieLab(L, a, b)
    return out
  ##

  @classmethod
  def fromCielab(cls, cie_lab: ColorCieLab, reference_XYZ: Optional[ColorXYZ] = None) -> ColorRGB:
    # DOCME
    if reference_XYZ is None:
      reference_XYZ = STANDARD_XYZ_REFERENCE.XYZ
    ##
    cie_L = cie_lab[0]
    cie_a = cie_lab[1]
    cie_b = cie_lab[2]
    var_Y = (cie_L * + 16.) / 116.
    var_X = cie_a / 500. + var_Y
    var_Z = var_Y - cie_b / 200.

    xyz = ((c**3) if ((c**3) > 0.008856) else ((c - 16. / 116.) / 7.787) for c in (var_X, var_Y, var_Z,))
    X, Y, Z = (c * scale for c, scale in zip(xyz, reference_XYZ))
    return ColorRGB.fromXYZ(XYZ=ColorXYZ(X, Y, Z))
  ##

  def asHsl(self) -> ColorHSL:
    # DOCME
    # H,S,L input range = [0., 1.]
    var_min = min(self.r, self.g, self.b)
    var_max = max(self.r, self.g, self.b)
    del_max = var_max - var_min

    L = (var_max + var_min) / 2.
    if del_max == 0.:
      # this is a gray, no chroma
      H = 0.
      S = 0.
      out = ColorHSL(H, S, L)
      return out
    ##
    if L < 0.5:
      S = del_max / (var_max + var_min)
    else:
      S = del_max / (2 - var_max - var_min)
    ##
    del_R = (((var_max - self.r) / 6) + (del_max / 2)) / del_max
    del_G = (((var_max - self.g) / 6) + (del_max / 2)) / del_max
    del_B = (((var_max - self.b) / 6) + (del_max / 2)) / del_max

    if self.r == var_max:
      H = del_B - del_G
    elif self.g == var_max:
      H = (1. / 3.) + del_R - del_B
    else:
      # self.b == var_max
      H = (2. / 3.) + del_G - del_R
    ##

    if H < 0.:
      H += 1.
    elif H > 1.:
      H -= 1.
    ##
    out = ColorHSL(H, S, L)
    return out
  ##

  @classmethod
  def fromHsl(cls, hsl: ColorHSL) -> ColorRGB:
    # DOCME
    # H,S,L input range = [0., 1.]
    H, S, L = hsl
    if S == 0.:
      out = ColorRGB(
          r=L,
          g=L,
          b=L
      )
      return out
    ##
    var_2 = (L * (1. + S)) if (L < 0.5) else ((L + S) - (S * L))
    var_1 = 2. * L - var_2
    r = _hue2rgb(var_1, var_2, H + (1. / 3.))
    g = _hue2rgb(var_1, var_2, H)
    b = _hue2rgb(var_1, var_2, H - (1. / 3.))
    out = ColorRGB(
        r=r,
        g=g,
        b=b
    )
    return out
  ##

  def asHsv(self) -> ColorHSV:
    # DOCME
    # H,S,V input range = [0., 1.]
    var_min = min(self.r, self.g, self.b)
    var_max = max(self.r, self.g, self.b)
    del_max = var_max - var_min

    V = var_max
    if del_max == 0.:
      # this is a gray
      H = 0.
      S = 0.
      out = ColorHSV(H, S, V)
      return out
    ##
    S = del_max / var_max
    del_R, del_G, del_B = ((((var_max - c) / 6. + del_max / 2.) / del_max) for c in (self.r, self.g, self.b,))

    if self.r == var_max:
      H = del_B - del_G
    elif self.g == var_max:
      H = (1. / 3.) + del_R - del_B
    else:
      # self.b == var_max
      H = (2. / 3.) + del_G - del_R
    ##

    if H < 0.:
      H += 1
    elif H > 1.:
      H -= 1
    ##
    out = ColorHSV(H, S, V)
    return out
  ##

  @classmethod
  def fromHsv(cls, hsv: ColorHSV) -> ColorRGB:
    # DOCME
    # H,S,V input range = [0., 1.]
    H, S, V = hsv
    if S == 0.:
      out = ColorRGB(
          r=V,
          g=V,
          b=V
      )
      return out
    ##
    var_h = H * 6.
    if var_h >= 6:
      var_h = 0.  # H must be <=1
    ##
    var_i = int(var_h)
    var_1 = V * (1. - S)
    var_2 = V * (1. - S * (var_h - var_i))
    var_3 = V * (1. - S * (1. - (var_h - var_i)))

    if var_i == 0:
      # V31
      var_r = V
      var_g = var_3
      var_b = var_1
    elif var_i == 1:
      # 2V1
      var_r = var_2
      var_g = V
      var_b = var_1
    elif var_i == 2:
      # 1V3
      var_r = var_1
      var_g = V
      var_b = var_3
    elif var_i == 3:
      # 12V
      var_r = var_1
      var_g = var_2
      var_b = V
    elif var_i == 4:
      # 31V
      var_r = var_3
      var_g = var_1
      var_b = V
    else:
      # var_i == 5
      # V12
      var_r = V
      var_g = var_1
      var_b = var_2
    ##
    out = ColorRGB(
        r=var_r,
        g=var_g,
        b=var_b
    )
    return out
  ##

  def asCmy(self) -> ColorCMY:
    # DOCME
    # C,M,Y have input range = [0., 1.]
    c = 1 - self.r
    m = 1 - self.g
    y = 1 - self.b
    out = ColorCMY(c, m, y)
    return out
  ##

  @classmethod
  def fromCmy(cls, cmy: ColorCMY) -> ColorRGB:
    # DOCME
    # C,M,Y have input range = [0., 1.]
    c, m, y = cmy
    out = ColorRGB(
        r=1. - c,
        g=1. - m,
        b=1. - y
    )
    return out
  ##

  def asCmyk(self) -> ColorCMYK:
    # DOCME
    # C,M,Y,K have input range = [0., 1.]
    c = 1. - self.r
    m = 1. - self.g
    y = 1. - self.b
    var_K = 1.
    if c < var_K:
      var_K = c
    ##
    if m < var_K:
      var_K = m
    ##
    if y < var_K:
      var_K = y
    ##
    if var_K == 1.:
      c = 0.
      m = 0.
      y = 0.
    else:
      c = (c - var_K) / (1. - var_K)
      m = (m - var_K) / (1. - var_K)
      y = (y - var_K) / (1. - var_K)
    ##
    k = var_K
    out = ColorCMYK(c, m, y, k)
    return out
  ##

  @classmethod
  def fromCmyk(cls, cmyk: ColorCMYK) -> ColorRGB:
    # DOCME
    # C,M,Y,K have input range = [0., 1.]
    var_cmy = cmyk[:3]
    k = cmyk[3]
    c, m, y = tuple(x * (1 - k) + k for x in var_cmy)
    return ColorRGB.fromCmy(cmy=ColorCMY(c, m, y))
  ##

  def asHexColorCode(self) -> str:
    # DOCME
    return f'#{int(self.r * 255.):02X}{int(self.g * 255.):02X}{int(self.b * 255.):02X}'
  ##

  @classmethod
  def fromHexColorCode(cls, hex_code: str) -> ColorRGB:
    # DOCME
    if hex_code[0] != '#':
      raise ValueError(f'Expected hex code to start with "#". Got value:{repr(hex_code)}')
    ##
    if len(hex_code) == 7:
      r = int(hex_code[1:3], base=16) / 255.
      g = int(hex_code[3:5], base=16) / 255.
      b = int(hex_code[5:7], base=16) / 255.
    elif len(hex_code) == 4:
      r = int(hex_code[1], base=16) / 15.
      g = int(hex_code[2], base=16) / 15.
      b = int(hex_code[3], base=16) / 15.
    else:
      raise ValueError(f'Expected hex color code to be of form #RGB or #RRGGBB. Got value:{repr(hex_code)}')
    ##
    out = ColorRGB(
        r=r,
        g=g,
        b=b
    )
    return out
  ##

  def asItpScaled(self) -> ColorITP_scaled:
    # DOCME
    itp_scaled = _PerceptualQuantizer.rgb2scaled_itp((self.r, self.g, self.b,))
    out = ColorITP_scaled(*itp_scaled)
    return out
  ##

  def invert(self) -> ColorRGB:
    # DOCME
    out = ColorRGB(
        r=1. - self.r,
        g=1. - self.g,
        b=1. - self.b
    )
    return out
  ##

  def calculateJustNoticeableDifference(self, other: ColorRGB) -> float:
    # DOCME
    if other == self:
      # Same colors have 0 JND
      return 0.
    ##
    # JND is scaled so that 1 indicates the potential of a "Just Noticeable Difference"
    itp1 = _PerceptualQuantizer.rgb2itp(rgb=(self.r, self.g, self.b,))
    itp2 = _PerceptualQuantizer.rgb2itp(rgb=(other.r, other.g, other.b,))
    # Heading 2, Step 5 - See PQ References
    delta_E_itp = float(720. * norm(itp1 - itp2))
    return delta_E_itp
  ##

  #####
  # Tuple/List-ish interface
  def __len__(self) -> int:
    # DOCME
    return 3
  ##

  def __getitem__(self, key: int) -> float:
    # DOCME
    if key == 0:
      return self.r
    elif key == 1:
      return self.g
    elif key == 2:
      return self.b
    else:
      raise IndexError('index out of range')
    ##
  ##

  def __iter__(self) -> Iterator[float]:
    # DOCME
    # noinspection PyRedundantParentheses
    yield from (self.r, self.g, self.b,)  # parentheses are not redundant in py<=3.7
  ##

  def __lt__(self, other: ColorRGB) -> bool:
    # DOCME
    return tuple(self) < tuple(other)
  ##

  def __le__(self, other: ColorRGB) -> bool:
    # DOCME
    return tuple(self) <= tuple(other)
  ##

  def __gt__(self, other: ColorRGB) -> bool:
    # DOCME
    return tuple(self) > tuple(other)
  ##

  def __ge__(self, other: ColorRGB) -> bool:
    # DOCME
    return tuple(self) >= tuple(other)
  ##
##
