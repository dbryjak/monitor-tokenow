# =============================================================
# logger.py — Moduł logowania zdarzeń i zliczania tokenów
# =============================================================

import json
import os
from datetime import datetime, date

# Ścieżka do pliku z logami (względem tego skryptu)
SCIEZKA_LOGU = os.path.join(os.path.dirname(__file__), '..', 'data', 'usage.log')
SCIEZKA_DANYCH = os.path.join(os.path.dirname(__file__), '..', 'data', 'dzisiaj.json')


def _znacznik_czasu():
    """Zwraca aktualny czas w formacie czytelnym dla człowieka."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def zapisz_log(poziom, wiadomosc):
    """
    Zapisuje wpis do pliku usage.log.
    Poziomy: INFO, WARNING, ERROR
    """
    wpis = f"{_znacznik_czasu()} | {poziom:<7} | {wiadomosc}\n"

    # Wypisz też w konsoli żeby było widać co się dzieje
    print(wpis.strip())

    # Dopisz do pliku (nie nadpisuj - chcemy historię)
    with open(SCIEZKA_LOGU, 'a', encoding='utf-8') as f:
        f.write(wpis)


def zapisz_uzycie(model, tokeny_wejscia, tokeny_wyjscia, koszt_usd):
    """
    Zapisuje dane o zużyciu tokenów z jednego wywołania API.
    Aktualizuje też dzienny licznik w dzisiaj.json.
    """
    laczne_tokeny = tokeny_wejscia + tokeny_wyjscia

    # Wpisz do logu czytelny wpis
    wiadomosc = (
        f"Model: {model} | "
        f"Wejście: {tokeny_wejscia} tok | "
        f"Wyjście: {tokeny_wyjscia} tok | "
        f"Łącznie: {laczne_tokeny} tok | "
        f"Koszt: ${koszt_usd:.6f}"
    )
    zapisz_log("INFO", wiadomosc)

    # Zaktualizuj dzienny licznik
    _aktualizuj_dzienny_licznik(tokeny_wejscia, tokeny_wyjscia, koszt_usd)


def _aktualizuj_dzienny_licznik(tokeny_wejscia, tokeny_wyjscia, koszt_usd):
    """
    Aktualizuje plik dzisiaj.json z sumą tokenów za dzisiaj.
    Resetuje się automatycznie każdego dnia.
    """
    dzisiaj = str(date.today())

    # Wczytaj istniejące dane lub zacznij od zera
    if os.path.exists(SCIEZKA_DANYCH):
        with open(SCIEZKA_DANYCH, 'r', encoding='utf-8') as f:
            dane = json.load(f)
    else:
        dane = {}

    # Jeśli to nowy dzień - resetuj licznik
    if dane.get('data') != dzisiaj:
        dane = {
            'data': dzisiaj,
            'tokeny_wejscia': 0,
            'tokeny_wyjscia': 0,
            'laczne_tokeny': 0,
            'koszt_usd': 0.0,
            'liczba_wywolan': 0
        }

    # Dodaj nowe dane
    dane['tokeny_wejscia'] += tokeny_wejscia
    dane['tokeny_wyjscia'] += tokeny_wyjscia
    dane['laczne_tokeny'] += tokeny_wejscia + tokeny_wyjscia
    dane['koszt_usd'] += koszt_usd
    dane['liczba_wywolan'] += 1

    # Zapisz zaktualizowane dane
    with open(SCIEZKA_DANYCH, 'w', encoding='utf-8') as f:
        json.dump(dane, f, indent=2, ensure_ascii=False)


def pobierz_statystyki_dnia():
    """
    Zwraca słownik ze statystykami dzisiejszego dnia.
    Używane przez VS Code extension i alerty.
    """
    dzisiaj = str(date.today())

    if not os.path.exists(SCIEZKA_DANYCH):
        # Brak danych - zwróć puste statystyki
        return {
            'data': dzisiaj,
            'tokeny_wejscia': 0,
            'tokeny_wyjscia': 0,
            'laczne_tokeny': 0,
            'koszt_usd': 0.0,
            'liczba_wywolan': 0
        }

    with open(SCIEZKA_DANYCH, 'r', encoding='utf-8') as f:
        dane = json.load(f)

    # Jeśli plik jest z poprzedniego dnia - zwróć zerowe dane
    if dane.get('data') != dzisiaj:
        return {
            'data': dzisiaj,
            'tokeny_wejscia': 0,
            'tokeny_wyjscia': 0,
            'laczne_tokeny': 0,
            'koszt_usd': 0.0,
            'liczba_wywolan': 0
        }

    return dane
