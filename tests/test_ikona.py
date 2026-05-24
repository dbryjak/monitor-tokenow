"""
Testy generowania ikony systemowej stworz_ikone().
"""
import sys
sys.path.insert(0, r"D:\MOJE PROJEKTY\Monitor-Tokenow")

import pytest
from PIL import Image
from tray_monitor import stworz_ikone


class TestStworZIkone:

    def test_zwraca_obiekt_image(self):
        ikona = stworz_ikone("pro")

        assert isinstance(ikona, Image.Image)

    def test_rozmiar_64x64(self):
        ikona = stworz_ikone("pro")

        assert ikona.size == (64, 64)

    def test_tryb_pro_zielona_ikona(self):
        ikona = stworz_ikone("pro")
        # Próbkuj bok kółka (x=12, y=32) — tam jest kolor, nie litera
        r, g, b, _ = ikona.getpixel((12, 32))

        assert g > r and g > b  # zielony dominuje

    def test_tryb_api_niebieska_ikona(self):
        ikona = stworz_ikone("api")
        r, g, b, _ = ikona.getpixel((12, 32))

        assert b > r  # niebieski dominuje

    def test_alarm_czerwona_ikona(self):
        ikona = stworz_ikone("pro", alarm=True)
        r, g, b, _ = ikona.getpixel((12, 32))

        assert r > g and r > b  # czerwony dominuje

    def test_tryb_api_i_pro_roznia_sie(self):
        pro = stworz_ikone("pro")
        api = stworz_ikone("api")

        assert pro.tobytes() != api.tobytes()

    def test_alarm_rozni_sie_od_normalnej(self):
        normalna = stworz_ikone("pro", alarm=False)
        alarmowa = stworz_ikone("pro", alarm=True)

        assert normalna.tobytes() != alarmowa.tobytes()
