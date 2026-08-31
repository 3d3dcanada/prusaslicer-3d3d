# Pushing the Core One L to its actual limit

2026-08-31. Ken: *"We wanna push the absolute limit of the core one l."*

Three separate ceilings were holding it back, and only one of them was the one
he knew about.

## 1. The filament clamp (PrusaSlicer only)

`filament_infill_max_speed = 200` in the PETG high-flow parent. His profile asked
for 400 mm/s infill and got 200, with nothing in the UI to say so. **The key does
not exist in OrcaSlicer.** This is why the move is worth making.

## 2. The machine clamp (and Orca ships it wrong)

Prusa's own current vendor bundle, for the CORE One **L**:

```
machine_max_feedrate_x/y            500,160
machine_max_acceleration_extruding  7000,2500
machine_max_acceleration_travel     6000,2500
machine_limits_usage                emit_to_gcode
```

The non-L CORE One is **350**. Orca's `Prusa CORE One L HF *` profiles carry
**350**, copied from the smaller machine, while correctly carrying the L's
different travel acceleration. Prusa publish 500 mm/s as the L's travel speed, so
Orca is simply wrong here.

`emit_to_gcode` is what makes it bite: Orca writes `M203 X350 Y350` into the file
and **the printer obeys it**. Migrating on Orca's stock machine profile would have
capped the machine at 70 percent of its rated travel, so the move would have made
it slower. The generated machine presets override it back to 500.

His PrusaSlicer numbers were over the other two ceilings as well: `travel_speed
600` against a 500 limit, `infill_acceleration 8000` and `perimeter_acceleration
8000` against a 7000 extruding limit. All silently clamped.

## 3. The real one: flow, not speed

The ceiling that actually governs a print:

```
speed (mm/s) = volumetric flow (mm3/s) / (layer height x extrusion width)
```

E3D's published table for the High Flow Nextruder nozzles, read 2026-08-31:

| Nozzle | PLA @220 | PETG @240 | ASA @260 |
|---|---|---|---|
| **HF 0.4** (plain high flow) | 20 | 25 | 27 |
| **HF 0.6** (ObXidian) | 30 | **36** | 32 |

Orca ships **31** for PETG on the HF 0.6, five short of E3D's own figure, and 34
for ASA, two over it. Both are corrected in the generated filaments.

**So `infill_speed = 400` on the 0.6 at 0.32 mm was never real.** At 0.32 x 0.68
that asks for 87 mm3/s, roughly two and a half times what the nozzle can melt.
The number the machine can actually hold is **165 mm/s**.

That is not a downgrade. Throughput is what sets print time, and the 0.6 moves
**36 mm3/s against the 0.4's 25**, a 44 percent gain, while showing a *lower*
mm/s figure. Chase mm3/s. The mm/s number is an output, not a setting.

## The matrix

`profiles/build-profiles.py` derives all of it. 41 presets:

* **2 machines**, one per nozzle, with the 500 mm/s feedrate restored.
* **21 processes**: HF 0.4 at 0.15 / 0.20 / 0.25 mm, HF 0.6 at 0.20 / 0.25 /
  0.32 / 0.40 mm, each in QUALITY / SPEED / MAX.
* **18 filaments**: PLA, PETG, ASA, ABS, PC and TPU per nozzle at E3D's ceiling,
  plus Sunlu PETG at his measured 268 C and a 255/270 calibration pair.

Every MAX tier lands exactly on the nozzle's published flow ceiling, which is the
check that the arithmetic is right:

| nozzle | layer | tier | infill | outer wall | travel | accel | mm3/s |
|---|---|---|---|---|---|---|---|
| HF 0.4 | 0.15 | MAX | 370 | 278 | 500 | 7000 | **25.0** |
| HF 0.4 | 0.20 | MAX | 278 | 208 | 500 | 7000 | **25.0** |
| HF 0.6 | 0.20 | MAX | 265 | 199 | 500 | 7000 | **36.0** |
| HF 0.6 | 0.32 | MAX | 165 | 124 | 500 | 7000 | **35.9** |
| HF 0.6 | 0.40 | MAX | 132 | 99 | 500 | 7000 | **35.9** |

The outer wall is the slowest printing role in every tier, because it is the only
one anyone looks at.

## What the numbers are not

E3D's figures are quoted at 220 / 240 / 260 C. Ken runs PETG at **268**, and flow
scales with melt rate, so his real ceiling is at or above 36 on the 0.6. **That
has to be earned by a flow calibration, not assumed**, so the shipped profiles
hold at the published number and the `CAL PETG 255/270` filaments (flow set 10
over, cooling throttle off) are what move it.

The 0.6 is the ObXidian, so it takes CF and GF. The 0.4 is plain brass high flow
and must not see an abrasive filament.
