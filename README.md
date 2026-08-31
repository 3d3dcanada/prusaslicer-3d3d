# prusaslicer-3d3d

3D3D's OrcaSlicer profile set for the **Prusa CORE One L**, derived from Prusa's
own machine limits and E3D's published flow figures rather than copied by hand.

Built when 3D3D moved the CORE One L off PrusaSlicer onto OrcaSlicer. The point
of the move: the single setting that had been clamping high-speed infill
(`filament_infill_max_speed`) does not exist in Orca, so speeds are governed by
real volumetric flow instead of an invisible cap.

## What is here

| | |
|---|---|
| `profiles/` | 41 generated Orca presets: 2 machines, 21 processes, 18 filaments |
| `profiles/build-profiles.py` | the generator. Every speed is derived, not typed |
| `delta.py` | resolves a PrusaSlicer preset against its vendor parent and prints only the real overrides |
| `install-profiles.sh` | installs into `~/.config/OrcaSlicer` and injects the printer host + credentials |
| `SPEED.md` | the reasoning: three clamps, and the flow arithmetic that replaces them |

## The idea in one line

```
speed (mm/s) = volumetric flow (mm3/s) / (layer height x extrusion width)
```

Chase mm3/s. The mm/s figure is an output, not a setting. Two nozzles: the 0.6 is
the High Flow ObXidian (36 mm3/s on PETG), the 0.4 is plain high flow (25).

## Building

```
python3 profiles/build-profiles.py   # regenerate, validates every key + parent
./install-profiles.sh                 # install (close OrcaSlicer first)
```

`build-profiles.py` refuses to write unless every key exists in OrcaSlicer's own
profile key universe and every inherited parent resolves.

## Not included

Printer credentials. They live in a local `printer.env` (gitignored) and are
injected only into the installed copy, never committed.
