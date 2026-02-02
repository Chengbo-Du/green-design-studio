# -*- coding: utf-8 -*-
"""
GDS Core - Green Design Studio Core Library
============================================

Building performance simulation core library for EnergyPlus/CONTAM integration.

Usage:
    from gds.presets.hvac import HVAC_CATEGORIES
    from gds.presets.schedules import SCHEDULE_PRESETS
    from gds.parsers import GDSScheduleParser
    from gds.models import GDSProgramData

Modules:
    gds.presets     - HVAC, schedule, renewable, intensity presets
    gds.parsers     - GDS JSON database parsers
    gds.models      - Data models (RoomProgram, etc.)
    gds.utils       - Grasshopper helpers, geometry utilities
"""

__version__ = "0.1.0"
__author__ = "Chengbo Zhang"

def get_version():
    """Return the current GDS Core version."""
    return __version__
