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
| `profiles/` | 54 generated Orca presets: 2 machines, 28 processes, 24 filaments |
| `profiles/build-profiles.py` | the generator. Every speed is derived, not typed |
| `profiles-tuned/` | hand-tuned presets for one real filament, kept out of the generator (it wipes `profiles/`) |
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

## Tuned: Overture TPU 95A on the HF 0.4

`Overture TPU 95A @CORE One L HF0.4 - 3D3D` (filament) and `0.10mm TPU Detail @CORE One L HF0.4 - 3D3D`
(process), made 2026-09-30 after OrcaSlicer's stock `Overture TPU @System` left gaps between lines and
strings on travel. That stock preset is a Bambu one: 220 C, 8 mm3/s, flow 0.95, 0.4 mm retraction.

| | stock Overture | tuned |
|---|---|---|
| nozzle | 220 C | 235 C |
| flow ratio | 0.95 | 1.05 |
| max volumetric speed | 8 mm3/s | 4 mm3/s |
| retraction | 0.4 mm | 1.5 mm @ 35 mm/s, wipe on, no z-hop |
| fan | 100 % | 30-60 % |

The process: 0.10 mm layers, 4 walls (Arachne, 0.40 mm outer line), 20 % gyroid, outer wall 20 mm/s at
800 mm/s2, first layer 20 mm/s, seam at the back, no brim, supports or ironing. Built for fine detail cut
into a wall. First print pending; tune flow 1.02-1.08, 230-245 C, 3-5 mm3/s, retraction 1-2.5 mm from here.
Dry the spool first.

## Not included

Printer credentials. They live in a local `printer.env` (gitignored) and are
injected only into the installed copy, never committed.
