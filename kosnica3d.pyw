"""Košnica 3D - pokretanje (Kosnica3D.vbs ili dupli klik).

Server na 127.0.0.1:8801 služi stranu iz static/, prozor u Edge --app, ikonica pored sata (Otvori / Ugasi).
Radi bez interneta i bez prijave.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA = APP_DIR / "data"
STATIC = APP_DIR / "static"
PORT = int(os.environ.get("K3D_PORT", "8801"))
URL = f"http://127.0.0.1:{PORT}/"
TITLE = "Košnica 3D"
sys.path.insert(0, str(APP_DIR))

from k3d import applog, update, version  # noqa: E402

VERSION = version.VERSION

applog.setup(DATA / "logs", "kosnica-3d")
log = applog.get("main")
applog.auto_trim(200)


def health():
    try:
        with urllib.request.urlopen(URL + "health", timeout=1) as r:
            return b"kosnica-3d" in r.read()
    except Exception:
        return False


def _windows():
    """Visible Edge/Chrome --app windows whose title starts with TITLE."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    found = []

    def cb(h, _):
        n = u.GetWindowTextLengthW(h)
        if n and u.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(h, b, n + 1)
            c = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(h, c, 64)
            if b.value.startswith(TITLE) and c.value.startswith("Chrome_WidgetWin"):
                found.append(h)
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return found


def focus_window():
    try:
        w = _windows()
        if w:
            import ctypes
            u = ctypes.windll.user32
            if u.IsIconic(w[0]):
                u.ShowWindow(w[0], 9)
            u.SetForegroundWindow(w[0])
            return True
    except Exception as e:
        log.warning("focus window: %s", e)
    return False


def close_window():
    """P4: gašenje zatvara i prozor app."""
    try:
        import ctypes
        w = _windows()
        for h in w:
            ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
        log.info("closed %d app window(s)", len(w))
    except Exception as e:
        log.warning("close window: %s", e)


def open_window():
    if focus_window():
        return
    for exe in [shutil.which("msedge"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe"]:
        if exe and Path(exe).exists():
            subprocess.Popen([exe, f"--app={URL}", f"--user-data-dir={DATA / 'edge'}", "--no-first-run",
                              "--no-default-browser-check", "--disable-sync", "--window-size=1400,900"])
            return
    webbrowser.open(URL)


def git_ready():
    return (APP_DIR / ".git").exists() and bool(update.git_exe())


def stop_running():
    """--restart (V2): stop the running server, its window stays and reloads itself."""
    try:
        req = urllib.request.Request(URL + "api/shutdown", data=json.dumps({"keep_window": True}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=3).read()
    except Exception as e:
        log.info("restart: stop request: %s", e)
    for _ in range(60):
        if not health():
            return
        time.sleep(0.5)
    log.warning("restart: old server still answers")


# ---------- Ramovi (HSW ram iz komada) ----------
IZVOZ = DATA / "izvoz"


def _ram_iz(body):
    from k3d import ramovi
    f = lambda k, d, lo, hi: min(max(float(body.get(k) or d), lo), hi)
    naziv = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(body.get("naziv") or "hsw_ram"))[:40] or "hsw_ram"
    return ramovi.Ram(sirina=f("sirina", 178, 40, 1500), visina=f("visina", 127, 40, 1500),
                      uspravno=bool(body.get("uspravno")), stampac="k2" if body.get("stampac") == "k2" else "k1",
                      kacenje="K1" if body.get("kacenje") == "K1" else "K2",
                      info=body.get("info") if body.get("info") in ("levo", "desno", "nema") else "levo", naziv=naziv)


def ram_proracun(body):
    import base64
    import numpy as np
    r = _ram_iz(body)
    delovi = []
    for d in r.delovi:
        me = d.m.to_mesh()
        v = np.asarray(me.vert_properties[:, :3], dtype=np.float32)
        i = np.asarray(me.tri_verts, dtype=np.uint32)
        delovi.append({"ime": d.ime, "boja": d.boja, "v": base64.b64encode(v.tobytes()).decode(),
                       "i": base64.b64encode(i.tobytes()).decode()})
    return {"ok": True, "naziv": r.naziv, "sazetak": r.sazetak(), "delovi": delovi}


def ram_izvoz(body):
    r = _ram_iz(body)
    gr = r.greska()
    if gr:
        return {"ok": False, "error": gr}
    folder = IZVOZ / f"{r.naziv}_{time.strftime('%Y%m%d-%H%M%S')}"
    from k3d import ramovi
    rez = ramovi.izvezi(r, folder)
    greske = [f"{ime}: {m}" for ime, n in rez["provera"].items() for lvl, m in n if lvl == "GREŠKA"]
    proveri = [f"{ime}: {m}" for ime, n in rez["provera"].items() for lvl, m in n if lvl == "PROVERI"]
    log.info("ramovi: izvoz %s, %d fajlova, %d grešaka", folder.name, len(rez["fajlovi"]), len(greske))
    return {"ok": not greske, "folder": str(folder), "ime": folder.name, "fajlovi": rez["fajlovi"],
            "greske": greske, "proveri": proveri, "nacrt_greska": rez.get("nacrt_greska"),
            "error": "Provera 3MF je našla greške (detalji u dnevniku)." if greske else None}


def otvori_folder(path):
    p = Path(path).resolve()
    if IZVOZ.resolve() not in p.parents or not p.is_dir():
        return {"ok": False, "error": "Folder nije iz izvoza."}
    if sys.platform == "win32":
        os.startfile(str(p))  # noqa: S606 (lokalni folder izvoza)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])
    return {"ok": True}


def make_server(shutdown):
    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(STATIC), **k)

        def log_message(self, fmt, *args):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def _json(self, obj, code=200):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/health":
                return self._json({"app": "kosnica-3d", "version": VERSION, "pid": os.getpid(), "label": version.label()})
            if self.path == "/api/update":
                if not git_ready():
                    return self._json({"ok": False, "error": "Ažuriranje nije podešeno na ovom računaru."})
                return self._json(update.status(VERSION))
            return super().do_GET()

        def do_POST(self):
            if self.client_address[0] != "127.0.0.1":
                return self._json({"error": "not found"}, 404)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except ValueError:
                body = {}
            if self.path == "/api/shutdown":
                self._json({"ok": True})
                threading.Thread(target=shutdown, args=(bool(body.get("keep_window")),), daemon=True).start()
                return
            if self.path == "/api/update":
                if not git_ready():
                    return self._json({"ok": False, "error": "Ažuriranje nije podešeno na ovom računaru."})
                r = update.apply(VERSION)
                return self._json({"ok": r.get("ok"), "changed": r.get("changed"),
                                   "error": None if r.get("ok") else "Ažuriranje nije uspelo (detalji u dnevniku)."})
            ram = {"/api/ramovi/proracun": ram_proracun, "/api/ramovi/izvoz": ram_izvoz,
                   "/api/ramovi/otvori": lambda b: otvori_folder(b.get("folder") or "")}.get(self.path)
            if ram:
                try:
                    return self._json(ram(body))
                except ImportError as e:
                    log.exception("ramovi: nedostaje biblioteka")
                    return self._json({"ok": False, "error": f"Nedostaje biblioteka ({e.name}). Pokreni ažuriranje ili pip install -r requirements.txt."})
                except Exception:
                    log.exception("ramovi: %s", self.path)
                    return self._json({"ok": False, "error": "Ram nije napravljen (detalji u dnevniku)."})
            self._json({"error": "not found"}, 404)

    return ThreadingHTTPServer(("127.0.0.1", PORT), H)


def main():
    restart = "--restart" in sys.argv
    if restart:
        log.info("restart requested")
        stop_running()
    elif health():
        open_window()
        return
    from k3d.runlock import RunLock
    lock = RunLock(DATA / "RUN.lock", max_age_h=24 * 365)
    for _ in range(40 if restart else 1):
        if lock.acquire():
            break
        time.sleep(0.5)
    else:
        log.info("another instance is starting, exit")
        return
    update.init(APP_DIR, version_file="k3d/version.py", launcher="kosnica3d.pyw")
    log.info("%s starting", version.label())
    tray = {"icon": None}
    done = threading.Event()

    def shutdown(keep_window=False):
        log.info("shutdown requested (keep_window=%s)", keep_window)
        time.sleep(0.5)
        if not keep_window:
            close_window()
        done.set()
        if tray["icon"]:
            tray["icon"].stop()

    srv = make_server(shutdown)
    threading.Thread(target=srv.serve_forever, name="web", daemon=True).start()
    log.info("server %s", URL)
    if not restart:
        open_window()
    try:
        import pystray
        from PIL import Image
        icon = pystray.Icon("kosnica-3d", Image.open(APP_DIR / "kosnica.ico"), TITLE, pystray.Menu(
            pystray.MenuItem("Otvori", lambda: open_window(), default=True),
            pystray.MenuItem("Ugasi", lambda: shutdown())))
        tray["icon"] = icon
        icon.run()
    except ImportError:
        log.warning("pystray not installed, no tray icon")
    done.wait()
    srv.shutdown()
    lock.release()
    log.info("stopped")
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("start failed")
        raise
