# -*- coding: utf-8 -*-
"""
Geometry Helper Functions
=========================

Functions for creating apertures, doors, and other geometric operations.

Note: This module requires RhinoCommon and will fail to import outside of Rhino.

Usage:
    from gds.utils.geometry import create_coplanar_aperture_by_ratio
"""

import math

# Try to import Rhino geometry
try:
    import Rhino.Geometry as rg
    RHINO_AVAILABLE = True
except ImportError:
    RHINO_AVAILABLE = False
    rg = None


def _check_rhino():
    """Check if Rhino is available."""
    if not RHINO_AVAILABLE:
        raise RuntimeError("Rhino.Geometry not available. This module only works in Rhino.")


# ==============================================================================
# APERTURE CREATION
# ==============================================================================

def create_coplanar_aperture_by_ratio(face_brep, ratio):
    """Create an aperture (window) surface on a face by window-to-wall ratio.
    
    Args:
        face_brep: The face Brep to add aperture to
        ratio: Window-to-wall ratio (0-1)
    
    Returns:
        Tuple of (aperture_brep, width, height) or (None, 0, 0) on failure
    """
    _check_rhino()
    
    try:
        srf = face_brep.Faces[0]
        amp = rg.AreaMassProperties.Compute(face_brep)
        if not amp:
            return None, 0, 0
        
        face_area = amp.Area
        centroid = amp.Centroid
        
        rc, u, v = srf.ClosestPoint(centroid)
        if not rc:
            u = (srf.Domain(0).T0 + srf.Domain(0).T1) / 2.0
            v = (srf.Domain(1).T0 + srf.Domain(1).T1) / 2.0
        
        rc, frame = srf.FrameAt(u, v)
        if not rc:
            return None, 0, 0
        
        center_pt = frame.Origin
        normal = frame.ZAxis
        x_axis = frame.XAxis
        y_axis = frame.YAxis
        
        # Orient axes for vertical walls (keep Y pointing up)
        if abs(normal.Z) < 0.7:
            z_world = rg.Vector3d.ZAxis
            z_in_plane = z_world - normal * (z_world * normal)
            if z_in_plane.Length > 0.01:
                z_in_plane.Unitize()
                y_axis = z_in_plane
                x_axis = rg.Vector3d.CrossProduct(y_axis, normal)
                x_axis.Unitize()
        
        local_plane = rg.Plane(center_pt, x_axis, y_axis)
        bb = face_brep.GetBoundingBox(local_plane)
        face_width = bb.Max.X - bb.Min.X
        face_height = bb.Max.Y - bb.Min.Y
        
        if face_width < 0.01:
            face_width = 1.0
        if face_height < 0.01:
            face_height = 1.0
        
        aperture_area = face_area * ratio
        aspect = face_width / face_height
        ap_height = math.sqrt(aperture_area / aspect)
        ap_width = aperture_area / ap_height if ap_height > 0.01 else math.sqrt(aperture_area)
        
        max_width = face_width * 0.95
        max_height = face_height * 0.95
        ap_width = min(max(ap_width, 0.1), max_width)
        ap_height = min(max(ap_height, 0.1), max_height)
        
        plane = rg.Plane(center_pt, x_axis, y_axis)
        rect = rg.Rectangle3d(plane,
                              rg.Interval(-ap_width/2.0, ap_width/2.0),
                              rg.Interval(-ap_height/2.0, ap_height/2.0))
        
        curve = rect.ToNurbsCurve()
        aperture_breps = rg.Brep.CreatePlanarBreps(curve, 0.001)
        
        if aperture_breps and len(aperture_breps) > 0:
            return aperture_breps[0], ap_width, ap_height
            
    except Exception as e:
        print("Aperture by ratio error: {}".format(e))
    return None, 0, 0


def create_coplanar_aperture_by_dims(face_brep, width, height):
    """Create an aperture (window) surface on a face by explicit dimensions.
    
    Args:
        face_brep: The face Brep to add aperture to
        width: Aperture width in meters
        height: Aperture height in meters
    
    Returns:
        Tuple of (aperture_brep, actual_width, actual_height) or (None, 0, 0) on failure
    """
    _check_rhino()
    
    try:
        srf = face_brep.Faces[0]
        amp = rg.AreaMassProperties.Compute(face_brep)
        if not amp:
            return None, 0, 0
        
        centroid = amp.Centroid
        rc, u, v = srf.ClosestPoint(centroid)
        if not rc:
            u = (srf.Domain(0).T0 + srf.Domain(0).T1) / 2.0
            v = (srf.Domain(1).T0 + srf.Domain(1).T1) / 2.0
        
        rc, frame = srf.FrameAt(u, v)
        if not rc:
            return None, 0, 0
        
        center_pt = frame.Origin
        normal = frame.ZAxis
        x_axis = frame.XAxis
        y_axis = frame.YAxis
        
        if abs(normal.Z) < 0.7:
            z_world = rg.Vector3d.ZAxis
            z_in_plane = z_world - normal * (z_world * normal)
            if z_in_plane.Length > 0.01:
                z_in_plane.Unitize()
                y_axis = z_in_plane
                x_axis = rg.Vector3d.CrossProduct(y_axis, normal)
                x_axis.Unitize()
        
        local_plane = rg.Plane(center_pt, x_axis, y_axis)
        bb = face_brep.GetBoundingBox(local_plane)
        face_width = bb.Max.X - bb.Min.X
        face_height = bb.Max.Y - bb.Min.Y
        
        if face_width < 0.01:
            face_width = 1.0
        if face_height < 0.01:
            face_height = 1.0
        
        ap_width = float(width)
        ap_height = float(height)
        max_width = face_width * 0.95
        max_height = face_height * 0.95
        ap_width = min(max(ap_width, 0.1), max_width)
        ap_height = min(max(ap_height, 0.1), max_height)
        
        plane = rg.Plane(center_pt, x_axis, y_axis)
        rect = rg.Rectangle3d(plane,
                              rg.Interval(-ap_width/2.0, ap_width/2.0),
                              rg.Interval(-ap_height/2.0, ap_height/2.0))
        
        curve = rect.ToNurbsCurve()
        aperture_breps = rg.Brep.CreatePlanarBreps(curve, 0.001)
        
        if aperture_breps and len(aperture_breps) > 0:
            return aperture_breps[0], ap_width, ap_height
            
    except Exception as e:
        print("Aperture by dims error: {}".format(e))
    return None, 0, 0


# ==============================================================================
# DOOR CREATION
# ==============================================================================

def create_coplanar_door_by_ratio(face_brep, ratio, sill_height=0.0):
    """Create a door surface on a face by door-to-wall ratio.
    
    Args:
        face_brep: The face Brep to add door to
        ratio: Door-to-wall ratio (0-1)
        sill_height: Height of door sill from floor (default 0)
    
    Returns:
        Tuple of (door_brep, width, height) or (None, 0, 0) on failure
    """
    _check_rhino()
    
    try:
        srf = face_brep.Faces[0]
        amp = rg.AreaMassProperties.Compute(face_brep)
        if not amp:
            return None, 0, 0
        
        face_area = amp.Area
        centroid = amp.Centroid
        
        rc, u, v = srf.ClosestPoint(centroid)
        if not rc:
            u = (srf.Domain(0).T0 + srf.Domain(0).T1) / 2.0
            v = (srf.Domain(1).T0 + srf.Domain(1).T1) / 2.0
        
        rc, frame = srf.FrameAt(u, v)
        if not rc:
            return None, 0, 0
        
        center_pt = frame.Origin
        normal = frame.ZAxis
        x_axis = frame.XAxis
        y_axis = frame.YAxis
        
        if abs(normal.Z) < 0.7:
            z_world = rg.Vector3d.ZAxis
            z_in_plane = z_world - normal * (z_world * normal)
            if z_in_plane.Length > 0.01:
                z_in_plane.Unitize()
                y_axis = z_in_plane
                x_axis = rg.Vector3d.CrossProduct(y_axis, normal)
                x_axis.Unitize()
        
        local_plane = rg.Plane(center_pt, x_axis, y_axis)
        bb = face_brep.GetBoundingBox(local_plane)
        face_width = bb.Max.X - bb.Min.X
        face_height = bb.Max.Y - bb.Min.Y
        face_bottom = bb.Min.Y
        
        if face_width < 0.01:
            face_width = 1.0
        if face_height < 0.01:
            face_height = 1.0
        
        door_area = face_area * ratio
        door_height = min(face_height * 0.9, 2.4)
        door_width = door_area / door_height if door_height > 0.01 else math.sqrt(door_area)
        
        max_width = face_width * 0.95
        max_height = face_height * 0.95 - sill_height
        door_width = min(max(door_width, 0.6), max_width)
        door_height = min(max(door_height, 1.8), max_height)
        
        door_center_y = face_bottom + sill_height + door_height / 2.0
        door_center = center_pt + y_axis * (door_center_y - (bb.Min.Y + bb.Max.Y) / 2.0)
        
        plane = rg.Plane(door_center, x_axis, y_axis)
        rect = rg.Rectangle3d(plane,
                              rg.Interval(-door_width/2.0, door_width/2.0),
                              rg.Interval(-door_height/2.0, door_height/2.0))
        
        curve = rect.ToNurbsCurve()
        door_breps = rg.Brep.CreatePlanarBreps(curve, 0.001)
        
        if door_breps and len(door_breps) > 0:
            return door_breps[0], door_width, door_height
            
    except Exception as e:
        print("Door by ratio error: {}".format(e))
    return None, 0, 0


# ==============================================================================
# GENERAL GEOMETRY UTILITIES
# ==============================================================================

def get_face_normal(face_brep):
    """Get the normal vector of a face.
    
    Args:
        face_brep: Face Brep
    
    Returns:
        Rhino.Geometry.Vector3d or None
    """
    _check_rhino()
    
    try:
        srf = face_brep.Faces[0]
        u = (srf.Domain(0).T0 + srf.Domain(0).T1) / 2.0
        v = (srf.Domain(1).T0 + srf.Domain(1).T1) / 2.0
        return srf.NormalAt(u, v)
    except:
        return None


def get_face_area(face_brep):
    """Get the area of a face.
    
    Args:
        face_brep: Face Brep
    
    Returns:
        Area in square meters, or 0 on failure
    """
    _check_rhino()
    
    try:
        amp = rg.AreaMassProperties.Compute(face_brep)
        if amp:
            return amp.Area
    except:
        pass
    return 0
