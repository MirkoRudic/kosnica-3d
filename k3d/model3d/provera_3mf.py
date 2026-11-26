"""VAJB provera_3mf 1.0 - check a slicer project before it goes to Mirko (PRAVILA_3D.md D2).

    python provera_3mf.py ram_v11.3mf [--stampac K1|K2] [--cena 3200]
    -> list of GREŠKA / PROVERI / INFO; exit code 1 when there is a GREŠKA.

Checks: names, every object on the plate (z=0) and inside it, objects that overlap each other,
bodies stacked inside one object (the "5 ornaments in one" case), closed meshes, and the settings
that actually apply to each object (object value wins over the project value).
Weight is an upper bound from the volume (as if 100% solid); real weight and time come from the slicer.
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from model3d import mf3

BEDS = {"K1": 300.0, "K2": 350.0}
DENS = {"PLA": 1.24, "PETG": 1.27, "ASA": 1.07, "ABS": 1.04, "TPU": 1.21}
SHOW = [("layer_height", "sloj"), ("initial_layer_print_height", "prvi sloj"), ("wall_loops", "zidovi"),
        ("sparse_infill_density", "ispuna"), ("sparse_infill_pattern", "šara ispune"),
        ("brim_type", "brim"), ("brim_width", "širina brima"), ("enable_support", "podrška"),
        ("support_type", "vrsta podrške"), ("elefant_foot_compensation", "elephant foot"),
        ("nozzle_temperature", "dizna °C"), ("hot_plate_temp", "ploča °C"), ("filament_type", "filament")]
DEFAULT_NAMES = re.compile(r"^(objekat \d+|object\s*\d*|cube|cylinder|sphere|mesh|untitled|copy|kopija)", re.I)


def _first(v):
    if isinstance(v, list):
        return v[0] if v else ""
    return v


def bed_size(settings, printer=None):
    if printer:
        return BEDS[printer.upper()[:2]], BEDS[printer.upper()[:2]]
    area = settings.get("printable_area")
    if area:
        pts = [tuple(map(float, p.split("x"))) for p in (area if isinstance(area, list) else str(area).split(","))]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return max(xs) - min(xs), max(ys) - min(ys)
    name = (str(_first(settings.get("printer_model", ""))) + str(_first(settings.get("printer_settings_id", "")))).upper()
    for k, v in BEDS.items():
        if k in name:
            return v, v
    return None


def _manifold(v, t):
    import manifold3d as m3
    mesh = m3.Mesh(vert_properties=np.asarray(v, np.float32), tri_verts=np.asarray(t, np.uint32))
    return m3.Manifold(mesh)


def _bodies(v, t):
    """Split a mesh into connected bodies (shared vertices)."""
    n = len(v)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    # merge coincident vertices first (meshes are often written with duplicated corners)
    key = {tuple(np.round(p, 4)): i for i, p in enumerate(v)}
    remap = np.array([key[tuple(np.round(p, 4))] for p in v])
    for a, b, c in remap[t]:
        for x, y in ((a, b), (b, c)):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry
    roots = np.array([find(i) for i in remap[t][:, 0]])
    out = []
    for r in np.unique(roots):
        tt = remap[t][roots == r]
        used = np.unique(tt)
        idx = {u: i for i, u in enumerate(used)}
        out.append((v[used], np.vectorize(idx.get)(tt)))
    return out


def check(path, printer=None, price=3200.0):
    p = mf3.open(path)
    out = []
    hit = lambda lvl, msg: out.append((lvl, msg))
    if not p.objects:
        hit("GREŠKA", "nema nijednog objekta na ploči")
        return out
    bed = bed_size(p.settings, printer)
    names = [o.name for o in p.objects]
    for n in set(names):
        if names.count(n) > 1:
            hit("PROVERI", f"isto ime za {names.count(n)} objekta: „{n}“ (Nadzor ih ne razlikuje, D11)")
    mans = {}
    for o in p.objects:
        tag = f"„{o.name}“"
        if DEFAULT_NAMES.match(o.name):
            hit("PROVERI", f"{tag}: ime nije ime dela (D11)")
        if not len(o.verts):
            hit("GREŠKA", f"{tag}: nema geometrije")
            continue
        lo, hi = o.verts.min(0), o.verts.max(0)
        if lo[2] < -0.01:
            hit("GREŠKA", f"{tag}: deo je ispod ploče ({lo[2]:.2f} mm)")
        elif lo[2] > 0.01:
            hit("GREŠKA", f"{tag}: ne leži na ploči (dno na {lo[2]:.2f} mm)")
        if bed and (lo[0] < -0.01 or lo[1] < -0.01 or hi[0] > bed[0] + 0.01 or hi[1] > bed[1] + 0.01):
            hit("GREŠKA", f"{tag}: izlazi van ploče {bed[0]:g}×{bed[1]:g} mm "
                          f"(x {lo[0]:.1f}–{hi[0]:.1f}, y {lo[1]:.1f}–{hi[1]:.1f})")
        try:
            m = _manifold(o.verts, o.tris)
            if m.status().name != "NoError" or m.volume() <= 0:
                raise ValueError(m.status().name)
            mans[o.name] = m
        except Exception as e:  # namerno: svaka greška mreže se prijavi, nijedna ne prekida proveru
            hit("GREŠKA", f"{tag}: mreža nije zatvorena ili je pokvarena ({e})")
            continue
        keys = [tuple(sorted(tuple(np.round(o.verts[i], 3)) for i in tri)) for tri in o.tris]
        dup = len(keys) - len(set(keys))
        if dup > 0.1 * len(keys):
            copies = round(len(keys) / max(1, len(set(keys))))
            hit("GREŠKA", f"{tag}: isti trouglovi postoje više puta (~{copies} kopije na istom mestu)")
        bodies = _bodies(o.verts, o.tris)
        if len(bodies) > 1:
            ms = []
            for bv, bt in bodies:
                try:
                    ms.append(_manifold(bv, bt))
                except Exception:  # namerno: otvoreno telo već prijavi provera celog objekta
                    pass
            stacked = sum(1 for i in range(len(ms)) for j in range(i + 1, len(ms))
                          if (ms[i] ^ ms[j]).volume() > 0.5 * min(ms[i].volume(), ms[j].volume()))
            if stacked:
                hit("GREŠKA", f"{tag}: {len(bodies)} tela, od toga {stacked} par(ova) jedno u drugom (preklopljene kopije?)")
            else:
                hit("INFO", f"{tag}: {len(bodies)} odvojena tela u jednom objektu")
        eff = {k: p.effective(k, o) for k, _ in SHOW}
        fil = str(eff.get("filament_type") or "PLA").upper()
        g = m.volume() / 1000 * DENS.get(fil, 1.24)
        hit("INFO", f"{tag}: {hi[0]-lo[0]:.1f}×{hi[1]-lo[1]:.1f}×{hi[2]-lo[2]:.1f} mm, najviše {g:.0f} g "
                    f"(~{g * price / 1000:.0f} RSD ako je pun)")
        own = {k: v for k, v in o.settings.items() if k in dict(SHOW)}
        mods = [pt for pt in o.parts if pt.subtype == "modifier_part"]
        hit("INFO", f"{tag}: " + ", ".join(f"{lbl} {eff[k]}{'*' if k in own else ''}" for k, lbl in SHOW if eff.get(k) != "")
            + (f"; modifikatori: {len(mods)}" if mods else "") + "   (* = podešeno na objektu)")
    pm = str(_first(p.settings.get("printer_model", "")))
    for n, ps in p.plate_settings.items():
        prof = " ".join(str(ps.get(k, "")) for k in ("inherits", "name", "print_settings_id"))
        for k in ("K1", "K2"):
            other = "K2" if k == "K1" else "K1"
            if k in pm.upper().replace(" ", "") and other in prof.upper().replace(" ", ""):
                hit("GREŠKA", f"ploča {n}: štampač je {pm}, a profil štampe je za {other} („{ps.get('name', '')}“)")
        if ps.keys() - {"from", "inherits", "name", "print_settings_id", "version"}:
            own = {k: v for k, v in ps.items() if k not in ("from", "inherits", "name", "print_settings_id", "version")}
            hit("INFO", f"ploča {n} menja podešavanja projekta: " + ", ".join(f"{k}={v}" for k, v in own.items()))
    keys = list(mans)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = mans[keys[i]], mans[keys[j]]
            bi, bj = a.bounding_box(), b.bounding_box()
            if bi[3] < bj[0] or bj[3] < bi[0] or bi[4] < bj[1] or bj[4] < bi[1]:
                continue
            v = (a ^ b).volume()
            if v > 0.01:
                hit("GREŠKA", f"„{keys[i]}“ i „{keys[j]}“ se preklapaju ({v:.0f} mm³)")
    if not bed:
        hit("PROVERI", "štampač nije prepoznat iz projekta: navedi --stampac K1 ili K2 da se proveri ploča")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("fajl")
    ap.add_argument("--stampac", choices=["K1", "K2"])
    ap.add_argument("--cena", type=float, default=3200.0, help="RSD po kg filamenta")
    a = ap.parse_args(argv)
    res = check(a.fajl, a.stampac, a.cena)
    order = {"GREŠKA": 0, "PROVERI": 1, "INFO": 2}
    for lvl, msg in sorted(res, key=lambda r: order[r[0]]):
        print(f"{lvl:7} {msg}")
    if not any(r[0] != "INFO" for r in res):
        print("provera_3mf: ništa sporno")
    return 1 if any(r[0] == "GREŠKA" for r in res) else 0


if __name__ == "__main__":
    sys.exit(main())
