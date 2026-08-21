# -*- coding: utf-8 -*-
""" This module contains some regular expression (regex) utilities"""
from __future__ import annotations

import re

__all__ = (
    'hasCapturingGroup',
    'replaceCaptureWithNonCapture',
    #######
    'UNSIGNED_INTEGER_LD0_PATTERN',
    'UNSIGNED_INTEGER_NO_LD0_PATTERN',
    'SIGNED_INTEGER_LD0_PATTERN',
    'SIGNED_INTEGER_NO_LD0_PATTERN',
    #######
    'FLOAT_POSITIONAL_LD0_PATTERN',
    'FLOAT_POSITIONAL_NO_LD0_PATTERN',
    'FLOAT_LD0_PATTERN',
    'FLOAT_NO_LD0_PATTERN',
    #######
    'UNSIGNED_INTEGER_STANDARD_PATTERN',
    'SIGNED_INTEGER_STANDARD_PATTERN',
    'FLOAT_STANDARD_PATTERN',
    #######
    'whitespace_rgx',
)
#############################
_NON_CAPTURING_PATTERN = r'(?<!\\)\((?!\?:)'
_NON_CAPTURING_RE = re.compile(_NON_CAPTURING_PATTERN)

UNSIGNED_INTEGER_LD0_PATTERN = r'(?:\d+)'  # Allows for leading 0's
UNSIGNED_INTEGER_NO_LD0_PATTERN = r'(?:0|[1-9]\d*)'  # Does not allow for leading 0's
SIGNED_INTEGER_LD0_PATTERN = rf'(?:[-+]?{UNSIGNED_INTEGER_LD0_PATTERN})'
SIGNED_INTEGER_NO_LD0_PATTERN = rf'(?:[-+]?{UNSIGNED_INTEGER_NO_LD0_PATTERN})'

FLOAT_POSITIONAL_LD0_PATTERN = r'(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+))'  # Floating point standard notation, allows leading 0's
FLOAT_POSITIONAL_NO_LD0_PATTERN = r'(?:[-+]?(?:(?:0|[1-9]\d*)(?:\.\d*)?|\.\d+))'  # Floating point standard notation, does not allow for extra leading 0's, e.g. 003.3

# Leading zeros are okay in scientific notation trailers
SCIENTIFIC_NOTATION_PATTERN = rf'(?:[eE]{SIGNED_INTEGER_LD0_PATTERN})'
FLOAT_LD0_PATTERN = rf'(?:nan|[-+]inf|(?:{FLOAT_POSITIONAL_LD0_PATTERN}{SCIENTIFIC_NOTATION_PATTERN}?))'
FLOAT_NO_LD0_PATTERN = rf'(?:nan|[-+]inf|(?:{FLOAT_POSITIONAL_NO_LD0_PATTERN}{SCIENTIFIC_NOTATION_PATTERN}?))'

# Aliases for standard/expected patterns for numbers
UNSIGNED_INTEGER_STANDARD_PATTERN = UNSIGNED_INTEGER_NO_LD0_PATTERN
SIGNED_INTEGER_STANDARD_PATTERN = SIGNED_INTEGER_NO_LD0_PATTERN
FLOAT_STANDARD_PATTERN = FLOAT_LD0_PATTERN

whitespace_rgx = re.compile(r'\s+')
nonword_rgx = re.compile(r'\W+')


def hasCapturingGroup(pattern: str) -> bool:
  r""" Determines if a regex pattern contains a capturing group - a regular beginning parenthesis `(`
  Does not verify if the groups are matched. Rather just that the parenthesis is neither escaped \( nor
  already non-capturing (?:
  """
  return bool(_NON_CAPTURING_RE.search(pattern))
##


def replaceCaptureWithNonCapture(pattern: str) -> str:
  """ Replaces the beginning of a capturing group ( with the non-capturing version (?: """
  return '(?:'.join(_NON_CAPTURING_RE.split(pattern))
##
