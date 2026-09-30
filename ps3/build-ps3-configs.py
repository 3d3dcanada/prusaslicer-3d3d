#!/usr/bin/env python3
"""Port Ken's OrcaSlicer Core One L 0.4 HF presets into PrusaSlicer 3 config JSON.

Why a JSON config and not CLI flags: in PrusaSlicer 3.0.0-alpha11 every
per-object-overridable print option (perimeters, fill_density, fill_pattern,
extrusion_width, every speed and acceleration) aborts the slice with an
unexplained "(4, [])" when passed as a --flag. Filament and printer options are
fine. The `--save` / `--load` JSON round trip is the path that works.

Usage:
    build-ps3-configs.py            # write every 0.4 HF combination
    build-ps3-configs.py --one "<orca process>" "<orca filament>"
"""
import json, os, subprocess, sys, glob, shlex

HOME   = os.path.expanduser("~")
ORCA   = f"{HOME}/.config/OrcaSlicer/user/default"
OUTDIR = f"{HOME}/Desktop/3D3D-STL/_slicer/prusaslicer3/configs"
PS3    = ["flatpak", "run", "--branch=beta", "com.prusa3d.PrusaSlicer"]

# The PS3 vendor presets we build on top of. The Core One L 0.4 HF vendor
# profile already carries every 3D3D machine deviation (M203 X500 Y500, accel
# 7000/6000, the Z150 taper, M572 pressure advance, M142 heatbreak), so the
# printer preset needs no porting at all.
PRINTER = "Prusa CORE One L 0.4 HF"
BASE_PRINT = {   # Orca 3D3D process -> nearest PS3 vendor print profile
    "0.15mm MAX":     "0.15mm SPEED @COREONEL 0.4HF",
    "0.15mm QUALITY": "0.15mm STRUCTURAL @COREONEL 0.4HF",
    "0.15mm SPEED":   "0.15mm SPEED @COREONEL 0.4HF",
    "0.15mm IRON":    "0.15mm STRUCTURAL @COREONEL 0.4HF",
    "0.20mm MAX":     "0.20mm SPEED @COREONEL 0.4HF",
    "0.20mm QUALITY": "0.20mm STRUCTURAL @COREONEL 0.4HF",
    "0.20mm SPEED":   "0.20mm SPEED @COREONEL 0.4HF",
    "0.20mm IRON":    "0.20mm STRUCTURAL @COREONEL 0.4HF",
    "0.25mm MAX":     "0.25mm SPEED @COREONEL 0.4HF",
    "0.25mm QUALITY": "0.25mm STRUCTURAL @COREONEL 0.4HF",
    "0.25mm SPEED":   "0.25mm SPEED @COREONEL 0.4HF",
    "0.25mm IRON":    "0.25mm STRUCTURAL @COREONEL 0.4HF",
}
BASE_FILAMENT = {  # Orca 3D3D filament -> nearest PS3 vendor filament profile
    "Sunlu PETG HS":    "Sunlu PETG@COREONE HF0.4@COREONE 0.4",
    "PETG MAXFLOW":     "Sunlu PETG@COREONE HF0.4@COREONE 0.4",
    "PLA MAXFLOW":      "Prusament PLA @COREONE HF0.4@COREONE 0.4",
    "PLA Silk MAXFLOW": "Generic PLA Silk@COREONE HF0.4@COREONE 0.4",
    "ASA MAXFLOW":      "Prusament ASA@COREONE HF0.4@COREONE 0.4",
    "ABS MAXFLOW":      "Generic ABS@COREONE HF0.4@COREONE 0.4",
    "PC MAXFLOW":       "Prusament PC Blend@COREONE HF0.4@COREONE 0.4",
    "TPU MAXFLOW":      "Prusament TPU 95A@COREONE HF0.4@COREONE 0.4",
    "TPU 95A MAXFLOW":  "Prusament TPU 95A@COREONE HF0.4@COREONE 0.4",
    "TPE 85 MAXFLOW":   "Forward AM Ultrafuse TPU-85A@COREONE HF0.4@COREONE 0.4",
    "CAL PETG 255":     "Sunlu PETG@COREONE HF0.4@COREONE 0.4",
    "CAL PETG 270":     "Sunlu PETG@COREONE HF0.4@COREONE 0.4",
    # PETG CF and ASA GF are ABRASIVE and exist on the 0.6 ObXidian only. The
    # 0.4 is plain brass. PrusaSlicer 3 can only address the 0.4 from the CLI,
    # so they are deliberately absent here rather than silently built for a
    # nozzle they would destroy.
}

KEYMAP_PRINT = {
    "outer_wall_speed":"external_perimeter_speed","inner_wall_speed":"perimeter_speed",
    "sparse_infill_speed":"infill_speed","internal_solid_infill_speed":"solid_infill_speed",
    "top_surface_speed":"top_solid_infill_speed","gap_infill_speed":"gap_fill_speed",
    "initial_layer_speed":"first_layer_speed","initial_layer_infill_speed":"first_layer_solid_infill_speed",
    "small_perimeter_speed":"small_perimeter_speed","bridge_speed":"bridge_speed",
    "support_speed":"support_material_speed","travel_speed":"travel_speed",
    "travel_speed_z":"travel_speed_z","default_acceleration":"default_acceleration",
    "outer_wall_acceleration":"external_perimeter_acceleration",
    "inner_wall_acceleration":"perimeter_acceleration",
    "sparse_infill_acceleration":"infill_acceleration",
    "internal_solid_infill_acceleration":"solid_infill_acceleration",
    "top_surface_acceleration":"top_solid_infill_acceleration",
    "initial_layer_acceleration":"first_layer_acceleration",
    "travel_acceleration":"travel_acceleration","enable_arc_fitting":"arc_fitting",
    # bridging and overhangs, added with the material matrix
    "bridge_acceleration":"bridge_acceleration", "bridge_flow":"bridge_flow_ratio",
    "thick_bridges":"thick_bridges", "detect_overhang_wall":"overhangs",
    "enable_overhang_speed":"enable_dynamic_overhang_speeds",
    "extra_perimeters_on_overhangs":"extra_perimeters_on_overhangs",
    "overhang_1_4_speed":"overhang_speed_0", "overhang_2_4_speed":"overhang_speed_1",
    "overhang_3_4_speed":"overhang_speed_2", "overhang_4_4_speed":"overhang_speed_3",
    # ironing. ironing_type is an enum in both, but PrusaSlicer also has a
    # separate `ironing` bool that actually switches it on; VALMAP handles the
    # enum and the FINISH block sets the bool.
    "ironing_type":"ironing_type", "ironing_flow":"ironing_flowrate",
    "ironing_speed":"ironing_speed", "ironing_spacing":"ironing_spacing",
    # Orca-only, no PrusaSlicer equivalent. Named so they are reported as
    # dropped on purpose rather than looking like an oversight:
    #   bridge_density, internal_bridge_flow, enable_extra_bridge_layer,
    #   ironing_pattern
}
KEYMAP_FIL = {
    "nozzle_temperature":"temperature","nozzle_temperature_initial_layer":"first_layer_temperature",
    "hot_plate_temp":"bed_temperature","hot_plate_temp_initial_layer":"first_layer_bed_temperature",
    "chamber_temperature":"chamber_temperature",
    "filament_max_volumetric_speed":"filament_max_volumetric_speed",
    "filament_start_gcode":"start_filament_gcode","filament_type":"filament_type",
    "filament_cost":"filament_cost","filament_density":"filament_density",
    "filament_flow_ratio":"extrusion_multiplier",
    "slow_down_layer_time":"slowdown_below_layer_time","slow_down_min_speed":"min_print_speed",
    "fan_cooling_layer_time":"fan_below_layer_time","fan_max_speed":"max_fan_speed",
    "fan_min_speed":"min_fan_speed","close_fan_the_first_x_layers":"disable_fan_first_layers",
    "full_fan_speed_layer":"full_fan_speed_layer","overhang_fan_speed":"bridge_fan_speed",
    "filament_vendor":"filament_vendor", "filament_notes":"filament_notes",
}
VALMAP = {
    "arc_fitting": {"1": "emit_center", "0": "disabled"},
    # Orca's ironing_type vocabulary is not PrusaSlicer's.
    "ironing_type": {"no ironing": "top", "top": "top",
                     "topmost surface": "topmost", "all solid": "solid"},
}

# Ironing and bridging. Deliberately conservative: ironing is the one setting
# that ruins a top surface when it is too hot or too fast, and 12% sits under
# Prusa's 15% default because PETG smears above that. Prusa already ship
# thick_bridges 0 and enable_dynamic_overhang_speeds 1, so those are confirmed
# rather than changed.
FINISH = {
    "ironing": True,
    "ironing_type": "top",
    "ironing_flowrate": "12%",
    "ironing_spacing": 0.1,
    "ironing_speed": 20.0,
    "thick_bridges": False,
    "bridge_flow_ratio": 1.0,
    "enable_dynamic_overhang_speeds": True,
    "extra_perimeters_on_overhangs": True,
    "overhangs": True,
}
# Ironing is wrong for flexibles: the nozzle drags and balls the surface.
NO_IRON_TYPES = {"FLEX", "TPU", "TPE"}
SKIP = {"from","is_custom_defined","name","type","version","inherits","print_settings_id",
        "filament_settings_id","printer_settings_id","compatible_printers",
        "textured_plate_temp","textured_plate_temp_initial_layer"}


def scalar(v):
    return v[0] if isinstance(v, list) and len(v) == 1 else v


def coerce(old, new):
    """Match the shape PS3 already uses for this key.

    PS3 stores some options as {"value": x, "is_percent": bool} and filament
    options as one-element lists (one per extruder). Writing a bare number where
    PS3 wants a dict is silently wrong, so mirror whatever is already there.
    """
    if isinstance(old, dict) and "value" in old:
        # PS3 stores these as {"value": x, "is_percent": bool}. Whether a value
        # is a percentage is a property of the VALUE, not the key: Orca's
        # external_perimeter_speed 142 is absolute mm/s where Prusa's default is
        # "50%" of the perimeter speed, while ironing_flowrate really is a
        # percentage. So a trailing % in the incoming value decides it, and a
        # bare number is absolute. Getting this backwards turned 12% ironing
        # flow into 12 mm.
        txt = str(new).strip()
        if txt.endswith("%"):
            return {"value": float(txt[:-1]), "is_percent": True}
        return {"value": float(txt), "is_percent": False}
    if isinstance(old, list):
        return [coerce(old[0], new)] * len(old) if old else [new]
    if isinstance(old, bool):
        return str(new) not in ("0", "false", "False")
    if isinstance(old, float):
        return float(new)
    if isinstance(old, int) and not isinstance(old, bool):
        try:
            return int(new)
        except (TypeError, ValueError):
            return float(new)
    return new


def lift_pressure_advance(src, section, report):
    """Move a hand-written `M572 S<x>` out of Orca's start G-code.

    PrusaSlicer 3 emits its OWN M572 from the filament profile's
    pressure_advance_value AFTER start_filament_gcode runs, so an M572 injected
    by hand is overwritten a line later and the tuned value is silently lost.
    PS 2.9.6 and Orca had no such option, which is why it was hand-written at
    all. Lift it into the real setting and strip it from the G-code.
    """
    import re
    g = src.get("filament_start_gcode")
    g = g[0] if isinstance(g, list) and g else g
    if not isinstance(g, str):
        return
    m = re.search(r"^\s*M572\s+S([0-9.]+)", g, re.M)
    if not m:
        return
    val = float(m.group(1))
    kept = "\n".join(l for l in g.splitlines()
                     if not re.match(r"\s*M572\s+S[0-9.]+", l))
    src["filament_start_gcode"] = [kept]
    if "pressure_advance_value" in section:
        section["pressure_advance_value"] = coerce(section["pressure_advance_value"], val)
        section["pressure_advance"] = coerce(section["pressure_advance"], "enabled")
        report.append(("carried", "filament_start_gcode M572 -> pressure_advance_value", val))
    else:
        report.append(("DROPPED (no PS3 key)", "M572 pressure advance", val))


def apply(section, preset_path, keymap, report):
    src = json.load(open(preset_path))
    for k in sorted(src):
        if k in SKIP:
            continue
        pk = keymap.get(k)
        if pk is None:
            report.append(("DROPPED (no PS3 key)", k, scalar(src[k])))
            continue
        v = scalar(src[k])
        if pk in VALMAP:
            v = VALMAP[pk].get(str(v), v)
        if pk not in section:
            report.append(("DROPPED (not in this config)", k, v))
            continue
        section[pk] = coerce(section[pk], v)
        report.append(("carried", f"{k} -> {pk}", v))


def save_base(print_profile, material_profile, dest):
    cmd = PS3 + ["--save", dest, "--printer-profile", PRINTER,
                 "--print-profile", print_profile,
                 "--material-profile", material_profile]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not os.path.exists(dest):
        sys.stderr.write(r.stdout[-2000:] + r.stderr[-2000:])
        raise SystemExit(f"--save produced nothing for {print_profile} / {material_profile}")


def build(orca_proc, orca_fil):
    os.makedirs(OUTDIR, exist_ok=True)
    pbase = BASE_PRINT[orca_proc.split(" @")[0]]
    fbase = BASE_FILAMENT[orca_fil.split(" @")[0]]
    out = f"{OUTDIR}/{orca_proc} + {orca_fil}.json".replace(" @CORE One L HF0.4 - 3D3D", "")
    save_base(pbase, fbase, out)
    cfg = json.load(open(out))
    c = cfg["configuration"]
    report = []
    apply(c["print_settings"], f"{ORCA}/process/{orca_proc}.json", KEYMAP_PRINT, report)
    fs = c["filament_settings"]
    fsec = fs[0] if isinstance(fs, list) else fs
    # THE CLAMP. PrusaSlicer's PETG high-flow parent sets
    # filament_infill_max_speed = 200 and Orca has no such key, so any Orca
    # infill speed above 200 is silently cut on the way over. Ken's is 236.
    # 0 means no clamp. This has to happen on the config too, not just the CLI.
    if "filament_infill_max_speed" in fsec:
        fsec["filament_infill_max_speed"] = coerce(fsec["filament_infill_max_speed"], 0)
        report.append(("carried", "filament_infill_max_speed -> 0 (clamp removed)", 0))
    fsrc = json.load(open(f"{ORCA}/filament/{orca_fil}.json"))
    lift_pressure_advance(fsrc, fsec, report)
    tmp = f"{OUTDIR}/.{orca_fil}.patched.json"
    json.dump(fsrc, open(tmp, "w"))
    apply(fsec, tmp, KEYMAP_FIL, report)
    os.remove(tmp)
    # ironing and bridging, unless the material is a flexible
    ftype = str(fsec.get("filament_type") or "").upper()
    flex = any(t in ftype for t in NO_IRON_TYPES) or "TPU" in orca_fil.upper()
    want_iron = " IRON " in f" {orca_proc} "
    for k, v in FINISH.items():
        if k.startswith("ironing") and not want_iron:
            continue
        if k not in c["print_settings"]:
            report.append(("DROPPED (not in this config)", k, v))
            continue
        if flex and k.startswith("ironing"):
            continue
        c["print_settings"][k] = coerce(c["print_settings"][k], v)
        report.append(("carried", f"finish/{k}", v))
    if flex or not want_iron:
        c["print_settings"]["ironing"] = False
        report.append(("carried", "finish/ironing", "off (flexible)"))

    json.dump(cfg, open(out, "w"), indent=1)
    return out, report


def main():
    if "--one" in sys.argv:
        i = sys.argv.index("--one")
        pairs = [(sys.argv[i + 1], sys.argv[i + 2])]
    else:
        procs = [os.path.basename(p)[:-5]
                 for p in sorted(glob.glob(f"{ORCA}/process/*CORE One L HF0.4*.json"))]
        fils = [os.path.basename(p)[:-5]
                for p in sorted(glob.glob(f"{ORCA}/filament/*CORE One L HF0.4*.json"))]
        pairs = [(p, f) for p in procs for f in fils]
    for p, f in pairs:
        try:
            out, report = build(p, f)
        except Exception as e:
            print(f"FAIL  {p} + {f}: {e}")
            continue
        dropped = [r for r in report if r[0].startswith("DROPPED")]
        print(f"OK    {os.path.basename(out)}  "
              f"carried={len(report)-len(dropped)} dropped={len(dropped)}")
        for d in dropped:
            print(f"        {d[0]}: {d[1]} = {d[2]}")


if __name__ == "__main__":
    main()
