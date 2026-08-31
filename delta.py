#!/usr/bin/env python3
"""What did Ken actually change? Resolve each user preset against the Prusa
vendor bundle it inherits from and print only the real overrides."""
import configparser, os, sys, glob

PS = os.path.expanduser("~/.var/app/com.prusa3d.PrusaSlicer/config/PrusaSlicer")
VENDOR = os.path.join(PS, "vendor", "PrusaResearch.ini")


def load_vendor():
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read(VENDOR, encoding="utf-8")
    return cp


def resolve(cp, section, depth=0):
    """Walk `inherits` up the vendor bundle and flatten."""
    if depth > 12 or section not in cp:
        return {}
    d = dict(cp[section])
    parent = d.get("inherits", "").strip()
    if parent:
        kind = section.split(":", 1)[0]
        # `inherits` may list several parents, later ones win
        out = {}
        for p in [x.strip() for x in parent.split(";") if x.strip()]:
            out.update(resolve(cp, f"{kind}:{p}", depth + 1))
        out.update(d)
        d = out
    d.pop("inherits", None)
    return d


def read_user(path):
    d = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def main():
    cp = load_vendor()
    kinds = {"print": "print", "filament": "filament", "printer": "printer"}
    for kind in kinds:
        for path in sorted(glob.glob(os.path.join(PS, kind, "*.ini"))):
            name = os.path.basename(path)[:-4]
            if "COREONE" not in name.upper():
                continue
            user = read_user(path)
            parent = user.get("inherits", "")
            base = resolve(cp, f"{kind}:{parent}") if parent else {}
            print(f"\n{'='*72}\n{kind.upper():9} {name}\n  inherits: {parent or '(none)'}"
                  f"  [parent resolved: {len(base)} keys]")
            diffs = []
            for k, v in sorted(user.items()):
                if k in ("inherits", "print_settings_id", "filament_settings_id",
                         "compatible_printers", "compatible_prints", "notes",
                         "filament_notes"):
                    continue
                bv = base.get(k)
                if bv is None or str(bv).strip() != str(v).strip():
                    diffs.append((k, bv, v))
            if not diffs:
                print("  (identical to parent)")
            for k, bv, v in diffs:
                tag = "NEW " if bv is None else "CHG "
                print(f"  {tag}{k:42} {str(bv)[:34]:<36} -> {v[:60]}")


main()
