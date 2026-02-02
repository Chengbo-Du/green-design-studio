# -*- coding: utf-8 -*-
"""
GDS Schedule Parser
===================

Parses GDS module database JSON for schedules, programs, and load intensities.

Usage:
    from gds.parsers import GDSScheduleParser
    
    parser = GDSScheduleParser("/path/to/gds_modules.json")
    schedules = parser.get_schedule_names()
    values = parser.get_schedule_values("Office Weekday")
"""

import json


class GDSScheduleParser(object):
    """Parse GDS module database for schedules and program types."""
    
    def __init__(self, json_path=None):
        """Initialize parser with optional JSON path.
        
        Args:
            json_path: Path to GDS modules JSON database
        """
        self.json_path = json_path
        self.schedules = {}
        self.setpoints = {}
        self.programs = {}
        self.intensities = {}
        
        if json_path:
            self._load_and_parse()
    
    def _load_and_parse(self):
        """Load and parse GDS JSON database."""
        try:
            with open(self.json_path, 'r') as f:
                data = json.load(f)
            
            modules = data.get('modules', {})
            
            for module_key, module_data in modules.items():
                if module_key.startswith('schedule.'):
                    self._parse_schedule_module(module_key, module_data)
                elif module_key.startswith('program.') or module_key.startswith('space_type.'):
                    self._parse_program_module(module_key, module_data)
                elif module_key.startswith('loads.'):
                    self._parse_loads_module(module_key, module_data)
                    
        except Exception as e:
            print("GDS Schedule Parser error: {}".format(e))
    
    def _parse_schedule_module(self, module_key, module_data):
        """Parse a schedule module from GDS JSON."""
        short_key = module_key.replace('schedule.', '')
        meta = module_data.get('meta', {})
        display_name = meta.get('display_name', short_key)
        
        design = module_data.get('design', {})
        
        # Get hourly values
        hourly = design.get('hourly_values', [])
        if not hourly:
            hourly = design.get('values', [])
        
        if hourly and len(hourly) == 24:
            schedule_type = design.get('schedule_type', 'fractional')
            
            if schedule_type in ['temperature', 'setpoint']:
                self.setpoints[display_name] = {
                    'identifier': short_key,
                    'values': hourly,
                    'type': schedule_type,
                    'weekend_values': design.get('weekend_values', hourly)
                }
            else:
                self.schedules[display_name] = {
                    'identifier': short_key,
                    'values': hourly,
                    'type': schedule_type,
                    'weekend_values': design.get('weekend_values', hourly)
                }
    
    def _parse_program_module(self, module_key, module_data):
        """Parse a program type module from GDS JSON."""
        short_key = module_key.replace('program.', '').replace('space_type.', '')
        meta = module_data.get('meta', {})
        display_name = meta.get('display_name', short_key)
        
        design = module_data.get('design', {})
        
        program_dict = {
            'identifier': short_key,
            'display_name': display_name,
        }
        
        # Parse people loads
        people = design.get('people', {})
        if people:
            program_dict['people'] = {
                'people_per_area': people.get('people_per_area', 0.0565),
                'occupancy_schedule': people.get('occupancy_schedule', 'Office Weekday'),
                'activity_schedule': people.get('activity_schedule', 'Office Seated'),
            }
        
        # Parse lighting loads
        lighting = design.get('lighting', {})
        if lighting:
            program_dict['lighting'] = {
                'watts_per_area': lighting.get('watts_per_area', 10.76),
                'schedule': lighting.get('schedule', 'Office Weekday'),
            }
        
        # Parse equipment loads
        equipment = design.get('electric_equipment', design.get('equipment', {}))
        if equipment:
            program_dict['electric_equipment'] = {
                'watts_per_area': equipment.get('watts_per_area', 10.76),
                'schedule': equipment.get('schedule', 'Office Weekday'),
            }
        
        # Parse infiltration
        infiltration = design.get('infiltration', {})
        if infiltration:
            program_dict['infiltration'] = {
                'flow_per_exterior_area': infiltration.get('flow_per_exterior_area', 0.0003),
                'schedule': infiltration.get('schedule', 'Always On'),
            }
        
        # Parse ventilation
        ventilation = design.get('ventilation', {})
        if ventilation:
            program_dict['ventilation'] = {
                'outdoor_air_per_person': ventilation.get('outdoor_air_per_person', 0.006),
                'outdoor_air_per_area': ventilation.get('outdoor_air_per_area', 0.0003),
            }
        
        # Parse setpoints
        setpoint = design.get('setpoint', {})
        if setpoint:
            program_dict['setpoint'] = {
                'heating_schedule': setpoint.get('heating_schedule', 'Office Heating'),
                'cooling_schedule': setpoint.get('cooling_schedule', 'Office Cooling'),
            }
        
        self.programs[display_name] = program_dict
    
    def _parse_loads_module(self, module_key, module_data):
        """Parse a loads intensity module from GDS JSON."""
        short_key = module_key.replace('loads.', '')
        meta = module_data.get('meta', {})
        display_name = meta.get('display_name', short_key)
        
        design = module_data.get('design', {})
        
        self.intensities[display_name] = {
            'people_per_area': design.get('people_per_area', 0.0565),
            'lighting_power': design.get('lighting_power', design.get('watts_per_area_lighting', 10.76)),
            'equipment_power': design.get('equipment_power', design.get('watts_per_area_equipment', 10.76)),
            'infiltration_rate': design.get('infiltration_rate', design.get('flow_per_exterior_area', 0.0003)),
            'ventilation_per_person': design.get('ventilation_per_person', design.get('outdoor_air_per_person', 0.006)),
            'ventilation_per_area': design.get('ventilation_per_area', design.get('outdoor_air_per_area', 0.0003)),
            # Service Hot Water
            'shw_flow_per_area': design.get('shw_flow_per_area', 0.0),
            'shw_target_temp': design.get('shw_target_temp', 49.0),
        }
    
    def get_schedule_values(self, display_name):
        """Get 24-hour values for a schedule by display name.
        
        Args:
            display_name: Schedule display name
            
        Returns:
            List of 24 hourly values, or None if not found
        """
        if display_name in self.schedules:
            return self.schedules[display_name]['values']
        return None
    
    def get_setpoint_values(self, display_name):
        """Get 24-hour values for a setpoint schedule by display name.
        
        Args:
            display_name: Setpoint schedule display name
            
        Returns:
            List of 24 hourly values, or None if not found
        """
        if display_name in self.setpoints:
            return self.setpoints[display_name]['values']
        return None
    
    def get_schedule_names(self):
        """Get list of all schedule display names."""
        return list(self.schedules.keys())
    
    def get_setpoint_names(self):
        """Get list of all setpoint schedule display names."""
        return list(self.setpoints.keys())
    
    def get_program_names(self):
        """Get list of all program display names."""
        return list(self.programs.keys())
    
    def get_intensity_names(self):
        """Get list of all load intensity display names."""
        return list(self.intensities.keys())
    
    def get_program(self, display_name):
        """Get program definition by display name.
        
        Args:
            display_name: Program display name
            
        Returns:
            Dict with program definition, or None if not found
        """
        return self.programs.get(display_name)
    
    def get_intensity(self, display_name):
        """Get load intensity definition by display name.
        
        Args:
            display_name: Intensity preset display name
            
        Returns:
            Dict with intensity values, or None if not found
        """
        return self.intensities.get(display_name)
