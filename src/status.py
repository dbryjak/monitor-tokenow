# =============================================================
# status.py — Szybki podgląd statystyk z linii poleceń
# =============================================================
# UŻYCIE:
#   python status.py          -> czytelne podsumowanie
#   python status.py --json   -> surowy JSON (używany przez extension)
# =============================================================

import sys
import json
import os

# Wymuś UTF-8 w terminalu Windows (bez tego emoji crashują)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from logger import pobierz_statystyki_dnia

SCIEZKA_KONFIG = os.path.join(os.path.dirname(__file__), 'config.json')


def pobierz_limit():
    """Wczytuje dzienny limit z config.json."""
    try:
        with open(SCIEZKA_KONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)['budzet']['dzienny_limit_usd']
    except Exception:
        return 10.00  # domyślny limit jeśli plik niedostępny


def main():
    stats = pobierz_statystyki_dnia()
    limit = pobierz_limit()
    procent = stats['koszt_usd'] / limit * 100 if limit > 0 else 0

    # Dodaj limit i procent do danych
    stats['limit_usd'] = limit
    stats['procent_budzetu'] = round(procent, 2)

    # Tryb JSON — dla VS Code extension
    if '--json' in sys.argv:
        print(json.dumps(stats, ensure_ascii=False))
        return

    # Tryb czytelny — dla człowieka
    if procent >= 95:
        ikona = '🔴'
    elif procent >= 80:
        ikona = '🟡'
    else:
        ikona = '🟢'

    print(f"\n{'='*52}")
    print(f"  {ikona}  MONITOR TOKENÓW ANTHROPIC — {stats['data']}")
    print(f"{'='*52}")
    print(f"  Wywołania API :  {stats['liczba_wywolan']}")
    print(f"  Tokeny wejście:  {stats['tokeny_wejscia']:,}")
    print(f"  Tokeny wyjście:  {stats['tokeny_wyjscia']:,}")
    print(f"  Tokeny łącznie:  {stats['laczne_tokeny']:,}")
    print(f"  Koszt:           ${stats['koszt_usd']:.6f}")
    print(f"  Budżet:          ${stats['koszt_usd']:.4f} / ${limit:.2f}  ({procent:.1f}%)")
    print(f"{'='*52}\n")


if __name__ == '__main__':
    main()
