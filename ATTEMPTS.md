# ATTEMPTS — šta je probano (R21)

Pre svakog predloga rešenja pročitaj ovo. Ono što je palo ne predlaže se ponovo bez novog razloga.
Format: datum / verzija — šta je probano → **radi / ne radi / delimično** — zašto.

## Opšte
- Novija three.js → **ne radi** bez prepravke (`Geometry` ne postoji u novijim); ostaje r128.

## Ramovi (HSW ram za fotografiju, „ramić“)
Izvor: čet „Ramovi za Radionicu“ (25–26.11.2026), `vajb-osnova/moduli/referenca/hsw_ram/`. Magnetni ram (barokni 95 × 74) je drugi model: `vajb-osnova/models/ram-magnet/ATTEMPTS.md`.

- 25.11 — crni L-profil 1,6 mm + bela ploča sa zubom ili lepljena → **odbačeno** (Mirko hoće ram od HSW saća, ploča ne lepljena nego da je nešto drži).
- 25.11 — saće 8 mm svuda (HSW dubina) → **previše filamenta**; 8 mm treba samo u ćelijama sa umetkom, ostalo 5 mm.
- 25.11 — saće samo spreda, iza ploče patrljci 2 mm → **ne radi** (Mirko: iza ploče mora celo saće).
- ~25.11 / v4 (`ram5.py`) — ploča ulazi odozgo kroz prorez 1,2 mm, drže je 2 opruge sa zubom (greda 2 × 18 mm, zub 0,8) → **zamenjeno** opcijom A; razlog nije zapisan.
- 26.11 / v1 opcija A (`ram_a.py`, 13×18) — ploča 1 mm zarobljena između prednjeg (saće 5 + podloga 1,2) i zadnjeg dela (3,5), **10 tipli** sa klikom na čvorovima oboda → **ne radi dovoljno dobro** (odštampano 26.11, Mirko): spojevi slabi i ima ih malo, pucaju pri rasklapanju, duge stranice bi se krivile. Lice je mnogo lepše kad je štampano na ploči štampača (licem nadole).
- 26.11 / v2 (Košnica 3D 0.10.0, `k3d/ramovi.py`) — tiple na **svim** čvorovima spoljnog oboda (30 kod 13×18), ne kroz ploču (Mirkova odluka), potporne kolone iza ploče na ~150 mm, širi ram iz komada (cigle, šav sredinom zida), ploča sa lastinim repom → **nije odštampano**.
