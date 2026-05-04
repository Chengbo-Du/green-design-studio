"""
gds_contam.py - CONTAM PRJ File Generator for Green Design Studio (v2)

All defaults verified against blank.prj AND ContamW 3.4.0.6 GUI output.
Format: NIST TN 1887r1 Appendix A.

CRITICAL SETTINGS (verified by diff against ContamW-generated reference):
  zone.flags = 3   -> variable pressure (bit 0) + variable concentration (bit 1)
                     flags=0 makes zones constant-P/C -> solver skips them!
  zone.color = -1  -> default/no fill color
  zone.u_T   = 2   -> display units Celsius (ContamW default)
  sim_af     = 1   -> steady airflow solved at each timestep
                     0 = SS init only (no time-stepping); 1 = steady per step
  sim_mf     = 2   -> transient contaminant transport (multi-day capable)
                     0 = none; 1 = SS; 2 = transient; 3 = cyclic (repeats 1 day)
"""

from dataclasses import dataclass, field
from typing import List
import subprocess, os, math, struct, json

# === Data Classes ===

@dataclass
class Species:
    name: str; desc: str = ""
    sflag: int = 1; ntflag: int = 0; molwt: float = 28.97
    mdiam: float = 0.0; edens: float = 0.0; decay: float = 0.0
    Dm: float = 2e-5; ccdef: float = 0.0; Cp: float = 0.0; Kuv: float = 0.0
    ucc: int = 0; umd: int = 0; ued: int = 0; udm: int = 0; ucp: int = 0

@dataclass
class Level:
    name: str = "<1>"; refht: float = 0.0; delht: float = 3.0
    u_rfht: int = 0; u_dlht: int = 0

@dataclass
class DaySchedule:
    name: str = "DaySch1"; desc: str = ""; shape: int = 0
    utyp: int = 0; ucnv: int = 0
    points: List[tuple] = field(default_factory=list)

@dataclass
class WeekSchedule:
    name: str = "WeekSch1"; desc: str = ""; utyp: int = 0; ucnv: int = 0
    day_indices: List[int] = field(default_factory=lambda: [0]*12)

@dataclass
class WindProfile:
    name: str = "WndPrf1"; desc: str = ""; profile_type: int = 1
    points: List[tuple] = field(default_factory=list)

@dataclass
class SourceElement:
    name: str; desc: str = ""; species_name: str = ""; ctype: str = "ccf"
    type_data: dict = field(default_factory=dict)

@dataclass
class AirflowElement:
    name: str; desc: str = ""; icon: int = 0; dtype: str = "plr_orfc"
    type_data: dict = field(default_factory=dict)

@dataclass
class Zone:
    """CONTAM zone definition.
    
    flags (U2): Bitfield controlling zone behavior (defined in contam.h):
        bit 0 (1): Variable pressure (1) vs constant pressure (0)
        bit 1 (2): Variable concentration (1) vs constant concentration (0)
        Default 3 = variable P + variable C (normal zone).
        Setting 0 = constant P + constant C (for analytical test cases only).
    color: Zone fill color. -1 = default/none.
    u_T: Temperature display units. 0=K, 2=°C (ContamW default).
    cc0: Initial species mass fractions per zone.
        List of floats (one per contaminant). Empty = use 0 for all.
        Set from previous partition's final state for continuous multi-run.
    """
    name: str; flags: int = 3; ps: int = 0; pc: int = 0; pk: int = 0
    pl: int = 1; relHt: float = 0.0; Vol: float = 100.0; T0: float = 293.15
    P0: float = 0.0; color: int = -1; u_Ht: int = 0; u_V: int = 0
    u_T: int = 2; u_P: int = 0; cdaxis: int = 0; vf_type: int = 0
    vf_node_name: str = "-"; cfd: int = 0
    cc0: list = None  # per-species initial mass fractions

@dataclass
class AirflowPath:
    flags: int = 0; pzn: int = 0; pzm: int = 0; pe: int = 1; pf: int = 0
    pw: int = 0; pa: int = 0; ps: int = 0; pc: int = 0; pld: int = 1
    X: float = 0.0; Y: float = 0.0; relHt: float = 0.0; mult: float = 1.0
    wPset: float = 0.0; wPmod: float = 1.0; wazm: float = 0.0
    Fahs: float = 0.0; Xmax: float = 0.0; Xmin: float = 0.0
    icon: int = 1; dir: int = 1; color: int = -1; u_Ht: int = 0
    u_XY: int = 0; u_dP: int = 0; u_F: int = 0; vf_type: int = 0
    vf_node_name: str = "-"; cfd: int = 0

@dataclass
class SimpleAHS:
    desc: str = ""; zone_r: int = 0; zone_s: int = 0; path_r: int = 0
    path_s: int = 0; path_x: int = 0; color: int = 0

@dataclass
class SourceSink:
    pz: int = 1; pe: int = 1; ps: int = 0; pc: int = 0; mult: float = 1.0
    CC0: float = 0.0; Xmin: float = 0.0; Ymin: float = 0.0; Hmin: float = 0.0
    Xmax: float = 0.0; Ymax: float = 0.0; Hmax: float = 0.0; color: int = 0
    u_XYZ: int = 0; vf_type: int = 0; vf_node_name: str = "-"; cfd: int = 0


# === Project (defaults from blank.prj) ===

@dataclass
class ContamProject:
    description: str = "GDS Generated"
    version: str = "3.4.0.6"; echo: int = 0
    skheight: int = 58; skwidth: int = 66; def_units: int = 0; def_flows: int = 0
    def_T: float = 293.150; udefT: int = 2; rel_N: float = 0.0
    wind_H: float = 10.0; uwH: int = 0; wind_Ao: float = 0.600; wind_a: float = 0.280
    scale: float = 1.0; uScale: int = 0; orgRow: int = 56; orgCol: int = 1
    invYaxis: int = 0; showGeom: int = 0
    # SS weather
    ss_Tambt: float = 293.150; ss_barpres: float = 101325.0
    ss_windspd: float = 0.0; ss_winddir: float = 0.0; ss_relhum: float = 0.0
    ss_daytyp: int = 1; ss_uTa: int = 2; ss_ubP: int = 0; ss_uws: int = 0; ss_uwd: int = 1
    # WPT weather
    wpt_Tambt: float = 293.150; wpt_barpres: float = 101325.0
    wpt_windspd: float = 1.0; wpt_winddir: float = 270.0; wpt_relhum: float = 0.0
    wpt_daytyp: int = 1; wpt_uTa: int = 2; wpt_ubP: int = 0; wpt_uws: int = 0; wpt_uwd: int = 1
    # Files
    WTHpath: str = ""; CTMpath: str = ""; CVFpath: str = ""; DVFpath: str = ""
    WPCfile: str = ""; EWCfile: str = ""
    WPCdesc: str = "WPC description"
    X0: float = 0.0; Y0: float = 0.0; Z0: float = 0.0; angle: float = 0.0; u_XYZ: int = 0
    epsPath: float = 0.01; epsSpcs: float = 0.01; tShift: str = "00:00:00"
    dStart: str = "1/1"; dEnd: str = "1/1"
    useWPCwp: int = 0; useWPCmf: int = 0; wpctrig: int = 0
    # Location
    latd: float = 40.0; lgtd: float = -90.0; Tznr: float = -6.0
    altd: int = 0; Tgrnd: float = 283.15; utg: int = 2; u_a: int = 0
    # Airflow NL
    sim_af: int = 1; afcalc: int = 1; afmaxi: int = 30  # sim_af: 0=SS-init-only, 1=steady-per-step
    afrcnvg: float = 1e-5; afacnvg: float = 1e-6; afrelax: float = 0.75
    uac2: int = 0; Pres: float = 50.0; uPres: int = 0
    # Airflow L
    afslae: int = 0; afrseq: int = 1; aflmaxi: int = 100
    aflcnvg: float = 1e-6; aflinit: int = 1; Tadj: int = 0
    # Contaminant
    sim_mf: int = 2; ccmaxi: int = 30; ccrcnvg: float = 1e-4  # sim_mf: 0=none, 1=SS, 2=transient, 3=cyclic
    ccacnvg: float = 1e-15; ccrelax: float = 1.250; uccc: int = 0
    mfnmthd: int = 0; mfnrseq: int = 1; mfnmaxi: int = 100
    mfnrcnvg: float = 1e-6; mfnacnvg: float = 1e-15; mfnrelax: float = 1.100
    mfngamma: float = 1.000; uccn: int = 0
    mftmthd: int = 0; mftrseq: int = 1; mftmaxi: int = 100
    mftrcnvg: float = 1e-6; mftacnvg: float = 1e-15; mftrelax: float = 1.100
    mftgamma: float = 1.000; ucct: int = 0
    mfvmthd: int = 0; mfvrseq: int = 1; mfvmaxi: int = 100
    mfvrcnvg: float = 1e-6; mfvacnvg: float = 1e-15; mfvrelax: float = 1.100; uccv: int = 0
    mf_solver: int = 0; sim_1dz: int = 1; sim_1dd: int = 0
    celldx: float = 1e-1; sim_vjt: int = 0; udx: int = 0
    cvode_mth: int = 0; cvode_rcnvg: float = 1e-6
    cvode_acnvg: float = 1e-13; cvode_dtmax: float = 0.0
    tsdens: int = 0; tsrelax: float = 0.75; tsmaxi: int = 20
    cnvgSS: int = 1; densZP: int = 0; stackD: int = 0; dodMdt: int = 0
    # Dates: Jan01 format
    date_st: str = "Jan01"; time_st: str = "00:00:00"
    date_0: str = "Jan01"; time_0: str = "00:00:00"
    date_1: str = "Jan01"; time_1: str = "24:00:00"
    time_step: str = "00:05:00"; time_list: str = "01:00:00"; time_scrn: str = "01:00:00"
    restart: int = 0; rstdate: str = "Jan01"; rsttime: str = "00:00:00"
    # Output
    _list: int = 1; _doDlg: int = 1; _pfsave: int = 1; _zfsave: int = 1; _zcsave: int = 1
    _achvol: int = 0; _achsave: int = 0; _abwsave: int = 0; _cbwsave: int = 0
    _expsave: int = 0; _ebwsave: int = 0; _zaasave: int = 0; _zbwsave: int = 0
    rzfsave: int = 0; rzmsave: int = 0; rz1save: int = 0
    csmsave: int = 1; srfsave: int = 1; logsave: int = 1
    bcexsave: int = 0; dcexsave: int = 0; pfsqlsave: int = 0
    zfsqlsave: int = 0; zcsqlsave: int = 0
    densACH: float = 1.2041; grav: float = 9.8055
    save: List[int] = field(default_factory=lambda: [0]*16)
    rvals: List[float] = field(default_factory=list)
    BldgFlowZ: int = 0; BldgFlowD: int = 0; BldgFlowC: int = 0
    cfd_ctype: int = 0; cfd_convcpl: float = 1e-2; cfd_var: int = 0; cfd_zref: int = 0
    cfd_imax: int = 1000; cfd_dtcmo: int = 1; cfd_solv: int = 1; cfd_smth: int = 1
    cfd_cvgvel: float = 1e-3; cfd_cvgt: float = 1e-3
    # Components
    species: List[Species] = field(default_factory=list)
    levels: List[Level] = field(default_factory=list)
    day_schedules: List[DaySchedule] = field(default_factory=list)
    week_schedules: List[WeekSchedule] = field(default_factory=list)
    wind_profiles: List[WindProfile] = field(default_factory=list)
    source_elements: List[SourceElement] = field(default_factory=list)
    airflow_elements: List[AirflowElement] = field(default_factory=list)
    zones: List[Zone] = field(default_factory=list)
    paths: List[AirflowPath] = field(default_factory=list)
    simple_ahs: List[SimpleAHS] = field(default_factory=list)
    source_sinks: List[SourceSink] = field(default_factory=list)


# === PRJ Writer ===

class PRJWriter:
    def write(self, p: ContamProject, filepath: str):
        with open(filepath, 'w') as f:
            W = f.write
            # === SECTION 1 (verified against blank.prj line by line) ===
            W(f"ContamW {p.version} {p.echo}\n")
            W(f"{p.description}\n")
            W(f"{p.skheight} {p.skwidth} {p.def_units} {p.def_flows} "
              f"{p.def_T:.3f} {p.udefT} {p.rel_N:.2f} {p.wind_H:.2f} "
              f"{p.uwH} {p.wind_Ao:.3f} {p.wind_a:.3f}\n")
            W(f"{p.scale:.3e} {p.uScale} {p.orgRow} {p.orgCol} "
              f"{p.invYaxis} {p.showGeom}\n")
            # SS weather
            W(f"{p.ss_Tambt:.3f} {p.ss_barpres:.1f} {p.ss_windspd:.3f} "
              f"{p.ss_winddir:.1f} {p.ss_relhum:.3f} {p.ss_daytyp} "
              f"{p.ss_uTa} {p.ss_ubP} {p.ss_uws} {p.ss_uwd}\n")
            # WPT weather
            W(f"{p.wpt_Tambt:.3f} {p.wpt_barpres:.1f} {p.wpt_windspd:.3f} "
              f"{p.wpt_winddir:.1f} {p.wpt_relhum:.3f} {p.wpt_daytyp} "
              f"{p.wpt_uTa} {p.wpt_ubP} {p.wpt_uws} {p.wpt_uwd}\n")
            # File paths
            for fp in [p.WTHpath, p.CTMpath, p.CVFpath, p.DVFpath,
                       p.WPCfile, p.EWCfile]:
                W(f"{fp if fp else 'null'}\n")
            W(f"{p.WPCdesc}\n")
            # WPC coords
            W(f"{p.X0:.3f} {p.Y0:.3f} {p.Z0:.3f} {p.angle:.2f} {p.u_XYZ}\n")
            W(f"{p.epsPath:.2f} {p.epsSpcs:.2f} {p.tShift} "
              f"{p.dStart} {p.dEnd} {p.useWPCwp} {p.useWPCmf} {p.wpctrig}\n")
            # Location
            W(f"{p.latd:.2f} {p.lgtd:.2f} {p.Tznr:.2f} "
              f"{p.altd} {p.Tgrnd:.2f} {p.utg} {p.u_a}\n")
            # Airflow NL
            W(f"{p.sim_af} {p.afcalc} {p.afmaxi} "
              f"{p.afrcnvg:.0e} {p.afacnvg:.0e} {p.afrelax:.2f} "
              f"{p.uac2} {p.Pres:.2f} {p.uPres}\n")
            # Airflow L
            W(f"{p.afslae} {p.afrseq} {p.aflmaxi} "
              f"{p.aflcnvg:.0e} {p.aflinit} {p.Tadj}\n")
            # Contaminant cyclic
            W(f"{p.sim_mf} {p.ccmaxi} {p.ccrcnvg:.2e} "
              f"{p.ccacnvg:.2e} {p.ccrelax:.3f} {p.uccc}\n")
            # Non-trace
            W(f"{p.mfnmthd} {p.mfnrseq} {p.mfnmaxi} {p.mfnrcnvg:.2e} "
              f"{p.mfnacnvg:.2e} {p.mfnrelax:.3f} {p.mfngamma:.3f} {p.uccn}\n")
            # Trace
            W(f"{p.mftmthd} {p.mftrseq} {p.mftmaxi} {p.mftrcnvg:.2e} "
              f"{p.mftacnvg:.2e} {p.mftrelax:.3f} {p.mftgamma:.3f} {p.ucct}\n")
            # CVODE
            W(f"{p.mfvmthd} {p.mfvrseq} {p.mfvmaxi} {p.mfvrcnvg:.2e} "
              f"{p.mfvacnvg:.2e} {p.mfvrelax:.3f} {p.uccv}\n")
            # Integration
            W(f"{p.mf_solver} {p.sim_1dz} {p.sim_1dd} "
              f"{p.celldx:.2e} {p.sim_vjt} {p.udx}\n")
            # CVODE params
            W(f"{p.cvode_mth} {p.cvode_rcnvg:.2e} "
              f"{p.cvode_acnvg:.2e} {p.cvode_dtmax:.2f}\n")
            # Density
            W(f"{p.tsdens} {p.tsrelax:.2f} {p.tsmaxi} "
              f"{p.cnvgSS} {p.densZP} {p.stackD} {p.dodMdt}\n")
            # Dates
            W(f"{p.date_st} {p.time_st} {p.date_0} {p.time_0} "
              f"{p.date_1} {p.time_1} {p.time_step} {p.time_list} "
              f"{p.time_scrn}\n")
            # Restart
            W(f"{p.restart} {p.rstdate} {p.rsttime}\n")
            # Output 1: list doDlg pfsave zfsave zcsave
            W(f"{p._list} {p._doDlg} {p._pfsave} {p._zfsave} {p._zcsave}\n")
            # Output 2: achvol achsave abwsave cbwsave expsave ebwsave zaasave zbwsave
            W(f"{p._achvol} {p._achsave} {p._abwsave} {p._cbwsave} "
              f"{p._expsave} {p._ebwsave} {p._zaasave} {p._zbwsave}\n")
            # Output 3
            W(f"{p.rzfsave} {p.rzmsave} {p.rz1save} "
              f"{p.csmsave} {p.srfsave} {p.logsave}\n")
            # Output 4
            W(f"{p.bcexsave} {p.dcexsave} {p.pfsqlsave} "
              f"{p.zfsqlsave} {p.zcsqlsave}\n")
            # Constants
            W(f"{p.densACH:.4f} {p.grav:.4f}\n")
            # Save array
            W(" ".join(str(s) for s in p.save) + "\n")
            # Rvals
            W(f"{len(p.rvals)} ! rvals:\n")
            if p.rvals:
                W(" ".join(f"{v:g}" for v in p.rvals) + "\n")
            # BldgFlow
            W(f"{p.BldgFlowZ} {p.BldgFlowD} {p.BldgFlowC}\n")
            # CFD
            W(f"{p.cfd_ctype} {p.cfd_convcpl:.2e} {p.cfd_var} "
              f"{p.cfd_zref} {p.cfd_imax} {p.cfd_dtcmo} "
              f"{p.cfd_solv} {p.cfd_smth} {p.cfd_cvgvel:.2e} {p.cfd_cvgt:.2e}\n")
            W("-999\n")

            # === SECTION 2: Species ===
            nctm = sum(1 for s in p.species if s.sflag == 1)
            W(f"{nctm} ! contaminants:\n")
            if nctm > 0:
                W(" ".join(str(i+1) for i,s in enumerate(p.species) if s.sflag==1) + "\n")
            W(f"{len(p.species)} ! species:\n")
            for i, s in enumerate(p.species):
                W(f"{i+1} {s.sflag} {s.ntflag} {s.molwt:g} {s.mdiam:g} "
                  f"{s.edens:g} {s.decay:g} {s.Dm:g} {s.ccdef:g} "
                  f"{s.Cp:g} {s.Kuv:g} {s.ucc} {s.umd} {s.ued} "
                  f"{s.udm} {s.ucp} {s.name}\n")
                W(f"{s.desc}\n")
            W("-999\n")

            # === SECTION 3: Levels ===
            W(f"{len(p.levels)} ! levels plus icon data:\n")
            for i, lv in enumerate(p.levels):
                W(f"{i+1} {lv.refht:.3f} {lv.delht:.3f} 0 "
                  f"{lv.u_rfht} {lv.u_dlht} {lv.name}\n")
            W("-999\n")

            # === Sections 4-8: Schedules, Wind, Kinetic, Filters ===
            W(f"{len(p.day_schedules)} ! day-schedules:\n")
            for i, ds in enumerate(p.day_schedules):
                W(f"{i+1} {len(ds.points)} {ds.shape} {ds.utyp} {ds.ucnv} {ds.name}\n")
                W(f"{ds.desc}\n")
                for t, v in ds.points:
                    W(f"{t} {v:g}\n")
            W("-999\n")

            W(f"{len(p.week_schedules)} ! week-schedules:\n")
            for i, ws in enumerate(p.week_schedules):
                W(f"{i+1} {ws.utyp} {ws.ucnv} {ws.name}\n")
                W(f"{ws.desc}\n")
                W(" ".join(str(j) for j in ws.day_indices) + "\n")
            W("-999\n")

            W(f"{len(p.wind_profiles)} ! wind pressure profiles:\n")
            for i, wp in enumerate(p.wind_profiles):
                W(f"{i+1} {len(wp.points)} {wp.profile_type} {wp.name}\n")
                W(f"{wp.desc}\n")
                for a, c in wp.points:
                    W(f"{a:g} {c:g}\n")
            W("-999\n")

            W("0 ! kinetic reactions:\n-999\n")
            W("0 ! filter elements:\n-999\n")
            W("0 ! filters:\n-999\n")

            # === SECTION 9: Source Elements ===
            W(f"{len(p.source_elements)} ! source/sink elements:\n")
            for i, se in enumerate(p.source_elements):
                W(f"{i+1} {se.species_name} {se.ctype} {se.name}\n")
                W(f"{se.desc}\n")
                td = se.type_data
                if se.ctype == "ccf":
                    W(f"{td.get('G',0):g} {td.get('D',0):g} "
                      f"{td.get('u_G',0)} {td.get('u_D',0)}\n")
            W("-999\n")

            # === SECTION 10: Airflow Elements ===
            W(f"{len(p.airflow_elements)} ! flow elements:\n")
            for i, ae in enumerate(p.airflow_elements):
                W(f"{i+1} {ae.icon} {ae.dtype} {ae.name}\n")
                W(f"{ae.desc}\n")
                td = ae.type_data
                if ae.dtype == "plr_orfc":
                    W(f"{td['lam']:g} {td['turb']:g} {td['expt']:g} "
                      f"{td['area']:g} {td['dia']:g} {td['coef']:g} "
                      f"{td['Re']:g} {td['u_A']} {td['u_D']}\n")
                elif ae.dtype == "plr_test1":
                    W(f"{td['lam']:g} {td['turb']:g} {td['expt']:g} "
                      f"{td['dP']:g} {td['Flow']:g} {td['u_P']} {td['u_F']}\n")
                elif ae.dtype == "plr_crack":
                    W(f"{td['lam']:g} {td['turb']:g} {td['expt']:g} "
                      f"{td['length']:g} {td['width']:g} {td['u_L']} {td['u_W']}\n")
                elif ae.dtype == "dor_door":
                    W(f"{td['lam']:g} {td['turb']:g} {td['expt']:g} "
                      f"{td['dTmin']:g} {td['ht']:g} {td['wd']:g} "
                      f"{td['cd']:g} {td['u_T']} {td['u_H']} {td['u_W']}\n")
                elif ae.dtype == "fan_cmf":
                    W(f"{td['Flow']:g} {td['u_F']}\n")
                elif ae.dtype == "fan_cvf":
                    W(f"{td['Flow']:g} {td['u_F']}\n")
            W("-999\n")

            W("0 ! duct elements:\n-999\n")
            W("0 ! control super elements:\n-999\n")
            W("0 ! control nodes:\n-999\n")

            # === SECTION 13: Simple AHS ===
            W(f"{len(p.simple_ahs)} ! simple AHS:\n")
            for i, ah in enumerate(p.simple_ahs):
                W(f"{i+1} {ah.zone_r} {ah.zone_s} {ah.path_r} "
                  f"{ah.path_s} {ah.path_x} {ah.color}\n")
                W(f"{ah.desc}\n")
            W("-999\n")

            # === SECTION 14: Zones ===
            W(f"{len(p.zones)} ! zones:\n")
            for i, z in enumerate(p.zones):
                W(f"{i+1} {z.flags} {z.ps} {z.pc} {z.pk} {z.pl} "
                  f"{z.relHt:g} {z.Vol:g} {z.T0:.3f} {z.P0:g} {z.name} "
                  f"{z.color} {z.u_Ht} {z.u_T} {z.u_P} {z.u_V} "
                  f"{z.cdaxis} {z.vf_type}"
                  + (f" {z.vf_node_name}" if z.vf_type > 0 else "")
                  + f" {z.cfd}\n")
            W("-999\n")

            # === SECTION 15: Init Zone Concentrations ===
            nctm = sum(1 for s in p.species if s.sflag == 1)
            nn = len(p.zones) * nctm
            W(f"{nn} ! initial zone concentrations:\n")
            for i, z in enumerate(p.zones):
                if nctm > 0:
                    if z.cc0 and len(z.cc0) >= nctm:
                        vals = " ".join(f"{z.cc0[j]:g}" for j in range(nctm))
                    else:
                        vals = " ".join("0" for _ in range(nctm))
                    W(f"{i+1} {vals}\n")
            W("-999\n")

            # === SECTION 16: Paths ===
            W(f"{len(p.paths)} ! flow paths:\n")
            for i, pa in enumerate(p.paths):
                W(f"{i+1} {pa.flags} {pa.pzn} {pa.pzm} "
                  f"{pa.pe} {pa.pf} {pa.pw} {pa.pa} "
                  f"{pa.ps} {pa.pc} {pa.pld} "
                  f"{pa.X:g} {pa.Y:g} {pa.relHt:g} "
                  f"{pa.mult:g} {pa.wPset:g} {pa.wPmod:g} "
                  f"{pa.wazm:g} {pa.Fahs:g} "
                  f"{pa.Xmax:g} {pa.Xmin:g} "
                  f"{pa.icon} {pa.dir} {pa.color} "
                  f"{pa.u_Ht} {pa.u_XY} {pa.u_dP} {pa.u_F} "
                  f"{pa.vf_type}"
                  + (f" {pa.vf_node_name}" if pa.vf_type > 0 else "")
                  + f" {pa.cfd}\n")
            W("-999\n")

            # Remaining empty sections
            W("0 ! duct junctions:\n-999\n")
            W("0 ! initial junction concentrations:\n-999\n")
            W("0 ! duct segments:\n-999\n")

            # === SECTION 20: Source/Sinks ===
            W(f"{len(p.source_sinks)} ! source/sinks:\n")
            for i, ss in enumerate(p.source_sinks):
                W(f"{i+1} {ss.pz} {ss.pe} {ss.ps} {ss.pc} "
                  f"{ss.mult:g} {ss.CC0:g} "
                  f"{ss.Xmin:g} {ss.Ymin:g} {ss.Hmin:g} "
                  f"{ss.Xmax:g} {ss.Ymax:g} {ss.Hmax:g} "
                  f"{ss.color} {ss.u_XYZ} {ss.vf_type}"
                  + (f" {ss.vf_node_name}" if ss.vf_type > 0 else "")
                  + f" {ss.cfd}\n")
            W("-999\n")

            W("0 ! occupancy schedules:\n-999\n")
            W("0 ! exposures:\n-999\n")
            W("0 ! annotations:\n-999\n")
            W("* end project file.\n")


# === Factory Functions ===

def make_CO2(ambient_ppm=415.0):
    # ccdef = ambient outdoor CO2 mass fraction.
    # ppm_vol * (molwt_CO2 / molwt_air) * 1e-6 = kg_CO2/kg_air
    ccdef = ambient_ppm * (44.01 / 28.97) * 1e-6
    return Species(name="CO2", desc="Carbon_Dioxide", sflag=1, molwt=44.01,
                   Dm=1.6e-5, ccdef=ccdef)

def make_PM25():
    return Species(name="PM2.5", desc="Fine_Particulate_Matter", sflag=1,
                   molwt=0.0, mdiam=2.5e-6, edens=1000.0, Dm=6.3e-11)

def make_test1_leak(name, dP=4.0, flow=0.001, expt=0.65, desc=""):
    turb = flow / (dP ** expt) if dP > 0 else 0.0
    return AirflowElement(name=name, desc=desc, dtype="plr_test1",
        type_data={'lam': turb, 'turb': turb, 'expt': expt,
                   'dP': dP, 'Flow': flow, 'u_P': 0, 'u_F': 0})

def make_door(name, ht=2.0, wd=0.9, cd=0.78, desc=""):
    turb = cd * ht * wd * (2.0/1.2)**0.5
    return AirflowElement(name=name, desc=desc, dtype="dor_door",
        type_data={'lam': turb, 'turb': turb, 'expt': 0.5,
                   'dTmin': 0.01, 'ht': ht, 'wd': wd, 'cd': cd,
                   'u_T': 0, 'u_H': 0, 'u_W': 0})

def make_fan_cvf(name, flow=0.1, desc=""):
    return AirflowElement(name=name, desc=desc, dtype="fan_cvf",
        type_data={'Flow': flow, 'u_F': 0})

def make_constant_source(name, species_name, G, desc=""):
    return SourceElement(name=name, desc=desc, species_name=species_name,
                         ctype="ccf", type_data={'G': G, 'D': 0.0, 'u_G': 0, 'u_D': 0})

def make_default_wind_profile(name="WndPrf_Default"):
    a = [0,22.5,45,67.5,90,112.5,135,157.5,180,202.5,225,247.5,270,292.5,315,337.5]
    c = [0.6,0.48,0.04,-0.56,-0.65,-0.56,-0.35,-0.3,-0.3,-0.3,-0.35,-0.56,-0.65,-0.56,0.04,0.48]
    return WindProfile(name=name, desc="Default_low-rise_Cp",
                       profile_type=1, points=list(zip(a, c)))


# ============================================================================
#  AIRFLOW ELEMENT LIBRARY (swappable presets)
# ============================================================================

class AirflowLib:
    """Library of common airflow elements. Use these to quickly populate models.
    
    Envelope types (plr_test1): tested at reference dP and flow rate.
      - tight_envelope:   ACH50 ~ 1.0  (passive house level)
      - typical_envelope: ACH50 ~ 5.0  (code-compliant)
      - leaky_envelope:   ACH50 ~ 15.0 (older buildings)
    
    Interior types (dor_door):
      - door_open:     standard 0.9×2.1m open doorway
      - door_undercut: 0.9m × 0.01m gap under closed door
    
    Window types (dor_pl2 - two-way opening):
      - window_operable: 0.6×1.0m casement, Cd=0.6
    
    Fan types (fan_cvf - constant volume flow):
      - exhaust_50Ls:  50 L/s bathroom/kitchen exhaust
      - supply_100Ls:  100 L/s supply fan
      - supply_150Ls:  150 L/s supply fan
    """

    @staticmethod
    def tight_envelope(name="TightEnv"):
        """Tight envelope: ~0.5 L/s per m² at 50 Pa."""
        return make_test1_leak(name, dP=50.0, flow=0.0005, expt=0.65,
                               desc="Tight_envelope_ACH50~1")

    @staticmethod
    def typical_envelope(name="TypEnv"):
        """Code-compliant: ~2.5 L/s per m² at 50 Pa."""
        return make_test1_leak(name, dP=50.0, flow=0.0025, expt=0.65,
                               desc="Typical_envelope_ACH50~5")

    @staticmethod
    def leaky_envelope(name="LeakyEnv"):
        """Older building: ~7.5 L/s per m² at 50 Pa."""
        return make_test1_leak(name, dP=50.0, flow=0.0075, expt=0.65,
                               desc="Leaky_envelope_ACH50~15")

    @staticmethod
    def door_open(name="DoorOpen"):
        """Standard open interior door 0.9×2.1m."""
        return make_door(name, ht=2.1, wd=0.9, cd=0.78, desc="Open_interior_door")

    @staticmethod
    def door_undercut(name="DoorUndercut"):
        """Closed door with 10mm undercut."""
        return make_door(name, ht=0.01, wd=0.9, cd=0.65, desc="Closed_door_undercut")

    @staticmethod
    def window_operable(name="Window"):
        """Operable casement window 0.6×1.0m."""
        return make_door(name, ht=1.0, wd=0.6, cd=0.60, desc="Operable_casement_window")

    @staticmethod
    def exhaust_50Ls(name="Exh50"):
        """Exhaust fan 50 L/s (bathroom/kitchen)."""
        return make_fan_cvf(name, flow=0.05, desc="Exhaust_50Ls")

    @staticmethod
    def supply_100Ls(name="Sup100"):
        """Supply fan 100 L/s."""
        return make_fan_cvf(name, flow=0.10, desc="Supply_100Ls")

    @staticmethod
    def supply_150Ls(name="Sup150"):
        """Supply fan 150 L/s."""
        return make_fan_cvf(name, flow=0.15, desc="Supply_150Ls")


# ============================================================================
#  SCHEDULE BUILDER (converts HH:MM points -> CONTAM DaySchedule/WeekSchedule)
# ============================================================================

def _parse_schedule_time(t_str):
    """Convert "HH:MM" string to seconds since midnight."""
    parts = t_str.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return h * 3600 + m * 60


def _build_day_schedule(name, points_hhmm, shape_str="step"):
    """Build a DaySchedule from [["HH:MM", value], ...] pairs."""
    shape = 1 if shape_str == "linear" else 0
    pts = []
    for t_str, val in points_hhmm:
        secs = _parse_schedule_time(t_str)
        pts.append((secs, float(val)))
    return DaySchedule(name=name, desc=name, shape=shape, points=pts)


def _build_week_schedule(name, wd_idx, we_idx, hol_idx=None):
    """Build a WeekSchedule mapping 12 day-types to DaySchedule indices.
    
    wd_idx: 1-based DaySchedule index for weekdays (Mon-Fri)
    we_idx: 1-based DaySchedule index for weekends (Sat+Sun)
    hol_idx: 1-based DaySchedule index for holidays (default=weekend)
    """
    if hol_idx is None:
        hol_idx = we_idx
    indices = [
        we_idx,   # 0: Sunday
        wd_idx, wd_idx, wd_idx, wd_idx, wd_idx,  # 1-5: Mon-Fri
        we_idx,   # 6: Saturday
        hol_idx, hol_idx, hol_idx, hol_idx, hol_idx,  # 7-11: Holidays
    ]
    return WeekSchedule(name=name, desc=name, day_indices=indices)


# ============================================================================
#  MODEL BUILDER (high-level API for zone/path/source creation)
# ============================================================================

class ModelBuilder:
    """High-level builder for CONTAM models from GDS zone data.
    
    Typical workflow:
        b = ModelBuilder()
        b.set_location(43.04, -76.14, altitude=127, timezone=-5)
        b.set_simulation(days=7)
        b.set_weather_epw("Syracuse.epw")  # or set_weather_ss(T=273.15, wind=5.0)
        
        b.add_zone("Office", volume=120, height=3.0)
        b.add_zone("Corridor", volume=60, height=3.0)
        
        b.connect_zones("Office", "Corridor", "door_open")
        b.add_envelope("Office", area=15.0, azimuth=0, element="typical_envelope")
        b.add_envelope("Corridor", area=8.0, azimuth=180, element="typical_envelope")
        
        b.add_co2_source("Office", occupants=5)
        
        proj = b.build()
        PRJWriter().write(proj, "model.prj")
    """

    def __init__(self):
        self._zones = {}       # name -> {volume, height, T0, zone_idx}
        self._zone_order = []  # ordered list of zone names
        self._elements = {}    # name -> AirflowElement
        self._paths = []       # list of path specs
        self._path_descs = []  # parallel list: human-readable desc per path
        self._sources = []     # list of (zone_name, se_name, mult, schedule_name)
        self._source_elements = {}  # name -> SourceElement
        self._species = {"CO2": make_CO2(), "PM2.5": make_PM25()}
        self._active_species = set()
        self._location = (43.04, -76.14, -5.0, 127)  # lat, lon, tz, alt
        self._sim_days = 1
        self._date_start = "Jan01"
        self._date_end = "Jan01"
        self._ss_weather = (293.15, 101325.0, 0.0, 0.0, 0.0)  # T,P,Ws,Wd,RH
        self._wth_path = ""
        self._wind_profile = make_default_wind_profile()
        self._level_height = 3.0
        # Solver settings (see ContamProject dataclass for definitions)
        self._sim_af = 1   # 0=SS-init-only, 1=steady-per-timestep
        self._sim_mf = 3   # 0=none, 1=SS, 2=transient (multi-day), 3=cyclic (1-day convergence)
        # Schedule support
        self._schedules = {}   # name -> {"weekday": [points], "weekend": [points], "shape": "step"}

    # --- Location & simulation ---

    def set_location(self, lat, lon, timezone=-5.0, altitude=0):
        self._location = (lat, lon, timezone, altitude)
        return self

    def set_simulation(self, days=1, start_month=1, start_day=1,
                       timestep_min=5, output_hr=1, sim_af=None, sim_mf=None):
        """Set simulation period and solver modes.
        
        sim_af: Airflow solver mode
            0 = SS init only (solve once at start)
            1 = Steady per timestep (re-solve each step) [default]
        sim_mf: Contaminant transport mode
            0 = None (airflow only)
            1 = Steady-state
            2 = Transient (runs full date range once) [default for multi-day]
            3 = Cyclic (repeats 1 day until convergence) [default for 1 day]
        """
        # Guard all inputs against None (common when GH inputs aren't connected)
        days = int(days) if days else 1
        start_month = int(start_month) if start_month else 1
        start_day = int(start_day) if start_day else 1
        timestep_min = int(timestep_min) if timestep_min else 5
        output_hr = int(output_hr) if output_hr else 1
        self._sim_days = days
        m_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
        self._date_start = f"{m_names[start_month-1]}{start_day:02d}"
        # End date
        from datetime import date, timedelta
        d0 = date(2001, start_month, start_day)
        d1 = d0 + timedelta(days=days - 1)
        self._date_end = f"{m_names[d1.month-1]}{d1.day:02d}"
        self._timestep = f"00:{timestep_min:02d}:00"
        self._output = f"{output_hr:02d}:00:00"
        # Solver modes
        if sim_af is not None:
            self._sim_af = int(sim_af)
        if sim_mf is not None:
            self._sim_mf = int(sim_mf)
        elif days > 1:
            # Auto-select: transient for multi-day (sim_mf=2 runs the full date range)
            self._sim_mf = 2
        else:
            # Single day: cyclic (sim_mf=3 repeats until convergence)
            self._sim_mf = 3
        return self

    # --- Weather ---

    def set_weather_ss(self, T_C=20.0, P=101325.0, wind_speed=0.0,
                       wind_dir=0.0, RH=0.0):
        """Set constant steady-state weather (no WTH file needed)."""
        T_C = T_C if T_C is not None else 20.0
        P = P if P is not None else 101325.0
        wind_speed = wind_speed if wind_speed is not None else 0.0
        wind_dir = wind_dir if wind_dir is not None else 0.0
        RH = RH if RH is not None else 0.0
        self._ss_weather = (T_C + 273.15, P, wind_speed, wind_dir, RH)
        self._wth_path = ""
        return self

    def set_weather_epw(self, epw_path, wth_output_path=None):
        """Set weather from EPW file, converting to WTH if needed.
        
        Priority:
          1. Use existing WTH file alongside the EPW (user pre-converted)
          2. Convert using NIST CONTAM_EPWtoWTH.exe (same folder as this script)
          3. Fallback to built-in Python converter
        """
        if wth_output_path is None:
            wth_output_path = os.path.splitext(epw_path)[0] + ".wth"

        # Priority 1: existing WTH file
        if os.path.exists(wth_output_path):
            self._wth_path = wth_output_path
            return self

        # Priority 2: NIST official converter
        script_dir = os.path.dirname(os.path.abspath(__file__))
        nist_exe = os.path.join(script_dir, "CONTAM_EPWtoWTH.exe")
        if os.path.exists(nist_exe):
            import subprocess as _sp
            try:
                _sp.run([nist_exe, epw_path, wth_output_path],
                        capture_output=True, text=True, timeout=120)
                if os.path.exists(wth_output_path):
                    self._wth_path = wth_output_path
                    return self
            except Exception:
                pass  # fall through to Python converter

        # Priority 3: built-in Python converter
        epw_to_wth(epw_path, wth_output_path)
        self._wth_path = wth_output_path
        return self

    # --- Schedules ---

    def add_schedule(self, name, weekday, weekend=None, shape="step"):
        """Register a schedule for use in sources/paths.
        
        weekday/weekend: list of [["HH:MM", value], ...] CONTAM-format pairs
        """
        self._schedules[name] = {
            'weekday': weekday,
            'weekend': weekend or weekday,
            'shape': shape,
        }
        return self

    def _build_schedules(self, project):
        """Convert registered schedules into DaySchedule/WeekSchedule objects.
        
        Returns dict {schedule_name: 1-based WeekSchedule index}.
        Index 0 means "no schedule" (always on) in CONTAM.
        """
        if not self._schedules:
            return {}
        
        day_schedules = []
        week_schedules = []
        schedule_map = {}
        
        for sch_name, sch_data in self._schedules.items():
            shape = sch_data.get('shape', 'step')
            
            wd_ds = _build_day_schedule(
                f"{sch_name}_wd", sch_data['weekday'], shape)
            day_schedules.append(wd_ds)
            wd_idx = len(day_schedules)  # 1-based
            
            we_data = sch_data.get('weekend', sch_data['weekday'])
            if we_data == sch_data['weekday']:
                we_idx = wd_idx
            else:
                we_ds = _build_day_schedule(
                    f"{sch_name}_we", we_data, shape)
                day_schedules.append(we_ds)
                we_idx = len(day_schedules)
            
            ws = _build_week_schedule(sch_name, wd_idx, we_idx)
            week_schedules.append(ws)
            schedule_map[sch_name] = len(week_schedules)
        
        project.day_schedules = day_schedules
        project.week_schedules = week_schedules
        return schedule_map

    # --- Zones ---

    def add_zone(self, name, volume, height=3.0, T_C=20.0):
        """Add a zone. In GDS, volume comes from Brep; height from level."""
        volume = volume if volume else 100.0
        height = height if height else 3.0
        T_C = T_C if T_C is not None else 20.0
        idx = len(self._zone_order) + 1
        self._zones[name] = {
            'volume': volume, 'height': height,
            'T0': T_C + 273.15, 'idx': idx
        }
        self._zone_order.append(name)
        self._level_height = max(self._level_height, height)
        return self

    # --- Connections (auto-generated airflow paths) ---

    def _ensure_element(self, element_key):
        """Get or create an airflow element from library or custom spec."""
        if element_key in self._elements:
            return self._elements[element_key]
        # Try library
        lib = AirflowLib
        factory = {
            "tight_envelope": lib.tight_envelope,
            "typical_envelope": lib.typical_envelope,
            "leaky_envelope": lib.leaky_envelope,
            "door_open": lib.door_open,
            "door_undercut": lib.door_undercut,
            "window_operable": lib.window_operable,
            "exhaust_50Ls": lib.exhaust_50Ls,
            "supply_100Ls": lib.supply_100Ls,
            "supply_150Ls": lib.supply_150Ls,
        }
        if element_key in factory:
            el = factory[element_key]()
            self._elements[el.name] = el
            return el
        raise ValueError(f"Unknown airflow element: {element_key}")

    def connect_zones(self, zone_a, zone_b, element="door_open",
                      relHt=0.0, mult=1.0):
        """Create interior path between two zones."""
        el = self._ensure_element(element)
        iz_a = self._zones[zone_a]['idx']
        iz_b = self._zones[zone_b]['idx']
        self._paths.append({
            'pzn': iz_a, 'pzm': iz_b, 'element': el.name,
            'pw': 0, 'relHt': relHt, 'mult': mult, 'wazm': 0.0,
            'type': 'interior'
        })
        return self

    def add_envelope(self, zone, area=1.0, azimuth=0.0,
                     element="typical_envelope", relHt=1.5):
        """Add envelope leakage path (zone <-> ambient).
        
        area: effective leakage area [m²] used as multiplier.
        azimuth: wall azimuth for wind pressure [degrees, 0=N].
        """
        el = self._ensure_element(element)
        iz = self._zones[zone]['idx']
        self._paths.append({
            'pzn': -1, 'pzm': iz, 'element': el.name,
            'pw': 1, 'relHt': relHt, 'mult': area, 'wazm': azimuth,
            'type': 'envelope'
        })
        return self

    def add_supply_fan(self, zone, flow_Ls=100.0, element=None):
        """Add supply fan path (ambient -> zone)."""
        if element is None:
            name = f"SupFan_{flow_Ls:.0f}Ls"
            el = make_fan_cvf(name, flow=flow_Ls / 1000.0,
                              desc=f"Supply_{flow_Ls:.0f}Ls")
            self._elements[el.name] = el
        else:
            el = self._ensure_element(element)
        iz = self._zones[zone]['idx']
        self._paths.append({
            'pzn': -1, 'pzm': iz, 'element': el.name,
            'pw': 0, 'relHt': 1.5, 'mult': 1.0, 'wazm': 0.0,
            'type': 'fan'
        })
        return self

    def add_exhaust_fan(self, zone, flow_Ls=50.0, element=None):
        """Add exhaust fan path (zone -> ambient)."""
        if element is None:
            name = f"ExhFan_{flow_Ls:.0f}Ls"
            el = make_fan_cvf(name, flow=flow_Ls / 1000.0,
                              desc=f"Exhaust_{flow_Ls:.0f}Ls")
            self._elements[el.name] = el
        else:
            el = self._ensure_element(element)
        iz = self._zones[zone]['idx']
        self._paths.append({
            'pzn': iz, 'pzm': -1, 'element': el.name,
            'pw': 0, 'relHt': 1.5, 'mult': 1.0, 'wazm': 0.0,
            'type': 'fan'
        })
        return self

    def add_opening(self, dtype, params, zone_a=None, zone_b=None,
                    relHt=0.0, mult=1.0, wazm=0.0, wind_pressure=False,
                    desc=""):
        """Add a generic opening from dtype + params (used by openings pipeline).

        dtype: 'plr_test1' or 'dor_door'
        params: dict of element parameters
        zone_a/zone_b: zone names (None = ambient)
        """
        # Build a cache key from dtype + sorted params for element dedup
        param_key = (dtype, tuple(sorted(params.items())))
        cache_name = "_opening_cache"
        if not hasattr(self, cache_name):
            self._opening_cache = {}

        if param_key in self._opening_cache:
            el_name = self._opening_cache[param_key]
        else:
            # Create a new element with SHORT name (CONTAM buffer ~16 chars).
            # Use dtype prefix + index for the element name.
            # The human-readable desc goes into the description field.
            idx = len(self._opening_cache) + 1
            prefix = dtype[:3]  # "plr", "dor", "fan"
            name = f"{prefix}_{idx}"
            # Ensure unique
            while name in self._elements:
                idx += 1
                name = f"{prefix}_{idx}"

            # Build a generic desc for the ELEMENT (shared across rooms).
            # Room-specific info belongs in the path, not the element.
            if dtype == 'plr_test1':
                safe_desc = "leak_dP{:.0f}_F{:.4f}".format(
                    params.get('dP', 50), params.get('Flow', 0.0025))
            elif dtype in ('dor_door', 'dor'):
                safe_desc = "door_{:.2f}x{:.2f}_Cd{:.2f}".format(
                    params.get('wd', 0.9), params.get('ht', 2.1), params.get('cd', 0.78))
            else:
                safe_desc = f"{dtype}_{idx}"

            if dtype == 'plr_test1':
                el = make_test1_leak(name,
                                     dP=params.get('dP', 50.0),
                                     flow=params.get('Flow', 0.0025),
                                     expt=params.get('expt', 0.65),
                                     desc=safe_desc)
            elif dtype in ('dor_door', 'dor'):
                el = make_door(name,
                               ht=params.get('ht', 2.1),
                               wd=params.get('wd', 0.9),
                               cd=params.get('cd', 0.78),
                               desc=safe_desc)
            else:
                # Fallback: treat unknown dtype as plr_test1
                el = make_test1_leak(name,
                                     dP=params.get('dP', 50.0),
                                     flow=params.get('Flow', 0.001),
                                     expt=params.get('expt', 0.65),
                                     desc=safe_desc)

            self._elements[el.name] = el
            el_name = el.name
            self._opening_cache[param_key] = el_name

        # Resolve zone indices (-1 = ambient)
        pzn = self._zones[zone_a]['idx'] if zone_a and zone_a in self._zones else -1
        pzm = self._zones[zone_b]['idx'] if zone_b and zone_b in self._zones else -1
        pw = 1 if wind_pressure else 0

        self._paths.append({
            'pzn': pzn, 'pzm': pzm, 'element': el_name,
            'pw': pw, 'relHt': relHt, 'mult': mult, 'wazm': wazm,
            'type': 'opening', 'desc': desc or ''
        })
        return self

    # --- Contaminant sources ---

    def add_co2_source(self, zone, occupants=1,
                       rate_per_person=4.8e-6, schedule=None, desc=""):
        """Add occupant CO2 source. Default: 4.8e-6 kg/s/person (sedentary).
        schedule: name of a registered schedule (from add_schedule).
        """
        self._active_species.add("CO2")
        se_name = f"OccCO2_{zone}"
        if se_name not in self._source_elements:
            self._source_elements[se_name] = make_constant_source(
                se_name, "CO2", rate_per_person,
                desc or f"CO2_occupants_{zone}")
        self._sources.append((zone, se_name, occupants, schedule))
        return self

    def add_pm25_source(self, zone, rate_kgs=1e-9, mult=1.0,
                        schedule=None, desc=""):
        """Add PM2.5 source. rate in kg/s."""
        self._active_species.add("PM2.5")
        se_name = f"PM25_{zone}"
        if se_name not in self._source_elements:
            self._source_elements[se_name] = make_constant_source(
                se_name, "PM2.5", rate_kgs,
                desc or f"PM25_source_{zone}")
        self._sources.append((zone, se_name, mult, schedule))
        return self

    # --- Build ---

    def build(self) -> ContamProject:
        """Assemble ContamProject from builder state."""
        p = ContamProject()
        p.description = "GDS_Generated_Model"

        # Location
        lat, lon, tz, alt = self._location
        p.latd = lat; p.lgtd = lon; p.Tznr = tz; p.altd = alt

        # Weather
        T, P, Ws, Wd, RH = self._ss_weather
        p.ss_Tambt = T; p.ss_barpres = P
        p.ss_windspd = Ws; p.ss_winddir = Wd; p.ss_relhum = RH
        if self._wth_path:
            p.WTHpath = self._wth_path
            # dStart/dEnd define the weather file's date coverage.
            # CONTAM rejects weather data outside this range.
            # For EPW-converted WTH files, this is always 1/1 to 12/31.
            p.dStart = "1/1"
            p.dEnd = "12/31"

        # Simulation dates
        p.date_st = self._date_start; p.date_0 = self._date_start
        p.date_1 = self._date_end
        if hasattr(self, '_timestep'):
            p.time_step = self._timestep
        if hasattr(self, '_output'):
            p.time_list = self._output; p.time_scrn = self._output
        # Solver modes
        p.sim_af = self._sim_af
        p.sim_mf = self._sim_mf

        # Species (only active ones)
        p.species = []
        if "CO2" in self._active_species:
            p.species.append(self._species["CO2"])
        if "PM2.5" in self._active_species:
            p.species.append(self._species["PM2.5"])
        if not p.species:
            p.species = [make_CO2()]
            self._active_species.add("CO2")

        # Level
        p.levels = [Level(name="Floor1", refht=0.0, delht=self._level_height)]

        # Wind profile
        p.wind_profiles = [self._wind_profile]

        # Airflow elements (deduplicated, ordered)
        elem_order = []
        elem_map = {}  # name -> 1-based index
        for path_spec in self._paths:
            ename = path_spec['element']
            if ename not in elem_map:
                elem_order.append(self._elements[ename])
                elem_map[ename] = len(elem_order)
        p.airflow_elements = elem_order

        # Zones
        p.zones = []
        for zname in self._zone_order:
            zd = self._zones[zname]
            p.zones.append(Zone(
                name=zname, Vol=zd['volume'], T0=zd['T0'],
                pl=1, relHt=zd['height'] / 2.0
            ))

        # Paths
        p.paths = []
        for ps in self._paths:
            pe_idx = elem_map[ps['element']]
            pw_idx = 1 if ps['pw'] else 0
            # CONTAM uses -1 for ambient zone index in flow paths.
            p.paths.append(AirflowPath(
                pzn=ps['pzn'], pzm=ps['pzm'], pe=pe_idx,
                pw=pw_idx, pld=1, relHt=ps['relHt'],
                mult=ps['mult'], wazm=ps['wazm']
            ))
        # Store opening descs for path manifest (parallel to p.paths)
        p._path_descs = [ps.get('desc', ps.get('type', '')) for ps in self._paths]

        # Schedules (must be built before sources that reference them)
        schedule_map = self._build_schedules(p)

        # Source elements
        se_order = []
        se_map = {}
        for _, se_name, _, _ in self._sources:
            if se_name not in se_map:
                se_order.append(self._source_elements[se_name])
                se_map[se_name] = len(se_order)
        p.source_elements = se_order

        # Source/sinks (with schedule wiring)
        p.source_sinks = []
        for zone_name, se_name, mult, sch_name in self._sources:
            pz = self._zones[zone_name]['idx']
            pe = se_map[se_name]
            ps_idx = schedule_map.get(sch_name, 0) if sch_name else 0
            p.source_sinks.append(SourceSink(pz=pz, pe=pe, ps=ps_idx, mult=mult))

        return p


# ============================================================================
#  SCHEDULE PARSING (moved from Runner — no Rhino dependency)
# ============================================================================

# Cumulative days per month (non-leap)
_MONTH_DAYS = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
_MONTH_CUM = [sum(_MONTH_DAYS[:i+1]) for i in range(13)]  # [0, 31, 59, 90, ...]


def _md_to_doy(md):
    """Convert [month, day] to day-of-year (1-based)."""
    return _MONTH_CUM[md[0] - 1] + md[1]


def _doy_to_md(doy):
    """Convert day-of-year (1-based) to [month, day]."""
    for m in range(12, 0, -1):
        if doy > _MONTH_CUM[m - 1]:
            return [m, doy - _MONTH_CUM[m - 1]]
    return [1, 1]


def _days_between(start_md, end_md):
    """Compute number of days in [start, end] range (inclusive), handling year wrap."""
    s = _md_to_doy(start_md)
    e = _md_to_doy(end_md)
    return (e - s + 1) if e >= s else (365 - s + e + 1)


def _hourly_to_points(values_24):
    """Convert 24-value hourly array to CONTAM [["HH:MM", value], ...] pairs.
    
    Only emits change-points (where value differs from previous).
    """
    if not values_24 or len(values_24) != 24:
        return [["00:00", 0.0], ["24:00", 0.0]]
    points = []
    prev = None
    for h in range(24):
        v = float(values_24[h])
        if prev is None or abs(v - prev) > 1e-6:
            points.append([f"{h:02d}:00", round(v, 4)])
        prev = v
    last = float(values_24[23])
    if not points or points[-1][0] != "24:00":
        points.append(["24:00", round(last, 4)])
    return points


def _parse_program_data(program_data, zones):
    """Parse HB ProgramType JSON strings into CONTAM schedules + sources.
    
    Moved from Runner to v3 for:
      1. Python 3 compatibility (f-strings, better error handling)
      2. Access to seasonal rule parsing (Phase 2 — see _detect_seasonal_segments)
    
    Extracts the first weekday rule and default (weekend) day schedule.
    For seasonal schedules with multiple date ranges, use _detect_seasonal_segments()
    which returns per-season schedule/source sets for multi-run simulation.
    
    Args:
        program_data: list of JSON strings (one per room, same order as zones)
        zones: list of zone dicts with 'name', 'volume', 'height'
    
    Returns:
        tuple (schedules_dict, sources_list, diag_dict)
    """
    schedules = {}
    sources = []
    seen = {}
    skipped = 0
    room_occ = []
    
    for i, pjson in enumerate(program_data):
        if i >= len(zones):
            break
        if not pjson:
            skipped += 1
            continue
        
        try:
            prog = json.loads(pjson) if isinstance(pjson, str) else pjson
            if not isinstance(prog, dict):
                skipped += 1
                continue
            
            people = prog.get('people')
            if not people or not isinstance(people, dict):
                skipped += 1
                continue
            
            occ_sched = people.get('occupancy_schedule')
            if not occ_sched or not isinstance(occ_sched, dict):
                skipped += 1
                continue
            
            # Build day_schedule lookup
            ds_map = {}
            for ds in occ_sched.get('day_schedules', []):
                if isinstance(ds, dict) and 'identifier' in ds:
                    vals = ds.get('values', [0.0] * 24)
                    if isinstance(vals, list) and len(vals) == 24:
                        ds_map[ds['identifier']] = vals
            if not ds_map:
                skipped += 1
                continue
            
            # Weekend = default_day_schedule
            default_name = occ_sched.get('default_day_schedule', '')
            weekend_vals = ds_map.get(default_name, [0.0] * 24)
            
            # Weekday = first rule with apply_monday
            weekday_vals = None
            for rule in occ_sched.get('schedule_rules', []):
                if isinstance(rule, dict) and (rule.get('apply_monday') or rule.get('apply_tuesday')):
                    wd_name = rule.get('schedule_day', '')
                    weekday_vals = ds_map.get(wd_name)
                    break
            if weekday_vals is None:
                weekday_vals = weekend_vals
            
            # Validate numeric
            try:
                weekday_vals = [float(v) for v in weekday_vals]
                weekend_vals = [float(v) for v in weekend_vals]
            except (TypeError, ValueError):
                skipped += 1
                continue
            
            # Occupant count: people_per_area × floor_area
            ppa = people.get('people_per_area', 0)
            if ppa is None or not isinstance(ppa, (int, float)):
                ppa = 0
            vol = zones[i].get('volume', 100)
            ht = zones[i].get('height', 3.0)
            floor_area = vol / ht if ht > 0 else vol / 3.0
            occ_count = max(1, int(round(ppa * floor_area))) if ppa > 0 else 1
            
            peak_frac = max(max(weekday_vals), max(weekend_vals))
            room_occ.append((zones[i]['name'], occ_count, round(peak_frac, 3)))
            
            # Dedup: identical schedule patterns share one CONTAM schedule
            sched_key = (tuple(weekday_vals), tuple(weekend_vals))
            if sched_key in seen:
                sched_name = seen[sched_key]
            else:
                display = prog.get('display_name', f'Room{i}')
                sched_name = "occ_{}".format(
                    str(display).lower().replace(" ", "_").replace("-", "_"))
                if sched_name in schedules and sched_key not in seen:
                    sched_name = f"{sched_name}_r{i}"
                
                schedules[sched_name] = {
                    "weekday": _hourly_to_points(weekday_vals),
                    "weekend": _hourly_to_points(weekend_vals),
                    "shape": "step",
                }
                seen[sched_key] = sched_name
            
            sources.append({
                'zone': zones[i]['name'],
                'species': 'CO2',
                'occupants': occ_count,
                'schedule': sched_name,
            })
        
        except Exception:
            skipped += 1
            continue
    
    diag = {'skipped': skipped, 'room_occ': room_occ}
    return schedules, sources, diag


# ============================================================================
#  CONTAM OCCUPANCY (lightweight wireless bridge from Hub)
# ============================================================================

def _parse_contam_occupancy(occ_data, zones):
    """Parse the lightweight GDS_CONTAM_OCC format into CONTAM schedules + sources.

    occ_data: dict with 'rooms' key mapping room_name -> {occupants, weekday, weekend}
    zones: list of zone dicts with 'name', 'volume', 'height'

    Returns: (schedules_dict, sources_list, diag_dict)
        Same shape as _parse_program_data output, so downstream code is unchanged.
    """
    rooms = occ_data.get('rooms', {})
    schedules = {}
    sources = []
    seen = {}   # dedup: (wd_tuple, we_tuple) -> schedule_name
    matched = 0
    skipped = 0
    room_occ = []

    # Build index-based fallback: Hub rooms are ordered by HB room index,
    # RUNNER zones are ordered by brep index — same order, different names.
    rooms_by_index = list(rooms.values())
    name_matched = 0
    index_matched = 0

    for i, z in enumerate(zones):
        # Try name match first
        room = rooms.get(z['name'])
        if room:
            name_matched += 1
        # Fallback: index-based match (same order, different naming)
        if not room and i < len(rooms_by_index):
            room = rooms_by_index[i]
            if room:
                index_matched += 1
        if not room:
            skipped += 1
            continue

        # Validate and extract
        try:
            weekday_vals = [float(v) for v in room['weekday']]
            weekend_vals = [float(v) for v in room.get('weekend', room['weekday'])]
            occ_count = int(room.get('occupants', 1))
        except (TypeError, ValueError, KeyError):
            skipped += 1
            continue

        if len(weekday_vals) != 24 or len(weekend_vals) != 24:
            skipped += 1
            continue

        peak_frac = max(max(weekday_vals), max(weekend_vals))
        room_occ.append((z['name'], occ_count, round(peak_frac, 3)))

        # Dedup: identical schedule patterns share one CONTAM schedule
        sched_key = (tuple(weekday_vals), tuple(weekend_vals))
        if sched_key in seen:
            sched_name = seen[sched_key]
        else:
            sched_name = "occ_{}".format(z['name'].lower().replace(" ", "_"))
            schedules[sched_name] = {
                "weekday": _hourly_to_points(weekday_vals),
                "weekend": _hourly_to_points(weekend_vals),
                "shape": "step",
            }
            seen[sched_key] = sched_name

        sources.append({
            'zone': z['name'],
            'species': 'CO2',
            'occupants': occ_count,
            'schedule': sched_name,
        })
        matched += 1

    diag = {'matched': matched, 'skipped': skipped, 'room_occ': room_occ,
            'name_matched': name_matched, 'index_matched': index_matched}
    return schedules, sources, diag


def _detect_seasonal_segments_from_occ(occ_data, zones):
    """Detect seasonal schedule segments from the lightweight occupancy format.

    Each room's 'seasonal' array contains explicit date ranges with weekday/weekend
    overrides.  This is much simpler than the HB ScheduleRuleset path — no priority
    resolution needed, just direct date-range lookup.

    Returns:
        list of segment dicts (same shape as _detect_seasonal_segments output):
          [{'start_date': [m,d], 'end_date': [m,d], 'label': str,
            'schedules': {name: {weekday, weekend, shape}},
            'sources': [source_dicts]}, ...]
        Empty list if no seasonal variation detected.
    """
    rooms = occ_data.get('rooms', {})

    # Build index-based fallback (same as _parse_contam_occupancy)
    rooms_by_index = list(rooms.values())

    # Collect all unique seasonal date ranges across all rooms
    all_boundaries = set()
    all_boundaries.add(1)    # Jan 1
    all_boundaries.add(366)  # sentinel: past Dec 31

    has_seasonal = False
    for i, z in enumerate(zones):
        room = rooms.get(z['name'], {})
        if not room and i < len(rooms_by_index):
            room = rooms_by_index[i] or {}
        for sr in room.get('seasonal', []):
            sd = sr.get('start', [1, 1])
            ed = sr.get('end', [12, 31])
            all_boundaries.add(_md_to_doy(sd))
            all_boundaries.add(_md_to_doy(ed) + 1)
            has_seasonal = True

    if not has_seasonal:
        return []

    # Sort boundaries to form segment edges
    boundaries = sorted(all_boundaries)

    # Build segments from boundary pairs
    raw_segments = []
    for k in range(len(boundaries) - 1):
        s_doy = boundaries[k]
        e_doy = boundaries[k + 1] - 1
        if e_doy > 365:
            e_doy = 365
        if s_doy > e_doy:
            continue
        raw_segments.append((s_doy, e_doy))

    # For each segment, resolve each room's effective schedule
    segments = []
    for s_doy, e_doy in raw_segments:
        mid_doy = (s_doy + e_doy) // 2   # representative day for rule matching
        schedules = {}
        sources = []
        seen = {}

        for i, z in enumerate(zones):
            room = rooms.get(z['name'])
            if not room and i < len(rooms_by_index):
                room = rooms_by_index[i]
            if not room:
                continue

            # Default schedule
            wd = room.get('weekday', [0.0] * 24)
            we = room.get('weekend', wd)

            # Check if any seasonal override covers this segment
            for sr in room.get('seasonal', []):
                sr_s = _md_to_doy(sr.get('start', [1, 1]))
                sr_e = _md_to_doy(sr.get('end', [12, 31]))

                if sr_s <= sr_e:
                    in_range = sr_s <= mid_doy <= sr_e
                else:
                    # Year-wrapping (e.g., Nov 1 to Feb 28)
                    in_range = mid_doy >= sr_s or mid_doy <= sr_e

                if in_range:
                    wd = sr.get('weekday', wd)
                    we = sr.get('weekend', we)
                    break   # first match wins

            try:
                wd = [float(v) for v in wd]
                we = [float(v) for v in we]
            except (TypeError, ValueError):
                continue

            occ_count = int(room.get('occupants', 1))

            # Dedup schedules within this segment
            sched_key = (tuple(wd), tuple(we))
            if sched_key in seen:
                sched_name = seen[sched_key]
            else:
                sched_name = "occ_{}".format(z['name'].lower().replace(" ", "_"))
                schedules[sched_name] = {
                    "weekday": _hourly_to_points(wd),
                    "weekend": _hourly_to_points(we),
                    "shape": "step",
                }
                seen[sched_key] = sched_name

            sources.append({
                'zone': z['name'],
                'species': 'CO2',
                'occupants': occ_count,
                'schedule': sched_name,
            })

        sd = _doy_to_md(s_doy)
        ed = _doy_to_md(e_doy)
        label = "seg_{:02d}{:02d}_{:02d}{:02d}".format(sd[0], sd[1], ed[0], ed[1])

        segments.append({
            'start_date': sd,
            'end_date': ed,
            'label': label,
            'schedules': schedules,
            'sources': sources,
        })

    # If all segments have identical schedule fingerprints, collapse to empty
    # (means no actual seasonal variation — single schedule set suffices)
    if len(segments) > 1:
        fingerprints = set()
        for seg in segments:
            # Use JSON string as hashable fingerprint (schedule values are lists)
            fp = json.dumps(seg['schedules'], sort_keys=True)
            fingerprints.add(fp)
        if len(fingerprints) == 1:
            return []   # no actual variation

    return segments


# ============================================================================
#  SEASONAL SCHEDULE DETECTION AND PARTITIONING (Phase 2)
# ============================================================================

def _detect_seasonal_segments(program_data, zones):
    """Detect seasonal schedule rules from HB ProgramType data.
    
    Resolves overlapping HB ScheduleRuleset rules using priority order:
    rules earlier in the schedule_rules list take precedence (first match wins).
    For each day-of-year, determines which rule applies per room, then groups
    consecutive days with identical effective schedules into non-overlapping
    segments.
    
    Returns:
        list of segment dicts, sorted by start DOY:
          [{'start_date': [m,d], 'end_date': [m,d], 'label': str,
            'schedules': {name: {weekday, weekend, shape}},
            'sources': [source_dicts]}, ...]
        Empty list if no seasonal variation detected (single effective set).
    """
    if not program_data or not zones:
        return []
    
    # Step 1: Parse all rooms' rules with priority and day-schedule lookups
    room_rules = []  # per-room: list of (rule_order, start_doy, end_doy, wd_vals, we_vals)
    room_defaults = []  # per-room: (wd_default, we_default)
    room_occ = []  # per-room: occupant count
    room_displays = []
    
    for i, pjson in enumerate(program_data):
        if i >= len(zones):
            break
        if not pjson:
            room_rules.append([])
            room_defaults.append(([0.0]*24, [0.0]*24))
            room_occ.append(1)
            room_displays.append(f'Room{i}')
            continue
        try:
            prog = json.loads(pjson) if isinstance(pjson, str) else pjson
            people = prog.get('people', {})
            occ_sched = people.get('occupancy_schedule', {})
            
            # Build day_schedule value lookup
            ds_map = {}
            for ds in occ_sched.get('day_schedules', []):
                if isinstance(ds, dict) and 'identifier' in ds:
                    vals = ds.get('values', [0.0]*24)
                    if isinstance(vals, list) and len(vals) == 24:
                        ds_map[ds['identifier']] = [float(v) for v in vals]
            
            # Default schedule (fallback when no rule matches)
            default_name = occ_sched.get('default_day_schedule', '')
            default_vals = ds_map.get(default_name, [0.0]*24)
            room_defaults.append((default_vals, default_vals))
            
            # Parse rules in priority order (index 0 = highest priority)
            rules = []
            for ri, rule in enumerate(occ_sched.get('schedule_rules', [])):
                sd = rule.get('start_date', [1, 1])
                ed = rule.get('end_date', [12, 31])
                s_doy = _md_to_doy(sd)
                e_doy = _md_to_doy(ed)
                
                is_wd = rule.get('apply_monday') or rule.get('apply_tuesday')
                is_we = rule.get('apply_saturday') or rule.get('apply_sunday')
                
                sch_day_name = rule.get('schedule_day', '')
                vals = ds_map.get(sch_day_name, default_vals)
                
                rules.append({
                    'priority': ri,
                    's_doy': s_doy, 'e_doy': e_doy,
                    'is_weekday': bool(is_wd), 'is_weekend': bool(is_we),
                    'vals': vals,
                })
            room_rules.append(rules)
            
            # Occupant count
            ppa = people.get('people_per_area', 0)
            if ppa is None or not isinstance(ppa, (int, float)):
                ppa = 0
            vol = zones[i].get('volume', 100)
            ht = zones[i].get('height', 3.0)
            floor_area = vol / ht if ht > 0 else vol / 3.0
            room_occ.append(max(1, int(round(ppa * floor_area))) if ppa > 0 else 1)
            room_displays.append(prog.get('display_name', f'Room{i}'))
        except Exception:
            room_rules.append([])
            room_defaults.append(([0.0]*24, [0.0]*24))
            room_occ.append(1)
            room_displays.append(f'Room{i}')
    
    # Step 2: For each DOY, resolve effective weekday/weekend schedule per room
    # Result: day_fingerprints[doy] = hashable key identifying the schedule set
    def _resolve_day(doy, room_idx):
        """Return (weekday_vals, weekend_vals) for a given DOY and room."""
        wd_vals = room_defaults[room_idx][0]
        we_vals = room_defaults[room_idx][1]
        wd_found = False
        we_found = False
        
        for rule in room_rules[room_idx]:  # already in priority order
            # Check if this DOY falls in the rule's date range
            if rule['s_doy'] <= rule['e_doy']:
                in_range = rule['s_doy'] <= doy <= rule['e_doy']
            else:
                # Year-wrapping range (e.g., Nov 1 to Feb 28)
                in_range = doy >= rule['s_doy'] or doy <= rule['e_doy']
            
            if not in_range:
                continue
            
            # First matching rule wins (per day type)
            if rule['is_weekday'] and not wd_found:
                wd_vals = rule['vals']
                wd_found = True
            if rule['is_weekend'] and not we_found:
                we_vals = rule['vals']
                we_found = True
            
            if wd_found and we_found:
                break
        
        return (tuple(wd_vals), tuple(we_vals))
    
    n_rooms = min(len(program_data), len(zones))
    
    # Build fingerprint for each DOY (tuple of all rooms' resolved schedules)
    day_fingerprints = {}
    for doy in range(1, 366):
        fp = tuple(_resolve_day(doy, ri) for ri in range(n_rooms))
        day_fingerprints[doy] = fp
    
    # Step 3: Group consecutive days with the same fingerprint
    segments_raw = []
    current_fp = day_fingerprints[1]
    current_start = 1
    
    for doy in range(2, 366):
        if day_fingerprints[doy] != current_fp:
            segments_raw.append((current_start, doy - 1, current_fp))
            current_fp = day_fingerprints[doy]
            current_start = doy
    segments_raw.append((current_start, 365, current_fp))
    
    # If only one segment covers the whole year, no seasonal variation
    if len(segments_raw) <= 1:
        return []
    
    # Step 4: Build schedule/source sets for each segment
    m_names = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]
    segments = []
    
    for s_doy, e_doy, fp in segments_raw:
        sd = _doy_to_md(s_doy)
        ed = _doy_to_md(e_doy)
        label = f"{m_names[sd[0]-1]}{sd[1]:02d}-{m_names[ed[0]-1]}{ed[1]:02d}"
        
        seg_schedules = {}
        seg_sources = []
        seen = {}
        
        for ri in range(n_rooms):
            wd_vals, we_vals = fp[ri]
            wd_list = list(wd_vals)
            we_list = list(we_vals)
            occ_count = room_occ[ri]
            
            # Dedup
            sched_key = (wd_vals, we_vals)
            if sched_key in seen:
                sched_name = seen[sched_key]
            else:
                display = room_displays[ri]
                sched_name = "occ_{}".format(
                    str(display).lower().replace(" ", "_").replace("-", "_"))
                if sched_name in seg_schedules and sched_key not in seen:
                    sched_name = f"{sched_name}_r{ri}"
                seg_schedules[sched_name] = {
                    "weekday": _hourly_to_points(wd_list),
                    "weekend": _hourly_to_points(we_list),
                    "shape": "step",
                }
                seen[sched_key] = sched_name
            
            seg_sources.append({
                'zone': zones[ri]['name'],
                'species': 'CO2',
                'occupants': occ_count,
                'schedule': sched_name,
            })
        
        segments.append({
            'start_date': sd,
            'end_date': ed,
            'label': label,
            'schedules': seg_schedules,
            'sources': seg_sources,
        })
    
    return segments


def _partition_sim_period(sim_start, sim_end, seasonal_segments):
    """Partition the simulation period using pre-resolved non-overlapping segments.
    
    Clips seasonal_segments (from _detect_seasonal_segments, which are already
    non-overlapping and cover the full year) to the actual simulation period.
    
    Args:
        sim_start: [month, day] simulation start
        sim_end: [month, day] simulation end
        seasonal_segments: list from _detect_seasonal_segments (non-overlapping)
    
    Returns:
        list of run dicts:
          [{'start_date': [m,d], 'end_date': [m,d], 'label': str,
            'schedules': {...}, 'sources': [...], 'days': int}, ...]
    """
    if not seasonal_segments:
        return []
    
    sim_s = _md_to_doy(sim_start)
    sim_e = _md_to_doy(sim_end)
    
    runs = []
    for seg in seasonal_segments:
        seg_s = _md_to_doy(seg['start_date'])
        seg_e = _md_to_doy(seg['end_date'])
        
        # Compute overlap with sim period
        # For non-wrapping sim period (sim_s <= sim_e):
        if sim_s <= sim_e:
            # Normal range: both within same year
            ov_start = max(sim_s, seg_s)
            ov_end = min(sim_e, seg_e)
            if ov_start > ov_end:
                continue  # no overlap
        else:
            # Year-wrapping sim period (e.g. Nov 1 -> Feb 28)
            # Segment overlaps if it touches either side
            if seg_e < sim_s and seg_s > sim_e:
                continue  # no overlap
            ov_start = seg_s if seg_s >= sim_s or seg_s <= sim_e else sim_s
            ov_end = seg_e if seg_e <= sim_e or seg_e >= sim_s else sim_e
        
        days = ov_end - ov_start + 1
        if days <= 0:
            continue
        
        runs.append({
            'start_date': _doy_to_md(ov_start),
            'end_date': _doy_to_md(ov_end),
            'label': seg['label'],
            'schedules': seg['schedules'],
            'sources': seg['sources'],
            'days': days,
        })
    
    # Sort by start DOY
    runs.sort(key=lambda r: _md_to_doy(r['start_date']))
    return runs


def _extract_final_cc(sim_result):
    """Extract final-timestep species mass fractions for cc0 carry-over.
    
    Returns list of lists: cc0[zone_idx] = [mf_species_0, mf_species_1, ...]
    """
    if not sim_result or not sim_result.timesteps:
        return []
    
    # Find the last non-summary timestep
    last_ts = None
    for ts in reversed(sim_result.timesteps):
        if not ts.get('is_summary', False):
            last_ts = ts
            break
    
    if not last_ts:
        return []
    
    cc0 = []
    for zcc in last_ts.get('zone_cc', []):
        cc0.append(list(zcc['cc']))
    return cc0


def _stitch_summary_jsons(segment_results, zone_names, species_names, npath, path_manifest=None):
    """Stitch hourly results from multiple seasonal segments into one summary.
    
    Args:
        segment_results: list of (segment_meta, sim_result, proj) tuples
        zone_names: list of zone names
        species_names: list of species names
        npath: number of paths
        path_manifest: path manifest from first segment (paths are the same across segments)
    
    Returns:
        dict: combined summary JSON structure
    """
    import json as jsonmod
    
    summary = {
        'nzone': len(zone_names),
        'npath': npath,
        'nctm': len(species_names),
        'species': species_names,
        'zones': zone_names,
        'hourly': [],
        'seasonal_segments': [],
    }
    
    if path_manifest:
        summary['paths'] = path_manifest
    
    for seg_meta, sim_result, proj in segment_results:
        seg_info = {
            'start': seg_meta['start_date'],
            'end': seg_meta['end_date'],
            'label': seg_meta['label'],
            'hours': 0,
        }
        
        # Append hourly data from this segment
        seg_hours = 0
        for ts in sim_result.timesteps:
            if ts.get('is_summary', False):
                continue
            if ts['sim_time'] % 3600 != 0:
                continue
            
            entry = {
                'day': ts['dayofy'],
                'hour': ts['sim_time'] // 3600,
                'T_amb_C': ts['Tambt'] - 273.15,
                'wind_ms': ts['windspd'],
                'zone_data': {}
            }
            for i, zname in enumerate(zone_names):
                zd = {}
                if i < len(ts.get('zones', [])):
                    zd['T_C'] = ts['zones'][i]['T'] - 273.15
                    zd['P_Pa'] = ts['zones'][i]['P']
                if i < len(ts.get('zone_cc', [])):
                    for j, c in enumerate(ts['zone_cc'][i]['cc']):
                        sp = species_names[j] if j < len(species_names) else f"Sp{j}"
                        if 'CO2' in sp:
                            zd['CO2_ppm'] = round(c * (28.97/44.01) * 1e6, 1)
                        elif 'PM' in sp:
                            zd['PM25_ugm3'] = round(c * 1.2 * 1e9, 2)
                        else:
                            zd[sp + '_kgkg'] = c
                entry['zone_data'][zname] = zd
            summary['hourly'].append(entry)
            seg_hours += 1
        
        seg_info['hours'] = seg_hours
        summary['seasonal_segments'].append(seg_info)
    
    return summary


def _build_path_manifest(sim_result, proj):
    """Build path manifest dict for summary JSON (same logic as export_summary_json)."""
    if not proj or not hasattr(proj, 'paths') or not proj.paths:
        return None

    def _zone_name(idx):
        if idx <= 0:
            return "Ambient"
        if idx <= len(proj.zones):
            return proj.zones[idx - 1].name
        return f"Z{idx}"

    def _elem_name(pe):
        if 1 <= pe <= len(proj.airflow_elements):
            return proj.airflow_elements[pe - 1].name
        return f"Elem{pe}"

    def _elem_dtype(pe):
        if 1 <= pe <= len(proj.airflow_elements):
            return proj.airflow_elements[pe - 1].dtype
        return "unknown"

    def _elem_desc(pe):
        if 1 <= pe <= len(proj.airflow_elements):
            return proj.airflow_elements[pe - 1].desc
        return ""

    # Accumulate average flows
    path_flows = {}
    for ts in sim_result.timesteps:
        if ts.get('is_summary', False):
            continue
        for pf in ts.get('paths', []):
            nr = pf['nr']
            if nr not in path_flows:
                path_flows[nr] = {'dP_sum': 0.0, 'F0_sum': 0.0, 'F1_sum': 0.0, 'n': 0}
            path_flows[nr]['dP_sum'] += pf['dP']
            path_flows[nr]['F0_sum'] += pf['Flow0']
            path_flows[nr]['F1_sum'] += pf['Flow1']
            path_flows[nr]['n'] += 1

    path_descs = getattr(proj, '_path_descs', [])
    manifest = []
    for pi, pa in enumerate(proj.paths):
        nr = pi + 1
        pdesc = path_descs[pi] if pi < len(path_descs) else ''
        if not pdesc:
            pdesc = _elem_desc(pa.pe)
        entry = {
            'nr': nr,
            'from': _zone_name(pa.pzn),
            'to': _zone_name(pa.pzm),
            'element': _elem_name(pa.pe),
            'dtype': _elem_dtype(pa.pe),
            'desc': pdesc,
            'mult': pa.mult,
            'wazm': pa.wazm,
            'relHt': pa.relHt,
            'wind': pa.pw > 0,
        }
        pf = path_flows.get(nr)
        if pf and pf['n'] > 0:
            n = pf['n']
            avg_net = (pf['F0_sum'] + pf['F1_sum']) / n
            entry['avg_dP'] = round(pf['dP_sum'] / n, 4)
            entry['avg_flow_kg_s'] = round(avg_net, 8)
            entry['avg_flow_L_s'] = round(avg_net / 1.2 * 1000, 3)
        manifest.append(entry)
    return manifest


def _stitch_csv(segment_results, csv_path, species_names, zone_names):
    """Write combined CSV from multiple segment results."""
    import csv as csvmod
    with open(csv_path, 'w', newline='') as f:
        w = csvmod.writer(f)
        header = ['segment', 'day', 'time_s', 'T_amb_K', 'P_amb_Pa', 'Ws_ms', 'Wd_deg']
        for zn in zone_names:
            header += [f'{zn}_T_K', f'{zn}_P_Pa', f'{zn}_rho']
            for sp in species_names:
                header.append(f'{zn}_{sp}_kgkg')
        w.writerow(header)
        for seg_meta, sim, proj in segment_results:
            label = seg_meta['label']
            for ts in sim.timesteps:
                if ts.get('is_summary', False):
                    continue
                row = [label, ts['dayofy'], ts['sim_time'],
                       ts['Tambt'], ts['barpres'],
                       ts['windspd'], ts['winddir']]
                for i in range(sim.nzone):
                    if i < len(ts['zones']):
                        z = ts['zones'][i]
                        row += [z['T'], z['P'], z['rho']]
                    if i < len(ts['zone_cc']):
                        row += ts['zone_cc'][i]['cc']
                w.writerow(row)
    return csv_path


# ============================================================================
#  EPW -> WTH CONVERTER
# ============================================================================

def epw_to_wth(epw_path, wth_path):
    """Convert EnergyPlus EPW weather file to CONTAM WTH format.

    Produces a ContamW 2.0 WTH file with the correct section order:
      1. Header (WeatherFile, LOCATION, start/end dates)
      2. Day table (365 rows: Date, DofW, Dtype, DST, Tgrnd)
      3. Hourly data (8760 rows: 12 tab-separated columns)

    EPW fields used (0-indexed):
      0: year, 1: month, 2: day, 3: hour
      6: dry-bulb temp [C], 7: dew-point temp [C]
      8: relative humidity [%], 9: atmospheric pressure [Pa]
     12: horizontal infrared radiation [Wh/m2]
     13: global horizontal radiation [Wh/m2]
     14: direct normal radiation [Wh/m2]
     20: wind speed [m/s], 21: wind direction [deg]
     33: liquid precipitation depth [mm]
    """
    import csv
    from datetime import date as _date
    SIGMA = 5.67e-8
    TGRND = 283.15

    # ── Parse EPW header for location info ──
    with open(epw_path, 'r') as f:
        header_lines = []
        for _ in range(8):
            header_lines.append(f.readline().strip())
    loc = header_lines[0].split(',')
    city    = loc[1].strip() if len(loc) > 1 else "Unknown"
    state   = loc[2].strip() if len(loc) > 2 else ""
    country = loc[3].strip() if len(loc) > 3 else ""
    source  = loc[4].strip() if len(loc) > 4 else ""
    wmo     = loc[5].strip() if len(loc) > 5 else ""
    lat  = float(loc[6]) if len(loc) > 6 else 0.0
    lon  = float(loc[7]) if len(loc) > 7 else 0.0
    tz   = float(loc[8]) if len(loc) > 8 else 0.0
    elev = float(loc[9]) if len(loc) > 9 else 0.0

    # ── Parse EPW data rows ──
    rows = []
    with open(epw_path, 'r') as f:
        for _ in range(8):
            f.readline()
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 22:
                continue
            try:
                yr   = int(row[0]);  mo  = int(row[1])
                dy   = int(row[2]);  hr  = int(row[3])
                tdb  = float(row[6])
                tdp  = float(row[7])
                rh   = float(row[8])
                patm = float(row[9])
                ir   = float(row[12]) if len(row) > 12 else 0.0
                ghi  = float(row[13]) if len(row) > 13 else 0.0
                dni  = float(row[14]) if len(row) > 14 else 0.0
                ws   = float(row[20])
                wd   = float(row[21])
                precip = 0.0
                if len(row) > 33 and row[33] not in ('', '999'):
                    try:    precip = float(row[33])
                    except: precip = 0.0
            except (ValueError, IndexError):
                continue
            rows.append({
                'yr': yr, 'mo': mo, 'dy': dy, 'hr': hr,
                'tdb': tdb, 'tdp': tdp, 'rh': rh, 'patm': patm,
                'ir': ir, 'ghi': ghi, 'dni': dni,
                'ws': ws, 'wd': wd, 'precip': precip,
            })

    if not rows:
        raise ValueError("No valid data rows found in EPW: {}".format(epw_path))

    year = rows[0]['yr']

    # ── Helpers ──
    def _humidity_ratio(tdp_c, p_pa):
        """Humidity ratio (g/kg dry air) from dew point and pressure."""
        pw = 611.21 * math.exp(17.502 * tdp_c / (240.97 + tdp_c))
        return 621.97 * pw / (p_pa - pw) if p_pa > pw else 0.0

    def _sky_temp(ir_wm2):
        """Sky temperature (K) from horizontal infrared radiation (W/m2)."""
        if ir_wm2 <= 0:
            return 250.0
        return (ir_wm2 / SIGMA) ** 0.25

    # ── Build day table (365 entries, all before hourly data) ──
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day_table = []
    for mo in range(1, 13):
        for dy in range(1, days_in_month[mo - 1] + 1):
            try:
                d = _date(year, mo, dy)
            except ValueError:
                d = _date(2023, mo, dy)
            # CONTAM DofW: 1=Sunday, 2=Monday, ..., 7=Saturday
            # Python weekday(): 0=Monday ... 6=Sunday
            contam_dow = (d.weekday() + 2) % 7
            if contam_dow == 0:
                contam_dow = 7
            day_table.append("{}/{}\t{}\t{}\t0\t{:.2f}".format(
                mo, dy, contam_dow, contam_dow, TGRND))

    # ── Build hourly data (8760 lines) ──
    hourly = []
    for r in rows:
        wth_hour = r['hr'] - 1          # EPW hr 1 -> WTH 00:00
        if wth_hour < 0: wth_hour = 23   # edge case

        ta_k   = r['tdb'] + 273.15
        hr_gkg = _humidity_ratio(r['tdp'], r['patm'])
        ith_kj = r['ghi'] * 3.6         # Wh/m2 -> kJ/m2
        idn_kj = r['dni'] * 3.6
        ts_k   = _sky_temp(r['ir'])
        rn     = 1 if r['precip'] > 0 else 0

        hourly.append(
            "{}/{}\t{:02d}:00:00\t{:.2f}\t{:.0f}\t{:.1f}\t{:.0f}\t"
            "{:.5f}\t{:.1f}\t{:.1f}\t{:.3f}\t{}\t0".format(
                r['mo'], r['dy'], wth_hour,
                ta_k, r['patm'], r['ws'], r['wd'],
                hr_gkg, ith_kj, idn_kj, ts_k, rn))

    # ── Write WTH ──
    with open(wth_path, 'w') as f:
        f.write("WeatherFile ContamW 2.0\n")
        f.write("LOCATION,{},{},{},{},{},{:.2f},{:.2f},{:.1f},{:.1f}\n".format(
            city, state, country, source, wmo, lat, lon, tz, elev))
        f.write("1/1 !start - of - file date\n")
        f.write("12/31 !end - of - file date\n")
        f.write("!Date\tDofW\tDtype\tDST\tTgrnd [K]\n")
        for dl in day_table:
            f.write(dl + "\n")
        f.write("!Date\tTime\tTa[K]\tPb[Pa]\tWs[m/s]\tWd[deg]\t"
                "Hr[g/kg]\tIth[kJ/m^2]\tIdn[kJ/m^2]\tTs[K]\tRn[-]\tSn[-]\n")
        for hl in hourly:
            f.write(hl + "\n")

    return wth_path


# ============================================================================
#  SIM READER (binary format per NIST TN 1887r1 pp. 207-208)
# ============================================================================

@dataclass
class SIMResults:
    """Parsed CONTAM .sim file results."""
    nzone: int = 0; npath: int = 0; nctm: int = 0
    species_names: List[str] = field(default_factory=list)
    zone_names: List[str] = field(default_factory=list)
    timesteps: List[dict] = field(default_factory=list)
    daily_summary: List[dict] = field(default_factory=list)


class SIMReader:
    """Read CONTAM binary .sim files.
    
    SIM format per NIST TN 1887r1:
      Header: 16 x I4 values + cross-ref tables
      Per day: N timestep blocks + 1 daily summary block
      Daily summary has same byte structure as a timestep block but
      contains max/min/avg values.  Its sim_time==86400 duplicates the
      last regular timestep; we detect and tag these as summaries.
    """

    def read(self, filepath, species_names=None, zone_names=None):
        with open(filepath, 'rb') as f:
            self._data = f.read()
        self._pos = 0
        res = SIMResults()

        # Header
        self._ri()  # version
        res.nzone = self._ri(); res.npath = self._ri(); res.nctm = self._ri()
        njct = self._ri(); ndct = self._ri(); time_list = self._ri()
        date_0 = self._ri(); time_0 = self._ri()
        date_1 = self._ri(); time_1 = self._ri()
        pfsave = self._ri(); zfsave = self._ri(); zcsave = self._ri()
        nafnd = self._ri(); nccnd = self._ri(); nafpt = self._ri()

        res.species_names = species_names or [f"Sp{i+1}" for i in range(res.nctm)]
        res.zone_names = zone_names or [f"Zone{i+1}" for i in range(res.nzone)]

        # Cross-ref tables
        for _ in range(nafnd): self._ri(); self._ri()
        for _ in range(nccnd): self._ri(); self._ri()
        for _ in range(nafpt): self._ri(); self._ri()

        # Read timestep + daily summary blocks
        prev_dayofy = -1
        prev_simtime = -1
        while self._pos < len(self._data) - 10:
            try:
                ts = self._read_block(nafpt, res.nzone, res.nctm,
                                      pfsave, zfsave, zcsave)
                if ts:
                    # Detect daily summary: same day + same sim_time as previous
                    # (both the last regular timestep and summary have sim_time=86400)
                    if (ts['dayofy'] == prev_dayofy and
                            ts['sim_time'] == prev_simtime and
                            ts['sim_time'] == 86400):
                        ts['is_summary'] = True
                    else:
                        ts['is_summary'] = False
                    prev_dayofy = ts['dayofy']
                    prev_simtime = ts['sim_time']
                    res.timesteps.append(ts)
            except (struct.error, IndexError):
                break

        return res

    def _read_block(self, nafpt, nzone, nctm, pfsave, zfsave, zcsave):
        ts = {}
        ts['dayofy'] = self._rh(); ts['daytyp'] = self._rh()
        ts['sim_time'] = self._ri()
        ts['Tambt'] = self._rf(); ts['barpres'] = self._rf()
        ts['windspd'] = self._rf(); ts['winddir'] = self._rf()
        ts['amb_cc'] = [self._rf() for _ in range(nctm)]

        ts['paths'] = []
        if pfsave:
            for _ in range(nafpt):
                ts['paths'].append({
                    'nr': self._ri(), 'dP': self._rf(),
                    'Flow0': self._rf(), 'Flow1': self._rf()
                })

        ts['zones'] = []
        if zfsave:
            for _ in range(nzone):
                ts['zones'].append({
                    'nr': self._ri(), 'T': self._rf(),
                    'P': self._rf(), 'rho': self._rf()
                })

        ts['zone_cc'] = []
        if zcsave:
            for _ in range(nzone):
                nr = self._ri()
                cc = [self._rf() for _ in range(nctm)]
                ts['zone_cc'].append({'nr': nr, 'cc': cc})

        return ts

    def _ri(self):
        v = struct.unpack_from('<i', self._data, self._pos)[0]; self._pos += 4; return v
    def _rf(self):
        v = struct.unpack_from('<f', self._data, self._pos)[0]; self._pos += 4; return v
    def _rh(self):
        v = struct.unpack_from('<h', self._data, self._pos)[0]; self._pos += 2; return v


def print_results(sim, hourly=True, summary=True):
    """Pretty-print SIM results with unit conversions."""
    print(f"\n{'='*70}")
    print(f"CONTAM Results: {sim.nzone} zones, {sim.npath} paths, "
          f"{sim.nctm} species ({', '.join(sim.species_names)})")
    print(f"{'='*70}")

    for ts in sim.timesteps:
        h = ts['sim_time'] // 3600
        m = (ts['sim_time'] % 3600) // 60

        if ts.get('is_summary', False):
            continue  # skip daily summary blocks

        if hourly and ts['sim_time'] % 3600 != 0:
            continue

        zinfo = []
        for i, z in enumerate(ts.get('zones', [])):
            name = sim.zone_names[i] if i < len(sim.zone_names) else f"Z{i+1}"
            parts = [f"T={z['T']-273.15:.1f}°C", f"P={z['P']:+.3f}Pa"]

            if i < len(ts.get('zone_cc', [])):
                for j, c in enumerate(ts['zone_cc'][i]['cc']):
                    sp = sim.species_names[j] if j < len(sim.species_names) else f"Sp{j}"
                    if 'CO2' in sp:
                        ppm = c * (28.97 / 44.01) * 1e6
                        parts.append(f"CO2={ppm:.0f}ppm")
                    elif 'PM' in sp:
                        ugm3 = c * 1.2 * 1e9
                        parts.append(f"PM2.5={ugm3:.1f}µg/m³")
                    else:
                        parts.append(f"{sp}={c:.2e}")
            zinfo.append(f"  {name}: {', '.join(parts)}")

        print(f"\nDay {ts['dayofy']} {h:02d}:{m:02d}")
        for line in zinfo:
            print(line)

    if summary and sim.timesteps:
        # Find last non-summary timestep
        non_summary = [ts for ts in sim.timesteps if not ts.get('is_summary', False)]
        last = non_summary[-1] if non_summary else sim.timesteps[-1]
        print(f"\n{'-'*70}")
        print(f"Final state (last timestep, day {last['dayofy']}):")
        for i, z in enumerate(last.get('zones', [])):
            name = sim.zone_names[i] if i < len(sim.zone_names) else f"Z{i+1}"
            if i < len(last.get('zone_cc', [])):
                for j, c in enumerate(last['zone_cc'][i]['cc']):
                    sp = sim.species_names[j] if j < len(sim.species_names) else f"Sp{j}"
                    if 'CO2' in sp:
                        ppm = c * (28.97 / 44.01) * 1e6
                        print(f"  {name} CO2: {ppm:.0f} ppm")

        # Path summary
        print("Path flows:")
        for p in last.get('paths', []):
            F_net = p['Flow0'] + p['Flow1']  # both signed from->to
            F_Ls = abs(F_net) / 1.2 * 1000
            f1_info = f" F1={p['Flow1']:+.5f}" if abs(p['Flow1']) > 1e-12 else ""
            print(f"  Path {p['nr']}: dP={p['dP']:+.3f}Pa, "
                  f"F0={p['Flow0']:+.5f}{f1_info} net={F_net:+.5f}kg/s (~{F_Ls:.1f} L/s)")


def results_to_csv(sim, csv_path):
    """Export SIM results to CSV for surrogate model training."""
    import csv as csvmod
    with open(csv_path, 'w', newline='') as f:
        w = csvmod.writer(f)
        # Header
        header = ['day', 'time_s', 'T_amb_K', 'P_amb_Pa', 'Ws_ms', 'Wd_deg']
        for i, zn in enumerate(sim.zone_names):
            header += [f'{zn}_T_K', f'{zn}_P_Pa', f'{zn}_rho']
            for sp in sim.species_names:
                header.append(f'{zn}_{sp}_kgkg')
        w.writerow(header)
        # Data
        for ts in sim.timesteps:
            if ts.get('is_summary', False):
                continue  # skip daily summary blocks
            row = [ts['dayofy'], ts['sim_time'],
                   ts['Tambt'], ts['barpres'],
                   ts['windspd'], ts['winddir']]
            for i in range(sim.nzone):
                if i < len(ts['zones']):
                    z = ts['zones'][i]
                    row += [z['T'], z['P'], z['rho']]
                if i < len(ts['zone_cc']):
                    row += ts['zone_cc'][i]['cc']
            w.writerow(row)
    return csv_path


# ============================================================================
#  JSON INTERFACE (for GH <-> CPython interop)
# ============================================================================

def build_from_json(spec):
    """Build ContamProject from a JSON spec (produced by GH component).
    
    JSON schema:
    {
      "output_prj": "path/to/output.prj",
      "contamx_path": "C:/Program Files (x86)/NIST/CONTAM 3.4.0.6/contamx3.exe",
      "location": {"lat": 43.04, "lon": -76.14, "timezone": -5, "altitude": 127},
      "simulation": {"days": 1, "start_month": 1, "start_day": 1,
                      "timestep_min": 5, "output_hr": 1},
      "weather": {"mode": "steady_state", "T_C": 0, "wind_speed": 5, "wind_dir": 0}
        OR  {"mode": "wth", "wth_path": "Syracuse.wth"}
        OR  {"mode": "epw", "epw_path": "Syracuse.epw"},
      "species": ["CO2", "PM2.5"],
      "zones": [
        {"name": "Office", "volume": 120.0, "height": 3.0, "T_C": 22.0,
         "level": 1}
      ],
      "connections": [
        {"zone_a": "Office", "zone_b": "Corridor", "element": "door_open",
         "mult": 1.0}
      ],
      "envelopes": [
        {"zone": "Office", "area": 10.0, "azimuth": 0.0,
         "element": "typical_envelope", "relHt": 1.5}
      ],
      "fans": [
        {"zone": "Office", "type": "supply", "flow_Ls": 100}
      ],
      "sources": [
        {"zone": "Office", "species": "CO2", "occupants": 5}
      ]
    }
    """
    b = ModelBuilder()

    # Override ambient CO2 if specified in spec
    ambient_ppm = spec.get('ambient_co2_ppm', 415.0)
    if ambient_ppm is not None:
        b._species["CO2"] = make_CO2(ambient_ppm=float(ambient_ppm))
        print(f"  Ambient CO2: {ambient_ppm} ppm")

    # --- Parse occupancy data ---
    # Priority: contam_occupancy (Hub wireless) > program_data (HB JSON) > manual occupants
    # If spec already has pre-parsed 'schedules', use those (backward compat).
    parsed_schedules = {}
    parsed_sources = []
    if spec.get('contam_occupancy') and not spec.get('schedules'):
        # Lightweight wireless format from Hub (sc.sticky["GDS_CONTAM_OCC"])
        occ = spec['contam_occupancy']
        zones_for_parse = spec.get('zones', [])
        parsed_schedules, parsed_sources, parse_diag = _parse_contam_occupancy(
            occ, zones_for_parse)
        if parsed_sources:
            spec['schedules'] = parsed_schedules
            spec['sources'] = parsed_sources
            print(f"  Parsed contam_occupancy: {parse_diag['matched']} rooms, "
                  f"{len(parsed_schedules)} schedules"
                  f" (name:{parse_diag.get('name_matched',0)}"
                  f" idx:{parse_diag.get('index_matched',0)})")
            if parse_diag.get('skipped'):
                print(f"  Skipped: {parse_diag['skipped']} rooms (not in occupancy data)")
        else:
            print("  contam_occupancy yielded no sources")
    elif spec.get('program_data') and not spec.get('schedules'):
        prog_data = spec['program_data']
        zones_for_parse = spec.get('zones', [])
        parsed_schedules, parsed_sources, parse_diag = _parse_program_data(
            prog_data, zones_for_parse)
        if parsed_sources:
            spec['schedules'] = parsed_schedules
            spec['sources'] = parsed_sources
            print(f"  Parsed program_data: {len(parsed_sources)} sources, "
                  f"{len(parsed_schedules)} schedules")
            if parse_diag.get('skipped'):
                print(f"  Skipped: {parse_diag['skipped']} rooms (bad program_data)")
        else:
            if spec.get('occupants'):
                spec['sources'] = spec['occupants']
                print(f"  program_data yielded no sources; using {len(spec['occupants'])} manual occupants")
    elif not spec.get('schedules') and spec.get('occupants'):
        spec['sources'] = spec['occupants']

    # Inline schedules (pre-parsed or just-parsed from program_data)
    for sch_name, sch_data in spec.get('schedules', {}).items():
        b.add_schedule(
            sch_name,
            weekday=sch_data.get('weekday', [["00:00", 1.0], ["24:00", 1.0]]),
            weekend=sch_data.get('weekend'),
            shape=sch_data.get('shape', 'step'))
    if spec.get('schedules'):
        print(f"  Schedules loaded: {', '.join(spec['schedules'].keys())}")

    # Location
    loc = spec.get('location', {})
    b.set_location(loc.get('lat') or 43.04, loc.get('lon') or -76.14,
                   loc.get('timezone') or -5, loc.get('altitude') or 0)

    # Simulation period: support start_date/end_date or legacy days
    sim = spec.get('simulation', {})
    start_date = sim.get('start_date', [1, 1])
    end_date = sim.get('end_date')
    if end_date:
        sim_days = _days_between(start_date, end_date)
    else:
        sim_days = sim.get('days') or 1

    b.set_simulation(days=sim_days,
                     start_month=start_date[0],
                     start_day=start_date[1],
                     timestep_min=sim.get('timestep_min') or 5,
                     output_hr=sim.get('output_hr') or 1,
                     sim_af=sim.get('sim_af'),
                     sim_mf=sim.get('sim_mf'))
    print(f"  Simulation: {start_date[0]}/{start_date[1]} for {sim_days} days")

    # Weather: wth (user-provided) > epw (needs conversion) > steady_state
    wx = spec.get('weather', {})
    if wx.get('mode') == 'wth' and wx.get('wth_path'):
        # User provided a pre-converted WTH file — use directly
        b._wth_path = wx['wth_path']
    elif wx.get('mode') == 'epw' and wx.get('epw_path'):
        b.set_weather_epw(wx['epw_path'])
    else:
        b.set_weather_ss(T_C=wx.get('T_C') if wx.get('T_C') is not None else 20,
                         wind_speed=wx.get('wind_speed') if wx.get('wind_speed') is not None else 0,
                         wind_dir=wx.get('wind_dir') if wx.get('wind_dir') is not None else 0)

    # Zones
    for zd in spec.get('zones', []):
        b.add_zone(zd['name'], zd.get('volume') or 100,
                   height=zd.get('height') or 3.0,
                   T_C=zd.get('T_C') if zd.get('T_C') is not None else 20)

    # Connections
    for cd in spec.get('connections', []):
        b.connect_zones(cd['zone_a'], cd['zone_b'],
                        element=cd.get('element', 'door_open'),
                        mult=cd.get('mult', 1.0))

    # Envelopes
    for ed in spec.get('envelopes', []):
        b.add_envelope(ed['zone'], area=ed.get('area', 1.0),
                       azimuth=ed.get('azimuth', 0),
                       element=ed.get('element', 'typical_envelope'),
                       relHt=ed.get('relHt', 1.5))

    # Openings (from GDS_CONTAM_OPENINGS interpreter — dtype+params resolved)
    for od in spec.get('openings', []):
        b.add_opening(
            dtype=od.get('dtype', 'plr_test1'),
            params=od.get('params', {}),
            zone_a=od.get('zone_a'),
            zone_b=od.get('zone_b'),
            relHt=od.get('relHt', 0.0),
            mult=od.get('mult', 1.0),
            wazm=od.get('wazm', 0.0),
            wind_pressure=od.get('wind_pressure', False),
            desc=od.get('desc', ''))

    # Fans
    for fd in spec.get('fans', []):
        if fd.get('type') == 'exhaust':
            b.add_exhaust_fan(fd['zone'], flow_Ls=fd.get('flow_Ls', 50))
        else:
            b.add_supply_fan(fd['zone'], flow_Ls=fd.get('flow_Ls', 100))

    # Sources (with per-source schedule support)
    for sd in spec.get('sources', []):
        sch = sd.get('schedule', None)
        if sd.get('species', 'CO2') == 'PM2.5':
            b.add_pm25_source(sd['zone'], rate_kgs=sd.get('rate_kgs', 1e-9),
                              mult=sd.get('mult', 1.0), schedule=sch)
        else:
            b.add_co2_source(sd['zone'], occupants=sd.get('occupants', 1),
                             schedule=sch)

    proj = b.build()
    out_prj = spec.get('output_prj', 'gds_model.prj')
    return proj, out_prj


def export_summary_json(sim, json_path, proj=None):
    """Export key results as JSON for GH to read back.
    
    When proj is provided, also exports a path manifest with zone names,
    element types, and average flow data from the SIM.
    """
    import json as jsonmod
    summary = {
        'nzone': sim.nzone, 'npath': sim.npath, 'nctm': sim.nctm,
        'species': sim.species_names, 'zones': sim.zone_names,
        'hourly': []
    }

    # ---- Path manifest: merge PRJ metadata with SIM flow averages ----
    if proj and hasattr(proj, 'paths') and proj.paths:
        # Build zone name lookup (1-based index -> name, -1 = ambient)
        def _zone_name(idx):
            if idx <= 0:
                return "Ambient"
            if idx <= len(proj.zones):
                return proj.zones[idx - 1].name
            return f"Z{idx}"

        # Build element name lookup (1-based pe -> name)
        def _elem_name(pe):
            if 1 <= pe <= len(proj.airflow_elements):
                return proj.airflow_elements[pe - 1].name
            return f"Elem{pe}"

        def _elem_dtype(pe):
            if 1 <= pe <= len(proj.airflow_elements):
                return proj.airflow_elements[pe - 1].dtype
            return "unknown"

        def _elem_desc(pe):
            if 1 <= pe <= len(proj.airflow_elements):
                return proj.airflow_elements[pe - 1].desc
            return ""

        # Accumulate average flows from SIM timesteps
        # path_flows[i] = {'dP_sum': ..., 'F0_sum': ..., 'F1_sum': ..., 'n': ...}
        path_flows = {}
        for ts in sim.timesteps:
            if ts.get('is_summary', False):
                continue
            for pf in ts.get('paths', []):
                nr = pf['nr']
                if nr not in path_flows:
                    path_flows[nr] = {'dP_sum': 0.0, 'F0_sum': 0.0, 'F1_sum': 0.0, 'n': 0}
                path_flows[nr]['dP_sum'] += pf['dP']
                path_flows[nr]['F0_sum'] += pf['Flow0']
                path_flows[nr]['F1_sum'] += pf['Flow1']
                path_flows[nr]['n'] += 1

        # Get path-level descs (from openings pipeline, if available)
        path_descs = getattr(proj, '_path_descs', [])

        path_manifest = []
        for pi, pa in enumerate(proj.paths):
            nr = pi + 1  # 1-based
            # Prefer path-level desc (e.g. "door_ext_open_Room15"),
            # fall back to element desc (e.g. "leak_dP50_F0.0025")
            pdesc = path_descs[pi] if pi < len(path_descs) else ''
            if not pdesc:
                pdesc = _elem_desc(pa.pe)
            entry = {
                'nr': nr,
                'from': _zone_name(pa.pzn),
                'to': _zone_name(pa.pzm),
                'element': _elem_name(pa.pe),
                'dtype': _elem_dtype(pa.pe),
                'desc': pdesc,
                'mult': pa.mult,
                'wazm': pa.wazm,
                'relHt': pa.relHt,
                'wind': pa.pw > 0,
            }
            # Merge average flows if available
            pf = path_flows.get(nr)
            if pf and pf['n'] > 0:
                n = pf['n']
                avg_F0 = pf['F0_sum'] / n
                avg_F1 = pf['F1_sum'] / n
                avg_net = avg_F0 + avg_F1  # both signed from->to
                entry['avg_dP'] = round(pf['dP_sum'] / n, 4)
                entry['avg_flow_kg_s'] = round(avg_net, 8)
                entry['avg_flow_L_s'] = round(avg_net / 1.2 * 1000, 3)
            path_manifest.append(entry)

        summary['paths'] = path_manifest

    for ts in sim.timesteps:
        if ts.get('is_summary', False):
            continue  # skip daily summary blocks
        if ts['sim_time'] % 3600 != 0:
            continue
        entry = {
            'day': ts['dayofy'],
            'hour': ts['sim_time'] // 3600,
            'T_amb_C': ts['Tambt'] - 273.15,
            'wind_ms': ts['windspd'],
            'zone_data': {}
        }
        for i in range(sim.nzone):
            zname = sim.zone_names[i] if i < len(sim.zone_names) else f"Z{i+1}"
            zd = {}
            if i < len(ts.get('zones', [])):
                zd['T_C'] = ts['zones'][i]['T'] - 273.15
                zd['P_Pa'] = ts['zones'][i]['P']
            if i < len(ts.get('zone_cc', [])):
                for j, c in enumerate(ts['zone_cc'][i]['cc']):
                    sp = sim.species_names[j] if j < len(sim.species_names) else f"Sp{j}"
                    if 'CO2' in sp:
                        zd['CO2_ppm'] = round(c * (28.97/44.01) * 1e6, 1)
                    elif 'PM' in sp:
                        zd['PM25_ugm3'] = round(c * 1.2 * 1e9, 2)
                    else:
                        zd[sp + '_kgkg'] = c
            entry['zone_data'][zname] = zd
        summary['hourly'].append(entry)

    with open(json_path, 'w') as f:
        jsonmod.dump(summary, f, indent=2)
    return json_path


# ============================================================================
#  DEMO
# ============================================================================

def create_demo_model():
    """Demo using low-level API (backward compatible)."""
    p = ContamProject(description="GDS_Demo_TwoZone")
    p.latd = 43.04; p.lgtd = -76.14; p.Tznr = -5.0; p.altd = 127
    p.ss_Tambt = 273.15; p.ss_windspd = 5.0; p.ss_winddir = 0.0
    p.species = [make_CO2(), make_PM25()]
    p.levels = [Level(name="Floor1", refht=0.0, delht=3.0)]
    p.wind_profiles = [make_default_wind_profile()]
    p.airflow_elements = [
        make_test1_leak("EnvCrack", dP=4.0, flow=0.01, expt=0.65,
                        desc="Envelope_infiltration"),
        make_door("IntDoor", ht=2.1, wd=0.9, desc="Interior_door"),
    ]
    p.zones = [
        Zone(name="Office", Vol=120.0, T0=295.15, pl=1, relHt=1.5),
        Zone(name="Corridor", Vol=60.0, T0=293.15, pl=1, relHt=1.5),
    ]
    p.paths = [
        AirflowPath(pzn=-1, pzm=1, pe=1, pw=1, pld=1, relHt=1.5,
                     mult=10.0, wazm=0.0),
        AirflowPath(pzn=1, pzm=2, pe=2, pld=1, relHt=0.0),
        AirflowPath(pzn=2, pzm=-1, pe=1, pw=1, pld=1, relHt=1.5,
                     mult=5.0, wazm=180.0),
    ]
    p.source_elements = [make_constant_source("OccCO2", "CO2", 4.8e-6,
                                               "CO2_from_occupant")]
    p.source_sinks = [SourceSink(pz=1, pe=1, mult=5.0)]
    return p


def create_demo_builder():
    """Demo using high-level ModelBuilder API."""
    b = ModelBuilder()
    b.set_location(43.04, -76.14, timezone=-5, altitude=127)
    b.set_simulation(days=1)
    b.set_weather_ss(T_C=0, wind_speed=5.0, wind_dir=0)

    b.add_zone("Office", volume=120, height=3.0, T_C=22)
    b.add_zone("Corridor", volume=60, height=3.0, T_C=20)

    b.add_envelope("Office", area=10.0, azimuth=0,
                   element="typical_envelope")
    b.connect_zones("Office", "Corridor", "door_open")
    b.add_envelope("Corridor", area=5.0, azimuth=180,
                   element="typical_envelope")

    b.add_co2_source("Office", occupants=5)
    return b.build()


# ============================================================================
#  SCHEDULE INSPECTOR (diagnostic output for GH/debugging)
# ============================================================================

def inspect_schedules(spec, output_path=None):
    """Write a human-readable text file showing parsed schedule details.
    
    Covers:
      - Detected schedules (weekday/weekend 24-hour values)
      - Source assignments (zone -> schedule -> occupant count)
      - Seasonal segments (if any)
      - Simulation period
    
    Args:
        spec: the JSON spec dict (from gds_spec.json)
        output_path: path for .txt output (default: alongside spec's output_prj)
    
    Returns:
        str: path to the written inspection file
    """
    if not output_path:
        out_prj = spec.get('output_prj', 'gds_model.prj')
        output_path = out_prj.replace('.prj', '_schedule_inspect.txt')
    
    zones = spec.get('zones', [])
    prog_data = spec.get('program_data', [])
    
    lines = []
    W = lines.append
    
    W("=" * 72)
    W("GDS-CONTAM SCHEDULE INSPECTION REPORT")
    W("=" * 72)
    
    # Simulation period
    sim = spec.get('simulation', {})
    sd = sim.get('start_date', [1, 1])
    ed = sim.get('end_date')
    days = sim.get('days', '?')
    W(f"\nSimulation: {sd[0]}/{sd[1]}", )
    if ed:
        W(f"  End: {ed[0]}/{ed[1]}")
    else:
        W(f"  Days: {days}")
    W(f"  Timestep: {sim.get('timestep_min', 5)} min")
    W(f"  Output: every {sim.get('output_hr', 1)} hr")
    W(f"  Solver: sim_af={sim.get('sim_af', '?')}, sim_mf={sim.get('sim_mf', '?')}")
    
    # Species
    W(f"\nSpecies: {spec.get('species', ['CO2'])}")
    W(f"Ambient CO2: {spec.get('ambient_co2_ppm', 415)} ppm")
    
    # Zones summary
    W(f"\n{'=' * 72}")
    W(f"ZONES ({len(zones)})")
    W(f"{'=' * 72}")
    W(f"{'Zone':<15} {'Vol(m3)':>8} {'Ht(m)':>6} {'T(C)':>5} {'Level':>5}")
    W("-" * 50)
    for z in zones:
        W(f"{z['name']:<15} {z.get('volume', 0):>8.1f} {z.get('height', 0):>6.2f} "
          f"{z.get('T_C', 20):>5.1f} {z.get('level', 1):>5}")
    
    # Parse schedules from program_data
    W(f"\n{'=' * 72}")
    W(f"SCHEDULE PARSING (from program_data)")
    W(f"{'=' * 72}")
    
    if not prog_data:
        W("  No program_data provided.")
    else:
        # Standard (non-seasonal) parse
        schedules, sources, diag = _parse_program_data(prog_data, zones)
        
        W(f"\nParsed: {len(schedules)} unique schedules, "
          f"{len(sources)} sources, {diag['skipped']} skipped rooms")
        
        # Show each schedule's 24-hour values
        for sch_name, sch_data in schedules.items():
            W(f"\n  Schedule: {sch_name}")
            wd_pts = sch_data.get('weekday', [])
            we_pts = sch_data.get('weekend', [])
            
            # Reconstruct 24-hour array from change-points for display
            wd_24 = _points_to_hourly(wd_pts)
            we_24 = _points_to_hourly(we_pts)
            
            W(f"    Hour:    " + " ".join(f"{h:>5}" for h in range(24)))
            W(f"    Weekday: " + " ".join(f"{v:>5.2f}" for v in wd_24))
            W(f"    Weekend: " + " ".join(f"{v:>5.2f}" for v in we_24))
        
        # Source assignments
        W(f"\n  {'Zone':<15} {'Occupants':>9} {'Peak Frac':>9} {'Schedule':<30}")
        W("  " + "-" * 65)
        for ro in diag.get('room_occ', []):
            zname, occ, peak = ro
            # Find matching source's schedule name
            sch = next((s['schedule'] for s in sources if s['zone'] == zname), '?')
            W(f"  {zname:<15} {occ:>9} {peak:>9.3f} {sch:<30}")
        
        # Seasonal detection
        W(f"\n{'=' * 72}")
        W(f"SEASONAL ANALYSIS")
        W(f"{'=' * 72}")
        
        seasonal_segs = _detect_seasonal_segments(prog_data, zones)
        if not seasonal_segs:
            W("  No seasonal variation detected (single date range across all rooms).")
            W("  All schedules apply uniformly for the entire simulation period.")
        else:
            W(f"  {len(seasonal_segs)} seasonal segments detected:")
            for si, seg in enumerate(seasonal_segs):
                W(f"\n  --- Segment {si+1}: {seg['label']} ---")
                W(f"  Date range: {seg['start_date'][0]}/{seg['start_date'][1]}"
                  f" -> {seg['end_date'][0]}/{seg['end_date'][1]}")
                W(f"  Schedules: {len(seg['schedules'])}, Sources: {len(seg['sources'])}")
                for sn, sd in seg['schedules'].items():
                    wd_24 = _points_to_hourly(sd.get('weekday', []))
                    we_24 = _points_to_hourly(sd.get('weekend', []))
                    W(f"    {sn}:")
                    W(f"      WD: " + " ".join(f"{v:.2f}" for v in wd_24))
                    W(f"      WE: " + " ".join(f"{v:.2f}" for v in we_24))
    
    # Openings summary
    openings = spec.get('openings', [])
    W(f"\n{'=' * 72}")
    W(f"OPENINGS SUMMARY ({len(openings)} total)")
    W(f"{'=' * 72}")
    # Count by type
    types = {}
    for o in openings:
        key = o.get('dtype', 'unknown')
        if o.get('zone_a') is None:
            key += " (envelope)"
        else:
            key += " (interior)"
        types[key] = types.get(key, 0) + 1
    for k, v in sorted(types.items()):
        W(f"  {k}: {v}")
    
    W(f"\n{'=' * 72}")
    W(f"END OF INSPECTION REPORT")
    W(f"{'=' * 72}")
    
    text = "\n".join(lines)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return output_path


def _points_to_hourly(points):
    """Convert CONTAM [['HH:MM', value], ...] change-points back to 24-hour array."""
    hourly = [0.0] * 24
    if not points:
        return hourly
    
    current_val = 0.0
    pt_idx = 0
    for h in range(24):
        t_sec = h * 3600
        while pt_idx < len(points):
            pt = points[pt_idx]
            # Parse time
            parts = str(pt[0]).split(':')
            pt_sec = int(parts[0]) * 3600
            if len(parts) > 1:
                pt_sec += int(parts[1]) * 60
            if pt_sec <= t_sec:
                current_val = float(pt[1])
                pt_idx += 1
            else:
                break
        hourly[h] = current_val
    return hourly


if __name__ == "__main__":
    import sys
    # Windows console often uses cp1252 which can't handle unicode chars.
    # Reconfigure stdout to replace unrepresentable chars instead of crashing.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"

    if mode == "demo":
        proj = create_demo_model()
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "gds_demo.prj")
        PRJWriter().write(proj, out)
        print(f"Written: {out}")

    elif mode == "builder_demo":
        proj = create_demo_builder()
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "gds_builder_demo.prj")
        PRJWriter().write(proj, out)
        print(f"Written: {out}")
        print(f"Zones: {len(proj.zones)}, Paths: {len(proj.paths)}")

    elif mode == "read_sim":
        sim_path = sys.argv[2] if len(sys.argv) > 2 else "gds_demo.sim"
        sp = sys.argv[3].split(",") if len(sys.argv) > 3 else ["CO2", "PM2.5"]
        zn = sys.argv[4].split(",") if len(sys.argv) > 4 else []
        res = SIMReader().read(sim_path, sp, zn or None)
        print_results(res)

    elif mode == "sim_to_csv":
        sim_path = sys.argv[2] if len(sys.argv) > 2 else "gds_demo.sim"
        csv_path = sys.argv[3] if len(sys.argv) > 3 else "results.csv"
        sp = sys.argv[4].split(",") if len(sys.argv) > 4 else ["CO2", "PM2.5"]
        res = SIMReader().read(sim_path, sp)
        results_to_csv(res, csv_path)
        print(f"Exported {len(res.timesteps)} timesteps to {csv_path}")

    elif mode == "from_json":
        # GH interop: read model definition from JSON, build PRJ, optionally run
        json_path = sys.argv[2]
        import json as jsonmod
        import copy
        with open(json_path, 'r') as f:
            spec = jsonmod.load(f)

        # Auto-generate schedule inspection report
        try:
            inspect_out = json_path.replace('.json', '_schedule_inspect.txt')
            inspect_path = inspect_schedules(spec, inspect_out)
            print(f"INSPECT: {inspect_path}")
        except Exception as e:
            print(f"  (inspect warning: {e})")

        # --- Detect seasonal schedules ---
        seasonal_segs = []
        if spec.get('contam_occupancy'):
            seasonal_segs = _detect_seasonal_segments_from_occ(
                spec['contam_occupancy'], spec.get('zones', []))
            if seasonal_segs:
                print(f"  Seasonal segments (from contam_occupancy): {len(seasonal_segs)}")
        if not seasonal_segs and spec.get('program_data'):
            seasonal_segs = _detect_seasonal_segments(
                spec['program_data'], spec.get('zones', []))
        
        contamx = spec.get('contamx_path', '')
        out_prj = spec.get('output_prj', 'gds_model.prj')

        if seasonal_segs and len(seasonal_segs) > 1:
            # ===== SEASONAL MULTI-RUN PIPELINE =====
            sim_cfg = spec.get('simulation', {})
            sim_start = sim_cfg.get('start_date', [1, 1])
            sim_end = sim_cfg.get('end_date')
            if not sim_end:
                sim_days = sim_cfg.get('days', 1)
                end_doy = _md_to_doy(sim_start) + sim_days - 1
                if end_doy > 365:
                    end_doy -= 365
                sim_end = _doy_to_md(end_doy)

            runs = _partition_sim_period(sim_start, sim_end, seasonal_segs)
            print(f"SEASONAL MODE: {len(runs)} segments from "
                  f"{sim_start[0]}/{sim_start[1]} to {sim_end[0]}/{sim_end[1]}")
            for r in runs:
                print(f"  {r['label']}: {r['start_date'][0]}/{r['start_date'][1]}"
                      f" -> {r['end_date'][0]}/{r['end_date'][1]} ({r['days']}d)")

            segment_results = []  # list of (seg_meta, sim_result, proj)
            prev_cc0 = None
            first_proj = None
            first_path_manifest = None

            for ri, run in enumerate(runs):
                seg_label = run['label']
                print(f"\n--- Segment {ri+1}/{len(runs)}: {seg_label} ---")

                # Create modified spec for this segment
                seg_spec = copy.deepcopy(spec)
                seg_spec['schedules'] = run['schedules']
                seg_spec['sources'] = run['sources']
                # Override simulation dates
                seg_spec['simulation']['start_date'] = run['start_date']
                seg_spec['simulation']['end_date'] = run['end_date']
                seg_spec['simulation']['days'] = run['days']
                # Solver mode: transient for multi-day, cyclic for 1 day
                seg_spec['simulation']['sim_mf'] = 2 if run['days'] > 1 else 3
                # Prevent re-parsing program_data (we already have schedules)
                seg_spec.pop('program_data', None)
                # Segment-specific PRJ filename
                seg_prj = out_prj.replace('.prj', f'_seg{ri+1}.prj')
                seg_spec['output_prj'] = seg_prj

                proj, _ = build_from_json(seg_spec)

                # Apply cc0 from previous segment for continuous concentration
                if prev_cc0:
                    for zi, z in enumerate(proj.zones):
                        if zi < len(prev_cc0):
                            z.cc0 = prev_cc0[zi]
                    print(f"  cc0 carried from previous segment")

                PRJWriter().write(proj, seg_prj)
                print(f"  PRJ: {seg_prj}")

                if first_proj is None:
                    first_proj = proj

                # Run ContamX
                if contamx and os.path.exists(contamx):
                    import subprocess as sp_mod
                    r = sp_mod.run([contamx, os.path.abspath(seg_prj)],
                                   capture_output=True, text=True, timeout=600)
                    seg_sim = seg_prj.replace('.prj', '.sim')
                    if os.path.exists(seg_sim):
                        sp_names = [s.name for s in proj.species]
                        zn_names = [z.name for z in proj.zones]
                        res = SIMReader().read(seg_sim, sp_names, zn_names)
                        print(f"  SIM: {len(res.timesteps)} timesteps")

                        # Extract final cc for next segment's cc0
                        prev_cc0 = _extract_final_cc(res)

                        # Build path manifest from first segment only
                        if first_path_manifest is None:
                            first_path_manifest = _build_path_manifest(res, proj)

                        segment_results.append((run, res, proj))
                    else:
                        print(f"  ERROR: ContamX failed for {seg_label}. Check .xlog")
                        print(r.stdout)
                        print(r.stderr)
                else:
                    print(f"  WARNING: contamx not available, PRJ written only")

            # Stitch results
            if segment_results:
                sp_names = [s.name for s in first_proj.species]
                zn_names = [z.name for z in first_proj.zones]
                npath = len(first_proj.paths)
                stitched = _stitch_summary_jsons(
                    segment_results, zn_names, sp_names, npath,
                    path_manifest=first_path_manifest)
                summary_path = out_prj.replace('.prj', '_summary.json')
                with open(summary_path, 'w') as f:
                    jsonmod.dump(stitched, f, indent=2)
                print(f"\nJSON: {summary_path}")
                print(f"Stitched: {len(stitched['hourly'])} hours across "
                      f"{len(stitched['seasonal_segments'])} segments")

                # Also write combined CSV
                csv_path = out_prj.replace('.prj', '_results.csv')
                _stitch_csv(segment_results, csv_path, sp_names, zn_names)
                print(f"CSV: {csv_path}")

        else:
            # ===== SINGLE RUN (no seasonal variation) =====
            proj, out_prj = build_from_json(spec)
            PRJWriter().write(proj, out_prj)
            print(f"PRJ: {out_prj}")

            # Auto-run if contamx path provided
            if contamx and os.path.exists(contamx):
                import subprocess as sp
                r = sp.run([contamx, os.path.abspath(out_prj)],
                           capture_output=True, text=True, timeout=600)
                sim_path = out_prj.replace('.prj', '.sim')
                if os.path.exists(sim_path):
                    sp_names = [s.name for s in proj.species]
                    zn_names = [z.name for z in proj.zones]
                    res = SIMReader().read(sim_path, sp_names, zn_names)
                    csv_path = out_prj.replace('.prj', '_results.csv')
                    results_to_csv(res, csv_path)
                    print(f"SIM: {sim_path}")
                    print(f"CSV: {csv_path}")
                    # Also write summary JSON for GH to read back
                    summary = export_summary_json(res,
                        out_prj.replace('.prj', '_summary.json'),
                        proj=proj)
                    print(f"JSON: {summary}")
                else:
                    print(f"ERROR: ContamX failed. Check .xlog")
                    print(r.stdout)
                    print(r.stderr)

    elif mode == "epw_to_wth":
        epw_path = sys.argv[2]
        wth_path = sys.argv[3] if len(sys.argv) > 3 else None
        out = epw_to_wth(epw_path, wth_path or epw_path.replace('.epw', '.wth'))
        print(f"Written: {out}")

    elif mode == "inspect":
        # Inspect schedules from a gds_spec.json without running simulation
        json_path = sys.argv[2]
        import json as jsonmod
        with open(json_path, 'r') as f:
            spec = jsonmod.load(f)
        out_txt = sys.argv[3] if len(sys.argv) > 3 else \
            json_path.replace('.json', '_schedule_inspect.txt')
        result = inspect_schedules(spec, out_txt)
        # Also print to stdout
        with open(result, 'r', encoding='utf-8') as f:
            print(f.read())
        print(f"\nWritten: {result}")

    else:
        print("Usage:")
        print("  python gds_contam.py demo              # low-level PRJ demo")
        print("  python gds_contam.py builder_demo      # ModelBuilder demo")
        print("  python gds_contam.py from_json SPEC.json  # GH interop: JSON->PRJ->run->results")
        print("  python gds_contam.py inspect SPEC.json [OUT.txt]  # schedule inspection")
        print("  python gds_contam.py read_sim FILE.sim [species] [zones]")
        print("  python gds_contam.py sim_to_csv FILE.sim OUT.csv [species]")
        print("  python gds_contam.py epw_to_wth FILE.epw [OUT.wth]")
