"""Košnica 3D - HSW ram (tab Ramovi).

Ram od HSW saća sa belom pločom koja prolazi kroz sredinu ćelija venca:
- prednji deo: saće 5 mm + podloga 1,2 van ploče, tiple sa klikom na svim čvorovima spoljnog oboda
- zadnji deo: saće 3,5 + potporne kolone iza ploče (svakih ~150 mm), rupe Ø2,8 i upusti Ø3,6
- ploča: čist pravougaonik, ne dodiruju je tiple; veća od ploče štampača se deli iznad
  potporne kolone sa lastinim repom
- veliki ram iz komada: prednji i zadnji deo se seku na različitim kolonama (kao cigle),
  pa tiple same premošćuju spoj
- ćelija za kačenje gore na sredini (umetak K1 ili K2), info ćelija dole levo/desno (nosač I2 + pločica)

    from k3d import ramovi
    r = ramovi.Ram(sirina=178, visina=127, stampac="k1", kacenje="K2", info="levo")
    r.delovi          # [Deo(ime, boja, manifold, ...)]
    r.izvezi(folder)  # STL po delu + 3MF po ploči štampača (beli / crni)
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from manifold3d import Manifold, CrossSection
from shapely.geometry import Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

VERSION = "1.1"

# HSW mere (RostaP): rupa 20 ravna-ravna, zid 1,8, korak 23,6
HOLE, WALL = 20.0, 1.8
P = HOLE + 2 * WALL
RO, RI = P / math.sqrt(3), HOLE / math.sqrt(3)
COL = 1.5 * RO
# slojevi (od lica ka zidu)
FRONT, SPACER, BACK = 5.0, 1.2, 3.5
Z1, TOT = FRONT + SPACER, FRONT + SPACER + BACK
PLATE, CLR = 1.0, 0.25
G_DUB, G_SIR = 0.8, 0.6                       # žleb za umetke u zadnjem delu
PIN_D, HOLE_D, CB_D, CB_H, BARB_D, SLOT_W = 2.6, 2.8, 3.6, 0.8, 3.4, 0.8
BOSS_R = 3.0
STAMPACI = {"k1": 300.0, "k2": 350.0}
MARGINA_PLOCE = 10.0                          # ostavi po 5 mm oko dela na ploči štampača
POTPORA_RAZMAK = 150.0
FORMATI = {"9×13": (127, 89), "10×15": (152, 102), "13×18": (178, 127), "15×20": (203, 152),
           "18×24": (240, 180), "20×30": (300, 200), "A4": (297, 210)}
PLA_G_CM3, CENA_KG, MIN_PO_G = 1.24, 3200.0, 4.3   # cena po D9; vreme procena za slojeve 0,12


def _hexagon(cx, cy, r):
    return Polygon([(cx + r * math.cos(math.radians(60 * k)), cy + r * math.sin(math.radians(60 * k)))
                    for k in range(6)])


def _clean(g, e=0.05):
    return g.buffer(-e, join_style=2).buffer(e, join_style=2)


def _cs(g):
    rings = []
    for p in (g.geoms if hasattr(g, "geoms") else [g]):
        if p.is_empty or p.geom_type != "Polygon":
            continue
        p = orient(p, 1.0)
        rings.append(np.array(p.exterior.coords[:-1]))
        rings += [np.array(h.coords[:-1]) for h in p.interiors]
    return CrossSection(rings)


def _ext(g, z0, z1):
    if g.is_empty:
        return Manifold()
    return Manifold.extrude(_cs(g), z1 - z0).translate((0, 0, z0))


@dataclass
class Deo:
    ime: str
    boja: str                 # "crni" | "beli"
    m: Manifold
    napomena: str = ""
    obrni: bool = False       # štampa: okrenuti (z -> -z) pre postavljanja na ploču

    @property
    def grama(self):
        return self.m.volume() / 1000 * PLA_G_CM3


@dataclass
class Ram:
    sirina: float = 178.0      # korisna površina (mm), uvek se uzima kao W >= H za položeni
    visina: float = 127.0
    uspravno: bool = False
    stampac: str = "k1"
    kacenje: str = "K2"        # K1 ključaonica | K2 testera
    info: str = "levo"         # levo | desno | nema
    naziv: str = "hsw_ram"
    za_crtez: bool = False     # True: ogledalo po x, samo za nacrt (vidi _mreza)
    delovi: list = field(default_factory=list, init=False)

    def __post_init__(self):
        w, h = sorted((self.sirina, self.visina), reverse=True)
        if self.uspravno:
            w, h = h, w
        self.W, self.H = w, h
        self._mreza()
        self._napravi()

    # ---------- mreža ----------
    def center(self, i, j):
        return i * COL, j * P + (P / 2 if i % 2 else 0)

    def _mreza(self):
        # najmanje kolona/redova da upisani pravougaonik prozora primi korisnu površinu
        nx = 3 + max(0, math.ceil((self.W - 1.0 - RO) / COL))
        if nx % 2 == 0:
            nx += 1                           # neparno: kačenje tačno na sredini
        ny = 3 + max(0, math.ceil((self.H - 1.0 - P / 2) / P))
        self.NX, self.NY = max(nx, 5), max(ny, 4)
        NX, NY = self.NX, self.NY
        self.cells = [(i, j) for i in range(NX) for j in range(NY)]
        self.ring = [(i, j) for i, j in self.cells if i in (0, NX - 1) or j in (0, NY - 1)]
        self.inner = [c for c in self.cells if c not in self.ring]
        self.HANG = (NX // 2, NY - 1)
        # Lice rama je na z = 0 i gleda ka -z, pa je gledano spreda levo = veliko x. Nacrt (tehnicki_crtez
        # "spreda") projektuje kao da se gleda sa +z, pa ramovi_nacrt crta ram sa za_crtez=True (ogledalo).
        mali_x = (self.info == "levo") == self.za_crtez
        self.INFO = None if self.info == "nema" else ((1, -1) if mali_x else (NX - 2, -1))
        if self.INFO and self.INFO[0] % 2 == 0:   # info visi ispod kolone koja je "gore" pomerena
            self.INFO = (self.INFO[0] + (1 if mali_x else -1), -1)
        self.PX0, self.PX1 = 0.0, (NX - 1) * COL
        self.PY0, self.PY1 = P / 2, (NY - 1) * P
        self.bed = STAMPACI[self.stampac] - MARGINA_PLOCE

    # ---------- geometrija ----------
    def _napravi(self):
        c, NX, NY = self.center, self.NX, self.NY
        dodatne = [self.INFO] if self.INFO else []
        main = Polygon(unary_union([_hexagon(*c(*x), RO + 1e-6) for x in self.cells]).exterior)
        outline = Polygon(unary_union([_hexagon(*c(*x), RO + 1e-6) for x in self.cells + dodatne]).exterior)
        window = Polygon(unary_union([_hexagon(*c(*x), RO + 1e-6) for x in self.inner]).exterior)
        holes = unary_union([_hexagon(*c(*x), RI) for x in self.ring + dodatne])
        lattice = _clean(outline.difference(holes).difference(window))
        self.outline, self.window, self.main = outline, window, main

        # potporne kolone iza ploče (samo zadnji deo)
        sir = self.PX1 - self.PX0
        n_pot = max(0, math.ceil(sir / POTPORA_RAZMAK) - 1)
        self.potpore = [round((k + 1) * (NX - 1) / (n_pot + 1)) for k in range(n_pot)]
        pot_cells = [(i, j) for i in self.potpore for j in range(1, NY - 1)]
        pot = unary_union([_hexagon(*c(*x), RO + 1e-6) for x in pot_cells]) if pot_cells else Polygon()
        pot_lat = _clean(pot.difference(unary_union([_hexagon(*c(*x), RI) for x in pot_cells]))) if pot_cells else Polygon()

        # podela na komade: prednji i zadnji deo na različitim kolonama (cigle)
        self.rez_pred = self._rezovi(0.0)
        self.rez_zad = self._rezovi(0.5)

        # tiple: svi čvorovi spoljnog oboda, dalje od kačenja/info i od svih rezova
        cnt = Counter()
        for x in self.cells:
            cx, cy = c(*x)
            for k in range(6):
                a = math.radians(60 * k)
                cnt[(round(cx + RO * math.cos(a), 3), round(cy + RO * math.sin(a), 3))] += 1
        posebne = [self.HANG] + dodatne
        rezovi_x = [self._x_reza(r) for r in self.rez_pred + self.rez_zad]
        self.cvorovi = sorted(p for p, n in cnt.items() if n == 2 and main.boundary.distance(Point(p)) < 0.05
                              and all(math.dist(p, c(*x)) > RO + BOSS_R + 0.5 for x in posebne)
                              and all(abs(p[0] - xr) > BOSS_R + COL / 2 for xr in rezovi_x))
        bosses = unary_union([Point(p).buffer(BOSS_R, 48) for p in self.cvorovi]).intersection(outline)
        lattice = _clean(unary_union([lattice, bosses]))
        plate_rect = box(self.PX0, self.PY0, self.PX1, self.PY1)
        spacer = _clean(lattice.difference(plate_rect.buffer(CLR, join_style=2)))
        back2d = _clean(unary_union([lattice, pot_lat]))
        groove = unary_union([_hexagon(*c(*x), RI + G_SIR) for x in posebne])
        self.lattice, self.back2d, self.plate_rect = lattice, back2d, plate_rect

        z_cb = TOT - CB_H
        pin = Point(0, 0).buffer(PIN_D / 2, 48)
        slot = box(-SLOT_W / 2, -2, SLOT_W / 2, 2)
        tipla = (_ext(pin, Z1 - 0.01, z_cb)
                 + Manifold.cylinder(TOT - 0.1 - z_cb, BARB_D / 2, PIN_D / 2 - 0.1, 48).translate((0, 0, z_cb))
                 - _ext(slot, Z1 + 0.8, TOT + 1))
        rupa = _ext(Point(0, 0).buffer(HOLE_D / 2, 48), Z1 - 1, TOT + 1) + \
            _ext(Point(0, 0).buffer(CB_D / 2, 48), z_cb, TOT + 1)

        self.delovi = []
        for k, (a, b) in enumerate(self._komadi(self.rez_pred)):
            reg = self._region(a, b, dodatne)
            m = _ext(lattice.intersection(reg), 0, FRONT) + _ext(spacer.intersection(reg), FRONT - 0.01, Z1)
            for p in self.cvorovi:
                if reg.buffer(0.1).contains(Point(p)):
                    m = m + tipla.translate((p[0], p[1], 0))
            self.delovi.append(Deo(self._ime("prednji", k, len(self.rez_pred)), "crni", m,
                                   "licem nadole"))
        for k, (a, b) in enumerate(self._komadi(self.rez_zad)):
            reg = self._region(a, b, dodatne)
            m = _ext(back2d.intersection(reg), Z1, TOT) - _ext(groove, Z1 - 0.1, Z1 + G_DUB)
            for p in self.cvorovi:
                if reg.buffer(0.1).contains(Point(p)):
                    m = m - rupa.translate((p[0], p[1], 0))
            self.delovi.append(Deo(self._ime("zadnji", k, len(self.rez_zad)), "crni", m,
                                   "stranom ka ploči nadole, upusti gore"))
        for k, g in enumerate(self._ploce(plate_rect)):
            self.delovi.append(Deo(self._ime("ploca", k, len(self._ploce_rez)), "beli",
                                   _ext(g, FRONT, FRONT + PLATE), "ravno"))
        self._umeci(posebne)

    def _ime(self, osnova, k, n):
        return f"{self.naziv}_{osnova}" + (f"_{k + 1}" if n else "")

    # rez = granica između kolona (posle kolone i); x reza = sredina zida između kolona
    def _x_reza(self, i):
        return i * COL + COL / 2

    def _rezovi(self, pomak):
        """Granice kolona (rez posle kolone i). Prednji: n jednakih komada; zadnji: pomeren za pola
        komada (cigle), pa ima n+1 komad. Svaki komad staje na ploču štampača."""
        sir = (self.NX - 1) * COL + 2 * RO
        n = math.ceil(sir / self.bed)
        if n <= 1:
            return []
        fr = [(k - pomak) / n for k in range(1, n + (1 if pomak else 0))]
        rez = sorted({min(max(int(round(f * self.NX)) - 1, 0), self.NX - 2) for f in fr if 0 < f < 1})
        while True:
            granice = [-1] + rez + [self.NX - 1]
            siroki = [(a, b) for a, b in zip(granice, granice[1:]) if (b - a - 1) * COL + 2 * RO > self.bed]
            if not siroki:
                return rez
            a, b = siroki[0]
            rez = sorted(set(rez + [(a + b) // 2]))

    def _komadi(self, rez):
        granice = [-1] + rez + [self.NX - 1]
        return list(zip(granice, granice[1:]))

    def _region(self, a, b, dodatne):
        """Ćelije kolona a+1..b (cela visina) + dodatne u tom opsegu; granica ide sredinom zida."""
        cel = [x for x in self.cells + dodatne if a < x[0] <= b]
        return unary_union([_hexagon(*self.center(*x), RO + 1e-6) for x in cel])

    def _ploce(self, rect):
        """Ploča u komade iznad potpornih kolona, spoj lastinim repom."""
        sir = self.PX1 - self.PX0
        self._ploce_rez = []
        if sir <= self.bed:
            return [rect]
        kandidati = [self.center(i, 0)[0] for i in self.potpore]
        rez, x0 = [], self.PX0
        while self.PX1 - x0 > self.bed:
            ok = [x for x in kandidati if x0 < x <= x0 + self.bed - 8]
            if not ok:
                raise ValueError("ploča ne može da se podeli iznad potpornih kolona")
            rez.append(max(ok)); x0 = max(ok)
        self._ploce_rez = rez
        delovi, x0 = [], self.PX0
        granice = rez + [self.PX1]
        for k, x1 in enumerate(granice):
            g = box(x0, self.PY0, x1, self.PY1)
            delovi.append(g); x0 = x1
        # lastin rep: zubi na desnoj ivici komada k, utori na levoj ivici komada k+1
        for k, xs in enumerate(rez):
            zubi = unary_union([self._rep(xs, y) for y in np.linspace(self.PY0, self.PY1, 5)[1:-1]])
            delovi[k] = delovi[k].union(zubi)
            delovi[k + 1] = delovi[k + 1].difference(zubi.buffer(0.15, join_style=2))
        return delovi

    @staticmethod
    def _rep(x, y, vrat=6.0, glava=10.0, dub=6.0):
        return Polygon([(x - 0.01, y - vrat / 2), (x + dub, y - glava / 2), (x + dub, y + glava / 2), (x - 0.01, y + vrat / 2)])

    # ---------- umeci ----------
    def _umeci(self, posebne):
        S, L, ZID, KAPA = 19.7, 9.4, 1.6, 1.2
        TAB_W, TAB_Z0, TAB_Z1, BARB = 6.0, 2.0, 7.2, 0.45

        def hexa(s):
            return _hexagon(0, 0, s / math.sqrt(3))

        def telo(zadnja=None):
            out, inn = hexa(S), hexa(S - 2 * ZID)
            m = _ext(out, 0, KAPA) + _ext(out.difference(inn), KAPA, L)
            if zadnja is not None:
                m = m + _ext(zadnja.intersection(inn), 7.4, L)
            y_out, y_in = S / 2, S / 2 - ZID
            rez = (Manifold.cube((0.6, 3, TAB_Z1 - TAB_Z0 + 0.2)).translate((TAB_W / 2, y_in - 0.5, TAB_Z0))
                   + Manifold.cube((0.6, 3, TAB_Z1 - TAB_Z0 + 0.2)).translate((-TAB_W / 2 - 0.6, y_in - 0.5, TAB_Z0))
                   + Manifold.cube((TAB_W + 1.2, 3, 0.2)).translate((-TAB_W / 2 - 0.6, y_in - 0.5, TAB_Z1)))
            zub = Manifold.extrude(CrossSection([np.array([(y_out - 0.01, 6.25), (y_out + BARB, 6.25), (y_out - 0.01, 7.0)])]), TAB_W)
            zub = zub.rotate((90, 0, 0)).rotate((0, 0, 90))
            b = zub.bounding_box(); zub = zub.translate((-(b[0] + b[3]) / 2, 0, 0))
            b = zub.bounding_box(); zub = zub.translate((0, y_out - 0.01 - b[1], 6.25 - b[2]))
            for ug in (0, 120, 240):
                m = m - rez.rotate((0, 0, ug)) + zub.rotate((0, 0, ug))
            return m

        if self.kacenje == "K1":
            kljuc = unary_union([Point(0, -3.5).buffer(4.5, 48), box(-2.25, -3.5, 2.25, 3.0), Point(0, 3.0).buffer(2.25, 48)])
            k = telo(hexa(S).difference(kljuc)); ime = "umetak_K1_kljucaonica"
        else:
            zupci = [Polygon([(x, 1.5), (x + 1.5, 0.3), (x + 3, 1.5)]) for x in np.arange(-6.0, 6.0, 3.0)]
            k = telo(unary_union([box(-12, 1.5, 12, 4.5)] + zupci)); ime = "umetak_K2_testera"
        hx, hy = self.center(*self.HANG)
        self.delovi.append(Deo(f"{self.naziv}_{ime}", "crni", k.translate((hx, hy, 0)), "licem nadole"))
        if not self.INFO:
            return
        NOS_W, NOS_H, NOS_D = 17.0, 8.0, 4.0
        LR_B, LR_T, LR_H, C = 5.0, 7.0, 1.4, 0.2
        PW, PH, PT = 60.0, 25.0, 2.4

        def prof(b, t, h, l):
            r = Manifold.extrude(CrossSection([np.array([(-b / 2, 0), (b / 2, 0), (t / 2, h), (-t / 2, h)])]), l)
            r = r.rotate((90, 0, 0)).rotate((0, 0, 90))
            bb = r.bounding_box()
            return r.translate((-(bb[0] + bb[3]) / 2, -(bb[1] + bb[4]) / 2, -bb[2]))

        nos = telo(None) + Manifold.cube((NOS_W, NOS_H, NOS_D)).translate((-NOS_W / 2, -NOS_H / 2, -NOS_D)) \
            + prof(LR_B, LR_T, LR_H, NOS_W).mirror((0, 0, 1)).translate((0, 0, -NOS_D))
        z_pl = -NOS_D - PT
        pl = Manifold.cube((PW, PH, PT)).translate((-PW / 2, -PH / 2, z_pl))
        pl = pl - prof(LR_B + 2 * C, LR_T + 2 * C, LR_H + C, PW).translate((-5, 0, 0)).mirror((0, 0, 1)).translate((0, 0, -NOS_D))
        zid = unary_union([box(-PW / 2, PH / 2 - 1, PW / 2, PH / 2), box(-PW / 2, -PH / 2, PW / 2, -PH / 2 + 1), box(-PW / 2, -PH / 2, -PW / 2 + 1, PH / 2)])
        usne = unary_union([box(-PW / 2, PH / 2 - 2.5, PW / 2, PH / 2), box(-PW / 2, -PH / 2, PW / 2, -PH / 2 + 2.5), box(-PW / 2, -PH / 2, -PW / 2 + 2.5, PH / 2)])
        pl = pl + _ext(zid, z_pl - 0.6, z_pl + 0.01) + _ext(usne, z_pl - 1.4, z_pl - 0.59)
        ix, iy = self.center(*self.INFO)
        self.delovi.append(Deo(f"{self.naziv}_umetak_I2_nosac", "crni", nos.translate((ix, iy, 0)),
                               "zadnjom stranom dole", obrni=True))
        self.delovi.append(Deo(f"{self.naziv}_info_plocica", "beli", pl.translate((ix, iy, 0)),
                               "licem nagore (usne bez podrške)", obrni=True))

    # ---------- sažetak ----------
    def sazetak(self):
        ob = self.outline.bounds
        d = {"kolone": self.NX, "redovi": self.NY, "ram_mm": [round(ob[2] - ob[0], 1), round(ob[3] - ob[1], 1)],
             "debljina_mm": TOT, "ploca_mm": [round(self.PX1 - self.PX0, 1), round(self.PY1 - self.PY0, 1)],
             "korisno_mm": [self.W, self.H], "tiple": len(self.cvorovi), "potpore": len(self.potpore),
             "delovi": []}
        for x in self.delovi:
            b = x.m.bounding_box()
            d["delovi"].append({"ime": x.ime, "boja": x.boja, "g": round(x.grama, 1),
                                "mm": [round(b[3] - b[0], 1), round(b[4] - b[1], 1), round(b[5] - b[2], 1)],
                                "napomena": x.napomena})
        for boja in ("crni", "beli"):
            g = sum(x.grama for x in self.delovi if x.boja == boja)
            d[boja] = {"g": round(g), "rsd": round(g / 1000 * CENA_KG), "min": round(g * MIN_PO_G)}
        d["greska"] = self.greska()
        return d

    def greska(self):
        """Ram se deli samo po širini: visina mora da stane na ploču štampača."""
        ob = self.outline.bounds
        h = ob[3] - ob[1]
        if h > self.bed:
            ime = {"k1": "K1 Max", "k2": "K2 Plus"}[self.stampac]
            return (f"Ram je visok {h:.0f} mm, a na {ime} staje najviše {self.bed:.0f} mm. "
                    "Ram se nastavlja samo po širini: smanji visinu, okreni ga ili izaberi veći štampač.")
        return None


# ---------- izvoz ----------
OSNOVA = {"k1": "ram_k1.3mf", "k2": "ram_k2.3mf"}   # Mirkovi 3MF iz Creality Print-a: ram2_v5 (K1 Max 0.12 Ramovi), Svi_ukrasi_v13 (K2 Plus 0.20)
RAZMAK, IVICA = 6.0, 5.0


def _za_stampu(d):
    m = d.m.mirror((0, 0, 1)) if d.obrni else d.m
    b = m.bounding_box()
    return m.translate((0, 0, -b[2]))


def _rasporedi(delovi, bed):
    """Police: najviši deo prvi; vraća listu ploča, svaka [(deo, manifold na mestu)]."""
    stavke = sorted(((d, _za_stampu(d)) for d in delovi), key=lambda x: -(x[1].bounding_box()[4] - x[1].bounding_box()[1]))
    ploce, tek = [], None

    def nova():
        return {"del": [], "y": IVICA, "x": IVICA, "h": 0.0}

    for d, m in stavke:
        b = m.bounding_box()
        w, h = b[3] - b[0], b[4] - b[1]
        if w > bed - 2 * IVICA or h > bed - 2 * IVICA:
            # pokušaj okrenut za 90°
            m = m.rotate((0, 0, 90)); b = m.bounding_box(); w, h = b[3] - b[0], b[4] - b[1]
            if w > bed - 2 * IVICA or h > bed - 2 * IVICA:
                raise ValueError(f"{d.ime} ({w:.0f} × {h:.0f} mm) ne staje na ploču {bed:.0f} mm")
        smesten = False
        for p in ploce + ([tek] if tek and tek not in ploce else []):
            if p["x"] + w <= bed - IVICA and p["y"] + h <= bed - IVICA:
                pass
            elif p["y"] + p["h"] + RAZMAK + h <= bed - IVICA and w <= bed - 2 * IVICA:
                p["y"] += p["h"] + RAZMAK; p["x"] = IVICA; p["h"] = 0.0
            else:
                continue
            p["del"].append((d, m.translate((p["x"] - b[0], p["y"] - b[1], 0))))
            p["x"] += w + RAZMAK; p["h"] = max(p["h"], h)
            smesten = True
            break
        if not smesten:
            p = nova(); ploce.append(p)
            p["del"].append((d, m.translate((p["x"] - b[0], p["y"] - b[1], 0))))
            p["x"] += w + RAZMAK; p["h"] = h
    return [p["del"] for p in ploce]


def izvezi(ram, folder, osnova_dir=None, nacrt=True):
    """STL po delu, 3MF po ploči štampača (crni_N / beli_N) na Mirkovom 3MF-u, provera i nacrt."""
    from pathlib import Path
    import trimesh
    from .model3d import mf3, provera_3mf
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    osnova_dir = Path(osnova_dir or Path(__file__).resolve().parent / "osnova")
    bed = STAMPACI[ram.stampac]
    rezultat = {"fajlovi": [], "provera": {}, "sazetak": ram.sazetak()}
    for d in ram.delovi:
        me = _za_stampu(d).to_mesh()
        trimesh.Trimesh(me.vert_properties[:, :3], me.tri_verts, process=False).export(folder / f"{d.ime}.stl")
        rezultat["fajlovi"].append(f"{d.ime}.stl")
    for boja in ("crni", "beli"):
        grupa = [d for d in ram.delovi if d.boja == boja]
        if not grupa:
            continue
        for k, ploca in enumerate(_rasporedi(grupa, bed)):
            p = mf3.open(osnova_dir / OSNOVA[ram.stampac])
            obj = []
            for d, m in ploca:
                me = m.to_mesh()
                obj.append((d.ime, np.asarray(me.vert_properties[:, :3]), np.asarray(me.tri_verts)))
            p.postavi_objekte(obj)
            for n in [n for n in p.files if n.startswith("Metadata/plate_") and n.endswith(".json")]:
                del p.files[n]
            ime = f"{ram.naziv}_{boja}_{k + 1}.3mf"
            p.save(folder / ime)
            rezultat["fajlovi"].append(ime)
            nalazi = provera_3mf.check(folder / ime, printer=ram.stampac.upper())
            rezultat["provera"][ime] = nalazi
    if nacrt:
        try:
            from . import ramovi_nacrt
            ramovi_nacrt.nacrt(ram, str(folder / f"{ram.naziv}_nacrt"))
            rezultat["fajlovi"] += [f"{ram.naziv}_nacrt.png", f"{ram.naziv}_nacrt.pdf"]
        except Exception as e:  # nacrt ne sme da obori izvoz modela
            rezultat["nacrt_greska"] = str(e)
    return rezultat
