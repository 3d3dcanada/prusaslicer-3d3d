#!/usr/bin/env python3
"""Generate the full Core One L OrcaSlicer profile matrix.

Two nozzles, four materials plus TPU and PC, three speed tiers per layer height.
Source of truth lives here, not in ~/.config/OrcaSlicer, so a slicer upgrade
cannot eat the work.

Everything is derived, not typed. The governing equation is

    speed (mm/s) = volumetric flow (mm3/s) / (layer height * extrusion width)

so the per-role speeds below are computed from the nozzle's real flow ceiling
rather than written down and silently clamped. That is the whole lesson of the
PrusaSlicer profiles this replaces, where `infill_speed = 400` was capped to 200
by the filament and nobody could see it in the UI.

Flow figures are E3D's own published table for the High Flow Nextruder nozzles,
read 2026-08-31, quoted at the temperature in the comment beside each one.
"""
import glob
import json
import os
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ORCA_SYS = os.path.expanduser("~/.config/OrcaSlicer/system")
VERSION = "2.4.1.0"

# --------------------------------------------------------------- the machines
#
# Ken runs BOTH nozzles: the 0.6 is the High Flow ObXidian, the 0.4 is the plain
# High Flow (brass). They are different parts with different flow ceilings and
# different abrasion tolerance, so nothing is shared between the two families.

NOZZLES = {
    "HF0.4": {
        "machine": "Prusa CORE One L HF 0.4 nozzle",
        "width": 0.45,          # Prusa's own extrusion width at 0.4
        "hardened": False,      # brass: no CF, no GF, no glow-in-the-dark
        # E3D published table for the High Flow Nextruder nozzle, at the
        # temperature quoted. Brass and ObXidian are within 1 mm3/s at 0.4.
        "flow": {"PLA": (20, 220), "PETG": (25, 240), "ASA": (27, 260),
                 "ABS": (25, 255), "PC": (24, 275), "TPU": (8, 240)},
    },
    "HF0.6": {
        "machine": "Prusa CORE One L HF 0.6 nozzle",
        "width": 0.68,
        "hardened": True,       # ObXidian: CF and GF are fine
        # E3D: 0.6 HF ObXidian is PLA 30 @220, PETG 36 @240, ASA 32 @260.
        # Note Orca ships 31 for PETG here, which is 5 short of E3D's own
        # number, and 34 for ASA, which is 2 over it.
        "flow": {"PLA": (30, 220), "PETG": (36, 240), "ASA": (32, 260),
                 "ABS": (32, 255), "PC": (30, 275), "TPU": (12, 240)},
    },
}

# Layer heights that have a real Orca parent for each nozzle.
LAYERS = {
    "HF0.4": [("0.15", "0.15mm SPEED @CORE One L HF 0.4"),
              ("0.20", "0.20mm SPEED @CORE One L HF 0.4"),
              ("0.25", "0.25mm SPEED @CORE One L HF 0.4")],
    "HF0.6": [("0.20", "0.20mm SPEED @CORE One L HF 0.6"),
              ("0.25", "0.25mm SPEED @CORE One L HF 0.6"),
              ("0.32", "0.32mm SPEED @CORE One L HF 0.6"),
              ("0.40", "0.40mm SPEED @CORE One L HF 0.6")],
}

# --------------------------------------------------------------- the ceilings
#
# Prusa's own current vendor bundle for the CORE One **L**:
#   machine_max_feedrate_x/y            500      (the non-L CORE One is 350)
#   machine_max_acceleration_extruding  7000
#   machine_max_acceleration_travel     6000
#   machine_max_acceleration_x/y        10000
# `machine_limits_usage = emit_to_gcode`, so these are emitted as M201/M203 and
# the printer obeys whatever the profile says. Asking for more than the ceiling
# does not go faster, it just makes the profile lie.

MAX_TRAVEL = 500          # mm/s, Prusa's published figure for the L
MAX_ACCEL_PRINT = 7000    # mm/s2, machine_max_acceleration_extruding
MAX_ACCEL_TRAVEL = 6000   # mm/s2, machine_max_acceleration_travel

# Tier: (fraction of the flow ceiling, outer-wall fraction, accel fraction).
# QUALITY leaves headroom for surface finish; MAX runs the nozzle at E3D's
# published number and the motion system at Prusa's, which is the honest
# definition of "the absolute limit of this machine".
TIERS = {
    "QUALITY": (0.65, 0.45, 0.55),
    "SPEED":   (0.85, 0.60, 0.80),
    "MAX":     (1.00, 0.75, 1.00),
}


def L(v):
    return [str(v)]


def speed_for(flow, layer, width):
    """The only speed that means anything: what the flow ceiling permits."""
    return flow / (float(layer) * width)


def clamp(v, hi):
    return int(min(round(v), hi))


def build_processes():
    """One process per nozzle x layer height x tier.

    Speeds are sized against PETG, which is the material Ken actually runs and
    the one with the highest flow ceiling on both nozzles. A slower filament
    lowers the real speed by itself through filament_max_volumetric_speed, so
    sizing to the fastest material here is safe and keeps the count sane.
    """
    out = []
    for noz, spec in NOZZLES.items():
        width = spec["width"]
        flow_petg = spec["flow"]["PETG"][0]
        for layer, parent in LAYERS[noz]:
            ceiling = speed_for(flow_petg, layer, width)
            for tier, (f_flow, f_outer, f_accel) in TIERS.items():
                base = ceiling * f_flow
                # Travel is limited by the motion system, not by flow.
                travel = clamp(MAX_TRAVEL * (0.7 if tier == "QUALITY" else
                                             0.9 if tier == "SPEED" else 1.0),
                               MAX_TRAVEL)
                accel = clamp(MAX_ACCEL_PRINT * f_accel, MAX_ACCEL_PRINT)
                out.append({
                    "type": "process", "from": "User",
                    "name": f"{layer}mm {tier} @CORE One L {noz} - 3D3D",
                    "print_settings_id": f"{layer}mm {tier} @CORE One L {noz} - 3D3D",
                    "inherits": parent,
                    "compatible_printers": [spec["machine"]],

                    # Sparse infill is the only role with nothing to lose from
                    # running at the ceiling: it is buried.
                    "sparse_infill_speed": str(clamp(base, 1000)),
                    "internal_solid_infill_speed": str(clamp(base * 0.80, 1000)),
                    "inner_wall_speed": str(clamp(base * 0.75, 1000)),
                    # The outer wall is what anyone sees. It is deliberately the
                    # slowest printing role in every tier.
                    "outer_wall_speed": str(clamp(base * f_outer, 1000)),
                    "small_perimeter_speed": str(clamp(base * f_outer * 0.8, 1000)),
                    "top_surface_speed": str(clamp(base * 0.45, 1000)),
                    "gap_infill_speed": str(clamp(base * 0.45, 1000)),
                    "support_speed": str(clamp(base * 0.75, 1000)),
                    "bridge_speed": str(clamp(base * 0.22, 120)),
                    "initial_layer_speed": "45",
                    "initial_layer_infill_speed": "70",

                    "travel_speed": str(travel),
                    "travel_speed_z": "12",

                    "sparse_infill_acceleration": str(accel),
                    "inner_wall_acceleration": str(accel),
                    "outer_wall_acceleration": str(clamp(accel * 0.55, MAX_ACCEL_PRINT)),
                    "internal_solid_infill_acceleration": str(clamp(accel * 0.7, MAX_ACCEL_PRINT)),
                    "top_surface_acceleration": str(clamp(accel * 0.3, MAX_ACCEL_PRINT)),
                    "travel_acceleration": str(MAX_ACCEL_TRAVEL),
                    "default_acceleration": str(clamp(accel * 0.45, MAX_ACCEL_PRINT)),
                    "initial_layer_acceleration": "500",

                    # Cheap and unambiguously good at these speeds: fewer, longer
                    # moves through the planner on every curve.
                    "enable_arc_fitting": "1",
                })
    return out


def build_filaments():
    out = []
    for noz, spec in NOZZLES.items():
        for mat, (flow, at_temp) in spec["flow"].items():
            if mat == "TPU":
                parent = ("Prusa Generic TPU @CORE One 0.6" if noz == "HF0.6"
                          else "Prusa Generic TPU @CORE One")
            elif mat == "PC":
                parent = f"Prusament PC Blend @CORE One {noz[:2]} {noz[2:]}"
            else:
                parent = f"Prusa Generic {mat} @CORE One {noz[:2]} {noz[2:]}"
            out.append({
                "type": "filament", "from": "User",
                "name": f"{mat} MAXFLOW @CORE One L {noz} - 3D3D",
                "filament_settings_id": [f"{mat} MAXFLOW @CORE One L {noz} - 3D3D"],
                "inherits": parent,
                "compatible_printers": [spec["machine"]],
                # E3D's published ceiling for this nozzle and material. This is
                # the number to BEAT with a flow calibration, not to trust.
                "filament_max_volumetric_speed": L(flow),
            })

    # Sunlu PETG is the spool he actually runs, at his own measured 268 C.
    for noz, spec in NOZZLES.items():
        flow = spec["flow"]["PETG"][0]
        # E3D quote PETG at 240 C and he runs 268. Flow scales with melt rate,
        # so his ceiling is at or above the published one, but that has to be
        # earned by calibration rather than assumed: hold at the published
        # number and let the tower move it.
        out.append({
            "type": "filament", "from": "User",
            "name": f"Sunlu PETG HS @CORE One L {noz} - 3D3D",
            "filament_settings_id": [f"Sunlu PETG HS @CORE One L {noz} - 3D3D"],
            "inherits": f"Prusa Generic PETG @CORE One {noz[:2]} {noz[2:]}",
            "compatible_printers": [spec["machine"]],
            "nozzle_temperature": L(268),
            "nozzle_temperature_initial_layer": L(260),
            "hot_plate_temp": L(85), "hot_plate_temp_initial_layer": L(85),
            "textured_plate_temp": L(85), "textured_plate_temp_initial_layer": L(85),
            "chamber_temperature": L(35),
            "filament_max_volumetric_speed": L(flow),
            "slow_down_layer_time": L(9),
            "slow_down_min_speed": L(15),
            "fan_max_speed": L(60), "fan_min_speed": L(30),
            "overhang_fan_speed": L(60),
            "close_fan_the_first_x_layers": L(3),
            "full_fan_speed_layer": L(5),
            "fan_cooling_layer_time": L(25),
            "filament_vendor": ["Sunlu"], "filament_type": ["PETG"],
            "filament_cost": L(15), "filament_density": L(1.23),
            # Orca does not emit either of these for a Prusa host. M572 is
            # pressure advance, M142 the heatbreak target. Losing them would
            # change print quality with nothing in the diff to explain it.
            "filament_start_gcode": [
                f"M572 S{'0.032' if noz == 'HF0.6' else '0.045'} ; pressure advance\n"
                "M142 S36 ; heatbreak target"
            ],
        })
        # Calibration pair: no cooling throttle, flow deliberately over the
        # ceiling so the tower measures the nozzle instead of the cooling logic.
        for t in (255, 270):
            out.append({
                "type": "filament", "from": "User",
                "name": f"CAL PETG {t} @CORE One L {noz} - 3D3D",
                "filament_settings_id": [f"CAL PETG {t} @CORE One L {noz} - 3D3D"],
                "inherits": f"Prusa Generic PETG @CORE One {noz[:2]} {noz[2:]}",
                "compatible_printers": [spec["machine"]],
                "nozzle_temperature": L(t),
                "nozzle_temperature_initial_layer": L(t),
                "filament_max_volumetric_speed": L(flow + 10),
                "slow_down_layer_time": L(0),
                "filament_type": ["PETG"],
            })
    return out


def build_machines():
    """Orca's Core One L profiles copy the non-L CORE One's 350 mm/s feedrate.

    Prusa's own current bundle says 500 for the L, and Prusa publish 500 as the
    machine's travel speed. Because `machine_limits_usage` is `emit_to_gcode`,
    Orca emits M203 X350 Y350 and the printer OBEYS it, so shipping Orca's
    number as-is would make this machine slower than it is on PrusaSlicer.
    """
    out = []
    for noz, spec in NOZZLES.items():
        out.append({
            "type": "machine", "from": "User",
            "name": f"{spec['machine']} - 3D3D",
            "printer_settings_id": f"{spec['machine']} - 3D3D",
            "inherits": spec["machine"],
            "machine_max_speed_x": ["500", "160"],
            "machine_max_speed_y": ["500", "160"],
            "machine_max_speed_z": ["15", "15"],
            "machine_max_acceleration_travel": ["6000", "2500"],
            "machine_max_acceleration_extruding": ["7000", "2500"],
        })
    return out


def orca_key_universe():
    uni = collections.defaultdict(set)
    for kind in ("process", "filament", "machine"):
        for f in glob.glob(f"{ORCA_SYS}/*/{kind}/*.json"):
            try:
                uni[kind].update(json.load(open(f)).keys())
            except Exception:
                pass
    return uni


def parent_exists(kind, name):
    for vendor in ("Prusa", "OrcaFilamentLibrary"):
        if os.path.exists(os.path.join(ORCA_SYS, vendor, kind, name + ".json")):
            return True
    return False


def main():
    presets = build_machines() + build_processes() + build_filaments()
    uni = orca_key_universe()
    bad = 0
    for p in presets:
        kind = p["type"]
        for k in p:
            if k in ("type", "from", "name", "inherits"):
                continue
            if k not in uni[kind]:
                print(f"  ! {p['name']}: '{k}' unknown to Orca {kind} profiles")
                bad += 1
        if not parent_exists(kind, p["inherits"]):
            print(f"  ! {p['name']}: parent '{p['inherits']}' does not exist")
            bad += 1
    if bad:
        print(f"\n{bad} problem(s). Nothing written.")
        return 1

    counts = collections.Counter()
    for kind in ("process", "filament", "machine"):
        d = os.path.join(HERE, kind)
        os.makedirs(d, exist_ok=True)
        for old in glob.glob(os.path.join(d, "*.json")):
            os.remove(old)
    for p in presets:
        out = dict(p, version=VERSION, is_custom_defined="0")
        with open(os.path.join(HERE, p["type"], p["name"] + ".json"), "w") as fh:
            json.dump(out, fh, indent=4, ensure_ascii=False)
            fh.write("\n")
        counts[p["type"]] += 1

    for k in ("machine", "process", "filament"):
        print(f"  {k:9} {counts[k]:>3}")
    print(f"\n{sum(counts.values())} presets, every key and parent validated "
          f"against Orca {VERSION}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
