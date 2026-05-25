"""
Testy integracyjne — Poziom 2.

Sprawdzają jak kilka elementów aplikacji współpracuje ze sobą:
- czytanie JSONL + zapis do dzisiaj.json + odczyt z powrotem
- zapis/odczyt config.json przez różne funkcje
- czytaj_wydatki_od() z wieloma plikami w różnych podkatalogach
- auto_zapisz_date_salda() — zapis do pliku i natychmiastowy odczyt
- pełny przepływ danych: JSONL → stats → JSON → odczyt
"""

import json
import sys
import pytest
from datetime import date, timedelta
from pathlib import Path

# Dodaj katalog główny projektu do sys.path żeby importy działały
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tray_monitor import (
    czytaj_uzycie,
    zapisz_json,
    czytaj_wydatki_od,
    auto_zapisz_date_salda,
    wczytaj_config,
    zapisz_tryb,
    DZISIAJ_JSON,
    CONFIG_JSON,
)
from tests.helpers import wpis_jsonl, DZISIAJ, WCZORAJ


# ─── Helpers lokalne ──────────────────────────────────────────────────────────

def _stworz_claude_dir(tmp_path, wpisy_per_projekt: dict) -> Path:
    """
    Tworzy strukturę katalogów udającą ~/.claude/projects/ z wieloma projektami.

    Przykład:
        _stworz_claude_dir(tmp_path, {
            "projekt-a": [wpis_jsonl(inp=1000)],
            "projekt-b": [wpis_jsonl(inp=2000), wpis_jsonl(inp=3000)],
        })
    """
    claude_dir = tmp_path / "claude"
    for projekt, wpisy in wpisy_per_projekt.items():
        katalog = claude_dir / "projects" / projekt
        katalog.mkdir(parents=True)
        (katalog / "session.jsonl").write_text(
            "\n".join(wpisy), encoding="utf-8"
        )
    return claude_dir


# ─── Testy: pełny przepływ danych ─────────────────────────────────────────────

class TestPelnyPrzeplyw:
    """Dane JSONL → czytaj_uzycie() → zapisz_json() → odczyt z pliku."""

    def test_dane_przezyja_zapis_i_odczyt(self, tmp_path, plik_jsonl):
        """Liczby tokenów nie zmieniają się po zapisaniu do dzisiaj.json i odczytaniu."""
        katalog = plik_jsonl([
            wpis_jsonl(inp=500_000, out=250_000, cc=100_000, cr=50_000)
        ])

        stats = czytaj_uzycie(claude_dir=katalog)

        # Zapisz do tymczasowego pliku (nie do prawdziwego data/dzisiaj.json)
        dzisiaj_plik = tmp_path / "dzisiaj.json"
        dzisiaj_plik.write_text(
            json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        odczytane = json.loads(dzisiaj_plik.read_text(encoding="utf-8"))

        assert odczytane["tokeny_wejscia"]  == 500_000
        assert odczytane["tokeny_wyjscia"]  == 250_000
        assert odczytane["cache_create"]    == 100_000
        assert odczytane["cache_read"]      == 50_000
        assert odczytane["liczba_wywolan"]  == 1

    def test_koszt_zachowany_z_precyzja(self, tmp_path, plik_jsonl):
        """Koszt USD zapisany jako float nie traci precyzji przy serializacji JSON."""
        katalog = plik_jsonl([
            wpis_jsonl(model="claude-sonnet-4-6", inp=1_000_000, out=0)
        ])

        stats = czytaj_uzycie(claude_dir=katalog)
        dzisiaj_plik = tmp_path / "dzisiaj.json"
        dzisiaj_plik.write_text(json.dumps(stats), encoding="utf-8")

        odczytane = json.loads(dzisiaj_plik.read_text())

        # 1M input tokenów Sonnet = $3.00 dokładnie
        assert abs(odczytane["koszt_usd"] - 3.00) < 0.0001

    def test_wiele_wywolan_sumuje_sie_poprawnie(self, plik_jsonl):
        """Suma tokenów z wielu wpisów w jednym pliku JSONL."""
        katalog = plik_jsonl([
            wpis_jsonl(inp=100_000, out=50_000),
            wpis_jsonl(inp=200_000, out=100_000),
            wpis_jsonl(inp=300_000, out=150_000),
        ])

        stats = czytaj_uzycie(claude_dir=katalog)

        assert stats["tokeny_wejscia"]  == 600_000
        assert stats["tokeny_wyjscia"]  == 300_000
        assert stats["liczba_wywolan"]  == 3

    def test_pusty_wynik_serializuje_sie_do_json(self, tmp_path):
        """Nawet zerowe statystyki (brak plików JSONL) można zapisać do JSON."""
        katalog = tmp_path / "pusty_claude"
        katalog.mkdir()

        stats = czytaj_uzycie(claude_dir=katalog)
        dzisiaj_plik = tmp_path / "dzisiaj.json"

        # Nie powinno rzucić wyjątku
        dzisiaj_plik.write_text(json.dumps(stats), encoding="utf-8")
        odczytane = json.loads(dzisiaj_plik.read_text())

        assert odczytane["liczba_wywolan"] == 0
        assert odczytane["koszt_usd"]      == 0.0


# ─── Testy: wiele projektów / plików JSONL ────────────────────────────────────

class TestWieleProjektow:
    """czytaj_uzycie() i czytaj_wydatki_od() z wieloma plikami w różnych podkatalogach."""

    def test_sumuje_tokeny_z_wielu_projektow(self, tmp_path):
        """Tokeny z różnych podkatalogów projektów są sumowane razem."""
        claude_dir = _stworz_claude_dir(tmp_path, {
            "projekt-alpha": [wpis_jsonl(inp=100_000, out=0)],
            "projekt-beta":  [wpis_jsonl(inp=200_000, out=0)],
            "projekt-gamma": [wpis_jsonl(inp=300_000, out=0)],
        })

        stats = czytaj_uzycie(claude_dir=claude_dir)

        assert stats["tokeny_wejscia"]  == 600_000
        assert stats["liczba_wywolan"]  == 3

    def test_sumuje_z_wielu_sesji_w_jednym_projekcie(self, tmp_path):
        """Wiele plików JSONL (sesji) w jednym projekcie są sumowane."""
        claude_dir = tmp_path / "claude"
        projekt = claude_dir / "projects" / "moj-projekt"
        projekt.mkdir(parents=True)

        (projekt / "sesja1.jsonl").write_text(wpis_jsonl(inp=100_000), encoding="utf-8")
        (projekt / "sesja2.jsonl").write_text(wpis_jsonl(inp=100_000), encoding="utf-8")
        (projekt / "sesja3.jsonl").write_text(wpis_jsonl(inp=100_000), encoding="utf-8")

        stats = czytaj_uzycie(claude_dir=claude_dir)

        assert stats["tokeny_wejscia"]  == 300_000
        assert stats["liczba_wywolan"]  == 3

    def test_czytaj_wydatki_od_sumuje_wiele_projektow(self, tmp_path):
        """czytaj_wydatki_od() sumuje koszty ze wszystkich projektów od podanej daty."""
        claude_dir = _stworz_claude_dir(tmp_path, {
            "alpha": [wpis_jsonl(model="claude-sonnet-4-6", inp=500_000, out=0)],
            "beta":  [wpis_jsonl(model="claude-sonnet-4-6", inp=500_000, out=0)],
        })

        wydatki = czytaj_wydatki_od(DZISIAJ, claude_dir=claude_dir)

        # 2 × 500k input Sonnet = 2 × $1.50 = $3.00
        assert abs(wydatki - 3.00) < 0.001

    def test_czytaj_wydatki_od_pomija_stare_wpisy(self, tmp_path):
        """Wpisy sprzed daty granicznej nie są wliczane do wydatków."""
        jutro = (date.today() + timedelta(days=1)).isoformat()
        claude_dir = _stworz_claude_dir(tmp_path, {
            "projekt": [
                wpis_jsonl(inp=1_000_000, data=DZISIAJ),    # dzisiejszy — wliczony
                wpis_jsonl(inp=1_000_000, data=WCZORAJ),    # wczorajszy — pominięty
            ]
        })

        wydatki_od_dzis = czytaj_wydatki_od(DZISIAJ, claude_dir=claude_dir)
        wydatki_od_jutra = czytaj_wydatki_od(jutro, claude_dir=claude_dir)

        # Od dzisiaj: liczy jeden wpis
        assert wydatki_od_dzis > 0
        # Od jutra: żaden wpis nie pasuje
        assert wydatki_od_jutra == 0.0


# ─── Testy: config.json — zapis i odczyt ──────────────────────────────────────

class TestConfigZapisOdczyt:
    """Cykl zapisz_tryb() + wczytaj_config() przez prawdziwy plik na dysku."""

    def test_zapisz_i_odczytaj_tryb_api(self, tmp_path):
        """zapisz_tryb('api') → wczytaj_config() zwraca tryb='api'."""
        cfg_plik = tmp_path / "config.json"
        cfg_plik.write_text(json.dumps({"tryb": "pro"}), encoding="utf-8")

        zapisz_tryb("api", sciezka=cfg_plik)
        odczytane = wczytaj_config(sciezka=cfg_plik)

        assert odczytane["tryb"] == "api"

    def test_zapisz_tryb_zachowuje_pozostale_klucze(self, tmp_path):
        """Zmiana trybu nie usuwa innych pól z config.json."""
        cfg_plik = tmp_path / "config.json"
        cfg_plik.write_text(json.dumps({
            "tryb": "pro",
            "budzet": {"dzienny_limit_usd": 15.0},
            "saldo_api_usd": 7.50,
        }), encoding="utf-8")

        zapisz_tryb("api", sciezka=cfg_plik)
        odczytane = wczytaj_config(sciezka=cfg_plik)

        assert odczytane["tryb"]                          == "api"
        assert odczytane["budzet"]["dzienny_limit_usd"]   == 15.0
        assert odczytane["saldo_api_usd"]                 == 7.50

    def test_wielokrotna_zmiana_trybu(self, tmp_path):
        """Wielokrotna zmiana trybu nie psuje pliku config.json."""
        cfg_plik = tmp_path / "config.json"
        cfg_plik.write_text(json.dumps({"tryb": "pro"}), encoding="utf-8")

        for tryb in ["api", "pro", "api", "pro", "api"]:
            zapisz_tryb(tryb, sciezka=cfg_plik)

        odczytane = wczytaj_config(sciezka=cfg_plik)
        assert odczytane["tryb"] == "api"

    def test_plik_config_jest_poprawnym_json_po_zapisie(self, tmp_path):
        """Po zapisz_tryb() plik zawiera poprawny JSON (nie jest uszkodzony)."""
        cfg_plik = tmp_path / "config.json"
        cfg_plik.write_text(json.dumps({"tryb": "pro", "klucz": "wartość"}), encoding="utf-8")

        zapisz_tryb("api", sciezka=cfg_plik)

        # Jeśli to rzuci — JSON jest uszkodzony
        zawartosc = json.loads(cfg_plik.read_text(encoding="utf-8"))
        assert isinstance(zawartosc, dict)


# ─── Testy: auto_zapisz_date_salda() ──────────────────────────────────────────

class TestAutoZapiszDateSalda:
    """auto_zapisz_date_salda() — zapis daty do pliku i natychmiastowy odczyt."""

    def test_dodaje_date_gdy_brak_i_zapisuje_do_pliku(self, tmp_path):
        """Gdy config ma saldo ale brak daty — funkcja zapisuje datę do pliku."""
        cfg_plik = tmp_path / "config.json"
        cfg = {"saldo_api_usd": 5.00}
        cfg_plik.write_text(json.dumps(cfg), encoding="utf-8")

        auto_zapisz_date_salda(cfg, sciezka=cfg_plik)

        # Odczytaj to co zostało faktycznie zapisane na dysku
        zapisany = json.loads(cfg_plik.read_text(encoding="utf-8"))
        assert zapisany.get("saldo_data_wpisania") == DZISIAJ

    def test_nie_nadpisuje_istniejącej_daty_w_pliku(self, tmp_path):
        """Jeśli data już jest — funkcja jej nie zmienia."""
        stara_data = "2026-01-15"
        cfg_plik = tmp_path / "config.json"
        cfg = {"saldo_api_usd": 5.00, "saldo_data_wpisania": stara_data}
        cfg_plik.write_text(json.dumps(cfg), encoding="utf-8")

        auto_zapisz_date_salda(cfg, sciezka=cfg_plik)

        zapisany = json.loads(cfg_plik.read_text(encoding="utf-8"))
        assert zapisany["saldo_data_wpisania"] == stara_data

    def test_bez_salda_nie_dotyka_pliku(self, tmp_path):
        """Gdy brak saldo_api_usd — plik config nie jest modyfikowany."""
        cfg_plik = tmp_path / "config.json"
        cfg = {"tryb": "pro"}
        cfg_plik.write_text(json.dumps(cfg), encoding="utf-8")
        mtime_przed = cfg_plik.stat().st_mtime

        auto_zapisz_date_salda(cfg, sciezka=cfg_plik)

        mtime_po = cfg_plik.stat().st_mtime
        assert mtime_po == mtime_przed  # plik nie był dotknięty

    def test_saldo_i_data_dostepne_po_odczycie(self, tmp_path):
        """Po auto_zapisz_date_salda() wczytaj_config() widzi oba pola."""
        cfg_plik = tmp_path / "config.json"
        cfg = {"saldo_api_usd": 3.78}
        cfg_plik.write_text(json.dumps(cfg), encoding="utf-8")

        auto_zapisz_date_salda(cfg, sciezka=cfg_plik)
        odczytane = wczytaj_config(sciezka=cfg_plik)

        assert odczytane["saldo_api_usd"]        == 3.78
        assert odczytane["saldo_data_wpisania"]  == DZISIAJ


# ─── Testy: kodowanie znaków ───────────────────────────────────────────────────

class TestKodowanieZnakow:
    """Polskie znaki w JSONL i config.json nie powodują błędów."""

    def test_polskie_znaki_w_jsonl_sa_ignorowane(self, tmp_path):
        """Plik JSONL z polskimi znakami w polach tekstowych nie psuje parsowania tokenów."""
        claude_dir = tmp_path / "claude"
        projekt = claude_dir / "projects" / "proj"
        projekt.mkdir(parents=True)

        # Wpis z polskim tekstem w polu które normalnie nie ma tokenów
        wpis_z_polskim = json.dumps({
            "timestamp": f"{DZISIAJ}T10:00:00.000Z",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Zażółć gęślą jaźń"}],
            },
        }, ensure_ascii=False)

        wpis_normalny = wpis_jsonl(inp=1000, out=500)

        (projekt / "log.jsonl").write_text(
            wpis_z_polskim + "\n" + wpis_normalny, encoding="utf-8"
        )

        # Nie powinno rzucić wyjątku, powinno policzyć 1 wywołanie (z tokenami)
        stats = czytaj_uzycie(claude_dir=claude_dir)
        assert stats["liczba_wywolan"] == 1

    def test_polskie_znaki_w_config_zachowane(self, tmp_path):
        """Polskie znaki w polach config.json przeżywają zapis i odczyt."""
        cfg_plik = tmp_path / "config.json"
        cfg = {"komentarz": "Żółw zażółcił gęślą jaźń", "tryb": "pro"}
        cfg_plik.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

        odczytane = wczytaj_config(sciezka=cfg_plik)
        assert odczytane["komentarz"] == "Żółw zażółcił gęślą jaźń"
