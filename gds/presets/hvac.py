# -*- coding: utf-8 -*-
"""
HVAC System Presets and Categories
==================================

Shared between GDS Hub and GDS Refiner.
Defines all HVAC system types, equipment options, and building presets.

Usage:
    from gds.presets.hvac import HVAC_CATEGORIES, HVAC_BUILDING_PRESETS
    from gds.presets.hvac import get_equipment_types_for_category
"""

# ==============================================================================
# HVAC SYSTEM CATEGORIES
# ==============================================================================

HVAC_CATEGORIES = {
    "Ideal Air (Loads Only)": {
        "description": "Perfect heating/cooling for load calculations",
        "class": "IdealAirSystem",
        "equipment_types": ["IdealAirSystem"],
        "has_economizer": True,
        "has_heat_recovery": True,
        "has_dcv": True,
    },
    "All-Air: VAV": {
        "description": "Variable Air Volume - large commercial buildings",
        "class": "VAV",
        "equipment_types": [
            "VAV_Chiller_Boiler", "VAV_Chiller_ASHP", "VAV_Chiller_DHW",
            "VAV_Chiller_PFP", "VAV_Chiller_GasCoil",
            "VAV_ACChiller_Boiler", "VAV_ACChiller_ASHP", "VAV_ACChiller_DHW",
            "VAV_ACChiller_PFP", "VAV_ACChiller_GasCoil",
            "VAV_DCW_Boiler", "VAV_DCW_ASHP", "VAV_DCW_DHW",
            "VAV_DCW_PFP", "VAV_DCW_GasCoil"
        ],
        "has_economizer": True,
        "has_heat_recovery": True,
        "has_dcv": True,
    },
    "All-Air: PVAV": {
        "description": "Packaged VAV - medium commercial",
        "class": "PVAV",
        "equipment_types": [
            "PVAV_Boiler", "PVAV_ASHP", "PVAV_DHW",
            "PVAV_PFP", "PVAV_BoilerElectricReheat"
        ],
        "has_economizer": True,
        "has_heat_recovery": True,
        "has_dcv": True,
    },
    "All-Air: PSZ": {
        "description": "Packaged Single Zone - small commercial/retail",
        "class": "PSZ",
        "equipment_types": [
            "PSZAC_ElectricBaseboard", "PSZAC_BoilerBaseboard", "PSZAC_GasHeaters",
            "PSZAC_ElectricCoil", "PSZAC_GasCoil", "PSZAC_Boiler", "PSZAC_ASHP",
            "PSZAC_DHW", "PSZAC", "PSZHP"
        ],
        "has_economizer": True,
        "has_heat_recovery": True,
        "has_dcv": True,
    },
    "DOAS + FCU": {
        "description": "Dedicated OA + Fan Coil Units - offices, hotels",
        "class": "FCUwithDOAS",
        "equipment_types": [
            "DOAS_FCU_Chiller_Boiler", "DOAS_FCU_Chiller_ASHP", "DOAS_FCU_Chiller_DHW",
            "DOAS_FCU_Chiller_ElectricBaseboard", "DOAS_FCU_Chiller",
            "DOAS_FCU_ACChiller_Boiler", "DOAS_FCU_ACChiller_ASHP", "DOAS_FCU_ACChiller_DHW",
            "DOAS_FCU_ACChiller_ElectricBaseboard", "DOAS_FCU_ACChiller",
            "DOAS_FCU_DCW_Boiler", "DOAS_FCU_DCW_ASHP", "DOAS_FCU_DCW_DHW",
            "DOAS_FCU_DCW_ElectricBaseboard", "DOAS_FCU_DCW"
        ],
        "has_economizer": False,
        "has_heat_recovery": True,
        "has_dcv": True,
    },
    "DOAS + VRF": {
        "description": "Dedicated OA + Variable Refrigerant Flow",
        "class": "VRFwithDOAS",
        "equipment_types": ["DOAS_VRF"],
        "has_economizer": False,
        "has_heat_recovery": True,
        "has_dcv": True,
    },
    "DOAS + Radiant": {
        "description": "Dedicated OA + Radiant Floors/Ceilings - high efficiency",
        "class": "RadiantwithDOAS",
        "equipment_types": [
            "DOAS_Radiant_Chiller_Boiler", "DOAS_Radiant_Chiller_ASHP", "DOAS_Radiant_Chiller_DHW",
            "DOAS_Radiant_ACChiller_Boiler", "DOAS_Radiant_ACChiller_ASHP", "DOAS_Radiant_ACChiller_DHW",
            "DOAS_Radiant_DCW_Boiler", "DOAS_Radiant_DCW_ASHP", "DOAS_Radiant_DCW_DHW"
        ],
        "has_economizer": False,
        "has_heat_recovery": True,
        "has_dcv": True,
        "has_radiant_type": True,
    },
    "DOAS + WSHP": {
        "description": "Dedicated OA + Water Source Heat Pumps",
        "class": "WSHPwithDOAS",
        "equipment_types": [
            "DOAS_WSHP_FluidCooler_Boiler", "DOAS_WSHP_CoolingTower_Boiler",
            "DOAS_WSHP_GSHP", "DOAS_WSHP_DCW_DHW"
        ],
        "has_economizer": False,
        "has_heat_recovery": True,
        "has_dcv": True,
    },
    "HeatCool: Residential": {
        "description": "Residential AC/HP/Furnace - no ventilation air",
        "class": "Residential",
        "equipment_types": [
            "ResidentialAC_ElectricBaseboard", "ResidentialAC_BoilerBaseboard",
            "ResidentialAC_ASHPBaseboard", "ResidentialAC_DHWBaseboard",
            "ResidentialAC_ResidentialFurnace", "ResidentialAC",
            "ResidentialHP", "ResidentialHPNoCool", "ResidentialFurnace"
        ],
        "has_economizer": False,
        "has_heat_recovery": False,
        "has_dcv": False,
    },
    "HeatCool: Baseboard": {
        "description": "Baseboard heating only - no cooling/ventilation",
        "class": "Baseboard",
        "equipment_types": [
            "ElectricBaseboard", "BoilerBaseboard", "ASHPBaseboard", "DHWBaseboard"
        ],
        "has_economizer": False,
        "has_heat_recovery": False,
        "has_dcv": False,
    },
    "HeatCool: Radiant": {
        "description": "Radiant floors/ceilings - no ventilation",
        "class": "Radiant",
        "equipment_types": [
            "Radiant_Chiller_Boiler", "Radiant_Chiller_ASHP", "Radiant_Chiller_DHW",
            "Radiant_ACChiller_Boiler", "Radiant_ACChiller_ASHP", "Radiant_ACChiller_DHW",
            "Radiant_DCW_Boiler", "Radiant_DCW_ASHP", "Radiant_DCW_DHW"
        ],
        "has_economizer": False,
        "has_heat_recovery": False,
        "has_dcv": False,
        "has_radiant_type": True,
    },
}

# ==============================================================================
# HVAC OPTIONS
# ==============================================================================

HVAC_VINTAGES = [
    "ASHRAE_2019", "ASHRAE_2016", "ASHRAE_2013", "ASHRAE_2010",
    "ASHRAE_2007", "ASHRAE_2004", "DOE_Ref_1980_2004", "DOE_Ref_Pre_1980"
]

HVAC_ECONOMIZER_TYPES = [
    "NoEconomizer", "DifferentialDryBulb", "DifferentialEnthalpy",
    "DifferentialDryBulbAndEnthalpy", "FixedDryBulb", "FixedEnthalpy"
]

HVAC_RADIANT_TYPES = ["Floor", "Ceiling", "FloorWithCarpet", "CeilingMetalPanel"]

# ==============================================================================
# HVAC QUICK PRESETS (for dropdown selection)
# ==============================================================================

HVAC_QUICK_PRESETS = {
    "Office Standard": {
        "category": "All-Air: VAV",
        "equipment_type": "VAV_Chiller_Boiler",
        "vintage": "ASHRAE_2019",
        "economizer": "DifferentialDryBulb",
        "sensible_hr": 0.0,
        "latent_hr": 0.0,
        "dcv": False,
    },
    "Office High-Eff": {
        "category": "DOAS + FCU",
        "equipment_type": "DOAS_FCU_Chiller_Boiler",
        "vintage": "ASHRAE_2019",
        "economizer": "NoEconomizer",
        "sensible_hr": 0.7,
        "latent_hr": 0.65,
        "dcv": True,
    },
    "Retail": {
        "category": "All-Air: PSZ",
        "equipment_type": "PSZAC_GasCoil",
        "vintage": "ASHRAE_2019",
        "economizer": "DifferentialDryBulb",
        "sensible_hr": 0.0,
        "latent_hr": 0.0,
        "dcv": False,
    },
    "Residential": {
        "category": "HeatCool: Residential",
        "equipment_type": "ResidentialHP",
        "vintage": "ASHRAE_2019",
        "economizer": "NoEconomizer",
        "sensible_hr": 0.0,
        "latent_hr": 0.0,
        "dcv": False,
    },
    "Lab High-Vent": {
        "category": "All-Air: VAV",
        "equipment_type": "VAV_Chiller_Boiler",
        "vintage": "ASHRAE_2019",
        "economizer": "DifferentialEnthalpy",
        "sensible_hr": 0.6,
        "latent_hr": 0.0,
        "dcv": True,
    },
    "Data Center": {
        "category": "All-Air: VAV",
        "equipment_type": "VAV_Chiller_Boiler",
        "vintage": "ASHRAE_2019",
        "economizer": "NoEconomizer",
        "sensible_hr": 0.7,
        "latent_hr": 0.65,
        "dcv": False,
    },
    "Hospital": {
        "category": "All-Air: VAV",
        "equipment_type": "VAV_Chiller_Boiler",
        "vintage": "ASHRAE_2019",
        "economizer": "NoEconomizer",
        "sensible_hr": 0.0,
        "latent_hr": 0.0,
        "dcv": False,
    },
    "Radiant High-Eff": {
        "category": "DOAS + Radiant",
        "equipment_type": "DOAS_Radiant_Chiller_Boiler",
        "vintage": "ASHRAE_2019",
        "economizer": "NoEconomizer",
        "sensible_hr": 0.75,
        "latent_hr": 0.7,
        "dcv": True,
        "radiant_type": "Floor",
    },
}

# ==============================================================================
# HVAC BUILDING PRESETS (Full configuration for building types)
# ==============================================================================

HVAC_BUILDING_PRESETS = {
    "Office - Standard": {
        "description": "VAV system with chiller/boiler",
        "class": "VAV",
        "equipment_type": "VAV_Chiller_Boiler",
        "vintage": "ASHRAE_2019",
        "economizer_type": "DifferentialDryBulb",
        "sensible_heat_recovery": 0.0,
        "latent_heat_recovery": 0.0,
        "demand_controlled_ventilation": True,
    },
    "Office - High Efficiency": {
        "description": "DOAS + FCU with heat recovery",
        "class": "FCUwithDOAS",
        "equipment_type": "DOAS_FCU_Chiller_Boiler",
        "vintage": "ASHRAE_2019",
        "economizer_type": "NoEconomizer",
        "sensible_heat_recovery": 0.7,
        "latent_heat_recovery": 0.65,
        "demand_controlled_ventilation": True,
    },
    "Residential": {
        "description": "Residential heat pump",
        "class": "Residential",
        "equipment_type": "ResidentialHP",
        "vintage": "ASHRAE_2019",
        "economizer_type": "NoEconomizer",
        "sensible_heat_recovery": 0.0,
        "latent_heat_recovery": 0.0,
        "demand_controlled_ventilation": False,
    },
    "Retail": {
        "description": "Packaged rooftop units",
        "class": "PSZ",
        "equipment_type": "PSZAC_GasCoil",
        "vintage": "ASHRAE_2019",
        "economizer_type": "DifferentialDryBulb",
        "sensible_heat_recovery": 0.0,
        "latent_heat_recovery": 0.0,
        "demand_controlled_ventilation": False,
    },
    "Hotel": {
        "description": "DOAS + FCU for guest rooms",
        "class": "FCUwithDOAS",
        "equipment_type": "DOAS_FCU_Chiller_Boiler",
        "vintage": "ASHRAE_2019",
        "economizer_type": "NoEconomizer",
        "sensible_heat_recovery": 0.6,
        "latent_heat_recovery": 0.5,
        "demand_controlled_ventilation": True,
    },
    "School": {
        "description": "DOAS + VRF for classrooms",
        "class": "VRFwithDOAS",
        "equipment_type": "DOAS_VRF",
        "vintage": "ASHRAE_2019",
        "economizer_type": "NoEconomizer",
        "sensible_heat_recovery": 0.6,
        "latent_heat_recovery": 0.5,
        "demand_controlled_ventilation": True,
    },
    "Hospital": {
        "description": "VAV with high ventilation",
        "class": "VAV",
        "equipment_type": "VAV_Chiller_Boiler",
        "vintage": "ASHRAE_2019",
        "economizer_type": "NoEconomizer",
        "sensible_heat_recovery": 0.7,
        "latent_heat_recovery": 0.65,
        "demand_controlled_ventilation": False,
    },
    "Ideal Air (Loads Only)": {
        "description": "Perfect HVAC for load calculations",
        "class": "IdealAirSystem",
        "equipment_type": "IdealAirSystem",
        "vintage": "ASHRAE_2019",
        "economizer_type": "NoEconomizer",
        "sensible_heat_recovery": 0.0,
        "latent_heat_recovery": 0.0,
        "demand_controlled_ventilation": False,
    },
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_equipment_types_for_category(category_name):
    """Get list of equipment types for a given HVAC category.
    
    Args:
        category_name: Name of the HVAC category (e.g., "All-Air: VAV")
    
    Returns:
        List of equipment type strings
    """
    category = HVAC_CATEGORIES.get(category_name, {})
    return category.get("equipment_types", [])


def get_hvac_class_for_category(category_name):
    """Get the HB HVAC class name for a category.
    
    Args:
        category_name: Name of the HVAC category
    
    Returns:
        String of HB class name (e.g., "VAV", "FCUwithDOAS")
    """
    category = HVAC_CATEGORIES.get(category_name, {})
    return category.get("class", "IdealAirSystem")


def category_has_feature(category_name, feature):
    """Check if a category supports a feature.
    
    Args:
        category_name: Name of the HVAC category
        feature: One of 'economizer', 'heat_recovery', 'dcv', 'radiant_type'
    
    Returns:
        True if category supports the feature
    """
    category = HVAC_CATEGORIES.get(category_name, {})
    return category.get("has_{}".format(feature), False)


def get_category_names():
    """Get list of all HVAC category names."""
    return list(HVAC_CATEGORIES.keys())


def get_building_preset_names():
    """Get list of all building preset names."""
    return list(HVAC_BUILDING_PRESETS.keys())


def get_quick_preset_names():
    """Get list of all quick preset names."""
    return list(HVAC_QUICK_PRESETS.keys())
