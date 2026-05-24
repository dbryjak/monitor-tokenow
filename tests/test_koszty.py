"""
Testy obliczania kosztów per model i filtrowania dat w czytaj_wydatki_od().
"""
import sys
sys.path.insert(0, r"D:\MOJE PROJEKTY\Monitor-Tokenow")

import pytest
from helpers import wpis_jsonl, DZISIAJ, WCZORAJ
from tray_monitor import czytaj_uzycie, czytaj_wydatki_od


class TestCennikModeli:

    @pytest.mark.parametrize("model,inp,out,oczekiwany", [
        ("claude-sonnet-4-6",         1_000_000, 0, 3.00),
        ("claude-sonnet-4-6",         0, 1_000_000, 15.00),
        ("claude-opus-4-7",           1_000_000, 0, 15.00),
        ("claude-opus-4-7",           0, 1_000_000, 75.00),
        ("claude-haiku-4-5-20251001", 1_000_000, 0, 0.80),
        ("claude-haiku-4-5-20251001", 0, 1_000_000, 4.00),
        ("claude-haiku-4-5",          1_000_000, 0, 0.80),
    ])
    def test_koszt_per_model(self, model, inp, out, oczekiwany, plik_jsonl):
        katalog = plik_jsonl([wpis_jsonl(model=model, inp=inp, out=out)])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert abs(stats["koszt_usd"] - oczekiwany) < 0.0001

    def test_koszt_cache_create(self, plik_jsonl):
        # Sonnet cache_create: $3.75/M — inp=0,out=0 żeby nie doliczać innych tokenów
        katalog = plik_jsonl([wpis_jsonl(model="claude-sonnet-4-6", inp=0, out=0, cc=1_000_000)])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert abs(stats["koszt_usd"] - 3.75) < 0.0001

    def test_koszt_cache_read(self, plik_jsonl):
        # Sonnet cache_read: $0.30/M
        katalog = plik_jsonl([wpis_jsonl(model="claude-sonnet-4-6", inp=0, out=0, cr=1_000_000)])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert abs(stats["koszt_usd"] - 0.30) < 0.0001

    def test_koszt_sumuje_wszystkie_typy_tokenow(self, plik_jsonl):
        # 1M inp ($3) + 1M out ($15) + 1M cc ($3.75) + 1M cr ($0.30) = $22.05
        katalog = plik_jsonl([
            wpis_jsonl(
                model="claude-sonnet-4-6",
                inp=1_000_000, out=1_000_000,
                cc=1_000_000, cr=1_000_000,
            )
        ])
        stats = czytaj_uzycie(claude_dir=katalog)

        assert abs(stats["koszt_usd"] - 22.05) < 0.001


class TestCzytajWydatkiOd:

    def test_liczy_wydatki_od_dzisiaj(self, plik_jsonl):
        katalog = plik_jsonl([
            wpis_jsonl(model="claude-sonnet-4-6", inp=1_000_000, out=0, data=DZISIAJ),
        ])
        wynik = czytaj_wydatki_od(DZISIAJ, claude_dir=katalog)

        assert abs(wynik - 3.00) < 0.0001

    def test_pomija_wpisy_przed_data(self, plik_jsonl):
        katalog = plik_jsonl([
            wpis_jsonl(inp=1_000_000, data=WCZORAJ),
        ])
        wynik = czytaj_wydatki_od(DZISIAJ, claude_dir=katalog)

        assert wynik == 0.0

    def test_sumuje_wpisy_z_wielu_dni(self, plik_jsonl):
        katalog = plik_jsonl([
            wpis_jsonl(model="claude-sonnet-4-6", inp=1_000_000, out=0, data=WCZORAJ),
            wpis_jsonl(model="claude-sonnet-4-6", inp=1_000_000, out=0, data=DZISIAJ),
        ])
        wynik = czytaj_wydatki_od(WCZORAJ, claude_dir=katalog)

        assert abs(wynik - 6.00) < 0.0001  # 2x $3.00

    def test_niepoprawna_data_zwraca_zero(self, katalog_claude):
        wynik = czytaj_wydatki_od("nie-data", claude_dir=katalog_claude)

        assert wynik == 0.0

    def test_pusty_katalog_zwraca_zero(self, katalog_claude):
        wynik = czytaj_wydatki_od(DZISIAJ, claude_dir=katalog_claude)

        assert wynik == 0.0
