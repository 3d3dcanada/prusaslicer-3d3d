#!/usr/bin/env python3
"""Repair OrcaSlicer's shipped Prusa CORE One L machine profiles.

Two faults, both in Orca's own Prusa vendor bundle (checked against version 02.04.00.03):

1. Five of the eight CORE One L nozzle profiles set `default_print_profile` to the
   **non-L** CORE One process. Those processes carry
   `compatible_printers_condition = printer_notes=~/.*PRINTER_MODEL_COREONE[^_a-zA-Z0-9].*/`,
   and this printer's notes read `PRINTER_MODEL_COREONE_L`. The character after COREONE is
   `_`, which the class explicitly excludes, so the condition can NEVER be true. The printer
   ships pointing at a default process that is unusable with it.

2. `Prusa CORE One L HF 0.4 nozzle.json` stores `printer_notes` as a one-element LIST where
   every other CORE One L machine stores a plain string. printer_notes is a ConfigOptionString.
   The HF 0.6 inherits from this file, so the whole HF chain carries the odd shape.

Idempotent. Only rewrites a file it actually changes.
"""
import json, os, sys

D = os.path.expanduser("~/.config/OrcaSlicer/system/Prusa/machine")
P = os.path.expanduser("~/.config/OrcaSlicer/system/Prusa/process")

# non-L default -> the L process that actually exists for that nozzle
FIX = {
    "Prusa CORE One L 0.5 nozzle.json":    "0.20mm SPEED @CORE One L 0.5",
    "Prusa CORE One L 0.6 nozzle.json":    "0.25mm SPEED @CORE One L 0.6",
    "Prusa CORE One L 0.8 nozzle.json":    "0.40mm QUALITY @CORE One L 0.8",
    "Prusa CORE One L HF 0.5 nozzle.json": "0.20mm SPEED @CORE One L HF 0.5",
    "Prusa CORE One L HF 0.6 nozzle.json": "0.32mm SPEED @CORE One L HF 0.6",
    "Prusa CORE One L HF 0.8 nozzle.json": "0.40mm STRUCTURAL @CORE One L HF 0.8",
}

changed = 0
for fname, target in FIX.items():
    path = os.path.join(D, fname)
    if not os.path.exists(path):
        print(f"SKIP  {fname}: not present"); continue
    if not os.path.exists(os.path.join(P, target + ".json")):
        sys.exit(f"ABORT {fname}: replacement process {target!r} does not exist")
    d = json.load(open(path))
    old = d.get("default_print_profile")
    if old == target:
        print(f"ok    {fname}: already {target}"); continue
    d["default_print_profile"] = target
    json.dump(d, open(path, "w"), indent=4)
    print(f"FIXED {fname}\n        {old}\n     -> {target}")
    changed += 1

# printer_notes shape
for fname in sorted(os.listdir(D)):
    if not fname.startswith("Prusa CORE One L"):
        continue
    path = os.path.join(D, fname)
    d = json.load(open(path))
    n = d.get("printer_notes")
    if isinstance(n, list):
        d["printer_notes"] = "\n".join(n)
        json.dump(d, open(path, "w"), indent=4)
        print(f"FIXED {fname}: printer_notes list -> string ({len(d['printer_notes'])} chars)")
        changed += 1

print(f"\n{changed} file(s) changed.")
