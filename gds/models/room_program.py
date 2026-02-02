# -*- coding: utf-8 -*-
"""
Room Program Model
==================

Data class for holding space program information (loads, schedules, setpoints).
Generates HB-compatible ProgramType JSON for use with HB Load Objects component.

Usage:
    from gds.models import GDSProgramData
    
    program = GDSProgramData("Office_Zone_1")
    program.people_per_area = 0.05
    program.lighting_power = 10.0
    json_output = program.to_json_string()
"""

import json

from gds.presets.schedules import SCHEDULE_PRESETS, SETPOINT_PRESETS, ACTIVITY_PRESETS


def _get_hb_schedule_by_id(schedule_id):
    """Get a ScheduleRuleset object from HB library by identifier.
    
    Args:
        schedule_id: HB schedule identifier
        
    Returns:
        HB ScheduleRuleset or None
    """
    try:
        from honeybee_energy.lib.schedules import schedule_by_identifier
        return schedule_by_identifier(schedule_id)
    except:
        return None


class GDSProgramData(object):
    """Holds all program type data for a space.
    
    Outputs FULL JSON format for HB Load Objects / String to Object component.
    """
    
    def __init__(self, identifier="GDS_Custom_Program"):
        """Initialize program data with defaults.
        
        Args:
            identifier: Unique identifier for this program
        """
        self.identifier = identifier
        
        # Load intensities
        self.people_per_area = 0.0565          # people/m²
        self.lighting_power = 10.76            # W/m²
        self.equipment_power = 10.76           # W/m²
        self.gas_equipment_power = 0.0         # W/m²
        self.infiltration_rate = 0.0003        # m³/s/m² exterior
        self.ventilation_per_person = 0.006    # m³/s/person
        self.ventilation_per_area = 0.0003     # m³/s/m²
        
        # Service Hot Water
        self.shw_flow_per_area = 0.0           # L/h/m² (0 = disabled)
        self.shw_target_temp = 49.0            # °C
        self.shw_sensible_fraction = 0.2
        self.shw_latent_fraction = 0.05
        self.shw_schedule = "Residential"
        
        # Schedule names
        self.occupancy_schedule = "Office Weekday"
        self.occupancy_weekend = "Office Weekend"
        self.activity_schedule = "Office Seated"
        self.lighting_schedule = "Office Weekday"
        self.equipment_schedule = "Office Weekday"
        self.infiltration_schedule = "Always On"
        self.heating_setpoint = "Office Heating"
        self.cooling_setpoint = "Office Cooling"
        
        # Custom schedules storage
        self.custom_schedules = {}
    
    def get_schedule_values(self, schedule_name, is_setpoint=False, gds_parser=None):
        """Get 24-hour values for a schedule by name.
        
        Handles custom schedules, GDS database schedules, HB library schedules,
        and built-in presets.
        
        Args:
            schedule_name: Name of the schedule
            is_setpoint: True if this is a temperature setpoint schedule
            gds_parser: Optional GDSScheduleParser for database lookups
        
        Returns:
            List of 24 hourly values
        """
        # Custom schedule (stored locally)
        if schedule_name.startswith("Custom:"):
            key = schedule_name[7:]
            if key in self.custom_schedules:
                return self.custom_schedules[key]
            return [0] * 24
        
        # GDS database schedule
        if schedule_name.startswith("[GDS] "):
            name = schedule_name[6:]
            if gds_parser:
                if is_setpoint:
                    return gds_parser.get_setpoint_values(name)
                else:
                    return gds_parser.get_schedule_values(name)
            return None
        
        # HB library schedule
        if schedule_name.startswith("[HB] "):
            hb_id = schedule_name[5:]
            schedule = _get_hb_schedule_by_id(hb_id)
            if schedule:
                try:
                    return schedule.values()[0:24] if hasattr(schedule, 'values') else None
                except:
                    return None
            return None
        
        # Built-in presets
        if is_setpoint:
            return SETPOINT_PRESETS.get(schedule_name, [21] * 24)
        elif "Activity" in schedule_name or schedule_name in ACTIVITY_PRESETS:
            return ACTIVITY_PRESETS.get(schedule_name, [120] * 24)
        else:
            return SCHEDULE_PRESETS.get(schedule_name, [0] * 24)
    
    def _make_schedule_full(self, name, weekday_vals, weekend_vals=None, type_limit="Fractional"):
        """Create ScheduleRuleset dict for JSON serialization.
        
        Args:
            name: Schedule identifier
            weekday_vals: List of 24 hourly values for weekdays
            weekend_vals: List of 24 hourly values for weekends (defaults to weekday)
            type_limit: "Fractional", "Temperature", or "ActivityLevel"
        
        Returns:
            Dict representing HB ScheduleRuleset
        """
        if weekend_vals is None:
            weekend_vals = weekday_vals
        
        # Ensure values are flat lists of floats
        weekday_vals = [float(v) for v in weekday_vals]
        weekend_vals = [float(v) for v in weekend_vals]
        
        # Times list for 24-hour schedule
        times_24 = [[i, 0] for i in range(24)]
        
        # Type limit definitions
        type_limits = {
            "Fractional": {
                "type": "ScheduleTypeLimit", 
                "identifier": "Fractional", 
                "lower_limit": 0, 
                "upper_limit": 1, 
                "numeric_type": "Continuous", 
                "unit_type": "Dimensionless"
            },
            "Temperature": {
                "type": "ScheduleTypeLimit", 
                "identifier": "Temperature",
                "lower_limit": -273.15, 
                "upper_limit": 200, 
                "numeric_type": "Continuous", 
                "unit_type": "Temperature"
            },
            "ActivityLevel": {
                "type": "ScheduleTypeLimit", 
                "identifier": "Activity Level",
                "lower_limit": 0, 
                "upper_limit": 1000, 
                "numeric_type": "Continuous", 
                "unit_type": "ActivityLevel"
            },
        }
        
        default_day_id = "{}_Default".format(name)
        weekday_day_id = "{}_Weekday".format(name)
        
        return {
            "type": "ScheduleRuleset",
            "identifier": name,
            "schedule_type_limit": type_limits.get(type_limit, type_limits["Fractional"]),
            "day_schedules": [
                {
                    "type": "ScheduleDay",
                    "identifier": default_day_id,
                    "values": weekend_vals,
                    "times": times_24
                },
                {
                    "type": "ScheduleDay",
                    "identifier": weekday_day_id,
                    "values": weekday_vals,
                    "times": times_24
                }
            ],
            "default_day_schedule": default_day_id,
            "schedule_rules": [
                {
                    "type": "ScheduleRuleAbridged",
                    "schedule_day": weekday_day_id,
                    "apply_sunday": False,
                    "apply_monday": True,
                    "apply_tuesday": True,
                    "apply_wednesday": True,
                    "apply_thursday": True,
                    "apply_friday": True,
                    "apply_saturday": False,
                    "start_date": [1, 1],
                    "end_date": [12, 31]
                }
            ]
        }
    
    def to_program_dict(self, gds_parser=None):
        """Generate FULL ProgramType JSON dict.
        
        Works directly with HB Load Objects component.
        
        Args:
            gds_parser: Optional GDSScheduleParser for database schedule lookups
        
        Returns:
            Dict representing complete HB ProgramType
        """
        base_id = self.identifier.replace(" ", "_")
        
        # Build occupancy schedule
        occ_wd = self.get_schedule_values(self.occupancy_schedule, gds_parser=gds_parser)
        if occ_wd is None:
            occ_wd = SCHEDULE_PRESETS.get("Office Weekday", [0] * 24)
        occ_we = self.get_schedule_values(self.occupancy_weekend, gds_parser=gds_parser)
        if occ_we is None:
            occ_we = SCHEDULE_PRESETS.get("Office Weekend", occ_wd)
        occ_sched = self._make_schedule_full("{}_Occupancy".format(base_id), occ_wd, occ_we, "Fractional")
        
        # Build activity schedule
        act_vals = self.get_schedule_values(self.activity_schedule, gds_parser=gds_parser)
        if act_vals is None:
            act_vals = ACTIVITY_PRESETS.get("Office Seated", [120] * 24)
        act_sched = self._make_schedule_full("{}_Activity".format(base_id), act_vals, act_vals, "ActivityLevel")
        
        # Build lighting schedule
        light_vals = self.get_schedule_values(self.lighting_schedule, gds_parser=gds_parser)
        if light_vals is None:
            light_vals = SCHEDULE_PRESETS.get("Office Weekday", [0] * 24)
        light_sched = self._make_schedule_full("{}_Lighting".format(base_id), light_vals, 
                                                [v * 0.1 for v in light_vals], "Fractional")
        
        # Build equipment schedule
        equip_vals = self.get_schedule_values(self.equipment_schedule, gds_parser=gds_parser)
        if equip_vals is None:
            equip_vals = SCHEDULE_PRESETS.get("Office Weekday", [0] * 24)
        equip_sched = self._make_schedule_full("{}_Equipment".format(base_id), equip_vals, 
                                                [v * 0.3 for v in equip_vals], "Fractional")
        
        # Build infiltration schedule
        infil_vals = self.get_schedule_values(self.infiltration_schedule, gds_parser=gds_parser)
        if infil_vals is None:
            infil_vals = [1.0] * 24
        infil_sched = self._make_schedule_full("{}_Infiltration".format(base_id), infil_vals, infil_vals, "Fractional")
        
        # Build ventilation schedule
        vent_sched = self._make_schedule_full("{}_Ventilation".format(base_id), occ_wd, [0] * 24, "Fractional")
        
        # Build setpoint schedules
        heat_vals = self.get_schedule_values(self.heating_setpoint, is_setpoint=True, gds_parser=gds_parser)
        if heat_vals is None:
            heat_vals = SETPOINT_PRESETS.get("Office Heating", [21] * 24)
        heat_sched = self._make_schedule_full("{}_Heating".format(base_id), heat_vals, 
                                               [v - 2 for v in heat_vals], "Temperature")
        
        cool_vals = self.get_schedule_values(self.cooling_setpoint, is_setpoint=True, gds_parser=gds_parser)
        if cool_vals is None:
            cool_vals = SETPOINT_PRESETS.get("Office Cooling", [24] * 24)
        cool_sched = self._make_schedule_full("{}_Cooling".format(base_id), cool_vals, 
                                               [v + 2 for v in cool_vals], "Temperature")
        
        # Build the ProgramType dict
        program = {
            "type": "ProgramType",
            "identifier": base_id,
            "display_name": self.identifier,
            
            "people": {
                "type": "People",
                "identifier": "{}_People".format(base_id),
                "people_per_area": self.people_per_area,
                "occupancy_schedule": occ_sched,
                "activity_schedule": act_sched,
                "radiant_fraction": 0.3,
                "latent_fraction": {"type": "Autocalculate"}
            },
            
            "lighting": {
                "type": "Lighting",
                "identifier": "{}_Lighting".format(base_id),
                "watts_per_area": self.lighting_power,
                "schedule": light_sched,
                "visible_fraction": 0.25,
                "radiant_fraction": 0.32,
                "return_air_fraction": 0.0
            },
            
            "electric_equipment": {
                "type": "ElectricEquipment",
                "identifier": "{}_ElecEquip".format(base_id),
                "watts_per_area": self.equipment_power,
                "schedule": equip_sched,
                "radiant_fraction": 0.5,
                "latent_fraction": 0.0,
                "lost_fraction": 0.0
            },
            
            "infiltration": {
                "type": "Infiltration",
                "identifier": "{}_Infiltration".format(base_id),
                "flow_per_exterior_area": self.infiltration_rate,
                "schedule": infil_sched,
                "constant_coefficient": 1.0,
                "temperature_coefficient": 0.0,
                "velocity_coefficient": 0.0
            },
            
            "ventilation": {
                "type": "Ventilation",
                "identifier": "{}_Ventilation".format(base_id),
                "outdoor_air_per_person": self.ventilation_per_person,
                "outdoor_air_per_area": self.ventilation_per_area,
                "air_changes_per_hour": 0.0,
                "schedule": vent_sched
            },
            
            "setpoint": {
                "type": "Setpoint",
                "identifier": "{}_Setpoint".format(base_id),
                "heating_schedule": heat_sched,
                "cooling_schedule": cool_sched
            }
        }
        
        # Add gas equipment if specified
        if self.gas_equipment_power > 0:
            program["gas_equipment"] = {
                "type": "GasEquipment",
                "identifier": "{}_GasEquip".format(base_id),
                "watts_per_area": self.gas_equipment_power,
                "schedule": equip_sched,
                "radiant_fraction": 0.3,
                "latent_fraction": 0.0,
                "lost_fraction": 0.0
            }
        
        # Add Service Hot Water if flow > 0
        if self.shw_flow_per_area > 0:
            shw_vals = self.get_schedule_values(self.shw_schedule, gds_parser=gds_parser)
            if shw_vals is None:
                shw_vals = SCHEDULE_PRESETS.get("Residential", [0.5] * 24)
            shw_sched = self._make_schedule_full("{}_SHW".format(base_id), shw_vals, shw_vals, "Fractional")
            
            program["service_hot_water"] = {
                "type": "ServiceHotWater",
                "identifier": "{}_SHW".format(base_id),
                "flow_per_area": self.shw_flow_per_area,
                "schedule": shw_sched,
                "target_temperature": self.shw_target_temp,
                "sensible_fraction": self.shw_sensible_fraction,
                "latent_fraction": self.shw_latent_fraction
            }
        
        return program
    
    def to_json_string(self, gds_parser=None):
        """Generate JSON string for HB String to Object component.
        
        Args:
            gds_parser: Optional GDSScheduleParser for database lookups
        
        Returns:
            JSON string
        """
        return json.dumps(self.to_program_dict(gds_parser), indent=2)
