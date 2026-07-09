# Multi-Agent Crypto Trading System — Architecture

## Overview

This system implements an **institutional-grade multi-agent trading desk**
that combines qualitative research (LLM-powered agents) with quantitative
technical analysis to make autonomous trading decisions on Coinbase.

### The "Hedge Fund Quant Desk" Pattern

```
Social Sentiment Agent  ─────┐
Macro & Geopolitical Agent ──┤──→ Master Quant Agent → Coinbase
Crypto Industry Agent    ─────┘        │
                                  Technical Indicators
                                  (ADX, EMA, RSI, Bollinger)
```

Research agents generate qualitative scores. The Master Quant fuses
these with live technical data and applies **veto-based decision logic**:
technicals suggest the trade, but qualitative agents can kill it.

---

## Agent Architecture

### 1. Social Sentiment Agent
- **Role:** Retail Sentiment Analyst
- **Model:** Fast (Hermes 2 Mixtral via Nous API)
- **Tool:** Tavily web search (X, Reddit, crypto news)
- **Output:** Sentiment score (-1.0 to 1.0) + rationale
- **Importance:** 25% weight in final qualitative score

### 2. Macro & Geopolitical Agent
- **Role:** Global Macro Economist
- **Model:** Fast (Hermes 2 Mixtral via Nous API)
- **Tool:** Tavily web search (Fed, inflation, geopolitics, stocks)
- **Output:** Macro impact score (-1.0 to 1.0) + rationale
- **Importance:** 40% weight in final qualitative score (highest)

### 3. Crypto Industry & Platform Agent
- **Role:** Crypto Tech & Platform Lead
- **Model:** Fast (Hermes 2 Mixtral via Nous API)
- **Tool:** Tavily web search (ETFs, upgrades, hacks, Coinbase CDP)
- **Output:** Structural impact score (-1.0 to 1.0) + API updates
- **Importance:** 35% weight in final qualitative score

### 4. Master Quant Execution Agent
- **Role:** Chief Trading Officer
- **Model:** Heavy (Hermes 2 Theta 70B via Nous API)
- **Scope:** Receives all 3 reports, fetches live data, calculates
  technical indicators, applies decision logic, executes trades
- **Decision Rules:**
  - Technicals BUY + qualitative >= 0.2 → **EXECUTE**
  - Technicals BUY + qualitative < -0.5 → **ABORT** (veto)
  - Technicals SELL → **EXECUTE immediately** (capital preservation)
  - Down market mean-reversion: stricter threshold (qualitative >= 0.1,
    abort if < -0.3)

---

## Technical Strategy

### Regime Detection
| ADX | Price vs EMA 200 | Regime |
|-----|-----------------|--------|
| > 25 | Above | **UP_TREND** — Momentum strategy |
| > 25 | Below | **DOWN_TREND** — Mean-reversion strategy |
| 20-25 | Any | **TRANSITIONAL** — Hold, no entries |
| < 20 | Any | **SIDEWAYS** — Hold cash |

### Up Market (Momentum Trend-Following)
- **Entry:** 9 EMA crosses above 21 EMA AND RSI between 50-70
- **Exit:** 9 EMA crosses below 21 EMA OR RSI > 75
- **Risk:** 3% trailing stop from highest price since entry

### Down Market (Mean-Reversion & Capital Preservation)
- **Entry:** Price touches lower Bollinger Band AND RSI < 30
- **Exit:** Price returns to middle Bollinger Band OR RSI > 45
- **Risk:** Hard 2% stop-loss below entry price

---

## Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ Agent Cycle  │────▶│ SQLite DB   │◀────│ Dash Dashboard│
│ (bg thread)  │     │              │     │ (web UI)      │
│              │     │ agent_decisions│     │              │
│  5min loop   │     │ trades        │     │ 5s poll      │
│              │     │ portfolio_snap│     │ real-time     │
│              │     │ pnl_history   │     │ charts/tables │
│              │     │ bot_status    │     │              │
└─────────────┘     └──────────────┘     └──────────────┘
```

---

## File Structure

```
crypto_trading_bot/
├── main.py                    # Entry point — launches bot + dashboard
├── config.py                  # Central configuration
├── .env.example               # Template for environment variables
├── requirements.txt           # Python dependencies
├── AGENTS.md                  # This file
├── trading_bot.db             # SQLite database (auto-created)
├── logs/
│   └── trading_bot.log        # Rotating log file
├── database/
│   └── db_manager.py          # SQLite schema + CRUD
├── agents/
│   ├── __init__.py
│   ├── sentiment.py           # Social Sentiment Agent
│   ├── macro.py               # Macro & Geopolitical Agent
│   ├── crypto_industry.py     # Crypto Industry & Platform Agent
│   └── master_quant.py        # Master Quant Execution Agent + PositionManager
├── utils/
│   ├── __init__.py
│   ├── technical_indicators.py # ADX, EMA, RSI, Bollinger Bands
│   └── coinbase_client.py     # Coinbase Advanced Trade API wrapper
└── dashboard/
    ├── __init__.py
    ├── app.py                 # Dash app setup
    ├── layouts.py              # UI layout definitions (5 tabs)
    └── callbacks.py           # Real-time update callbacks
```

---

## Deployment Notes

### Prerequisites
- Python 3.11+
- Nous Research API key (`NOUS_API_KEY`)
- Tavily API key (`TAVILY_API_KEY`) — free tier available

### First Run
```bash
cd crypto_trading_bot
cp .env.example .env
# Edit .env with your API keys
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Modes
- `python main.py` — Full system (bot + dashboard)
- `python main.py --bot-only` — Headless bot engine
- `python main.py --dashboard-only` — Dashboard only (view historical data)
- `python main.py --check-config` — Validate configuration

### Access Dashboard
Open http://localhost:8050 in your browser.

### Safety
- `PAPER_TRADING=True` by default — no real money moves
- Flip to `False` only after validating signals for 3-5 days
- Start with small amounts (e.g., $50)

---

## LLM Routing

All agents use **Nous Research / Hermes API** via `litellm` with OpenAI-compatible
format:

| Agent | Model | Purpose |
|-------|-------|---------|
| Social Sentiment | Fast (Mixtral 8x7B) | Cheap, fast research |
| Macro | Fast (Mixtral 8x7B) | Cheap, fast research |
| Crypto Industry | Fast (Mixtral 8x7B) | Cheap, fast research |
| Master Quant | Heavy (Theta 70B) | Critical decision-making |

Research agents use lower-cost models because they do bulk web search
processing. The Master Quant uses the heavier model for nuanced
decision-making that considers all qualitative reports + quantitative data.