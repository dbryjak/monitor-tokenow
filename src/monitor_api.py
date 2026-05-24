# =============================================================
# monitor_api.py — Główny skrypt monitora tokenów Anthropic
# =============================================================
# JAK UŻYWAĆ:
#   from monitor_api import MonitorAPI
#   monitor = MonitorAPI()
#   odpowiedz = monitor.wyslij("Napisz mi haiku o Pythonie")
#   print(odpowiedz)
#   monitor.pokaz_statystyki()
# =============================================================

import os
import json
import anthropic
from logger import zapisz_log, zapisz_uzycie, pobierz_statystyki_dnia

# Ścieżka do pliku konfiguracyjnego
SCIEZKA_KONFIG = os.path.join(os.path.dirname(__file__), 'config.json')

# Cennik Anthropic (USD za 1 milion tokenów, stan na 2025)
# Źródło: https://www.anthropic.com/pricing
CENNIK = {
    'claude-haiku-4-5-20251001': {
        'wejscie': 0.80,    # $0.80 za 1M tokenów wejściowych
        'wyjscie': 4.00     # $4.00 za 1M tokenów wyjściowych
    },
    'claude-sonnet-4-6': {
        'wejscie': 3.00,
        'wyjscie': 15.00
    },
    'claude-opus-4-7': {
        'wejscie': 15.00,
        'wyjscie': 75.00
    }
}


def oblicz_koszt(model, tokeny_wejscia, tokeny_wyjscia):
    """
    Oblicza koszt w USD na podstawie liczby tokenów i modelu.
    Jeśli model nie jest w cenniku, zwraca 0 i loguje ostrzeżenie.
    """
    if model not in CENNIK:
        zapisz_log("WARNING", f"Nieznany model '{model}' - koszt nie zostanie obliczony")
        return 0.0

    ceny = CENNIK[model]
    koszt = (tokeny_wejscia / 1_000_000 * ceny['wejscie'] +
             tokeny_wyjscia / 1_000_000 * ceny['wyjscie'])
    return koszt


class MonitorAPI:
    """
    Wrapper na klienta Anthropic.
    Każde wywołanie automatycznie loguje tokeny i koszt.
    """

    def __init__(self):
        # Wczytaj konfigurację z pliku
        self.konfig = self._wczytaj_konfig()

        # Pobierz klucz API - najpierw z env, potem z configa
        klucz = os.environ.get('ANTHROPIC_API_KEY') or self.konfig['api']['klucz']

        if klucz == 'sk-ant-TWOJ-KLUCZ-TUTAJ':
            raise ValueError(
                "Brak klucza API! Ustaw zmienną środowiskową ANTHROPIC_API_KEY "
                "lub wpisz klucz w config.json"
            )

        self.klient = anthropic.Anthropic(api_key=klucz)
        self.model = self.konfig.get('model', 'claude-haiku-4-5-20251001')
        self.limit_usd = self.konfig['budzet']['dzienny_limit_usd']
        self.prog_ostrzezenia = self.konfig['budzet']['prog_ostrzezenia_procent'] / 100

        zapisz_log("INFO", f"MonitorAPI uruchomiony | Model: {self.model} | Limit dzienny: ${self.limit_usd}")

    def _wczytaj_konfig(self):
        """Wczytuje plik config.json."""
        with open(SCIEZKA_KONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)

    def wyslij(self, wiadomosc, system=None):
        """
        Wysyła wiadomość do API i zwraca odpowiedź tekstową.
        Automatycznie loguje zużycie tokenów.
        """
        # Sprawdź czy nie przekroczono budżetu przed wysłaniem
        self._sprawdz_budzet()

        # Przygotuj parametry wywołania
        parametry = {
            'model': self.model,
            'max_tokens': 1024,
            'messages': [{'role': 'user', 'content': wiadomosc}]
        }
        if system:
            parametry['system'] = system

        # Wyślij do API
        odpowiedz = self.klient.messages.create(**parametry)

        # Pobierz dane o zużyciu z odpowiedzi
        tokeny_wejscia = odpowiedz.usage.input_tokens
        tokeny_wyjscia = odpowiedz.usage.output_tokens
        koszt = oblicz_koszt(self.model, tokeny_wejscia, tokeny_wyjscia)

        # Zapisz do logu
        zapisz_uzycie(self.model, tokeny_wejscia, tokeny_wyjscia, koszt)

        # Sprawdź budżet po wysłaniu (może teraz przekroczyliśmy próg)
        self._sprawdz_budzet()

        return odpowiedz.content[0].text

    def _sprawdz_budzet(self):
        """Sprawdza czy dzienny budżet nie jest przekroczony i wysyła alerty."""
        stats = pobierz_statystyki_dnia()
        wydano = stats['koszt_usd']
        procent = wydano / self.limit_usd if self.limit_usd > 0 else 0

        if procent >= 1.0:
            zapisz_log("ERROR",
                f"PRZEKROCZONO BUDŻET! Wydano: ${wydano:.4f} / Limit: ${self.limit_usd:.2f}")
        elif procent >= self.prog_ostrzezenia:
            zapisz_log("WARNING",
                f"Zbliżasz się do limitu! Wydano: ${wydano:.4f} ({procent*100:.0f}%) / Limit: ${self.limit_usd:.2f}")

    def pokaz_statystyki(self):
        """Wypisuje czytelne podsumowanie dzisiejszego dnia."""
        stats = pobierz_statystyki_dnia()
        procent = stats['koszt_usd'] / self.limit_usd * 100 if self.limit_usd > 0 else 0

        print("\n" + "="*50)
        print(f"  STATYSTYKI NA DZIŚ ({stats['data']})")
        print("="*50)
        print(f"  Wywołania API:    {stats['liczba_wywolan']}")
        print(f"  Tokeny wejście:   {stats['tokeny_wejscia']:,}")
        print(f"  Tokeny wyjście:   {stats['tokeny_wyjscia']:,}")
        print(f"  Tokeny łącznie:   {stats['laczne_tokeny']:,}")
        print(f"  Koszt:            ${stats['koszt_usd']:.6f}")
        print(f"  Budżet:           ${self.limit_usd:.2f} ({procent:.1f}% wykorzystane)")
        print("="*50 + "\n")
        return stats


# =============================================================
# Uruchomienie testowe (tylko gdy odpalisz ten plik bezpośrednio)
# =============================================================
if __name__ == '__main__':
    print("Test monitora tokenów...\n")

    monitor = MonitorAPI()

    # Wyślij testową wiadomość
    odpowiedz = monitor.wyslij("Powiedz tylko: 'Test OK' i nic więcej.")
    print(f"\nOdpowiedź API: {odpowiedz}")

    # Pokaż statystyki
    monitor.pokaz_statystyki()
