#!/usr/bin/env python3
"""Flatten an OrcaSlicer preset's `inherits` chain into one standalone config.

Why this exists: Orca's CLI refuses presets that still carry `inherits`, and it
was previously written off here as "returns -17, not worth chasing". The -17 is
CLI_PROCESS_NOT_COMPATIBLE and the cause is in src/OrcaSlicer.cpp: the compat
check compares the process preset's `compatible_printers` against the MACHINE's
*system* name, which Orca only sets when the machine config says `from: system`.
Strip `inherits` without that and the system name is empty, so nothing matches.

So: flatten everything, mark the machine `from: system`, and set every process
and filament `compatible_printers` to the machine's exact name. Then --slice
works and print-time estimates can actually be measured instead of guessed.
"""
import json, os, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
USER = os.path.expanduser("~/.config/OrcaSlicer/user/default")
MACHINE = os.environ.get("ORCA_MACHINE", "Prusa CORE One L HF 0.4 nozzle - 3D3D")

def resources():
    """Orca ships its vendor profiles inside the AppImage; extract them once."""
    out = os.path.join(HERE, "orca-resources")
    if os.path.isdir(os.path.join(out, "resources/profiles")):
        return os.path.join(out, "resources/profiles")
    app = sorted(glob.glob(os.path.expanduser(
        "~/Applications/OrcaSlicer/OrcaSlicer_Linux_AppImage_*.AppImage")))[-1]
    os.makedirs(out, exist_ok=True)
    os.system(f'cd "{out}" && "{app}" --appimage-extract "resources/profiles/*" '
              f'>/dev/null 2>&1 && mv squashfs-root/resources . && rm -rf squashfs-root')
    return os.path.join(out, "resources/profiles")

ROOT = resources()
INDEX = {}
for pat in ("*/*/*.json", "*/*.json"):
    for p in glob.glob(os.path.join(ROOT, pat)):
        INDEX.setdefault(os.path.splitext(os.path.basename(p))[0], []).append(p)
for p in glob.glob(os.path.join(USER, "*", "*.json")):
    INDEX.setdefault(os.path.splitext(os.path.basename(p))[0], []).append(p)

def load(name, kind):
    cands = [p for p in INDEX.get(name, []) if f"/{kind}/" in p]
    if not cands:
        raise SystemExit(f"preset not found: {kind}/{name}")
    cands.sort(key=lambda p: (0 if p.startswith(USER) else 1))
    return json.load(open(cands[0]))

def flatten(name, kind):
    cfg = load(name, kind)
    parent = cfg.get("inherits")
    if not parent:
        return cfg
    base = flatten(parent, kind)
    base.update({k: v for k, v in cfg.items() if k != "inherits"})
    return base

def emit(kind, name, out, overrides=None):
    d = flatten(name, kind)
    for k in ("inherits", "instantiation", "setting_id", "filament_id",
              "compatible_printers_condition", "compatible_prints_condition",
              "compatible_prints"):
        d.pop(k, None)
    d["is_custom_defined"] = "0"
    d["version"] = "2.4.2.0"
    if kind == "machine":
        # from:system is what makes Orca populate new_printer_system_name, which
        # is the value the compatibility check actually compares against.
        d["from"] = "system"
        d["printer_settings_id"] = d["name"]
    else:
        d["from"] = "User"
        d["printer_technology"] = "FFF"
        d["compatible_printers"] = [MACHINE]
    if overrides:
        d.update(overrides)
    json.dump(d, open(out, "w"), indent=2, sort_keys=True)
    return d

if __name__ == "__main__":
    kind, name, out = sys.argv[1], sys.argv[2], sys.argv[3]
    ov = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    d = emit(kind, name, out, ov)
    print(f"{out}  ({len(d)} keys)")
