# -*- coding: utf-8 -*-
"""
Renewable Energy Presets
========================

Presets for PV, Battery, Wind, and Solar Hot Water systems.

Usage:
    from gds.presets.renewables import PV_PRESETS, BATTERY_PRESETS
"""

# ==============================================================================
# PHOTOVOLTAIC PRESETS
# ==============================================================================

PV_PRESETS = {
    "Standard Silicon": {
        "description": "Typical poly/mono-crystalline (14-17% eff)",
        "efficiency": 0.15,
        "module_type": "Standard",
        "mounting": "FixedOpenRack",
        "loss_fraction": 0.14,
        "tracking_gcr": 0.4,
    },
    "Premium Silicon": {
        "description": "High-efficiency mono-crystalline (18-20% eff)",
        "efficiency": 0.19,
        "module_type": "Premium", 
        "mounting": "FixedOpenRack",
        "loss_fraction": 0.12,
        "tracking_gcr": 0.4,
    },
    "Thin Film": {
        "description": "Amorphous silicon or CdTe (<12% eff)",
        "efficiency": 0.10,
        "module_type": "ThinFilm",
        "mounting": "FixedOpenRack",
        "loss_fraction": 0.16,
        "tracking_gcr": 0.4,
    },
    "BIPV Facade": {
        "description": "Building-integrated on vertical facade",
        "efficiency": 0.12,
        "module_type": "Standard",
        "mounting": "FixedRoofMounted",
        "loss_fraction": 0.18,
        "tracking_gcr": 0.4,
    },
    "Roof Flush Mount": {
        "description": "Panels flush with roof surface",
        "efficiency": 0.16,
        "module_type": "Standard",
        "mounting": "FixedRoofMounted",
        "loss_fraction": 0.15,
        "tracking_gcr": 0.4,
    },
    "Single-Axis Tracker": {
        "description": "Ground-mount with E-W tracking",
        "efficiency": 0.17,
        "module_type": "Premium",
        "mounting": "OneAxis",
        "loss_fraction": 0.12,
        "tracking_gcr": 0.4,
    },
    "Dual-Axis Tracker": {
        "description": "Full sun tracking (highest yield)",
        "efficiency": 0.18,
        "module_type": "Premium",
        "mounting": "TwoAxis",
        "loss_fraction": 0.10,
        "tracking_gcr": 0.4,
    },
}

PV_MODULE_TYPES = ['Standard', 'Premium', 'ThinFilm']
PV_MOUNTING_TYPES = ['FixedOpenRack', 'FixedRoofMounted', 'OneAxis', 
                     'OneAxisBacktracking', 'TwoAxis']

# ==============================================================================
# BATTERY PRESETS
# ==============================================================================

BATTERY_PRESETS = {
    "Residential Small (5 kWh)": {
        "capacity_kwh": 5,
        "power_kw": 3.8,
        "efficiency": 0.89,
    },
    "Residential Medium (13.5 kWh)": {
        "capacity_kwh": 13.5,
        "power_kw": 5.0,
        "efficiency": 0.90,
    },
    "Residential Large (20 kWh)": {
        "capacity_kwh": 20,
        "power_kw": 10.0,
        "efficiency": 0.90,
    },
    "Commercial Small (50 kWh)": {
        "capacity_kwh": 50,
        "power_kw": 25,
        "efficiency": 0.88,
    },
    "Commercial Medium (200 kWh)": {
        "capacity_kwh": 200,
        "power_kw": 100,
        "efficiency": 0.88,
    },
}

# ==============================================================================
# WIND TURBINE PRESETS
# ==============================================================================

WIND_PRESETS = {
    "Micro Turbine (1 kW)": {
        "rated_power_kw": 1.0,
        "rotor_diameter_m": 2.5,
        "hub_height_m": 10,
    },
    "Small Turbine (5 kW)": {
        "rated_power_kw": 5.0,
        "rotor_diameter_m": 5.0,
        "hub_height_m": 18,
    },
    "Medium Turbine (10 kW)": {
        "rated_power_kw": 10.0,
        "rotor_diameter_m": 7.0,
        "hub_height_m": 25,
    },
    "VAWT Rooftop (2 kW)": {
        "rated_power_kw": 2.0,
        "rotor_diameter_m": 2.0,
        "hub_height_m": 5,
    },
}

# ==============================================================================
# SOLAR HOT WATER PRESETS
# ==============================================================================

SOLHW_PRESETS = {
    "Flat Plate - Standard": {
        "efficiency": 0.50,
        "collector_type": "FlatPlate",
    },
    "Flat Plate - Premium": {
        "efficiency": 0.65,
        "collector_type": "FlatPlate",
    },
    "Evacuated Tube": {
        "efficiency": 0.55,
        "collector_type": "TubularEvacuated",
    },
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_pv_preset_names():
    """Get list of all PV preset names."""
    return list(PV_PRESETS.keys())


def get_battery_preset_names():
    """Get list of all battery preset names."""
    return list(BATTERY_PRESETS.keys())


def get_wind_preset_names():
    """Get list of all wind turbine preset names."""
    return list(WIND_PRESETS.keys())


def get_solhw_preset_names():
    """Get list of all solar hot water preset names."""
    return list(SOLHW_PRESETS.keys())
