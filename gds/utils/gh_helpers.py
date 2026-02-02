# -*- coding: utf-8 -*-
"""
Grasshopper Helper Functions
============================

Functions for interacting with Grasshopper components (sliders, panels, buttons, etc.)

Note: This module requires the Grasshopper environment and will fail to import
outside of Rhino/Grasshopper.

Usage:
    from gds.utils.gh_helpers import set_document, find_objs, set_slider_value
    
    # In your GhPython component:
    from gds.utils import gh_helpers
    gh_helpers.set_document(ghenv.Component.OnPingDocument())
"""

# Try to import Grasshopper dependencies
try:
    import Grasshopper.Kernel as gk
    import Grasshopper.Kernel.Types as gkt
    GH_AVAILABLE = True
except ImportError:
    GH_AVAILABLE = False
    gk = None
    gkt = None

# Module-level reference to GH document
_DOC = None


def set_document(doc):
    """Set the GH document reference for helper functions.
    
    Args:
        doc: Grasshopper document (from ghenv.Component.OnPingDocument())
    """
    global _DOC
    _DOC = doc


def get_document():
    """Get the current GH document reference.
    
    Returns:
        Grasshopper document or None
    """
    return _DOC


def _check_gh():
    """Check if GH is available and document is set."""
    if not GH_AVAILABLE:
        raise RuntimeError("Grasshopper SDK not available. This module only works in Rhino/Grasshopper.")
    if _DOC is None:
        raise RuntimeError("GH document not set. Call set_document(ghenv.Component.OnPingDocument()) first.")


# ==============================================================================
# SCHEDULING
# ==============================================================================

def schedule(action):
    """Schedule an action to run on the next GH solution.
    
    Args:
        action: Callable to execute
    """
    doc = get_document()
    if not doc or not GH_AVAILABLE:
        return
    
    def cb(doc):
        try:
            action()
        except Exception as e:
            print("Schedule error: {}".format(e))
    
    doc.ScheduleSolution(1, gk.GH_Document.GH_ScheduleDelegate(cb))


# ==============================================================================
# FINDING COMPONENTS
# ==============================================================================

def find_objs(type_name, nickname):
    """Find GH objects by type name and nickname.
    
    Args:
        type_name: GH component type name (e.g., "GH_NumberSlider", "GH_Panel")
        nickname: Component nickname to match
    
    Returns:
        List of matching objects
    """
    doc = get_document()
    hits = []
    if not doc:
        return hits
    try:
        for obj in doc.Objects:
            if obj and obj.NickName == nickname and obj.GetType().Name == type_name:
                hits.append(obj)
    except:
        pass
    return hits


# ==============================================================================
# SLIDERS
# ==============================================================================

def get_slider_info(name, default_val=1.0):
    """Get information about a number slider.
    
    Args:
        name: Slider nickname
        default_val: Default value if slider not found
    
    Returns:
        Tuple of (min, max, current_value, decimal_places)
    """
    sliders = find_objs("GH_NumberSlider", name)
    if not sliders:
        return (0.0, 10.0, float(default_val), 0)
    sld = sliders[0]
    try:
        mn = float(sld.Slider.Minimum)
        mx = float(sld.Slider.Maximum)
        val = float(sld.CurrentValue) if hasattr(sld, "CurrentValue") else float(sld.Slider.Value)
        dec = sld.Slider.DecimalPlaces if hasattr(sld.Slider, 'DecimalPlaces') else 0
        return (mn, mx, val, dec)
    except:
        return (0.0, 10.0, float(default_val), 0)


def set_slider_value(name, value):
    """Set a slider's value.
    
    Args:
        name: Slider nickname
        value: New value to set
    """
    targets = find_objs("GH_NumberSlider", name)
    if not targets:
        return
    v = float(value)
    def do():
        for sld in targets:
            try:
                mn = float(sld.Slider.Minimum)
                mx = float(sld.Slider.Maximum)
                sld.SetSliderValue(max(mn, min(mx, v)))
                sld.ExpireSolution(True)
            except:
                pass
    schedule(do)


# ==============================================================================
# TOGGLES
# ==============================================================================

def get_toggles_aggregate(name):
    """Get the aggregate state of toggles with a given name.
    
    Args:
        name: Toggle nickname
    
    Returns:
        True if all toggles are on, False if all are off, None if mixed
    """
    tgs = find_objs("GH_BooleanToggle", name)
    if not tgs:
        return False
    states = []
    for t in tgs:
        if hasattr(t, 'Value'):
            states.append(bool(t.Value))
    if not states:
        return False
    if all(states):
        return True
    if not any(states):
        return False
    return None


def set_toggle_value(name, value):
    """Set a toggle's value.
    
    Args:
        name: Toggle nickname
        value: Boolean value to set
    """
    targets = find_objs("GH_BooleanToggle", name)
    if not targets:
        return
    def do():
        for t in targets:
            try:
                t.Value = bool(value)
                t.ExpireSolution(True)
            except:
                pass
    schedule(do)


# ==============================================================================
# PANELS
# ==============================================================================

def _panel_display_text(panel, max_items=200):
    """Get display text from a panel.
    
    Args:
        panel: GH Panel object
        max_items: Maximum number of items to show per branch
    
    Returns:
        Unicode string of panel contents
    """
    try:
        if panel and panel.SourceCount > 0 and panel.VolatileData is not None:
            dt = panel.VolatileData
            lines = []
            for path in dt.Paths:
                branch = dt.get_Branch(path)
                if not branch:
                    continue
                vals = []
                for i, goo in enumerate(branch):
                    if i >= max_items:
                        vals.append(u"...(+{} more)".format(len(branch) - max_items))
                        break
                    v = getattr(goo, "Value", None)
                    vals.append(unicode(v) if v is not None else unicode(goo))
                lines.append(u"{}: {}".format(path, u", ".join(vals)))
            return u"\n".join(lines) if lines else u""
        elif panel:
            return unicode(panel.UserText or u"")
        return u""
    except Exception as e:
        return u"Error: {}".format(e)


def get_output_panels_text(name, max_items=200):
    """Get text from output panels.
    
    Args:
        name: Panel nickname
        max_items: Maximum items to show per branch
    
    Returns:
        Combined text from all matching panels
    """
    pans = find_objs("GH_Panel", name)
    if not pans:
        return u""
    chunks = []
    for i, p in enumerate(pans, 1):
        txt = _panel_display_text(p, max_items)
        header = u"— {} #{} —".format(name, i) if len(pans) > 1 else u""
        if txt:
            chunks.append((header + "\n" if header else u"") + txt)
    return u"\n\n".join(chunks) if chunks else u""


def get_panel_text(name):
    """Get user-entered text from a panel.
    
    Args:
        name: Panel nickname
    
    Returns:
        Panel's UserText content
    """
    pans = find_objs("GH_Panel", name)
    if not pans:
        return u""
    try:
        if pans[0] and hasattr(pans[0], 'UserText'):
            return unicode(pans[0].UserText or u"")
    except:
        pass
    return u""


def set_panel_text(name, text):
    """Set text in a panel.
    
    Args:
        name: Panel nickname
        text: Text to set
    """
    targets = find_objs("GH_Panel", name)
    if not targets:
        return
    def do():
        for p in targets:
            try:
                p.UserText = text
                p.ExpireSolution(True)
            except:
                pass
    schedule(do)


# ==============================================================================
# BUTTONS
# ==============================================================================

def press_button(name):
    """Simulate pressing a button component.
    
    Args:
        name: Button nickname
    """
    targets = find_objs("GH_ButtonObject", name)
    if not targets:
        return
    def press():
        for btn in targets:
            try:
                btn.ButtonDown = True
                btn.ExpireSolution(True)
            except:
                pass
    def release():
        for btn in targets:
            try:
                btn.ButtonDown = False
                btn.ExpireSolution(True)
            except:
                pass
    schedule(press)
    schedule(release)


# ==============================================================================
# DATA COMPONENTS
# ==============================================================================

def set_bool_data_component(nickname, bool_list):
    """Set boolean values to a Data component.
    
    Args:
        nickname: Component nickname
        bool_list: List of boolean values
    
    Returns:
        True if successful, False otherwise
    """
    doc = get_document()
    if not doc or not GH_AVAILABLE:
        return False
    
    targets = []
    for obj in doc.Objects:
        obj_type = obj.GetType().Name
        if obj.NickName == nickname and ("Param_" in obj_type or "Data" in obj_type):
            targets.append(obj)
    
    if not targets or not bool_list:
        return False
    
    def do():
        for comp in targets:
            try:
                comp.PersistentData.Clear()
                comp.ClearData()
                for val in bool_list:
                    comp.PersistentData.Append(gkt.GH_Boolean(bool(val)))
                comp.ExpireSolution(True)
            except Exception as ex:
                print("Error setting bool data: {}".format(ex))
    schedule(do)
    return True
