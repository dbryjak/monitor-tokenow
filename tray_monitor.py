"""
Monitor Tokenów — ikona w zasobniku systemowym (tray)
=====================================================
Uruchomienie: pythonw tray_monitor.py   (bez okna konsoli)
              python  tray_monitor.py   (z konsolą do debugowania)

Klik na ikonę przy zegarku → otwiera / ukrywa okienko.
Prawy klik → menu: przełącz PRO/API, zakończ.
"""

import ctypes
import json
import re
import threading
import time
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont


def _ciemny_pasek_tytulu(root: tk.Tk) -> None:
    """Ciemny pasek tytułu (Windows 10 20H1+ / Windows 11)."""
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        DARK = ctypes.c_int(1)
        # atrybut 20 = DWMWA_USE_IMMERSIVE_DARK_MODE (Win10 20H1+)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(DARK), ctypes.sizeof(DARK))
    except Exception:
        pass  # starszy Windows — ignoruj

# ── Ścieżki ───────────────────────────────────────────────────────────────────
CONFIG_JSON  = Path(r"D:\MOJE PROJEKTY\Monitor-Tokenow\src\config.json")
CLAUDE_DIR   = Path.home() / ".claude"
DZISIAJ_JSON = Path(r"D:\MOJE PROJEKTY\Monitor-Tokenow\data\dzisiaj.json")
ODSWIEZAJ_CO = 30  # sekund

CENNIK = {
    "claude-sonnet-4-6":         {"i": 3.00,  "o": 15.00, "cc": 3.75,  "cr": 0.30},
    "claude-opus-4-7":           {"i": 15.00, "o": 75.00, "cc": 18.75, "cr": 1.50},
    "claude-haiku-4-5-20251001": {"i": 0.80,  "o": 4.00,  "cc": 1.00,  "cr": 0.08},
    "claude-haiku-4-5":          {"i": 0.80,  "o": 4.00,  "cc": 1.00,  "cr": 0.08},
}
DOMYSLNY = "claude-sonnet-4-6"

# ── Kolory ────────────────────────────────────────────────────────────────────
K = {
    "tlo":         "#1e1e2e",
    "tlo2":        "#2a2a3e",
    "tlo_wyszarz": "#252525",
    "tekst":       "#e0e0f0",        # jasny — dobry kontrast
    "tekst2":      "#a0a0c0",        # drugi plan
    "tekst_dim":   "#505070",        # wyszarzony
    "zielony":     "#a6e3a1",
    "zolty":       "#f9e2af",
    "czerwony":    "#f38ba8",
    "niebieski":   "#89b4fa",
    "cyan":        "#89dceb",
    "szary":       "#585b70",
    "pro_wl":      "#2d6a27",        # przycisk PRO włączony
    "api_wl":      "#1a4fa0",        # przycisk API włączony
    "btn_wyl":     "#333355",        # przycisk wyłączony
    "btn_tekst":   "#ffffff",
    "sep":         "#3a3a5a",
}
FONT     = "Segoe UI"
F_NORM   = (FONT, 10)
F_BOLD   = (FONT, 10, "bold")
F_TITLE  = (FONT, 13, "bold")
F_SMALL  = (FONT, 9)
F_VAL    = (FONT, 11, "bold")       # wartości — większe


# ── Konfiguracja ──────────────────────────────────────────────────────────────

def wczytaj_config(sciezka=None):
    sciezka = sciezka or CONFIG_JSON
    try:
        return json.loads(Path(sciezka).read_text(encoding="utf-8"))
    except Exception:
        return {}


def zapisz_tryb(tryb, sciezka=None):
    sciezka = Path(sciezka or CONFIG_JSON)
    try:
        cfg = wczytaj_config(sciezka)
        cfg["tryb"] = tryb
        sciezka.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    except Exception:
        pass


# ── Odczyt danych ─────────────────────────────────────────────────────────────

def czytaj_uzycie(claude_dir=None):
    claude_dir = Path(claude_dir or CLAUDE_DIR)
    dzisiaj = date.today().isoformat()
    stats = {
        "data": dzisiaj, "liczba_wywolan": 0,
        "tokeny_wejscia": 0, "tokeny_wyjscia": 0,
        "cache_create": 0, "cache_read": 0,
        "laczne_tokeny": 0, "koszt_usd": 0.0, "modele": {},
        "ostatnia_aktualizacja": datetime.now().strftime("%H:%M:%S"),
    }
    for jsonl in claude_dir.rglob("*.jsonl"):
        try:
            if datetime.fromtimestamp(jsonl.stat().st_mtime).date() < date.today():
                continue
            for line in jsonl.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if not obj.get("timestamp", "").startswith(dzisiaj):
                    continue
                msg = obj.get("message", {})
                u = msg.get("usage", {})
                if not u:
                    continue
                inp = u.get("input_tokens", 0)
                out = u.get("output_tokens", 0)
                cc  = u.get("cache_creation_input_tokens", 0)
                cr  = u.get("cache_read_input_tokens", 0)
                if inp == out == cc == cr == 0:
                    continue
                model = msg.get("model", DOMYSLNY)
                c = CENNIK.get(model, CENNIK[DOMYSLNY])
                koszt = (inp/1e6*c["i"] + out/1e6*c["o"] +
                         cc/1e6*c["cc"] + cr/1e6*c["cr"])
                stats["liczba_wywolan"] += 1
                stats["tokeny_wejscia"] += inp
                stats["tokeny_wyjscia"] += out
                stats["cache_create"]   += cc
                stats["cache_read"]     += cr
                stats["laczne_tokeny"]  += inp + out + cc + cr
                stats["koszt_usd"]      += koszt
                m = stats["modele"].setdefault(model, {
                    "wywolania": 0, "tokeny": 0, "koszt_usd": 0.0})
                m["wywolania"] += 1
                m["tokeny"]    += inp + out + cc + cr
                m["koszt_usd"] += koszt
        except Exception:
            continue
    return stats


def zapisz_json(stats):
    DZISIAJ_JSON.parent.mkdir(parents=True, exist_ok=True)
    DZISIAJ_JSON.write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                            encoding="utf-8")


def czytaj_wydatki_od(data_od_str, claude_dir=None):
    """Sumuje koszty API ze wszystkich JSONL od podanej daty (włącznie)."""
    claude_dir = Path(claude_dir or CLAUDE_DIR)
    try:
        data_od = date.fromisoformat(data_od_str)
    except Exception:
        return 0.0
    koszt_total = 0.0
    for jsonl in claude_dir.rglob("*.jsonl"):
        try:
            if datetime.fromtimestamp(jsonl.stat().st_mtime).date() < data_od:
                continue
            for line in jsonl.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("timestamp", "")[:10] < data_od_str:
                    continue
                msg = obj.get("message", {})
                u = msg.get("usage", {})
                if not u:
                    continue
                inp = u.get("input_tokens", 0)
                out = u.get("output_tokens", 0)
                cc  = u.get("cache_creation_input_tokens", 0)
                cr  = u.get("cache_read_input_tokens", 0)
                if inp == out == cc == cr == 0:
                    continue
                model = msg.get("model", DOMYSLNY)
                c = CENNIK.get(model, CENNIK[DOMYSLNY])
                koszt_total += (inp/1e6*c["i"] + out/1e6*c["o"] +
                                cc/1e6*c["cc"] + cr/1e6*c["cr"])
        except Exception:
            continue
    return koszt_total


def auto_zapisz_date_salda(cfg, sciezka=None):
    """Jeśli saldo_api_usd jest w config ale brak daty — zapisuje dzisiejszą."""
    sciezka = Path(sciezka or CONFIG_JSON)
    if cfg.get("saldo_api_usd") is not None and not cfg.get("saldo_data_wpisania"):
        cfg["saldo_data_wpisania"] = date.today().isoformat()
        try:
            sciezka.write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    return cfg


# ── Auto-detekcja rate-limitu z plików JSONL ──────────────────────────────────

def _parsuj_reset_czas(tekst: str):
    """Parsuje czas resetu z komunikatu Claude, np. 'resets 8pm (Europe/Warsaw)'.
    Zwraca datetime lub None."""
    m = re.search(r'resets\s+(\d+)(?::(\d+))?\s*(am|pm)', tekst, re.IGNORECASE)
    if not m:
        return None
    godz  = int(m.group(1))
    min_  = int(m.group(2) or 0)
    ampm  = m.group(3).lower()
    if ampm == "pm" and godz != 12:
        godz += 12
    elif ampm == "am" and godz == 12:
        godz = 0
    teraz  = datetime.now()
    reset  = teraz.replace(hour=godz, minute=min_, second=0, microsecond=0)
    if reset <= teraz:
        reset += timedelta(days=1)
    return reset


class RateLimitWatcher:
    """Obserwuje pliki JSONL w tle i wykrywa komunikaty rate-limit od Claude."""

    CLAUDE_DIR = Path.home() / ".claude"
    SPRAWDZAJ_CO = 5  # sekund

    def __init__(self, callback_wykryto):
        """callback_wykryto(reset_datetime) — wywoływane gdy limit wykryty."""
        self._callback  = callback_wykryto
        self._pozycje   = {}   # ścieżka → rozmiar pliku przy ostatnim odczycie
        self._stop_evt  = threading.Event()
        self._watek     = threading.Thread(target=self._petla, daemon=True)
        self._watek.start()

    def stop(self):
        self._stop_evt.set()

    def _petla(self):
        while not self._stop_evt.wait(self.SPRAWDZAJ_CO):
            try:
                self._sprawdz()
            except Exception:
                pass

    def _sprawdz(self):
        for plik in self.CLAUDE_DIR.rglob("*.jsonl"):
            try:
                rozmiar = plik.stat().st_size
            except OSError:
                continue
            ostatni = self._pozycje.get(plik, 0)
            if rozmiar <= ostatni:
                self._pozycje[plik] = rozmiar
                continue
            # Czytaj tylko nowe linie
            try:
                with plik.open("r", encoding="utf-8", errors="ignore") as f:
                    f.seek(ostatni)
                    nowe = f.read()
                self._pozycje[plik] = rozmiar
            except OSError:
                continue
            for linia in nowe.splitlines():
                if not linia.strip():
                    continue
                try:
                    dane = json.loads(linia)
                except json.JSONDecodeError:
                    continue
                # Sprawdź czy to wpis rate-limit
                if dane.get("error") != "rate_limit":
                    continue
                if dane.get("apiErrorStatus") != 429:
                    continue
                # Wyciągnij tekst z treści wiadomości
                tresc = ""
                msg = dane.get("message", {})
                for blok in msg.get("content", []):
                    if isinstance(blok, dict) and blok.get("type") == "text":
                        tresc += blok.get("text", "")
                reset = _parsuj_reset_czas(tresc)
                if reset:
                    self._callback(reset)
                    return  # jeden callback wystarczy


# ── Ikona tray ────────────────────────────────────────────────────────────────

def stworz_ikone(tryb, alarm=False):
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if alarm:
        kol = (243, 139, 168)
    elif tryb == "pro":
        kol = (166, 227, 161)
    else:
        kol = (137, 180, 250)
    draw.ellipse([4, 4, size - 4, size - 4], fill=kol)
    litera = "P" if tryb == "pro" else "A"
    try:
        fnt = ImageFont.truetype("arialbd.ttf", 32)
        draw.text((size // 2, size // 2), litera, fill=(20, 20, 30),
                  anchor="mm", font=fnt)
    except Exception:
        draw.text((22, 16), litera, fill=(20, 20, 30))
    return img


# ── Pomocnik: wiersz etykieta + wartość ───────────────────────────────────────

def wiersz(parent, napis, kol_napis=None, kol_wartosc=None, font_val=None):
    """Zwraca (frame, label_wartosci)."""
    kol_napis    = kol_napis    or K["tekst2"]
    kol_wartosc  = kol_wartosc  or K["tekst"]
    font_val     = font_val     or F_VAL
    bg = parent.cget("bg")
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", pady=2)
    tk.Label(row, text=napis, anchor="w", bg=bg,
             fg=kol_napis, font=F_NORM).pack(side="left")
    lbl = tk.Label(row, text="–", anchor="e", bg=bg,
                   fg=kol_wartosc, font=font_val)
    lbl.pack(side="right")
    return row, lbl


def separator(parent):
    tk.Frame(parent, bg=K["sep"], height=1).pack(fill="x", padx=0, pady=6)


# ── Okienko tkinter ───────────────────────────────────────────────────────────

class OkienkoDane:
    def __init__(self, app):
        self.app   = app
        self.root  = None
        self.lbls  = {}        # słownik etykiet wartości
        self.pasek_canvas = None

    def pokaz(self):
        if self.root and self.root.winfo_exists():
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            return
        self._buduj()

    def ukryj(self):
        if self.root and self.root.winfo_exists():
            self.root.withdraw()

    def _buduj(self):
        root = tk.Tk()
        self.root = root
        root.title("Monitor Tokenów")
        root.configure(bg=K["tlo"])
        root.resizable(False, False)
        root.attributes("-topmost", True)

        # Nie pokazuj w pasku zadań — okienko chowa się do tray
        root.attributes("-toolwindow", True)

        # Ciemny pasek tytułu (spójny z ciemnym motywem okienka)
        root.update_idletasks()
        _ciemny_pasek_tytulu(root)

        # "X" = tylko ukryj (nie wyłącza programu)
        root.protocol("WM_DELETE_WINDOW", self.ukryj)

        pad = {"padx": 18}

        # ── Nagłówek ──────────────────────────────────────────────────────
        tk.Label(root, text="Monitor Tokenów Claude",
                 bg=K["tlo"], fg=K["niebieski"],
                 font=F_TITLE).pack(pady=(14, 6), **pad)

        # ── Przyciski PRO / API ────────────────────────────────────────────
        btn_f = tk.Frame(root, bg=K["tlo"])
        btn_f.pack(pady=4, **pad)

        self.btn_pro = tk.Button(
            btn_f, text="● PRO", width=12,
            font=F_BOLD, relief="flat", cursor="hand2", bd=0,
            command=lambda: self.app.przelacz("pro"))
        self.btn_pro.pack(side="left", padx=5, ipady=4)

        self.btn_api = tk.Button(
            btn_f, text="● API", width=12,
            font=F_BOLD, relief="flat", cursor="hand2", bd=0,
            command=lambda: self.app.przelacz("api"))
        self.btn_api.pack(side="left", padx=5, ipady=4)

        separator(root)

        # ── Tokeny (wspólne) ──────────────────────────────────────────────
        tk.Label(root, text="TOKENY DZISIAJ", bg=K["tlo"],
                 fg=K["szary"], font=F_SMALL).pack(anchor="w", **pad)

        tok_f = tk.Frame(root, bg=K["tlo"])
        tok_f.pack(fill="x", **pad)

        for klucz, napis in [
            ("wywolania",  "Wywołania API"),
            ("wejscie",    "Tokeny wejście"),
            ("wyjscie",    "Tokeny wyjście"),
            ("cache_cr",   "Cache create"),
            ("cache_rd",   "Cache read"),
            ("laczne",     "Tokeny łącznie"),
        ]:
            kw = {"kol_wartosc": K["cyan"]} if klucz == "laczne" else {}
            _, lbl = wiersz(tok_f, napis, **kw)
            self.lbls[klucz] = lbl

        separator(root)

        # ── Panel PRO ─────────────────────────────────────────────────────
        self.pro_f = tk.Frame(root, bg=K["tlo2"])
        self.pro_f.pack(fill="x", padx=12, pady=3)

        tk.Label(self.pro_f, text="  ● CLAUDE PRO  —  $20 / miesiąc",
                 bg=K["tlo2"], fg=K["zielony"],
                 font=F_BOLD).pack(anchor="w", pady=(8, 2))

        _, self.lbls["ekwiwalent"] = wiersz(
            self.pro_f, "  Ekwiwalent API (teoretyczny)",
            kol_wartosc=K["tekst2"], font_val=F_NORM)

        # ── Panel rate-limit ──────────────────────────────────────────────
        self.rl_f = tk.Frame(self.pro_f, bg=K["tlo2"])
        self.rl_f.pack(fill="x", padx=8, pady=(2, 6))

        # Wiersz górny: status + przycisk
        rl_top = tk.Frame(self.rl_f, bg=K["tlo2"])
        rl_top.pack(fill="x")

        self.lbl_rl_status = tk.Label(rl_top, text="", bg=K["tlo2"], font=F_SMALL)
        self.lbl_rl_status.pack(side="left")

        self.btn_rl_ustaw = tk.Button(
            rl_top, text="⏱ Ustaw", font=F_SMALL,
            bg=K["btn_wyl"], fg=K["tekst2"],
            relief="flat", cursor="hand2", bd=0,
            command=self._dialog_rate_limit)
        self.btn_rl_ustaw.pack(side="right", padx=2)

        self.btn_rl_clear = tk.Button(
            rl_top, text="✕ Wyczyść", font=F_SMALL,
            bg=K["btn_wyl"], fg=K["tekst_dim"],
            relief="flat", cursor="hand2", bd=0,
            command=self._wyczysc_rate_limit)
        # nie pack — pokazujemy tylko gdy aktywny

        # Wiersz odliczania (widoczny tylko gdy aktywny)
        self.lbl_rl_countdown = tk.Label(
            self.rl_f, text="", bg=K["tlo2"],
            fg=K["czerwony"], font=(FONT, 18, "bold"))
        # nie pack — pokazujemy tylko gdy aktywny

        separator(root)

        # ── Panel API ─────────────────────────────────────────────────────
        self.api_f = tk.Frame(root, bg=K["tlo2"])
        self.api_f.pack(fill="x", padx=12, pady=3)

        tk.Label(self.api_f, text="  ● ANTHROPIC API  —  kredyty",
                 bg=K["tlo2"], fg=K["niebieski"],
                 font=F_BOLD).pack(anchor="w", pady=(8, 2))

        for klucz, napis in [
            ("saldo_pocz",   "  Saldo startowe (wpisane)"),
            ("saldo_wydano", "  Wydano od dnia wpisania"),
            ("saldo_akt",    "  Aktualne saldo"),
        ]:
            _, lbl = wiersz(self.api_f, napis)
            self.lbls[klucz] = lbl

        tk.Frame(self.api_f, bg=K["sep"], height=1).pack(fill="x", padx=10, pady=4)

        for klucz, napis in [
            ("api_wydano",    "  Wydano dziś"),
            ("api_limit",     "  Limit dzienny"),
            ("api_pozostalo", "  Pozostało z limitu"),
        ]:
            _, lbl = wiersz(self.api_f, napis)
            self.lbls[klucz] = lbl

        # Przycisk aktualizacji salda
        tk.Button(
            self.api_f, text="↺  Zaktualizuj saldo po doładowaniu",
            bg=K["btn_wyl"], fg=K["niebieski"], font=F_SMALL,
            relief="flat", cursor="hand2", bd=0,
            command=self._dialog_saldo,
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # Pasek API
        pasek_outer = tk.Frame(self.api_f, bg=K["tlo2"])
        pasek_outer.pack(fill="x", padx=10, pady=(4, 8))
        self.pasek_canvas = tk.Canvas(pasek_outer, height=8,
                                       bg=K["tlo2"], highlightthickness=0)
        self.pasek_canvas.pack(fill="x")

        separator(root)

        # ── Stopka ────────────────────────────────────────────────────────
        self.lbl_czas = tk.Label(root, text="", bg=K["tlo"],
                                  fg=K["tekst_dim"], font=F_SMALL)
        self.lbl_czas.pack(pady=(0, 12))

        # Pierwsze odświeżenie + uruchom countdown jeśli limit był zapisany
        root.after(100, self._odswiez)
        root.after(200, self._start_countdown_rl)
        root.mainloop()

    def _dialog_rate_limit(self):
        """Dialog: wpisz ile minut zostało z komunikatu Claude."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Ustaw rate limit")
        dialog.configure(bg=K["tlo"])
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        tk.Label(dialog, text="Claude napisał: \"możesz korzystać za X minut\"",
                 bg=K["tlo"], fg=K["tekst2"], font=F_SMALL).pack(padx=20, pady=(14, 2))
        tk.Label(dialog, text="Ile minut wpisał?",
                 bg=K["tlo"], fg=K["tekst"], font=F_BOLD).pack(padx=20, pady=(0, 4))

        entry = tk.Entry(dialog, font=(FONT, 22, "bold"), bg=K["tlo2"],
                         fg=K["czerwony"], insertbackground=K["czerwony"],
                         relief="flat", justify="center", width=6)
        entry.pack(padx=20, pady=4)
        entry.focus_set()

        info = tk.Label(dialog, text="", bg=K["tlo"], fg=K["tekst_dim"], font=F_SMALL)
        info.pack(pady=2)

        def zatwierdz():
            tekst = entry.get().strip()
            try:
                minuty = int(tekst)
                if minuty <= 0 or minuty > 240:
                    raise ValueError
            except ValueError:
                info.config(text="⚠  Wpisz liczbę minut (1–240)", fg=K["czerwony"])
                return
            koniec = datetime.now() + __import__("datetime").timedelta(minutes=minuty)
            cfg = wczytaj_config()
            cfg["rate_limit_do"] = koniec.strftime("%Y-%m-%d %H:%M:%S")
            CONFIG_JSON.write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            dialog.destroy()
            self._start_countdown_rl()

        btn_f = tk.Frame(dialog, bg=K["tlo"])
        btn_f.pack(pady=(8, 16))
        tk.Button(btn_f, text="Zapisz", font=F_BOLD,
                  bg=K["czerwony"], fg="white", relief="flat",
                  cursor="hand2", width=10, command=zatwierdz).pack(side="left", padx=6)
        tk.Button(btn_f, text="Anuluj", font=F_NORM,
                  bg=K["btn_wyl"], fg=K["tekst2"], relief="flat",
                  cursor="hand2", width=8, command=dialog.destroy).pack(side="left", padx=6)

        entry.bind("<Return>", lambda e: zatwierdz())
        entry.bind("<Escape>", lambda e: dialog.destroy())

    def _wyczysc_rate_limit(self):
        """Ręczne wyczyszczenie rate-limitu."""
        cfg = wczytaj_config()
        cfg.pop("rate_limit_do", None)
        CONFIG_JSON.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        self._ukryj_countdown()

    def _start_countdown_rl(self):
        """Uruchamia pętlę odliczającą co sekundę."""
        self._tick_countdown()

    def _tick_countdown(self):
        """Tick co sekundę — aktualizuje odliczanie rate-limitu."""
        if not self.root or not self.root.winfo_exists():
            return
        cfg = wczytaj_config()
        rl_str = cfg.get("rate_limit_do", "")
        if not rl_str:
            self._ukryj_countdown()
            return
        try:
            # obsługa formatu "YYYY-MM-DD HH:MM:SS" i starszego "HH:MM"
            if len(rl_str) > 5:
                koniec = datetime.strptime(rl_str, "%Y-%m-%d %H:%M:%S")
            else:
                h, m = map(int, rl_str.split(":"))
                koniec = datetime.now().replace(hour=h, minute=m, second=0)
            delta = koniec - datetime.now()
            sekundy = int(delta.total_seconds())
            if sekundy <= 0:
                # Limit minął — wyczyść automatycznie
                cfg.pop("rate_limit_do", None)
                CONFIG_JSON.write_text(
                    json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                self._ukryj_countdown()
                return
            # Pokaż odliczanie
            godz  = sekundy // 3600
            min_  = (sekundy % 3600) // 60
            sek   = sekundy % 60
            if godz > 0:
                tekst = f"{godz}:{min_:02d}:{sek:02d}"
            else:
                tekst = f"{min_:02d}:{sek:02d}"
            self.lbl_rl_status.config(
                text="  ⚠  Rate limit aktywny — pozostało: ",
                fg=K["czerwony"])
            self.lbl_rl_countdown.config(text=tekst)
            self.lbl_rl_countdown.pack(anchor="w", padx=8, pady=(0, 2))
            self.btn_rl_ustaw.pack_forget()
            self.btn_rl_clear.pack(side="right", padx=2)
        except Exception:
            self._ukryj_countdown()
            return
        self.root.after(1000, self._tick_countdown)

    def _ukryj_countdown(self):
        """Ukrywa panel odliczania, wraca do stanu normalnego."""
        self.lbl_rl_status.config(
            text="  ✓  Brak aktywnego rate-limitu", fg=K["zielony"])
        self.lbl_rl_countdown.pack_forget()
        self.btn_rl_clear.pack_forget()
        self.btn_rl_ustaw.pack(side="right", padx=2)

    def _dialog_saldo(self):
        """Okienko do wpisania nowego salda po doładowaniu konta."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Aktualizuj saldo")
        dialog.configure(bg=K["tlo"])
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()  # blokuj główne okno

        tk.Label(dialog, text="Nowe saldo konta Anthropic (USD):",
                 bg=K["tlo"], fg=K["tekst"], font=F_NORM).pack(padx=20, pady=(16, 4))

        entry = tk.Entry(dialog, font=F_VAL, bg=K["tlo2"], fg=K["cyan"],
                         insertbackground=K["cyan"], relief="flat",
                         justify="center", width=14)
        # Wstaw aktualne saldo jako punkt startowy
        cfg = wczytaj_config()
        stare = cfg.get("saldo_api_usd", "")
        if stare != "":
            entry.insert(0, str(stare))
        entry.pack(padx=20, pady=4)
        entry.select_range(0, "end")
        entry.focus_set()

        info = tk.Label(dialog, text="", bg=K["tlo"], fg=K["tekst_dim"], font=F_SMALL)
        info.pack(pady=2)

        def zatwierdz():
            tekst = entry.get().strip().replace(",", ".")
            try:
                kwota = float(tekst)
                if kwota < 0:
                    raise ValueError
            except ValueError:
                info.config(text="⚠  Wpisz poprawną kwotę, np. 5.00", fg=K["czerwony"])
                return
            cfg = wczytaj_config()
            cfg["saldo_api_usd"]       = round(kwota, 2)
            cfg["saldo_data_wpisania"] = date.today().isoformat()
            CONFIG_JSON.write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            dialog.destroy()

        btn_f = tk.Frame(dialog, bg=K["tlo"])
        btn_f.pack(pady=(8, 16))
        tk.Button(btn_f, text="Zapisz", font=F_BOLD,
                  bg=K["api_wl"], fg="white", relief="flat",
                  cursor="hand2", width=10, command=zatwierdz).pack(side="left", padx=6)
        tk.Button(btn_f, text="Anuluj", font=F_NORM,
                  bg=K["btn_wyl"], fg=K["tekst2"], relief="flat",
                  cursor="hand2", width=8, command=dialog.destroy).pack(side="left", padx=6)

        entry.bind("<Return>", lambda e: zatwierdz())
        entry.bind("<Escape>", lambda e: dialog.destroy())

    def _odswiez(self):
        if not self.root or not self.root.winfo_exists():
            return

        stats = self.app.stats
        tryb  = self.app.tryb
        cfg   = auto_zapisz_date_salda(wczytaj_config())
        limit = cfg.get("budzet", {}).get("dzienny_limit_usd", 10.0)
        saldo = cfg.get("saldo_api_usd", None)
        data_wpisania = cfg.get("saldo_data_wpisania", None)

        fmt = lambda n: f"{n:,}".replace(",", " ")
        koszt = stats.get("koszt_usd", 0.0)

        # Tokeny
        self.lbls["wywolania"].config(text=str(stats.get("liczba_wywolan", 0)))
        self.lbls["wejscie"].config( text=fmt(stats.get("tokeny_wejscia", 0)))
        self.lbls["wyjscie"].config( text=fmt(stats.get("tokeny_wyjscia", 0)))
        self.lbls["cache_cr"].config(text=fmt(stats.get("cache_create", 0)))
        self.lbls["cache_rd"].config(text=fmt(stats.get("cache_read", 0)))
        self.lbls["laczne"].config(  text=fmt(stats.get("laczne_tokeny", 0)))

        # PRO
        self.lbls["ekwiwalent"].config(text=f"${koszt:.4f} USD")

        # Rate-limit — uruchom odliczanie jeśli aktywne
        rl = cfg.get("rate_limit_do", "")
        if rl:
            self._start_countdown_rl()
        else:
            self._ukryj_countdown()

        # API — saldo kumulatywne od daty wpisania
        if saldo is not None and data_wpisania:
            wydano_od = czytaj_wydatki_od(data_wpisania)
            saldo_akt = max(0.0, saldo - wydano_od)
            data_kr = data_wpisania[5:]  # MM-DD
            self.lbls["saldo_pocz"].config(
                text=f"${saldo:.2f} USD", fg=K["tekst"])
            self.lbls["saldo_wydano"].config(
                text=f"${wydano_od:.4f} USD  (od {data_kr})", fg=K["zolty"])
            kol_s = (K["czerwony"] if saldo_akt < 1
                     else K["zolty"] if saldo_akt < saldo * 0.2
                     else K["zielony"])
            self.lbls["saldo_akt"].config(
                text=f"${saldo_akt:.4f} USD", fg=kol_s)
        else:
            for k in ("saldo_pocz", "saldo_wydano", "saldo_akt"):
                self.lbls[k].config(
                    text="— wpisz saldo_api_usd w config.json", fg=K["tekst_dim"])

        # API — dzienny limit
        self.lbls["api_wydano"].config(text=f"${koszt:.4f} USD")
        self.lbls["api_limit"].config( text=f"${limit:.2f} USD")
        pozostalo = max(0.0, limit - koszt)
        kol_p = (K["czerwony"] if pozostalo < limit * 0.1
                 else K["zolty"] if pozostalo < limit * 0.3
                 else K["zielony"])
        self.lbls["api_pozostalo"].config(text=f"${pozostalo:.4f} USD",
                                          fg=kol_p)

        # Pasek API
        procent = min(koszt / limit * 100 if limit > 0 else 0, 100)
        self.pasek_canvas.update_idletasks()
        w = self.pasek_canvas.winfo_width()
        if w > 10:
            self.pasek_canvas.delete("all")
            self.pasek_canvas.create_rectangle(0, 0, w, 8,
                                                fill=K["szary"], width=0)
            wypeln = int(w * procent / 100)
            if wypeln > 0:
                kol_b = (K["czerwony"] if procent >= 95
                         else K["zolty"] if procent >= 80 else K["zielony"])
                self.pasek_canvas.create_rectangle(0, 0, wypeln, 8,
                                                    fill=kol_b, width=0)

        # Aktywność paneli
        self._aktywuj_panel(self.pro_f, tryb == "pro", K["zielony"])
        self._aktywuj_panel(self.api_f, tryb == "api", K["niebieski"])

        # Przyciski
        self._styl_btn(self.btn_pro, tryb == "pro",
                       "● PRO  ✓" if tryb == "pro" else "  PRO",
                       K["pro_wl"])
        self._styl_btn(self.btn_api, tryb == "api",
                       "● API  ✓" if tryb == "api" else "  API",
                       K["api_wl"])

        akt = stats.get("ostatnia_aktualizacja", "–")
        self.lbl_czas.config(
            text=f"Ostatnia aktualizacja: {akt}  •  odświeżam co {ODSWIEZAJ_CO}s")

        self.root.after(5000, self._odswiez)

    def _styl_btn(self, btn, aktywny, tekst, kol_aktywny):
        btn.config(
            text=tekst,
            bg=kol_aktywny if aktywny else K["btn_wyl"],
            fg=K["btn_tekst"],
            relief="sunken" if aktywny else "flat",
        )

    def _aktywuj_panel(self, frame, aktywny, kol_akc):
        kol_tlo = K["tlo2"] if aktywny else K["tlo_wyszarz"]
        kol_txt = K["tekst"] if aktywny else K["tekst_dim"]
        frame.config(bg=kol_tlo)
        for w in frame.winfo_children():
            try:
                w.config(bg=kol_tlo)
                if isinstance(w, tk.Label):
                    w.config(fg=kol_txt if aktywny else K["tekst_dim"])
                elif isinstance(w, tk.Frame):
                    w.config(bg=kol_tlo)
                    for ww in w.winfo_children():
                        try:
                            ww.config(bg=kol_tlo,
                                      fg=kol_txt if aktywny else K["tekst_dim"])
                        except Exception:
                            pass
            except Exception:
                pass


# ── Aplikacja główna ──────────────────────────────────────────────────────────

class MonitorApp:
    def __init__(self):
        cfg       = wczytaj_config()
        self.tryb = cfg.get("tryb", "pro")

        # Wyczyść rate-limit zanim GUI się zbuduje:
        # - jeśli już minął, LUB
        # - jeśli >3h w przyszłości (błąd parsowania "resets 8pm" z poprzedniego dnia)
        rl_str = cfg.get("rate_limit_do", "")
        if rl_str:
            try:
                koniec = datetime.strptime(rl_str, "%Y-%m-%d %H:%M:%S")
                pozostalo = (koniec - datetime.now()).total_seconds()
                if pozostalo <= 0 or pozostalo > 10800:
                    cfg.pop("rate_limit_do")
                    CONFIG_JSON.write_text(
                        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                cfg.pop("rate_limit_do", None)
                CONFIG_JSON.write_text(
                    json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stats = czytaj_uzycie()
        self.okno  = OkienkoDane(self)
        self.icon  = None
        # Wątek obserwujący JSONL — auto-wykrywanie rate-limitu
        self._rl_watcher = RateLimitWatcher(self._on_rate_limit_wykryty)

    def _on_rate_limit_wykryty(self, reset: datetime):
        """Wywoływane przez watcher gdy JSONL zawiera wpis rate-limit."""
        cfg = wczytaj_config()
        # Zapisz tylko jeśli limit jeszcze nie był ustawiony lub jest wcześniejszy
        stary = cfg.get("rate_limit_do", "")
        nowy_str = reset.strftime("%Y-%m-%d %H:%M:%S")
        if stary and stary >= nowy_str:
            return
        cfg["rate_limit_do"] = nowy_str
        CONFIG_JSON.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        # Uruchom countdown w wątku GUI (thread-safe przez after)
        if self.okno.root and self.okno.root.winfo_exists():
            self.okno.root.after(0, self.okno._start_countdown_rl)

    def przelacz(self, nowy_tryb):
        self.tryb = nowy_tryb
        zapisz_tryb(nowy_tryb)
        if self.icon:
            self.icon.icon  = stworz_ikone(nowy_tryb)
            self._aktualizuj_tooltip()

    def _aktualizuj_tooltip(self):
        if not self.icon:
            return
        koszt   = self.stats.get("koszt_usd", 0.0)
        laczne  = self.stats.get("laczne_tokeny", 0)
        wywolan = self.stats.get("liczba_wywolan", 0)
        cfg     = wczytaj_config()
        limit   = cfg.get("budzet", {}).get("dzienny_limit_usd", 10.0)
        alarm   = (self.tryb == "api" and koszt >= limit * 0.95)
        self.icon.icon  = stworz_ikone(self.tryb, alarm)
        self.icon.title = (
            f"Monitor Tokenów  ● {'PRO' if self.tryb == 'pro' else 'API'}\n"
            f"{wywolan} wywołań  |  {laczne:,} tokenów\n"
            f"Ekwiwalent API: ${koszt:.4f}"
        )

    def _refresh_loop(self):
        while True:
            self.stats = czytaj_uzycie()
            zapisz_json(self.stats)
            self._aktualizuj_tooltip()
            time.sleep(ODSWIEZAJ_CO)

    def run(self):
        threading.Thread(target=self._refresh_loop, daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem("Pokaż / Ukryj",    self._toggle,  default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Przełącz na PRO",  lambda i: self.przelacz("pro")),
            pystray.MenuItem("Przełącz na API",  lambda i: self.przelacz("api")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Zakończ",          self._zakoncz),
        )
        self.icon = pystray.Icon(
            "monitor_tokenow",
            stworz_ikone(self.tryb),
            "Monitor Tokenów Claude",
            menu,
        )
        self.icon.run_detached()

        # Okienko — główny wątek
        self.okno.pokaz()

        # Po zamknięciu okienka ("X" = ukryj) pętla tray pozostaje
        try:
            while self.icon.visible:
                time.sleep(1)
        except Exception:
            pass

    def _toggle(self, icon=None, item=None):
        if self.okno.root and self.okno.root.winfo_exists():
            if self.okno.root.state() == "withdrawn":
                self.okno.pokaz()
            else:
                self.okno.ukryj()
        else:
            self.okno.pokaz()

    def _zakoncz(self, icon=None, item=None):
        self._rl_watcher.stop()
        self.icon.stop()
        if self.okno.root and self.okno.root.winfo_exists():
            self.okno.root.after(0, self.okno.root.destroy)


# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    MonitorApp().run()
