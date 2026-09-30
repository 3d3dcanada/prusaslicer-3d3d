#!/usr/bin/env python3
"""Generate the self-contained 3D3D vendor bundle for PrusaSlicer 3.

Why self-contained: a bundle that declares vendor `PrusaResearch` collides with
Prusa's own repository and the app keeps theirs, so the 3D3D presets never
appear. Declaring vendor `3D3D` works, but then nothing can inherit Prusa's
starred base nodes across vendors. So every preset here carries its FULL
resolved value set, produced by resolve.py walking Prusa's own YAML trees for
the exact (nozzle, high-flow) hardware. Nothing is copied by hand and nothing is
invented.

The result mirrors how the Orca setup is already organised: two machines,
`CORE One L 0.4 HF (3D3D)` and `CORE One L 0.6 HF (3D3D)`, each with its own
process and filament lists.

PROVENANCE RULE: a flow cap is only raised above Prusa's own value when there is
a published figure or a measured one to raise it to. Every such value carries a
`src` tag in FLOW below. Everything else keeps Prusa's number.
"""
import base64, hashlib, json, os, sys, yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resolve import resolve_file, facts_for

HOME = os.path.expanduser("~")
BASE = f"{HOME}/.cache/ps3-repo/full/PrusaResearch/1.0.11"
ORCA = f"{HOME}/.config/OrcaSlicer/user/default"
OUT  = f"{HOME}/Desktop/3D3D-STL/_slicer/prusaslicer3/bundle/generated"

VENDOR_ID   = "3D3D"
VENDOR_NAME = "3D3D Canada"
PRINTER_ID  = "COREONEL3D3D"

# ---------------------------------------------------------------- materials
# base   : the Prusa filament YAML the values are resolved from
# abras  : abrasive, so 0.6 ObXidian ONLY. The 0.4 is plain brass and must never
#          see one. The emitted M862.1 A-flag makes the printer enforce it too.
# nozzles: which nozzles this material is built for
MATERIALS = {
    "PLA":       dict(base="preset-filament-PLA-Prusament-PLA.yaml",           abras=False, nozzles=(0.4, 0.6)),
    "PLA Silk":  dict(base="preset-filament-PLA-Generic-PLA-SILK.yaml",        abras=False, nozzles=(0.4, 0.6)),
    "PETG":      dict(base="preset-filament-PETG-Sunlu-PETG.yaml",             abras=False, nozzles=(0.4, 0.6)),
    "PETG CF":   dict(base="preset-filament-PETG-Prusament-PETG-Carbon-Fiber.yaml", abras=True,  nozzles=(0.6,)),
    "ASA":       dict(base="preset-filament-ASA-Prusament-ASA.yaml",           abras=False, nozzles=(0.4, 0.6)),
    "ASA GF":    dict(base="preset-filament-ASA-Prusament-ASA.yaml",           abras=True,  nozzles=(0.6,),
                      note="no glass-fibre ASA exists in Prusa's bundle; derived from Prusament ASA "
                           "with the abrasive flag set and the flow left at Prusa's ASA value. "
                           "UNPROVEN: needs a flow tower before it is trusted."),
    "TPU 95A":   dict(base="preset-filament-FLEX-Prusament-TPU-95A.yaml",      abras=False, nozzles=(0.4, 0.6)),
    "TPE 85":    dict(base="preset-filament-FLEX-Forward-AM-Ultrafuse-TPU-85A.yaml", abras=False, nozzles=(0.4, 0.6)),
}

# Flow caps we are willing to RAISE Prusa's value to, with the source.
# speed = flow / (layer x width): the mm/s figure is an output, not a setting.
FLOW = {
    ("PLA",  0.4): (20, "E3D published, HF 0.4 brass"),
    ("PLA",  0.6): (30, "E3D published, HF 0.6 ObXidian"),
    ("PETG", 0.4): (25, "E3D published + Ken's Orca value, both 25"),
    ("PETG", 0.6): (36, "E3D published, HF 0.6 ObXidian; Orca ships 31, five short"),
    ("ASA",  0.4): (27, "E3D published, HF 0.4 brass"),
    ("ASA",  0.6): (32, "E3D published, HF 0.6 ObXidian"),
}

# Ironing and bridging, applied to every 3D3D process preset.
# Prusa already ship thick_bridges 0 and enable_dynamic_overhang_speeds 1; the
# ironing block is ours, and it is deliberately conservative because ironing is
# the one setting that ruins a top surface when it is too hot or too fast.
FINISH = {
    "ironing": 1,
    "ironing_type": "top",          # top surfaces only, not every solid layer
    "ironing_flowrate": "12%",      # under Prusa's 15% default: PETG smears above that
    "ironing_spacing": 0.1,
    "ironing_speed": 20,
    "thick_bridges": 0,             # thin bridges follow the real surface
    "bridge_flow_ratio": 1.0,
    "enable_dynamic_overhang_speeds": 1,
    "extra_perimeters_on_overhangs": 1,
    "overhangs": 1,
    "gcode_comments": 0,
}
# Ironing is wrong for flexibles: the nozzle drags and balls the surface.
NO_IRON = {"TPU 95A", "TPE 85"}

ORCA_PROC = {   # Orca key -> PrusaSlicer key, for Ken's tuned processes
    "outer_wall_speed": "external_perimeter_speed", "inner_wall_speed": "perimeter_speed",
    "sparse_infill_speed": "infill_speed", "internal_solid_infill_speed": "solid_infill_speed",
    "top_surface_speed": "top_solid_infill_speed", "gap_infill_speed": "gap_fill_speed",
    "initial_layer_speed": "first_layer_speed",
    "initial_layer_infill_speed": "first_layer_solid_infill_speed",
    "small_perimeter_speed": "small_perimeter_speed", "bridge_speed": "bridge_speed",
    "support_speed": "support_material_speed", "travel_speed": "travel_speed",
    "travel_speed_z": "travel_speed_z", "default_acceleration": "default_acceleration",
    "outer_wall_acceleration": "external_perimeter_acceleration",
    "inner_wall_acceleration": "perimeter_acceleration",
    "sparse_infill_acceleration": "infill_acceleration",
    "internal_solid_infill_acceleration": "solid_infill_acceleration",
    "top_surface_acceleration": "top_solid_infill_acceleration",
    "initial_layer_acceleration": "first_layer_acceleration",
    "travel_acceleration": "travel_acceleration",
}
DROP_FROM_PRINT = {"default_material", "compatible_printers", "compatible_prints"}


def pid(*parts):
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()[:16]
    return base64.b64encode(h).decode().rstrip("=")


def orca_process(nozzle):
    """Ken's tuned Orca process presets for this nozzle, as PS3 key/value."""
    import glob
    tag = f"HF{nozzle:.1f}"
    out = {}
    for p in sorted(glob.glob(f"{ORCA}/process/*CORE One L {tag}*.json")):
        src = json.load(open(p))
        vals = {}
        for k, v in src.items():
            if k in ORCA_PROC:
                try:
                    vals[ORCA_PROC[k]] = int(v) if float(v) == int(float(v)) else float(v)
                except (TypeError, ValueError):
                    pass
        if src.get("enable_arc_fitting") in (1, "1", True, "true"):
            vals["arc_fitting"] = "emit_center"
        out[os.path.basename(p)[:-5]] = vals
    return out


def build_print_presets():
    """One 3D3D process per (nozzle, Prusa profile), Prusa's resolved values as
    the floor, Ken's Orca tuning on top where the layer height matches, then the
    ironing and bridging block."""
    docs, made = [], []
    for nozzle in (0.4, 0.6):
        facts = facts_for(nozzle, True)
        prusa = resolve_file(f"{BASE}/preset-print-coreonel.yaml", facts)
        ken = orca_process(nozzle)
        leaves = []
        for pname, pvals in sorted(prusa.items()):
            if f"{nozzle:.1f}HF" not in pname.replace(" ", "") and not pname.endswith(f"{nozzle}HF"):
                continue
            vals = {k: v for k, v in pvals.items() if k not in DROP_FROM_PRINT}
            lh = vals.get("layer_height")
            # Ken tuned by layer height and intent; match on both when we can
            for kn, kv in ken.items():
                if lh is not None and kn.startswith(f"{lh:.2f}mm"):
                    intent = pname.split("@")[0].strip().split()[-1].upper()
                    if intent in kn.upper() or ("SPEED" in intent and "MAX" in kn.upper()):
                        vals.update(kv)
                        break
            vals.update(FINISH)
            nice = f"{pname} - 3D3D"
            leaves.append({"name": nice, "id": pid("print", nice), "values": vals})
            made.append(nice)
        docs.append({
            "kind": "print",
            "variants": [{
                "condition": f'printer.model == "{PRINTER_ID}"',
                "id": pid("print-root", PRINTER_ID, nozzle),
                "variants": [{
                    "condition": f"tool.nozzle_diameter == {nozzle}",
                    "id": pid("print-nz", PRINTER_ID, nozzle),
                    "variants": leaves,
                }],
            }],
        })
    return docs, made


def build_filament_presets():
    docs, made, notes = [], [], []
    for mat, spec in MATERIALS.items():
        for nozzle in spec["nozzles"]:
            facts = facts_for(nozzle, True)
            res = resolve_file(f"{BASE}/{spec['base']}", facts)
            if not res:
                notes.append(f"SKIP {mat} {nozzle}: no profile resolved from {spec['base']}")
                continue
            # the base file may hold several brands; take the one whose name has no @, else the first
            key = sorted(res, key=lambda n: (0 if "@" not in n else 1, n))[0]
            vals = dict(res[key])
            vals["filament_abrasive"] = 1 if spec["abras"] else 0
            vals["filament_infill_max_speed"] = 0      # the clamp Orca does not have
            cur = vals.get("filament_max_volumetric_speed")
            flow = FLOW.get((mat, nozzle))

            # Two tiers, the same shape as the AD5M TPU ladder: the FILAMENT is
            # the knob, the process speeds are pure ceilings, so the volumetric
            # cap always governs. The default tier keeps Prusa's per-brand value,
            # which is proven. MAX carries the published nozzle ceiling and is
            # NOT measured on our spools, so it is named so nobody reaches for it
            # by accident.
            tiers = [("", vals, f"Prusa's own value for this brand ({cur})")]
            if flow and cur is not None and flow[0] > float(cur):
                mx = dict(vals)
                mx["filament_max_volumetric_speed"] = flow[0]
                tiers.append((" MAX", mx, f"{flow[0]} from {flow[1]} - UNPROVEN, run a flow tower"))
                notes.append(f"{mat} {nozzle}: default {cur}, MAX tier {flow[0]} ({flow[1]})")
            elif flow and cur is None:
                vals["filament_max_volumetric_speed"] = flow[0]
                notes.append(f"{mat} {nozzle}: Prusa had no cap, set {flow[0]} ({flow[1]})")

            if spec.get("note"):
                notes.append(f"{mat}: {spec['note']}")
            for suffix, tv, why in tiers:
                nice = f"{mat}{suffix} @COREONEL {nozzle}HF - 3D3D"
                tv = dict(tv)
                tv["filament_notes"] = f"3D3D. Flow cap: {why}"
                made.append(nice)
                docs.append({
                    "kind": "filament",
                    "variants": [{
                        "condition": f'printer.model == "{PRINTER_ID}" and tool.nozzle_diameter == {nozzle}',
                        "id": pid("fil-root", nice),
                        "variants": [{"name": nice, "id": pid("fil", nice), "values": tv}],
                    }],
                })
    return docs, made, notes


def build_printer_preset():
    vals = dict(resolve_file(f"{BASE}/preset-printer-coreonel.yaml", facts_for(0.4, True))["Prusa CORE One L"])
    return {
        "kind": "printer",
        "variants": [{
            "condition": f'printer.model == "{PRINTER_ID}"',
            "id": pid("printer", PRINTER_ID),
            "values": vals,
        }],
    }


def build_vendor():
    src = list(yaml.safe_load_all(open(f"{BASE}/vendor.yaml")))
    feat = next(d for d in src if d.get("kind") == "vendor")["features"]
    tools = [d for d in src if d.get("kind") == "tool" and d.get("id") in ("0.4HF", "0.6HF")]
    sheet = next(d for d in src if d.get("kind") == "sheet" and d.get("id") == "satin")
    docs = [
        {"kind": "vendor", "id": VENDOR_ID, "name": VENDOR_NAME,
         "version": "1.0.0", "features": feat},
        {"kind": "printer", "technology": "FFF", "name": "CORE One L (3D3D)",
         "id": PRINTER_ID, "model": {"base_model": "COREONE", "model": PRINTER_ID},
         "tool_count": 1,
         "features": {"input_shaper": {"default": True}},
         "visual": {"bed_model": "coreonel_bed.stl", "bed_texture": "coreonel.svg",
                    "thumbnail": "COREONEL_thumbnail.svg"}},
    ]
    for t in tools:
        t = dict(t)
        t.pop("condition", None)      # our printer offers both, no gating needed
        docs.append(t)
    docs.append(sheet)
    for nozzle, tid in ((0.4, "0.4HF"), (0.6, "0.6HF")):
        docs.append({"kind": "printer_config",
                     "id": f"c1l-3d3d-{tid.replace('.','')}",
                     "name": f"CORE One L {tid[:3]} HF (3D3D)",
                     "printer": PRINTER_ID,
                     "legacy_printer_model": [PRINTER_ID],
                     "tools": [{"tool": tid}],
                     "sheet": "satin"})
    return docs


def dump(path, docs):
    with open(path, "w") as f:
        yaml.safe_dump_all(docs, f, sort_keys=False, default_flow_style=False, width=10000)


if __name__ == "__main__":
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            os.remove(f"{OUT}/{f}")
    os.makedirs(OUT, exist_ok=True)
    dump(f"{OUT}/vendor.yaml", build_vendor())
    dump(f"{OUT}/preset-printer-3d3d.yaml", [build_printer_preset()])
    pd, pm = build_print_presets()
    dump(f"{OUT}/preset-print-3d3d.yaml", pd)
    fd, fm, notes = build_filament_presets()
    dump(f"{OUT}/preset-filament-3d3d.yaml", fd)
    print(f"printer presets : 1")
    print(f"process presets : {len(pm)}")
    for n in pm:
        print("   ", n)
    print(f"filament presets: {len(fm)}")
    for n in fm:
        print("   ", n)
    print("notes:")
    for n in notes:
        print("   -", n)
