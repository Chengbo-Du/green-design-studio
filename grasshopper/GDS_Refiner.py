"""
GDS GBE Refiner v8: Assembly Designer with Hub Integration
===========================================================
Full integration with GDS Hub - reads HVAC, PV, SHW, IDF configs automatically.

v8 - MODULAR: HVAC presets imported from gds-core package
     Run 'pip install gds-core' before using this script

v7 - HUB INTEGRATION:
- Reads GDS_HVAC_DEFAULT from Hub and auto-creates default HVAC system
- Reads GDS_PV_CONFIG from Hub and applies PV to all shades
- Reads GDS_SOLHW_CONFIG from Hub and injects SHW system into model
- Reads GDS_RENEWABLES_IDF from Hub and injects Battery/Wind IDF strings

INPUTS:
    _model: A Honeybee Model
    _run: Boolean/Button to launch the UI
    _gds_library: Path to GDS module database JSON file (optional)
    _output_path_: Output .hbjson file path (optional)
    _preview_name_: Nickname of Brep parameter for preview

OUTPUTS:
    hbjson_path: Path to the saved .hbjson file
    report: Status messages
"""

import Rhino
import Rhino.Geometry as rg
import System
import Eto.Forms as forms
import Eto.Drawing as drawing
import scriptcontext as sc
import json
import os
import tempfile
import time
import hashlib

from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path
import Grasshopper

# ========================= GDS-CORE IMPORTS ==================================
try:
    from gds import __version__ as GDS_CORE_VERSION
    from gds.presets.hvac import (
        HVAC_CATEGORIES, HVAC_VINTAGES, HVAC_ECONOMIZER_TYPES, HVAC_RADIANT_TYPES
    )
    GDS_CORE_AVAILABLE = True
except ImportError:
    GDS_CORE_AVAILABLE = False
    GDS_CORE_VERSION = "N/A"
    print("WARNING: gds-core not installed. Using embedded HVAC presets.")
    
    # Fallback HVAC presets
    HVAC_CATEGORIES = {
        "Ideal Air (Loads Only)": {
            "class": "IdealAirSystem",
            "description": "Perfect HVAC for load calculations",
            "equipment_types": ["IdealAirSystem"]
        },
        "All-Air: VAV": {
            "class": "VAV",
            "description": "Variable Air Volume systems",
            "equipment_types": ["VAV_Chiller_Boiler", "VAV_Chiller_ASHP", "VAV_Chiller_DHW"]
        },
    }
    HVAC_VINTAGES = ["ASHRAE_2019", "ASHRAE_2016", "ASHRAE_2013"]
    HVAC_ECONOMIZER_TYPES = ["NoEconomizer", "DifferentialDryBulb", "DifferentialEnthalpy"]
    HVAC_RADIANT_TYPES = ["Floor", "Ceiling", "FloorWithCarpet", "CeilingMetalPanel"]
# =============================================================================

STORAGE_KEY = "HB_SURFACE_PROP_EDITOR_V5"
DIALOG_KEY = "HB_SURFACE_PROP_EDITOR_V5_DIALOG"
COMPONENT_KEY = "HB_SURFACE_PROP_EDITOR_V5_COMPONENT"
RUN_STATE_KEY = "HB_SURFACE_PROP_EDITOR_V5_RUN_STATE"
OUTPUT_PATH_KEY = "HB_SURFACE_PROP_EDITOR_V5_OUTPUT_PATH"
MODEL_HASH_KEY = "HB_SURFACE_PROP_EDITOR_V5_MODEL_HASH"
LAST_MODIFICATIONS_KEY = "HB_SURFACE_PROP_EDITOR_V5_LAST_MODS"
RELEASE_OUTPUT_KEY = "HB_SURFACE_PROP_EDITOR_V5_RELEASE"
HVAC_CONFIG_KEY = "GDS_HVAC_CONFIG"
HVAC_DEFAULT_KEY = "GDS_HVAC_DEFAULT"
PV_CONFIG_KEY = "GDS_PV_CONFIG"
SOLHW_CONFIG_KEY = "GDS_SOLHW_CONFIG"
IDF_CONFIG_KEY = "GDS_RENEWABLES_IDF"

# Version info for window title
GDS_REFINER_VERSION = "v8"
if GDS_CORE_AVAILABLE:
    REFINER_TITLE = "GDS Refiner {} (core {})".format(GDS_REFINER_VERSION, GDS_CORE_VERSION)
else:
    REFINER_TITLE = "GDS Refiner {} (standalone)".format(GDS_REFINER_VERSION)



# ======================= HUB INTEGRATION FUNCTIONS (v7) =======================

def load_hub_hvac_default():
    """Load HVAC default configuration from GDS Hub."""
    hub_default = sc.sticky.get(HVAC_DEFAULT_KEY, None)
    if hub_default and isinstance(hub_default, dict):
        print("GDS Hub: Loaded HVAC default - {}".format(hub_default.get('preset_name', 'Unknown')))
        return hub_default
    return None


def load_hub_pv_config():
    """Load PV configuration from GDS Hub."""
    pv_config = sc.sticky.get(PV_CONFIG_KEY, None)
    if pv_config and isinstance(pv_config, dict):
        print("GDS Hub: Loaded PV config - {:.1f}% efficiency".format(
            pv_config.get('efficiency', 0) * 100))
        return pv_config
    return None


def load_hub_shw_config():
    """Load Solar Hot Water configuration from GDS Hub."""
    shw_config = sc.sticky.get(SOLHW_CONFIG_KEY, None)
    if shw_config and isinstance(shw_config, dict) and shw_config.get('enabled', False):
        print("GDS Hub: Loaded SHW config - {} m² collector".format(
            shw_config.get('collector_area', 0)))
        return shw_config
    return None


def load_hub_idf_injection():
    """Load IDF injection string from GDS Hub (Battery, Wind)."""
    idf_string = sc.sticky.get(IDF_CONFIG_KEY, None)
    if idf_string and isinstance(idf_string, str):
        has_content = any(line.strip() and not line.strip().startswith('!') 
                         for line in idf_string.split('\n'))
        if has_content:
            print("GDS Hub: Loaded IDF injection string")
            return idf_string
    return None


def apply_pv_to_model_dict(model_dict, pv_config):
    """
    Apply PV properties to orphaned/context shades in model dict.
    Returns: (count, list of shade names)
    """
    if not pv_config:
        return 0, []
    
    pv_count = 0
    pv_shade_names = []
    
    # Get all shades from model
    all_shades = model_dict.get('orphaned_shades', []) + model_dict.get('context_shades', [])
    
    if not all_shades:
        print("PV: No orphaned or context shades found in model")
        return 0, []
    
    # Build PV properties dict in HB schema
    pv_properties = {
        'type': 'PVProperties',
        'identifier': 'GDS_PV_System',
        'rated_efficiency': pv_config.get('efficiency', 0.15),
        'active_area_fraction': pv_config.get('active_area_fraction', 0.9),
        'module_type': pv_config.get('module_type', 'Standard'),
        'mounting_type': pv_config.get('mounting_type', 'FixedOpenRack'),
        'system_loss_fraction': pv_config.get('loss_fraction', 0.14),
    }
    
    for shade in all_shades:
        shade_id = shade.get('identifier', '')
        
        if 'properties' not in shade:
            shade['properties'] = {}
        if 'energy' not in shade['properties']:
            shade['properties']['energy'] = {}
        
        shade['properties']['energy']['pv_properties'] = pv_properties.copy()
        pv_count += 1
        pv_shade_names.append(shade.get('display_name', shade_id)[:25])
        print("PV applied to shade: {}".format(shade_id[:40]))
    
    return pv_count, pv_shade_names


def apply_shw_to_model_dict(model_dict, shw_config):
    """
    Apply SHW system to model dict.
    Returns: (success, report_message)
    """
    if not shw_config:
        return False, ""
    
    # Build SHW system dict
    shw_dict = {
        'type': 'SHWSystem',
        'identifier': 'GDS_SHW_System',
        'equipment_type': shw_config.get('equipment_type', 'Gas_WaterHeater'),
        'heater_efficiency': shw_config.get('efficiency', 0.8),
        'ambient_condition': 22.0,
        'ambient_loss_coefficient': 0.8,
    }
    
    # Ensure energy properties exist
    if 'properties' not in model_dict:
        model_dict['properties'] = {}
    if 'energy' not in model_dict['properties']:
        model_dict['properties']['energy'] = {}
    if 'shws' not in model_dict['properties']['energy']:
        model_dict['properties']['energy']['shws'] = []
    
    # Add SHW system
    existing_ids = {s.get('identifier') for s in model_dict['properties']['energy']['shws']}
    if shw_dict['identifier'] not in existing_ids:
        model_dict['properties']['energy']['shws'].append(shw_dict)
    
    # Assign to all rooms
    for room_dict in model_dict.get('rooms', []):
        if 'properties' not in room_dict:
            room_dict['properties'] = {}
        if 'energy' not in room_dict['properties']:
            room_dict['properties']['energy'] = {}
        room_dict['properties']['energy']['shw'] = shw_dict['identifier']
    
    collector_area = shw_config.get('collector_area', 0)
    if collector_area > 0:
        report = "SHW: {} ({} m² solar)".format(shw_config.get('equipment_type', 'Unknown'), collector_area)
    else:
        report = "SHW: {}".format(shw_config.get('equipment_type', 'Unknown'))
    
    return True, report


def inject_idf_to_model_dict(model_dict, idf_string):
    """
    Inject IDF string into model dict.
    Returns: (success, report_message)
    """
    if not idf_string:
        return False, ""
    
    # Ensure energy properties exist
    if 'properties' not in model_dict:
        model_dict['properties'] = {}
    if 'energy' not in model_dict['properties']:
        model_dict['properties']['energy'] = {}
    
    # Append to additional_idf
    existing_idf = model_dict['properties']['energy'].get('additional_idf', '')
    if existing_idf:
        combined = existing_idf + '\n\n! === GDS Hub Renewables ===\n' + idf_string
    else:
        combined = '! === GDS Hub Renewables ===\n' + idf_string
    
    model_dict['properties']['energy']['additional_idf'] = combined
    
    # Count objects
    obj_count = sum(1 for line in idf_string.split('\n') 
                   if line.strip() and not line.strip().startswith('!') and ';' in line)
    
    return True, "IDF: {} objects injected".format(obj_count)


# ======================= END HUB INTEGRATION FUNCTIONS ========================


def get_model_hash(model):
    """
    Generate a hash of the model to detect changes.
    Uses model's dict representation for comparison.
    """
    try:
        model_dict = model.to_dict()
        model_str = json.dumps(model_dict, sort_keys=True)
        return hashlib.md5(model_str.encode()).hexdigest()
    except:
        return None


def get_modifications_hash(modified_faces, modified_apertures, modified_doors):
    """
    Generate a hash of the modifications to detect changes.
    Now includes doors.
    """
    try:
        mods_dict = {
            'faces': modified_faces,
            'apertures': modified_apertures,
            'doors': modified_doors
        }
        mods_str = json.dumps(mods_dict, sort_keys=True)
        return hashlib.md5(mods_str.encode()).hexdigest()
    except:
        return None


def get_unique_filepath(filepath):
    """
    Get a unique filepath by adding suffix if file exists.
    """
    if not os.path.exists(filepath):
        return filepath
    
    base, ext = os.path.splitext(filepath)
    counter = 1
    
    while True:
        new_path = "{}_{}{}".format(base, counter, ext)
        if not os.path.exists(new_path):
            return new_path
        counter += 1
        if counter > 1000:
            timestamp = int(time.time())
            return "{}_{}{}".format(base, timestamp, ext)


def get_output_filepath(user_path=None):
    """
    Get the output filepath.
    """
    if user_path:
        if not user_path.lower().endswith('.hbjson'):
            user_path = user_path + '.hbjson'
        return get_unique_filepath(user_path)
    else:
        temp_dir = tempfile.gettempdir()
        timestamp = int(time.time())
        filename = "hb_modified_model_{}.hbjson".format(timestamp)
        return os.path.join(temp_dir, filename)


def create_brep_from_vertices(vertices):
    """Create Brep from ladybug Point3D vertices"""
    if vertices is None or len(vertices) < 3:
        return None
    try:
        pts = [rg.Point3d(v.x, v.y, v.z) for v in vertices]
        pts.append(pts[0])
        polyline = rg.Polyline(pts)
        curve = polyline.ToNurbsCurve()
        if curve is None:
            return None
        tol = Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
        breps = rg.Brep.CreatePlanarBreps(curve, tol)
        if breps and len(breps) > 0:
            return breps[0]
        breps = rg.Brep.CreatePlanarBreps(curve, 0.01)
        if breps and len(breps) > 0:
            return breps[0]
        n = len(pts) - 1
        if n == 4:
            srf = rg.NurbsSurface.CreateFromCorners(pts[0], pts[1], pts[2], pts[3])
            if srf:
                return srf.ToBrep()
        elif n == 3:
            srf = rg.NurbsSurface.CreateFromCorners(pts[0], pts[1], pts[2])
            if srf:
                return srf.ToBrep()
        return None
    except:
        return None


def find_preview_component(nickname):
    """Find a GH component by nickname"""
    try:
        doc = Grasshopper.Instances.ActiveCanvas.Document
        for obj in doc.Objects:
            if obj.NickName == nickname:
                return obj
    except:
        pass
    return None


def update_preview_component(nickname, breps):
    """Update preview component with breps - thread safe"""
    def do_update():
        comp = find_preview_component(nickname)
        if comp is None:
            return
        try:
            if hasattr(comp, 'PersistentData'):
                comp.PersistentData.Clear()
                if breps:
                    from Grasshopper.Kernel.Types import GH_Brep
                    for brep in breps:
                        if brep:
                            gh_brep = GH_Brep(brep)
                            comp.PersistentData.Append(gh_brep)
                comp.ExpireSolution(True)
        except Exception as e:
            print("Preview update error: {}".format(e))
    
    try:
        Rhino.RhinoApp.InvokeOnUiThread(System.Action(do_update))
    except:
        do_update()


def clear_preview_component(nickname):
    """Clear preview component"""
    update_preview_component(nickname, [])


def expire_gh_component():
    """Expire the main GH component to trigger recalculation"""
    try:
        if COMPONENT_KEY in sc.sticky:
            comp = sc.sticky[COMPONENT_KEY]
            if comp:
                def do_expire():
                    comp.ExpireSolution(True)
                Rhino.RhinoApp.InvokeOnUiThread(System.Action(do_expire))
    except:
        pass


class GDSLibraryParser:
    """Parse GDS module database"""
    
    def __init__(self, json_path):
        self.json_path = json_path
        self.constructions = {}
        self.modifiers = {}
        if json_path:
            self._load_and_parse()
    
    def _load_and_parse(self):
        try:
            with open(self.json_path, 'r') as f:
                data = json.load(f)
            modules = data.get('modules', {})
            for module_key, module_data in modules.items():
                if not module_key.startswith('enclosure.'):
                    continue
                short_key = module_key.replace('enclosure.', '')
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
        except:
            pass
    
    def _build_construction(self, module_key, layers, is_window):
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
        elif layer_type == 'EnergyWindowMaterialSimpleGlazSys':
            return {
                'type': 'EnergyWindowMaterialSimpleGlazSys',
                'identifier': mat_id,
                'u_factor': layer.get('u_factor', 2.7),
                'shgc': layer.get('shgc', 0.6),
                'vt': layer.get('visible_transmittance', 0.6)
            }
        return None
    
    def _build_modifier(self, modifier):
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
        return None
    
    def get_constructions_for_boundary(self, boundary, is_window=False):
        result = {}
        for name, data in self.constructions.items():
            if data['boundary'] == boundary and data['is_window'] == is_window:
                result[name] = data
        return result
    
    def get_modifiers_for_boundary(self, boundary, is_glass=False):
        result = {}
        for name, data in self.modifiers.items():
            if data['boundary'] == boundary and data['is_glass'] == is_glass:
                result[name] = data
        return result


class SurfacePropertyEditor(forms.Form):
    """Main editor dialog - MODELESS with preview support"""
    
    def __init__(self):
        forms.Form.__init__(self)
    
    def initialize(self, hb_model, gds_parser, preview_nickname):
        self.hb_model = hb_model
        self.gds_parser = gds_parser
        self.preview_nickname = preview_nickname
        self.face_list = []
        self.aperture_list = []
        self.door_list = []
        self.filtered_faces = []
        self.filtered_apertures = []
        self.filtered_doors = []
        self.modified_faces = {}
        self.modified_apertures = {}
        self.modified_doors = {}  # NEW: Track door modifications
        self.shading_config = {}
        # HVAC: New data structures for system grouping
        self.hvac_systems = {}  # system_name -> config (defines the HVAC systems)
        self.room_hvac_assignments = {}  # room_id -> system_name (assigns rooms to systems)
        self.room_list = []
        self.room_breps = {}  # NEW: Store room geometry for preview (room_id -> list of breps)
        
        if STORAGE_KEY in sc.sticky:
            stored = sc.sticky[STORAGE_KEY]
            self.modified_faces = dict(stored.get('faces', {}))
            self.modified_apertures = dict(stored.get('apertures', {}))
            self.modified_doors = dict(stored.get('doors', {}))  # NEW
            self.shading_config = dict(stored.get('shading', {}))
            # Load new HVAC data structures
            self.hvac_systems = dict(stored.get('hvac_systems', {}))
            self.room_hvac_assignments = dict(stored.get('room_hvac_assignments', {}))
        
        # v7: Load Hub's HVAC default and pre-create system if none defined
        if not self.hvac_systems:
            hub_hvac = load_hub_hvac_default()
            if hub_hvac:
                system_name = "Hub_{}".format(hub_hvac.get('preset_name', 'Default'))
                self.hvac_systems[system_name] = {
                    'class': hub_hvac.get('class', 'IdealAirSystem'),
                    'equipment_type': hub_hvac.get('equipment_type', 'IdealAirSystem'),
                    'vintage': hub_hvac.get('vintage', 'ASHRAE_2019'),
                    'economizer_type': hub_hvac.get('economizer_type', 'NoEconomizer'),
                    'sensible_heat_recovery': hub_hvac.get('sensible_heat_recovery', 0),
                    'latent_heat_recovery': hub_hvac.get('latent_heat_recovery', 0),
                    'demand_controlled_ventilation': hub_hvac.get('demand_controlled_ventilation', False),
                    'radiant_type': hub_hvac.get('radiant_type', 'Floor'),
                }
                print("Created HVAC system from Hub: {}".format(system_name))
        
        self._extract_model_data()
        self._setup_form()
        self.Closed += self._on_form_closed
        return self
    
    def _extract_model_data(self):
        for room in self.hb_model.rooms:
            room_name = room.display_name or room.identifier
            room_id = room.identifier
            
            try:
                room_area = round(room.floor_area, 2)
            except:
                room_area = 0
            
            hvac_status = "<default>"
            if room_id in self.room_hvac_assignments:
                system_name = self.room_hvac_assignments[room_id]
                hvac_status = system_name[:15]
            elif hasattr(room.properties, 'energy') and hasattr(room.properties.energy, 'hvac'):
                if room.properties.energy.hvac is not None:
                    hvac_status = str(type(room.properties.energy.hvac).__name__)[:15]
            
            self.room_list.append({
                'id': room_id,
                'name': room_name,
                'area': room_area,
                'hvac': hvac_status
            })
            
            # NEW: Collect all breps for this room for preview
            room_brep_list = []
            
            for face in room.faces:
                face_id = face.identifier
                bc = "Outdoors"
                bc_str = str(face.boundary_condition)
                if 'Ground' in bc_str:
                    bc = "Ground"
                elif 'Surface' in bc_str or 'Adiabatic' in bc_str:
                    bc = "Surface"
                brep = create_brep_from_vertices(face.geometry.boundary)
                # Add to room breps for room preview
                if brep:
                    room_brep_list.append(brep)
                stored_constr = self.modified_faces.get(face_id, {}).get('construction', '<Unchanged>')
                stored_mod = self.modified_faces.get(face_id, {}).get('modifier', '<Unchanged>')
                self.face_list.append({
                    'id': face_id,
                    'room': room_name,
                    'type': str(face.type),
                    'bc': bc,
                    'area': round(face.area, 2),
                    'brep': brep,
                    'construction': stored_constr,
                    'modifier': stored_mod
                })
                for ap in face.apertures:
                    ap_id = ap.identifier
                    ap_brep = create_brep_from_vertices(ap.geometry.boundary)
                    stored_ap_constr = self.modified_apertures.get(ap_id, {}).get('construction', '<Unchanged>')
                    stored_ap_mod = self.modified_apertures.get(ap_id, {}).get('modifier', '<Unchanged>')
                    self.aperture_list.append({
                        'id': ap_id,
                        'room': room_name,
                        'parent': face_id,
                        'bc': bc,
                        'area': round(ap.area, 2),
                        'brep': ap_brep,
                        'construction': stored_ap_constr,
                        'modifier': stored_ap_mod
                    })
                # NEW: Extract doors with stored modifications
                for door in face.doors:
                    door_id = door.identifier
                    door_brep = create_brep_from_vertices(door.geometry.boundary)
                    # Check if door is glass
                    is_glass = False
                    try:
                        is_glass = door.is_glass
                    except:
                        pass
                    stored_door_constr = self.modified_doors.get(door_id, {}).get('construction', '<Unchanged>')
                    stored_door_mod = self.modified_doors.get(door_id, {}).get('modifier', '<Unchanged>')
                    self.door_list.append({
                        'id': door_id,
                        'room': room_name,
                        'parent': face_id,
                        'bc': bc,
                        'area': round(door.area, 2),
                        'brep': door_brep,
                        'is_glass': is_glass,
                        'construction': stored_door_constr,
                        'modifier': stored_door_mod
                    })
            
            # NEW: Store all breps for this room
            if room_brep_list:
                self.room_breps[room_id] = room_brep_list
        
        self.filtered_faces = list(self.face_list)
        self.filtered_apertures = list(self.aperture_list)
        self.filtered_doors = list(self.door_list)
    
    def _setup_form(self):
        self.Title = REFINER_TITLE
        self.Resizable = True
        self.Size = drawing.Size(950, 800)
        self.Padding = drawing.Padding(10)
        
        main_layout = forms.DynamicLayout()
        main_layout.Spacing = drawing.Size(5, 5)
        
        face_geo_count = sum(1 for f in self.face_list if f['brep'])
        ap_geo_count = sum(1 for a in self.aperture_list if a['brep'])
        door_geo_count = sum(1 for d in self.door_list if d['brep'])
        info_text = "Faces: {} ({} geo) | Apertures: {} ({} geo) | Doors: {} ({} geo) | GDS: {} constr, {} mod".format(
            len(self.face_list), face_geo_count, len(self.aperture_list), ap_geo_count,
            len(self.door_list), door_geo_count,
            len(self.gds_parser.constructions), len(self.gds_parser.modifiers))
        main_layout.Add(forms.Label(Text=info_text))
        
        preview_comp = find_preview_component(self.preview_nickname)
        if preview_comp:
            self.preview_status = forms.Label(Text="Preview: Connected to '{}'".format(self.preview_nickname))
        else:
            self.preview_status = forms.Label(Text="Preview: Component '{}' not found".format(self.preview_nickname))
        main_layout.Add(self.preview_status)
        
        self.tabs = forms.TabControl()
        face_tab = forms.TabPage(Text="Opaque Faces ({})".format(len(self.face_list)))
        face_tab.Content = self._create_face_panel()
        self.tabs.Pages.Add(face_tab)
        ap_tab = forms.TabPage(Text="Apertures ({})".format(len(self.aperture_list)))
        ap_tab.Content = self._create_aperture_panel()
        self.tabs.Pages.Add(ap_tab)
        # NEW: Doors tab
        door_tab = forms.TabPage(Text="Doors ({})".format(len(self.door_list)))
        door_tab.Content = self._create_door_panel()
        self.tabs.Pages.Add(door_tab)
        shading_tab = forms.TabPage(Text="Shading")
        shading_tab.Content = self._create_shading_panel()
        self.tabs.Pages.Add(shading_tab)
        hvac_tab = forms.TabPage(Text="HVAC Systems ({})".format(len(self.room_list)))
        hvac_tab.Content = self._create_hvac_panel()
        self.tabs.Pages.Add(hvac_tab)
        main_layout.Add(self.tabs, yscale=True)
        
        self.status_label = forms.Label()
        self._update_status()
        main_layout.Add(self.status_label)
        
        preview_layout = forms.DynamicLayout()
        preview_layout.BeginHorizontal()
        self.chk_preview_selected = forms.CheckBox(Text="Preview Selected")
        self.chk_preview_selected.Checked = True
        self.chk_preview_selected.CheckedChanged += self._on_preview_toggle
        preview_layout.Add(self.chk_preview_selected)
        self.chk_preview_modified = forms.CheckBox(Text="Preview All Modified")
        self.chk_preview_modified.CheckedChanged += self._on_preview_toggle
        preview_layout.Add(self.chk_preview_modified)
        btn_clear_preview = forms.Button(Text="Clear Preview")
        btn_clear_preview.Click += self._on_clear_preview
        preview_layout.Add(btn_clear_preview)
        preview_layout.Add(None, xscale=True)
        preview_layout.EndHorizontal()
        main_layout.Add(preview_layout)
        
        btn_layout = forms.DynamicLayout()
        btn_layout.BeginHorizontal()
        # Left column: Save Settings | Clear All
        btn_save = forms.Button(Text="Save Settings")
        btn_save.Click += self._on_save
        btn_layout.Add(btn_save)
        btn_clear = forms.Button(Text="Clear All")
        btn_clear.Click += self._on_clear
        btn_layout.Add(btn_clear)
        btn_layout.Add(None, xscale=True)
        # Center column: Save & Run (green)
        btn_save_run = forms.Button(Text="Save && Run")
        btn_save_run.BackgroundColor = drawing.Color.FromArgb(200, 255, 200)
        btn_save_run.Click += self._on_save_and_run
        btn_layout.Add(btn_save_run)
        btn_layout.Add(None, xscale=True)
        # Right column: Save & Close | Cancel
        btn_save_close = forms.Button(Text="Save && Close")
        btn_save_close.Click += self._on_apply
        btn_layout.Add(btn_save_close)
        btn_cancel = forms.Button(Text="Cancel")
        btn_cancel.Click += self._on_cancel
        btn_layout.Add(btn_cancel)
        btn_layout.EndHorizontal()
        main_layout.Add(btn_layout)
        
        self.Content = main_layout
    
    def _update_status(self):
        mod_face_count = len([f for f in self.face_list if f['id'] in self.modified_faces])
        mod_ap_count = len([a for a in self.aperture_list if a['id'] in self.modified_apertures])
        mod_door_count = len([d for d in self.door_list if d['id'] in self.modified_doors])
        self.status_label.Text = "Modified: {} faces, {} apertures, {} doors".format(
            mod_face_count, mod_ap_count, mod_door_count)
    
    def _update_preview(self):
        """Update preview - includes faces, apertures, doors, rooms, and shading selections"""
        breps = []
        if self.chk_preview_selected.Checked:
            # Faces
            selected_indices = list(self.face_grid.SelectedRows)
            for idx in selected_indices:
                if idx < len(self.filtered_faces):
                    brep = self.filtered_faces[idx].get('brep')
                    if brep:
                        breps.append(brep)
            # Apertures
            selected_ap_indices = list(self.ap_grid.SelectedRows)
            for idx in selected_ap_indices:
                if idx < len(self.filtered_apertures):
                    brep = self.filtered_apertures[idx].get('brep')
                    if brep:
                        breps.append(brep)
            # Doors
            selected_door_indices = list(self.door_grid.SelectedRows)
            for idx in selected_door_indices:
                if idx < len(self.filtered_doors):
                    brep = self.filtered_doors[idx].get('brep')
                    if brep:
                        breps.append(brep)
            # Rooms (from HVAC tab)
            try:
                selected_room_indices = list(self.hvac_room_grid.SelectedRows)
                for idx in selected_room_indices:
                    if idx < len(self.filtered_hvac_rooms):
                        room_id = self.filtered_hvac_rooms[idx]['id']
                        room_brep_list = self.room_breps.get(room_id, [])
                        for brep in room_brep_list:
                            if brep and brep not in breps:
                                breps.append(brep)
            except:
                pass  # HVAC grid might not exist yet during initialization
            
            # Shading tab selections (walls, apertures, doors)
            try:
                # Shading walls
                selected_shade_wall_indices = list(self.shade_wall_grid.SelectedRows)
                for idx in selected_shade_wall_indices:
                    if idx < len(self.filtered_shade_walls):
                        brep = self.filtered_shade_walls[idx].get('brep')
                        if brep and brep not in breps:
                            breps.append(brep)
                # Shading apertures
                selected_shade_ap_indices = list(self.shade_ap_grid.SelectedRows)
                for idx in selected_shade_ap_indices:
                    if idx < len(self.filtered_shade_apertures):
                        brep = self.filtered_shade_apertures[idx].get('brep')
                        if brep and brep not in breps:
                            breps.append(brep)
                # Shading doors
                selected_shade_door_indices = list(self.shade_door_grid.SelectedRows)
                for idx in selected_shade_door_indices:
                    if idx < len(self.filtered_shade_doors):
                        brep = self.filtered_shade_doors[idx].get('brep')
                        if brep and brep not in breps:
                            breps.append(brep)
            except:
                pass  # Shading grids might not exist yet during initialization
        
        if self.chk_preview_modified.Checked:
            for f in self.face_list:
                if f['id'] in self.modified_faces and f.get('brep'):
                    if f['brep'] not in breps:
                        breps.append(f['brep'])
            for a in self.aperture_list:
                if a['id'] in self.modified_apertures and a.get('brep'):
                    if a['brep'] not in breps:
                        breps.append(a['brep'])
            # Modified doors
            for d in self.door_list:
                if d['id'] in self.modified_doors and d.get('brep'):
                    if d['brep'] not in breps:
                        breps.append(d['brep'])
            # Rooms with HVAC assignments
            for room_id in self.room_hvac_assignments.keys():
                room_brep_list = self.room_breps.get(room_id, [])
                for brep in room_brep_list:
                    if brep and brep not in breps:
                        breps.append(brep)
            
            # Surfaces with shading configured
            for surface_id in self.shading_config.keys():
                # Check faces
                for f in self.face_list:
                    if f['id'] == surface_id and f.get('brep'):
                        if f['brep'] not in breps:
                            breps.append(f['brep'])
                # Check apertures
                for a in self.aperture_list:
                    if a['id'] == surface_id and a.get('brep'):
                        if a['brep'] not in breps:
                            breps.append(a['brep'])
                # Check doors
                for d in self.door_list:
                    if d['id'] == surface_id and d.get('brep'):
                        if d['brep'] not in breps:
                            breps.append(d['brep'])
        
        update_preview_component(self.preview_nickname, breps)
    
    def _on_preview_toggle(self, sender, e):
        self._update_preview()
    
    def _on_clear_preview(self, sender, e):
        clear_preview_component(self.preview_nickname)
    
    def _create_face_panel(self):
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(5, 5)
        layout.Padding = drawing.Padding(5)
        
        filter_layout = forms.DynamicLayout()
        filter_layout.BeginHorizontal()
        filter_layout.Add(forms.Label(Text="Room:"))
        self.room_filter = forms.DropDown()
        rooms = ["<All>"] + sorted(set(f['room'] for f in self.face_list))
        for r in rooms:
            self.room_filter.Items.Add(r)
        self.room_filter.SelectedIndex = 0
        filter_layout.Add(self.room_filter)
        filter_layout.Add(forms.Label(Text="  Type:"))
        self.type_filter = forms.DropDown()
        for t in ["<All>", "Wall", "Floor", "RoofCeiling"]:
            self.type_filter.Items.Add(t)
        self.type_filter.SelectedIndex = 0
        filter_layout.Add(self.type_filter)
        filter_layout.Add(forms.Label(Text="  BC:"))
        self.bc_filter = forms.DropDown()
        for bc in ["<All>", "Outdoors", "Ground", "Surface"]:
            self.bc_filter.Items.Add(bc)
        self.bc_filter.SelectedIndex = 0
        filter_layout.Add(self.bc_filter)
        btn_filter = forms.Button(Text="Filter")
        btn_filter.Click += self._on_filter_faces
        filter_layout.Add(btn_filter)
        filter_layout.Add(None, xscale=True)
        filter_layout.EndHorizontal()
        layout.Add(filter_layout)
        
        self.face_grid = forms.GridView()
        self.face_grid.Height = 200
        self.face_grid.AllowMultipleSelection = True
        
        # Column: Modified marker
        col_mod = forms.GridColumn()
        col_mod.HeaderText = "M"
        col_mod.DataCell = forms.TextBoxCell(0)
        col_mod.Width = 25
        self.face_grid.Columns.Add(col_mod)
        
        # Column: Geometry marker
        col_geo = forms.GridColumn()
        col_geo.HeaderText = "G"
        col_geo.DataCell = forms.TextBoxCell(1)
        col_geo.Width = 25
        self.face_grid.Columns.Add(col_geo)
        
        # Column: Type
        col_type = forms.GridColumn()
        col_type.HeaderText = "Type"
        col_type.DataCell = forms.TextBoxCell(2)
        col_type.Width = 80
        self.face_grid.Columns.Add(col_type)
        
        # Column: Room
        col_room = forms.GridColumn()
        col_room.HeaderText = "Room"
        col_room.DataCell = forms.TextBoxCell(3)
        col_room.Width = 150
        self.face_grid.Columns.Add(col_room)
        
        # Column: BC
        col_bc = forms.GridColumn()
        col_bc.HeaderText = "BC"
        col_bc.DataCell = forms.TextBoxCell(4)
        col_bc.Width = 60
        self.face_grid.Columns.Add(col_bc)
        
        # Column: Area
        col_area = forms.GridColumn()
        col_area.HeaderText = "Area"
        col_area.DataCell = forms.TextBoxCell(5)
        col_area.Width = 60
        self.face_grid.Columns.Add(col_area)
        
        # Column: Construction
        col_constr = forms.GridColumn()
        col_constr.HeaderText = "Construction"
        col_constr.DataCell = forms.TextBoxCell(6)
        col_constr.Width = 150
        self.face_grid.Columns.Add(col_constr)
        
        self._refresh_face_grid()
        self.face_grid.SelectionChanged += self._on_face_selection_changed
        layout.Add(self.face_grid, yscale=True)
        
        assign_group = forms.GroupBox(Text="Assign Properties")
        assign_layout = forms.DynamicLayout()
        assign_layout.Spacing = drawing.Size(5, 5)
        assign_layout.Padding = drawing.Padding(5)
        self.face_selection_info = forms.Label(Text="No selection")
        assign_layout.Add(self.face_selection_info)
        assign_layout.BeginHorizontal()
        assign_layout.Add(forms.Label(Text="Construction:"))
        self.face_constr_dropdown = forms.DropDown()
        self.face_constr_dropdown.Items.Add("<Unchanged>")
        self.face_constr_dropdown.SelectedIndex = 0
        assign_layout.Add(self.face_constr_dropdown, xscale=True)
        assign_layout.EndHorizontal()
        assign_layout.BeginHorizontal()
        assign_layout.Add(forms.Label(Text="Modifier:"))
        self.face_mod_dropdown = forms.DropDown()
        self.face_mod_dropdown.Items.Add("<Unchanged>")
        self.face_mod_dropdown.SelectedIndex = 0
        assign_layout.Add(self.face_mod_dropdown, xscale=True)
        assign_layout.EndHorizontal()
        btn_row = forms.DynamicLayout()
        btn_row.BeginHorizontal()
        btn_set_selected = forms.Button(Text="Set for Selected")
        btn_set_selected.Click += self._on_set_selected_faces
        btn_row.Add(btn_set_selected)
        self.btn_set_all_faces = forms.Button(Text="Set for All Filtered ({})".format(len(self.filtered_faces)))
        self.btn_set_all_faces.Click += self._on_set_all_faces
        btn_row.Add(self.btn_set_all_faces)
        btn_row.Add(None, xscale=True)
        btn_row.EndHorizontal()
        assign_layout.Add(btn_row)
        assign_group.Content = assign_layout
        layout.Add(assign_group)
        return layout
    
    def _create_aperture_panel(self):
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(5, 5)
        layout.Padding = drawing.Padding(5)
        
        filter_layout = forms.DynamicLayout()
        filter_layout.BeginHorizontal()
        filter_layout.Add(forms.Label(Text="Room:"))
        self.ap_room_filter = forms.DropDown()
        rooms = ["<All>"] + sorted(set(a['room'] for a in self.aperture_list))
        for r in rooms:
            self.ap_room_filter.Items.Add(r)
        self.ap_room_filter.SelectedIndex = 0
        filter_layout.Add(self.ap_room_filter)
        filter_layout.Add(forms.Label(Text="  BC:"))
        self.ap_bc_filter = forms.DropDown()
        for bc in ["<All>", "Outdoors", "Surface"]:
            self.ap_bc_filter.Items.Add(bc)
        self.ap_bc_filter.SelectedIndex = 0
        filter_layout.Add(self.ap_bc_filter)
        btn_filter = forms.Button(Text="Filter")
        btn_filter.Click += self._on_filter_apertures
        filter_layout.Add(btn_filter)
        filter_layout.Add(None, xscale=True)
        filter_layout.EndHorizontal()
        layout.Add(filter_layout)
        
        self.ap_grid = forms.GridView()
        self.ap_grid.Height = 200
        self.ap_grid.AllowMultipleSelection = True
        
        # Column: Modified marker
        col_mod = forms.GridColumn()
        col_mod.HeaderText = "M"
        col_mod.DataCell = forms.TextBoxCell(0)
        col_mod.Width = 25
        self.ap_grid.Columns.Add(col_mod)
        
        # Column: Geometry marker
        col_geo = forms.GridColumn()
        col_geo.HeaderText = "G"
        col_geo.DataCell = forms.TextBoxCell(1)
        col_geo.Width = 25
        self.ap_grid.Columns.Add(col_geo)
        
        # Column: Room
        col_room = forms.GridColumn()
        col_room.HeaderText = "Room"
        col_room.DataCell = forms.TextBoxCell(2)
        col_room.Width = 150
        self.ap_grid.Columns.Add(col_room)
        
        # Column: Parent Face
        col_parent = forms.GridColumn()
        col_parent.HeaderText = "Parent"
        col_parent.DataCell = forms.TextBoxCell(3)
        col_parent.Width = 100
        self.ap_grid.Columns.Add(col_parent)
        
        # Column: BC
        col_bc = forms.GridColumn()
        col_bc.HeaderText = "BC"
        col_bc.DataCell = forms.TextBoxCell(4)
        col_bc.Width = 60
        self.ap_grid.Columns.Add(col_bc)
        
        # Column: Area
        col_area = forms.GridColumn()
        col_area.HeaderText = "Area"
        col_area.DataCell = forms.TextBoxCell(5)
        col_area.Width = 60
        self.ap_grid.Columns.Add(col_area)
        
        # Column: Construction
        col_constr = forms.GridColumn()
        col_constr.HeaderText = "Construction"
        col_constr.DataCell = forms.TextBoxCell(6)
        col_constr.Width = 150
        self.ap_grid.Columns.Add(col_constr)
        
        self._refresh_ap_grid()
        self.ap_grid.SelectionChanged += self._on_ap_selection_changed
        layout.Add(self.ap_grid, yscale=True)
        
        assign_group = forms.GroupBox(Text="Assign Properties")
        assign_layout = forms.DynamicLayout()
        assign_layout.Spacing = drawing.Size(5, 5)
        assign_layout.Padding = drawing.Padding(5)
        self.ap_selection_info = forms.Label(Text="No selection")
        assign_layout.Add(self.ap_selection_info)
        assign_layout.BeginHorizontal()
        assign_layout.Add(forms.Label(Text="Construction:"))
        self.ap_constr_dropdown = forms.DropDown()
        self.ap_constr_dropdown.Items.Add("<Unchanged>")
        self.ap_constr_dropdown.SelectedIndex = 0
        assign_layout.Add(self.ap_constr_dropdown, xscale=True)
        assign_layout.EndHorizontal()
        assign_layout.BeginHorizontal()
        assign_layout.Add(forms.Label(Text="Modifier:"))
        self.ap_mod_dropdown = forms.DropDown()
        self.ap_mod_dropdown.Items.Add("<Unchanged>")
        self.ap_mod_dropdown.SelectedIndex = 0
        assign_layout.Add(self.ap_mod_dropdown, xscale=True)
        assign_layout.EndHorizontal()
        btn_row = forms.DynamicLayout()
        btn_row.BeginHorizontal()
        btn_set_selected = forms.Button(Text="Set for Selected")
        btn_set_selected.Click += self._on_set_selected_apertures
        btn_row.Add(btn_set_selected)
        self.btn_set_all_ap = forms.Button(Text="Set for All Filtered ({})".format(len(self.filtered_apertures)))
        self.btn_set_all_ap.Click += self._on_set_all_apertures
        btn_row.Add(self.btn_set_all_ap)
        btn_row.Add(None, xscale=True)
        btn_row.EndHorizontal()
        assign_layout.Add(btn_row)
        assign_group.Content = assign_layout
        layout.Add(assign_group)
        return layout
    
    def _create_door_panel(self):
        """NEW: Create the Doors tab panel for door selection and modification"""
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(5, 5)
        layout.Padding = drawing.Padding(5)
        
        # Info about doors
        glass_doors = len([d for d in self.door_list if d.get('is_glass', False)])
        opaque_doors = len(self.door_list) - glass_doors
        layout.Add(forms.Label(Text="Total: {} doors ({} opaque, {} glass)".format(
            len(self.door_list), opaque_doors, glass_doors)))
        
        # Filter controls
        filter_layout = forms.DynamicLayout()
        filter_layout.BeginHorizontal()
        filter_layout.Add(forms.Label(Text="Room:"))
        self.door_room_filter = forms.DropDown()
        rooms = ["<All>"] + sorted(set(d['room'] for d in self.door_list))
        for r in rooms:
            self.door_room_filter.Items.Add(r)
        self.door_room_filter.SelectedIndex = 0
        filter_layout.Add(self.door_room_filter)
        filter_layout.Add(forms.Label(Text="  BC:"))
        self.door_bc_filter = forms.DropDown()
        for bc in ["<All>", "Outdoors", "Surface"]:
            self.door_bc_filter.Items.Add(bc)
        self.door_bc_filter.SelectedIndex = 0
        filter_layout.Add(self.door_bc_filter)
        filter_layout.Add(forms.Label(Text="  Type:"))
        self.door_type_filter = forms.DropDown()
        for dt in ["<All>", "Opaque", "Glass"]:
            self.door_type_filter.Items.Add(dt)
        self.door_type_filter.SelectedIndex = 0
        filter_layout.Add(self.door_type_filter)
        btn_filter = forms.Button(Text="Filter")
        btn_filter.Click += self._on_filter_doors
        filter_layout.Add(btn_filter)
        filter_layout.Add(None, xscale=True)
        filter_layout.EndHorizontal()
        layout.Add(filter_layout)
        
        # Door grid
        self.door_grid = forms.GridView()
        self.door_grid.Height = 200
        self.door_grid.AllowMultipleSelection = True
        
        # Column: Modified marker
        col_mod = forms.GridColumn()
        col_mod.HeaderText = "M"
        col_mod.DataCell = forms.TextBoxCell(0)
        col_mod.Width = 25
        self.door_grid.Columns.Add(col_mod)
        
        # Column: Geometry marker
        col_geo = forms.GridColumn()
        col_geo.HeaderText = "G"
        col_geo.DataCell = forms.TextBoxCell(1)
        col_geo.Width = 25
        self.door_grid.Columns.Add(col_geo)
        
        # Column: Type (Opaque/Glass)
        col_type = forms.GridColumn()
        col_type.HeaderText = "Type"
        col_type.DataCell = forms.TextBoxCell(2)
        col_type.Width = 55
        self.door_grid.Columns.Add(col_type)
        
        # Column: Room
        col_room = forms.GridColumn()
        col_room.HeaderText = "Room"
        col_room.DataCell = forms.TextBoxCell(3)
        col_room.Width = 150
        self.door_grid.Columns.Add(col_room)
        
        # Column: BC
        col_bc = forms.GridColumn()
        col_bc.HeaderText = "BC"
        col_bc.DataCell = forms.TextBoxCell(4)
        col_bc.Width = 60
        self.door_grid.Columns.Add(col_bc)
        
        # Column: Area
        col_area = forms.GridColumn()
        col_area.HeaderText = "Area"
        col_area.DataCell = forms.TextBoxCell(5)
        col_area.Width = 60
        self.door_grid.Columns.Add(col_area)
        
        # Column: Construction
        col_constr = forms.GridColumn()
        col_constr.HeaderText = "Construction"
        col_constr.DataCell = forms.TextBoxCell(6)
        col_constr.Width = 150
        self.door_grid.Columns.Add(col_constr)
        
        self._refresh_door_grid()
        self.door_grid.SelectionChanged += self._on_door_selection_changed
        layout.Add(self.door_grid, yscale=True)
        
        # Assign properties group
        assign_group = forms.GroupBox(Text="Assign Properties")
        assign_layout = forms.DynamicLayout()
        assign_layout.Spacing = drawing.Size(5, 5)
        assign_layout.Padding = drawing.Padding(5)
        self.door_selection_info = forms.Label(Text="No selection")
        assign_layout.Add(self.door_selection_info)
        
        # Construction dropdown
        assign_layout.BeginHorizontal()
        assign_layout.Add(forms.Label(Text="Construction:"))
        self.door_constr_dropdown = forms.DropDown()
        self.door_constr_dropdown.Items.Add("<Unchanged>")
        self.door_constr_dropdown.SelectedIndex = 0
        assign_layout.Add(self.door_constr_dropdown, xscale=True)
        assign_layout.EndHorizontal()
        
        # Modifier dropdown
        assign_layout.BeginHorizontal()
        assign_layout.Add(forms.Label(Text="Modifier:"))
        self.door_mod_dropdown = forms.DropDown()
        self.door_mod_dropdown.Items.Add("<Unchanged>")
        self.door_mod_dropdown.SelectedIndex = 0
        assign_layout.Add(self.door_mod_dropdown, xscale=True)
        assign_layout.EndHorizontal()
        
        # Action buttons
        btn_row = forms.DynamicLayout()
        btn_row.BeginHorizontal()
        btn_set_selected = forms.Button(Text="Set for Selected")
        btn_set_selected.Click += self._on_set_selected_doors
        btn_row.Add(btn_set_selected)
        self.btn_set_all_doors = forms.Button(Text="Set for All Filtered ({})".format(len(self.filtered_doors)))
        self.btn_set_all_doors.Click += self._on_set_all_doors
        btn_row.Add(self.btn_set_all_doors)
        btn_row.Add(None, xscale=True)
        btn_row.EndHorizontal()
        assign_layout.Add(btn_row)
        
        assign_group.Content = assign_layout
        layout.Add(assign_group)
        
        return layout
    
    def _create_shading_panel(self):
        """Create the Shading tab panel with scrolling support"""
        # Inner layout for all shading content
        inner_layout = forms.DynamicLayout()
        inner_layout.Spacing = drawing.Size(5, 5)
        inner_layout.Padding = drawing.Padding(5)
        
        # Count exterior elements
        ext_walls = [f for f in self.face_list if f['bc'] == 'Outdoors' and 'Wall' in f['type']]
        ext_apertures = [a for a in self.aperture_list if a['bc'] == 'Outdoors']
        ext_doors = [d for d in self.door_list if d['bc'] == 'Outdoors']
        
        info_text = "Exterior: {} walls, {} apertures, {} doors".format(
            len(ext_walls), len(ext_apertures), len(ext_doors))
        inner_layout.Add(forms.Label(Text=info_text))
        
        # ===== Wall Shading Section =====
        wall_group = forms.GroupBox(Text="Wall Shading ({} exterior walls)".format(len(ext_walls)))
        wall_layout = forms.DynamicLayout()
        wall_layout.Spacing = drawing.Size(5, 5)
        wall_layout.Padding = drawing.Padding(5)
        
        wall_filter_layout = forms.DynamicLayout()
        wall_filter_layout.BeginHorizontal()
        wall_filter_layout.Add(forms.Label(Text="Room:"))
        self.shade_wall_room_filter = forms.DropDown()
        rooms = ["<All>"] + sorted(set(f['room'] for f in ext_walls))
        for r in rooms:
            self.shade_wall_room_filter.Items.Add(r)
        self.shade_wall_room_filter.SelectedIndex = 0
        wall_filter_layout.Add(self.shade_wall_room_filter)
        btn_filter_walls = forms.Button(Text="Filter")
        btn_filter_walls.Click += self._on_filter_shade_walls
        wall_filter_layout.Add(btn_filter_walls)
        wall_filter_layout.Add(None, xscale=True)
        wall_filter_layout.EndHorizontal()
        wall_layout.Add(wall_filter_layout)
        
        self.shade_wall_grid = forms.GridView()
        self.shade_wall_grid.Height = 100
        self.shade_wall_grid.AllowMultipleSelection = True
        
        # Column: Shaded marker
        col_shaded = forms.GridColumn()
        col_shaded.HeaderText = "S"
        col_shaded.DataCell = forms.TextBoxCell(0)
        col_shaded.Width = 25
        self.shade_wall_grid.Columns.Add(col_shaded)
        
        # Column: Type
        col_type = forms.GridColumn()
        col_type.HeaderText = "Type"
        col_type.DataCell = forms.TextBoxCell(1)
        col_type.Width = 60
        self.shade_wall_grid.Columns.Add(col_type)
        
        # Column: Room
        col_room = forms.GridColumn()
        col_room.HeaderText = "Room"
        col_room.DataCell = forms.TextBoxCell(2)
        col_room.Width = 150
        self.shade_wall_grid.Columns.Add(col_room)
        
        # Column: Area
        col_area = forms.GridColumn()
        col_area.HeaderText = "Area"
        col_area.DataCell = forms.TextBoxCell(3)
        col_area.Width = 60
        self.shade_wall_grid.Columns.Add(col_area)
        
        self.filtered_shade_walls = list(ext_walls)
        self.shade_wall_grid.SelectionChanged += self._on_shade_selection_changed  # Preview support
        self._refresh_shade_wall_grid()
        wall_layout.Add(self.shade_wall_grid)
        
        wall_param_layout = forms.DynamicLayout()
        wall_param_layout.BeginHorizontal()
        self.chk_wall_overhang = forms.CheckBox(Text="Overhang")
        wall_param_layout.Add(self.chk_wall_overhang)
        wall_param_layout.Add(forms.Label(Text="Depth:"))
        self.num_wall_oh_depth = forms.NumericUpDown()
        self.num_wall_oh_depth.MinValue = 0.1
        self.num_wall_oh_depth.MaxValue = 5.0
        self.num_wall_oh_depth.DecimalPlaces = 2
        self.num_wall_oh_depth.Value = 0.5
        self.num_wall_oh_depth.Width = 60
        wall_param_layout.Add(self.num_wall_oh_depth)
        wall_param_layout.Add(forms.Label(Text="Angle:"))
        self.num_wall_oh_angle = forms.NumericUpDown()
        self.num_wall_oh_angle.MinValue = 0
        self.num_wall_oh_angle.MaxValue = 90
        self.num_wall_oh_angle.Value = 0
        self.num_wall_oh_angle.Width = 50
        wall_param_layout.Add(self.num_wall_oh_angle)
        wall_param_layout.EndHorizontal()
        wall_layout.Add(wall_param_layout)
        
        btn_apply_wall = forms.Button(Text="Set for Selected Walls")
        btn_apply_wall.Click += self._on_apply_wall_shading
        wall_layout.Add(btn_apply_wall)
        
        wall_group.Content = wall_layout
        inner_layout.Add(wall_group)
        
        # ===== Aperture Shading Section =====
        ap_group = forms.GroupBox(Text="Aperture Shading ({} exterior)".format(len(ext_apertures)))
        ap_layout = forms.DynamicLayout()
        ap_layout.Spacing = drawing.Size(5, 5)
        ap_layout.Padding = drawing.Padding(5)
        
        ap_filter_layout = forms.DynamicLayout()
        ap_filter_layout.BeginHorizontal()
        ap_filter_layout.Add(forms.Label(Text="Room:"))
        self.shade_ap_room_filter = forms.DropDown()
        ap_rooms = ["<All>"] + sorted(set(a['room'] for a in ext_apertures))
        for r in ap_rooms:
            self.shade_ap_room_filter.Items.Add(r)
        self.shade_ap_room_filter.SelectedIndex = 0
        ap_filter_layout.Add(self.shade_ap_room_filter)
        btn_filter_ap = forms.Button(Text="Filter")
        btn_filter_ap.Click += self._on_filter_shade_apertures
        ap_filter_layout.Add(btn_filter_ap)
        ap_filter_layout.Add(None, xscale=True)
        ap_filter_layout.EndHorizontal()
        ap_layout.Add(ap_filter_layout)
        
        self.shade_ap_grid = forms.GridView()
        self.shade_ap_grid.Height = 100
        self.shade_ap_grid.AllowMultipleSelection = True
        
        # Column: Shaded marker
        col_shaded = forms.GridColumn()
        col_shaded.HeaderText = "S"
        col_shaded.DataCell = forms.TextBoxCell(0)
        col_shaded.Width = 25
        self.shade_ap_grid.Columns.Add(col_shaded)
        
        # Column: Room
        col_room = forms.GridColumn()
        col_room.HeaderText = "Room"
        col_room.DataCell = forms.TextBoxCell(1)
        col_room.Width = 150
        self.shade_ap_grid.Columns.Add(col_room)
        
        # Column: Parent
        col_parent = forms.GridColumn()
        col_parent.HeaderText = "Parent Face"
        col_parent.DataCell = forms.TextBoxCell(2)
        col_parent.Width = 100
        self.shade_ap_grid.Columns.Add(col_parent)
        
        # Column: Area
        col_area = forms.GridColumn()
        col_area.HeaderText = "Area"
        col_area.DataCell = forms.TextBoxCell(3)
        col_area.Width = 60
        self.shade_ap_grid.Columns.Add(col_area)
        
        self.filtered_shade_apertures = list(ext_apertures)
        self.shade_ap_grid.SelectionChanged += self._on_shade_selection_changed  # Preview support
        self._refresh_shade_ap_grid()
        ap_layout.Add(self.shade_ap_grid)
        
        ap_opt_layout = forms.DynamicLayout()
        ap_opt_layout.BeginHorizontal()
        self.chk_ap_overhang = forms.CheckBox(Text="Overhang")
        ap_opt_layout.Add(self.chk_ap_overhang)
        ap_opt_layout.Add(forms.Label(Text="Dp:"))
        self.num_ap_oh_depth = forms.NumericUpDown()
        self.num_ap_oh_depth.MinValue = 0.1
        self.num_ap_oh_depth.MaxValue = 5.0
        self.num_ap_oh_depth.DecimalPlaces = 2
        self.num_ap_oh_depth.Value = 0.5
        self.num_ap_oh_depth.Width = 50
        ap_opt_layout.Add(self.num_ap_oh_depth)
        ap_opt_layout.Add(forms.Label(Text="Ang:"))
        self.num_ap_oh_angle = forms.NumericUpDown()
        self.num_ap_oh_angle.MinValue = 0
        self.num_ap_oh_angle.MaxValue = 90
        self.num_ap_oh_angle.Value = 0
        self.num_ap_oh_angle.Width = 40
        ap_opt_layout.Add(self.num_ap_oh_angle)
        ap_opt_layout.EndHorizontal()
        ap_layout.Add(ap_opt_layout)
        
        ap_opt2_layout = forms.DynamicLayout()
        ap_opt2_layout.BeginHorizontal()
        self.chk_ap_fins = forms.CheckBox(Text="Fins")
        ap_opt2_layout.Add(self.chk_ap_fins)
        ap_opt2_layout.Add(forms.Label(Text="Dp:"))
        self.num_ap_fin_depth = forms.NumericUpDown()
        self.num_ap_fin_depth.MinValue = 0.1
        self.num_ap_fin_depth.MaxValue = 3.0
        self.num_ap_fin_depth.DecimalPlaces = 2
        self.num_ap_fin_depth.Value = 0.3
        self.num_ap_fin_depth.Width = 50
        ap_opt2_layout.Add(self.num_ap_fin_depth)
        ap_opt2_layout.Add(forms.Label(Text="Ang:"))
        self.num_ap_fin_angle = forms.NumericUpDown()
        self.num_ap_fin_angle.MinValue = 0
        self.num_ap_fin_angle.MaxValue = 90
        self.num_ap_fin_angle.Value = 0
        self.num_ap_fin_angle.Width = 40
        ap_opt2_layout.Add(self.num_ap_fin_angle)
        ap_opt2_layout.EndHorizontal()
        ap_layout.Add(ap_opt2_layout)
        
        ap_opt3_layout = forms.DynamicLayout()
        ap_opt3_layout.BeginHorizontal()
        self.chk_ap_louvers = forms.CheckBox(Text="Louvers")
        ap_opt3_layout.Add(self.chk_ap_louvers)
        ap_opt3_layout.Add(forms.Label(Text="Cnt:"))
        self.num_ap_louver_count = forms.NumericUpDown()
        self.num_ap_louver_count.MinValue = 1
        self.num_ap_louver_count.MaxValue = 20
        self.num_ap_louver_count.Value = 5
        self.num_ap_louver_count.Width = 40
        ap_opt3_layout.Add(self.num_ap_louver_count)
        ap_opt3_layout.Add(forms.Label(Text="Dp:"))
        self.num_ap_louver_depth = forms.NumericUpDown()
        self.num_ap_louver_depth.MinValue = 0.05
        self.num_ap_louver_depth.MaxValue = 1.0
        self.num_ap_louver_depth.DecimalPlaces = 2
        self.num_ap_louver_depth.Value = 0.1
        self.num_ap_louver_depth.Width = 45
        ap_opt3_layout.Add(self.num_ap_louver_depth)
        ap_opt3_layout.Add(forms.Label(Text="Off:"))
        self.num_ap_louver_offset = forms.NumericUpDown()
        self.num_ap_louver_offset.MinValue = 0.0
        self.num_ap_louver_offset.MaxValue = 1.0
        self.num_ap_louver_offset.DecimalPlaces = 2
        self.num_ap_louver_offset.Value = 0.05
        self.num_ap_louver_offset.Width = 45
        ap_opt3_layout.Add(self.num_ap_louver_offset)
        ap_opt3_layout.Add(forms.Label(Text="Ang:"))
        self.num_ap_louver_angle = forms.NumericUpDown()
        self.num_ap_louver_angle.MinValue = 0
        self.num_ap_louver_angle.MaxValue = 89
        self.num_ap_louver_angle.Value = 45
        self.num_ap_louver_angle.Width = 40
        ap_opt3_layout.Add(self.num_ap_louver_angle)
        ap_opt3_layout.EndHorizontal()
        ap_layout.Add(ap_opt3_layout)
        
        btn_apply_ap = forms.Button(Text="Set for Selected Apertures")
        btn_apply_ap.Click += self._on_apply_aperture_shading
        ap_layout.Add(btn_apply_ap)
        
        ap_group.Content = ap_layout
        inner_layout.Add(ap_group)
        
        # ===== Door Shading Section =====
        door_group = forms.GroupBox(Text="Door Shading ({} exterior)".format(len(ext_doors)))
        door_layout = forms.DynamicLayout()
        door_layout.Spacing = drawing.Size(5, 5)
        door_layout.Padding = drawing.Padding(5)
        
        self.shade_door_grid = forms.GridView()
        self.shade_door_grid.Height = 80
        self.shade_door_grid.AllowMultipleSelection = True
        
        # Column: Shaded marker
        col_shaded = forms.GridColumn()
        col_shaded.HeaderText = "S"
        col_shaded.DataCell = forms.TextBoxCell(0)
        col_shaded.Width = 25
        self.shade_door_grid.Columns.Add(col_shaded)
        
        # Column: Type
        col_type = forms.GridColumn()
        col_type.HeaderText = "Type"
        col_type.DataCell = forms.TextBoxCell(1)
        col_type.Width = 55
        self.shade_door_grid.Columns.Add(col_type)
        
        # Column: Room
        col_room = forms.GridColumn()
        col_room.HeaderText = "Room"
        col_room.DataCell = forms.TextBoxCell(2)
        col_room.Width = 150
        self.shade_door_grid.Columns.Add(col_room)
        
        # Column: Area
        col_area = forms.GridColumn()
        col_area.HeaderText = "Area"
        col_area.DataCell = forms.TextBoxCell(3)
        col_area.Width = 60
        self.shade_door_grid.Columns.Add(col_area)
        
        self.filtered_shade_doors = list(ext_doors)
        self.shade_door_grid.SelectionChanged += self._on_shade_selection_changed  # Preview support
        self._refresh_shade_door_grid()
        door_layout.Add(self.shade_door_grid)
        
        door_param_layout = forms.DynamicLayout()
        door_param_layout.BeginHorizontal()
        self.chk_door_canopy = forms.CheckBox(Text="Canopy")
        self.chk_door_canopy.Checked = True
        door_param_layout.Add(self.chk_door_canopy)
        door_param_layout.Add(forms.Label(Text="Depth:"))
        self.num_door_canopy_depth = forms.NumericUpDown()
        self.num_door_canopy_depth.MinValue = 0.3
        self.num_door_canopy_depth.MaxValue = 5.0
        self.num_door_canopy_depth.DecimalPlaces = 2
        self.num_door_canopy_depth.Value = 1.0
        self.num_door_canopy_depth.Width = 60
        door_param_layout.Add(self.num_door_canopy_depth)
        door_param_layout.EndHorizontal()
        door_layout.Add(door_param_layout)
        
        btn_apply_door = forms.Button(Text="Set for Selected Doors")
        btn_apply_door.Click += self._on_apply_door_shading
        door_layout.Add(btn_apply_door)
        
        door_group.Content = door_layout
        inner_layout.Add(door_group)
        
        self.shade_status = forms.Label(Text="")
        inner_layout.Add(self.shade_status)
        
        # Wrap in scrollable container
        scrollable = forms.Scrollable()
        scrollable.Content = inner_layout
        scrollable.ExpandContentWidth = True
        scrollable.ExpandContentHeight = False
        
        return scrollable
    
    def _create_hvac_panel(self):
        """Create the HVAC Systems panel with system grouping support"""
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(8, 8)
        layout.Padding = drawing.Padding(5)
        
        # Info section
        info_group = forms.GroupBox(Text="HVAC System Grouping")
        info_layout = forms.DynamicLayout()
        info_layout.Padding = drawing.Padding(8)
        info_layout.AddRow(forms.Label(Text="Central systems (VAV, DOAS, VRF) should be shared by multiple rooms."))
        info_layout.AddRow(forms.Label(Text="Zone-level systems (PSZ, Baseboard) can be per-room or shared."))
        info_group.Content = info_layout
        layout.Add(info_group)
        
        # Main 3-column layout
        columns = forms.DynamicLayout()
        columns.BeginHorizontal()
        
        # LEFT: Room Selection
        room_group = forms.GroupBox(Text="Room Selection ({} rooms)".format(len(self.room_list)))
        room_layout = forms.DynamicLayout()
        room_layout.Spacing = drawing.Size(5, 5)
        room_layout.Padding = drawing.Padding(5)
        
        filter_row = forms.DynamicLayout()
        filter_row.BeginHorizontal()
        filter_row.Add(forms.Label(Text="Show:"))
        self.dd_hvac_filter = forms.DropDown()
        self.dd_hvac_filter.Items.Add("All Rooms")
        self.dd_hvac_filter.Items.Add("Unassigned Only")
        self.dd_hvac_filter.Items.Add("Assigned Only")
        self.dd_hvac_filter.SelectedIndex = 0
        self.dd_hvac_filter.SelectedIndexChanged += self._on_hvac_filter_changed
        filter_row.Add(self.dd_hvac_filter)
        filter_row.EndHorizontal()
        room_layout.Add(filter_row)
        
        self.hvac_room_grid = forms.GridView()
        self.hvac_room_grid.Height = 250
        self.hvac_room_grid.AllowMultipleSelection = True
        
        col = forms.GridColumn()
        col.HeaderText = "Room"
        col.DataCell = forms.TextBoxCell(0)
        col.Width = 140
        self.hvac_room_grid.Columns.Add(col)
        
        col2 = forms.GridColumn()
        col2.HeaderText = "Area"
        col2.DataCell = forms.TextBoxCell(1)
        col2.Width = 50
        self.hvac_room_grid.Columns.Add(col2)
        
        col3 = forms.GridColumn()
        col3.HeaderText = "System"
        col3.DataCell = forms.TextBoxCell(2)
        col3.Width = 100
        self.hvac_room_grid.Columns.Add(col3)
        
        self.filtered_hvac_rooms = list(self.room_list)
        self.hvac_room_grid.SelectionChanged += self._on_hvac_room_selection_changed
        room_layout.Add(self.hvac_room_grid, yscale=True)
        
        self.lbl_hvac_room_selection = forms.Label(Text="Select rooms to assign")
        room_layout.Add(self.lbl_hvac_room_selection)
        
        room_group.Content = room_layout
        columns.Add(room_group, xscale=True)
        
        # CENTER: Existing Systems List
        systems_group = forms.GroupBox(Text="Defined Systems")
        systems_layout = forms.DynamicLayout()
        systems_layout.Spacing = drawing.Size(5, 5)
        systems_layout.Padding = drawing.Padding(5)
        
        self.hvac_systems_grid = forms.GridView()
        self.hvac_systems_grid.Height = 180
        self.hvac_systems_grid.AllowMultipleSelection = False
        
        sys_col1 = forms.GridColumn()
        sys_col1.HeaderText = "System Name"
        sys_col1.DataCell = forms.TextBoxCell(0)
        sys_col1.Width = 120
        self.hvac_systems_grid.Columns.Add(sys_col1)
        
        sys_col2 = forms.GridColumn()
        sys_col2.HeaderText = "Type"
        sys_col2.DataCell = forms.TextBoxCell(1)
        sys_col2.Width = 80
        self.hvac_systems_grid.Columns.Add(sys_col2)
        
        sys_col3 = forms.GridColumn()
        sys_col3.HeaderText = "Rooms"
        sys_col3.DataCell = forms.TextBoxCell(2)
        sys_col3.Width = 50
        self.hvac_systems_grid.Columns.Add(sys_col3)
        
        self.hvac_systems_grid.SelectionChanged += self._on_hvac_system_selected
        systems_layout.Add(self.hvac_systems_grid, yscale=True)
        
        # Buttons for system management
        sys_btn_row = forms.DynamicLayout()
        sys_btn_row.BeginHorizontal()
        btn_load_system = forms.Button(Text="Load Selected")
        btn_load_system.Click += self._on_hvac_load_system
        sys_btn_row.Add(btn_load_system)
        btn_delete_system = forms.Button(Text="Delete")
        btn_delete_system.Click += self._on_hvac_delete_system
        sys_btn_row.Add(btn_delete_system)
        sys_btn_row.EndHorizontal()
        systems_layout.Add(sys_btn_row)
        
        systems_group.Content = systems_layout
        columns.Add(systems_group, xscale=True)
        
        # RIGHT: HVAC Configuration
        config_group = forms.GroupBox(Text="System Configuration")
        config_layout = forms.DynamicLayout()
        config_layout.Spacing = drawing.Size(5, 5)
        config_layout.Padding = drawing.Padding(8)
        
        # System Name (key field!)
        config_layout.AddRow(forms.Label(Text="System Name:"))
        self.txt_hvac_system_name = forms.TextBox()
        self.txt_hvac_system_name.Text = "System_1"
        config_layout.AddRow(self.txt_hvac_system_name)
        
        config_layout.AddSpace()
        
        config_layout.AddRow(forms.Label(Text="System Category:"))
        self.dd_hvac_category = forms.DropDown()
        for cat in HVAC_CATEGORIES.keys():
            self.dd_hvac_category.Items.Add(cat)
        self.dd_hvac_category.SelectedIndex = 0
        self.dd_hvac_category.SelectedIndexChanged += self._on_hvac_category_changed
        config_layout.AddRow(self.dd_hvac_category)
        
        self.lbl_hvac_cat_desc = forms.Label(Text="")
        self.lbl_hvac_cat_desc.TextColor = drawing.Color.FromArgb(100, 100, 100)
        config_layout.AddRow(self.lbl_hvac_cat_desc)
        
        config_layout.AddRow(forms.Label(Text="Equipment Type:"))
        self.dd_hvac_equipment = forms.DropDown()
        config_layout.AddRow(self.dd_hvac_equipment)
        
        config_layout.AddRow(forms.Label(Text="Vintage:"))
        self.dd_hvac_vintage = forms.DropDown()
        for v in HVAC_VINTAGES:
            self.dd_hvac_vintage.Items.Add(v)
        self.dd_hvac_vintage.SelectedIndex = 0
        config_layout.AddRow(self.dd_hvac_vintage)
        
        config_layout.AddRow(forms.Label(Text="Economizer:"))
        self.dd_hvac_economizer = forms.DropDown()
        for e in HVAC_ECONOMIZER_TYPES:
            self.dd_hvac_economizer.Items.Add(e)
        self.dd_hvac_economizer.SelectedIndex = 0
        config_layout.AddRow(self.dd_hvac_economizer)
        
        hr_row = forms.DynamicLayout()
        hr_row.BeginHorizontal()
        hr_row.Add(forms.Label(Text="Sensible HR:"))
        self.num_hvac_sensible = forms.NumericStepper()
        self.num_hvac_sensible.MinValue = 0.0
        self.num_hvac_sensible.MaxValue = 0.95
        self.num_hvac_sensible.DecimalPlaces = 2
        self.num_hvac_sensible.Increment = 0.05
        self.num_hvac_sensible.Value = 0.0
        self.num_hvac_sensible.Width = 60
        hr_row.Add(self.num_hvac_sensible)
        hr_row.EndHorizontal()
        config_layout.Add(hr_row)
        
        hr_row2 = forms.DynamicLayout()
        hr_row2.BeginHorizontal()
        hr_row2.Add(forms.Label(Text="Latent HR:"))
        self.num_hvac_latent = forms.NumericStepper()
        self.num_hvac_latent.MinValue = 0.0
        self.num_hvac_latent.MaxValue = 0.95
        self.num_hvac_latent.DecimalPlaces = 2
        self.num_hvac_latent.Increment = 0.05
        self.num_hvac_latent.Value = 0.0
        self.num_hvac_latent.Width = 60
        hr_row2.Add(self.num_hvac_latent)
        hr_row2.EndHorizontal()
        config_layout.Add(hr_row2)
        
        self.chk_hvac_dcv = forms.CheckBox(Text="Demand Controlled Vent.")
        config_layout.AddRow(self.chk_hvac_dcv)
        
        config_layout.AddSpace()
        
        # Action buttons
        btn_assign = forms.Button(Text="Assign Rooms to System")
        btn_assign.Click += self._on_hvac_assign_rooms
        config_layout.AddRow(btn_assign)
        
        btn_unassign = forms.Button(Text="Unassign Selected Rooms")
        btn_unassign.Click += self._on_hvac_unassign_rooms
        config_layout.AddRow(btn_unassign)
        
        config_group.Content = config_layout
        columns.Add(config_group, xscale=True)
        
        columns.EndHorizontal()
        layout.Add(columns, yscale=True)
        
        # Status
        self.hvac_status = forms.Label(Text="")
        layout.Add(self.hvac_status)
        
        # Initialize
        self._update_hvac_equipment_dropdown()
        self._refresh_hvac_room_grid()
        self._refresh_hvac_systems_grid()
        self._suggest_system_name()
        
        return layout
    
    def _refresh_hvac_room_grid(self):
        """Refresh the HVAC room grid based on filter"""
        filter_idx = self.dd_hvac_filter.SelectedIndex
        
        rows = []
        for r in self.filtered_hvac_rooms:
            system_name = self.room_hvac_assignments.get(r['id'], '<none>')
            rows.append([r['name'][:20], "{:.0f}".format(r['area']), system_name[:12]])
        self.hvac_room_grid.DataStore = rows
    
    def _refresh_hvac_systems_grid(self):
        """Refresh the systems list grid"""
        rows = []
        for sys_name, config in self.hvac_systems.items():
            # Count rooms assigned to this system
            room_count = sum(1 for r_id, s_name in self.room_hvac_assignments.items() if s_name == sys_name)
            sys_type = config.get('class', 'Unknown')[:10]
            rows.append([sys_name[:15], sys_type, str(room_count)])
        self.hvac_systems_grid.DataStore = rows
    
    def _suggest_system_name(self):
        """Suggest a unique system name"""
        base = "System"
        counter = 1
        while True:
            name = "{}_{}".format(base, counter)
            if name not in self.hvac_systems:
                self.txt_hvac_system_name.Text = name
                return
            counter += 1
            if counter > 100:
                self.txt_hvac_system_name.Text = "System_New"
                return
    
    def _update_hvac_equipment_dropdown(self):
        """Update equipment dropdown based on selected category"""
        try:
            cat_name = str(self.dd_hvac_category.SelectedValue)
            cat_info = HVAC_CATEGORIES.get(cat_name, {})
            
            self.lbl_hvac_cat_desc.Text = cat_info.get("description", "")
            
            self.dd_hvac_equipment.Items.Clear()
            for eq in cat_info.get("equipment_types", []):
                self.dd_hvac_equipment.Items.Add(eq)
            if self.dd_hvac_equipment.Items.Count > 0:
                self.dd_hvac_equipment.SelectedIndex = 0
        except:
            pass
    
    def _on_hvac_filter_changed(self, sender, e):
        """Handle HVAC room filter change"""
        filter_idx = self.dd_hvac_filter.SelectedIndex
        if filter_idx == 0:  # All
            self.filtered_hvac_rooms = list(self.room_list)
        elif filter_idx == 1:  # Unassigned Only
            self.filtered_hvac_rooms = [r for r in self.room_list if r['id'] not in self.room_hvac_assignments]
        else:  # Assigned Only
            self.filtered_hvac_rooms = [r for r in self.room_list if r['id'] in self.room_hvac_assignments]
        self._refresh_hvac_room_grid()
    
    def _on_hvac_category_changed(self, sender, e):
        """Handle HVAC category change"""
        self._update_hvac_equipment_dropdown()
    
    def _on_hvac_room_selection_changed(self, sender, e):
        """Handle HVAC room selection change - update preview and selection label"""
        selected_indices = list(self.hvac_room_grid.SelectedRows)
        if not selected_indices:
            self.lbl_hvac_room_selection.Text = "Select rooms to assign"
        else:
            total_area = 0
            for idx in selected_indices:
                if idx < len(self.filtered_hvac_rooms):
                    total_area += self.filtered_hvac_rooms[idx].get('area', 0)
            self.lbl_hvac_room_selection.Text = "Selected: {} room(s), {:.0f} m2 total".format(
                len(selected_indices), total_area)
        self._update_preview()
    
    def _on_hvac_system_selected(self, sender, e):
        """Handle system selection in the systems grid"""
        selected = list(self.hvac_systems_grid.SelectedRows)
        if selected:
            idx = selected[0]
            system_names = list(self.hvac_systems.keys())
            if idx < len(system_names):
                sys_name = system_names[idx]
                self.txt_hvac_system_name.Text = sys_name
    
    def _on_hvac_load_system(self, sender, e):
        """Load selected system configuration into the form"""
        selected = list(self.hvac_systems_grid.SelectedRows)
        if not selected:
            self.hvac_status.Text = "Select a system to load"
            return
        
        idx = selected[0]
        system_names = list(self.hvac_systems.keys())
        if idx >= len(system_names):
            return
        
        sys_name = system_names[idx]
        config = self.hvac_systems[sys_name]
        
        # Load into form
        self.txt_hvac_system_name.Text = sys_name
        
        # Find and set category
        cat_name = config.get('category', 'Ideal Air (Loads Only)')
        for i in range(self.dd_hvac_category.Items.Count):
            if str(self.dd_hvac_category.Items[i]) == cat_name:
                self.dd_hvac_category.SelectedIndex = i
                break
        
        self._update_hvac_equipment_dropdown()
        
        # Find and set equipment type
        eq_type = config.get('equipment_type', '')
        for i in range(self.dd_hvac_equipment.Items.Count):
            if str(self.dd_hvac_equipment.Items[i]) == eq_type:
                self.dd_hvac_equipment.SelectedIndex = i
                break
        
        # Set vintage
        vintage = config.get('vintage', 'ASHRAE_2019')
        for i in range(self.dd_hvac_vintage.Items.Count):
            if str(self.dd_hvac_vintage.Items[i]) == vintage:
                self.dd_hvac_vintage.SelectedIndex = i
                break
        
        # Set economizer
        econ = config.get('economizer_type', 'NoEconomizer')
        for i in range(self.dd_hvac_economizer.Items.Count):
            if str(self.dd_hvac_economizer.Items[i]) == econ:
                self.dd_hvac_economizer.SelectedIndex = i
                break
        
        self.num_hvac_sensible.Value = config.get('sensible_heat_recovery', 0)
        self.num_hvac_latent.Value = config.get('latent_heat_recovery', 0)
        self.chk_hvac_dcv.Checked = config.get('demand_controlled_ventilation', False)
        
        self.hvac_status.Text = "Loaded system: {}".format(sys_name)
    
    def _on_hvac_delete_system(self, sender, e):
        """Delete selected system and unassign all rooms from it"""
        selected = list(self.hvac_systems_grid.SelectedRows)
        if not selected:
            self.hvac_status.Text = "Select a system to delete"
            return
        
        idx = selected[0]
        system_names = list(self.hvac_systems.keys())
        if idx >= len(system_names):
            return
        
        sys_name = system_names[idx]
        
        # Unassign all rooms from this system
        rooms_to_unassign = [r_id for r_id, s_name in self.room_hvac_assignments.items() if s_name == sys_name]
        for r_id in rooms_to_unassign:
            del self.room_hvac_assignments[r_id]
        
        # Delete the system
        del self.hvac_systems[sys_name]
        
        self._refresh_hvac_systems_grid()
        self._refresh_hvac_room_grid()
        self._suggest_system_name()
        self.hvac_status.Text = "Deleted system '{}', unassigned {} rooms".format(sys_name, len(rooms_to_unassign))
    
    def _on_hvac_assign_rooms(self, sender, e):
        """Assign selected rooms to the named system (create/update system)"""
        system_name = self.txt_hvac_system_name.Text.strip()
        if not system_name:
            self.hvac_status.Text = "Enter a system name"
            return
        
        # Validate system name (no spaces, special chars)
        system_name = system_name.replace(' ', '_')
        
        selected = list(self.hvac_room_grid.SelectedRows)
        if not selected:
            self.hvac_status.Text = "Select rooms to assign"
            return
        
        cat_name = str(self.dd_hvac_category.SelectedValue)
        cat_info = HVAC_CATEGORIES.get(cat_name, {})
        
        # Build system config
        config = {
            'class': cat_info.get('class', 'IdealAirSystem'),
            'category': cat_name,
            'equipment_type': str(self.dd_hvac_equipment.SelectedValue) if self.dd_hvac_equipment.SelectedIndex >= 0 else '',
            'vintage': str(self.dd_hvac_vintage.SelectedValue) if self.dd_hvac_vintage.SelectedIndex >= 0 else 'ASHRAE_2019',
            'economizer_type': str(self.dd_hvac_economizer.SelectedValue) if self.dd_hvac_economizer.SelectedIndex >= 0 else 'NoEconomizer',
            'sensible_heat_recovery': float(self.num_hvac_sensible.Value),
            'latent_heat_recovery': float(self.num_hvac_latent.Value),
            'demand_controlled_ventilation': self.chk_hvac_dcv.Checked,
        }
        
        # Create or update the system
        is_new = system_name not in self.hvac_systems
        self.hvac_systems[system_name] = config
        
        # Assign selected rooms to this system
        count = 0
        for idx in selected:
            if idx < len(self.filtered_hvac_rooms):
                room_id = self.filtered_hvac_rooms[idx]['id']
                self.room_hvac_assignments[room_id] = system_name
                count += 1
        
        self._refresh_hvac_room_grid()
        self._refresh_hvac_systems_grid()
        
        action = "Created" if is_new else "Updated"
        self.hvac_status.Text = "{} '{}' ({}) - assigned {} rooms".format(
            action, system_name, cat_info.get('class', '')[:10], count)
    
    def _on_hvac_unassign_rooms(self, sender, e):
        """Unassign selected rooms from their HVAC systems"""
        selected = list(self.hvac_room_grid.SelectedRows)
        if not selected:
            self.hvac_status.Text = "Select rooms to unassign"
            return
        
        count = 0
        for idx in selected:
            if idx < len(self.filtered_hvac_rooms):
                room_id = self.filtered_hvac_rooms[idx]['id']
                if room_id in self.room_hvac_assignments:
                    del self.room_hvac_assignments[room_id]
                    count += 1
        
        self._refresh_hvac_room_grid()
        self._refresh_hvac_systems_grid()  # Update room counts
        self.hvac_status.Text = "Unassigned {} rooms".format(count)
    
    def _refresh_shade_wall_grid(self):
        """Refresh wall shading grid: [S, Type, Room, Area]"""
        rows = []
        for f in self.filtered_shade_walls:
            shaded = "S" if f['id'] in self.shading_config else ""
            rows.append([
                shaded,
                f['type'][:10],
                f['room'][:20],
                "{:.1f}".format(f['area'])
            ])
        self.shade_wall_grid.DataStore = rows
    
    def _refresh_shade_ap_grid(self):
        """Refresh aperture shading grid: [S, Room, Parent, Area]"""
        rows = []
        for a in self.filtered_shade_apertures:
            shaded = "S" if a['id'] in self.shading_config else ""
            parent_short = a.get('parent', '')[-12:] if a.get('parent') else ""
            rows.append([
                shaded,
                a['room'][:20],
                parent_short,
                "{:.1f}".format(a['area'])
            ])
        self.shade_ap_grid.DataStore = rows
    
    def _refresh_shade_door_grid(self):
        """Refresh door shading grid: [S, Type, Room, Area]"""
        rows = []
        for d in self.filtered_shade_doors:
            shaded = "S" if d['id'] in self.shading_config else ""
            type_marker = "Glass" if d.get('is_glass', False) else "Opaque"
            rows.append([
                shaded,
                type_marker,
                d['room'][:20],
                "{:.1f}".format(d['area'])
            ])
        self.shade_door_grid.DataStore = rows
    
    def _on_shade_selection_changed(self, sender, e):
        """Handle shading surface selection change - update preview"""
        self._update_preview()
    
    def _on_filter_shade_walls(self, sender, e):
        room_f = str(self.shade_wall_room_filter.Items[self.shade_wall_room_filter.SelectedIndex])
        ext_walls = [f for f in self.face_list if f['bc'] == 'Outdoors' and 'Wall' in f['type']]
        if room_f == "<All>":
            self.filtered_shade_walls = list(ext_walls)
        else:
            self.filtered_shade_walls = [f for f in ext_walls if f['room'] == room_f]
        self._refresh_shade_wall_grid()
    
    def _on_filter_shade_apertures(self, sender, e):
        room_f = str(self.shade_ap_room_filter.Items[self.shade_ap_room_filter.SelectedIndex])
        ext_ap = [a for a in self.aperture_list if a['bc'] == 'Outdoors']
        if room_f == "<All>":
            self.filtered_shade_apertures = list(ext_ap)
        else:
            self.filtered_shade_apertures = [a for a in ext_ap if a['room'] == room_f]
        self._refresh_shade_ap_grid()
    
    def _on_apply_wall_shading(self, sender, e):
        if not self.chk_wall_overhang.Checked:
            self.shade_status.Text = "Check 'Overhang' to apply"
            return
        selected = list(self.shade_wall_grid.SelectedRows)
        if not selected:
            self.shade_status.Text = "Select walls first"
            return
        depth = float(self.num_wall_oh_depth.Value)
        angle = float(self.num_wall_oh_angle.Value)
        count = 0
        for idx in selected:
            if idx < len(self.filtered_shade_walls):
                face_data = self.filtered_shade_walls[idx]
                self.shading_config[face_data['id']] = {
                    'type': 'wall_overhang',
                    'depth': depth,
                    'angle': angle
                }
                count += 1
        self._refresh_shade_wall_grid()
        self.shade_status.Text = "Applied overhang to {} walls".format(count)
    
    def _on_apply_aperture_shading(self, sender, e):
        has_overhang = self.chk_ap_overhang.Checked
        has_fins = self.chk_ap_fins.Checked
        has_louvers = self.chk_ap_louvers.Checked
        if not (has_overhang or has_fins or has_louvers):
            self.shade_status.Text = "Select at least one shading type"
            return
        selected = list(self.shade_ap_grid.SelectedRows)
        if not selected:
            self.shade_status.Text = "Select apertures first"
            return
        config = {'type': 'aperture_shading'}
        if has_overhang:
            config['overhang'] = {
                'depth': float(self.num_ap_oh_depth.Value),
                'angle': float(self.num_ap_oh_angle.Value)
            }
        if has_fins:
            config['fins'] = {
                'depth': float(self.num_ap_fin_depth.Value),
                'angle': float(self.num_ap_fin_angle.Value)
            }
        if has_louvers:
            config['louvers'] = {
                'count': int(self.num_ap_louver_count.Value),
                'depth': float(self.num_ap_louver_depth.Value),
                'offset': float(self.num_ap_louver_offset.Value),
                'angle': float(self.num_ap_louver_angle.Value)
            }
        count = 0
        for idx in selected:
            if idx < len(self.filtered_shade_apertures):
                ap_data = self.filtered_shade_apertures[idx]
                self.shading_config[ap_data['id']] = config.copy()
                count += 1
        self._refresh_shade_ap_grid()
        types = []
        if has_overhang: types.append("OH")
        if has_fins: types.append("Fins")
        if has_louvers: types.append("Louvers")
        self.shade_status.Text = "Applied {} to {} apertures".format("+".join(types), count)
    
    def _on_apply_door_shading(self, sender, e):
        if not self.chk_door_canopy.Checked:
            self.shade_status.Text = "Check 'Canopy' to apply"
            return
        selected = list(self.shade_door_grid.SelectedRows)
        if not selected:
            self.shade_status.Text = "Select doors first"
            return
        depth = float(self.num_door_canopy_depth.Value)
        count = 0
        for idx in selected:
            if idx < len(self.filtered_shade_doors):
                door_data = self.filtered_shade_doors[idx]
                self.shading_config[door_data['id']] = {
                    'type': 'door_canopy',
                    'depth': depth
                }
                count += 1
        self._refresh_shade_door_grid()
        self.shade_status.Text = "Applied canopy to {} doors".format(count)

    def _format_face_row(self, f):
        """Format face row for multi-column grid: [M, G, Type, Room, BC, Area, Construction]"""
        mod_marker = "*" if f['id'] in self.modified_faces else ""
        geo_marker = "G" if f['brep'] else "-"
        constr_display = f['construction'][:20] if f['construction'] != '<Unchanged>' else ""
        return [
            mod_marker,
            geo_marker,
            f['type'][:10],
            f['room'][:20],
            f['bc'][:7],
            "{:.1f}".format(f['area']),
            constr_display
        ]
    
    def _format_ap_row(self, a):
        """Format aperture row for multi-column grid: [M, G, Room, Parent, BC, Area, Construction]"""
        mod_marker = "*" if a['id'] in self.modified_apertures else ""
        geo_marker = "G" if a['brep'] else "-"
        constr_display = a['construction'][:20] if a['construction'] != '<Unchanged>' else ""
        parent_short = a.get('parent', '')[-15:] if a.get('parent') else ""
        return [
            mod_marker,
            geo_marker,
            a['room'][:20],
            parent_short,
            a['bc'][:7],
            "{:.1f}".format(a['area']),
            constr_display
        ]
    
    def _format_door_row(self, d):
        """Format door row for multi-column grid: [M, G, Type, Room, BC, Area, Construction]"""
        mod_marker = "*" if d['id'] in self.modified_doors else ""
        geo_marker = "G" if d['brep'] else "-"
        type_marker = "Glass" if d.get('is_glass', False) else "Opaque"
        constr_display = d['construction'][:20] if d['construction'] != '<Unchanged>' else ""
        return [
            mod_marker,
            geo_marker,
            type_marker,
            d['room'][:20],
            d['bc'][:7],
            "{:.1f}".format(d['area']),
            constr_display
        ]
    
    def _refresh_face_grid(self):
        self.filtered_faces = []
        room_f = str(self.room_filter.Items[self.room_filter.SelectedIndex]) if self.room_filter.SelectedIndex >= 0 else "<All>"
        type_f = str(self.type_filter.Items[self.type_filter.SelectedIndex]) if self.type_filter.SelectedIndex >= 0 else "<All>"
        bc_f = str(self.bc_filter.Items[self.bc_filter.SelectedIndex]) if self.bc_filter.SelectedIndex >= 0 else "<All>"
        for f in self.face_list:
            if room_f != "<All>" and f['room'] != room_f:
                continue
            if type_f != "<All>" and type_f.lower() not in f['type'].lower():
                continue
            if bc_f != "<All>" and f['bc'] != bc_f:
                continue
            self.filtered_faces.append(f)
        rows = [self._format_face_row(f) for f in self.filtered_faces]
        self.face_grid.DataStore = rows
        if hasattr(self, 'btn_set_all_faces'):
            self.btn_set_all_faces.Text = "Set for All Filtered ({})".format(len(self.filtered_faces))
    
    def _refresh_ap_grid(self):
        self.filtered_apertures = []
        room_f = str(self.ap_room_filter.Items[self.ap_room_filter.SelectedIndex]) if self.ap_room_filter.SelectedIndex >= 0 else "<All>"
        bc_f = str(self.ap_bc_filter.Items[self.ap_bc_filter.SelectedIndex]) if self.ap_bc_filter.SelectedIndex >= 0 else "<All>"
        for a in self.aperture_list:
            if room_f != "<All>" and a['room'] != room_f:
                continue
            if bc_f != "<All>" and a['bc'] != bc_f:
                continue
            self.filtered_apertures.append(a)
        rows = [self._format_ap_row(a) for a in self.filtered_apertures]
        self.ap_grid.DataStore = rows
        if hasattr(self, 'btn_set_all_ap'):
            self.btn_set_all_ap.Text = "Set for All Filtered ({})".format(len(self.filtered_apertures))
    
    def _refresh_door_grid(self):
        """NEW: Refresh the door grid based on filters"""
        self.filtered_doors = []
        room_f = str(self.door_room_filter.Items[self.door_room_filter.SelectedIndex]) if self.door_room_filter.SelectedIndex >= 0 else "<All>"
        bc_f = str(self.door_bc_filter.Items[self.door_bc_filter.SelectedIndex]) if self.door_bc_filter.SelectedIndex >= 0 else "<All>"
        type_f = str(self.door_type_filter.Items[self.door_type_filter.SelectedIndex]) if self.door_type_filter.SelectedIndex >= 0 else "<All>"
        for d in self.door_list:
            if room_f != "<All>" and d['room'] != room_f:
                continue
            if bc_f != "<All>" and d['bc'] != bc_f:
                continue
            if type_f == "Opaque" and d.get('is_glass', False):
                continue
            if type_f == "Glass" and not d.get('is_glass', False):
                continue
            self.filtered_doors.append(d)
        rows = [self._format_door_row(d) for d in self.filtered_doors]
        self.door_grid.DataStore = rows
        if hasattr(self, 'btn_set_all_doors'):
            self.btn_set_all_doors.Text = "Set for All Filtered ({})".format(len(self.filtered_doors))
    
    def _update_face_dropdowns(self, bc):
        self.face_constr_dropdown.Items.Clear()
        self.face_constr_dropdown.Items.Add("<Unchanged>")
        gds_c = self.gds_parser.get_constructions_for_boundary(bc, is_window=False)
        for name in sorted(gds_c.keys()):
            self.face_constr_dropdown.Items.Add("[GDS] " + name)
        try:
            from honeybee_energy.lib.constructions import OPAQUE_CONSTRUCTIONS
            for c in sorted(OPAQUE_CONSTRUCTIONS):
                self.face_constr_dropdown.Items.Add("[HB] " + c)
        except:
            pass
        self.face_constr_dropdown.SelectedIndex = 0
        self.face_mod_dropdown.Items.Clear()
        self.face_mod_dropdown.Items.Add("<Unchanged>")
        gds_m = self.gds_parser.get_modifiers_for_boundary(bc, is_glass=False)
        for name in sorted(gds_m.keys()):
            self.face_mod_dropdown.Items.Add("[GDS] " + name)
        try:
            from honeybee_radiance.lib.modifiers import MODIFIERS
            for m in sorted(MODIFIERS):
                self.face_mod_dropdown.Items.Add("[HB] " + m)
        except:
            pass
        self.face_mod_dropdown.SelectedIndex = 0
    
    def _update_ap_dropdowns(self, bc):
        self.ap_constr_dropdown.Items.Clear()
        self.ap_constr_dropdown.Items.Add("<Unchanged>")
        gds_c = self.gds_parser.get_constructions_for_boundary(bc, is_window=True)
        for name in sorted(gds_c.keys()):
            self.ap_constr_dropdown.Items.Add("[GDS] " + name)
        try:
            from honeybee_energy.lib.constructions import WINDOW_CONSTRUCTIONS
            for c in sorted(WINDOW_CONSTRUCTIONS):
                self.ap_constr_dropdown.Items.Add("[HB] " + c)
        except:
            pass
        self.ap_constr_dropdown.SelectedIndex = 0
        self.ap_mod_dropdown.Items.Clear()
        self.ap_mod_dropdown.Items.Add("<Unchanged>")
        gds_m = self.gds_parser.get_modifiers_for_boundary(bc, is_glass=True)
        for name in sorted(gds_m.keys()):
            self.ap_mod_dropdown.Items.Add("[GDS] " + name)
        try:
            from honeybee_radiance.lib.modifiers import MODIFIERS
            for m in sorted(MODIFIERS):
                self.ap_mod_dropdown.Items.Add("[HB] " + m)
        except:
            pass
        self.ap_mod_dropdown.SelectedIndex = 0
    
    def _update_door_dropdowns(self, bc, is_glass):
        """NEW: Update door dropdowns based on boundary condition and door type"""
        self.door_constr_dropdown.Items.Clear()
        self.door_constr_dropdown.Items.Add("<Unchanged>")
        
        # For glass doors, use window constructions; for opaque doors, use opaque constructions
        gds_c = self.gds_parser.get_constructions_for_boundary(bc, is_window=is_glass)
        for name in sorted(gds_c.keys()):
            self.door_constr_dropdown.Items.Add("[GDS] " + name)
        
        try:
            if is_glass:
                from honeybee_energy.lib.constructions import WINDOW_CONSTRUCTIONS
                for c in sorted(WINDOW_CONSTRUCTIONS):
                    self.door_constr_dropdown.Items.Add("[HB] " + c)
            else:
                from honeybee_energy.lib.constructions import OPAQUE_CONSTRUCTIONS
                for c in sorted(OPAQUE_CONSTRUCTIONS):
                    self.door_constr_dropdown.Items.Add("[HB] " + c)
        except:
            pass
        self.door_constr_dropdown.SelectedIndex = 0
        
        # Modifiers
        self.door_mod_dropdown.Items.Clear()
        self.door_mod_dropdown.Items.Add("<Unchanged>")
        gds_m = self.gds_parser.get_modifiers_for_boundary(bc, is_glass=is_glass)
        for name in sorted(gds_m.keys()):
            self.door_mod_dropdown.Items.Add("[GDS] " + name)
        try:
            from honeybee_radiance.lib.modifiers import MODIFIERS
            for m in sorted(MODIFIERS):
                self.door_mod_dropdown.Items.Add("[HB] " + m)
        except:
            pass
        self.door_mod_dropdown.SelectedIndex = 0
    
    def _on_filter_faces(self, sender, e):
        self._refresh_face_grid()
    
    def _on_filter_apertures(self, sender, e):
        self._refresh_ap_grid()
    
    def _on_filter_doors(self, sender, e):
        """NEW: Handle door filter button click"""
        self._refresh_door_grid()
    
    def _on_face_selection_changed(self, sender, e):
        selected_indices = list(self.face_grid.SelectedRows)
        if not selected_indices:
            self.face_selection_info.Text = "No selection"
        else:
            self.face_selection_info.Text = "Selected: {} face(s)".format(len(selected_indices))
            first_idx = selected_indices[0]
            if first_idx < len(self.filtered_faces):
                bc = self.filtered_faces[first_idx]['bc']
                self._update_face_dropdowns(bc)
        self._update_preview()
    
    def _on_ap_selection_changed(self, sender, e):
        selected_indices = list(self.ap_grid.SelectedRows)
        if not selected_indices:
            self.ap_selection_info.Text = "No selection"
        else:
            self.ap_selection_info.Text = "Selected: {} aperture(s)".format(len(selected_indices))
            first_idx = selected_indices[0]
            if first_idx < len(self.filtered_apertures):
                bc = self.filtered_apertures[first_idx]['bc']
                self._update_ap_dropdowns(bc)
        self._update_preview()
    
    def _on_door_selection_changed(self, sender, e):
        """NEW: Handle door selection change"""
        selected_indices = list(self.door_grid.SelectedRows)
        if not selected_indices:
            self.door_selection_info.Text = "No selection"
        else:
            self.door_selection_info.Text = "Selected: {} door(s)".format(len(selected_indices))
            first_idx = selected_indices[0]
            if first_idx < len(self.filtered_doors):
                door = self.filtered_doors[first_idx]
                bc = door['bc']
                is_glass = door.get('is_glass', False)
                self._update_door_dropdowns(bc, is_glass)
        self._update_preview()
    
    def _apply_to_faces(self, faces_to_modify):
        constr = str(self.face_constr_dropdown.Items[self.face_constr_dropdown.SelectedIndex])
        mod = str(self.face_mod_dropdown.Items[self.face_mod_dropdown.SelectedIndex])
        for f in faces_to_modify:
            fid = f['id']
            if constr != "<Unchanged>" or mod != "<Unchanged>":
                if fid not in self.modified_faces:
                    self.modified_faces[fid] = {}
                if constr != "<Unchanged>":
                    self.modified_faces[fid]['construction'] = constr
                    f['construction'] = constr
                if mod != "<Unchanged>":
                    self.modified_faces[fid]['modifier'] = mod
                    f['modifier'] = mod
        self._refresh_face_grid()
        self._update_status()
        self._update_preview()
    
    def _apply_to_apertures(self, apertures_to_modify):
        constr = str(self.ap_constr_dropdown.Items[self.ap_constr_dropdown.SelectedIndex])
        mod = str(self.ap_mod_dropdown.Items[self.ap_mod_dropdown.SelectedIndex])
        for a in apertures_to_modify:
            aid = a['id']
            if constr != "<Unchanged>" or mod != "<Unchanged>":
                if aid not in self.modified_apertures:
                    self.modified_apertures[aid] = {}
                if constr != "<Unchanged>":
                    self.modified_apertures[aid]['construction'] = constr
                    a['construction'] = constr
                if mod != "<Unchanged>":
                    self.modified_apertures[aid]['modifier'] = mod
                    a['modifier'] = mod
        self._refresh_ap_grid()
        self._update_status()
        self._update_preview()
    
    def _apply_to_doors(self, doors_to_modify):
        """NEW: Apply construction and modifier to doors"""
        constr = str(self.door_constr_dropdown.Items[self.door_constr_dropdown.SelectedIndex])
        mod = str(self.door_mod_dropdown.Items[self.door_mod_dropdown.SelectedIndex])
        for d in doors_to_modify:
            did = d['id']
            if constr != "<Unchanged>" or mod != "<Unchanged>":
                if did not in self.modified_doors:
                    self.modified_doors[did] = {}
                if constr != "<Unchanged>":
                    self.modified_doors[did]['construction'] = constr
                    self.modified_doors[did]['is_glass'] = d.get('is_glass', False)
                    d['construction'] = constr
                if mod != "<Unchanged>":
                    self.modified_doors[did]['modifier'] = mod
                    self.modified_doors[did]['is_glass'] = d.get('is_glass', False)
                    d['modifier'] = mod
        self._refresh_door_grid()
        self._update_status()
        self._update_preview()
    
    def _on_set_selected_faces(self, sender, e):
        selected_indices = list(self.face_grid.SelectedRows)
        if not selected_indices:
            self.face_selection_info.Text = "No faces selected"
            return
        faces_to_modify = [self.filtered_faces[i] for i in selected_indices if i < len(self.filtered_faces)]
        self._apply_to_faces(faces_to_modify)
        self.face_selection_info.Text = "Set {} face(s)".format(len(faces_to_modify))
    
    def _on_set_all_faces(self, sender, e):
        self._apply_to_faces(self.filtered_faces)
        self.face_selection_info.Text = "Set all {} filtered faces".format(len(self.filtered_faces))
    
    def _on_set_selected_apertures(self, sender, e):
        selected_indices = list(self.ap_grid.SelectedRows)
        if not selected_indices:
            self.ap_selection_info.Text = "No apertures selected"
            return
        apertures_to_modify = [self.filtered_apertures[i] for i in selected_indices if i < len(self.filtered_apertures)]
        self._apply_to_apertures(apertures_to_modify)
        self.ap_selection_info.Text = "Set {} aperture(s)".format(len(apertures_to_modify))
    
    def _on_set_all_apertures(self, sender, e):
        self._apply_to_apertures(self.filtered_apertures)
        self.ap_selection_info.Text = "Set all {} filtered apertures".format(len(self.filtered_apertures))
    
    def _on_set_selected_doors(self, sender, e):
        """NEW: Set properties for selected doors"""
        selected_indices = list(self.door_grid.SelectedRows)
        if not selected_indices:
            self.door_selection_info.Text = "No doors selected"
            return
        doors_to_modify = [self.filtered_doors[i] for i in selected_indices if i < len(self.filtered_doors)]
        self._apply_to_doors(doors_to_modify)
        self.door_selection_info.Text = "Set {} door(s)".format(len(doors_to_modify))
    
    def _on_set_all_doors(self, sender, e):
        """NEW: Set properties for all filtered doors"""
        self._apply_to_doors(self.filtered_doors)
        self.door_selection_info.Text = "Set all {} filtered doors".format(len(self.filtered_doors))
    
    def _on_clear(self, sender, e):
        self.modified_faces = {}
        self.modified_apertures = {}
        self.modified_doors = {}
        self.shading_config = {}
        self.hvac_systems = {}
        self.room_hvac_assignments = {}
        for f in self.face_list:
            f['construction'] = '<Unchanged>'
            f['modifier'] = '<Unchanged>'
        for a in self.aperture_list:
            a['construction'] = '<Unchanged>'
            a['modifier'] = '<Unchanged>'
        for d in self.door_list:
            d['construction'] = '<Unchanged>'
            d['modifier'] = '<Unchanged>'
        if STORAGE_KEY in sc.sticky:
            del sc.sticky[STORAGE_KEY]
        self._refresh_face_grid()
        self._refresh_ap_grid()
        self._refresh_door_grid()
        self._refresh_shade_wall_grid()
        self._refresh_shade_ap_grid()
        self._refresh_shade_door_grid()
        self._refresh_hvac_room_grid()
        self._refresh_hvac_systems_grid()
        self._suggest_system_name()
        self._update_status()
        clear_preview_component(self.preview_nickname)
    
    def _on_cancel(self, sender, e):
        clear_preview_component(self.preview_nickname)
        if DIALOG_KEY in sc.sticky:
            del sc.sticky[DIALOG_KEY]
        self.Close()
    
    def _on_save(self, sender, e):
        """Save settings without closing UI or triggering downstream"""
        sc.sticky[STORAGE_KEY] = {
            'faces': dict(self.modified_faces),
            'apertures': dict(self.modified_apertures),
            'doors': dict(self.modified_doors),
            'shading': dict(self.shading_config),
            'hvac_systems': dict(self.hvac_systems),
            'room_hvac_assignments': dict(self.room_hvac_assignments),
            'force_update': False
        }
        shade_count = len(self.shading_config)
        hvac_count = len(self.room_hvac_assignments)
        self.status_label.Text = "Saved: {} faces, {} aps, {} doors, {} shades, {} HVAC rooms".format(
            len(self.modified_faces), len(self.modified_apertures), len(self.modified_doors), shade_count, hvac_count)
    
    def _on_apply(self, sender, e):
        """Save and close, but DON'T trigger downstream simulation"""
        sc.sticky[STORAGE_KEY] = {
            'faces': dict(self.modified_faces),
            'apertures': dict(self.modified_apertures),
            'doors': dict(self.modified_doors),
            'shading': dict(self.shading_config),
            'hvac_systems': dict(self.hvac_systems),
            'room_hvac_assignments': dict(self.room_hvac_assignments),
            'force_update': True
        }
        sc.sticky[RELEASE_OUTPUT_KEY] = False
        clear_preview_component(self.preview_nickname)
        if DIALOG_KEY in sc.sticky:
            del sc.sticky[DIALOG_KEY]
        expire_gh_component()
        self.Close()
    
    def _on_save_and_run(self, sender, e):
        """Save and trigger downstream simulation, but keep UI open"""
        sc.sticky[STORAGE_KEY] = {
            'faces': dict(self.modified_faces),
            'apertures': dict(self.modified_apertures),
            'doors': dict(self.modified_doors),
            'shading': dict(self.shading_config),
            'hvac_systems': dict(self.hvac_systems),
            'room_hvac_assignments': dict(self.room_hvac_assignments),
            'force_update': True
        }
        sc.sticky[RELEASE_OUTPUT_KEY] = True
        expire_gh_component()
        shade_count = len(self.shading_config)
        hvac_count = len(self.room_hvac_assignments)
        self.status_label.Text = "Running: {} faces, {} aps, {} doors, {} shades, {} HVAC rooms".format(
            len(self.modified_faces), len(self.modified_apertures), len(self.modified_doors), shade_count, hvac_count)
    
    def _on_form_closed(self, sender, e):
        clear_preview_component(self.preview_nickname)
        if DIALOG_KEY in sc.sticky:
            del sc.sticky[DIALOG_KEY]


def get_construction_dict(identifier, gds_constructions, is_window=False):
    """Get construction as dictionary for embedding in model JSON"""
    if not identifier or identifier == '<Unchanged>':
        return None
    
    if identifier.startswith("[GDS] "):
        name = identifier[6:]
        if name in gds_constructions:
            return gds_constructions[name]['hb_dict']
    
    elif identifier.startswith("[HB] "):
        hb_id = identifier[5:]
        try:
            if is_window:
                from honeybee_energy.lib.constructions import window_construction_by_identifier
                return window_construction_by_identifier(hb_id).to_dict()
            else:
                from honeybee_energy.lib.constructions import opaque_construction_by_identifier
                return opaque_construction_by_identifier(hb_id).to_dict()
        except:
            try:
                if is_window:
                    from honeybee_energy.lib.constructions import opaque_construction_by_identifier
                    return opaque_construction_by_identifier(hb_id).to_dict()
                else:
                    from honeybee_energy.lib.constructions import window_construction_by_identifier
                    return window_construction_by_identifier(hb_id).to_dict()
            except:
                pass
    return None


def get_modifier_dict(identifier, gds_modifiers):
    """Get modifier as dictionary for embedding in model JSON"""
    if not identifier or identifier == '<Unchanged>':
        return None
    
    if identifier.startswith("[GDS] "):
        name = identifier[6:]
        if name in gds_modifiers:
            return gds_modifiers[name]['hb_dict']
    
    elif identifier.startswith("[HB] "):
        hb_id = identifier[5:]
        try:
            from honeybee_radiance.lib.modifiers import modifier_by_identifier
            return modifier_by_identifier(hb_id).to_dict()
        except:
            pass
    return None


def apply_shading_to_model(hb_model, shading_config):
    """
    Apply shading configurations to HB model using native HB methods.
    Must be called BEFORE to_dict() since it modifies live objects.
    
    Returns count of shades applied.
    """
    shade_count = 0
    error_count = 0
    
    for room in hb_model.rooms:
        for face in room.faces:
            face_id = face.identifier
            
            if face_id in shading_config:
                config = shading_config[face_id]
                if config.get('type') == 'wall_overhang':
                    try:
                        depth = config.get('depth', 0.5)
                        angle = config.get('angle', 0)
                        face.overhang(depth, angle=angle, indoor=False)
                        shade_count += 1
                    except Exception as ex:
                        print("Wall overhang error on {}: {}".format(face_id, ex))
                        error_count += 1
            
            for aperture in face.apertures:
                ap_id = aperture.identifier
                if ap_id in shading_config:
                    config = shading_config[ap_id]
                    if config.get('type') == 'aperture_shading':
                        try:
                            if 'overhang' in config:
                                oh = config['overhang']
                                aperture.overhang(oh['depth'], angle=oh['angle'], indoor=False)
                                shade_count += 1
                            if 'fins' in config:
                                fin = config['fins']
                                aperture.right_fin(fin['depth'], angle=fin['angle'], indoor=False)
                                aperture.left_fin(fin['depth'], angle=fin['angle'], indoor=False)
                                shade_count += 2
                            if 'louvers' in config:
                                louv = config['louvers']
                                aperture.louvers_by_count(
                                    louv['count'], louv['depth'],
                                    offset=louv['offset'], angle=louv['angle'],
                                    indoor=False
                                )
                                shade_count += louv['count']
                        except Exception as ex:
                            print("Aperture shading error on {}: {}".format(ap_id, ex))
                            error_count += 1
            
            for door in face.doors:
                door_id = door.identifier
                if door_id in shading_config:
                    config = shading_config[door_id]
                    if config.get('type') == 'door_canopy':
                        try:
                            depth = config.get('depth', 1.0)
                            door.overhang(depth, angle=0, indoor=False)
                            shade_count += 1
                        except Exception as ex:
                            print("Door canopy error on {}: {}".format(door_id, ex))
                            error_count += 1
    
    return shade_count, error_count


def build_hvac_dict(system_name, hvac_config):
    """
    Build HVAC dict in HB schema format.
    system_name: The shared identifier for this HVAC system
    hvac_config: Configuration dict with class, equipment_type, vintage, etc.
    """
    class_name = hvac_config.get('class', 'IdealAirSystem')
    
    hvac_dict = {
        'identifier': system_name
    }
    
    if class_name == 'IdealAirSystem':
        hvac_dict['type'] = 'IdealAirSystemAbridged'
        hvac_dict['economizer_type'] = hvac_config.get('economizer_type', 'NoEconomizer')
        hvac_dict['sensible_heat_recovery'] = hvac_config.get('sensible_heat_recovery', 0)
        hvac_dict['latent_heat_recovery'] = hvac_config.get('latent_heat_recovery', 0)
        hvac_dict['demand_controlled_ventilation'] = hvac_config.get('demand_controlled_ventilation', False)
    
    elif class_name == 'VAV':
        hvac_dict['type'] = 'VAV'
        hvac_dict['vintage'] = hvac_config.get('vintage', 'ASHRAE_2019')
        hvac_dict['equipment_type'] = hvac_config.get('equipment_type', 'VAV_Chiller_Boiler')
        hvac_dict['economizer_type'] = hvac_config.get('economizer_type', 'NoEconomizer')
        hvac_dict['sensible_heat_recovery'] = hvac_config.get('sensible_heat_recovery', 0)
        hvac_dict['latent_heat_recovery'] = hvac_config.get('latent_heat_recovery', 0)
        hvac_dict['demand_controlled_ventilation'] = hvac_config.get('demand_controlled_ventilation', False)
    
    elif class_name == 'PVAV':
        hvac_dict['type'] = 'PVAV'
        hvac_dict['vintage'] = hvac_config.get('vintage', 'ASHRAE_2019')
        hvac_dict['equipment_type'] = hvac_config.get('equipment_type', 'PVAV_Boiler')
        hvac_dict['economizer_type'] = hvac_config.get('economizer_type', 'NoEconomizer')
        hvac_dict['sensible_heat_recovery'] = hvac_config.get('sensible_heat_recovery', 0)
        hvac_dict['latent_heat_recovery'] = hvac_config.get('latent_heat_recovery', 0)
        hvac_dict['demand_controlled_ventilation'] = hvac_config.get('demand_controlled_ventilation', False)
    
    elif class_name == 'PSZ':
        hvac_dict['type'] = 'PSZ'
        hvac_dict['vintage'] = hvac_config.get('vintage', 'ASHRAE_2019')
        hvac_dict['equipment_type'] = hvac_config.get('equipment_type', 'PSZAC')
        hvac_dict['economizer_type'] = hvac_config.get('economizer_type', 'NoEconomizer')
        hvac_dict['sensible_heat_recovery'] = hvac_config.get('sensible_heat_recovery', 0)
        hvac_dict['latent_heat_recovery'] = hvac_config.get('latent_heat_recovery', 0)
        hvac_dict['demand_controlled_ventilation'] = hvac_config.get('demand_controlled_ventilation', False)
    
    elif class_name == 'FCUwithDOAS':
        hvac_dict['type'] = 'FCUwithDOAS'
        hvac_dict['vintage'] = hvac_config.get('vintage', 'ASHRAE_2019')
        hvac_dict['equipment_type'] = hvac_config.get('equipment_type', 'DOAS_FCU_Chiller_Boiler')
        hvac_dict['sensible_heat_recovery'] = hvac_config.get('sensible_heat_recovery', 0)
        hvac_dict['latent_heat_recovery'] = hvac_config.get('latent_heat_recovery', 0)
        hvac_dict['demand_controlled_ventilation'] = hvac_config.get('demand_controlled_ventilation', False)
    
    elif class_name == 'VRFwithDOAS':
        hvac_dict['type'] = 'VRFwithDOAS'
        hvac_dict['vintage'] = hvac_config.get('vintage', 'ASHRAE_2019')
        hvac_dict['equipment_type'] = hvac_config.get('equipment_type', 'DOAS_VRF')
        hvac_dict['sensible_heat_recovery'] = hvac_config.get('sensible_heat_recovery', 0)
        hvac_dict['latent_heat_recovery'] = hvac_config.get('latent_heat_recovery', 0)
        hvac_dict['demand_controlled_ventilation'] = hvac_config.get('demand_controlled_ventilation', False)
    
    elif class_name == 'RadiantwithDOAS':
        hvac_dict['type'] = 'RadiantwithDOAS'
        hvac_dict['vintage'] = hvac_config.get('vintage', 'ASHRAE_2019')
        hvac_dict['equipment_type'] = hvac_config.get('equipment_type', 'DOAS_Radiant_Chiller_Boiler')
        hvac_dict['sensible_heat_recovery'] = hvac_config.get('sensible_heat_recovery', 0)
        hvac_dict['latent_heat_recovery'] = hvac_config.get('latent_heat_recovery', 0)
        hvac_dict['demand_controlled_ventilation'] = hvac_config.get('demand_controlled_ventilation', False)
        hvac_dict['radiant_type'] = hvac_config.get('radiant_type', 'Floor')
    
    elif class_name == 'WSHPwithDOAS':
        hvac_dict['type'] = 'WSHPwithDOAS'
        hvac_dict['vintage'] = hvac_config.get('vintage', 'ASHRAE_2019')
        hvac_dict['equipment_type'] = hvac_config.get('equipment_type', 'DOAS_WSHP_FluidCooler_Boiler')
        hvac_dict['sensible_heat_recovery'] = hvac_config.get('sensible_heat_recovery', 0)
        hvac_dict['latent_heat_recovery'] = hvac_config.get('latent_heat_recovery', 0)
        hvac_dict['demand_controlled_ventilation'] = hvac_config.get('demand_controlled_ventilation', False)
    
    elif class_name == 'Residential':
        hvac_dict['type'] = 'Residential'
        hvac_dict['vintage'] = hvac_config.get('vintage', 'ASHRAE_2019')
        hvac_dict['equipment_type'] = hvac_config.get('equipment_type', 'ResidentialAC_ResidentialFurnace')
    
    elif class_name == 'Baseboard':
        hvac_dict['type'] = 'Baseboard'
        hvac_dict['vintage'] = hvac_config.get('vintage', 'ASHRAE_2019')
        hvac_dict['equipment_type'] = hvac_config.get('equipment_type', 'ElectricBaseboard')
    
    elif class_name == 'Radiant':
        hvac_dict['type'] = 'Radiant'
        hvac_dict['vintage'] = hvac_config.get('vintage', 'ASHRAE_2019')
        hvac_dict['equipment_type'] = hvac_config.get('equipment_type', 'Radiant_Chiller_Boiler')
        hvac_dict['radiant_type'] = hvac_config.get('radiant_type', 'Floor')
    
    else:
        hvac_dict['type'] = 'IdealAirSystemAbridged'
        hvac_dict['economizer_type'] = 'NoEconomizer'
        hvac_dict['sensible_heat_recovery'] = 0
        hvac_dict['latent_heat_recovery'] = 0
        hvac_dict['demand_controlled_ventilation'] = False
    
    return hvac_dict


def build_modified_model_file(hb_model, modified_faces, modified_apertures, modified_doors, shading_config, hvac_systems, room_hvac_assignments, gds_parser, output_path):
    """
    Build complete modified model and save to .hbjson file.
    
    v6: HVAC system grouping - multiple rooms can share the same HVAC system.
    hvac_systems: dict of system_name -> config
    room_hvac_assignments: dict of room_id -> system_name
    """
    report_lines = ["Model Modification Report", "=" * 40]
    
    # Step 0: Apply shading to live model BEFORE converting to dict
    shade_count = 0
    shade_errors = 0
    if shading_config:
        shade_count, shade_errors = apply_shading_to_model(hb_model, shading_config)
        if shade_count > 0:
            report_lines.append("Shading: {} shades applied".format(shade_count))
            if shade_errors > 0:
                report_lines.append("  ({} shading errors)".format(shade_errors))
    
    # Now convert to dict
    model_dict = hb_model.to_dict()
    
    # Step 1: Collect all unique constructions and modifiers
    construction_library = {}
    modifier_library = {}
    hvac_library = {}  # system_name -> hvac_dict (only one entry per system)
    
    # From faces
    for face_id, props in modified_faces.items():
        constr_id = props.get('construction', '')
        if constr_id and constr_id != '<Unchanged>':
            constr_dict = get_construction_dict(constr_id, gds_parser.constructions, is_window=False)
            if constr_dict:
                construction_library[constr_dict['identifier']] = constr_dict
        
        mod_id = props.get('modifier', '')
        if mod_id and mod_id != '<Unchanged>':
            mod_dict = get_modifier_dict(mod_id, gds_parser.modifiers)
            if mod_dict:
                modifier_library[mod_dict['identifier']] = mod_dict
    
    # From apertures
    for ap_id, props in modified_apertures.items():
        constr_id = props.get('construction', '')
        if constr_id and constr_id != '<Unchanged>':
            constr_dict = get_construction_dict(constr_id, gds_parser.constructions, is_window=True)
            if constr_dict:
                construction_library[constr_dict['identifier']] = constr_dict
        
        mod_id = props.get('modifier', '')
        if mod_id and mod_id != '<Unchanged>':
            mod_dict = get_modifier_dict(mod_id, gds_parser.modifiers)
            if mod_dict:
                modifier_library[mod_dict['identifier']] = mod_dict
    
    # NEW: From doors
    for door_id, props in modified_doors.items():
        is_glass = props.get('is_glass', False)
        constr_id = props.get('construction', '')
        if constr_id and constr_id != '<Unchanged>':
            constr_dict = get_construction_dict(constr_id, gds_parser.constructions, is_window=is_glass)
            if constr_dict:
                construction_library[constr_dict['identifier']] = constr_dict
        
        mod_id = props.get('modifier', '')
        if mod_id and mod_id != '<Unchanged>':
            mod_dict = get_modifier_dict(mod_id, gds_parser.modifiers)
            if mod_dict:
                modifier_library[mod_dict['identifier']] = mod_dict
    
    # Step 2: Add constructions to model's energy properties library
    if construction_library:
        if 'properties' not in model_dict:
            model_dict['properties'] = {}
        if 'energy' not in model_dict['properties']:
            model_dict['properties']['energy'] = {}
        if 'constructions' not in model_dict['properties']['energy']:
            model_dict['properties']['energy']['constructions'] = []
        
        existing_constr_ids = {c['identifier'] for c in model_dict['properties']['energy']['constructions']}
        
        for constr_id, constr_data in construction_library.items():
            if constr_id not in existing_constr_ids:
                model_dict['properties']['energy']['constructions'].append(constr_data)
    
    # Step 3: Add modifiers to model's radiance properties library
    if modifier_library:
        if 'properties' not in model_dict:
            model_dict['properties'] = {}
        if 'radiance' not in model_dict['properties']:
            model_dict['properties']['radiance'] = {}
        if 'modifiers' not in model_dict['properties']['radiance']:
            model_dict['properties']['radiance']['modifiers'] = []
        
        existing_mod_ids = {m['identifier'] for m in model_dict['properties']['radiance']['modifiers']}
        
        for mod_id, mod_data in modifier_library.items():
            if mod_id not in existing_mod_ids:
                model_dict['properties']['radiance']['modifiers'].append(mod_data)
    
    # Step 4: Apply assignments to faces, apertures, and doors
    total_faces_modified = 0
    total_apertures_modified = 0
    total_doors_modified = 0
    total_hvac_modified = 0
    
    for room_dict in model_dict.get('rooms', []):
        room_id = room_dict.get('identifier', '')
        room_name = room_dict.get('display_name', room_id)
        
        room_faces_mod = 0
        room_aps_mod = 0
        room_doors_mod = 0
        
        for face_dict in room_dict.get('faces', []):
            face_id = face_dict.get('identifier', '')
            
            # Face modifications
            if face_id in modified_faces:
                props = modified_faces[face_id]
                
                if 'properties' not in face_dict:
                    face_dict['properties'] = {}
                
                constr_id = props.get('construction', '')
                if constr_id and constr_id != '<Unchanged>':
                    constr_dict = get_construction_dict(constr_id, gds_parser.constructions, is_window=False)
                    if constr_dict:
                        if 'energy' not in face_dict['properties']:
                            face_dict['properties']['energy'] = {}
                        face_dict['properties']['energy']['construction'] = constr_dict['identifier']
                        room_faces_mod += 1
                
                mod_id = props.get('modifier', '')
                if mod_id and mod_id != '<Unchanged>':
                    mod_dict = get_modifier_dict(mod_id, gds_parser.modifiers)
                    if mod_dict:
                        if 'radiance' not in face_dict['properties']:
                            face_dict['properties']['radiance'] = {}
                        face_dict['properties']['radiance']['modifier'] = mod_dict['identifier']
            
            # Aperture modifications
            for ap_dict in face_dict.get('apertures', []):
                ap_id = ap_dict.get('identifier', '')
                
                if ap_id in modified_apertures:
                    ap_props = modified_apertures[ap_id]
                    
                    if 'properties' not in ap_dict:
                        ap_dict['properties'] = {}
                    
                    ap_constr_id = ap_props.get('construction', '')
                    if ap_constr_id and ap_constr_id != '<Unchanged>':
                        ap_constr_dict = get_construction_dict(ap_constr_id, gds_parser.constructions, is_window=True)
                        if ap_constr_dict:
                            if 'energy' not in ap_dict['properties']:
                                ap_dict['properties']['energy'] = {}
                            ap_dict['properties']['energy']['construction'] = ap_constr_dict['identifier']
                            room_aps_mod += 1
                    
                    ap_mod_id = ap_props.get('modifier', '')
                    if ap_mod_id and ap_mod_id != '<Unchanged>':
                        ap_mod_dict = get_modifier_dict(ap_mod_id, gds_parser.modifiers)
                        if ap_mod_dict:
                            if 'radiance' not in ap_dict['properties']:
                                ap_dict['properties']['radiance'] = {}
                            ap_dict['properties']['radiance']['modifier'] = ap_mod_dict['identifier']
            
            # NEW: Door modifications
            for door_dict in face_dict.get('doors', []):
                door_id = door_dict.get('identifier', '')
                
                if door_id in modified_doors:
                    door_props = modified_doors[door_id]
                    is_glass = door_props.get('is_glass', False)
                    
                    if 'properties' not in door_dict:
                        door_dict['properties'] = {}
                    
                    door_constr_id = door_props.get('construction', '')
                    if door_constr_id and door_constr_id != '<Unchanged>':
                        door_constr_dict = get_construction_dict(door_constr_id, gds_parser.constructions, is_window=is_glass)
                        if door_constr_dict:
                            if 'energy' not in door_dict['properties']:
                                door_dict['properties']['energy'] = {}
                            door_dict['properties']['energy']['construction'] = door_constr_dict['identifier']
                            room_doors_mod += 1
                    
                    door_mod_id = door_props.get('modifier', '')
                    if door_mod_id and door_mod_id != '<Unchanged>':
                        door_mod_dict = get_modifier_dict(door_mod_id, gds_parser.modifiers)
                        if door_mod_dict:
                            if 'radiance' not in door_dict['properties']:
                                door_dict['properties']['radiance'] = {}
                            door_dict['properties']['radiance']['modifier'] = door_mod_dict['identifier']
        
        # HVAC application - NEW: Use system grouping
        if room_hvac_assignments and room_id in room_hvac_assignments:
            system_name = room_hvac_assignments[room_id]
            
            if system_name in hvac_systems:
                hvac_cfg = hvac_systems[system_name]
                
                # Build HVAC dict using system_name as identifier (so rooms share the system)
                if system_name not in hvac_library:
                    # First room using this system - create the HVAC dict
                    hvac_dict = build_hvac_dict(system_name, hvac_cfg)
                    hvac_library[system_name] = hvac_dict
                
                # Assign this room to the shared HVAC system
                if 'properties' not in room_dict:
                    room_dict['properties'] = {}
                if 'energy' not in room_dict['properties']:
                    room_dict['properties']['energy'] = {}
                
                room_dict['properties']['energy']['hvac'] = system_name
                total_hvac_modified += 1
                print("HVAC assigned: room='{}' -> system='{}'".format(room_id[:25], system_name[:30]))
        
        if room_faces_mod > 0 or room_aps_mod > 0 or room_doors_mod > 0:
            report_lines.append("'{}': {} faces, {} apertures, {} doors".format(
                room_name, room_faces_mod, room_aps_mod, room_doors_mod))
        
        total_faces_modified += room_faces_mod
        total_apertures_modified += room_aps_mod
        total_doors_modified += room_doors_mod
    
    # Step 5: Add HVAC systems to model's energy properties library
    if hvac_library:
        if 'properties' not in model_dict:
            model_dict['properties'] = {}
        if 'energy' not in model_dict['properties']:
            model_dict['properties']['energy'] = {}
        if 'hvacs' not in model_dict['properties']['energy']:
            model_dict['properties']['energy']['hvacs'] = []
        
        existing_hvac_ids = set()
        for h in model_dict['properties']['energy']['hvacs']:
            if isinstance(h, dict) and 'identifier' in h:
                existing_hvac_ids.add(h['identifier'])
        
        for hvac_id, hvac_data in hvac_library.items():
            if hvac_id not in existing_hvac_ids:
                model_dict['properties']['energy']['hvacs'].append(hvac_data)
                print("Added HVAC to model library: {}".format(hvac_id[:40]))
    
    # =========================================================================
    # Step 6: GDS Hub Integration - Apply PV, SHW, IDF (v7)
    # =========================================================================
    report_lines.append("")
    report_lines.append("--- GDS Hub Integration ---")
    
    # 6a: Apply PV properties from Hub
    pv_config = load_hub_pv_config()
    pv_count = 0
    pv_shade_names = []
    if pv_config:
        pv_count, pv_shade_names = apply_pv_to_model_dict(model_dict, pv_config)
        if pv_count > 0:
            report_lines.append("PV: Applied to {} shades ({:.1f}% eff)".format(
                pv_count, pv_config.get('efficiency', 0) * 100))
        else:
            report_lines.append("PV: Config found but no shades available")
    else:
        report_lines.append("PV: Not configured in Hub")
    
    # 6b: Apply SHW system from Hub
    shw_config = load_hub_shw_config()
    shw_applied = False
    shw_report = ""
    if shw_config:
        shw_applied, shw_report = apply_shw_to_model_dict(model_dict, shw_config)
        report_lines.append(shw_report if shw_applied else "SHW: Failed to apply")
    else:
        report_lines.append("SHW: Not configured in Hub")
    
    # 6c: Inject IDF from Hub (Battery, Wind)
    idf_string = load_hub_idf_injection()
    idf_injected = False
    idf_report = ""
    if idf_string:
        idf_injected, idf_report = inject_idf_to_model_dict(model_dict, idf_string)
        report_lines.append(idf_report if idf_injected else "IDF: Failed to inject")
    else:
        report_lines.append("IDF: No Battery/Wind in Hub")
    
    report_lines.append("---------------------------")
    
    # Step 7: Write to file
    try:
        with open(output_path, 'w') as f:
            json.dump(model_dict, f, indent=2)
        
        report_lines.append("")
        report_lines.append("=" * 40)
        report_lines.append("SUMMARY")
        report_lines.append("=" * 40)
        report_lines.append("Envelope: {} faces, {} apertures, {} doors".format(
            total_faces_modified, total_apertures_modified, total_doors_modified))
        report_lines.append("HVAC: {} rooms assigned".format(total_hvac_modified))
        report_lines.append("Shading: {} devices".format(shade_count))
        report_lines.append("PV: {} shades".format(pv_count))
        report_lines.append("SHW: {}".format("Applied" if shw_applied else "Not applied"))
        report_lines.append("IDF: {}".format("Injected" if idf_injected else "Not injected"))
        
        if construction_library:
            report_lines.append("")
            report_lines.append("Added {} constructions to model library:".format(len(construction_library)))
            for constr_id in construction_library.keys():
                report_lines.append("  - {}".format(constr_id))
        
        if modifier_library:
            report_lines.append("")
            report_lines.append("Added {} modifiers to model library:".format(len(modifier_library)))
            for mod_id in modifier_library.keys():
                report_lines.append("  - {}".format(mod_id))
        
        if total_hvac_modified > 0:
            report_lines.append("")
            report_lines.append("HVAC Systems ({} systems, {} rooms):".format(len(hvac_library), total_hvac_modified))
            for sys_name, sys_dict in hvac_library.items():
                room_count = sum(1 for r_id, s_name in room_hvac_assignments.items() if s_name == sys_name)
                report_lines.append("  - {} ({}) -> {} rooms".format(sys_name, sys_dict.get('type', 'Unknown'), room_count))
        
        report_lines.append("")
        report_lines.append("Saved to: {}".format(output_path))
        report_lines.append("")
        report_lines.append("Connect hbjson_path to HB Load Objects")
        
        return output_path, "\n".join(report_lines)
    
    except Exception as e:
        report_lines.append("=" * 40)
        report_lines.append("ERROR saving file: {}".format(str(e)))
        return "", "\n".join(report_lines)


# ============ MAIN EXECUTION ============

gds_path = None
try:
    if _gds_library:
        gds_path = _gds_library
except:
    pass

preview_name = "GDS envelope preview"
try:
    if _preview_name_:
        preview_name = _preview_name_
except:
    pass

try:
    sc.sticky[COMPONENT_KEY] = ghenv.Component
except:
    pass

# Handle _model input
model = None
try:
    if _model is not None:
        if hasattr(_model, 'rooms'):
            model = _model
        elif hasattr(_model, '__iter__'):
            for item in _model:
                if hasattr(item, 'rooms'):
                    model = item
                    break
except:
    pass

# Handle optional output path
user_output_path = None
try:
    if _output_path_:
        user_output_path = _output_path_
except:
    pass

# Initialize outputs
hbjson_path = None
out_report = ""

if model is None:
    out_report = "Connect HB Model to _model"
else:
    gds_parser = GDSLibraryParser(gds_path)
    
    prev_run = sc.sticky.get(RUN_STATE_KEY, False)
    curr_run = bool(_run)
    sc.sticky[RUN_STATE_KEY] = curr_run
    rising_edge = curr_run and not prev_run
    
    # =========================================================================
    # Get modifications and flags
    # =========================================================================
    if STORAGE_KEY in sc.sticky:
        stored = sc.sticky[STORAGE_KEY]
        modified_faces = stored.get('faces', {})
        modified_apertures = stored.get('apertures', {})
        modified_doors = stored.get('doors', {})
        shading_config = stored.get('shading', {})
        hvac_systems = stored.get('hvac_systems', {})
        room_hvac_assignments = stored.get('room_hvac_assignments', {})
        force_update = stored.get('force_update', False)
        
        if force_update:
            stored['force_update'] = False
            sc.sticky[STORAGE_KEY] = stored
    else:
        modified_faces = {}
        modified_apertures = {}
        modified_doors = {}
        shading_config = {}
        hvac_systems = {}
        room_hvac_assignments = {}
        force_update = False
    
    release_output = sc.sticky.get(RELEASE_OUTPUT_KEY, False)
    if release_output:
        sc.sticky[RELEASE_OUTPUT_KEY] = False
    
    # =========================================================================
    # CASE 1: Rising edge - ONLY open UI, never generate file
    # =========================================================================
    if rising_edge:
        if DIALOG_KEY in sc.sticky and sc.sticky[DIALOG_KEY] is not None:
            try:
                existing = sc.sticky[DIALOG_KEY]
                if existing.Visible:
                    existing.BringToFront()
                    out_report = "Editor already open - brought to front"
                else:
                    editor = SurfacePropertyEditor()
                    editor.initialize(model, gds_parser, preview_name)
                    editor.Owner = Rhino.UI.RhinoEtoApp.MainWindow
                    sc.sticky[DIALOG_KEY] = editor
                    editor.Show()
                    out_report = "Editor opened"
            except:
                editor = SurfacePropertyEditor()
                editor.initialize(model, gds_parser, preview_name)
                editor.Owner = Rhino.UI.RhinoEtoApp.MainWindow
                sc.sticky[DIALOG_KEY] = editor
                editor.Show()
                out_report = "Editor opened"
        else:
            editor = SurfacePropertyEditor()
            editor.initialize(model, gds_parser, preview_name)
            editor.Owner = Rhino.UI.RhinoEtoApp.MainWindow
            sc.sticky[DIALOG_KEY] = editor
            editor.Show()
            out_report = "Editor opened"
        
        hbjson_path = None
    
    # =========================================================================
    # CASE 2: force_update=True - User clicked Apply button, generate file
    # =========================================================================
    elif force_update:
        output_file = get_output_filepath(user_output_path)
        generated_path = None
        
        if modified_faces or modified_apertures or modified_doors or shading_config or room_hvac_assignments:
            # Build and save modified model (includes doors, shading and HVAC)
            generated_path, detail_report = build_modified_model_file(
                model, modified_faces, modified_apertures, modified_doors, shading_config, hvac_systems, room_hvac_assignments, gds_parser, output_file)
            
            if generated_path:
                sc.sticky[MODEL_HASH_KEY] = get_model_hash(model)
                sc.sticky[LAST_MODIFICATIONS_KEY] = get_modifications_hash(modified_faces, modified_apertures, modified_doors)
                sc.sticky[OUTPUT_PATH_KEY] = generated_path
                out_report = detail_report
        else:
            model_dict = model.to_dict()
            
            try:
                with open(output_file, 'w') as f:
                    json.dump(model_dict, f, indent=2)
                
                generated_path = output_file
                sc.sticky[MODEL_HASH_KEY] = get_model_hash(model)
                sc.sticky[LAST_MODIFICATIONS_KEY] = get_modifications_hash(modified_faces, modified_apertures, modified_doors)
                sc.sticky[OUTPUT_PATH_KEY] = generated_path
                
                face_count = sum(len(room_dict.get('faces', [])) 
                               for room_dict in model_dict.get('rooms', []))
                ap_count = sum(len(face_dict.get('apertures', [])) 
                             for room_dict in model_dict.get('rooms', [])
                             for face_dict in room_dict.get('faces', []))
                door_count = sum(len(face_dict.get('doors', [])) 
                               for room_dict in model_dict.get('rooms', [])
                               for face_dict in room_dict.get('faces', []))
                
                report_lines = [
                    "Original Model Saved (No Modifications)",
                    "=" * 40,
                    "Rooms: {}".format(len(model_dict.get('rooms', []))),
                    "Faces: {}".format(face_count),
                    "Apertures: {}".format(ap_count),
                    "Doors: {}".format(door_count),
                    "",
                    "Saved to: {}".format(output_file)
                ]
                out_report = "\n".join(report_lines)
            
            except Exception as e:
                generated_path = None
                out_report = "ERROR saving model: {}".format(str(e))
        
        if release_output and generated_path:
            hbjson_path = generated_path
            out_report += "\n\n>>> RUNNING: Output sent to downstream components <<<"
        else:
            hbjson_path = None
            if generated_path:
                out_report += "\n\nFile saved. Click 'Save & Run' to trigger simulation."
    
    # =========================================================================
    # CASE 3: No action - return None, file ready for manual trigger
    # =========================================================================
    else:
        cached_path = sc.sticky.get(OUTPUT_PATH_KEY, None)
        
        if cached_path and os.path.exists(cached_path):
            current_model_hash = get_model_hash(model)
            stored_model_hash = sc.sticky.get(MODEL_HASH_KEY, None)
            
            if current_model_hash != stored_model_hash:
                out_report = "Input model changed. Click _run to open the refiner and re-apply."
                hbjson_path = None
            else:
                out_report = "File ready: {}\n\nClick _run to modify, or 'Save & Run' to re-trigger.".format(cached_path)
                hbjson_path = None
        else:
            out_report = "Set _run=True to open editor"
            hbjson_path = None

# Outputs
report = out_report
# hbjson_path is set above (None or path)