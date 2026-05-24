"""
Testy funkcji czytaj_uzycie() — odczyt tokenów z plików JSONL.
"""
import sys
sys.path.insert(0, r"D:\MOJE PROJEKTY\Monitor-Tokenow")

import pytest
from datetime import date
from helpers import wpis_jsonl, DZISIAJ, WCZORAJ
from tray_monitor import czytaj_uzycie


class TestPusteŹródła:

    def test_pusty_katalog_zwraca_zera(self, katalog_claude):
        stats = czytaj_uzycie(claude_dir=katalog_claude)

        assert stats["liczba_wywolan"] == 0
        assert stats["laczne_tokeny"] == 0
        assert stats["koszt_usd"] == 0.0

    def test_brakujacy_katalog_nie_rzuca_wyjatku(self, tmp_path):
        nieistniejacy = tmp_path / "ghost"
        stats = czytaj_uzycie(claude_dir=nieistniejacy)

        assert stats["liczba_wywolan"] == 0

    def test_pusty_plik_jsonl(self, plik_jsonl):
        plik_jsonl([])
        stats = czytaj_uzycie(claude_dir=plik_jsonl([]))

        assert stats["liczba_wywolan"] == 0

    def test_plik_z_pustymi_liniami(self, plik_jsonl):
        katalog = plik_jsonl(["", "   ", ""])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert stats["liczba_wywolan"] == 0


class TestFiltrowaniePodacie:

    def test_wpis_dzisiejszy_jest_liczony(self, plik_jsonl):
        katalog = plik_jsonl([wpis_jsonl(inp=1000, out=500, data=DZISIAJ)])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert stats["liczba_wywolan"] == 1
        assert stats["tokeny_wejscia"] == 1000
        assert stats["tokeny_wyjscia"] == 500

    def test_wpis_wczorajszy_jest_pomijany(self, plik_jsonl):
        katalog = plik_jsonl([wpis_jsonl(inp=999, out=999, data=WCZORAJ)])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert stats["liczba_wywolan"] == 0

    def test_mieszane_daty_liczy_tylko_dzisiejsze(self, plik_jsonl):
        katalog = plik_jsonl([
            wpis_jsonl(inp=100, data=DZISIAJ),
            wpis_jsonl(inp=999, data=WCZORAJ),
            wpis_jsonl(inp=200, data=DZISIAJ),
        ])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert stats["liczba_wywolan"] == 2
        assert stats["tokeny_wejscia"] == 300


class TestSumowaniaTokenow:

    def test_sumuje_wejscie_i_wyjscie(self, plik_jsonl):
        katalog = plik_jsonl([
            wpis_jsonl(inp=1000, out=200),
            wpis_jsonl(inp=500,  out=100),
        ])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert stats["tokeny_wejscia"] == 1500
        assert stats["tokeny_wyjscia"] == 300
        assert stats["laczne_tokeny"] == 1800

    def test_sumuje_cache(self, plik_jsonl):
        katalog = plik_jsonl([
            wpis_jsonl(inp=0, out=0, cc=5000, cr=2000),
        ])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert stats["cache_create"] == 5000
        assert stats["cache_read"] == 2000
        assert stats["laczne_tokeny"] == 7000

    def test_pomija_wpis_z_zerami(self, plik_jsonl):
        katalog = plik_jsonl([
            wpis_jsonl(inp=0, out=0, cc=0, cr=0),
        ])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert stats["liczba_wywolan"] == 0

    def test_pomija_wpis_bez_usage(self, plik_jsonl):
        import json
        wpis_bez_usage = json.dumps({
            "timestamp": f"{DZISIAJ}T10:00:00Z",
            "message": {"model": "claude-sonnet-4-6"},
        })
        katalog = plik_jsonl([wpis_bez_usage])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert stats["liczba_wywolan"] == 0


class TestPodziałuModeli:

    def test_rozdziela_wywolania_per_model(self, plik_jsonl):
        katalog = plik_jsonl([
            wpis_jsonl(model="claude-sonnet-4-6",         inp=1000),
            wpis_jsonl(model="claude-haiku-4-5-20251001", inp=2000),
            wpis_jsonl(model="claude-sonnet-4-6",         inp=500),
        ])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert stats["modele"]["claude-sonnet-4-6"]["wywolania"] == 2
        assert stats["modele"]["claude-haiku-4-5-20251001"]["wywolania"] == 1

    def test_nieznany_model_uzywa_domyslnego_cennika(self, plik_jsonl):
        katalog = plik_jsonl([
            wpis_jsonl(model="claude-unknown-99", inp=1_000_000, out=0),
        ])
        stats = czytaj_uzycie(claude_dir=katalog)

        # Domyślny model: sonnet $3.00/M input
        assert abs(stats["koszt_usd"] - 3.00) < 0.0001
