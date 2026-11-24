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
