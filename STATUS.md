# Košnica 3D — stanje (26.11.2026)

Verzija **0.10.0**. Računar u radionici `desktop-fk7e7jt`, `C:\Users\zzroz\Desktop\VAJB\kosnica-3d`, port 8801, git klon ovog repoa, ažuriranje iz Podešavanja → Verzija.
Nastavak u novom četu: pročitaj `AGENTS.md`, `SPECIFICATION.md`, ovaj fajl; pravila `vajb-osnova/RULES.md` i `RULES_3D_PRINTING.md`.

## Poslednje urađeno
- 26.11 (0.10.0): režim **Ramovi** — HSW ram za fotografiju iz komada (tiple na obodu, potporne kolone, cigle kad je ram širi od ploče, ploča sa lastinim repom). Pravi izvoz: STL po delu, 3MF po ploči (crni/beli) na Mirkovim 3MF-ovima iz `k3d/osnova/`, `provera_3mf`, nacrt PNG+PDF u `data/izvoz/`.
- 24.11: lokalna app (ranije artifact na claude.ai), ažuriranje iz app, ikonica pored sata.
- Režimi HSW, Ornament (nosač kapice v6, presa), Kutija (klik poklopac sa presekom), Logo (slojevi boja, magnet).

## Odluke
- Lokalna app kao Nadzor i Print (23.11); kasnije i na sajtu radionice (`sajt-radionice-koraci.md`).
- Odvojena od Košnice Print.
- Pravila za modele i štampu su u `RULES_3D_PRINTING.md`; moduli `moduli/model3d/`.

## Otvoreno (redom)
1. **Izvoz 3MF za HSW, Ornament, Kutiju i Logo** (Ramovi ga imaju od 0.10.0) — isti put: geometrija u Pythonu, osnova iz `k3d/osnova/`, `provera_3mf`.
1a. Ramovi: prvi probni ram odštampati i izmeriti (zazor tipli, ploča 1 mm, šav cigli).
2. Odstupanja od pravila iz `AGENTS.md`: UI12 (O programu, Deinstaliraj, dnevnik u prozoru), L1 (dnevnik strane u `data/logs`), F9, P3, P1, P9, V5, UI1, UI16 (čuvanje projekta), UI17 (Poništi/Ponovi).
3. Probni komadi za potvrdu mera HSW i zazora kutije.
4. Kako se nosač kapice pričvršćuje između presovanih polovina (lepak ili žleb) — nije rešeno.

## Nije provereno
- Nijedan model iz app još nije odštampan.
