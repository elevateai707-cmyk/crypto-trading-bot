"""
Central configuration module for the multi-agent crypto trading bot.

All environment variables, trading parameters, and model selections
are defined here. Loads .env file automatically via python-dotenv.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── LLM / API Configuration ────────────────────────────────────────────────
# Nous Research / Hermes API (OpenAI-compatible, routed via litellm)
NOUS_API_KEY = os.getenv("NOUS_API_KEY", "")
NOUS_API_BASE = os.getenv(
    "NOUS_API_BASE", "https://inference-api.nousresearch.com/v1"
)

# Fast model for research agents (sentiment, macro, crypto industry)
FAST_MODEL = os.getenv("FAST_MODEL", "deepseek/deepseek-v4-flash")

# Heavy model for the Master Quant Agent (decision-making & execution)
HEAVY_MODEL = os.getenv("HEAVY_MODEL", "Hermes-4-405B")

# Tavily API key for AI-optimized web search (used by research agents)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ─── Coinbase API Configuration ─────────────────────────────────────────────
COINBASE_API_KEY = os.getenv("COINBASE_API_KEY", "")
COINBASE_API_SECRET = os.getenv("COINBASE_API_SECRET", "")

# ─── Trading Parameters ─────────────────────────────────────────────────────
# Default trading pair (Coinbase product ID format)
TRADING_PAIR = os.getenv("TRADING_PAIR", "BTC-USD")

# Base order size in USD — the bot will trade this amount per signal
ORDER_SIZE_USD = float(os.getenv("ORDER_SIZE_USD", "50.0"))

# Bot loop interval in minutes — how often the agent cycle runs
LOOP_INTERVAL_MINUTES = int(os.getenv("LOOP_INTERVAL_MINUTES", "5"))

# Maximum risk per trade as % of portfolio (used for position sizing)
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "2.0"))

# Trailing stop-loss percentage for momentum trades (up market)
TRAILING_STOP_PCT = float(os.getenv("TRAILING_STOP_PCT", "3.0"))

# Hard stop-loss percentage for mean-reversion trades (down market)
HARD_STOP_PCT = float(os.getenv("HARD_STOP_PCT", "2.0"))

# ─── Safety Flags ────────────────────────────────────────────────────────────
# When True, all trades are simulated — no real API calls to Coinbase
PAPER_TRADING = os.getenv("PAPER_TRADING", "True").lower() in (
    "true", "1", "yes"
)

# ─── Database ───────────────────────────────────────────────────────────────
# Path to the SQLite database file
DATABASE_PATH = os.getenv(
    "DATABASE_PATH", os.path.join(os.path.dirname(__file__), "trading_bot.db")
)

# ─── Dashboard ───────────────────────────────────────────────────────────────
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8050"))
DASHBOARD_THEME = os.getenv("DASHBOARD_THEME", "darkly")
DASHBOARD_UPDATE_INTERVAL_MS = int(
    os.getenv("DASHBOARD_UPDATE_INTERVAL_MS", "5000")
)

# ─── Validation ─────────────────────────────────────────────────────────────
def validate_config() -> list[str]:
    """Return a list of missing critical configuration items."""
    missing = []
    if not NOUS_API_KEY:
        missing.append("NOUS_API_KEY")
    if not TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")
    if not PAPER_TRADING:  # only warn on keys if we're going live
        if not COINBASE_API_KEY:
            missing.append("COINBASE_API_KEY (live trading)")
        if not COINBASE_API_SECRET:
            missing.append("COINBASE_API_SECRET (live trading)")
    return missing