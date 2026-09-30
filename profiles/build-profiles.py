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
    },
    "HF0.6": {
        "machine": "Prusa CORE One L HF 0.6 nozzle",
        "width": 0.68,
        "hardened": True,       # ObXidian: CF and GF are fine
    },
}

# ------------------------------------------------------------- the materials
#
# flow: (mm3/s, temperature the figure is quoted at) per nozzle. `src` says
# where each pair came from, and nothing here is invented:
#
#   E3D      E3D's published table for the High Flow Nextruder nozzles, read
#            2026-08-31. Brass and ObXidian are within 1 mm3/s at 0.4.
#   DERIVED  no published figure exists for this material, so it is a stated
#            fraction of the base polymer's number. The fraction itself comes
#            from Prusa's own bundle: their PETG-CF runs 12 where plain PETG
#            runs 20 on the same 0.4 HF nozzle, so a filled or softened variant
#            is taken at 60% of its base. Every DERIVED figure is a starting
#            point for a flow tower, NOT a measured ceiling.
#
# abrasive: filled with carbon or glass. The 0.4 is plain brass and one spool of
# this through it ruins the nozzle, so abrasive materials are built for the 0.6
# ObXidian ONLY and the generator refuses to emit them for the 0.4.

FILLED = 0.60   # the Prusa PETG-CF / PETG ratio, applied to filled and softened grades

MATERIALS = {
    "PLA":      dict(flow={"HF0.4": (20, 220), "HF0.6": (30, 220)}, src="E3D",
                     parent="Prusa Generic PLA @CORE One HF {n}", abrasive=False),
    "PLA Silk": dict(flow={"HF0.4": (12, 225), "HF0.6": (18, 225)}, src="DERIVED 60% of PLA",
                     parent={"HF0.4": "Prusa Generic PLA Silk @CORE One",
                             "HF0.6": "Prusa Generic PLA Silk @CORE One 0.6"}, abrasive=False),
    "PETG":     dict(flow={"HF0.4": (25, 240), "HF0.6": (36, 240)}, src="E3D",
                     parent="Prusa Generic PETG @CORE One HF {n}", abrasive=False),
    "PETG CF":  dict(flow={"HF0.6": (21, 250)}, src="DERIVED 60% of PETG",
                     parent={"HF0.6": "Generic PETG-CF @System"}, abrasive=True),
    "ASA":      dict(flow={"HF0.4": (27, 260), "HF0.6": (32, 260)}, src="E3D",
                     parent="Prusa Generic ASA @CORE One HF {n}", abrasive=False),
    "ASA GF":   dict(flow={"HF0.6": (19, 260)}, src="DERIVED 60% of ASA",
                     parent={"HF0.6": "Prusa Generic ASA @CORE One HF 0.6"}, abrasive=True),
    "ABS":      dict(flow={"HF0.4": (25, 255), "HF0.6": (32, 255)}, src="E3D",
                     parent="Prusa Generic ABS @CORE One HF {n}", abrasive=False),
    "PC":       dict(flow={"HF0.4": (24, 275), "HF0.6": (30, 275)}, src="E3D",
                     parent={"HF0.4": "Prusament PC Blend @CORE One HF 0.4",
                             "HF0.6": "Prusament PC Blend @CORE One HF 0.6"}, abrasive=False),
    "TPU 95A":  dict(flow={"HF0.4": (8, 240), "HF0.6": (12, 240)}, src="E3D",
                     parent={"HF0.4": "Prusa Generic TPU @CORE One",
                             "HF0.6": "Prusa Generic TPU @CORE One 0.6"},
                     abrasive=False, flexible=True),
    "TPE 85":   dict(flow={"HF0.4": (5, 230), "HF0.6": (7, 230)}, src="DERIVED 60% of TPU 95A",
                     parent={"HF0.4": "Prusa Generic TPU @CORE One",
                             "HF0.6": "Prusa Generic TPU @CORE One 0.6"},
                     abrasive=False, flexible=True),
}


def parent_for(mat, noz):
    spec = MATERIALS[mat]["parent"]
    if isinstance(spec, dict):
        return spec.get(noz)
    return spec.format(n=noz[2:])


def materials_for(noz):
    """Every material this nozzle may print. Abrasives are 0.6 ObXidian only."""
    hardened = NOZZLES[noz]["hardened"]
    out = []
    for mat, spec in MATERIALS.items():
        if noz not in spec["flow"]:
            continue
        if spec["abrasive"] and not hardened:
            continue          # brass nozzle: never
        if parent_for(mat, noz) is None:
            continue
        out.append(mat)
    return out

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
        flow_petg = MATERIALS["PETG"]["flow"][noz][0]
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

                    # --- bridging -------------------------------------------
                    # A bridge is unsupported extrusion, so it is governed by
                    # cooling, not by flow. bridge_speed above is already
                    # deliberately the slowest role. thick_bridges off makes the
                    # bridge follow the real surface instead of being lifted a
                    # whole layer; Prusa ship it off on the CORE One too.
                    "thick_bridges": "0",
                    "bridge_flow": "1",
                    "internal_bridge_flow": "1",
                    "bridge_density": "100%",
                    "enable_extra_bridge_layer": "1",
                    "bridge_acceleration": str(clamp(accel * 0.35, MAX_ACCEL_PRINT)),

                    # --- overhangs ------------------------------------------
                    # Four bands from barely overhanging to nearly unsupported.
                    # These are fractions of the outer wall speed, which is the
                    # role an overhang actually is.
                    "detect_overhang_wall": "1",
                    "enable_overhang_speed": "1",
                    "overhang_1_4_speed": str(clamp(base * f_outer * 0.85, 1000)),
                    "overhang_2_4_speed": str(clamp(base * f_outer * 0.55, 1000)),
                    "overhang_3_4_speed": str(clamp(base * f_outer * 0.35, 1000)),
                    "overhang_4_4_speed": str(clamp(base * 0.22, 120)),
                    "extra_perimeters_on_overhangs": "1",

                    # --- ironing --------------------------------------------
                    # OFF here, deliberately. Measured on 3D3D-CALIPER-1-BACK at
                    # 0.20mm MAX on the 0.6: ironing took the part from 22m18s to
                    # 56m06s for 0.10 g more filament. It more than doubles the
                    # clock because a whole extra pass crawls over every top
                    # surface. It belongs on a tier you choose, not on every
                    # profile, so it lives in the IRON twin below.
                    "ironing_type": "no ironing",
                })

                # An IRON twin, on the QUALITY tier only. Nobody irons a part
                # they are running at MAX, and the measurement above is why.
                # Flow is under Orca's common 10-15% and the speed is fixed
                # rather than scaled with the tier, because ironing is the one
                # setting that ruins a top surface when it is too hot or too
                # fast. `top` is a value that appears in a shipped Orca profile,
                # so it is known to parse.
                # NOT for flexibles: the nozzle drags and balls the surface.
                if tier == "QUALITY":
                    iron = dict(out[-1])
                    iron["name"] = iron["print_settings_id"] = (
                        f"{layer}mm IRON @CORE One L {noz} - 3D3D")
                    iron.update({
                        "ironing_type": "top",
                        "ironing_flow": "10%",
                        "ironing_speed": "20",
                        "ironing_spacing": "0.1",
                        "ironing_pattern": "zig-zag",
                    })
                    out.append(iron)
    return out


def build_filaments():
    out = []
    for noz, spec in NOZZLES.items():
        for mat in materials_for(noz):
            m = MATERIALS[mat]
            flow, at_temp = m["flow"][noz]
            parent = parent_for(mat, noz)
            note = (f"3D3D. Flow {flow} mm3/s quoted at {at_temp} C, source: {m['src']}."
                    + (" ABRASIVE: 0.6 ObXidian ONLY, never the 0.4 brass." if m["abrasive"] else "")
                    + (" DERIVED, not measured: run a flow tower before trusting it."
                       if m["src"].startswith("DERIVED") else ""))
            f = {
                "type": "filament", "from": "User",
                "name": f"{mat} MAXFLOW @CORE One L {noz} - 3D3D",
                "filament_settings_id": [f"{mat} MAXFLOW @CORE One L {noz} - 3D3D"],
                "inherits": parent,
                "compatible_printers": [spec["machine"]],
                # The published or derived ceiling for this nozzle and material.
                # A number to BEAT with a flow calibration, not to trust.
                "filament_max_volumetric_speed": L(flow),
                "filament_notes": [note],
            }
            if m["abrasive"]:
                # Orca has no filament_abrasive key; required_nozzle_HRC is its
                # abrasion guard. The ObXidian is a hardened steel nozzle.
                f["required_nozzle_HRC"] = L(60)
            if m.get("flexible"):
                # Ironing is a PROCESS setting in Orca, not a filament one, so it
                # cannot be switched off from here. Pair these with the FLEX
                # processes below, which have it off.
                note += " Flexible: do not use an IRON process, the nozzle balls the surface."
                f["filament_notes"] = [note]
            out.append(f)

    # Sunlu PETG is the spool he actually runs, at his own measured 268 C.
    for noz, spec in NOZZLES.items():
        flow = MATERIALS["PETG"]["flow"][noz][0]
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


def _parent_notes(machine_name):
    """The system profile's printer_notes, walking `inherits` until they appear."""
    name = machine_name
    for _ in range(10):
        for vendor in ("Prusa", "OrcaFilamentLibrary"):
            path = os.path.join(ORCA_SYS, vendor, "machine", name + ".json")
            if os.path.exists(path):
                d = json.load(open(path))
                n = d.get("printer_notes")
                if n:
                    return n if isinstance(n, str) else n[0]
                name = d.get("inherits")
                break
        else:
            break
        if not name:
            break
    raise SystemExit(f"could not find printer_notes for {machine_name}")


def build_machines():
    """Orca's Core One L profiles copy the non-L CORE One's 350 mm/s feedrate.

    Prusa's own current bundle says 500 for the L, and Prusa publish 500 as the
    machine's travel speed. Because `machine_limits_usage` is `emit_to_gcode`,
    Orca emits M203 X350 Y350 and the printer OBEYS it, so shipping Orca's
    number as-is would make this machine slower than it is on PrusaSlicer.
    """
    out = []
    for noz, spec in NOZZLES.items():
        m = {
            "type": "machine", "from": "User",
            "name": f"{spec['machine']} - 3D3D",
            "printer_settings_id": f"{spec['machine']} - 3D3D",
            "inherits": spec["machine"],
            "machine_max_speed_x": ["500", "160"],
            "machine_max_speed_y": ["500", "160"],
            "machine_max_speed_z": ["15", "15"],
            "machine_max_acceleration_travel": ["6000", "2500"],
            "machine_max_acceleration_extruding": ["7000", "2500"],
        }
        if spec["hardened"]:
            # Orca's M862.1 A-flag reads the PRINTER's notes, not the filament:
            #   M862.1 P[nozzle_diameter] A{(printer_notes=~/.*ABRASIVE_NOZZLE.*/ ? 1 : 0)} ...
            # Orca's own Core One L profile never sets ABRASIVE_NOZZLE, and the
            # 0.6 profile inherits the 0.4's notes, so the printer is told "no
            # abrasive nozzle fitted" while the hardened ObXidian is on. The
            # keywords are also used in compatible-printer conditions, so they
            # are appended to the inherited block, never replaced.
            m["printer_notes"] = _parent_notes(spec["machine"]) + "\nABRASIVE_NOZZLE"
        out.append(m)
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
