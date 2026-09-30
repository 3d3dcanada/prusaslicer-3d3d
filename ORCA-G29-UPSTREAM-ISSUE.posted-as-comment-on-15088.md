# Draft: OrcaSlicer issue (NOT POSTED, needs Ken's go)

Title: Time estimate adds a hardcoded 260 s for every G29 on non-Bambu printers (+26 min on Prusa CORE One L)

`GCodeProcessor::process_G29` (src/libslic3r/GCode/GCodeProcessor.cpp) calls
`simulate_st_synchronize(260.0)` unconditionally when `s_IsBBLPrinter` is false.
The comment says the value is a Bambu bed-levelling assumption ("hardcode 260
seconds for G29, Todo: use a machine related setting").

Prusa's stock CORE One L start gcode (shipped in Orca's own profile) contains six
G29 lines: `G29 P9`, `G29 P1`, `G29 P1 X.. Y.. W.. H.. C`, `G29 P3.2`, `G29 P3.13`,
`G29 A`. Each one adds 260 s, so every estimate on this printer is 26 minutes too
long. The extra time is reported as prepare time and, in the feature breakdown,
as travel, because the dwell attaches to the next queued move block.

Reproduce: OrcaSlicer 2.4.2 Linux, Prusa CORE One L HF 0.4 nozzle system profile,
any small part. Two gears, 4 mm tall, 3.9 g: estimate 41m 25s, first layer 26m 10s.
With the 260 s dwell skipped for non-Bambu printers: 15m 25s, first layer 10s.
Still present on `main` as of 2026-09-04.

Suggested fix: make the G29 time a machine setting (default 0 for third-party
printers, 260 for Bambu), or at least apply it once per print rather than per
G29 line.
