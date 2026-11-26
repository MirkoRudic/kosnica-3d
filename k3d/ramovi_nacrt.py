"""Nacrt HSW rama po R15 (tehnicki_crtez): spreda, sa strane, otpozadi, odozdo, izometrija, okvir."""
from shapely.geometry import box

from . import ramovi as R
from . import tehnicki_crtez as tc


def _nacrt(r, ime, naslov, razmera):
    c = tc.Crtez(naslov)
    c.margina = 6
    if razmera:
        c.razmera = razmera
    pred = [d for d in r.delovi if "prednji" in d.ime]
    zad = [d for d in r.delovi if "zadnji" in d.ime]
    plo = [d for d in r.delovi if "_ploca" in d.ime]
    kuk = [d for d in r.delovi if "umetak_K" in d.ime]
    nos = [d for d in r.delovi if "I2_nosac" in d.ime]
    pin = [d for d in r.delovi if "info_plocica" in d.ime]
    TP = ["#262626", "#3f3f3f"]; TZ = ["#5c5c5c", "#7a7a7a"]; PL = ["#cfe0f5", "#b4cdec"]

    def dodaj(lst, boje, pogledi, z, **kw):
        for k, d in enumerate(lst):
            b = boje[k % len(boje)] if isinstance(boje, list) else boje
            tc.iz_modela(c, d.m, boja=b, izometrija=False, pogledi=pogledi, z=z, **kw)

    dodaj(zad, TZ, ("spreda",), 1); dodaj(plo, PL, ("spreda",), 2); dodaj(pred, TP, ("spreda",), 3)
    dodaj(kuk, "#333333", ("spreda",), 4); dodaj(nos, TP[0], ("spreda",), 5); dodaj(pin, "#f4f4f4", ("spreda",), 6)
    dodaj(pin, "#f4f4f4", ("pozadi",), 1); dodaj(nos, TP[0], ("pozadi",), 2); dodaj(pred, TP, ("pozadi",), 3)
    dodaj(plo, PL, ("pozadi",), 4); dodaj(kuk, "#333333", ("pozadi",), 5); dodaj(zad, TZ, ("pozadi",), 6)
    xh = r.center(*r.HANG)[0]
    dodaj(pred, TP, ("strana",), 1, strana_na=xh); dodaj(plo, PL, ("strana",), 2, strana_na=xh)
    dodaj(zad, TZ, ("strana",), 3, strana_na=xh); dodaj(kuk, "#333333", ("strana",), 4, strana_na=xh)
    dodaj(kuk, "#333333", ("odozdo",), 1); dodaj(zad, TZ, ("odozdo",), 2); dodaj(plo, PL, ("odozdo",), 3)
    dodaj(pred, TP, ("odozdo",), 4); dodaj(nos, TP[0], ("odozdo",), 5); dodaj(pin, "#f4f4f4", ("odozdo",), 6)

    ob = r.outline.bounds
    s = c.spreda
    s.kota_h(ob[0], ob[2], ob[3] + 10, f"{ob[2] - ob[0]:.1f}")
    s.kota_v(ob[1] - (13 if r.INFO else 0), ob[3], ob[0] - 6, f"{ob[3] - ob[1] + (13 if r.INFO else 0):.1f}")
    cx, cy = r.center(r.NX // 2, 0)[0], (23.6 + (r.NY - 2) * R.P + 11.8) / 2
    s.oblik(box(cx - r.W / 2, cy - r.H / 2, cx + r.W / 2, cy + r.H / 2), "none", ivica=tc.CRVENO, crtkano=True, z=8)
    s.kota_h(cx - r.W / 2, cx + r.W / 2, cy - r.H / 2 + 6, f"{r.W:g}")
    s.kota_v(cy - r.H / 2, cy + r.H / 2, cx - r.W / 2 + 6, f"{r.H:g}", desno=True)
    st = c.strana
    st.kota_h(0, R.TOT, ob[3] + 10, f"{R.TOT:g}".replace(".", ","))
    pz = c.pozadi
    ox = r.center(r.NX // 2, 0)[0]
    m = lambda x: -x
    pz.kota_h(m(r.PX1), m(r.PX0), ob[3] + 10, f"ploča {r.PX1 - r.PX0:.1f}")
    pz.kota_v(r.PY0, r.PY1, m(r.PX0) + 8, f"{r.PY1 - r.PY0:.1f}", desno=True)

    c.izo_ugao = (22, -32)
    for lst, b in ((pred, (0.17, 0.17, 0.17)), (zad, (0.36, 0.36, 0.36)), (plo, (0.85, 0.90, 0.97)),
                   (kuk, (0.24, 0.24, 0.24)), (nos, (0.17, 0.17, 0.17)), (pin, (0.95, 0.95, 0.95))):
        for d in lst:
            c.izometrija(d.m, boja=b)
    sz = r.sazetak()
    np_, nz, npl = len(pred), len(zad), len(plo)
    delovi = [f"Prednji deo{'' if np_ == 1 else f' ×{np_}'}, crni PLA",
              f"Zadnji deo{'' if nz == 1 else f' ×{nz}'}, crni PLA",
              (f"Ploča{'' if npl == 1 else f' ×{npl}'} 1 mm, beli PLA", tc.PLAVO),
              f"Umetak {r.kacenje}, nosač I2 + info pločica"]
    nap = [f"{sz['tiple']} tipli na obodu, {sz['potpore']} potp. kolona, ploča slobodna"]
    if np_ > 1:
        nap.append("Komadi kao cigle: spojeve prednjeg premošćuje zadnji")
    if npl > 1:
        nap.append("Ploča spojena lastinim repom iznad potpore")
    nap.append(f"Crni ~{sz['crni']['g']} g, beli ~{sz['beli']['g']} g, ~{sz['crni']['rsd'] + sz['beli']['rsd']} RSD")
    c.okvir(delovi=delovi, napomene=nap,
            legenda=[("tamno: prednji · sivo: zadnji · plavo: ploča · crveno: korisno", tc.CRNO)])
    return c, c.sacuvaj(ime)


def nacrt(r, ime, naslov=None):
    """Bira najkrupniju standardnu razmeru u kojoj i izometrija staje (R15: svi pogledi ista razmera)."""
    if not r.za_crtez and r.info != "nema":   # "spreda" u tehnicki_crtez gleda sa +z: crta se ogledalo
        import dataclasses
        r = dataclasses.replace(r, za_crtez=True)
    ob = r.outline.bounds
    naslov = naslov or f"HSW RAM {r.W:g}×{r.H:g}" + (" IZ KOMADA" if len([d for d in r.delovi if "prednji" in d.ime]) > 1 else "")
    razmera = None
    for _ in range(4):
        c, problemi = _nacrt(r, ime, naslov, razmera)
        if not any("izometrija umanjena" in p for p in problemi):
            return problemi
        razmera = next(k for k in (1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10, 15, 20) if k > c._n)
    return problemi
