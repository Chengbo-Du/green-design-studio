# GDS Installation Guide

Follow each step in order before opening the canvas.

---

## Requirements

| Software | Version | Notes |
|---|---|---|
| Rhinoceros 8 | 8.x | Required license |
| Ladybug Tools | 1.9+ | Installs EnergyPlus and OpenStudio automatically |
| EnergyPlus | 24.2+ | Installed by Ladybug |
| OpenStudio | 3.9+ | Installed by Ladybug |
| CONTAM | 3.4+ | Installed by GDS installer |
| Heron | latest | Via Rhino Package Manager |
| eleFront | latest | Via Rhino Package Manager |
| MetaHopper | latest | Via Rhino Package Manager |

---

## Step 1 — Download GDS

1. Go to [github.com/Chengbo-Du/green-design-studio](https://github.com/Chengbo-Du/green-design-studio)
2. Click **Code → Download ZIP**
3. Right-click the ZIP → **Extract All**
4. Move the extracted folder somewhere easy to find

---

## Step 2 — Install Ladybug Tools 1.9

1. Go to [food4rhino.com](https://www.food4rhino.com) and create a free account
2. Search for **Ladybug Tools** and download version **1.9**
3. Open Rhino → open Grasshopper → **File → Open** → select `installer.gh`
4. Flip the first toggle to **True** and wait for installation to complete
5. Flip the second toggle to **True** to finish
6. Close and reopen Rhino

---

## Step 3 — Install Grasshopper Plugins

1. Open Rhino → **Tools → Package Manager**
2. Search for and install:
   - **Heron**
   - **eleFront**
   - **MetaHopper**
3. Close and reopen Rhino
4. Confirm by opening Grasshopper — you should see tabs for Ladybug, Honeybee, Dragonfly, Heron, eleFront, MetaHopper

---

## Step 4 — Run the GDS Installer

1. Open the GDS folder from Step 1
2. Double-click **install.exe**
3. Click **Yes** on the admin permission prompt
4. Wait for all steps to complete — you should see:

```
[OK]   All checks passed
[OK]   Open GDS_General.gh in Grasshopper to run simulations
```

5. Press **Enter** to close

> If Windows blocks install.exe run install.bat instead

---

## Step 5 — Open the Canvas

1. Open Rhino → open Grasshopper
2. **File → Open** → select `GDS_General.gh`
3. Press **Ctrl+S** to save the canvas before doing anything else
4. The status panel should show:

```
Source: config.json
All checks passed - ready to run!
```

---

## Step 6 — Run a Simulation

1. Find the **RUN_SOLVER** toggle on the canvas — it shows `False`
2. Double-click it to flip to `True`
3. Wait approximately 3 minutes
4. An HTML dashboard opens automatically in your browser when done


