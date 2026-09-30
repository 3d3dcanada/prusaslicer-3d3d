#!/usr/bin/env python3
"""Build a 3D3D preset bundle for PrusaSlicer 3 and install it as a local repo.

Why a bundle and not the plugin API: `ConfigBox:set()` in alpha11 silently drops
string and bool writes, so a Lua plugin cannot even turn `ironing` on. A vendor
bundle is plain YAML and carries every type, exactly like Prusa's own.

Why it grafts onto the PrusaResearch bundle rather than declaring a new vendor:
print presets inherit the starred nodes `*common*` and `*common COREONEL*`, which
live inside the Prusa bundle. Cross-vendor inheritance is not something the alpha
documents, so the safe move is to add files to a copy of Prusa's bundle and bump
its version. Prusa's own preset updates will overwrite it, which is why this is a
script and not a hand edit: re-run it after any update.
"""
import hashlib, json, os, shutil, subprocess, sys, zipfile

HOME = os.path.expanduser("~")
SRC  = f"{HOME}/.cache/ps3-repo/full/PrusaResearch"
WORK = f"{HOME}/.cache/ps3-repo/3d3d-build"
OUT  = f"{HOME}/Desktop/3D3D-STL/_slicer/prusaslicer3/bundle"
PS3  = ["flatpak", "run", "--branch=beta", "com.prusa3d.PrusaSlicer"]
VENDOR = "3D3D"
BUNDLE_VERSION = "1.0.0"


def stage():
    """A standalone 3D3D vendor: only our generated presets, plus the bed model,
    texture and thumbnail assets they reference, copied from Prusa's bundle."""
    dst = f"{WORK}/{VENDOR}/{BUNDLE_VERSION}"
    if os.path.exists(f"{WORK}/{VENDOR}"):
        shutil.rmtree(f"{WORK}/{VENDOR}")
    os.makedirs(f"{dst}/assets", exist_ok=True)
    base = sorted(d for d in os.listdir(SRC) if os.path.isdir(f"{SRC}/{d}"))[-1]
    for a in ("coreonel_bed.stl", "coreonel.svg", "COREONEL_thumbnail.svg"):
        src = f"{SRC}/{base}/assets/{a}"
        if os.path.exists(src):
            shutil.copy(src, f"{dst}/assets/{a}")
    return dst


def write_manifest(dst):
    """manifest.json is a flat list of {filename, filehash} over every file."""
    entries = []
    for root, _dirs, files in os.walk(dst):
        for f in sorted(files):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, dst)
            if rel == "manifest.json":
                continue
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            entries.append({"filename": rel, "filehash": h})
    json.dump(entries, open(f"{dst}/manifest.json", "w"), indent=1)
    return len(entries)


REPO_ID = "3d3d-coreonel"

def write_root_manifest(root):
    """The zip root needs its own repository descriptor, separate from the
    per-vendor-version file list. Without it the install fails with
    "Failed to open manifest file: .../local_repositories/<uuid>/manifest.json".
    """
    json.dump({
        "name": "3D3D Core One L",
        "description": "3D3D tuned presets for the Prusa CORE One L",
        "visibility": "",
        "id": REPO_ID,
        "version": 2,
        "url": f"http://localhost:8000/v2/repos/{REPO_ID}",
        "index_url": f"http://localhost:8000/v2/repos/{REPO_ID}/vendor_indices.zip",
        "offline_archive_url": "",
    }, open(f"{root}/manifest.json", "w"), indent=1)


def write_index(root):
    """vendor_indices.zip holds one `<VendorId>.idx` per vendor: a
    `min_slic3r_version` line then `<version> <comment>` newest first. Without it
    the install fails with `Missing index archive at .../vendor_indices.zip`.
    """
    idx = f"{root}/{VENDOR}.idx"
    with open(idx, "w") as f:
        f.write("min_slic3r_version = 3.0.0-alpha0\n")
        f.write(f"{BUNDLE_VERSION} 3D3D tuned presets for the CORE One L.\n")
    with zipfile.ZipFile(f"{root}/vendor_indices.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(idx, f"{VENDOR}.idx")
    os.remove(idx)


def zip_bundle(dst):
    os.makedirs(OUT, exist_ok=True)
    z = f"{OUT}/3d3d-presets.zip"
    root = os.path.dirname(os.path.dirname(dst))  # .../3d3d-build
    write_root_manifest(root)
    write_index(root)
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(f"{root}/manifest.json", "manifest.json")
        zf.write(f"{root}/vendor_indices.zip", "vendor_indices.zip")
        for r, _d, files in os.walk(f"{root}/{VENDOR}"):
            for f in files:
                p = os.path.join(r, f)
                zf.write(p, os.path.relpath(p, root))
    return z


def run(args, timeout=600):
    return subprocess.run(PS3 + args, capture_output=True, text=True, timeout=timeout)


def install(z):
    # drop any previous 3D3D local source first so they do not stack up
    r = run(["--preset-update-sources"])
    txt = r.stdout
    import re
    for m in re.finditer(r'"uuid": "([0-9a-f-]{36})"[^}]*?"zip_path": "([^"]*)"', txt, re.S):
        pass
    # simpler: parse the json blob
    try:
        blob = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        for s in blob["result"]:
            d = s["descriptor"]
            if d.get("zip_path"):
                run(["--preset-update-remove-local", d["uuid"]])
                print("  removed previous local source", d["uuid"][:8])
    except Exception as e:
        print("  (could not enumerate existing sources:", e, ")")
    r = run(["--preset-update-add-local", z])
    return r


if __name__ == "__main__":
    dst = stage()
    n_extra = 0
    # preset files are dropped in by build-3d3d-presets.py before this runs
    extra = f"{OUT}/generated"
    if os.path.isdir(extra):
        for f in sorted(os.listdir(extra)):
            shutil.copy(f"{extra}/{f}", f"{dst}/{f}")
            n_extra += 1
    n = write_manifest(dst)
    z = zip_bundle(dst)
    print(f"staged {dst}\n  added {n_extra} 3D3D preset file(s), {n} files in manifest")
    print(f"  zip {z} ({os.path.getsize(z)//1024} KB)")
    if "--install" in sys.argv:
        r = install(z)
        print("  install rc:", r.returncode)
        print("  ", (r.stdout or r.stderr)[-400:].replace("\n", " ")[:400])
