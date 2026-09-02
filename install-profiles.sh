#!/usr/bin/env bash
# Install the generated Core One L presets into OrcaSlicer's user datadir, and
# inject the PrusaLink host + credentials into the machine presets so Orca can
# connect, print, and read status.
#
# The credentials live ONLY here at install time, read from the gitignored
# printer.env. They are written into ~/.config/OrcaSlicer (machine-local), never
# into the source profiles under profiles/, so the public repo stays clean.
#
# Orca rewrites its user dir on exit, so this refuses to run while Orca is open.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.config/OrcaSlicer/user/default"

if pgrep -x orca-slicer >/dev/null 2>&1; then
  echo "OrcaSlicer is running. Close it first (it rewrites its user dir on exit)." >&2
  exit 1
fi
[ -f "$HERE/printer.env" ] || { echo "printer.env missing. Copy printer.env.example." >&2; exit 1; }
set -a; . "$HERE/printer.env"; set +a

python3 - "$HERE" "$DEST" "$COREONEL_IP" "$COREONEL_USER" "$COREONEL_PASSWORD" <<'PY'
import json, os, sys, glob
here, dest, ip, user, pw = sys.argv[1:6]
n = 0
for kind in ("machine", "process", "filament"):
    src_dir = os.path.join(here, "profiles", kind)
    dst_dir = os.path.join(dest, kind)
    os.makedirs(dst_dir, exist_ok=True)
    for src in glob.glob(os.path.join(src_dir, "*.json")):
        d = json.load(open(src))
        if kind == "machine":
            # Inject the live connection. Not stored in the source file.
            d["host_type"] = "prusalink"
            d["print_host"] = ip
            d["printhost_user"] = user
            d["printhost_password"] = pw
            # Orca's enum serializes as "user" (HTTP digest) / "key" (API key).
            # "AuthUserPass" is not a value Orca knows; it silently falls back
            # to API-key auth with no key and every request 401s.
            d["printhost_authorization_type"] = "user"
        with open(os.path.join(dst_dir, os.path.basename(src)), "w") as fh:
            json.dump(d, fh, indent=4, ensure_ascii=False); fh.write("\n")
        n += 1
        info = os.path.join(dst_dir, os.path.basename(src)[:-5] + ".info")
        with open(info, "w") as fh:
            fh.write("sync_info = create\nuser_id = \nsetting_id = \nbase_id = \n"
                     "updated_time = %d\n" % int(__import__("time").time()))
print(f"  installed {n} presets into {dest}")
print("  machine presets carry the PrusaLink host + credentials")
PY
echo "Done. Start OrcaSlicer and pick 'Prusa CORE One L HF 0.4 nozzle - 3D3D'."
