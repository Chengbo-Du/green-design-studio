# -*- coding: utf-8 -*-
"""
Load Intensity Presets
======================

Default load densities for different building/space types.
Includes people, lighting, equipment, infiltration, and ventilation.

Usage:
    from gds.presets.intensities import INTENSITY_DEFAULTS, SHW_PRESETS
    from gds.presets.intensities import get_intensity_defaults
"""

# ==============================================================================
# INTENSITY DEFAULTS BY BUILDING TYPE
# ==============================================================================

INTENSITY_DEFAULTS = {
    "Office": {
        "people_per_area": 0.0565,          # people/m²
        "lighting_power": 10.76,             # W/m²
        "equipment_power": 10.76,            # W/m²
        "infiltration_rate": 0.0003,         # m³/s/m² exterior
        "ventilation_per_person": 0.006,     # m³/s/person
        "ventilation_per_area": 0.0003,      # m³/s/m²
    },
    "Retail": {
        "people_per_area": 0.108,
        "lighting_power": 16.0,
        "equipment_power": 5.0,
        "infiltration_rate": 0.0003,
        "ventilation_per_person": 0.0075,
        "ventilation_per_area": 0.0006,
    },
    "Residential": {
        "people_per_area": 0.04,
        "lighting_power": 6.0,
        "equipment_power": 5.0,
        "infiltration_rate": 0.0003,
        "ventilation_per_person": 0.0025,
        "ventilation_per_area": 0.0003,
    },
    "Laboratory": {
        "people_per_area": 0.05,
        "lighting_power": 14.0,
        "equipment_power": 20.0,
        "infiltration_rate": 0.0003,
        "ventilation_per_person": 0.006,
        "ventilation_per_area": 0.0009,
    },
    "Hospital": {
        "people_per_area": 0.1,
        "lighting_power": 12.0,
        "equipment_power": 15.0,
        "infiltration_rate": 0.0003,
        "ventilation_per_person": 0.006,
        "ventilation_per_area": 0.0006,
    },
}

# ==============================================================================
# SERVICE HOT WATER PRESETS
# ==============================================================================

SHW_PRESETS = {
    "None": {
        "flow_per_area": 0.0,
        "target_temp": 49.0,
        "sensible_fraction": 0.0,
        "latent_fraction": 0.0,
    },
    "Residential": {
        "flow_per_area": 0.05,       # L/h/m² 
        "target_temp": 49.0,         # °C (120°F)
        "sensible_fraction": 0.2,
        "latent_fraction": 0.05,
    },
    "Residential - ABC Baseline": {
        "flow_per_area": 0.05,
        "target_temp": 48.9,         # 120°F from paper
        "sensible_fraction": 0.2,
        "latent_fraction": 0.05,
    },
    "Office": {
        "flow_per_area": 0.01,
        "target_temp": 43.0,
        "sensible_fraction": 0.2,
        "latent_fraction": 0.05,
    },
    "Hotel": {
        "flow_per_area": 0.08,
        "target_temp": 49.0,
        "sensible_fraction": 0.2,
        "latent_fraction": 0.05,
    },
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_intensity_defaults(building_type):
    """Get default load intensities for a building type.
    
    Args:
        building_type: One of 'Office', 'Retail', 'Residential', etc.
    
    Returns:
        Dict with load intensity values, or Office defaults if type not found
    """
    return INTENSITY_DEFAULTS.get(building_type, INTENSITY_DEFAULTS["Office"])


def get_shw_preset(preset_name):
    """Get service hot water preset by name.
    
    Args:
        preset_name: One of 'None', 'Residential', 'Office', etc.
    
    Returns:
        Dict with SHW parameters, or 'None' preset if not found
    """
    return SHW_PRESETS.get(preset_name, SHW_PRESETS["None"])


def get_intensity_type_names():
    """Get list of all building type names."""
    return list(INTENSITY_DEFAULTS.keys())


def get_shw_preset_names():
    """Get list of all SHW preset names."""
    return list(SHW_PRESETS.keys())
