"""
Pomocnicze stałe i funkcje współdzielone przez testy.
"""
import json
from datetime import date

DZISIAJ = date.today().isoformat()
WCZORAJ = "2026-05-23"


def wpis_jsonl(model="claude-sonnet-4-6", inp=1000, out=500, cc=0, cr=0, data=None):
    """Zwraca jeden poprawny wpis JSONL jako string."""
    data = data or DZISIAJ
    return json.dumps({
        "timestamp": f"{data}T12:00:00.000Z",
        "message": {
            "model": model,
            "usage": {
                "input_tokens": inp,
                "output_tokens": out,
                "cache_creation_input_tokens": cc,
                "cache_read_input_tokens": cr,
            },
        },
    })
