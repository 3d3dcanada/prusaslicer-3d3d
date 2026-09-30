#!/usr/bin/env python3
"""Orca -> PrusaSlicer 3.0.0-alpha11 field map for the Core One L.

Reads Ken's OrcaSlicer user presets and the PS3 config schema exported by
`PrusaSlicer --export-config-schema`, then emits ORCA-TO-PS3-MAP.md.

Every PS3 target key is checked against the schema. A key that does not exist
in PS3 is reported as MISSING, never silently dropped.
"""
import json, os, sys, glob

ORCA = os.path.expanduser("~/.config/OrcaSlicer/user/default")
OUT  = os.path.expanduser("~/Desktop/3D3D-STL/_slicer/prusaslicer3")
SCHEMA = os.path.join(OUT, "evidence", "ps3-config-schema.json")
STOCK  = os.path.join(OUT, "evidence", "slices", "cube20-COL04HF-stock.gcode")

# Orca key -> PrusaSlicer key. None = no equivalent, handled by hand.
KEYMAP = {
    # --- process: speeds ---
    "outer_wall_speed":                 "external_perimeter_speed",
    "inner_wall_speed":                 "perimeter_speed",
    "sparse_infill_speed":              "infill_speed",
    "internal_solid_infill_speed":      "solid_infill_speed",
    "top_surface_speed":                "top_solid_infill_speed",
    "gap_infill_speed":                 "gap_fill_speed",
    "initial_layer_speed":              "first_layer_speed",
    "initial_layer_infill_speed":       "first_layer_solid_infill_speed",
    "small_perimeter_speed":            "small_perimeter_speed",
    "bridge_speed":                     "bridge_speed",
    "support_speed":                    "support_material_speed",
    "travel_speed":                     "travel_speed",
    "travel_speed_z":                   "travel_speed_z",
    # --- process: accelerations ---
    "default_acceleration":             "default_acceleration",
    "outer_wall_acceleration":          "external_perimeter_acceleration",
    "inner_wall_acceleration":          "perimeter_acceleration",
    "sparse_infill_acceleration":       "infill_acceleration",
    "internal_solid_infill_acceleration":"solid_infill_acceleration",
    "top_surface_acceleration":         "top_solid_infill_acceleration",
    "initial_layer_acceleration":       "first_layer_acceleration",
    "travel_acceleration":              "travel_acceleration",
    # --- process: other ---
    "enable_arc_fitting":               "arc_fitting",
    # --- filament ---
    "nozzle_temperature":               "temperature",
    "nozzle_temperature_initial_layer": "first_layer_temperature",
    "hot_plate_temp":                   "bed_temperature",
    "hot_plate_temp_initial_layer":     "first_layer_bed_temperature",
    "textured_plate_temp":              "bed_temperature",
    "textured_plate_temp_initial_layer":"first_layer_bed_temperature",
    "chamber_temperature":              "chamber_temperature",
    "filament_max_volumetric_speed":    "filament_max_volumetric_speed",
    "filament_start_gcode":             "start_filament_gcode",
    "filament_type":                    "filament_type",
    "filament_vendor":                  "filament_vendor",
    "filament_cost":                    "filament_cost",
    "filament_density":                 "filament_density",
    "filament_flow_ratio":              "extrusion_multiplier",
    "slow_down_layer_time":             "slowdown_below_layer_time",
    "slow_down_min_speed":              "min_print_speed",
    "fan_cooling_layer_time":           "fan_below_layer_time",
    "fan_max_speed":                    "max_fan_speed",
    "fan_min_speed":                    "min_fan_speed",
    "close_fan_the_first_x_layers":     "disable_fan_first_layers",
    "full_fan_speed_layer":             "full_fan_speed_layer",
    "overhang_fan_speed":               "bridge_fan_speed",
    # --- machine ---
    "machine_max_speed_x":              "machine_max_feedrate_x",
    "machine_max_speed_y":              "machine_max_feedrate_y",
    "machine_max_speed_z":              "machine_max_feedrate_z",
    "machine_max_acceleration_extruding":"machine_max_acceleration_extruding",
    "machine_max_acceleration_travel":  "machine_max_acceleration_travel",
    # --- no PS3 equivalent / not a slicing value ---
    "host_type":            None, "print_host": None, "printhost_apikey": None,
    "printhost_user":       None, "printhost_password": None,
    "printhost_authorization_type": None,
    "flashforge_serial_number": None,
    "printer_extruder_id":  None, "printer_extruder_variant": None,
}
# bookkeeping keys that carry no tuning
SKIP = {"from","is_custom_defined","name","type","version","inherits",
        "print_settings_id","filament_settings_id","printer_settings_id",
        "compatible_printers"}

def load_schema():
    d = json.load(open(SCHEMA))
    keys = {}
    for sec in ("printer","print","filament","tool_print"):
        for item in d[sec]["items"]:
            keys[item["name"]] = (sec, item.get("value"))
    return keys

def stock_values():
    """Stock PS3 vendor values, read off the reference slice's config block."""
    vals = {}
    if not os.path.exists(STOCK):
        return vals
    for line in open(STOCK, errors="ignore"):
        if not line.startswith("; "):
            continue
        if " = " not in line:
            continue
        k, _, v = line[2:].partition(" = ")
        vals[k.strip()] = v.strip()
    return vals

def scalar(v):
    if isinstance(v, list):
        return v[0] if len(v) == 1 else json.dumps(v)
    return v

def rows_for(path, schema, stock):
    d = json.load(open(path))
    out = []
    for k in sorted(d):
        if k in SKIP:
            continue
        ov = scalar(d[k])
        if k in KEYMAP and KEYMAP[k] is None:
            out.append((k, ov, "(none)", "", "NO PS3 EQUIVALENT"))
            continue
        pk = KEYMAP.get(k, k)
        if pk in schema:
            sv = stock.get(pk, "")
            same = str(sv) == str(ov)
            out.append((k, ov, pk, sv, "same as stock" if same else "CARRY"))
        else:
            out.append((k, ov, pk, "", "MISSING IN PS3"))
    return out

def md_escape(s):
    return str(s).replace("|", "\\|").replace("\n", "<br>")

def main():
    schema = load_schema()
    stock = stock_values()
    groups = [
        ("Machine preset", sorted(glob.glob(f"{ORCA}/machine/*CORE One L HF 0.4*.json"))),
        ("Process presets (0.4 HF)", sorted(glob.glob(f"{ORCA}/process/*CORE One L HF0.4*.json"))),
        ("Filament presets (0.4 HF)", sorted(glob.glob(f"{ORCA}/filament/*CORE One L HF0.4*.json"))),
    ]
    n_carry = n_missing = n_none = 0
    lines = []
    for title, files in groups:
        lines.append(f"\n### {title}\n")
        for f in files:
            name = os.path.basename(f)[:-5]
            lines.append(f"\n**`{name}`**\n")
            lines.append("| Orca field | Orca value | PS3 field | PS3 stock | Verdict |")
            lines.append("|---|---|---|---|---|")
            for k, ov, pk, sv, verdict in rows_for(f, schema, stock):
                if verdict == "CARRY":       n_carry += 1
                elif verdict.startswith("MISSING"): n_missing += 1
                elif verdict.startswith("NO PS3"):  n_none += 1
                lines.append(f"| `{k}` | {md_escape(ov)} | `{pk}` | {md_escape(sv)} | {verdict} |")
    print("\n".join(lines))
    sys.stderr.write(f"carry={n_carry} missing={n_missing} no-equivalent={n_none}\n")

if __name__ == "__main__":
    main()
