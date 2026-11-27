# Košnica 3D — specifikacija

Šta app radi iz ugla korisnika. Svaka izmena ponašanja prvo se upiše ovde, pa u kod.
Oblik: **kad uradim X → desi se Y**. Tehnika u `AGENTS.md`, gde smo stali u `STATUS.md`, pravila za modele `vajb-osnova/RULES_3D_PRINTING.md`.

## Svrha
Pravljenje modela za 3D štampu u radionici Ožiljak bez CAD programa: biram vrstu projekta, menjam mere klizačima, vidim model uživo, dobijem fajl za Creality Print sa podešavanjima. Štampači K1 Max (300 mm) i K2 Plus (350 mm, CFS).

## 1. Opšte
- Prečica „Košnica 3D“ → app u sopstvenom prozoru, ikonica pored sata (Otvori/Ugasi).
- Zaglavlje: režimi **HSW**, **Ornament**, **Kutija**, **Logo**, **Ramovi**; izbor štampača (K1/K2) menja granice ploče i plan boja.
- Svaki režim: 3D prikaz (okretanje mišem), spisak delova za štampu sa preuzimanjem po delu i „Izvezi sve“, preporuke štampe po delu i materijalu (PLA, PETG, ASA, Silk) označene „polazno“, težina i procena.
- Podešavanja (zupčanik): tema, štampač, dnevnik, verzija i ažuriranje.

## 2. HSW (zidna mreža šestougaonih ćelija)
- **Projekat**: unesem zid (širina × visina) → app ga deli na jednake panele koji staju na ploču izabranog štampača; spisak štampe grupisan.
- **Panel**: jedan panel; klik na ćeliju je uklanja (izrez za utičnicu).
- **Elementi**: kuke, polica, čaša, fioka, kutija s poklopcem, držači alata, kalem filamenta, traka, namotač kablova — svaki sa podesivim merama.
- Šare (otvori) na ravnim površinama elemenata i kutija.

## 3. Ornament (ukras za jelku)
- Biram oblik (kugla, jaje, kap, srce, zvezda, jelka, mesec, dijamant ili svoj SVG) i šaru (saće, pletivo, krugovi, voronoi, spirala…), debljinu rebra i ivice.
- Štampa se ravna mreža, greje se i utiskuje **presom** (čep sa rukohvatom + kalup), pa se spoje dve polovine.
- Kačenje: kapica, **nosač kapice v6** (trenutne mere i istorija: `vajb-osnova/models/ukrasi-za-jelku/`) ili šraf.
- Mreža za štampu u malom okviru dole desno; Play pokazuje oblikovanje i spajanje.

## 4. Kutija
- Spoljne mere, zid, dno, pregrade; poklopac: bez, nasadni, šarke, klizni, **klik**; hvataljka: jezičak, dugme, udubljenje.
- Zazor (polazno 0,3) i zub klik spoja (0,4–1,6, polazno 1); kod Klik dole desno presek spoja sa merama.
- Donja traka: spoljne i unutrašnje mere, zapremina, filament, vreme, da li staje na ploču.

## 5. Logo
- Uvezem sliku (PNG, JPG, WEBP, SVG) → app prepozna 1–5 boja i ukloni pozadinu.
- Svaka boja svoj visinski pojas (debljina i redosled podesivi); prva boja je osnova.
- Dodatak: magnet (Ø i debljina, upozorenje kad je osnova pretanka), privezak, igla.
- Plan boja: na kojoj visini K1 pauzira za ručnu promenu, odnosno K2 menja kroz CFS.
- Napomena o dozvoli vlasnika za tuđi znak.

## 6. Ramovi (od 0.10.0)
- Kad izaberem format (9×13 … 20×30, A4, ručno) i položeno/uspravno → vidim HSW ram sa pločom za fotografiju, kačenjem gore i info ćelijom dole.
- Kad je ram širi od ploče štampača → app ga sama seče na komade (cigle, lastin rep); kad je viši nego što staje → javlja da ne staje.
- Kad kliknem Izvezi → u `data/izvoz/<naziv>_<datum>/` dobijem STL po delu, 3MF po ploči (crni i beli filament) spreman za Creality Print, izveštaj provere i nacrt; app otvara folder.

## Namerno ne radi
- Ne čuva stanje projekta između pokretanja (otvoreno, UI16).

## Nije urađeno / nije provereno
- **Izvoz 3MF za HSW, Ornament, Kutiju i Logo** — dugmad još samo javljaju „U mokapu izvoz nije aktivan“. Plan: 3MF sa podešavanjima kroz `moduli/model3d/mf3.py`, provera `provera_3mf.py`, ime objekta = ime dela (Nadzor ga tako nalazi).
- Mere HSW (otvor 20, korak 23,6, debljina 8) i svi zazori su polazni — potvrđuju se probnim komadom.
