"""
Main entry point for the multi-agent crypto trading system.

Launches two parallel processes:
1. Bot Engine — Runs the agent cycle on a configurable loop interval
2. Dash Dashboard — Real-time web UI at http://localhost:8050

Usage:
    python main.py                  # Start bot + dashboard
    python main.py --dashboard-only # Start dashboard without bot engine
    python main.py --bot-only       # Start bot engine without dashboard
"""

import argparse
import logging
import logging.handlers
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Optional

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    LOOP_INTERVAL_MINUTES,
    NOUS_API_KEY,
    TAVILY_API_KEY,
    DATABASE_PATH,
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    DASHBOARD_UPDATE_INTERVAL_MS,
    validate_config,
    PAPER_TRADING,
    TRADING_PAIR,
    ORDER_SIZE_USD,
    FAST_MODEL,
    HEAVY_MODEL,
)
from database.db_manager import DatabaseManager
from utils.coinbase_client import CoinbaseClient
from agents.sentiment import SocialSentimentAgent
from agents.macro import MacroAgent
from agents.crypto_industry import CryptoIndustryAgent
from agents.master_quant import MasterQuantAgent, PositionManager

# ─── Logging Setup ──────────────────────────────────────────────────────────

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Log format with timestamps and level
LOG_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-5s | %(name)-25s | %(message)s"
)
LOG_DATE_FORMAT = "%H:%M:%S"

# File handler (rotating, keeps last 5 files of 5MB each)
file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOG_DIR, "trading_bot.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

# Stream handler (stdout)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s | %(message)s",
        datefmt=LOG_DATE_FORMAT,
    )
)

# Root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

# Quieter third-party logs
for noisy in ["litellm", "urllib3", "httpx", "httpcore"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger("main")


# ─── Bot Engine ─────────────────────────────────────────────────────────────


class BotEngine:
    """Runs the agent cycle loop in a background thread."""

    def __init__(self):
        missing = validate_config()
        if missing:
            logger.warning(f"Missing configuration: {', '.join(missing)}")
            if "NOUS_API_KEY" in missing:
                logger.error("NOUS_API_KEY is required. Bot cannot start.")
                raise SystemExit(1)

        self.db = DatabaseManager(DATABASE_PATH)
        self.db.initialize()

        self.coinbase = CoinbaseClient()
        self.positions = PositionManager(self.db, self.coinbase)
        self.master = MasterQuantAgent(self.db, self.coinbase, self.positions)

        # Research agents (with Tavily tool if key is available)
        self.tavily_tool = None
        if TAVILY_API_KEY:
            try:
                from tavily import TavilyClient
                self.tavily_tool = TavilyClient(api_key=TAVILY_API_KEY)
                logger.info("Tavily search client initialized")
            except ImportError:
                logger.warning(
                    "tavily-python not installed. Agents will use baseline analysis."
                )
            except Exception as e:
                logger.warning(f"Tavily init failed: {e}")
        else:
            logger.info(
                "No TAVILY_API_KEY set. Agents will provide baseline analysis "
                "without live web search."
            )

        self.sentiment_agent = SocialSentimentAgent(tavily_tool=self.tavily_tool)
        self.macro_agent = MacroAgent(tavily_tool=self.tavily_tool)
        self.industry_agent = CryptoIndustryAgent(tavily_tool=self.tavily_tool)

        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None

        logger.info("BotEngine initialized")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def start(self):
        """Start the bot loop in a background thread."""
        if self._running:
            logger.warning("Bot is already running")
            return

        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Bot engine started")

        self.db.update_bot_status(
            status="RUNNING",
            message=f"Bot started at {datetime.now(timezone.utc).isoformat()}",
        )

    def pause(self):
        """Pause the bot after the current cycle completes."""
        self._paused = True
        logger.info("Bot paused (will pause after current cycle)")
        self.db.update_bot_status(
            status="PAUSED",
            message="Bot paused by user",
        )

    def resume(self):
        """Resume a paused bot."""
        self._paused = False
        logger.info("Bot resumed")
        self.db.update_bot_status(
            status="RUNNING",
            message="Bot resumed by user",
        )

    def stop(self):
        """Stop the bot gracefully."""
        self._running = False
        self._paused = False
        logger.info("Bot stopping...")
        self.db.update_bot_status(
            status="STOPPED",
            message="Bot stopped by user",
        )
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("Bot stopped")

    def _loop(self):
        """Main bot agent loop."""
        logger.info("=" * 60)
        logger.info("🤖 MULTI-AGENT TRADING BOT INITIALIZED")
        logger.info(f"   Trading Pair: {TRADING_PAIR}")
        logger.info(f"   Order Size: ${ORDER_SIZE_USD:.2f}")
        logger.info(f"   Paper Trading: {PAPER_TRADING}")
        logger.info(f"   Loop Interval: {LOOP_INTERVAL_MINUTES} minutes")
        logger.info(
            f"   Fast Model: {FAST_MODEL}"
        )
        logger.info(
            f"   Heavy Model: {HEAVY_MODEL}"
        )
        logger.info("=" * 60)

        cycle_count = 0

        while self._running:
            if self._paused:
                time.sleep(5)
                continue

            cycle_count += 1
            logger.info(f"\n{'─' * 50}")
            logger.info(f"Cycle #{cycle_count} — {datetime.now(timezone.utc).isoformat()}")
            logger.info(f"{'─' * 50}")

            try:
                # ── Run all 3 research agents in parallel ──
                logger.info("Phase 1/3: Running research agents...")

                sentiment_result = self.sentiment_agent.analyze(
                    target_asset="Bitcoin"
                )
                self.db.log_agent_decision(
                    agent_name=sentiment_result["agent_name"],
                    decision=sentiment_result["decision"],
                    score=sentiment_result.get("score"),
                    rationale=sentiment_result.get("rationale"),
                    raw_output=sentiment_result.get("raw_output"),
                )
                logger.info(
                    f"  ✓ {sentiment_result['agent_name']}: "
                    f"{sentiment_result['decision']} "
                    f"[{sentiment_result.get('score', 0.0):+.2f}]"
                )

                macro_result = self.macro_agent.analyze()
                self.db.log_agent_decision(
                    agent_name=macro_result["agent_name"],
                    decision=macro_result["decision"],
                    score=macro_result.get("score"),
                    rationale=macro_result.get("rationale"),
                    raw_output=macro_result.get("raw_output"),
                )
                logger.info(
                    f"  ✓ {macro_result['agent_name']}: "
                    f"{macro_result['decision']} "
                    f"[{macro_result.get('score', 0.0):+.2f}]"
                )

                industry_result = self.industry_agent.analyze()
                self.db.log_agent_decision(
                    agent_name=industry_result["agent_name"],
                    decision=industry_result["decision"],
                    score=industry_result.get("score"),
                    rationale=industry_result.get("rationale"),
                    raw_output=industry_result.get("raw_output"),
                )
                logger.info(
                    f"  ✓ {industry_result['agent_name']}: "
                    f"{industry_result['decision']} "
                    f"[{industry_result.get('score', 0.0):+.2f}]"
                )

                # ── Phase 2: Master Quant executes ──
                logger.info("Phase 2/3: Master Quant evaluating...")
                cycle_result = self.master.execute_cycle(
                    sentiment_report=sentiment_result,
                    macro_report=macro_result,
                    industry_report=industry_result,
                )

                logger.info(f"  → Action: {cycle_result['action']}")
                logger.info(f"  → Regime: {cycle_result['regime']}")
                if cycle_result.get("rationale"):
                    logger.info(f"  → Rationale: {cycle_result['rationale']}")
                if cycle_result.get("trade_executed"):
                    logger.info(f"  ⚡ TRADE EXECUTED ({TRADING_PAIR})")

                # ── Phase 3: Logging complete ──
                logger.info(f"Phase 3/3: Cycle #{cycle_count} complete.")
                logger.info(
                    f"Next cycle in {LOOP_INTERVAL_MINUTES} minutes..."
                )

            except Exception as e:
                logger.error(f"Cycle #{cycle_count} failed: {e}", exc_info=True)
                self.db.update_bot_status(
                    status="ERROR",
                    message=f"Cycle #{cycle_count} failed: {str(e)}",
                )

            # Wait for next interval (check every 5s for pause/stop)
            for _ in range(LOOP_INTERVAL_MINUTES * 60 // 5):
                if not self._running or self._paused:
                    break
                time.sleep(5)


def run_bot_engine(
    engine: BotEngine,
    dashboard_mode: bool = False,
):
    """Run the bot engine, optionally integrating with a dashboard."""

    # Start the bot
    engine.start()

    if dashboard_mode:
        # In dashboard mode, the main thread runs the Dash server.
        # The bot runs in the background thread.
        # The dashboard callbacks can reference the engine's DB.
        import dashboard.callbacks as dash_cb
        dash_cb.set_db(engine.db)
        dash_cb.set_bot_engine(engine)
        dash_cb.set_bot_thread(engine._thread)

    else:
        # Standalone mode — main thread just waits
        try:
            while engine.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            engine.stop()


def run_dashboard_only():
    """Run the dashboard without the bot engine."""
    logger.info("Starting dashboard-only mode")
    db = DatabaseManager(DATABASE_PATH)
    db.initialize()

    import dashboard.callbacks as dash_cb
    dash_cb.set_db(db)

    from dashboard.app import create_dash_app
    app = create_dash_app()
    logger.info(
        f"Dashboard starting at http://{DASHBOARD_HOST}:{DASHBOARD_PORT}"
    )
    app.run(
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        debug=False,
        use_reloader=False,
    )


def run_bot_only():
    """Run the bot engine without the dashboard."""
    engine = BotEngine()
    run_bot_engine(engine, dashboard_mode=False)


def run_full():
    """Run both the bot engine and the dashboard."""
    engine = BotEngine()
    run_bot_engine(engine, dashboard_mode=True)

    from dashboard.app import create_dash_app
    app = create_dash_app()

    logger.info(
        f"Full system starting — "
        f"Dashboard: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}"
    )
    logger.info(
        f"Bot engine running in background "
        f"(cycle every {LOOP_INTERVAL_MINUTES} min)"
    )

    # Run the Dash app on the main thread (bot is on daemon thread)
    try:
        app.run(
            host=DASHBOARD_HOST,
            port=DASHBOARD_PORT,
            debug=False,
            use_reloader=False,
        )
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        engine.stop()


# ─── CLI Entry Point ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Agent Crypto Trading Bot with Real-Time Dashboard",
    )
    parser.add_argument(
        "--dashboard-only",
        action="store_true",
        help="Run only the dashboard (no bot engine)",
    )
    parser.add_argument(
        "--bot-only",
        action="store_true",
        help="Run only the bot engine (no dashboard)",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Check configuration and exit",
    )

    args = parser.parse_args()

    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))

    if args.check_config:
        missing = validate_config()
        if missing:
            logger.warning("Configuration issues found:")
            for item in missing:
                logger.warning(f"  ✗ {item}")
            sys.exit(1)
        else:
            logger.info("Configuration looks good!")
            sys.exit(0)

    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║   QUANTUM TRADING TERMINAL                   ║")
    logger.info("║   Multi-Agent Crypto Trading System          ║")
    logger.info("╚══════════════════════════════════════════════╝")
    logger.info(f"Nous API: {'✓' if NOUS_API_KEY else '✗'} configured")
    logger.info(f"Tavily:   {'✓' if TAVILY_API_KEY else '✗'} configured")
    logger.info(f"Paper:    {'PAPER MODE' if PAPER_TRADING else 'LIVE MODE ⚠'}")

    if args.dashboard_only:
        run_dashboard_only()
    elif args.bot_only:
        run_bot_only()
    else:
        run_full()


if __name__ == "__main__":
    main()