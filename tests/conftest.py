"""
Fixtures współdzielone przez wszystkie testy.
"""
import json
import pytest
from datetime import date
from pathlib import Path


@pytest.fixture
def katalog_claude(tmp_path):
    """Tymczasowy katalog udający ~/.claude/ z jednym plikiem JSONL."""
    projekty = tmp_path / "projects" / "test-projekt"
    projekty.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def plik_jsonl(katalog_claude):
    """Fixture zwracająca funkcję tworzącą plik JSONL z podanymi wpisami."""
    def _tworz(wpisy: list[str], nazwa="test.jsonl"):
        p = katalog_claude / "projects" / "test-projekt" / nazwa
        p.write_text("\n".join(wpisy), encoding="utf-8")
        return katalog_claude
    return _tworz


@pytest.fixture
def config_plik(tmp_path):
    """Tymczasowy config.json z domyślnymi wartościami."""
    cfg = {
        "tryb": "pro",
        "budzet": {"dzienny_limit_usd": 10.0},
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p
