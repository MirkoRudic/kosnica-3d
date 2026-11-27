# ATTEMPTS — šta je probano (R21)

Pre svakog predloga rešenja pročitaj ovo. Ono što je palo ne predlaže se ponovo bez novog razloga.
Format: datum / verzija — šta je probano → **radi / ne radi / delimično** — zašto.

## Opšte
- Novija three.js → **ne radi** bez prepravke (`Geometry` ne postoji u novijim); ostaje r128.

## Ramovi (HSW ram za fotografiju, „ramić“)
Izvor: `vajb-osnova/moduli/referenca/hsw_ram/` (skripte i STATUS.md), Mirkovi 3MF u `Desktop\3D\Projekti\Ram za sliku Magnet\` i `...\Lepljenje\`.
**Nije još upisano:** pokušaji iz starih četova o ramiću van projekta (magnetni ram proba1–proba9, lepljeni ram2 v1–v5). Ti četovi se čitaju samo preko pregledača na laptopu — dopuniti kad laptop bude upaljen.

- ~25.11 / v4 (`ram5.py`) — ploča ulazi odozgo kroz prorez 1,2 mm, drže je 2 opruge sa zubom (greda 2 × 18 mm, zub 0,8) → **zamenjeno** opcijom A; razlog nije zapisan.
- 26.11 / v1 opcija A (`ram_a.py`, 13×18) — ploča 1 mm zarobljena između prednjeg (saće 5 + podloga 1,2) i zadnjeg dela (3,5), **10 tipli** sa klikom na čvorovima oboda → **ne radi dovoljno dobro** (odštampano 26.11, Mirko): spojevi slabi i ima ih malo, duge stranice bi se krivile.
- 26.11 / v2 (Košnica 3D 0.10.0, `k3d/ramovi.py`) — tiple na **svim** čvorovima spoljnog oboda (30 kod 13×18), ne kroz ploču (Mirkova odluka), potporne kolone iza ploče na ~150 mm, širi ram iz komada (cigle, šav sredinom zida), ploča sa lastinim repom → **nije odštampano**.
