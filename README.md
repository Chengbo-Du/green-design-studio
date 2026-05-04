# Green Design Studio (GDS)

GDS is a modular, cross-domain simulation platform that unifies building
performance simulation engines under a single architectural workflow, 
lowering the engineering barrier for designers while preserving the 
validity of the underlying physics.

This Phase 1 release includes the platform, a calibrated case study, and
all source code used in the accompanying paper:

## What this repository contains

A single Grasshopper canvas (`GDS_General.gh`) that drives the entire
simulation workflow, plus a working example of a calibrated 1972 dormitory
at Syracuse University (DOE-ABC building).

When you open the canvas in Grasshopper, it already includes its
internal components from the `components/` folder and runs the pre-configured
example in the `case-study/` folder. Results write back to the case-study
folder and an HTML dashboard opens in your browser.

## Requirements

You will need the following installed on your computer before using GDS:

- **Rhinoceros 8** with Grasshopper
- **EnergyPlus 22.2+**
- **CONTAM 3.4+** (NIST)
- **Python 3.9+**

Plugins for Rhino:
- **Ladybug Tools 1.8+** (Honeybee, Ladybug, Dragonfly)
- **eleFront** 
- **Heron**
- **Metahopper** 

## Quick start: running the example

1. **Download this repository.**
   - Click the green **Code** button on the GitHub page
   - Choose **Download ZIP**
   - Unzip the folder somewhere on your computer

2. **Open the canvas.**
   - Launch Rhino, then open Grasshopper
   - In Grasshopper, go to File → Open and select `GDS_General.gh`
   - The canvas loads with the example pre-configured
   - Make sure the paths on the .gh canvas are correctly configured to your
     local files. Paths to modify:
     1) Weather path (on main canvas, 'panel' component)
     2) Site context (on main canvas, 'panel' component)
     3) GDS Database Path (on main canvas, 'panel' component)
     4) Four paths inside GDS_CONTAM cluster: local 'contamX3.exe', 'py.exe';
        'gds_contam_v3.py', 'gds_contam_viewer.py'.

3. **Run the simulation.**
   - The canvas runs automatically when opened
   - Two simulations execute in sequence: EnergyPlus (energy + thermal)
     and CONTAM (multi-zone airflow + CO₂)
   - This takes roughly 3 minutes on a typical laptop

4. **View the results.**
   - An HTML dashboard opens automatically in your default browser
   - Numerical outputs are written

## Folder overview

This is what each folder contains, in plain terms:

- **`GDS_General.gh`** — The Grasshopper canvas. This is platform with 
  all components wired. Everything else is loaded by the canvas behind the scenes.

- **`tools/`** — Two Python scripts (CONTAM pipeline) the canvas calls 
  internally to write CONTAM input files and to generate the results dashboard. 
  You do not run these directly.

- **`case-study/`** — A complete pre-configured example of a calibrated
  Syracuse University dormitory. Contains the EnergyPlus model (`.idf`),
  the CONTAM project file (`.prj`), the weather file (`.epw`), and the
  occupancy schedules(`.json`). The canvas reads from this folder by default.

- **`components/`** — The Grasshopper components that the canvas uses
  internally (compiled `.ghpy` files). You do not need to edit these to run the example.

- **`docs/`** — Background documentation: an overview of the platform's
  architecture, detailed installation instructions, and the figures used
  in the paper.

## Adapting GDS to your own building

The example uses Syracuse's DOE-ABC dormitory, but the platform is general.
To run a different building, replace the files in `case-study/` with your
own model (`.idf`, `.prj`, weather file, schedules) and re-run the canvas.
See `docs/architecture.md` for the input naming conventions the canvas
expects.

## Reproducing the manuscript results

The version of the code released here corresponds to GDS phase 1 in the manuscript. 
Running the canvas as shipped (without modifications) reproduces the calibration 
result reported in the paper: CV(RMSE) = 9.2%, NMBE = 3.5%.

## Citation

If you use GDS in your research, please cite both the paper and the
software release:

> Du, C., et al. 
> [Green Design Studio: A Modular Integration Layer for Cross-Domain Building Performance Simulation].
> DOI: [to be added]
>
> Du, C. Green Design Studio (GDS), SyracuseCoE, Syracuse University.
> https://github.com/Chengbo-Du/gds

A `CITATION.cff` file in this repository provides machine-readable
citation metadata.

## License

GDS is released under the BSD 3-Clause License.
Copyright (c) 2026 SyracuseCoE, Syracuse University. All rights reserved.

See `LICENSE` for the full license text.

## Questions and feedback

For questions about GDS or to report issues, please [open an issue on
GitHub](https://github.com/Chengbo-Du/gds/issues) or contact:
> Dr. Chengbo Du — cdu113@syr.edu
> Dr. Jianshun Zhang — jszhang@syr.edu