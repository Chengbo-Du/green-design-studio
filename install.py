"""
GDS Installer
Detects and validates all GDS dependencies, installs CONTAM if missing,
and writes config.json for the Grasshopper canvas to read on startup.

Required versions:
    Ladybug Tools  1.9+  (ships EnergyPlus 24.2 and OpenStudio 3.9)
    EnergyPlus     24.2+
    OpenStudio     3.9+
    CONTAM         3.4+
    Python         3.9+
"""

import os
import sys
import json
import time
import ctypes
import urllib.request
import subprocess
import tempfile

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


# ── Constants ────────────────────────────────────────────────────────────────

CONTAM_URL      = "https://www.nist.gov/system/files/documents/2026/01/08/CONTAM-3.4.0.8-Win32-setup.exe"
CONTAM_EXE_NAME = "CONTAM-3.4.0.8-Win32-setup.exe"
EPW_FILENAME    = "Syracuse_ABC_2023_composite.epw"
CONFIG_FILE     = "config.json"

GDS_FOLDER_NAMES = [
    "green-design-studio-main",
    "green-design-studio",
    "GDS",
    "gds",
    "Green-Design-Studio",
    "GreenDesignStudio",
]

GDS_BASE_LOCATIONS = [
    "Desktop",
    "Documents",
    "Downloads",
    "",
]


# ── Admin ────────────────────────────────────────────────────────────────────

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def request_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit(0)

if not is_admin():
    request_admin()


# ── Print helpers ────────────────────────────────────────────────────────────

def header(text):
    print(f"\n{'-' * 50}\n  {text}\n{'-' * 50}")

def ok(text):   print(f"  [OK]   {text}")
def err(text):  print(f"  [ERR]  {text}")
def info(text): print(f"  [INFO] {text}")
def warn(text): print(f"  [WARN] {text}")


# ── GDS root ─────────────────────────────────────────────────────────────────

def _is_gds_root(path):
    return (os.path.exists(os.path.join(path, "tools")) and
            os.path.exists(os.path.join(path, "case-study")))

def find_gds_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if _is_gds_root(script_dir):
        return script_dir

    username = os.environ.get("USERNAME", "")
    user_root = f"C:\\Users\\{username}"

    for base in GDS_BASE_LOCATIONS:
        for name in GDS_FOLDER_NAMES:
            path = os.path.join(user_root, base, name) if base else os.path.join(user_root, name)
            if _is_gds_root(path):
                return path

    for base in ["Downloads", "Documents", "Desktop"]:
        base_path = os.path.join(user_root, base)
        if os.path.exists(base_path):
            try:
                for folder in os.listdir(base_path):
                    full = os.path.join(base_path, folder)
                    if os.path.isdir(full) and _is_gds_root(full):
                        return full
            except:
                pass

    return None


# ── Ladybug Tools ────────────────────────────────────────────────────────────

def _find_energyplus(lbt_root):
    try:
        for folder in os.listdir(lbt_root):
            if "openstudio" in folder.lower():
                candidate = os.path.join(lbt_root, folder, "EnergyPlus")
                if os.path.exists(candidate):
                    return candidate
    except:
        pass

    for v in ["24-2-0", "24-1-0", "25-1-0", "26-1-0"]:
        p = f"C:\\EnergyPlusV{v}"
        if os.path.exists(p):
            return p

    try:
        for folder in os.listdir("C:\\"):
            if "EnergyPlus" in folder and os.path.isdir(os.path.join("C:\\", folder)):
                return os.path.join("C:\\", folder)
    except:
        pass
    return None

def find_ladybug():
    username = os.environ.get("USERNAME", "")
    lbt_root = os.path.join("C:\\Users", username, "ladybug_tools")

    if not os.path.exists(lbt_root):
        return None, None, None

    lbt_python = os.path.join(lbt_root, "python", "python.exe")
    if not os.path.exists(lbt_python):
        lbt_python = None

    ep_path = _find_energyplus(lbt_root)
    return lbt_root, lbt_python, ep_path

def check_energyplus_version(ep_path):
    if not ep_path:
        return False
    for marker in ["24-2", "24-3", "25", "26"]:
        if marker in ep_path:
            return True
    idd = os.path.join(ep_path, "Energy+.idd")
    if os.path.exists(idd):
        try:
            with open(idd) as f:
                line = f.readline()
            return "24.2" in line or "24.3" in line
        except:
            pass
    return False


# ── CONTAM ───────────────────────────────────────────────────────────────────

def find_contam():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
        )
        i = 0
        while True:
            try:
                name = winreg.EnumKey(key, i)
                sub = winreg.OpenKey(key, name)
                try:
                    if "CONTAM" in winreg.QueryValueEx(sub, "DisplayName")[0]:
                        loc = winreg.QueryValueEx(sub, "InstallLocation")[0]
                        exe = os.path.join(loc, "contamx3.exe")
                        if os.path.exists(exe):
                            return exe
                except:
                    pass
                i += 1
            except OSError:
                break
    except:
        pass

    for base in ["C:\\Program Files (x86)\\NIST", "C:\\Program Files\\NIST"]:
        if os.path.exists(base):
            for folder in os.listdir(base):
                if "CONTAM" in folder.upper():
                    exe = os.path.join(base, folder, "contamx3.exe")
                    if os.path.exists(exe):
                        return exe
    return None

def check_contam_version(exe):
    if not exe:
        return False
    folder = os.path.dirname(exe)
    return any(v in folder for v in ["3.4", "3.5", "3.6", "3.7", "3.8", "3.9"])

def download_contam(dest_folder):
    installer_path = os.path.join(dest_folder, CONTAM_EXE_NAME)
    info("Downloading CONTAM 3.4 from NIST (~6 MB)...")

    # NIST server requires a browser-like User-Agent or it blocks the request
    request = urllib.request.Request(
        CONTAM_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )

    with urllib.request.urlopen(request) as response:
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        block_size = 8192
        with open(installer_path, "wb") as f:
            while True:
                chunk = response.read(block_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = min(int(downloaded * 100 / total_size), 100)
                    bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
                    print(f"\r  [{bar}] {pct}%", end="", flush=True)
    print()
    return installer_path

def install_contam():
    tmp = tempfile.mkdtemp()
    try:
        installer = download_contam(tmp)
        info("Installing silently...")
        subprocess.run([installer, "/S"], capture_output=True, timeout=120)
        time.sleep(5)
        path = find_contam()
        if path:
            ok(f"CONTAM installed: {path}")
            return path
        err("Installation may have failed — install manually")
        info(f"Download: {CONTAM_URL}")
        return None
    except urllib.error.URLError as e:
        err(f"Could not download CONTAM — {e.reason}")
        info(f"Manual download: {CONTAM_URL}")
        return None
    except subprocess.TimeoutExpired:
        err("Installer timed out")
        return None
    except Exception as e:
        err(f"Install failed: {e}")
        return None
    finally:
        try:
            os.remove(os.path.join(tmp, CONTAM_EXE_NAME))
        except:
            pass


# ── Python ───────────────────────────────────────────────────────────────────
# CONTAM scripts (gds_contam_v3.py, gds_contam_viewer.py) use stdlib only
# Any Python 3.9+ works — no specific version or packages required

def find_python():
    username = os.environ.get("USERNAME", "")
    candidates = [
        os.path.join("C:\\Users", username, "ladybug_tools", "python", "python.exe"),
        *[os.path.join("C:\\Users", username, "AppData", "Local", "Programs",
                       "Python", f"Python{v}", "python.exe")
          for v in ["313", "312", "311", "310", "39"]],
        "C:\\Windows\\py.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


# ── config.json ──────────────────────────────────────────────────────────────

def write_config(gds_root, contam_exe, python_exe):
    config = {
        "gds_root":      gds_root,
        "weather_path":  os.path.join(gds_root, "case-study", EPW_FILENAME),
        "site_context":  os.path.join(gds_root, "case-study"),
        "contam_exe":    contam_exe,
        "python_exe":    python_exe,
        "contam_script": os.path.join(gds_root, "tools", "gds_contam_v3.py"),
        "viewer_script": os.path.join(gds_root, "tools", "gds_contam_viewer.py"),
    }
    path = os.path.join(gds_root, CONFIG_FILE)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    return path


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    header("GDS Installer")
    info("Admin privileges active")
    info("Required: LBT 1.9+ | EnergyPlus 24.2+ | OpenStudio 3.9+ | CONTAM 3.4+ | Python 3.9+")

    errors, warnings = [], []

    # GDS root
    header("Step 1 - GDS folder")
    gds_root = find_gds_root()
    if gds_root:
        ok(f"GDS root: {gds_root}")
    else:
        err("GDS folder not found")
        info("Make sure install.exe is inside the GDS folder")
        input("\nPress Enter to exit...")
        return

    epw = os.path.join(gds_root, "case-study", EPW_FILENAME)
    if os.path.exists(epw):
        ok("Weather file found")
    else:
        warn(f"Weather file missing: {EPW_FILENAME}")
        info("Add the .epw file to case-study/")
        warnings.append("EPW file missing")

    # Ladybug + EnergyPlus
    header("Step 2 - Ladybug Tools")
    info("Ladybug 1.9+ ships EnergyPlus 24.2 and OpenStudio 3.9 automatically")
    lbt_root, _, ep_path = find_ladybug()

    if lbt_root:
        ok(f"Ladybug Tools: {lbt_root}")
    else:
        err("Ladybug Tools not found")
        info("Install via installer.gh — food4rhino.com/en/app/ladybug-tools")
        errors.append("Ladybug Tools not found")

    if ep_path:
        if check_energyplus_version(ep_path):
            ok(f"EnergyPlus 24.2+: {ep_path}")
        else:
            warn(f"EnergyPlus version may be below 24.2: {ep_path}")
            info("Reinstall Ladybug Tools 1.9 to get EnergyPlus 24.2")
            warnings.append("EnergyPlus version may be too old")
    else:
        err("EnergyPlus not found")
        info("Install Ladybug Tools 1.9 — it includes EnergyPlus 24.2")
        errors.append("EnergyPlus not found")

    # CONTAM
    header("Step 3 - CONTAM")
    contam_exe = find_contam()

    if contam_exe:
        if check_contam_version(contam_exe):
            ok(f"CONTAM 3.4+: {contam_exe}")
        else:
            warn(f"CONTAM version may be below 3.4: {contam_exe}")
            warnings.append("CONTAM version may be too old")
    else:
        warn("CONTAM not found — downloading and installing...")
        contam_exe = install_contam()
        if not contam_exe:
            errors.append("CONTAM installation failed")

    # Python
    header("Step 4 - Python")
    python_exe = find_python()

    if python_exe:
        ok(f"Python found: {python_exe}")
    else:
        warn("Python not found — install from python.org")
        warnings.append("Python not found")
        python_exe = "NOT FOUND"

    # Write config
    header("Step 5 - Writing config.json")
    if not errors:
        config_path = write_config(gds_root, contam_exe, python_exe)
        ok(f"config.json written: {config_path}")
    else:
        err("config.json not written — fix errors above first")
        errors.append("config.json not written")

    # Summary
    header("Summary")
    if not errors and not warnings:
        ok("All checks passed")
        ok("Open GDS_General.gh in Grasshopper to run simulations")
    elif not errors:
        for w in warnings:
            warn(w)
        ok("config.json written — GDS should work, review warnings above")
    else:
        for e in errors:
            err(e)
        for w in warnings:
            warn(w)
        info("Fix errors above and run install.exe again")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()