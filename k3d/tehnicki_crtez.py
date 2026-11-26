"""VAJB tehnicki_crtez 1.12 - skica/nacrt kao tehnicki crtez (PRAVILA.md R15).

Gornji red: spreda, sa strane, otpozadi (ista razmera, poravnati vrhovi i naslovi).
Donji red: odozdo, izometrija, okvir sa delovima/napomenama/legendom dole desno.
Posle crtanja sam proverava da nijedan tekst nije isecen ili preklopljen.

    import tehnicki_crtez as tc
    c = tc.Crtez("HSW RAM, POLOZENI, 13x18")
    c.spreda.oblik(ram2d, tc.TAMNO, rupe=tc.BELO)          # shapely Polygon/Multi
    c.spreda.oblik(ploca2d, "none", ivica=tc.PLAVO, crtkano=True)
    c.spreda.kota_h(x0, x1, y, "231.6")                     # kota preko predmeta
    c.spreda.kota_v(y0, y1, x, "200.6", desno=True)
    c.spreda.pomocna(x0, y0, x1, y1)                         # pomocna linija za kotu van predmeta
    c.strana.pravougaonik(z0, y0, z1, y1, tc.TAMNO)          # x = dubina, y = visina
    tc.iz_modela(c, manifold, boja=tc.TAMNO)                 # popuni sve poglede iz 3D modela
    c.pozadi / c.odozdo  - isto kao spreda (odozdo: x, dubina)
    c.izometrija(manifold_ili_trimesh, boja=(0.35, 0.35, 0.35))
    c.izometrija_lice(shapely_poly, dubina=8.1, boja=(0.8, 0.88, 0.97))   # ravna povrs
    c.okvir(podnaslov="mere u mm", delovi=[("1  Ram, crni PLA, ~59 g", tc.CRNO)],
            napomene=["Ploca ulazi odozgo"], legenda=[("plavo: ploca", tc.CRNO)])
    problemi = c.sacuvaj("nacrt")       # nacrt.png + nacrt.pdf; vraca listu problema ([] = ok)

Format: "ekran" (podrazumevano, 16:9, 1920x1080 - ceo nacrt na jednom ekranu bez skrolovanja)
ili "A3" (za stampu). List ima milimetarsku mrezom (1 / 5 / 10 mm papira); razmera se bira iz standardnih
(1:1, 1:2, 1:2,5, 1:5 ...) i upisuje u okvir zajedno sa lenjirom. Svi pogledi su u ISTOJ razmeri
(medjusobni odnosi 1:1); pogled odozdo je tacno ispod pogleda spreda (iste x-koordinate).
uvecanje != 1 je dozvoljeno samo ako drugacije ne moze i provera ga prijavljuje.

Pogled sa strane gleda sleva: x = dubina od lica (0) ka zidu, y = ista visina kao spreda.
Pogled otpozadi: prosledi vec preslikanu geometriju (tc.preslikaj(g, os_x)).
Pogled odozdo: x isto kao spreda, y = dubina (0 = lice).
"""
from __future__ import annotations

import datetime as _dt
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as _MP, Rectangle as _Rect

CRNO, SIVO, TAMNO, SREDNJE, SVETLO = "#111111", "#8a8a8a", "#2b2b2b", "#6d6d6d", "#b5b5b5"
PLAVO, PLAVO_POVRS, CRVENO, BELO = "#1f5fbf", "#cfe0f5", "#c0392b", "white"
CRTKANO = (0, (5, 3))
_FS = 8          # velicina slova kota

FORMATI = {
    # sirina, visina (in), dpi, gornji red (y, h), okvir
    "ekran": dict(FW=16.0, FH=9.0, dpi=120, top=(0.43, 0.49), okvir=[0.775, 0.03, 0.205, 0.39], slova=0.88),
    "A3": dict(FW=16.54, FH=11.69, dpi=130, top=(0.40, 0.52), okvir=[0.77, 0.03, 0.21, 0.33], slova=1.0),
}


def preslikaj(g, os_x):
    """Preslikava shapely geometriju oko vertikalne ose x = os_x (za pogled otpozadi)."""
    from shapely.affinity import scale
    return scale(g, -1, 1, origin=(os_x, 0))


def _cs_u_shapely(cs):
    """manifold3d CrossSection -> shapely (rupe preko XOR prstenova)."""
    from shapely.geometry import Polygon
    g = None
    for r in cs.to_polygons():
        if len(r) < 3:
            continue
        p = Polygon(r).buffer(0)
        g = p if g is None else g.symmetric_difference(p)
    from shapely.geometry import GeometryCollection
    return g if g is not None else GeometryCollection()


# pogled -> matrica (3x4) koja dovodi smer gledanja na -z i horizontalu/vertikalu pogleda na x/y
# "spreda" projektuje gledano sa +z (x desno, y gore). Ako je lice predmeta na z = 0 i gleda ka -z
# (štampa licem nadole), crtež spreda je ogledalo stvarnog izgleda: crtaj model ogledan po x (1.12).
_POGLEDI = {
    "spreda": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]],      # x desno, y gore, z = dubina od lica
    "strana": [[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0]],     # gledano sleva: x = dubina
    "pozadi": [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0]],    # gledano otpozadi: x obrnut
    "odozdo": [[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0]],     # gledano odozdo: y = dubina
}


def projekcija(m, pogled):
    """Obris (senka) modela u datom pogledu, kao shapely geometrija u koordinatama pogleda."""
    return _cs_u_shapely(m.transform(_POGLEDI[pogled]).project())


def presek(m, pogled, na):
    """Presek modela ravni normalnom na smer gledanja; na = koordinata u modelu duz te ose
    (spreda/pozadi: z, strana: x, odozdo: y)."""
    znak = {"spreda": 1, "strana": -1, "pozadi": -1, "odozdo": -1}[pogled]
    return _cs_u_shapely(m.transform(_POGLEDI[pogled]).slice(znak * na))


def iz_modela(c, m, boja=None, pozadi_na=None, strana_na=0.0, izometrija=True,
              pogledi=("spreda", "strana", "pozadi", "odozdo"), z=1):
    """Popunjava sve poglede iz jednog 3D modela: spreda i odozdo = obris,
    sa strane = presek kroz strana_na (x), otpozadi = presek na dubini pozadi_na (z) ili obris."""
    """Vise delova: zovi redom od zadnjeg ka prednjem za svaki pogled (pogledi=...), jer
    kasnije nacrtan deo pokriva ranije; z odredjuje redosled unutar pogleda."""
    boja = boja or TAMNO
    if "spreda" in pogledi:
        c.spreda.oblik(projekcija(m, "spreda"), boja, z=z, rupe=None)
    if "strana" in pogledi:
        c.strana.oblik(presek(m, "strana", strana_na), boja, z=z, rupe=None)
    if "odozdo" in pogledi:
        c.odozdo.oblik(projekcija(m, "odozdo"), boja, z=z, rupe=None)
    if "pozadi" in pogledi:
        g = presek(m, "pozadi", pozadi_na) if pozadi_na is not None else projekcija(m, "pozadi")
        c.pozadi.oblik(g, boja, z=z, rupe=None)
    if izometrija:
        rgb = tuple(int(boja[i:i + 2], 16) / 255 for i in (1, 3, 5)) if isinstance(boja, str) and boja.startswith("#") else boja
        c.izometrija(m, boja=rgb)


class Pogled:
    def __init__(self, crtez, rect, naslov):
        self.c, self.rect, self.naslov = crtez, rect, naslov
        self.ax = crtez.fig.add_axes(rect)
        self.ax.axis("off")
        self.uvecanje = 1.0           # samo po x (za tanak pogled sa strane)
        self._xs, self._ys = [], []   # granice sadrzaja (za razmeru i centriranje)
        self._kote = []               # (osa, polozaj, smer) - tekst kote zauzima ~4 mm papira

    # --- crtanje ---
    def _x(self, x):
        return x * self.uvecanje

    def _obuhvati(self, x0, y0, x1, y1):
        self._xs += [self._x(x0), self._x(x1)]
        self._ys += [y0, y1]

    def oblik(self, g, boja, ivica=None, debljina=0.6, crtkano=False, rupe=BELO, z=1):
        """shapely Polygon / MultiPolygon / GeometryCollection; rupe=None ostavlja providno."""
        if g is None or g.is_empty:
            return
        if g.geom_type in ("MultiPolygon", "GeometryCollection"):
            for p in g.geoms:
                self.oblik(p, boja, ivica, debljina, crtkano, rupe, z)
            return
        if g.geom_type != "Polygon":
            return
        ls = CRTKANO if crtkano else "-"
        ec = ivica or ("none" if boja == "none" else CRNO)
        from matplotlib.path import Path as _Path
        from matplotlib.patches import PathPatch as _PP
        verts, codes = [], []
        for ring in [g.exterior] + list(g.interiors):
            pts = [(self._x(x), y) for x, y in ring.coords]
            verts += pts
            codes += [_Path.MOVETO] + [_Path.LINETO] * (len(pts) - 2) + [_Path.CLOSEPOLY]
        # rupe su prave rupe (vidi se ono iza); rupe=boja ih dodatno popunjava
        self.ax.add_patch(_PP(_Path(verts, codes), fc=boja, ec=ec, lw=debljina, ls=ls, zorder=z))
        if rupe:
            for h in g.interiors:
                hp = [(self._x(x), y) for x, y in h.coords]
                self.ax.add_patch(_MP(hp, fc=rupe, ec=ec, lw=debljina, ls=ls, zorder=z - 0.01))
        b = g.bounds
        self._obuhvati(*b)

    def pravougaonik(self, x0, y0, x1, y1, boja, ivica=None, crtkano=False, z=1):
        ec = ivica or ("none" if boja == "none" else CRNO)
        self.ax.add_patch(_Rect((self._x(x0), y0), self._x(x1) - self._x(x0), y1 - y0, fc=boja,
                                ec=ec, lw=0.9 if crtkano else 0.6, ls=CRTKANO if crtkano else "-",
                                zorder=z))
        self._obuhvati(x0, y0, x1, y1)

    def linija(self, x0, y0, x1, y1, boja=SIVO, debljina=0.5, crtkano=False):
        self.ax.plot([self._x(x0), self._x(x1)], [y0, y1], color=boja, lw=debljina,
                     ls=CRTKANO if crtkano else "-", zorder=6)

    # --- kote ---
    def kota_h(self, x0, x1, y, tekst, ispod=False, vel=_FS):
        a, b = self._x(x0), self._x(x1)
        self.ax.annotate("", (a, y), (b, y), arrowprops=dict(arrowstyle="<->", lw=0.6))
        t = self.ax.text((a + b) / 2, y + (-1.5 if ispod else 1.5), tekst, ha="center",
                         va="top" if ispod else "bottom", fontsize=vel)
        self.c._tekstovi.append((t, self))
        self._kote.append(("y", y, -1 if ispod else 1))

    def kota_v(self, y0, y1, x, tekst, desno=False, vel=_FS):
        xx = self._x(x)
        self.ax.annotate("", (xx, y0), (xx, y1), arrowprops=dict(arrowstyle="<->", lw=0.6))
        t = self.ax.text(xx + (1.5 if desno else -1.5), (y0 + y1) / 2, tekst,
                         ha="left" if desno else "right", va="center", fontsize=vel, rotation=90)
        self.c._tekstovi.append((t, self))
        self._kote.append(("x", xx, 1 if desno else -1))

    def pomocna(self, x0, y0, x1, y1):
        """Tanka pomocna linija od ivice predmeta do kote koja je van predmeta."""
        self.linija(x0, y0, x1, y1, boja="#999999", debljina=0.4)
        self._obuhvati(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def granice(self):
        xs, ys = list(self._xs), list(self._ys)
        pad = self.c._pad
        for osa, v, smer in self._kote:
            (xs if osa == "x" else ys).append(v + smer * pad)
        if not xs or not ys:
            return 0, 0, 1, 1
        return min(xs), min(ys), max(xs), max(ys)


class Crtez:
    def __init__(self, naslov, podnaslov=None, datum=None, format="ekran"):
        f = FORMATI[format]
        self.format, self.FW, self.FH, self.dpi = format, f["FW"], f["FH"], f["dpi"]
        ty, th = f["top"]
        self.R_SPREDA = [0.03, ty, 0.40, th]
        self.R_STRANA = [0.45, ty, 0.07, th]
        self.R_POZADI = [0.56, ty, 0.40, th]
        self.R_ODOZDO = [0.03, 0.14, 0.40, 0.12]
        self.R_IZO = [0.45, 0.03, 0.30, 0.25]
        self.R_OKVIR = f["okvir"]
        self.slova = f["slova"]
        self.naslov = naslov
        self.datum = datum or _dt.date.today().strftime("%d.%m.%Y")
        self.podnaslov = podnaslov or f"mere u mm · {self.datum}"
        self.fig = plt.figure(figsize=(self.FW, self.FH))
        self._tekstovi = []
        self.spreda = Pogled(self, self.R_SPREDA, "Pogled spreda")
        self.strana = Pogled(self, self.R_STRANA, "Sa strane")
        self.pozadi = Pogled(self, self.R_POZADI, "Otpozadi")
        self.odozdo = Pogled(self, self.R_ODOZDO, "Odozdo")
        self._izo = []
        self.izo_ugao = (25, -35)  # (elevacija, azimut) u stepenima; otpozadi npr. (25, 145)
        self._pad = 6.0          # prostor za tekst kote, u mm modela (preracunava se iz razmere)
        self._okvir = None
        self.margina = 8.0     # mm vazduha oko sadrzaja; za sitne detalje smanjiti (npr. 3)
        self.razmera = None    # npr. 2 za 1:2; None = sama bira
        self.mreza = True

    # --- izometrija ---
    def izometrija(self, mreza, boja=(0.35, 0.35, 0.35)):
        """mreza: manifold3d.Manifold, trimesh.Trimesh ili (verts, tris)."""
        if hasattr(mreza, "to_mesh"):
            m = mreza.to_mesh()
            v, t = np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts)
        elif hasattr(mreza, "vertices"):
            v, t = np.asarray(mreza.vertices), np.asarray(mreza.faces)
        else:
            v, t = map(np.asarray, mreza)
        self._izo.append(("mreza", v[t][:, :, [0, 2, 1]], boja))

    def izometrija_lice(self, poligon, dubina, boja):
        """Ravna povrs (npr. ploca) kao jedan poligon - bez pruga od trouglova."""
        for p in (poligon.geoms if hasattr(poligon, "geoms") else [poligon]):
            r = np.array(p.exterior.coords)
            self._izo.append(("lice", np.c_[r[:, 0], np.full(len(r), dubina), r[:, 1]], boja))

    # --- okvir dole desno ---
    def okvir(self, delovi=(), napomene=(), legenda=()):
        self._okvir = (list(delovi), list(napomene), list(legenda))

    # --- slaganje ---
    def _razmera(self):
        """Prvi prolaz: razmera sa grubim prostorom za kote; drugi: kote = 4 mm papira."""
        self._pad = 6.0
        n = self._izracunaj_n()
        self._pad = 4.0 * n
        return self._izracunaj_n()

    def _izracunaj_n(self):
        m = self.margina
        gornji = [self.spreda, self.strana, self.pozadi]
        th = self.spreda.rect[3]
        gf, gd = self.spreda.granice(), self.odozdo.granice()
        kol_x = (min(gf[0], gd[0]), max(gf[2], gd[2]))
        sir = [kol_x[1] - kol_x[0] + 2 * m] + [p.granice()[2] - p.granice()[0] + 2 * m for p in gornji[1:]]
        vis = max(p.granice()[3] - p.granice()[1] + 2 * m for p in gornji)
        u = max(vis / (th * self.FH), sum(sir) / ((0.97 - 0.03 - 0.05) * self.FW))
        n = u / 25.4
        if self.razmera:
            return max(n, self.razmera)
        for k in (0.1, 0.2, 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10, 15, 20, 25, 50, 100):
            if k >= n - 1e-9:
                return k
        return n

    def _rasporedi(self):
        self._razmera()
        m = self.margina
        gornji = [self.spreda, self.strana, self.pozadi]
        # ista razmera za ceo gornji red; sirine pogleda prema sadrzaju (ne fiksne kolone)
        ty, th = self.spreda.rect[1], self.spreda.rect[3]
        gf, gd = self.spreda.granice(), self.odozdo.granice()
        kol_x = (min(gf[0], gd[0]), max(gf[2], gd[2]))       # spreda i odozdo dele x-ose
        sir = [kol_x[1] - kol_x[0] + 2 * m] + [p.granice()[2] - p.granice()[0] + 2 * m for p in gornji[1:]]
        vis = max(p.granice()[3] - p.granice()[1] + 2 * m for p in gornji)
        razmak, levo, desno = 0.025, 0.03, 0.97
        u = max(vis / (th * self.FH), sum(sir) / ((desno - levo - 2 * razmak) * self.FW))
        # standardna razmera: 1:N, gde je N model-mm po papir-mm
        n = u / 25.4
        if self.razmera:
            n = max(n, self.razmera)
        else:
            for k in (0.1, 0.2, 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10, 15, 20, 25, 50, 100):
                if k >= n - 1e-9:
                    n = k
                    break
        self._n = n
        u = n * 25.4
        w_fig = [max(w / (u * self.FW), 0.075) for w in sir]    # mesta bar za naslov pogleda
        x = levo + ((desno - levo) - (sum(w_fig) + 2 * razmak)) / 2
        for p, w in zip(gornji, w_fig):
            p.rect = [x, ty, w, th]
            p.ax.set_position(p.rect)
            x += w + razmak
        # gornji red: isti vrh sadrzaja
        top = max(p.granice()[3] for p in gornji)
        dno = min(p.granice()[1] for p in gornji)
        for p in gornji:
            x0, y0, x1, y1 = p.granice()
            if p is self.spreda:
                x0, x1 = kol_x
            w, h = p.rect[2] * self.FW * u, p.rect[3] * self.FH * u
            cx = (x0 + x1) / 2
            p.ax.set_xlim(cx - w / 2, cx + w / 2)
            p.ax.set_ylim(top + m - h, top + m)
        r = self.spreda.rect
        dno_fig = r[1] + r[3] - (top + m - (dno - m)) / (self.FH * u)    # dno sadrzaja gornjeg reda
        for p in gornji:
            t = p.naslov
            self._tekstovi.append((self.fig.text(p.rect[0], p.rect[1] + p.rect[3] + 0.012, t, fontsize=10,
                                                 color=SIVO), "naslov", None))
        # donji red odmah ispod gornjeg (bez praznog pojasa), do dna lista
        y_nasl = dno_fig - 0.04                     # donji red odmah ispod gornjeg (okvir je desno, ne smeta)
        dole, vis = 0.03, y_nasl - 0.012 - 0.03
        rf = self.spreda.rect
        self._r_odozdo = [rf[0], dole, rf[2], vis]                  # tacno ispod pogleda spreda
        izo_x = max(rf[0] + rf[2] + razmak, 0.30)
        self._r_izo = [izo_x, dole, max(self.R_OKVIR[0] - 0.015 - izo_x, 0.15), vis]
        self.odozdo.ax.set_position(self._r_odozdo)
        x0, y0, x1, y1 = self.odozdo.granice()
        h = vis * self.FH * u
        self.odozdo.ax.set_xlim(*self.spreda.ax.get_xlim())        # iste x-ose kao spreda
        self.odozdo.ax.set_ylim(y1 + m - h, y1 + m)                 # uz vrh pojasa, kao gornji red
        self.fig.text(rf[0], y_nasl, self.odozdo.naslov, fontsize=10, color=SIVO)
        self.fig.text(izo_x, y_nasl, "Izometrija", fontsize=10, color=SIVO)

    def _crtaj_izometriju(self):
        """Izometrija softverskim z-baferom (tacno skrivanje), u ISTOJ razmeri kao pogledi."""
        if not self._izo:
            return
        tris, cols = [], []
        for vrsta, data, boja in self._izo:
            if vrsta == "mreza":                      # data: (n,3,3) u (x, dubina, y)
                t = data[:, :, [0, 2, 1]]             # nazad u (x, y, z=dubina)
                tris.append(t); cols.append(np.repeat(np.array(boja, float)[None, :3], len(t), 0))
            else:
                from shapely.geometry import Polygon as _P
                from shapely.ops import triangulate
                pts = data[:, [0, 2, 1]]
                z0 = pts[0, 2]
                poly = _P(pts[:, :2]).buffer(0)
                tt = [tr for tr in triangulate(poly) if poly.contains(tr.centroid)]
                if tt:
                    arr = np.array([[[x, y, z0] for x, y in list(tr.exterior.coords)[:3]] for tr in tt])
                    tris.append(arr); cols.append(np.repeat(np.array(boja, float)[None, :3], len(arr), 0))
        T, C = np.vstack(tris), np.vstack(cols)
        el, az = np.radians(self.izo_ugao[0]), np.radians(self.izo_ugao[1])
        # model: x desno, y gore, z dubina (od lica ka zidu). Kamera ispred (z<0), rotacija oko y pa oko x
        Ry = np.array([[np.cos(az), 0, np.sin(az)], [0, 1, 0], [-np.sin(az), 0, np.cos(az)]])
        Rx = np.array([[1, 0, 0], [0, np.cos(el), -np.sin(el)], [0, np.sin(el), np.cos(el)]])
        V = T @ (Rx @ Ry).T                            # x, y ekrana; z = dubina (manje = blize)
        n = np.cross(V[:, 1] - V[:, 0], V[:, 2] - V[:, 0])
        n /= (np.linalg.norm(n, axis=1)[:, None] + 1e-12)
        sv = np.array([-0.35, 0.55, -0.75]); sv /= np.linalg.norm(sv)
        shade = 0.40 + 0.60 * np.abs(n @ sv)
        ax = self.fig.add_axes(self._r_izo); ax.axis("off")
        u = self._n * 25.4                             # mm modela po inchu
        w_mm, h_mm = self._r_izo[2] * self.FW * u, self._r_izo[3] * self.FH * u
        lo, hi = V[:, :, :2].reshape(-1, 2).min(0), V[:, :, :2].reshape(-1, 2).max(0)
        cx, cy = (lo + hi) / 2
        f = max((hi[0] - lo[0]) / (w_mm * 0.96), (hi[1] - lo[1]) / (h_mm * 0.96), 1.0)
        if f > 1.0:                                    # ne staje u istoj razmeri: umanji samo izometriju
            self._izo_umanjena = f
            w_mm, h_mm = w_mm * f, h_mm * f
        px = 0.12 * self._n * f                        # mm modela po pikselu rastera (~8 px/mm papira)
        W, Hh = int(w_mm / px) + 1, int(h_mm / px) + 1
        x0, y0 = cx - w_mm / 2, cy - h_mm / 2
        zb = np.full((Hh, W), np.inf); img = np.zeros((Hh, W, 4))
        P = (V[:, :, :2] - [x0, y0]) / px
        for k in range(len(V)):
            a_, b_, c_ = P[k]
            xmin, xmax = int(max(min(a_[0], b_[0], c_[0]), 0)), int(min(max(a_[0], b_[0], c_[0]) + 1, W - 1))
            ymin, ymax = int(max(min(a_[1], b_[1], c_[1]), 0)), int(min(max(a_[1], b_[1], c_[1]) + 1, Hh - 1))
            if xmax < xmin or ymax < ymin:
                continue
            gx, gy = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
            d = (b_[1] - c_[1]) * (a_[0] - c_[0]) + (c_[0] - b_[0]) * (a_[1] - c_[1])
            if abs(d) < 1e-12:
                continue
            l1 = ((b_[1] - c_[1]) * (gx - c_[0]) + (c_[0] - b_[0]) * (gy - c_[1])) / d
            l2 = ((c_[1] - a_[1]) * (gx - c_[0]) + (a_[0] - c_[0]) * (gy - c_[1])) / d
            l3 = 1 - l1 - l2
            ins = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
            if not ins.any():
                continue
            z = l1 * V[k, 0, 2] + l2 * V[k, 1, 2] + l3 * V[k, 2, 2]
            sub = zb[ymin:ymax + 1, xmin:xmax + 1]
            upd = ins & (z < sub)
            sub[upd] = z[upd]
            col = np.r_[np.clip(C[k] * shade[k], 0, 1), 1.0]
            img[ymin:ymax + 1, xmin:xmax + 1][upd] = col
        ax.imshow(img, origin="lower", extent=(x0, x0 + W * px, y0, y0 + Hh * px), interpolation="nearest")
        ax.set_xlim(x0, x0 + w_mm); ax.set_ylim(y0, y0 + h_mm); ax.set_aspect("equal")

    def _crtaj_okvir(self):
        ax = self.fig.add_axes(self.R_OKVIR); ax.axis("off")
        ax.add_patch(_Rect((0, 0), 1, 1, fc="white", ec=CRNO, lw=1, transform=ax.transAxes, zorder=0))
        delovi, napomene, legenda = self._okvir or ([], [], [])
        if self._n < 1:
            raz = f"{1 / self._n:g}:1".replace(".", ",")
        else:
            raz = "1:" + f"{self._n:g}".replace(".", ",")
        redovi = [(self.naslov, 11, CRNO, True), (f"{self.podnaslov} · razmera {raz}" + (" (A3)" if self.format == "A3" else ""), 8, SIVO, False)]
        for ime, stavke in (("Delovi", delovi), ("Napomene", napomene), ("Legenda", legenda)):
            if not stavke:
                continue
            redovi += [("", 6, CRNO, False), (ime, 9, CRNO, True)]
            for s in stavke:
                t, boja = (s, CRNO) if isinstance(s, str) else s
                redovi.append((t, 8, boja, False))
        y = 0.96
        for t, fs, boja, bold in redovi:
            fs = fs * self.slova
            txt = ax.text(0.04, y, t, fontsize=fs, color=boja, va="top",
                          weight="bold" if bold else "normal", transform=ax.transAxes)
            if t:
                self._tekstovi.append((txt, "okvir", ax))
            y -= (fs * 1.5 + 1.0) / 72 / (self.R_OKVIR[3] * self.FH)
        # lenjir: 50 mm (ili 100/200) modela u razmeri, dole u okviru
        duz = next(d for d in (1, 2, 5, 10, 20, 50, 100, 200, 500) if d / self._n >= 20)
        w = (duz / self._n) / (self.R_OKVIR[2] * self.FW * 25.4)        # udeo sirine okvira
        x0, y0 = 0.04, 0.035
        for i in range(5):
            ax.add_patch(_Rect((x0 + i * w / 5, y0), w / 5, 0.07 / (self.R_OKVIR[3] * self.FH), transform=ax.transAxes,
                               fc=CRNO if i % 2 == 0 else "white", ec=CRNO, lw=0.6))
        if y < y0 + 0.4 / (self.R_OKVIR[3] * self.FH):
            self._okvir_pun = True
        for k, lab in ((0, "0"), (1, f"{duz} mm")):
            txt = ax.text(x0 + k * w, y0 + 0.11 / (self.R_OKVIR[3] * self.FH), lab, fontsize=7, ha="center", va="bottom",
                          transform=ax.transAxes)
            self._tekstovi.append((txt, "okvir", ax))

    # --- provera (R15: nista isceceno ni preklopljeno) ---
    def provera(self):
        self.fig.canvas.draw()
        r = self.fig.canvas.get_renderer()
        fb = self.fig.bbox
        problemi, kutije = [], []
        for item in self._tekstovi:
            t = item[0]
            if not t.get_text().strip():
                continue
            bb = t.get_window_extent(r)
            ime = t.get_text()
            if bb.x0 < fb.x0 or bb.y0 < fb.y0 or bb.x1 > fb.x1 or bb.y1 > fb.y1:
                problemi.append(f"van lista: {ime}")
            if len(item) == 3 and item[1] == "naslov":
                pass
            elif len(item) == 3:      # okvir: tekst mora ostati u okviru
                ob = item[2].get_window_extent(r)
                if bb.y0 < ob.y0 or bb.x1 > ob.x1:
                    problemi.append(f"izlazi iz okvira: {ime}")
            else:                   # kota: mora ostati u svom pogledu
                ab = item[1].ax.get_window_extent(r)
                if bb.x0 < ab.x0 - 1 or bb.x1 > ab.x1 + 1 or bb.y0 < ab.y0 - 1 or bb.y1 > ab.y1 + 1:
                    problemi.append(f"isecena kota: {ime}")
            kutije.append((ime, bb.padded(2)))
        for i in range(len(kutije)):
            for j in range(i + 1, len(kutije)):
                if kutije[i][1].overlaps(kutije[j][1]):
                    problemi.append(f"preklapaju se: {kutije[i][0]} / {kutije[j][0]}")
        return problemi

    def _crtaj_mrezu(self):
        """Milimetarski papir preko celog lista (u mm papira): 1 mm, 5 mm, 10 mm."""
        if not self.mreza:
            return
        ax = self.fig.add_axes([0, 0, 1, 1], zorder=-10)
        ax.set_xlim(0, self.FW * 25.4); ax.set_ylim(0, self.FH * 25.4); ax.axis("off")
        boja = "#e9a07a"
        for korak, lw, a in ((1, 0.2, 0.18), (5, 0.35, 0.28), (10, 0.5, 0.40)):
            for x in np.arange(0, self.FW * 25.4, korak):
                ax.axvline(x, color=boja, lw=lw, alpha=a)
            for y in np.arange(0, self.FH * 25.4, korak):
                ax.axhline(y, color=boja, lw=lw, alpha=a)
        for a in self.fig.axes:
            if a is not ax:
                a.patch.set_alpha(0)

    def sacuvaj(self, ime, dpi=None):
        """Slaze, crta, proverava i cuva <ime>.png i <ime>.pdf. Vraca listu problema."""
        self._rasporedi()
        self._crtaj_izometriju()
        self._crtaj_okvir()
        self._crtaj_mrezu()
        problemi = self.provera()
        for p in (self.spreda, self.strana, self.pozadi, self.odozdo):
            if abs(p.uvecanje - 1) > 1e-9:
                problemi.append(f"neproporcionalno: {p.naslov} uvecan {p.uvecanje:g}x (dozvoljeno samo ako ne moze drugacije)")
        if getattr(self, "_izo_umanjena", 0):
            problemi.append(f"izometrija umanjena {self._izo_umanjena:.2f}x (ne staje u istoj razmeri) - navedi u napomeni")
        if getattr(self, "_okvir_pun", False):
            problemi.append("okvir: tekst silazi do lenjira - skrati napomene")
        self.fig.savefig(f"{ime}.png", dpi=dpi or self.dpi)
        self.fig.savefig(f"{ime}.pdf")
        plt.close(self.fig)
        return problemi
