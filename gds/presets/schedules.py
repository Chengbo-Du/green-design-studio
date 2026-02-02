# -*- coding: utf-8 -*-
"""
Schedule Presets
================

24-hour schedule profiles for occupancy, lighting, equipment, and setpoints.

Usage:
    from gds.presets.schedules import SCHEDULE_PRESETS, SETPOINT_PRESETS
    from gds.presets.schedules import get_schedule_values
"""

# ==============================================================================
# FRACTIONAL SCHEDULES (0-1 scale)
# ==============================================================================

SCHEDULE_PRESETS = {
    "Always On": [1.0] * 24,
    "Always Off": [0.0] * 24,
    "Office Weekday": [0, 0, 0, 0, 0, 0, 0.1, 0.2, 0.95, 0.95, 0.95, 0.5, 
                       0.95, 0.95, 0.95, 0.95, 0.95, 0.3, 0.1, 0.05, 0, 0, 0, 0],
    "Office Weekend": [0, 0, 0, 0, 0, 0, 0.05, 0.05, 0.1, 0.1, 0.1, 0.1, 
                       0.1, 0.1, 0.05, 0.05, 0, 0, 0, 0, 0, 0, 0, 0],
    "Retail": [0, 0, 0, 0, 0, 0, 0, 0.1, 0.2, 0.5, 0.8, 0.9, 
               0.9, 0.9, 0.9, 0.9, 0.9, 0.8, 0.5, 0.2, 0, 0, 0, 0],
    "Hospital 24/7": [0.8, 0.7, 0.6, 0.6, 0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 1.0, 1.0, 
                      1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.9, 0.9, 0.9, 0.9, 0.8, 0.8],
    "School": [0, 0, 0, 0, 0, 0, 0.1, 0.5, 0.95, 0.95, 0.95, 0.95, 
               0.5, 0.95, 0.95, 0.5, 0.1, 0, 0, 0, 0, 0, 0, 0],
    "Residential": [0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.7, 0.4, 0.4, 0.2, 0.2, 0.2, 
                    0.2, 0.2, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 0.9, 0.9, 0.9, 0.9],
}

# ==============================================================================
# SETPOINT SCHEDULES (Temperature in °C)
# ==============================================================================

SETPOINT_PRESETS = {
    "Office Heating": [15.6, 15.6, 15.6, 15.6, 15.6, 15.6, 18, 21, 21, 21, 21, 21, 
                       21, 21, 21, 21, 21, 21, 15.6, 15.6, 15.6, 15.6, 15.6, 15.6],
    "Office Cooling": [29.4, 29.4, 29.4, 29.4, 29.4, 29.4, 26, 24, 24, 24, 24, 24, 
                       24, 24, 24, 24, 24, 24, 29.4, 29.4, 29.4, 29.4, 29.4, 29.4],
    "Residential Heating": [18, 18, 18, 18, 18, 18, 20, 21, 21, 18, 18, 18, 
                            18, 18, 18, 18, 21, 21, 21, 21, 21, 20, 18, 18],
    "Residential Cooling": [28, 28, 28, 28, 28, 28, 26, 25, 25, 28, 28, 28, 
                            28, 28, 28, 28, 25, 25, 25, 25, 25, 26, 28, 28],
    "Constant 21C": [21] * 24,
    "Constant 24C": [24] * 24,
}

# ==============================================================================
# ACTIVITY SCHEDULES (Metabolic rate in W/person)
# ==============================================================================

ACTIVITY_PRESETS = {
    "Office Seated": [120] * 24,
    "Office Light Work": [126] * 24,
    "Standing/Walking": [150] * 24,
    "Light Labor": [180] * 24,
    "Heavy Labor": [300] * 24,
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_schedule_values(schedule_name, is_setpoint=False):
    """Get 24-hour values for a schedule by name.
    
    Args:
        schedule_name: Name of the schedule preset
        is_setpoint: If True, look in SETPOINT_PRESETS first
    
    Returns:
        List of 24 hourly values, or None if not found
    """
    if schedule_name is None:
        return None
    
    if is_setpoint:
        if schedule_name in SETPOINT_PRESETS:
            return SETPOINT_PRESETS[schedule_name]
    
    if "Activity" in schedule_name or schedule_name in ACTIVITY_PRESETS:
        return ACTIVITY_PRESETS.get(schedule_name)
    
    return SCHEDULE_PRESETS.get(schedule_name)


def get_all_schedule_names():
    """Get list of all available schedule names."""
    return list(SCHEDULE_PRESETS.keys())


def get_all_setpoint_names():
    """Get list of all available setpoint schedule names."""
    return list(SETPOINT_PRESETS.keys())


def get_all_activity_names():
    """Get list of all available activity schedule names."""
    return list(ACTIVITY_PRESETS.keys())
