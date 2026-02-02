# -*- coding: utf-8 -*-
"""
GDS Library Parser
==================

Parses GDS module database JSON for constructions, materials, and modifiers.
Used by GDS Refiner for enclosure property modifications.

Usage:
    from gds.parsers import GDSLibraryParser
    
    parser = GDSLibraryParser("/path/to/gds_modules.json")
    constructions = parser.get_constructions_for_boundary("Outdoors", is_window=False)
"""

import json


class GDSLibraryParser(object):
    """Parse GDS module database for constructions and modifiers."""
    
    def __init__(self, json_path):
        """Initialize parser with JSON path.
        
        Args:
            json_path: Path to GDS modules JSON database
        """
        self.json_path = json_path
        self.constructions = {}
        self.modifiers = {}
        
        if json_path:
            self._load_and_parse()
    
    def _load_and_parse(self):
        """Load and parse GDS JSON database."""
        try:
            with open(self.json_path, 'r') as f:
                data = json.load(f)
            
            modules = data.get('modules', {})
            
            for module_key, module_data in modules.items():
                if not module_key.startswith('enclosure.'):
                    continue
                
                short_key = module_key.replace('enclosure.', '')
                
                # Determine boundary condition from key
                if '_exterior' in short_key:
                    boundary = 'Outdoors'
                elif '_ground' in short_key:
                    boundary = 'Ground'
                elif '_interior' in short_key:
                    boundary = 'Surface'
                else:
                    boundary = 'Outdoors'
                
                meta = module_data.get('meta', {})
                display_name = meta.get('display_name', short_key)
                design = module_data.get('design', {})
                
                # Parse thermal construction
                thermal = design.get('thermal', {})
                layers = thermal.get('layers', [])
                if layers:
                    is_window = any(l.get('type', '').startswith('EnergyWindow') for l in layers)
                    constr_dict = self._build_construction(short_key, layers, is_window)
                    if constr_dict:
                        self.constructions[display_name] = {
                            'hb_dict': constr_dict,
                            'boundary': boundary,
                            'is_window': is_window
                        }
                
                # Parse radiance modifier
                lighting = design.get('lighting', {})
                modifier = lighting.get('modifier', {})
                if modifier:
                    mod_dict = self._build_modifier(modifier)
                    if mod_dict:
                        mod_name = modifier.get('name', short_key + '_mod')
                        self.modifiers[mod_name] = {
                            'hb_dict': mod_dict,
                            'boundary': boundary,
                            'is_glass': modifier.get('type') in ['glass', 'trans'],
                            'display_name': display_name
                        }
        except Exception as e:
            print("GDS Library Parser error: {}".format(e))
    
    def _build_construction(self, module_key, layers, is_window):
        """Build HB construction dict from layers.
        
        Args:
            module_key: Module identifier
            layers: List of layer definitions
            is_window: True if this is a window construction
            
        Returns:
            Dict representing HB construction
        """
        constr_id = "gds__{}".format(module_key.replace('.', '_').replace('-', '_'))
        material_ids = []
        materials = []
        
        for i, layer in enumerate(layers):
            mat_id = "gds__{}_{}".format(constr_id, i)
            mat_dict = self._build_material(mat_id, layer)
            if mat_dict:
                material_ids.append(mat_id)
                materials.append(mat_dict)
        
        if not materials:
            return None
        
        return {
            'type': 'WindowConstruction' if is_window else 'OpaqueConstruction',
            'identifier': constr_id,
            'layers': material_ids,
            'materials': materials
        }
    
    def _build_material(self, mat_id, layer):
        """Build HB material dict from layer definition.
        
        Args:
            mat_id: Material identifier
            layer: Layer definition dict
            
        Returns:
            Dict representing HB material
        """
        layer_type = layer.get('type', 'EnergyMaterial')
        
        if layer_type == 'EnergyMaterial':
            return {
                'type': 'EnergyMaterial',
                'identifier': mat_id,
                'thickness': layer.get('thickness', 0.1),
                'conductivity': layer.get('conductivity', 1.0),
                'density': layer.get('density', 1000),
                'specific_heat': layer.get('specific_heat', 1000),
                'roughness': layer.get('roughness', 'MediumRough'),
                'thermal_absorptance': layer.get('thermal_absorptance', 0.9),
                'solar_absorptance': layer.get('solar_absorptance', 0.7),
                'visible_absorptance': layer.get('visible_absorptance', 0.7)
            }
        elif layer_type == 'EnergyMaterialNoMass':
            return {
                'type': 'EnergyMaterialNoMass',
                'identifier': mat_id,
                'r_value': layer.get('r_value', 0.1),
                'roughness': layer.get('roughness', 'MediumRough'),
                'thermal_absorptance': layer.get('thermal_absorptance', 0.9),
                'solar_absorptance': layer.get('solar_absorptance', 0.7),
                'visible_absorptance': layer.get('visible_absorptance', 0.7)
            }
        elif layer_type == 'EnergyWindowMaterialSimpleGlazSys':
            return {
                'type': 'EnergyWindowMaterialSimpleGlazSys',
                'identifier': mat_id,
                'u_factor': layer.get('u_factor', 2.7),
                'shgc': layer.get('shgc', 0.6),
                'vt': layer.get('visible_transmittance', layer.get('vt', 0.6))
            }
        elif layer_type == 'EnergyWindowMaterialGlazing':
            return {
                'type': 'EnergyWindowMaterialGlazing',
                'identifier': mat_id,
                'thickness': layer.get('thickness', 0.006),
                'solar_transmittance': layer.get('solar_transmittance', 0.6),
                'solar_reflectance': layer.get('solar_reflectance', 0.075),
                'visible_transmittance': layer.get('visible_transmittance', 0.6),
                'visible_reflectance': layer.get('visible_reflectance', 0.081),
                'infrared_transmittance': layer.get('infrared_transmittance', 0.0),
                'emissivity': layer.get('emissivity', 0.84),
                'conductivity': layer.get('conductivity', 0.9)
            }
        elif layer_type == 'EnergyWindowMaterialGas':
            return {
                'type': 'EnergyWindowMaterialGas',
                'identifier': mat_id,
                'gas_type': layer.get('gas_type', 'Air'),
                'thickness': layer.get('thickness', 0.0125)
            }
        
        return None
    
    def _build_modifier(self, modifier):
        """Build Radiance modifier dict.
        
        Args:
            modifier: Modifier definition dict
            
        Returns:
            Dict representing Radiance modifier
        """
        mod_type = modifier.get('type', 'plastic')
        mod_name = modifier.get('name', 'unnamed')
        
        if mod_type == 'plastic':
            rgb = modifier.get('rgb_reflectance', [0.5, 0.5, 0.5])
            return {
                'type': 'Plastic',
                'identifier': mod_name,
                'modifier': None,
                'r_reflectance': rgb[0],
                'g_reflectance': rgb[1],
                'b_reflectance': rgb[2],
                'specularity': modifier.get('specularity', 0.0),
                'roughness': modifier.get('roughness', 0.0)
            }
        elif mod_type == 'glass':
            rgb = modifier.get('rgb_transmissivity', [0.6, 0.6, 0.6])
            return {
                'type': 'Glass',
                'identifier': mod_name,
                'modifier': None,
                'r_transmissivity': rgb[0],
                'g_transmissivity': rgb[1],
                'b_transmissivity': rgb[2]
            }
        elif mod_type == 'trans':
            rgb_refl = modifier.get('rgb_reflectance', [0.5, 0.5, 0.5])
            return {
                'type': 'Trans',
                'identifier': mod_name,
                'modifier': None,
                'r_reflectance': rgb_refl[0],
                'g_reflectance': rgb_refl[1],
                'b_reflectance': rgb_refl[2],
                'specularity': modifier.get('specularity', 0.0),
                'roughness': modifier.get('roughness', 0.0),
                'transmitted_diff': modifier.get('transmitted_diff', 0.0),
                'transmitted_spec': modifier.get('transmitted_spec', 0.0)
            }
        
        return None
    
    def get_constructions_for_boundary(self, boundary, is_window=False):
        """Get constructions for a specific boundary condition.
        
        Args:
            boundary: 'Outdoors', 'Ground', or 'Surface'
            is_window: True for window constructions, False for opaque
        
        Returns:
            Dict of {display_name: construction_data}
        """
        result = {}
        for name, data in self.constructions.items():
            if data['boundary'] == boundary and data['is_window'] == is_window:
                result[name] = data
        return result
    
    def get_modifiers_for_boundary(self, boundary, is_glass=False):
        """Get modifiers for a specific boundary condition.
        
        Args:
            boundary: 'Outdoors', 'Ground', or 'Surface'
            is_glass: True for glass modifiers, False for opaque
        
        Returns:
            Dict of {modifier_name: modifier_data}
        """
        result = {}
        for name, data in self.modifiers.items():
            if data['boundary'] == boundary and data['is_glass'] == is_glass:
                result[name] = data
        return result
    
    def get_construction(self, display_name):
        """Get construction dict by display name.
        
        Args:
            display_name: Construction display name
            
        Returns:
            HB construction dict, or None if not found
        """
        if display_name in self.constructions:
            return self.constructions[display_name]['hb_dict']
        return None
    
    def get_modifier(self, modifier_name):
        """Get modifier dict by name.
        
        Args:
            modifier_name: Modifier name
            
        Returns:
            Radiance modifier dict, or None if not found
        """
        if modifier_name in self.modifiers:
            return self.modifiers[modifier_name]['hb_dict']
        return None
    
    def get_all_construction_names(self):
        """Get list of all construction display names."""
        return list(self.constructions.keys())
    
    def get_all_modifier_names(self):
        """Get list of all modifier names."""
        return list(self.modifiers.keys())
