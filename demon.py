"""
Monitor Tokenów — Demon
=======================
Czyta PLIKI JSONL Claude Code z ~/.claude/ i pokazuje
live dashboard zużycia tokenów + kosztów w terminalu.
Równolegle aktualizuje dzisiaj.json dla rozszerzenia VS Code.

Uruchomienie:
    python demon.py

Wymagania:
    pip install rich
"""

import json
import time
from datetime import date, datetime
from pathlib import Path

# ── Ścieżki ──────────────────────────────────────────────────────────────────
CLAUDE_DIR   = Path.home() / ".claude"
CONFIG_JSON  = Path(r"D:\MOJE PROJEKTY\Monitor-Tokenow\src\config.json")
DZISIAJ_JSON = Path(r"D:\MOJE PROJEKTY\Monitor-Tokenow\data\dzisiaj.json")
ODSWIEZAJ_CO = 30   # sekund


def wczytaj_config():
    """Wczytuje config.json — zwraca słownik z ustawieniami."""
    try:
        with open(CONFIG_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# Wczytaj przy starcie
_cfg          = wczytaj_config()
TRYB          = _cfg.get("tryb", "pro")          # "pro" lub "api"
LIMIT_DZIENNY = _cfg.get("budzet", {}).get("dzienny_limit_usd", 10.00)

# ── Cennik Anthropic (USD / 1M tokenów) ──────────────────────────────────────
CENNIK = {
    "claude-sonnet-4-6": {
        "wejscie": 3.00, "wyjscie": 15.00,
        "cache_create": 3.75, "cache_read": 0.30,
    },
    "claude-opus-4-7": {
        "wejscie": 15.00, "wyjscie": 75.00,
        "cache_create": 18.75, "cache_read": 1.50,
    },
    "claude-haiku-4-5-20251001": {
        "wejscie": 0.80, "wyjscie": 4.00,
        "cache_create": 1.00, "cache_read": 0.08,
    },
    "claude-haiku-4-5": {
        "wejscie": 0.80, "wyjscie": 4.00,
        "cache_create": 1.00, "cache_read": 0.08,
    },
}
DOMYSLNY_MODEL = "claude-sonnet-4-6"


# ── Odczyt danych ─────────────────────────────────────────────────────────────

def czytaj_uzycie():
    """Skanuje wszystkie JSONL z ~/.claude/ i sumuje tokeny z dzisiaj."""
    dzisiaj = date.today().isoformat()

    stats = {
        "data": dzisiaj,
        "liczba_wywolan": 0,
        "tokeny_wejscia": 0,
        "tokeny_wyjscia": 0,
        "cache_create": 0,
        "cache_read": 0,
        "laczne_tokeny": 0,
        "koszt_usd": 0.0,
        "modele": {},
        "ostatnia_aktualizacja": datetime.now().strftime("%H:%M:%S"),
    }

    for jsonl in CLAUDE_DIR.rglob("*.jsonl"):
        try:
            # Pomiń pliki niemodyfikowane dzisiaj (szybsza praca)
            mtime = datetime.fromtimestamp(jsonl.stat().st_mtime).date()
            if mtime < date.today():
                continue

            with open(jsonl, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue

                    # Filtruj po dacie
                    ts = obj.get("timestamp", "")
                    if not ts.startswith(dzisiaj):
                        continue

                    msg   = obj.get("message", {})
                    usage = msg.get("usage", {})
                    if not usage:
                        continue

                    inp = usage.get("input_tokens", 0)
                    out = usage.get("output_tokens", 0)
                    cc  = usage.get("cache_creation_input_tokens", 0)
                    cr  = usage.get("cache_read_input_tokens", 0)

                    if inp == 0 and out == 0 and cc == 0 and cr == 0:
                        continue

                    model = msg.get("model", DOMYSLNY_MODEL)
                    ceny  = CENNIK.get(model, CENNIK[DOMYSLNY_MODEL])
                    koszt = (
                        inp / 1_000_000 * ceny["wejscie"]  +
                        out / 1_000_000 * ceny["wyjscie"]  +
                        cc  / 1_000_000 * ceny["cache_create"] +
                        cr  / 1_000_000 * ceny["cache_read"]
                    )

                    stats["liczba_wywolan"] += 1
                    stats["tokeny_wejscia"] += inp
                    stats["tokeny_wyjscia"] += out
                    stats["cache_create"]   += cc
                    stats["cache_read"]     += cr
                    stats["laczne_tokeny"]  += inp + out + cc + cr
                    stats["koszt_usd"]      += koszt

                    krotka = stats["modele"].setdefault(model, {
                        "wywolania": 0, "tokeny": 0, "koszt_usd": 0.0
                    })
                    krotka["wywolania"] += 1
                    krotka["tokeny"]    += inp + out + cc + cr
                    krotka["koszt_usd"] += koszt

        except Exception:
            continue

    return stats


def zapisz_json(stats):
    """Aktualizuje dzisiaj.json dla rozszerzenia VS Code."""
    DZISIAJ_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(DZISIAJ_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


# ── Dashboard (rich) ──────────────────────────────────────────────────────────

def _tabela_tokenow(stats, box):
    """Wspólna tabela tokenów dla obu trybów."""
    from rich.table import Table
    laczne = stats["laczne_tokeny"]
    t = Table(box=box.ROUNDED, show_header=False, padding=(0, 2),
              border_style="bright_blue")
    t.add_column("Etykieta", style="dim", width=26)
    t.add_column("Wartość",  style="bold white")
    t.add_row("Wywołania API",
              f"[cyan]{stats['liczba_wywolan']}[/cyan]")
    t.add_row("Tokeny wejście",
              f"{stats['tokeny_wejscia']:,}".replace(",", " "))
    t.add_row("Tokeny wyjście",
              f"{stats['tokeny_wyjscia']:,}".replace(",", " "))
    t.add_row("Cache create",
              f"{stats['cache_create']:,}".replace(",", " "))
    t.add_row("Cache read",
              f"{stats['cache_read']:,}".replace(",", " "))
    t.add_row("─" * 24, "─" * 16)
    t.add_row("Tokeny łącznie",
              f"[bold cyan]{laczne:,}[/bold cyan]".replace(",", " "))
    return t


def _tabela_modeli(stats, naglowek_kosztu, box):
    """Tabela podziału wg modelu."""
    from rich.table import Table
    mt = Table(box=box.SIMPLE, show_header=True, padding=(0, 1),
               border_style="dim")
    mt.add_column("Model",          style="cyan", width=28)
    mt.add_column("Wywołania",      justify="right", width=10)
    mt.add_column("Tokeny",         justify="right", width=14)
    mt.add_column(naglowek_kosztu,  justify="right", width=14)
    for nazwa, dane in sorted(stats["modele"].items(),
                              key=lambda x: x[1]["koszt_usd"], reverse=True):
        mt.add_row(
            nazwa,
            str(dane["wywolania"]),
            f"{dane['tokeny']:,}".replace(",", " "),
            f"${dane['koszt_usd']:.4f}",
        )
    if not stats["modele"]:
        mt.add_row("[dim]brak danych[/dim]", "", "", "")
    return mt


def _pasek_budzetu(procent):
    """Pasek z kolorowymi progami 80% / 95% / 100%."""
    from rich.text import Text as RT
    dl     = 40
    p80    = int(0.80 * dl)
    p95    = int(0.95 * dl)
    wypeln = min(int(procent / 100 * dl), dl)

    pasek = RT("  ")
    for i in range(dl):
        if i < wypeln:
            styl = "bold green" if i < p80 else ("bold yellow" if i < p95 else "bold red")
        else:
            styl = "dim"
        pasek.append("█" if i < wypeln else "░", style=styl)

    linijka = RT("  ")
    for i in range(dl):
        if i == p80:   linijka.append("┬", style="yellow")
        elif i == p95: linijka.append("┬", style="red")
        else:          linijka.append("─", style="dim")

    etykiety = RT("  ")
    etykiety.append("0%",  style="dim")
    etykiety.append(" " * (p80 - 4))
    etykiety.append("80%",  style="bold green")
    etykiety.append(" " * (p95 - p80 - 4))
    etykiety.append("95%",  style="bold yellow")
    etykiety.append(" " * (dl - p95 - 4))
    etykiety.append("100%", style="bold red")

    return pasek, linijka, etykiety


def buduj_dashboard(stats):
    """Buduje dashboard w zależności od trybu (pro / api)."""
    from rich.panel import Panel
    from rich.text import Text
    from rich.console import Group
    from rich import box as rich_box

    akt   = stats.get("ostatnia_aktualizacja", "–")
    koszt = stats["koszt_usd"]

    if TRYB == "pro":
        # ── TRYB PRO ──────────────────────────────────────────────────────
        t = _tabela_tokenow(stats, rich_box)
        t.add_row("─" * 24, "─" * 16)
        t.add_row("Ekwiwalent API",
                  f"[dim](teoretyczny)[/dim] [bold white]${koszt:.4f}[/bold white]")
        t.add_row("Abonament",
                  "[bold green]Claude Pro  $20/mies.[/bold green]")

        mt = _tabela_modeli(stats, "Ekwiwalent $", rich_box)

        info = Text()
        info.append("  ℹ  ", style="bold cyan")
        info.append("Tryb PRO — koszt realny: $20/mies. niezależnie od użycia. "
                    "Ekwiwalent API to wartość informacyjna.", style="dim")

        tytul = (f"[bold bright_blue]Monitor Tokenów[/bold bright_blue]  "
                 f"[bold green]● PRO[/bold green]  "
                 f"[dim]│  {stats['data']}  │  ostatni: {akt}[/dim]")

        content = Group(
            t, Text(""),
            info, Text(""),
            Text("Podział wg modelu", style="bold dim"),
            mt,
        )

    else:
        # ── TRYB API ──────────────────────────────────────────────────────
        limit   = LIMIT_DZIENNY
        procent = koszt / limit * 100 if limit > 0 else 0
        kolor_p = ("bold red" if procent >= 95
                   else "bold yellow" if procent >= 80 else "bold green")

        t = _tabela_tokenow(stats, rich_box)
        t.add_row("─" * 24, "─" * 16)
        t.add_row("Koszt dziś",    f"[bold white]${koszt:.6f}[/bold white]")
        t.add_row("Limit dzienny", f"${limit:.2f}")
        t.add_row("Wykorzystano",  f"[{kolor_p}]{procent:.1f}%[/{kolor_p}]")

        pasek, linijka, etykiety = _pasek_budzetu(procent)
        mt = _tabela_modeli(stats, "Koszt USD", rich_box)

        tytul = (f"[bold bright_blue]Monitor Tokenów[/bold bright_blue]  "
                 f"[bold yellow]● API[/bold yellow]  "
                 f"[dim]│  {stats['data']}  │  ostatni: {akt}[/dim]")

        content = Group(
            t, Text(""),
            pasek, linijka, etykiety, Text(""),
            Text("Podział wg modelu", style="bold dim"),
            mt,
        )

    return Panel(content, title=tytul, border_style="bright_blue", padding=(1, 2))


# ── Główna pętla ──────────────────────────────────────────────────────────────

def main():
    try:
        from rich.console import Console
        uzywaj_rich = True
    except ImportError:
        uzywaj_rich = False

    if not uzywaj_rich:
        print("Zainstaluj rich:  pip install rich")
        print("Uruchamiam tryb tekstowy...\n")
        while True:
            s = czytaj_uzycie()
            zapisz_json(s)
            print(f"[{s['ostatnia_aktualizacja']}]  "
                  f"Wywołania: {s['liczba_wywolan']}  "
                  f"Tokeny: {s['laczne_tokeny']:,}  "
                  f"Koszt: ${s['koszt_usd']:.6f}")
            time.sleep(ODSWIEZAJ_CO)
        return

    import io, sys, os
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace", line_buffering=True)
    console = Console(force_terminal=True, highlight=False)

    while True:
        stats = czytaj_uzycie()
        zapisz_json(stats)
        console.clear()
        console.print(buduj_dashboard(stats))
        # Odliczanie do następnego odświeżenia — bez migania
        for pozostalo in range(ODSWIEZAJ_CO, 0, -1):
            console.print(
                f"  [dim]Następne odświeżenie za [cyan]{pozostalo}s[/cyan] "
                f"— Ctrl+C aby zakończyć[/dim]",
                end="\r"
            )
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor zatrzymany.")
