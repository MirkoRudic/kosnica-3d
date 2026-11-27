Važe pravila iz `RULES.md` u repou MirkoRudic/vajb-osnova (za modele i štampu i `RULES_3D_PRINTING.md`). Ovde su arhitektura, zamke i izuzeci. Šta app radi iz ugla korisnika je u `SPECIFICATION.md` — svaka izmena ponašanja prvo tamo. Dokle smo stigli: `STATUS.md`. Šta je već probano i nije radilo: `ATTEMPTS.md` — pročitati pre predloga rešenja.

# Košnica 3D

Lokalna app za pravljenje modela za 3D štampu u radionici Ožiljak. Korisnik bira vrstu projekta, menja mere
klizačima i vidi model uživo. Kasnije model izvozi kao 3MF za Creality Print.
Štampači: **K1 Max** (ploča 300 mm, bez CFS) i **K2 Plus** (350 mm, CFS). Slajser: Creality Print 7.x.

Pre rada pročitaj:
- `RULES.md` iz repoa MirkoRudic/vajb-osnova (pravila za aplikacije);
- `RULES_3D_PRINTING.md` iz istog repoa (pravila za modele i štampu, šifre D);
- ovaj fajl.

Moduli za 3MF i proveru modela su u `vajb-osnova/moduli/model3d/` (`mf3.py`, `provera_3mf.py`, `spojevi.py`).
Primeri pravih 3MF fajlova iz Creality Print-a su u `moduli/model3d/primeri/`.

## Gde radi
- Računar u radionici: `desktop-fk7e7jt`, folder `C:\Users\zzroz\Desktop\VAJB\kosnica-3d`.
- Folder je git klon ovog repoa i ažurira se iz app (V2/V3).
- Port **8801** (upisan u `APPLICATIONS.md`).
- Pokretanje: `Kosnica3D.vbs`.
  - Pravi i osvežava prečicu „Košnica 3D“ na Desktopu.
  - Bez `.venv` prvo pokreće `instaliraj.bat` (venv + `requirements.txt`: pystray, pillow, numpy, manifold3d, shapely, trimesh, matplotlib). Pri ažuriranju `update.py` sam pokrene pip kad se `requirements.txt` promeni.
- Ranije je app bila strana (artifact) na claude.ai. Od 23.11.2026 je lokalna app, kao Nadzor i Print (Mirkova odluka).
- Kasnije je plan da ide i na sajt radionice (vidi projektni dokument `sajt-radionice-koraci.md`).

## Arhitektura
| Fajl | Šta radi |
|---|---|
| `kosnica3d.pyw` | Server (stdlib `ThreadingHTTPServer`) na 127.0.0.1:8801. Služi `static/`, otvara Edge `--app` prozor i ikonicu pored sata (Otvori/Ugasi). Ima `/health` (app, version, pid, label), `POST /api/shutdown` (`keep_window` za restart) i `GET/POST /api/update`. Pokretanje sa `--restart` gasi stari server i diže novi bez novog prozora. |
| `k3d/applog.py` | Dnevnik servera, `data/logs/kosnica-3d_YYYY-MM-DD.log` (kopija modula iz vajb-osnova). |
| `k3d/runlock.py` | Sprečava dva servera (kopija modula). |
| `k3d/update.py` | `git pull --ff-only` + restart (kopija modula iz Nadzora, ume da nađe git i u `%LOCALAPPDATA%\Programs\Git`). |
| `k3d/version.py` | `APP_NAME`, `VERSION` (i u `static/index.html` konstanta `VERSION` — podići obe). |
| `k3d/ramovi.py`, `k3d/ramovi_nacrt.py` | HSW ram iz komada: geometrija (manifold3d), sažetak, izvoz STL/3MF, nacrt. |
| `k3d/model3d/`, `k3d/tehnicki_crtez.py` | Kopije modula iz vajb-osnova (mf3 1.1, provera_3mf, tehnicki_crtez 1.12). |
| `k3d/osnova/` | Mirkovi 3MF iz Creality Print-a kao osnova izvoza: `ram_k1.3mf` (= ram2_v5, K1 Max 0.12 Ramovi), `ram_k2.3mf` (= Svi_ukrasi_v13, K2 Plus 0.20). |
| `static/index.html` | **Cela app u jednom fajlu**: CSS, Tabler sprite, JS. Ovo je izvor; ručno se menja. |
| `static/three.min.js` | three.js r128, lokalno, bez interneta. |
| `izvor/src.html`, `izvor/build.py` | Stari mokap sa claude.ai iz koga je nastao `index.html`. **Ne gradi se više**, samo za istoriju. |
| `kosnica.ico`, `ikona.ico` | Ikonica app (ista porodica kao Nadzor i Print). |

Podaci u pregledaču (`localStorage`, prefiks `kosnica3d`):
- tema;
- dnevnik strane, po danima (`kosnica3d_log_YYYY-MM-DD`);
- stanje ažuriranja (`kosnica3d.upd`).

Stanje projekta (`S`, mere i izbori) **se ne čuva** između pokretanja.

## Šta app pravi (režimi u zaglavlju)
Ceo izbor je u objektu `S` u `index.html`: `S.mode` je `hsw`, `orn`, `box`, `logo` ili `ram`, a `S.printer` je `k1` ili `k2`.

1. **HSW** (Honeycomb Storage Wall, zidna mreža šestougaonih ćelija).
   - Podrežimi: **projekat**, **panel** i **elementi**.
     - **Projekat:** zadaje se ceo zid (širina × visina), app ga deli na panele koji staju na ploču izabranog štampača.
     - **Panel:** jedan panel.
     - **Elementi** (`EL`): kuka, dvostruka kuka, polica, čaša, fioka, kutija s poklopcem, držači za odvijače, imbus ključeve, klešta i makaze, kalem filamenta, lepljivu traku, namotač kablova.
   - Konstante mreže: `P = 23.6` (korak), `RI = 20/√3`, `T = 8` (debljina), `FR = 3.6` (ravna ivica).
   - Ćelije se mogu uklanjati klikom, a ivice paneli imaju ravne trake (`edges`).
   - Statistika: broj ćelija i procena grama (`G_PER_CELL`, `G_PER_H`).
   - Šare na ravnim površinama (`S.pat`) važe i za kutije i HSW elemente.
2. **Ornament** (ukras za jelku, mrežasta ljuska).
   - Oblici (`SHAPE_NAMES`): kugla, jaje, kap, srce, zvezda (5/6/8 krakova), jelka, mesec, dijamant i svoj oblik (uvoz SVG).
   - Šare (`PATTERNS`): saće, pletivo, krugovi, trougao, romb, krljušt, voronoi, spirala, puna; može i radijalno.
   - Mreža se pravi kao slika: alfa → konture → ekstruzija 1,2 mm (`NET_T`) → savija se na ljusku. Dva dela, prednji i zadnji.
   - Kačenje (`HANG`): kapica, **nosač kapice v6** ili šraf (matica sa alkom spaja obe polovine).
     - Mere nosača kapice (trenutno v8) i šta nije radilo: `vajb-osnova/models/ukrasi-za-jelku/` (STATUS.md, ATTEMPTS.md). App još crta stari v6, koji je pao na probi pada sa 1 m.
   - **Presa** (čep + kalup) za oblikovanje mreže.
   - Simulacija sklapanja: dugme Play.
3. **Kutija** (`S.box`).
   - Spoljne mere, zid, dno, pregrade X/Y.
   - Poklopci (`LIDS`): bez, nasadni, šarke (kutija i poklopac u jednom komadu), klizni, klik.
   - Hvataljke (`GRIPS`): jezičak, dugme, udubljenje.
   - Zazor (`gap`, početno 0,3) i zub klik spoja (`snap`, početno 1).
   - Presek klik spoja se crta posebno (`drawPresek`).
4. **Logo** (slika → boje → slojevi).
   - Uvezena slika se svede na 2–N boja. Svaka boja dobija svoj visinski pojas, kao kod štampe sa promenom filamenta (K1 pauza, K2 CFS).
   - Dodaci (`EXTRAS`): magnet (Ø i dubina), privezak, igla.
   - Prikaz plana visina na kojima se menja filament.

5. **Ramovi** (`S.ram`, od 0.10.0) — HSW ram za fotografiju.
   - Saće: prednji deo 5 + podloga 1,2 mm, zadnji 3,5 mm; ploča 1 mm (beli PLA) zarobljena između, čist pravougaonik kroz sredinu ćelija venca. Tiple sa klikom na svim čvorovima spoljnog oboda (ne kroz ploču — Mirkova odluka). Potporne kolone saća iza ploče na ~150 mm.
   - Kačenje u ćeliji na sredini gore (umetak K1 ključaonica / K2 testera), info ćelija dole levo/desno (nosač I2 + pločica 60×25 sa kanalom za papirić).
   - Formati 9×13 … 20×30, A4 ili ručno; položeno/uspravno.
   - Širi ram od ploče štampača se seče na komade: prednji i zadnji deo na različitim kolonama (cigle, šav sredinom zida, bez tipli uz šav), ploča se deli lastinim repom iznad potporne kolone. Visina se ne deli: mora da stane na ploču (K1 ≈ 200 mm korisne visine, K2 ≈ 245); app javlja kad ne staje.
   - **Geometrija i izvoz su u Pythonu.** `POST /api/ramovi/proracun` vraća sažetak i mreže (base64) za prikaz; `POST /api/ramovi/izvoz` piše u `data/izvoz/<naziv>_<datum>/` STL po delu, 3MF po ploči štampača (`<naziv>_crni_N`, `<naziv>_beli_N`, na osnovi iz `k3d/osnova/`), proveru `provera_3mf` i nacrt PNG+PDF; `POST /api/ramovi/otvori` otvara folder.
   - Lice rama je na z = 0 i gleda ka −z: „levo“ gledano spreda je veliko x. `tehnicki_crtez` „spreda“ gleda sa +z, pa nacrt crta ogledalo (`Ram(za_crtez=True)`).

Za svaki režim app prikazuje:
- spisak delova za štampu sa dugmetom za preuzimanje po delu i „Izvezi sve“;
- preporuke štampe po delu i materijalu (`MATS`: PLA, PETG, ASA, Silk; `PARTS`), označene kao „polazno“;
- težinu i procenu.

## Poznate zamke
- **Izvoz radi samo u Ramovima.** U ostalim režimima dugmad za preuzimanje i „Izvezi sve“ samo pokazuju poruku „U mokapu izvoz nije aktivan“. Sledeći veliki korak:
  - 3MF sa podešavanjima štampe po `RULES_3D_PRINTING.md`, kroz `moduli/model3d/mf3.py`;
  - provera kroz `provera_3mf.py` pre slanja;
  - ime fajla i objekta = ime dela, jer Nadzor po tom imenu nalazi projekat dok štampa traje.
- Mere i zazori u app su polazne (PRAVILA_3D D1/D2). Potvrđuju se tek probnim komadom i šublerom.
- Ćelija HSW 20 mm i umetak 19,7 su iz HSW rama (repo vajb-osnova, `moduli/referenca/hsw_ram/`).
- three.js je r128. Novije verzije menjaju API (npr. `Geometry` ne postoji), pa se ne menja bez razloga.
- **Nije provereno u Creality Print-u:** 3MF koji pravi `mf3.postavi_objekte` i K2 osnova (sloj 0,20) za ramove. Prvi izvoz otvoriti u slajseru i pogledati podešavanja.
- Edge `--app` prozor koristi svoj profil u `data/edge`.

## Odstupanja od RULES.md (stanje 26.11.2026, za sređivanje)
| Šifra | Kako je sada |
|---|---|
| UI12 | Podešavanja imaju samo „Opšte“ (Tema, Štampač, Verzija) i „Dnevnik“. Nedostaju O programu i Deinstaliraj; redosled nije po pravilu; dnevnik nije u posebnom prozoru. |
| L1 | Dnevnik strane je u `localStorage`, ne u `data/logs/` (server ima pravi dnevnik u `data/logs/`). |
| F9 | Server ne proverava `Host`/`Origin` (`moduli/localguard.py`). |
| P3 | Nije isključen Edge pomoćnik za pisanje (`writingsuggestions`) ni mini meni nad označenim tekstom (`winsetup.edge_prefs`). |
| P1 | Prečica se pravi u `.vbs`, ne kroz `winsetup.refresh`; app u Task Manager-u je „Python“. |
| P9 | Nema Deinstaliraj. |
| V5 | Nema automatskog ažuriranja; ide preko dugmeta Proveri/Ažuriraj (V3). |
| UI1 | Nedostaje `overflow-x:hidden`. |
| UI16 | Stanje projekta se gubi pri zatvaranju. |
| UI17 | Nema Poništi/Ponovi. |

## Ažuriranje na računaru u radionici
- Mirko: Podešavanja → Verzija → „Proveri“ / „Ažuriraj odmah“.
- Bez Mirka:
  1. push na GitHub;
  2. u ugrađenom pregledaču na `http://127.0.0.1:8801` uradi `fetch('/api/update',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})`. App povlači kod i restartuje se.
- Commit autor: `Claude <noreply@anthropic.com>`; pravi mejl blokira GitHub. Force push nije dozvoljen.
