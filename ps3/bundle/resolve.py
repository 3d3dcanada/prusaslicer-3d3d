#!/usr/bin/env python3
"""Resolve PrusaSlicer 3's preset YAML trees into flat configs.

A preset file is a tree: a root with `values`, then nested `variants`, each with
a `condition` and its own `values`, leaves carrying a `name`. The effective
config for a named profile is the root's values merged with every ancestor
variant whose condition holds, in order, deepest last.

Conditions are small expressions over printer./tool./feeder./sheet. facts. Only
the handful of forms Prusa actually use are implemented; anything unrecognised
raises rather than being silently treated as true, because a condition quietly
misread is a wrong profile that still slices.
"""
import re, sys, yaml, os, json

class Facts(dict):
    def get_path(self, p):
        if p not in self:
            raise KeyError(f"unknown fact: {p}")
        return self[p]


def ev(cond, f):
    """Evaluate one condition string against the facts."""
    c = cond.strip()
    if c.startswith("!"):
        inner = c[1:].strip()
        if inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1]
        return not ev(inner, f)
    # split on top-level and/or
    for op, fn in ((" or ", any), (" and ", all)):
        parts = split_top(c, op)
        if len(parts) > 1:
            return fn(ev(p, f) for p in parts)
    if c.startswith("(") and c.endswith(")") and balanced(c[1:-1]):
        return ev(c[1:-1], f)
    m = re.match(r'^([\w.]+)\s*(==|!=|=~|!~)\s*(.+)$', c)
    if m:
        lhs, op, rhs = m.group(1), m.group(2), m.group(3).strip()
        v = f.get_path(lhs)
        if op in ("=~", "!~"):
            pat = rhs.strip()
            if pat.startswith("/") and pat.endswith("/"):
                pat = pat[1:-1]
            hit = re.search(pat, str(v)) is not None
            return hit if op == "=~" else not hit
        rv = rhs.strip().strip('"').strip("'")
        try:
            same = float(v) == float(rv)
        except (TypeError, ValueError):
            same = str(v) == rv
        return same if op == "==" else not same
    # a bare fact used as a boolean, e.g. `tool.nozzle_high_flow`
    if re.match(r'^[\w.]+$', c):
        return bool(f.get_path(c))
    raise ValueError(f"unparsed condition: {cond!r}")


def balanced(s):
    d = 0
    for ch in s:
        d += ch == "("
        d -= ch == ")"
        if d < 0:
            return False
    return d == 0


def split_top(s, op):
    """Split on `op` only outside parentheses and outside /regex/ literals."""
    out, depth, i, last, inre = [], 0, 0, 0, False
    while i < len(s):
        ch = s[i]
        if ch == "/" and not inre and (i == 0 or s[i-1] in " (~"):
            inre = True
        elif ch == "/" and inre:
            inre = False
        elif not inre:
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and s.startswith(op, i):
                out.append(s[last:i]); i += len(op); last = i; continue
        i += 1
    out.append(s[last:])
    return [o for o in out if o.strip()]


STARRED = {}

def index_bundle(bundle_dir):
    """Index every starred base node in the bundle, by id.

    A preset declares `inherits: ['*PET*', '*sunluPETG_MAXVOLSPEED*']` and those
    nodes live in OTHER files (`preset-filament-common-*.yaml` and friends).
    Without following them a filament preset resolves to a handful of keys
    instead of ~65, which looks like it worked and is missing the temperatures.
    """
    import glob
    STARRED.clear()
    for f in sorted(glob.glob(os.path.join(bundle_dir, "preset-*.yaml"))):
        for doc in yaml.safe_load_all(open(f)):
            if isinstance(doc, dict) and str(doc.get("id", "")).startswith("*"):
                STARRED[doc["id"]] = doc
    return len(STARRED)


def apply_inherits(node, facts, acc):
    for parent in node.get("inherits") or []:
        base = STARRED.get(parent)
        if base is None:
            raise KeyError(f"inherited node not found in bundle index: {parent}")
        acc = merge_node(base, facts, acc)
    return acc


def merge_node(node, facts, acc):
    """Merge a base node's values plus every matching variant, ignoring names."""
    acc = apply_inherits(node, facts, acc)
    acc = {**acc, **(node.get("values") or {})}
    for v in node.get("variants") or []:
        c = v.get("condition")
        if c is not None and not ev(c, facts):
            continue
        acc = merge_node(v, facts, acc)
    return acc


def walk(node, facts, acc, path, want, found):
    acc = apply_inherits(node, facts, acc)
    vals = node.get("values") or {}
    acc = {**acc, **vals}
    name = node.get("name")
    # Prusa use `name` for intermediate branch nodes too, starred like
    # `*non-MMU branch*`. Those are not user-selectable profiles: keep descending.
    if name and not (name.startswith("*") and name.endswith("*")):
        if want is None or name == want:
            found[name] = dict(acc)
        return
    for v in node.get("variants") or []:
        cond = v.get("condition")
        if cond is not None and not ev(cond, facts):
            continue
        walk(v, facts, acc, path + [cond], want, found)


def resolve_file(path, facts, want=None):
    if not STARRED:
        index_bundle(os.path.dirname(path))
    found = {}
    for doc in yaml.safe_load_all(open(path)):
        if not isinstance(doc, dict) or doc.get("kind") not in ("print", "filament", "printer", "tool_print"):
            continue
        if str(doc.get("id", "")).startswith("*"):
            continue          # a starred node is a base, not a profile tree
        walk(doc, facts, {}, [], want, found)
    return found


def bases(path):
    """The starred base nodes a file defines, id -> resolved values (no conditions)."""
    out = {}
    for doc in yaml.safe_load_all(open(path)):
        if isinstance(doc, dict) and str(doc.get("id", "")).startswith("*"):
            out[doc["id"]] = doc
    return out


COREONEL = {
    "printer.model": "COREONEL", "printer.base_model": "COREONE",
    "printer.supports_high_flow_nozzle": True,
    "printer.supports_non_high_flow_nozzle": True,
    "printer.input_shaper": True, "printer.planetary_gearbox": True,
    "printer.multi_extruder": False, "printer.supports_tool_preheating": False,
    "feeder.base_model": "", "feeder.model": "", "feeder.single_mode": True,
    "sheet.type": "satin",
}

def facts_for(nozzle, hf):
    f = Facts(COREONEL)
    f["tool.nozzle_diameter"] = nozzle
    f["tool.nozzle_high_flow"] = hf
    return f


if __name__ == "__main__":
    p, nz, hf = sys.argv[1], float(sys.argv[2]), sys.argv[3] == "hf"
    want = sys.argv[4] if len(sys.argv) > 4 else None
    r = resolve_file(p, facts_for(nz, hf), want)
    if want:
        print(json.dumps(r.get(want, {}), indent=1, sort_keys=True))
    else:
        for k in sorted(r):
            print(f"{k}  ({len(r[k])} keys)")
