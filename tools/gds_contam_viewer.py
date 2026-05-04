# -*- coding: utf-8 -*-
"""
GDS CONTAM Results Viewer
=========================
CPython script: parses CONTAM .sim binary + .prj metadata,
generates an interactive HTML dashboard.

USAGE:
  python gds_contam_viewer.py <prj_file>            # looks for .sim alongside
  python gds_contam_viewer.py <sim_file>             # infers .prj from name
  python gds_contam_viewer.py <prj_file> <sim_file>  # explicit paths
  python gds_contam_viewer.py --from-json <summary.json>  # from pipeline JSON

OUTPUT:
  <basename>_dashboard.html  (self-contained, opens in browser)

REQUIREMENTS:
  Python 3.8+, no external packages (uses Plotly CDN in HTML)
"""

import struct
import os
import sys
import json
import math
import webbrowser
from datetime import datetime, timedelta
from collections import OrderedDict

# ============================================================================
#  PRJ PARSER (extract zone names, species, flow elements, levels)
# ============================================================================

class PRJParser:
    """Minimal parser for CONTAM .prj files — extracts metadata needed
    to label simulation results."""

    def __init__(self, prj_path):
        self.prj_path = prj_path
        self.zones = []         # [{nr, name, vol, T_C, level}, ...]
        self.species = []       # [name, ...]
        self.flow_paths = []    # [{nr, zone_a, zone_b, element}, ...]
        self.flow_elements = [] # [{nr, name, type}, ...]
        self.levels = []        # [{nr, refht, delht, name}, ...]
        self.sim_info = {}      # {start, end, timestep}
        self._parse()

    def _parse(self):
        with open(self.prj_path, 'r', errors='replace') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # ---- Species ----
            # Format: "N ! species:" followed by N entries (each = data line + desc line)
            if line.endswith('! species:'):
                try:
                    n_sp = int(line.split('!')[0].strip())
                except:
                    i += 1; continue
                i += 1
                for _ in range(n_sp):
                    if i >= len(lines):
                        break
                    sp_line = lines[i].strip()
                    if sp_line == '-999':
                        break
                    parts = sp_line.split()
                    if len(parts) >= 2:
                        # Last token is species name
                        sp_name = parts[-1]
                        self.species.append(sp_name)
                    i += 1
                    # Skip description line
                    if i < len(lines) and lines[i].strip() != '-999':
                        i += 1
                continue

            # ---- Levels ----
            # Format: "N ! levels plus icon data:"
            if '! levels' in line and 'icon' in line:
                try:
                    n_lv = int(line.split('!')[0].strip())
                except:
                    i += 1; continue
                i += 1
                for _ in range(n_lv):
                    if i >= len(lines):
                        break
                    lv_line = lines[i].strip()
                    if lv_line == '-999':
                        break
                    parts = lv_line.split()
                    if len(parts) >= 4:
                        # Format: nr refht delht 0 u_rfht u_dlht name
                        self.levels.append({
                            'nr': int(parts[0]),
                            'refht': float(parts[1]),
                            'delht': float(parts[2]),
                            'name': parts[-1] if len(parts) >= 7 else "Level{}".format(parts[0])
                        })
                    i += 1
                continue

            # ---- Zones ----
            # Format: "N ! zones:"
            # Zone line: nr flags ps pc pk pl relHt Vol T0 P0 name color u_Ht u_T u_P u_V ...
            if '! zones:' in line and 'initial' not in line.lower():
                try:
                    n_z = int(line.split('!')[0].strip())
                except:
                    i += 1; continue
                i += 1
                for _ in range(n_z):
                    if i >= len(lines):
                        break
                    z_line = lines[i].strip()
                    if z_line == '-999':
                        break
                    parts = z_line.split()
                    if len(parts) >= 11:
                        # nr=0, flags=1, Vol=7, T0=8, name=10
                        self.zones.append({
                            'nr': int(parts[0]),
                            'flags': int(parts[1]),
                            'vol': float(parts[7]),
                            'T0': float(parts[8]),
                            'name': parts[10],
                        })
                    i += 1
                continue

            # ---- Flow Elements ----
            # Format: "N ! flow elements:"
            if '! flow elements:' in line:
                try:
                    n_fe = int(line.split('!')[0].strip())
                except:
                    i += 1; continue
                i += 1
                for _ in range(n_fe):
                    if i >= len(lines):
                        break
                    fe_line = lines[i].strip()
                    if fe_line == '-999':
                        break
                    parts = fe_line.split()
                    if len(parts) >= 4:
                        # Format: nr icon dtype name
                        self.flow_elements.append({
                            'nr': int(parts[0]),
                            'name': parts[3] if len(parts) >= 4 else parts[-1],
                            'dtype': parts[2],
                        })
                    i += 1
                    # Skip description line
                    if i < len(lines) and lines[i].strip() != '-999':
                        i += 1
                    # Skip type data line(s)
                    if i < len(lines) and lines[i].strip() != '-999':
                        i += 1
                continue

            # ---- Flow Paths ----
            # Format: "N ! flow paths:"
            # Path line: nr flags pzn pzm pe pf pw pa ps pc pld X Y relHt mult ...
            if '! flow paths:' in line:
                try:
                    n_fp = int(line.split('!')[0].strip())
                except:
                    i += 1; continue
                i += 1
                for _ in range(n_fp):
                    if i >= len(lines):
                        break
                    fp_line = lines[i].strip()
                    if fp_line == '-999':
                        break
                    parts = fp_line.split()
                    if len(parts) >= 5:
                        # nr=0, flags=1, pzn=2, pzm=3, pe=4
                        self.flow_paths.append({
                            'nr': int(parts[0]),
                            'flags': int(parts[1]),
                            'zone_n': int(parts[2]),  # from-zone (-1=ambient)
                            'zone_m': int(parts[3]),  # to-zone (-1=ambient)
                            'fe_nr': int(parts[4]),
                        })
                    i += 1
                continue

            i += 1

    def zone_name(self, nr):
        """Get zone name by number (1-indexed). nr<=0 means ambient."""
        if nr <= 0:
            return "Ambient"
        for z in self.zones:
            if z['nr'] == nr:
                return z['name']
        return "Zone{}".format(nr)


# ============================================================================
#  ZONE CONNECTIVITY GRAPH (integrated from contam_prj_parser.py)
# ============================================================================

def _classify_element(dtype, name=""):
    """Classify a flow element into a broad category for colour-coding."""
    d = dtype.lower().strip()
    n = name.lower()
    # dtype-first (authoritative)
    if "leak" in d or "cr_" in d or "test1" in d or "test2" in d:
        return "leakage"
    if d.startswith("dor_") or d == "cr_door":
        return "door"
    if "fan" in d:
        return "fan"
    if "orfc" in d or "qfr" in d:
        return "opening"
    if d.startswith("af_"):
        return "ahs"
    if "qcn" in d or "fcn" in d:
        return "stairwell"
    # name fallback
    if "leak" in n or "crack" in n:
        return "leakage"
    if "door" in n:
        return "door"
    if "fan" in n:
        return "fan"
    return "other"


_BROAD_LABELS = {
    "door": "Door", "leakage": "Leakage / Crack", "fan": "Fan / Mechanical",
    "opening": "Orifice / Opening", "ahs": "AHS (Supply/Exhaust)",
    "stairwell": "Stairwell", "other": "Other",
}


def build_connectivity_section(prj):
    """Build the Zone Connectivity section HTML+JS from a PRJParser instance.

    Returns (section_html, section_js) strings to embed in the dashboard.
    """
    import json as _json

    # Build element lookup: fe_nr -> {dtype, name, broad}
    fe_map = {}
    for fe in prj.flow_elements:
        broad = _classify_element(fe.get('dtype', ''), fe.get('name', ''))
        fe_map[fe['nr']] = {
            'dtype': fe.get('dtype', '?'),
            'name': fe.get('name', '?'),
            'broad': broad,
        }

    # Nodes
    nodes = [{"id": 0, "name": "Ambient", "volume": 0, "type": "ambient"}]
    for z in prj.zones:
        nodes.append({
            "id": z['nr'], "name": z['name'],
            "volume": z.get('vol', 0), "type": "zone",
        })

    # Links
    links = []
    elem_summary = {}
    for fp in prj.flow_paths:
        src = max(fp['zone_n'], 0)  # normalize -1 → 0
        tgt = max(fp['zone_m'], 0)
        fe = fe_map.get(fp['fe_nr'], {})
        broad = fe.get('broad', 'other')
        elem_summary[broad] = elem_summary.get(broad, 0) + 1
        links.append({
            "source": src, "target": tgt,
            "element_name": fe.get('name', '?'),
            "element_dtype": fe.get('dtype', '?'),
            "broad": broad,
        })

    graph_data = _json.dumps({
        "nodes": nodes, "links": links,
        "element_summary": elem_summary,
    })

    # Door leakage detection
    door_links = [l for l in links if l['broad'] == 'door']
    leak_links = [l for l in links if l['broad'] == 'leakage']
    door_pairs = set()
    for l in door_links:
        door_pairs.add((min(l['source'], l['target']), max(l['source'], l['target'])))
    leak_pairs = set()
    for l in leak_links:
        leak_pairs.add((min(l['source'], l['target']), max(l['source'], l['target'])))

    node_name = {0: "Ambient"}
    for z in prj.zones:
        node_name[z['nr']] = z['name']

    leak_det_rows = ""
    for pair in sorted(door_pairs):
        n1 = node_name.get(pair[0], "Z{}".format(pair[0]))
        n2 = node_name.get(pair[1], "Z{}".format(pair[1]))
        has_leak = pair in leak_pairs
        badge_cls = "badge-found" if has_leak else "badge-missing"
        badge_txt = "+ leakage" if has_leak else "no leakage"
        leak_det_rows += (
            '<div style="font-size:0.8em;margin-bottom:4px;">'
            '{n1} ↔ {n2} '
            '<span class="conn-badge {cls}">{txt}</span>'
            '</div>\n'
        ).format(n1=n1, n2=n2, cls=badge_cls, txt=badge_txt)

    # Stats
    n_zones = len(prj.zones)
    n_paths = len(prj.flow_paths)
    n_amb = sum(1 for l in links if l['source'] == 0 or l['target'] == 0)

    # Legend rows
    legend_html = ""
    for broad, label in _BROAD_LABELS.items():
        cnt = elem_summary.get(broad, 0)
        if cnt == 0:
            continue
        legend_html += (
            '<div class="conn-legend-item">'
            '<span class="conn-swatch" data-broad="{b}"></span>'
            '<span>{label}</span>'
            '<span class="conn-count">{cnt}</span>'
            '</div>\n'
        ).format(b=broad, label=label, cnt=cnt)

    # Filter buttons
    filter_btns = '<button class="conn-filter active" data-f="all">All</button>\n'
    for broad, label in _BROAD_LABELS.items():
        if elem_summary.get(broad, 0) > 0:
            filter_btns += (
                '<button class="conn-filter" data-f="{b}">{label}</button>\n'
            ).format(b=broad, label=label)

    section_html = """
  <div class="section" id="connectivity-section">
    <div class="section-title">Zone Connectivity Graph</div>
    <div style="display:flex;gap:0;">
      <div style="flex:1;min-height:550px;position:relative;" id="conn-graph-wrap">
        <svg id="conn-svg" style="width:100%;height:550px;background:transparent;"></svg>
        <div id="conn-tooltip" class="conn-tooltip"></div>
      </div>
      <div style="width:280px;padding:12px 16px;font-size:0.82em;overflow-y:auto;max-height:550px;border-left:1px solid var(--border-dim,#333);">
        <div style="font-weight:600;margin-bottom:8px;color:var(--text-secondary,#58a6ff);">
          {n_zones} zones · {n_paths} paths · {n_amb} ambient
        </div>
        <div style="font-weight:600;margin:12px 0 6px;text-transform:uppercase;letter-spacing:0.5px;font-size:0.85em;color:var(--text-secondary,#58a6ff);">Edge Types</div>
        {legend_html}
        <div style="font-weight:600;margin:14px 0 6px;text-transform:uppercase;letter-spacing:0.5px;font-size:0.85em;color:var(--text-secondary,#58a6ff);">Filter</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px;">
          {filter_btns}
        </div>
        <div style="font-weight:600;margin:14px 0 6px;text-transform:uppercase;letter-spacing:0.5px;font-size:0.85em;color:var(--text-secondary,#58a6ff);">Door Leakage</div>
        {leak_det_rows}
      </div>
    </div>
  </div>
""".format(
        n_zones=n_zones, n_paths=n_paths, n_amb=n_amb,
        legend_html=legend_html, filter_btns=filter_btns,
        leak_det_rows=leak_det_rows if leak_det_rows else
            '<div style="font-size:0.8em;color:#888;">No door paths in model.</div>',
    )

    section_js = """
  // ---- Zone Connectivity Graph ----
  setTimeout(function() {{
    var DATA = {graph_data};
    var COLORS = {{
      door:'#ff7b72', leakage:'#d2a8ff', fan:'#79c0ff',
      opening:'#56d364', ahs:'#ffa657', stairwell:'#f778ba', other:'#8b949e'
    }};
    var LABELS = {broad_labels};
    var svg = document.getElementById('conn-svg');
    var tooltip = document.getElementById('conn-tooltip');
    if (!svg || !DATA.nodes.length) return;
    var NS = 'http://www.w3.org/2000/svg';
    var wrap = svg.parentElement;
    var W = wrap.offsetWidth || wrap.clientWidth || 700;
    var H = 550;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    var cx = W / 2, cy = H / 2;

    // Init node positions
    var nodeMap = {{}};
    DATA.nodes.forEach(function(n, i) {{
      var angle = (i / DATA.nodes.length) * 2 * Math.PI;
      var r = Math.min(cx, cy) * 0.55;
      nodeMap[n.id] = {{
        id:n.id, name:n.name, volume:n.volume, type:n.type,
        x: cx + r * Math.cos(angle) + (Math.random()-0.5)*30,
        y: cy + r * Math.sin(angle) + (Math.random()-0.5)*30,
        vx:0, vy:0, radius: n.type==='ambient'?16:10, _pinned:false
      }};
    }});

    var edgeG = document.createElementNS(NS,'g');
    var nodeG = document.createElementNS(NS,'g');
    svg.appendChild(edgeG); svg.appendChild(nodeG);

    // Edges
    var edgeEls = [];
    DATA.links.forEach(function(lk) {{
      var line = document.createElementNS(NS,'line');
      line.setAttribute('stroke', COLORS[lk.broad]||COLORS.other);
      line.setAttribute('stroke-width','1.4');
      line.setAttribute('stroke-opacity','0.55');
      line.dataset.broad = lk.broad;
      edgeG.appendChild(line);
      edgeEls.push({{el:line, lk:lk}});
    }});

    // Nodes
    var nodeEls = [];
    Object.values(nodeMap).forEach(function(n) {{
      var g = document.createElementNS(NS,'g');
      g.style.cursor='grab';
      var c = document.createElementNS(NS,'circle');
      c.setAttribute('r', n.radius);
      c.setAttribute('fill', n.type==='ambient'?'#f0883e':'#3fb950');
      c.setAttribute('stroke','#0f0f0f'); c.setAttribute('stroke-width','2');
      g.appendChild(c);
      var t = document.createElementNS(NS,'text');
      t.textContent = n.name.length>14 ? n.name.slice(0,12)+'…' : n.name;
      t.setAttribute('fill','#d4d4d4'); t.setAttribute('font-size','10');
      t.setAttribute('font-family','monospace');
      t.setAttribute('text-anchor','middle'); t.setAttribute('dy', n.radius+12);
      g.appendChild(t);
      nodeG.appendChild(g);
      nodeEls.push({{el:g, n:n}});

      g.addEventListener('mouseenter',function(e){{
        var cp=DATA.links.filter(function(l){{return l.source===n.id||l.target===n.id}});
        var tip='<b>'+n.name+'</b>';
        if(n.type==='zone') tip+='<br>Vol: '+n.volume.toFixed(1)+' m³';
        tip+='<br>Paths: '+cp.length;
        tooltip.innerHTML=tip;
        tooltip.style.opacity='1';
      }});
      g.addEventListener('mousemove',function(e){{
        var r=svg.getBoundingClientRect();
        tooltip.style.left=(e.clientX-r.left+12)+'px';
        tooltip.style.top=(e.clientY-r.top+12)+'px';
      }});
      g.addEventListener('mouseleave',function(){{ tooltip.style.opacity='0'; }});

      var dragging=false;
      g.addEventListener('mousedown',function(e){{
        dragging=true; n._pinned=true; g.style.cursor='grabbing'; e.preventDefault();
      }});
      window.addEventListener('mousemove',function(e){{
        if(!dragging) return;
        var r=svg.getBoundingClientRect();
        n.x=e.clientX-r.left; n.y=e.clientY-r.top; n.vx=0; n.vy=0;
      }});
      window.addEventListener('mouseup',function(){{
        if(dragging){{ dragging=false; g.style.cursor='grab';
          setTimeout(function(){{n._pinned=false;}},2000);
        }}
      }});
    }});

    // Filter
    var activeFilter='all';
    document.querySelectorAll('.conn-filter').forEach(function(btn){{
      btn.addEventListener('click',function(){{
        document.querySelectorAll('.conn-filter').forEach(function(b){{b.classList.remove('active')}});
        btn.classList.add('active');
        activeFilter=btn.dataset.f;
        edgeEls.forEach(function(ee){{
          ee.el.setAttribute('stroke-opacity',
            (activeFilter==='all'||ee.lk.broad===activeFilter)?'0.55':'0.06');
        }});
      }});
    }});

    // Swatch colors
    document.querySelectorAll('.conn-swatch').forEach(function(sw){{
      sw.style.background=COLORS[sw.dataset.broad]||COLORS.other;
    }});

    // Physics
    function tick(){{
      var nodes=Object.values(nodeMap);
      nodes.forEach(function(n){{if(!n._pinned){{n.fx=0;n.fy=0;}}}});
      for(var i=0;i<nodes.length;i++){{
        for(var j=i+1;j<nodes.length;j++){{
          var a=nodes[i],b=nodes[j];
          var dx=a.x-b.x,dy=a.y-b.y;
          var dist=Math.sqrt(dx*dx+dy*dy)||1;
          var f=2500/(dist*dist);
          var fx=(dx/dist)*f, fy=(dy/dist)*f;
          if(!a._pinned){{a.fx+=fx;a.fy+=fy;}}
          if(!b._pinned){{b.fx-=fx;b.fy-=fy;}}
        }}
      }}
      DATA.links.forEach(function(lk){{
        var a=nodeMap[lk.source],b=nodeMap[lk.target];
        if(!a||!b) return;
        var dx=b.x-a.x,dy=b.y-a.y;
        var dist=Math.sqrt(dx*dx+dy*dy)||1;
        var f=(dist-100)*0.005;
        var fx=(dx/dist)*f,fy=(dy/dist)*f;
        if(!a._pinned){{a.fx+=fx;a.fy+=fy;}}
        if(!b._pinned){{b.fx-=fx;b.fy-=fy;}}
      }});
      nodes.forEach(function(n){{
        if(n._pinned) return;
        n.fx+=(cx-n.x)*0.003; n.fy+=(cy-n.y)*0.003;
        n.vx=(n.vx+n.fx)*0.87; n.vy=(n.vy+n.fy)*0.87;
        n.x+=n.vx; n.y+=n.vy;
        n.x=Math.max(n.radius,Math.min(W-n.radius,n.x));
        n.y=Math.max(n.radius,Math.min(H-n.radius,n.y));
      }});
      edgeEls.forEach(function(ee){{
        var a=nodeMap[ee.lk.source],b=nodeMap[ee.lk.target];
        if(!a||!b) return;
        ee.el.setAttribute('x1',a.x);ee.el.setAttribute('y1',a.y);
        ee.el.setAttribute('x2',b.x);ee.el.setAttribute('y2',b.y);
      }});
      nodeEls.forEach(function(ne){{
        ne.el.setAttribute('transform','translate('+ne.n.x+','+ne.n.y+')');
      }});
      requestAnimationFrame(tick);
    }}
    tick();
  }}, 100);
""".format(
        graph_data=graph_data,
        broad_labels=_json.dumps(_BROAD_LABELS),
    )

    return section_html, section_js


# ============================================================================
#  SIM FILE PARSER (binary results)
# ============================================================================

class SIMParser:
    """Parse CONTAM .sim binary output files.
    
    The .sim format stores time-series data for zones, paths, and species.
    Structure (CONTAM 3.x):
      Header → repeated timestep records → EOF
      
    Each timestep record contains:
      - timestamp (date/time)
      - zone data: pressure, temperature, species concentrations
      - path data: airflow rates (0→1, 1→0)
    """

    def __init__(self, sim_path, prj):
        self.sim_path = sim_path
        self.prj = prj
        self.n_zones = len(prj.zones)
        self.n_species = len(prj.species)
        self.n_paths = len(prj.flow_paths)
        self.timesteps = []    # list of datetime
        self.zone_data = {}    # zone_name → {pressure:[], temp:[], species_name:[]}
        self.path_data = {}    # path_nr → {flow_0to1:[], flow_1to0:[]}
        self._parse()

    def _parse(self):
        """Parse the binary .sim file."""
        if not os.path.exists(self.sim_path):
            raise FileNotFoundError("SIM file not found: {}".format(self.sim_path))

        file_size = os.path.getsize(self.sim_path)
        if file_size == 0:
            raise ValueError("SIM file is empty")

        # Initialize storage
        for z in self.prj.zones:
            self.zone_data[z['name']] = {
                'pressure': [],
                'temperature': [],
            }
            for sp in self.prj.species:
                self.zone_data[z['name']][sp] = []

        for fp in self.prj.flow_paths:
            self.path_data[fp['nr']] = {
                'flow_0': [],
                'flow_1': [],
            }

        with open(self.sim_path, 'rb') as f:
            data = f.read()

        offset = 0

        # ---- Try to detect format and parse ----
        # CONTAM 3.x .sim format:
        #   Each record: 5 shorts (date/time) + zone data + path data
        #   Zone data per zone: 1 float (pressure) + 1 float (temp) + n_species floats
        #   Path data per path: 2 floats (flow 0→1, 1→0)

        n_z = self.n_zones
        n_sp = self.n_species
        n_p = self.n_paths

        # Bytes per zone: pressure(4) + temp(4) + n_species*4
        zone_bytes = n_z * (4 + 4 + n_sp * 4)
        # Bytes per path: 2 floats
        path_bytes = n_p * (4 + 4)
        # Time header: 5 shorts = 10 bytes  (year, month, day, hour, minute)
        time_bytes = 10

        record_size = time_bytes + zone_bytes + path_bytes

        if record_size == 0:
            return

        n_records = len(data) // record_size
        if n_records == 0:
            # Try alternative: time as 2 ints (date_int, time_int) = 8 bytes
            time_bytes = 8
            record_size = time_bytes + zone_bytes + path_bytes
            n_records = len(data) // record_size

        if n_records == 0:
            # Try with float32 for everything
            # Fallback: attempt to read as pure float array
            self._parse_flat(data)
            return

        # Try 5-short time header first
        try:
            self._parse_structured(data, n_records, time_bytes=10, time_format='5h')
            if len(self.timesteps) > 0:
                return
        except:
            pass

        # Try 2-int time header
        try:
            self._parse_structured(data, n_records, time_bytes=8, time_format='2i')
            if len(self.timesteps) > 0:
                return
        except:
            pass

        # Fallback: flat float parse
        self._parse_flat(data)

    def _parse_structured(self, data, n_records, time_bytes, time_format):
        """Parse with known record structure."""
        n_z = self.n_zones
        n_sp = self.n_species
        n_p = self.n_paths
        zone_floats = n_z * (2 + n_sp)  # pressure + temp + species per zone
        path_floats = n_p * 2
        record_size = time_bytes + (zone_floats + path_floats) * 4

        offset = 0
        for rec in range(n_records):
            if offset + record_size > len(data):
                break

            # Parse time
            if time_format == '5h':
                yr, mo, dy, hr, mn = struct.unpack_from('<5h', data, offset)
                offset += 10
                try:
                    dt = datetime(yr if yr > 0 else 2024, max(1,min(12,mo)),
                                  max(1,min(28,dy)), max(0,min(23,hr)), max(0,min(59,mn)))
                except:
                    dt = datetime(2024, 1, 1) + timedelta(hours=rec)
            else:
                d_int, t_int = struct.unpack_from('<2i', data, offset)
                offset += 8
                dt = datetime(2024, 1, 1) + timedelta(seconds=t_int)

            self.timesteps.append(dt)

            # Parse zone data
            for zi, z in enumerate(self.prj.zones):
                P = struct.unpack_from('<f', data, offset)[0]; offset += 4
                T = struct.unpack_from('<f', data, offset)[0]; offset += 4
                self.zone_data[z['name']]['pressure'].append(P)
                self.zone_data[z['name']]['temperature'].append(T)
                for si, sp in enumerate(self.prj.species):
                    conc = struct.unpack_from('<f', data, offset)[0]; offset += 4
                    self.zone_data[z['name']][sp].append(conc)

            # Parse path data
            for pi, fp in enumerate(self.prj.flow_paths):
                f0 = struct.unpack_from('<f', data, offset)[0]; offset += 4
                f1 = struct.unpack_from('<f', data, offset)[0]; offset += 4
                self.path_data[fp['nr']]['flow_0'].append(f0)
                self.path_data[fp['nr']]['flow_1'].append(f1)

    def _parse_flat(self, data):
        """Fallback: read all as float32, assign to zones by column position."""
        n_floats = len(data) // 4
        if n_floats == 0:
            return

        all_vals = struct.unpack('<{}f'.format(n_floats), data[:n_floats*4])

        n_z = self.n_zones
        n_sp = self.n_species
        cols_per_step = n_z * (2 + n_sp)  # pressure + temp + species
        if cols_per_step == 0:
            return

        n_steps = n_floats // cols_per_step
        idx = 0
        for step in range(n_steps):
            self.timesteps.append(datetime(2024, 1, 1) + timedelta(hours=step))
            for zi, z in enumerate(self.prj.zones):
                if idx < n_floats:
                    self.zone_data[z['name']]['pressure'].append(all_vals[idx]); idx += 1
                if idx < n_floats:
                    self.zone_data[z['name']]['temperature'].append(all_vals[idx]); idx += 1
                for sp in self.prj.species:
                    if idx < n_floats:
                        self.zone_data[z['name']][sp].append(all_vals[idx]); idx += 1

    def get_species_ppm(self, zone_name, species_name):
        """Get species concentration in ppm for a zone."""
        if zone_name not in self.zone_data:
            return []
        raw = self.zone_data[zone_name].get(species_name, [])
        # CONTAM stores as mass fraction (kg/kg); convert to ppm
        # For CO2: molecular weight ~44, air ~29 → ppm = fraction * 1e6 * (29/44)
        # For PM2.5: stored as µg/m³ already (depends on species config)
        if 'CO2' in species_name.upper():
            mol_ratio = 29.0 / 44.0
            return [v * 1e6 * mol_ratio for v in raw]
        elif 'PM' in species_name.upper():
            # Already in µg/m³ for particulate species
            return [v * 1e6 for v in raw]
        else:
            return [v * 1e6 for v in raw]  # generic ppm

    def summary_stats(self):
        """Compute summary statistics per zone per species."""
        stats = {}
        for z in self.prj.zones:
            zn = z['name']
            stats[zn] = {}
            for sp in self.prj.species:
                vals = self.get_species_ppm(zn, sp)
                if vals:
                    stats[zn][sp] = {
                        'min': round(min(vals), 1),
                        'max': round(max(vals), 1),
                        'mean': round(sum(vals)/len(vals), 1),
                        'final': round(vals[-1], 1),
                    }
                else:
                    stats[zn][sp] = {'min': 0, 'max': 0, 'mean': 0, 'final': 0}

            # Pressure stats
            pvals = self.zone_data[zn]['pressure']
            if pvals:
                stats[zn]['_pressure'] = {
                    'min': round(min(pvals), 4),
                    'max': round(max(pvals), 4),
                    'mean': round(sum(pvals)/len(pvals), 4),
                }
        return stats


# ============================================================================
#  ALTERNATE: PARSE FROM PIPELINE JSON (summary.json / results.csv)
# ============================================================================

def parse_from_json(json_path):
    """Parse results from the gds_contam_v3 pipeline output."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data


def parse_from_csv(csv_path):
    """Parse results CSV from gds_contam_v3 pipeline."""
    rows = []
    with open(csv_path, 'r') as f:
        header = f.readline().strip().split(',')
        for line in f:
            vals = line.strip().split(',')
            row = {}
            for h, v in zip(header, vals):
                try:
                    row[h] = float(v)
                except:
                    row[h] = v
            rows.append(row)
    return header, rows


# ============================================================================
#  HTML DASHBOARD GENERATOR
# ============================================================================

def generate_dashboard(prj_path, sim_parser=None, json_data=None,
                       csv_data=None, output_path=None, zone_geometry=None):
    """Generate a self-contained HTML dashboard with Plotly.js charts.
    
    zone_geometry: list of dicts with keys: name, floor_polygon (preferred)
                   or bb_min/bb_max (fallback), plus optional cx, cy, level
                   (from gds_spec.json zones)
    """

    if sim_parser:
        prj = sim_parser.prj
        zone_names = [z['name'] for z in prj.zones]
        species = prj.species
        n_steps = len(sim_parser.timesteps)
        time_labels = [dt.strftime('%H:%M') for dt in sim_parser.timesteps]
        stats = sim_parser.summary_stats()
    elif json_data:
        zone_names = json_data.get('zones', [])
        species = json_data.get('species', ['CO2'])
        n_steps = len(json_data.get('hourly', []))

        # Build proper time labels from day/hour fields
        time_labels = []
        for entry in json_data.get('hourly', []):
            day = entry.get('day', 1)
            hour = entry.get('hour', len(time_labels))
            if n_steps > 26:
                # Multi-day: show "D1 H00", "D1 H01", ...
                time_labels.append("D{} H{:02d}".format(day, hour))
            else:
                time_labels.append("{:02d}:00".format(hour))

        # Key mapping: species name -> JSON key in zone_data
        # gds_contam_v3 exports: CO2_ppm, PM25_ugm3, T_C, P_Pa
        _sp_key_map = {
            'CO2': 'CO2_ppm',
            'PM2.5': 'PM25_ugm3',
        }

        # ---- Extract all time-series from JSON ----
        # Species traces per zone
        _sp_series = {}   # {species: {zone: [values]}}
        _p_series = {}    # {zone: [pressure values]}
        for sp in species:
            _sp_series[sp] = {zn: [] for zn in zone_names}
        for zn in zone_names:
            _p_series[zn] = []

        for entry in json_data.get('hourly', []):
            for zn in zone_names:
                zd = entry.get('zone_data', {}).get(zn, {})
                for sp in species:
                    key = _sp_key_map.get(sp, '{}_ppm'.format(sp))
                    _sp_series[sp][zn].append(zd.get(key, 0))
                _p_series[zn].append(zd.get('P_Pa', 0))

        # ---- Compute stats from extracted series ----
        stats = {}
        for zn in zone_names:
            stats[zn] = {}
            for sp in species:
                vals = _sp_series[sp][zn]
                if vals and any(v != 0 for v in vals):
                    stats[zn][sp] = {
                        'min': round(min(vals), 1),
                        'max': round(max(vals), 1),
                        'mean': round(sum(vals) / len(vals), 1),
                        'final': round(vals[-1], 1),
                    }
            # Pressure stats
            pvals = _p_series[zn]
            if pvals and any(v != 0 for v in pvals):
                stats[zn]['_pressure'] = {
                    'min': round(min(pvals), 4),
                    'max': round(max(pvals), 4),
                    'mean': round(sum(pvals) / len(pvals), 4),
                }
    else:
        zone_names = []
        species = []
        n_steps = 0
        time_labels = []
        stats = {}

    # ---- Prepare chart data ----
    # Species time-series per zone
    species_traces = {}
    for sp in species:
        species_traces[sp] = {}
        for zn in zone_names:
            if sim_parser:
                species_traces[sp][zn] = sim_parser.get_species_ppm(zn, sp)
            elif json_data:
                species_traces[sp][zn] = _sp_series[sp][zn]

    # Pressure traces
    pressure_traces = {}
    if sim_parser:
        for zn in zone_names:
            pressure_traces[zn] = sim_parser.zone_data[zn]['pressure']
    elif json_data:
        for zn in zone_names:
            pressure_traces[zn] = _p_series[zn]

    # Airflow summary (net flows per path)
    flow_summary = []
    if sim_parser and sim_parser.path_data:
        for fp in prj.flow_paths[:50]:  # limit display
            nr = fp['nr']
            pd = sim_parser.path_data.get(nr, {})
            f0 = pd.get('flow_0', [])
            f1 = pd.get('flow_1', [])
            if f0:
                avg_net = sum(a - b for a, b in zip(f0, f1)) / len(f0)
                z_from = prj.zone_name(fp.get('zone_n', 0))
                z_to = prj.zone_name(fp.get('zone_m', 0))
                flow_summary.append({
                    'from': z_from,
                    'to': z_to,
                    'avg_net_kg_s': round(avg_net, 6),
                    'avg_net_L_s': round(avg_net / 1.2 * 1000, 2),  # approx
                })

    # ---- Build summary table data ----
    table_rows_json = []
    for zn in zone_names:
        row = {'zone': zn}
        if zn in stats:
            for sp in species:
                if sp in stats[zn]:
                    row['{}_max'.format(sp)] = stats[zn][sp]['max']
                    row['{}_mean'.format(sp)] = stats[zn][sp]['mean']
            if '_pressure' in stats[zn]:
                row['P_mean'] = stats[zn]['_pressure']['mean']
        table_rows_json.append(row)

    # ---- ASHRAE thresholds ----
    thresholds = {
        'CO2': {'warn': 1000, 'fail': 1500, 'unit': 'ppm', 'label': 'ASHRAE 62.1'},
        'PM2.5': {'warn': 12, 'fail': 35, 'unit': 'ug/m3', 'label': 'EPA/WHO'},
    }

    # ---- Compliance summary ----
    compliance = []
    for zn in zone_names:
        if zn not in stats:
            continue
        for sp in species:
            if sp not in stats[zn]:
                continue
            s = stats[zn][sp]
            # Direct lookup, then try normalized key
            th = thresholds.get(sp, {})
            if not th:
                continue
            status = 'pass'
            if s['max'] > th.get('fail', 9999):
                status = 'fail'
            elif s['max'] > th.get('warn', 9999):
                status = 'warn'
            compliance.append({
                'zone': zn, 'species': sp, 'status': status,
                'peak': s['max'], 'threshold': th.get('warn', 0),
                'standard': th.get('label', '')
            })

    # Count statuses
    n_pass = sum(1 for c in compliance if c['status'] == 'pass')
    n_warn = sum(1 for c in compliance if c['status'] == 'warn')
    n_fail = sum(1 for c in compliance if c['status'] == 'fail')

    # ---- Generate HTML ----
    # Path manifest (from gds_contam_v3 summary JSON — zone pairs + avg flows)
    path_manifest = []
    if json_data:
        path_manifest = json_data.get('paths', [])

    # Connectivity graph section
    conn_html, conn_js = "", ""
    if sim_parser and sim_parser.prj:
        conn_html, conn_js = build_connectivity_section(sim_parser.prj)
    elif prj_path and os.path.exists(prj_path):
        try:
            _prj_for_conn = PRJParser(prj_path)
            conn_html, conn_js = build_connectivity_section(_prj_for_conn)
        except Exception:
            pass

    html = _build_html(
        prj_path=prj_path,
        zone_names=zone_names,
        species=species,
        n_steps=n_steps,
        time_labels=time_labels,
        species_traces=species_traces,
        pressure_traces=pressure_traces,
        flow_summary=flow_summary,
        table_rows=table_rows_json,
        stats=stats,
        compliance=compliance,
        n_pass=n_pass, n_warn=n_warn, n_fail=n_fail,
        thresholds=thresholds,
        zone_geometry=zone_geometry,
        path_manifest=path_manifest,
        conn_html=conn_html,
        conn_js=conn_js,
    )

    if not output_path:
        base = os.path.splitext(prj_path)[0]
        output_path = base + '_dashboard.html'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


def _build_html(prj_path, zone_names, species, n_steps, time_labels,
                species_traces, pressure_traces, flow_summary,
                table_rows, stats, compliance,
                n_pass, n_warn, n_fail, thresholds,
                zone_geometry=None, path_manifest=None,
                conn_html="", conn_js=""):
    """Build the full HTML string."""

    prj_name = os.path.basename(prj_path)
    gen_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Prepare JS data
    def to_js_array(lst):
        return json.dumps(lst)

    # ---- 32+ distinct colors for zone traces (HSL-based) ----
    def _generate_zone_colors(n):
        """Generate n visually distinct colors via HSL with varied lightness/saturation."""
        colors = []
        for i in range(n):
            hue = (i * 360 / n) % 360
            sat = 70 + (i % 3) * 10   # 70, 80, 90
            lit = 55 + (i % 2) * 10   # 55, 65
            colors.append('hsl({}, {}%, {}%)'.format(int(hue), sat, lit))
        return colors

    zone_colors = _generate_zone_colors(max(len(zone_names), 1))
    zone_color_map = {zn: zone_colors[i] for i, zn in enumerate(zone_names)}

    # Build Plotly trace objects for species
    species_chart_js = {}
    for sp in species:
        traces = []
        for zn in zone_names:
            vals = species_traces.get(sp, {}).get(zn, [])
            if vals and any(v != 0 for v in vals):
                traces.append({
                    'x': time_labels[:len(vals)],
                    'y': [round(v, 2) for v in vals],
                    'name': zn,
                    'type': 'scatter',
                    'mode': 'lines',
                    'line': {'color': zone_color_map.get(zn, '#888')},
                })
        species_chart_js[sp] = json.dumps(traces)

    # Pressure chart traces
    pressure_chart_traces = []
    for zn in zone_names:
        vals = pressure_traces.get(zn, [])
        if vals and any(v != 0 for v in vals):
            pressure_chart_traces.append({
                'x': time_labels[:len(vals)],
                'y': [round(v, 4) for v in vals],
                'name': zn,
                'type': 'scatter',
                'mode': 'lines',
                'line': {'color': zone_color_map.get(zn, '#888')},
            })
    pressure_chart_js = json.dumps(pressure_chart_traces)

    # Bar chart: peak concentrations per zone
    peak_bar_js = {}
    for sp in species:
        zones_with_data = []
        peaks = []
        for zn in zone_names:
            if zn in stats and sp in stats[zn]:
                zones_with_data.append(zn)
                peaks.append(stats[zn][sp]['max'])
        if zones_with_data:
            th = thresholds.get(sp, {})
            peak_bar_js[sp] = json.dumps([{
                'x': zones_with_data,
                'y': peaks,
                'type': 'bar',
                'marker': {
                    'color': [
                        '#ef4444' if v > th.get('fail', 9e9)
                        else '#f59e0b' if v > th.get('warn', 9e9)
                        else '#10b981'
                        for v in peaks
                    ]
                },
                'name': 'Peak {}'.format(sp)
            }])

    # Flow summary table (top 20 by magnitude)
    flow_sorted = sorted(flow_summary, key=lambda x: abs(x['avg_net_L_s']), reverse=True)[:20]

    # Build species tab buttons and chart divs
    sp_tabs_html = ""
    sp_charts_html = ""
    sp_bars_html = ""
    for si, sp in enumerate(species):
        active = "active" if si == 0 else ""
        sp_tabs_html += '<button class="tab-btn {a}" data-sp="{sp}">{sp}</button>\n'.format(
            a=active, sp=sp)
        display = "block" if si == 0 else "none"
        sp_charts_html += '<div id="chart-ts-{sp}" class="sp-chart" style="display:{d}"></div>\n'.format(
            sp=sp, d=display)
        sp_bars_html += '<div id="chart-bar-{sp}" class="sp-chart" style="display:{d}"></div>\n'.format(
            sp=sp, d=display)

    # ---- Merged Zone Summary table (compliance + stats) ----
    # Build compliance lookup: {(zone, species): {status, icon, cls, threshold, standard}}
    compliance_map = {}
    for c in compliance:
        cls = {'pass': 'status-pass', 'warn': 'status-warn', 'fail': 'status-fail'}[c['status']]
        icon = {'pass': '●', 'warn': '▲', 'fail': '✖'}[c['status']]
        compliance_map[(c['zone'], c['species'])] = {
            'cls': cls, 'icon': icon,
            'threshold': c['threshold'], 'standard': c['standard'],
        }

    # Species units for header
    sp_units = {'CO2': 'ppm', 'PM2.5': 'µg/m³'}

    zone_summary_header = "<th>Zone</th>"
    for sp in species:
        unit = sp_units.get(sp, 'ppm')
        zone_summary_header += "<th>{sp} ({u})</th>".format(sp=sp, u=unit)
    zone_summary_header += "<th>ΔP Mean (Pa)</th>"

    zone_summary_rows = ""
    for row in table_rows:
        zn = row['zone']
        zone_summary_rows += "<tr><td>{}</td>".format(zn)
        for sp in species:
            peak = row.get('{}_max'.format(sp), '-')
            mean = row.get('{}_mean'.format(sp), '-')
            comp = compliance_map.get((zn, sp))
            if comp:
                zone_summary_rows += (
                    '<td class="{cls}">'
                    '<span class="status-icon">{icon}</span> '
                    '{peak} / {mean}'
                    '</td>'
                ).format(cls=comp['cls'], icon=comp['icon'],
                         peak=peak, mean=mean)
            else:
                zone_summary_rows += "<td>{} / {}</td>".format(peak, mean)
        zone_summary_rows += "<td>{}</td></tr>".format(row.get('P_mean', '-'))

    # Flow table rows
    flow_rows = ""
    for fl in flow_sorted:
        flow_rows += "<tr><td>{from}</td><td>{to}</td><td>{avg_net_L_s}</td></tr>".format(**fl)

    # Room-wise airflow summary (aggregate paths per room)
    # Merges path manifest detail into expandable per-room rows
    room_flow_rows = ""
    if path_manifest:
        room_data = {}
        for p in path_manifest:
            flow = p.get('avg_flow_L_s', 0)
            desc = p.get('desc', '')
            dtype = p.get('dtype', '')
            if 'envelope' in desc:
                cat = 'env'
            elif 'window' in desc:
                cat = 'win'
            elif 'door_ext' in desc:
                cat = 'door_ext'
            elif 'vertical' in desc:
                cat = 'vert'
            elif 'dor' in dtype:
                cat = 'int_door'
            elif 'fan' in dtype:
                cat = 'fan'
            else:
                cat = 'leak'
            frm = p.get('from', '')
            to = p.get('to', '')
            for zn, is_from in [(frm, True), (to, False)]:
                if not zn or zn == 'Ambient':
                    continue
                if zn not in room_data:
                    room_data[zn] = {'n': 0, 'cats': {}, 'in_Ls': 0.0, 'out_Ls': 0.0, 'paths': []}
                room_data[zn]['n'] += 1
                room_data[zn]['cats'][cat] = room_data[zn]['cats'].get(cat, 0) + 1
                other = to if is_from else frm
                if not other:
                    other = 'Ambient'
                if is_from:
                    if flow < 0:
                        room_data[zn]['in_Ls'] += abs(flow)
                    else:
                        room_data[zn]['out_Ls'] += flow
                    room_data[zn]['paths'].append({
                        'other': other, 'cat': cat, 'room_flow': -flow,
                        'nr': p.get('nr', ''), 'element': p.get('desc', '') or p.get('element', ''),
                        'dtype': dtype, 'mult': p.get('mult', 1),
                        'avg_dP': p.get('avg_dP', None),
                        'avg_flow_L_s': p.get('avg_flow_L_s', None),
                        'wind': p.get('wind', False),
                    })
                else:
                    if flow > 0:
                        room_data[zn]['in_Ls'] += flow
                    else:
                        room_data[zn]['out_Ls'] += abs(flow)
                    room_data[zn]['paths'].append({
                        'other': other, 'cat': cat, 'room_flow': flow,
                        'nr': p.get('nr', ''), 'element': p.get('desc', '') or p.get('element', ''),
                        'dtype': dtype, 'mult': p.get('mult', 1),
                        'avg_dP': p.get('avg_dP', None),
                        'avg_flow_L_s': p.get('avg_flow_L_s', None),
                        'wind': p.get('wind', False),
                    })
        cat_labels = {'env': 'Env', 'win': 'Win', 'door_ext': 'DoorExt',
                      'int_door': 'IntDoor', 'vert': 'Vert', 'fan': 'Fan', 'leak': 'Leak'}

        # Color-code dtype tags (same as former manifest)
        def _dtype_tag(dtype):
            if 'dor' in dtype:
                return '<span style="color:#3b82f6">door</span>'
            elif dtype == 'plr_test1':
                return '<span style="color:#f59e0b">leak</span>'
            elif 'fan' in dtype:
                return '<span style="color:#10b981">fan</span>'
            return dtype

        # Natural sort: Room1, Room2, ..., Room10, Room11 (not alphabetical)
        import re as _re
        def _nat_key(s):
            return [int(c) if c.isdigit() else c.lower()
                    for c in _re.split(r'(\d+)', s)]

        for zn in sorted(room_data.keys(), key=_nat_key):
            rd = room_data[zn]
            cat_str = ", ".join("{} {}".format(v, cat_labels.get(k, k))
                                for k, v in sorted(rd['cats'].items()) if v > 0)
            # Use average of in/out as the room throughflow (equal by mass balance)
            flow_Ls = (rd['in_Ls'] + rd['out_Ls']) / 2.0

            # Build collapsible detail table with full path info
            all_paths = sorted(rd['paths'], key=lambda x: abs(x['room_flow']), reverse=True)

            detail_items = (
                '<table style="width:100%;font-size:0.75em;margin-top:4px">'
                '<tr style="border-bottom:1px solid #333">'
                '<th style="text-align:left;padding:2px 4px;color:#666">#</th>'
                '<th style="text-align:left;padding:2px 4px;color:#666">Other</th>'
                '<th style="text-align:left;padding:2px 4px;color:#666">Element</th>'
                '<th style="text-align:left;padding:2px 4px;color:#666">Type</th>'
                '<th style="text-align:right;padding:2px 4px;color:#666">Mult</th>'
                '<th style="text-align:right;padding:2px 4px;color:#666">Avg dP</th>'
                '<th style="text-align:right;padding:2px 4px;color:#666">Flow (L/s)</th>'
                '<th style="text-align:center;padding:2px 4px;color:#666">Wind</th>'
                '</tr>'
            )
            for pinfo in all_paths:
                pf_color = '#10b981' if pinfo['room_flow'] > 0 else '#ef4444'
                dp_str = "{:.3f}".format(pinfo['avg_dP']) if pinfo['avg_dP'] is not None else '-'
                fl_str = "{:.2f}".format(pinfo['avg_flow_L_s']) if pinfo['avg_flow_L_s'] is not None else '-'
                wind_str = "Y" if pinfo['wind'] else ""
                detail_items += (
                    '<tr style="border-bottom:1px solid #222">'
                    '<td style="padding:2px 4px;color:#888">{nr}</td>'
                    '<td style="padding:2px 4px">{other} <span style="color:#888">({cat})</span></td>'
                    '<td style="padding:2px 4px;color:#aaa">{elem}</td>'
                    '<td style="padding:2px 4px">{tag}</td>'
                    '<td style="padding:2px 4px;text-align:right;color:#aaa">{mult}</td>'
                    '<td style="padding:2px 4px;text-align:right;color:#aaa">{dp}</td>'
                    '<td style="padding:2px 4px;text-align:right;color:{clr}">{flow:+.2f}</td>'
                    '<td style="padding:2px 4px;text-align:center;color:#888">{wind}</td>'
                    '</tr>'
                ).format(
                    nr=pinfo['nr'], other=pinfo['other'],
                    cat=cat_labels.get(pinfo['cat'], pinfo['cat']),
                    elem=pinfo['element'], tag=_dtype_tag(pinfo['dtype']),
                    mult=round(pinfo['mult'], 3), dp=dp_str,
                    clr=pf_color, flow=pinfo['room_flow'],
                    wind=wind_str,
                )
            detail_items += '</table>'

            # Summary line for the collapsed state
            top3 = all_paths[:3]
            summary_str = "; ".join("{} ({}) {:+.1f}".format(
                tp['other'], cat_labels.get(tp['cat'], tp['cat']), tp['room_flow']) for tp in top3)
            if len(all_paths) > 3:
                summary_str += "; +{} more".format(len(all_paths) - 3)

            room_flow_rows += (
                "<tr>"
                "<td><b>{zn}</b></td>"
                "<td>{n}</td>"
                "<td>{cats}</td>"
                "<td>{flow_Ls:.1f}</td>"
                "<td><details><summary style='cursor:pointer;font-size:0.8em'>"
                "{summary}</summary>"
                "<div style='padding:4px 0'>{details}</div>"
                "</details></td>"
                "</tr>\n"
            ).format(zn=zn, n=rd['n'], cats=cat_str,
                     flow_Ls=flow_Ls,
                     summary=summary_str, details=detail_items)

    # Build species chart init JS
    sp_init_js = ""
    for sp in species:
        traces_js = species_chart_js.get(sp, '[]')
        th = thresholds.get(sp, {})
        shapes_js = '[]'
        if 'warn' in th:
            shapes_js = json.dumps([{
                'type': 'line', 'y0': th['warn'], 'y1': th['warn'],
                'x0': 0, 'x1': 1, 'xref': 'paper',
                'line': {'color': '#f59e0b', 'width': 1.5, 'dash': 'dash'}
            }])
        has_data = traces_js.strip() not in ('[]', '')
        no_data_anno = ''
        if not has_data:
            no_data_anno = """,
        annotations: [{{
            text: 'No {sp} data - connect occupants or program_data input',
            xref: 'paper', yref: 'paper', x: 0.5, y: 0.5,
            showarrow: false,
            font: {{size: 14, color: '#666'}}
        }}]""".format(sp=sp)
        sp_init_js += """
    Plotly.newPlot('chart-ts-{sp}', {traces}, {{
        title: '{sp} Concentration Over Time',
        xaxis: {{title: 'Timestep', nticks: 24, tickangle: -45}},
        yaxis: {{title: '{sp} (ppm)'}},
        shapes: {shapes},
        template: 'plotly_dark',
        paper_bgcolor: '#0f0f0f',
        plot_bgcolor: '#1a1a1a',
        font: {{color: '#d4d4d4'}},
        margin: {{t: 40, r: 180, b: 80, l: 60}},
        legend: {{
            orientation: 'v',
            x: 1.02, y: 1, xanchor: 'left', yanchor: 'top',
            font: {{size: 10}},
            bgcolor: 'rgba(15,15,15,0.8)',
            bordercolor: '#333', borderwidth: 1,
        }},
        height: 500{no_data_anno}
    }});
    """.format(sp=sp, traces=traces_js, shapes=shapes_js,
               no_data_anno=no_data_anno)

    # Bar chart init JS
    bar_init_js = ""
    for sp in species:
        if sp in peak_bar_js:
            th = thresholds.get(sp, {})
            bar_shapes = '[]'
            if 'warn' in th:
                bar_shapes = json.dumps([{
                    'type': 'line', 'y0': th['warn'], 'y1': th['warn'],
                    'x0': 0, 'x1': 1, 'xref': 'paper',
                    'line': {'color': '#f59e0b', 'width': 1.5, 'dash': 'dash'}
                }])
            bar_init_js += """
    Plotly.newPlot('chart-bar-{sp}', {traces}, {{
        title: 'Peak {sp} by Zone',
        xaxis: {{title: '', tickangle: -45}},
        yaxis: {{title: '{sp}'}},
        shapes: {shapes},
        template: 'plotly_dark',
        paper_bgcolor: '#0f0f0f',
        plot_bgcolor: '#1a1a1a',
        font: {{color: '#d4d4d4'}},
        margin: {{t: 40, r: 20, b: 100, l: 60}},
        height: 380,
    }});
    """.format(sp=sp, traces=peak_bar_js[sp], shapes=bar_shapes)
        else:
            bar_init_js += """
    Plotly.newPlot('chart-bar-{sp}', [], {{
        title: 'Peak {sp} by Zone',
        xaxis: {{title: ''}}, yaxis: {{title: '{sp}'}},
        annotations: [{{
            text: 'No {sp} sources',
            xref: 'paper', yref: 'paper', x: 0.5, y: 0.5,
            showarrow: false, font: {{size: 14, color: '#666'}}
        }}],
        template: 'plotly_dark',
        paper_bgcolor: '#0f0f0f', plot_bgcolor: '#1a1a1a',
        font: {{color: '#d4d4d4'}},
        margin: {{t: 40, r: 20, b: 60, l: 60}},
        height: 380,
    }});
    """.format(sp=sp)

    # ---- Floor plan JS ----
    floorplan_js = ""
    floorplan_display = "display:none"
    if zone_geometry:
        zones_with_geo = [z for z in zone_geometry
                          if 'floor_polygon' in z or 'bb_min' in z]
        if zones_with_geo:
            floorplan_display = ""
            # Color palette for zones
            colors = ['#06b6d4','#3b82f6','#8b5cf6','#ec4899','#f59e0b',
                      '#10b981','#ef4444','#6366f1','#14b8a6','#f97316',
                      '#a855f7','#22d3ee','#84cc16','#e879f9','#fb923c',
                      '#2dd4bf','#818cf8','#fbbf24','#34d399','#f472b6']

            # Build traces (filled polygons) and annotations (labels)
            traces = []
            annotations = []
            all_x = []
            all_y = []

            for zi, z in enumerate(zones_with_geo):
                color = colors[zi % len(colors)]

                if 'floor_polygon' in z and z['floor_polygon']:
                    # Real polygon vertices
                    poly = z['floor_polygon']
                    xs = [p[0] for p in poly] + [poly[0][0]]  # close polygon
                    ys = [p[1] for p in poly] + [poly[0][1]]
                    cx = sum(p[0] for p in poly) / len(poly)
                    cy = sum(p[1] for p in poly) / len(poly)
                elif 'bb_min' in z and 'bb_max' in z:
                    # Fallback: bbox rectangle
                    bmin, bmax = z['bb_min'], z['bb_max']
                    xs = [bmin[0], bmax[0], bmax[0], bmin[0], bmin[0]]
                    ys = [bmin[1], bmin[1], bmax[1], bmax[1], bmin[1]]
                    cx = z.get('cx', (bmin[0]+bmax[0])/2)
                    cy = z.get('cy', (bmin[1]+bmax[1])/2)
                else:
                    continue

                all_x.extend(xs)
                all_y.extend(ys)

                traces.append({
                    'x': xs, 'y': ys,
                    'fill': 'toself',
                    'fillcolor': color,
                    'opacity': 0.35,
                    'line': {'color': color, 'width': 2},
                    'mode': 'lines',
                    'name': z['name'],
                    'hoverinfo': 'name',
                    'showlegend': False,
                })

                annotations.append({
                    'x': cx, 'y': cy,
                    'text': '<b>{}</b>'.format(z['name']),
                    'showarrow': False,
                    'font': {'color': color, 'size': 10,
                             'family': 'JetBrains Mono'},
                })

            pad = 2.0
            floorplan_js = """
    Plotly.newPlot('chart-floorplan', {traces}, {{
        title: 'Zone Floor Plan',
        xaxis: {{title: 'X (m)', scaleanchor: 'y', scaleratio: 1,
                 gridcolor: '#222', zerolinecolor: '#333',
                 range: [{x_lo}, {x_hi}]}},
        yaxis: {{title: 'Y (m)', gridcolor: '#222', zerolinecolor: '#333',
                 range: [{y_lo}, {y_hi}]}},
        annotations: {annotations},
        template: 'plotly_dark',
        paper_bgcolor: '#0f0f0f',
        plot_bgcolor: '#1a1a1a',
        font: {{color: '#d4d4d4'}},
        margin: {{t: 40, r: 20, b: 50, l: 60}},
        height: 550,
    }});
    """.format(
                traces=json.dumps(traces),
                annotations=json.dumps(annotations),
                x_lo=min(all_x) - pad, x_hi=max(all_x) + pad,
                y_lo=min(all_y) - pad, y_hi=max(all_y) + pad,
            )

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GDS CONTAM Results — {prj_name}</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg-primary: #0a0a0a;
    --bg-card: #111111;
    --bg-card-hover: #161616;
    --border: #222222;
    --border-accent: #2a2a2a;
    --text-primary: #e8e8e8;
    --text-secondary: #888888;
    --text-dim: #555555;
    --accent-green: #10b981;
    --accent-amber: #f59e0b;
    --accent-red: #ef4444;
    --accent-blue: #3b82f6;
    --accent-cyan: #06b6d4;
    --mono: 'JetBrains Mono', monospace;
    --sans: 'DM Sans', system-ui, sans-serif;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--sans);
    line-height: 1.6;
    min-height: 100vh;
  }}

  .container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
  }}

  /* ---- Header ---- */
  .header {{
    border-bottom: 1px solid var(--border);
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
  }}
  .header h1 {{
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}
  .header h1 .tag {{
    font-family: var(--mono);
    font-size: 0.7rem;
    font-weight: 600;
    background: var(--accent-cyan);
    color: #000;
    padding: 2px 8px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .header-meta {{
    font-family: var(--mono);
    font-size: 0.75rem;
    color: var(--text-dim);
    margin-top: 0.4rem;
  }}

  /* ---- KPI Cards ---- */
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }}
  .kpi {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.2rem;
    transition: border-color 0.2s;
  }}
  .kpi:hover {{ border-color: var(--border-accent); }}
  .kpi-label {{
    font-size: 0.7rem;
    font-family: var(--mono);
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.3rem;
  }}
  .kpi-value {{
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.04em;
  }}
  .kpi-value.green {{ color: var(--accent-green); }}
  .kpi-value.amber {{ color: var(--accent-amber); }}
  .kpi-value.red {{ color: var(--accent-red); }}
  .kpi-value.blue {{ color: var(--accent-blue); }}
  .kpi-value.cyan {{ color: var(--accent-cyan); }}
  .kpi-sub {{
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 0.2rem;
  }}

  /* ---- Section ---- */
  .section {{
    margin-bottom: 2.5rem;
  }}
  .section-title {{
    font-size: 0.8rem;
    font-family: var(--mono);
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
  }}

  /* ---- Tabs ---- */
  .tab-bar {{
    display: flex;
    gap: 0.25rem;
    margin-bottom: 1rem;
  }}
  .tab-btn {{
    font-family: var(--mono);
    font-size: 0.75rem;
    font-weight: 600;
    background: var(--bg-card);
    color: var(--text-secondary);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.4rem 1rem;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .tab-btn:hover {{ color: var(--text-primary); border-color: var(--border-accent); }}
  .tab-btn.active {{
    background: var(--accent-cyan);
    color: #000;
    border-color: var(--accent-cyan);
  }}

  /* ---- Charts ---- */
  .chart-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
  }}
  .chart-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    overflow: visible;
  }}
  .chart-full {{
    grid-column: 1 / -1;
  }}
  @media (max-width: 900px) {{
    .chart-row {{ grid-template-columns: 1fr; }}
  }}

  /* ---- Tables ---- */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }}
  th {{
    font-family: var(--mono);
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    text-align: left;
    padding: 0.6rem 0.8rem;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    background: var(--bg-card);
  }}
  td {{
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
    font-variant-numeric: tabular-nums;
  }}
  tr:hover td {{ background: var(--bg-card-hover); }}
  .table-wrap {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: auto;
    max-height: 500px;
  }}

  /* ---- Status badges ---- */
  .status-pass {{ color: var(--accent-green); }}
  .status-warn {{ color: var(--accent-amber); }}
  .status-fail {{ color: var(--accent-red); font-weight: 600; }}
  .status-icon {{ font-size: 0.7rem; }}

  /* ---- No-data message ---- */
  .no-data {{
    padding: 3rem;
    text-align: center;
    color: var(--text-dim);
    font-family: var(--mono);
    font-size: 0.85rem;
  }}

  /* ---- Connectivity graph ---- */
  .conn-tooltip {{
    position:absolute; pointer-events:none; background:#161b22;
    border:1px solid #30363d; border-radius:5px; padding:8px 12px;
    font-size:0.78rem; font-family:var(--mono); line-height:1.5;
    max-width:250px; opacity:0; transition:opacity 0.15s;
    box-shadow:0 4px 16px rgba(0,0,0,0.5); color:#e6edf3; z-index:50;
  }}
  .conn-legend-item {{
    display:flex; align-items:center; gap:8px; margin-bottom:5px;
  }}
  .conn-swatch {{
    width:24px; height:3px; border-radius:1px; flex-shrink:0;
  }}
  .conn-count {{
    margin-left:auto; font-family:var(--mono); font-size:0.8em; color:#8b949e;
  }}
  .conn-filter {{
    font-size:0.72rem; font-family:var(--mono); padding:2px 8px;
    border-radius:10px; border:1px solid #30363d; background:transparent;
    color:#8b949e; cursor:pointer; transition:all 0.2s;
  }}
  .conn-filter.active {{
    background:rgba(88,166,255,0.15); color:#58a6ff; border-color:#58a6ff;
  }}
  .conn-filter:hover {{ border-color:#58a6ff; }}
  .conn-badge {{
    display:inline-block; padding:1px 7px; border-radius:8px;
    font-size:0.75em; font-weight:600; font-family:var(--mono);
  }}
  .badge-found {{ background:rgba(63,185,80,0.15); color:#3fb950; }}
  .badge-missing {{ background:rgba(255,123,114,0.15); color:#ff7b72; }}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <h1>GDS CONTAM Results <span class="tag">IAQ Dashboard</span></h1>
    <div class="header-meta">{prj_name} &nbsp;·&nbsp; {n_zones} zones &nbsp;·&nbsp; {n_steps} timesteps &nbsp;·&nbsp; Generated {gen_time}</div>
  </div>

  <!-- KPI Cards -->
  <div class="kpi-grid">
    <div class="kpi">
      <div class="kpi-label">Zones</div>
      <div class="kpi-value cyan">{n_zones}</div>
      <div class="kpi-sub">simulation domains</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Timesteps</div>
      <div class="kpi-value blue">{n_steps}</div>
      <div class="kpi-sub">output records</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Compliant</div>
      <div class="kpi-value green">{n_pass}</div>
      <div class="kpi-sub">zone·species checks</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Warnings</div>
      <div class="kpi-value amber">{n_warn}</div>
      <div class="kpi-sub">near threshold</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Failures</div>
      <div class="kpi-value red">{n_fail}</div>
      <div class="kpi-sub">exceed limit</div>
    </div>
  </div>

  <!-- Floor Plan -->
  <div class="section" style="{floorplan_display}">
    <div class="section-title">Zone Floor Plan</div>
    <div class="chart-card chart-full">
      <div id="chart-floorplan"></div>
    </div>
  </div>

  <!-- Zone Connectivity Graph -->
  ___CONN_HTML___

  <!-- Species Time Series -->
  <div class="section">
    <div class="section-title">Concentration Time Series</div>
    <div class="tab-bar" id="sp-tabs">
      {sp_tabs_html}
    </div>
    <div class="chart-card chart-full">
      {sp_charts_html}
    </div>
  </div>

  <!-- Peak Bar + Pressure -->
  <div class="section">
    <div class="section-title">Peak Concentrations &amp; Zone Pressures</div>
    <div class="chart-card" style="margin-bottom: 1.5rem;">
      {sp_bars_html}
    </div>
    <div class="chart-card">
      <div id="chart-pressure"></div>
    </div>
  </div>

  <!-- Zone Summary (compliance + statistics) -->
  <div class="section">
    <div class="section-title">Zone Summary</div>
    <div class="table-wrap">
      <table>
        <thead><tr>{zone_summary_header}</tr></thead>
        <tbody>{zone_summary_rows}</tbody>
      </table>
      {no_compliance}
    </div>
    <div style="font-family:var(--mono);font-size:0.7rem;color:var(--text-dim);margin-top:0.5rem;padding:0 0.2rem">
      Values shown as peak / mean. &nbsp;
      <span class="status-pass">●</span> compliant &nbsp;
      <span class="status-warn">▲</span> near threshold &nbsp;
      <span class="status-fail">✖</span> exceeds limit
    </div>
  </div>

  <!-- Airflow Table -->
  <div class="section" id="flow-section" style="{flow_display}">
    <div class="section-title">Top Airflow Paths (by magnitude)</div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>From</th><th>To</th><th>Avg Net Flow (L/s)</th></tr></thead>
        <tbody>{flow_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Room Airflow Summary (with per-path details) -->
  <div class="section" id="room-flow-section" style="{room_flow_display}">
    <div class="section-title">Room Airflow Summary</div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Room</th><th>Paths</th><th>Breakdown</th>
          <th>Flow (L/s)</th>
          <th>Path Details (click to expand)</th>
        </tr></thead>
        <tbody>{room_flow_rows}</tbody>
      </table>
    </div>
  </div>

</div>

<script>
  // ---- Initialize Plotly Charts ----
  {sp_init_js}
  {bar_init_js}

  // Pressure chart
  Plotly.newPlot('chart-pressure', {pressure_traces}, {{
    title: 'Zone Pressure (Pa)',
    xaxis: {{title: 'Timestep', nticks: 24, tickangle: -45}},
    yaxis: {{title: 'Pressure (Pa)'}},
    template: 'plotly_dark',
    paper_bgcolor: '#0f0f0f',
    plot_bgcolor: '#1a1a1a',
    font: {{color: '#d4d4d4'}},
    margin: {{t: 40, r: 180, b: 80, l: 60}},
    legend: {{
        orientation: 'v',
        x: 1.02, y: 1, xanchor: 'left', yanchor: 'top',
        font: {{size: 10}},
        bgcolor: 'rgba(15,15,15,0.8)',
        bordercolor: '#333', borderwidth: 1,
    }},
    height: 500,
  }});

  // Floor plan
  {floorplan_js}

  // ---- Tab switching ----
  document.querySelectorAll('#sp-tabs .tab-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('#sp-tabs .tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const sp = btn.dataset.sp;
      document.querySelectorAll('.sp-chart').forEach(el => el.style.display = 'none');
      const tsEl = document.getElementById('chart-ts-' + sp);
      const barEl = document.getElementById('chart-bar-' + sp);
      if (tsEl) {{ tsEl.style.display = 'block'; Plotly.Plots.resize(tsEl); }}
      if (barEl) {{ barEl.style.display = 'block'; Plotly.Plots.resize(barEl); }}
    }});
  }});

  // ---- Zone Connectivity Graph ----
  ___CONN_JS___

  // ---- Responsive resize ----
  window.addEventListener('resize', () => {{
    document.querySelectorAll('.js-plotly-plot').forEach(el => Plotly.Plots.resize(el));
  }});
</script>
</body>
</html>""".format(
        prj_name=prj_name,
        n_zones=len(zone_names),
        n_steps=n_steps,
        gen_time=gen_time,
        sp_tabs_html=sp_tabs_html,
        sp_charts_html=sp_charts_html,
        sp_bars_html=sp_bars_html,
        zone_summary_header=zone_summary_header,
        zone_summary_rows=zone_summary_rows,
        no_compliance='<div class="no-data">No contaminant sources detected. Connect <b>occupants</b> or <b>program_data</b> to see IAQ compliance results.</div>' if not compliance else "",
        flow_rows=flow_rows,
        flow_display="" if flow_rows else "display:none",
        room_flow_rows=room_flow_rows,
        room_flow_display="" if room_flow_rows else "display:none",
        sp_init_js=sp_init_js,
        bar_init_js=bar_init_js,
        pressure_traces=pressure_chart_js,
        n_pass=n_pass if compliance else '-',
        n_warn=n_warn if compliance else '-',
        n_fail=n_fail if compliance else '-',
        floorplan_display=floorplan_display,
        floorplan_js=floorplan_js,
    )

    # Insert connectivity graph via plain replace (not .format()) to preserve
    # JS braces — .format() does NOT unescape {{ }} inside substituted values.
    html = html.replace('___CONN_HTML___', conn_html)
    html = html.replace('___CONN_JS___', conn_js)

    return html


# ============================================================================
#  MAIN CLI
# ============================================================================

def main():
    args = sys.argv[1:]

    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        print("\nExamples:")
        print("  python gds_contam_viewer.py gds_model.prj")
        print("  python gds_contam_viewer.py gds_model.prj gds_model.sim")
        print("  python gds_contam_viewer.py --from-json gds_model_summary.json")
        sys.exit(0)

    # Mode: from pipeline JSON
    if args[0] == '--from-json':
        json_path = args[1]
        print("[GDS Viewer] Loading pipeline JSON: {}".format(json_path))
        data = parse_from_json(json_path)
        prj_path = json_path.replace('_summary.json', '.prj')

        # Try to load zone geometry from sibling gds_spec.json
        zone_geometry = None
        spec_path = os.path.join(os.path.dirname(json_path), 'gds_spec.json')
        if os.path.exists(spec_path):
            try:
                with open(spec_path, 'r') as f:
                    spec = json.load(f)
                zone_geometry = spec.get('zones', [])
                if zone_geometry and ('bb_min' in zone_geometry[0]
                                      or 'floor_polygon' in zone_geometry[0]):
                    print("[GDS Viewer] Loaded floor plan geometry for {} zones".format(
                        len(zone_geometry)))
                else:
                    zone_geometry = None  # no bbox data
            except:
                pass

        out = generate_dashboard(prj_path, json_data=data,
                                 zone_geometry=zone_geometry)
        print("[GDS Viewer] Dashboard: {}".format(out))
        if not os.environ.get('GDS_NO_BROWSER'):
            webbrowser.open('file://' + os.path.abspath(out))
        return

    # Mode: from PRJ + SIM files
    prj_path = None
    sim_path = None

    for a in args:
        if a.endswith('.prj'):
            prj_path = a
        elif a.endswith('.sim'):
            sim_path = a

    # Infer missing paths
    if prj_path and not sim_path:
        sim_path = prj_path.replace('.prj', '.sim')
    if sim_path and not prj_path:
        prj_path = sim_path.replace('.sim', '.prj')

    if not prj_path or not os.path.exists(prj_path):
        print("ERROR: PRJ file not found: {}".format(prj_path))
        sys.exit(1)

    print("[GDS Viewer] Parsing PRJ: {}".format(prj_path))
    prj = PRJParser(prj_path)
    print("  -> {} zones, {} species, {} paths, {} levels".format(
        len(prj.zones), len(prj.species), len(prj.flow_paths), len(prj.levels)))

    if sim_path and os.path.exists(sim_path):
        print("[GDS Viewer] Parsing SIM: {}".format(sim_path))
        sim = SIMParser(sim_path, prj)
        print("  -> {} timesteps parsed".format(len(sim.timesteps)))
    else:
        print("[GDS Viewer] No SIM file found - dashboard will show structure only")
        sim = None

    out = generate_dashboard(prj_path, sim_parser=sim)
    print("[GDS Viewer] Dashboard written: {}".format(out))
    if not os.environ.get('GDS_NO_BROWSER'):
        webbrowser.open('file://' + os.path.abspath(out))


if __name__ == '__main__':
    main()