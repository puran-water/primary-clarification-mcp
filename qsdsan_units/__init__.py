"""
Custom QSDsan SanUnits for advanced primary clarifier modeling.

This package provides custom SanUnit implementations that integrate:
- Population Balance Models (PBM) for particle aggregation
- Fractal settling velocity calculations  
- DLVO attachment efficiency modeling
- Takács/Vesilind hindered settling

Units:
- PrimaryClarifierPBM: Size-resolved primary clarifier with PBM and fractal settling
"""

from .primary_clarifier_pbm import PrimaryClarifierPBM

__all__ = ['PrimaryClarifierPBM']
