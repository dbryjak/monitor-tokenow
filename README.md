# Monitor Tokenów Claude

Desktop app for Windows that tracks Claude AI token usage in real time.
Reads local Claude Code JSONL logs — no API key required for PRO mode.

![Python](https://img.shields.io/badge/Python-3.14-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What it does

- Sits in the **Windows System Tray** (near the clock)
- Click the icon → shows a popup window with today's token stats
- Reads `~/.claude/**/*.jsonl` files written by Claude Code
- Calculates theoretical cost based on Anthropic pricing
- Two modes: **PRO** (flat $20/month subscription) and **API** (pay-per-token credits)
- **Terminal dashboard** (`demon.py`) — full-screen rich display with budget bar

---

## Screenshots

| Tray popup — PRO mode | Terminal dashboard |
|---|---|
| Real-time token stats | Budget bar + countdown |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/dbryjak/monitor-tokenow.git
cd monitor-tokenow

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install pystray pillow rich

# 4. Configure
copy src\config.example.json src\config.json
# Edit src\config.json — set your mode (pro/api) and daily budget

# 5a. Run tray icon (silent, no console window)
double-click START_TRAY.vbs

# 5b. Run terminal dashboard
double-click START_MONITOR.bat
```

---

## Modes

### PRO mode (`"tryb": "pro"`)
For Claude.ai subscribers ($20/month flat fee).
Shows **theoretical equivalent cost** — how much the same usage would cost on API.
No real money is being spent.

### API mode (`"tryb": "api"`)
For Anthropic API credit users (pay-per-token).
Shows **real cost** deducted from your credit balance.
Enter your balance once via the "Update balance" button — the app tracks spending automatically.

---

## Project Structure

```
Monitor-Tokenow/
├── tray_monitor.py       # System tray icon + popup window (main app)
├── demon.py              # Terminal dashboard (rich)
├── START_TRAY.vbs        # Silent launcher (no CMD window)
├── START_MONITOR.bat     # Terminal dashboard launcher
├── src/
│   ├── config.json       # Your configuration (not committed)
│   ├── config.example.json  # Template
│   ├── monitor_api.py    # Token reading logic
│   ├── logger.py         # File logging
│   └── status.py         # Status helpers
├── tests/                # Pytest test suite (10 test cases)
│   ├── test_config.py
│   ├── test_czytaj_uzycie.py
│   ├── test_ikona.py
│   └── test_koszty.py
├── data/
│   └── usage.log         # Auto-generated usage history
├── vscode-extension/
│   └── monitor-tokenow-0.1.0.vsix  # VS Code status bar extension
└── docs/
    └── README.md
```

---

## How token reading works

Claude Code stores every conversation in JSONL files:
```
~/.claude/projects/<project-hash>/<session-id>.jsonl
```

Each line contains token usage:
```json
{
  "timestamp": "2026-05-24T10:30:00Z",
  "message": {
    "model": "claude-sonnet-4-6",
    "usage": {
      "input_tokens": 1500,
      "output_tokens": 320,
      "cache_creation_input_tokens": 800,
      "cache_read_input_tokens": 12000
    }
  }
}
```

The monitor reads all files, filters by today's date, and sums everything up.

---

## VS Code Extension

The included `.vsix` extension shows live token stats in the VS Code status bar.

Install:
```bash
code --install-extension vscode-extension\monitor-tokenow-0.1.0.vsix
```

Reads `data/dzisiaj.json` updated by the monitor every 60 seconds.

---

## Configuration (`src/config.json`)

```json
{
  "tryb": "pro",
  "budzet": {
    "dzienny_limit_usd": 10.0,
    "prog_ostrzezenia_procent": 80
  },
  "monitoring": {
    "czestotliwosc_odswiezania_sekund": 60
  }
}
```

Optional fields for API mode:
```json
{
  "tryb": "api",
  "saldo_api_usd": 5.00,
  "saldo_data_wpisania": "2026-05-24",
  "rate_limit_do": "14:30"
}
```

---

## Running tests

```bash
pytest tests/ -v
```

10 test cases covering: config loading, JSONL parsing, cost calculation, icon creation.

---

## Built by

**Daniel Bryjak** — part of the QA Automation Portfolio  
Main portfolio: [qa-automation-portfolio](https://github.com/dbryjak/qa-automation-portfolio)

*Built as a practical tool and learning exercise in Python desktop development.*
