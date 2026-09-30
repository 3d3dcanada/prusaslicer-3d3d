#!/usr/bin/env bash
# Patch an OrcaSlicer Linux AppImage so the time estimator stops adding a
# hardcoded 260 s for every G29 line on non-Bambu printers. Prusa's Core One L
# start gcode has six G29 lines, so stock Orca overstates every estimate by
# 26 minutes. Upstream: GCodeProcessor::process_G29, still hardcoded on main
# as of 2026-09-04.
#
# Usage: orca-g29-patch.sh /path/to/OrcaSlicer_...AppImage
# Writes /path/to/OrcaSlicer_..._-3d3d-g29fix.AppImage next to the input.
# The original is never modified. Needs mksquashfs (squashfs-tools).
set -euo pipefail
IN=$(readlink -f "${1:?AppImage path}")
OUT="${IN%.AppImage}-3d3d-g29fix.AppImage"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
"$IN" --appimage-extract >/dev/null
OFFSET=$("$IN" --appimage-offset | tail -1)
BIN=squashfs-root/bin/orca-slicer
python3 - "$BIN" <<'PY'
import re, sys
p = sys.argv[1]
b = bytearray(open(p, 'rb').read())
# cmp byte [rax],0 ; je +0x0a ; cmp byte [rdi+0x12a8],0 ; jne +0x01 ; ret
# The je skips to the dwell when s_IsBBLPrinter is false. Retarget it one
# byte earlier, onto the ret, so non-Bambu printers get no dwell at all.
pat = re.compile(rb"\x80\x38\x00\x74\x0a\x80\xbf.{4}\x00\x75\x01\xc3", re.S)
hits = [m.start() + 4 for m in pat.finditer(b)]
if not hits:
    sys.exit('pattern not found: codegen changed, patch by hand from the README')
for h in hits:
    b[h] = 0x09
open(p, 'wb').write(b)
print(f'patched {len(hits)} site(s): ' + ', '.join(hex(h) for h in hits))
PY
head -c "$OFFSET" "$IN" > runtime.bin
mksquashfs squashfs-root patched.squashfs -root-owned -noappend -comp zstd -b 131072 -quiet -no-progress
cat runtime.bin patched.squashfs > "$OUT"
chmod +x "$OUT"
echo "wrote $OUT"
