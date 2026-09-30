#!/usr/bin/env python3
"""Emit PrusaSlicer 3 CLI overrides for a given Orca process + filament preset.

Usage: overrides.py "<process preset name>" "<filament preset name>"
Prints one shell-quoted --flag=value per line, ready for `xargs` or $(...).

Every emitted flag is validated against the PS3 config schema first, so a
rename in a future alpha fails loudly instead of being silently ignored.
"""
import json, os, sys, shlex

ORCA   = os.path.expanduser("~/.config/OrcaSlicer/user/default")
SCHEMA = os.path.expanduser("~/Desktop/3D3D-STL/_slicer/prusaslicer3/evidence/ps3-config-schema.json")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
KEYMAP = import_module("build_map_keys").KEYMAP if False else None

# same map as build-map.py; kept here so this script stands alone
KEYMAP = {
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
    "nozzle_temperature":"temperature","nozzle_temperature_initial_layer":"first_layer_temperature",
    "hot_plate_temp":"bed_temperature","hot_plate_temp_initial_layer":"first_layer_bed_temperature",
    "chamber_temperature":"chamber_temperature",
    "filament_max_volumetric_speed":"filament_max_volumetric_speed",
    "filament_start_gcode":"start_filament_gcode","filament_type":"filament_type",
    "filament_vendor":"filament_vendor","filament_cost":"filament_cost",
    "filament_density":"filament_density","filament_flow_ratio":"extrusion_multiplier",
    "slow_down_layer_time":"slowdown_below_layer_time","slow_down_min_speed":"min_print_speed",
    "fan_cooling_layer_time":"fan_below_layer_time","fan_max_speed":"max_fan_speed",
    "fan_min_speed":"min_fan_speed","close_fan_the_first_x_layers":"disable_fan_first_layers",
    "full_fan_speed_layer":"full_fan_speed_layer","overhang_fan_speed":"bridge_fan_speed",
}
# Orca booleans -> PS3 enums. PS3 PANICs (ConfigValue.cpp:89) on a bad enum
# string instead of reporting the offending key, so translate before emitting.
VALMAP = {
    "arc_fitting": {"1": "emit_center", "0": "disabled",
                    "true": "emit_center", "false": "disabled"},
}
FLAGSET = set()
SKIP = {"from","is_custom_defined","name","type","version","inherits","print_settings_id",
        "filament_settings_id","printer_settings_id","compatible_printers",
        "textured_plate_temp","textured_plate_temp_initial_layer"}

FLAGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ps3-cli-flags.txt")

def cli_flags():
    """The flags PS3 actually accepts, harvested from `--help-fff`.

    The config schema is wider than the CLI: filament_vendor and
    first_layer_infill_speed are real settings with no command-line flag, and
    passing one aborts the whole slice with "arguments were not expected".
    """
    with open(FLAGS) as f:
        return {ln.strip() for ln in f if ln.strip()}

def schema_keys():
    d = json.load(open(SCHEMA))
    return {i["name"] for sec in ("printer","print","filament","tool_print") for i in d[sec]["items"]}

def scalar(v):
    return v[0] if isinstance(v, list) and len(v) == 1 else v

def emit(path, keys, out):
    d = json.load(open(path))
    for k in sorted(d):
        if k in SKIP:
            continue
        pk = KEYMAP.get(k, k)
        if pk not in keys:
            sys.stderr.write(f"NO PS3 KEY   {k} -> {pk}\n")
            continue
        flag = "--" + pk.replace("_", "-")
        if flag not in FLAGSET:
            sys.stderr.write(f"NO CLI FLAG  {k} -> {pk} (value {scalar(d[k])!r} "
                             f"cannot be carried on the command line)\n")
            continue
        v = scalar(d[k])
        if pk in VALMAP:
            v = VALMAP[pk].get(str(v), v)
        if isinstance(v, str) and "\n" in v:
            # PrusaSlicer's config deserializer expands the two-character \n
            # inside custom G-code fields. A real newline on the CLI gets
            # flattened to a space, which would fold M142 into the M572 comment.
            v = v.replace("\n", "\\n")
        out.append(f"--{pk.replace('_','-')}={v}")

def main():
    proc, fil = sys.argv[1], sys.argv[2]
    global FLAGSET
    keys = schema_keys()
    FLAGSET = cli_flags()
    out = []
    emit(f"{ORCA}/process/{proc}.json", keys, out)
    emit(f"{ORCA}/filament/{fil}.json", keys, out)
    # THE TRAP: PrusaSlicer's own PETG high-flow parent clamps infill to 200 mm/s
    # via filament_infill_max_speed. Orca has no such key, so an Orca infill
    # speed above 200 is silently cut when it moves to PrusaSlicer. 0 = no clamp.
    out.append("--filament-infill-max-speed=0")
    for o in out:
        print(shlex.quote(o))

if __name__ == "__main__":
    main()
