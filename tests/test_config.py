"""
Testy wczytaj_config(), zapisz_tryb() i auto_zapisz_date_salda().
"""
import sys
sys.path.insert(0, r"D:\MOJE PROJEKTY\Monitor-Tokenow")

import json
import pytest
from datetime import date
from tray_monitor import wczytaj_config, zapisz_tryb, auto_zapisz_date_salda


class TestWczytajConfig:

    def test_wczytuje_poprawny_json(self, config_plik):
        cfg = wczytaj_config(config_plik)

        assert cfg["tryb"] == "pro"
        assert cfg["budzet"]["dzienny_limit_usd"] == 10.0

    def test_brakujacy_plik_zwraca_pusty_slownik(self, tmp_path):
        cfg = wczytaj_config(tmp_path / "nie_istnieje.json")

        assert cfg == {}

    def test_bledny_json_zwraca_pusty_slownik(self, tmp_path):
        p = tmp_path / "zepsuty.json"
        p.write_text("{ to nie jest json !!!", encoding="utf-8")

        cfg = wczytaj_config(p)

        assert cfg == {}


class TestZapiszTryb:

    def test_zapisuje_tryb_api(self, config_plik):
        zapisz_tryb("api", sciezka=config_plik)
        cfg = json.loads(config_plik.read_text())

        assert cfg["tryb"] == "api"

    def test_zapisuje_tryb_pro(self, config_plik):
        zapisz_tryb("pro", sciezka=config_plik)
        cfg = json.loads(config_plik.read_text())

        assert cfg["tryb"] == "pro"

    def test_zachowuje_pozostale_klucze(self, config_plik):
        zapisz_tryb("api", sciezka=config_plik)
        cfg = json.loads(config_plik.read_text())

        assert "budzet" in cfg  # oryginalne klucze nie znikają

    def test_brakujacy_plik_nie_rzuca_wyjatku(self, tmp_path):
        zapisz_tryb("api", sciezka=tmp_path / "ghost.json")
        # brak wyjątku = test zaliczony


class TestAutoZapiszDateSalda:

    def test_dodaje_date_gdy_brak(self, config_plik):
        cfg = {"saldo_api_usd": 5.00}

        wynik = auto_zapisz_date_salda(cfg, sciezka=config_plik)

        assert wynik["saldo_data_wpisania"] == date.today().isoformat()

    def test_nie_nadpisuje_istniejaca_daty(self, config_plik):
        stara_data = "2026-01-01"
        cfg = {"saldo_api_usd": 5.00, "saldo_data_wpisania": stara_data}

        wynik = auto_zapisz_date_salda(cfg, sciezka=config_plik)

        assert wynik["saldo_data_wpisania"] == stara_data

    def test_bez_salda_nic_nie_robi(self, config_plik):
        cfg = {"tryb": "pro"}

        wynik = auto_zapisz_date_salda(cfg, sciezka=config_plik)

        assert "saldo_data_wpisania" not in wynik

    def test_zapisuje_date_do_pliku(self, config_plik):
        cfg = {"saldo_api_usd": 3.78}

        auto_zapisz_date_salda(cfg, sciezka=config_plik)
        zapisany = json.loads(config_plik.read_text())

        assert zapisany["saldo_data_wpisania"] == date.today().isoformat()
