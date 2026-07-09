"""
Master Quant Execution Agent — Chief Trading Officer.

This is the decision-making core of the bot. It:
1. Receives qualitative reports from the 3 research agents
2. Fetches live market data and calculates technical indicators
3. Detects the current market regime (Up/Down/Sideways)
4. Applies the appropriate strategy signals
5. Makes the final BUY/SELL/ABORT decision
6. Executes trades via Coinbase (or paper-trading simulation)

Decision Rules:
- IF Technicals say BUY but combined qualitative score < -0.5 → ABORT
- IF Technicals say BUY and combined qualitative score > 0.2 → EXECUTE
- IF Technicals say SELL → EXECUTE immediately (capital preservation)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from litellm import completion

from config import (
    NOUS_API_BASE,
    NOUS_API_KEY,
    HEAVY_MODEL,
    TRADING_PAIR,
    ORDER_SIZE_USD,
    PAPER_TRADING,
    TRAILING_STOP_PCT,
    HARD_STOP_PCT,
)
from database.db_manager import DatabaseManager
from utils.coinbase_client import CoinbaseClient
from utils.technical_indicators import (
    calculate_all_indicators,
    detect_regime,
    check_up_market_signal,
    check_down_market_signal,
)

logger = logging.getLogger(__name__)


# ─── Position State (in-memory, persisted to SQLite via trades table) ──────


class PositionManager:
    """Tracks open positions, entry prices, and trailing stops in memory.

    Survives restarts via database trade history reconstruction.
    """

    def __init__(self, db: DatabaseManager, coinbase: CoinbaseClient):
        self.db = db
        self.coinbase = coinbase
        self.open_position: Optional[dict] = None
        self.trailing_stop_price: Optional[float] = None
        self.highest_price_since_entry: Optional[float] = None

    def enter_position(
        self,
        pair: str,
        side: str,
        amount: float,
        price: float,
        regime: str,
        rationale: str,
    ):
        """Record a position entry."""
        self.open_position = {
            "pair": pair,
            "side": side,
            "amount": amount,
            "entry_price": price,
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "regime": regime,
        }
        self.highest_price_since_entry = price
        if side == "BUY":
            self.trailing_stop_price = price * (1 - TRAILING_STOP_PCT / 100)
        else:
            self.trailing_stop_price = price * (1 + HARD_STOP_PCT / 100)

        self.db.log_trade(
            pair=pair,
            side=side,
            amount=amount,
            price=price,
            status="SIMULATED" if self.coinbase.is_paper_trading() else "EXECUTED",
            paper_trading=self.coinbase.is_paper_trading(),
            regime=regime,
            entry_rationale=rationale,
        )
        logger.info(
            f"Position ENTERED: {side} {amount:.6f} {pair} @ ${price:.2f} "
            f"[{regime}]"
        )

    def exit_position(
        self,
        price: float,
        reason: str,
        rationale: str,
    ):
        """Close the current position."""
        if not self.open_position:
            return

        pos = self.open_position
        pnl = (price - pos["entry_price"]) * pos["amount"]
        if pos["side"] == "SELL":
            pnl = (pos["entry_price"] - price) * pos["amount"]

        pnl_pct = (price / pos["entry_price"] - 1) * 100
        if pos["side"] == "SELL":
            pnl_pct = (pos["entry_price"] / price - 1) * 100

        self.db.log_trade(
            pair=pos["pair"],
            side="SELL" if pos["side"] == "BUY" else "BUY",
            amount=pos["amount"],
            price=price,
            status="SIMULATED" if self.coinbase.is_paper_trading() else "EXECUTED",
            paper_trading=self.coinbase.is_paper_trading(),
            regime=pos["regime"],
            entry_rationale=pos.get("rationale", ""),
            exit_rationale=rationale,
        )

        logger.info(
            f"Position EXITED: {pos['side']} {pos['amount']:.6f} @ ${price:.2f} "
            f"| PnL: ${pnl:.2f} ({pnl_pct:.2f}%) | Reason: {reason}"
        )

        # Save PnL snapshot
        self.db.save_pnl(
            realized_pnl=pnl,
            unrealized_pnl=0,
            total_pnl=pnl,
            roi_percentage=pnl_pct,
        )

        self.open_position = None
        self.trailing_stop_price = None
        self.highest_price_since_entry = None

    def check_trailing_stop(self, current_price: float) -> Optional[str]:
        """Check if trailing stop should trigger. Returns exit reason or None."""
        if not self.open_position or self.open_position["side"] != "BUY":
            return None

        if current_price > self.highest_price_since_entry:
            self.highest_price_since_entry = current_price
            self.trailing_stop_price = current_price * (
                1 - TRAILING_STOP_PCT / 100
            )
            return None  # no stop hit, price moving up

        if self.trailing_stop_price and current_price <= self.trailing_stop_price:
            return f"TRAILING_STOP: Price ${current_price:.2f} fell to stop ${self.trailing_stop_price:.2f}"

        return None

    def check_hard_stop(self, current_price: float) -> Optional[str]:
        """Check if hard stop should trigger (for mean-reversion entries)."""
        if not self.open_position or self.open_position["side"] != "BUY":
            return None

        entry_price = self.open_position["entry_price"]
        stop_price = entry_price * (1 - HARD_STOP_PCT / 100)
        if current_price <= stop_price:
            return (
                f"HARD_STOP: Price ${current_price:.2f} fell below "
                f"${stop_price:.2f} ({HARD_STOP_PCT}% below entry)"
            )
        return None

    def is_in_position(self) -> bool:
        """Return whether there's an open position."""
        return self.open_position is not None

    def get_position_summary(self, current_price: float) -> dict:
        """Return a summary dict for the dashboard."""
        if not self.open_position:
            return {"in_position": False}

        pos = self.open_position
        unrealized_pnl = (current_price - pos["entry_price"]) * pos["amount"]
        if pos["side"] == "SELL":
            unrealized_pnl = (pos["entry_price"] - current_price) * pos["amount"]

        return {
            "in_position": True,
            "pair": pos["pair"],
            "side": pos["side"],
            "amount": pos["amount"],
            "entry_price": pos["entry_price"],
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": (
                (current_price / pos["entry_price"] - 1) * 100
            ),
            "trailing_stop": self.trailing_stop_price,
            "entry_time": pos["entry_time"],
        }


# ─── Master Quant Agent ────────────────────────────────────────────────────


class MasterQuantAgent:
    """Chief Trading Officer — receives all agent reports, runs technical
    analysis, applies decision logic, and executes trades."""

    def __init__(
        self,
        db: DatabaseManager,
        coinbase: CoinbaseClient,
        positions: PositionManager,
    ):
        self.db = db
        self.coinbase = coinbase
        self.positions = positions
        self.name = "Master Quant Execution Agent"
        self.current_regime = "UNKNOWN"

    async def execute_cycle(
        self,
        sentiment_report: dict,
        macro_report: dict,
        industry_report: dict,
    ) -> dict:
        """Run one full agent cycle.

        1. Fetch market data and calculate indicators
        2. Detect market regime
        3. Check for exit signals if in position
        4. Check for entry signals if flat
        5. Apply qualitative filter for BUY signals
        6. Execute or abort
        7. Save portfolio snapshot

        Returns:
            dict with cycle summary
        """
        logger.info("=" * 60)
        logger.info(f"{self.name}: Starting analysis cycle...")

        cycle_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "regime": "UNKNOWN",
            "action": "NONE",
            "rationale": "",
            "trade_executed": False,
            "qualitative_scores": {},
            "error": None,
        }

        try:
            # ── Step 1: Fetch market data ──
            df = self.coinbase.get_candles(
                product_id=TRADING_PAIR,
                granularity="FIVE_MINUTE",
                limit=250,
            )

            if df.empty:
                error_msg = "No market data received"
                cycle_result["error"] = error_msg
                logger.error(error_msg)
                self.db.log_agent_decision(
                    agent_name=self.name,
                    decision="ERROR",
                    rationale=error_msg,
                )
                return cycle_result

            # ── Step 2: Calculate indicators ──
            df = calculate_all_indicators(df, is_up_market=True)
            # Also add Bollinger Bands regardless (needed for down market)
            from utils.technical_indicators import add_bollinger_bands
            df = add_bollinger_bands(df)

            # ── Step 3: Detect regime ──
            regime, regime_rationale = detect_regime(df)
            self.current_regime = regime
            cycle_result["regime"] = regime
            logger.info(f"Market Regime: {regime}")
            logger.info(f"Regime Rationale: {regime_rationale}")

            # Log the regime decision
            self.db.log_agent_decision(
                agent_name=self.name,
                decision=f"REGIME: {regime}",
                rationale=regime_rationale,
            )

            # ── Step 4: Check exit signals if in position ──
            current_price = float(df.iloc[-1]["close"])

            if self.positions.is_in_position():
                exit_action = self._check_exit_signals(
                    current_price, df, regime
                )
                if exit_action:
                    cycle_result["action"] = exit_action["action"]
                    cycle_result["rationale"] = exit_action["rationale"]
                    cycle_result["trade_executed"] = True

                    self.positions.exit_position(
                        price=current_price,
                        reason=exit_action["action"],
                        rationale=exit_action["rationale"],
                    )

                    self.db.update_bot_status(
                        status="RUNNING",
                        current_regime=regime,
                        message=exit_action["rationale"],
                    )
                    return cycle_result

                # No exit — we're holding
                cycle_result["action"] = "HOLD_POSITION"
                cycle_result["rationale"] = (
                    f"Holding existing position. "
                    f"Current price: ${current_price:.2f}"
                )
                logger.info(cycle_result["rationale"])

            # ── Step 5: Check entry signals (flat) ──
            else:
                action = self._evaluate_entry(
                    df, regime, sentiment_report, macro_report, industry_report
                )
                cycle_result["action"] = action["action"]
                cycle_result["rationale"] = action["rationale"]
                cycle_result["qualitative_scores"] = action.get("scores", {})

                if action["action"] in ("BUY", "BUY_DIP"):
                    order = self.coinbase.place_market_buy(
                        product_id=TRADING_PAIR,
                        amount_usd=ORDER_SIZE_USD,
                    )

                    if order.get("success") or self.coinbase.is_paper_trading():
                        executed_price = float(
                            order.get("price", current_price)
                        )
                        btc_amount = ORDER_SIZE_USD / executed_price

                        self.positions.enter_position(
                            pair=TRADING_PAIR,
                            side="BUY",
                            amount=btc_amount,
                            price=executed_price,
                            regime=regime,
                            rationale=action["rationale"],
                        )
                        cycle_result["trade_executed"] = True
                        logger.info(
                            f"BUY EXECUTED: {btc_amount:.6f} @ ${executed_price:.2f}"
                        )
                    else:
                        logger.error(f"Order failed: {order}")
                        cycle_result["error"] = f"Order failed: {order.get('error')}"

                elif action["action"] == "ABORT":
                    self.db.log_trade(
                        pair=TRADING_PAIR,
                        side="ABORT",
                        amount=0,
                        price=current_price,
                        status="ABORTED",
                        paper_trading=self.coinbase.is_paper_trading(),
                        regime=regime,
                        entry_rationale=action["rationale"],
                    )
                    logger.info(f"TRADE ABORTED: {action['rationale']}")

            # ── Step 6: Save portfolio snapshot ──
            try:
                portfolio = self.coinbase.get_portfolio_value()
                self.db.save_portfolio_snapshot(
                    total_value_usd=portfolio.get("total_value", 10000),
                    cash_usd=portfolio.get("cash", 0),
                    crypto_value_usd=portfolio.get("crypto_value", 0),
                    btc_balance=portfolio.get("btc_balance", 0),
                    usdc_balance=portfolio.get("usdc_balance", 0),
                )
            except Exception as e:
                logger.warning(f"Portfolio snapshot failed: {e}")

            # ── Step 7: Update bot status ──
            self.db.update_bot_status(
                status="RUNNING",
                current_regime=regime,
                message=cycle_result.get("rationale", "Cycle complete."),
            )

            # Log the master decision
            self.db.log_agent_decision(
                agent_name=self.name,
                decision=cycle_result["action"],
                rationale=cycle_result.get("rationale", ""),
                raw_output=json.dumps(cycle_result),
            )

        except Exception as e:
            logger.error(f"{self.name}: Cycle failed: {e}", exc_info=True)
            cycle_result["error"] = str(e)
            self.db.update_bot_status(
                status="ERROR",
                message=f"Cycle failed: {e}",
            )

        return cycle_result

    def _check_exit_signals(
        self,
        current_price: float,
        df: pd.DataFrame,
        regime: str,
    ) -> Optional[dict]:
        """Check all exit conditions for an open position."""

        # 1. Check trailing stop (for momentum trades)
        trailing_reason = self.positions.check_trailing_stop(current_price)
        if trailing_reason:
            return {
                "action": "EXIT_LONG",
                "rationale": f"{trailing_reason} | Regime: {regime}",
            }

        # 2. Check hard stop (for mean-reversion trades)
        hard_stop_reason = self.positions.check_hard_stop(current_price)
        if hard_stop_reason:
            return {
                "action": "EXIT_LONG",
                "rationale": f"{hard_stop_reason} | Regime: {regime}",
            }

        # 3. Check technical exit signals based on regime
        if regime == "UP_TREND":
            signal, msg = check_up_market_signal(df)
            if signal and "EXIT" in msg:
                return {"action": "EXIT_LONG", "rationale": msg}

        elif regime == "DOWN_TREND":
            signal, msg = check_down_market_signal(df)
            if signal and "EXIT" in msg:
                return {"action": "EXIT_LONG", "rationale": msg}

        return None

    def _evaluate_entry(
        self,
        df: pd.DataFrame,
        regime: str,
        sentiment_report: dict,
        macro_report: dict,
        industry_report: dict,
    ) -> dict:
        """Evaluate entry signals with qualitative filtering."""

        # Extract qualitative scores
        sentiment_score = sentiment_report.get("score", 0.0)
        macro_score = macro_report.get("score", 0.0)
        industry_score = industry_report.get("score", 0.0)

        # Combined qualitative score (weighted average)
        # Sentiment: 25%, Macro: 40%, Industry: 35%
        combined_score = (
            sentiment_score * 0.25 + macro_score * 0.40 + industry_score * 0.35
        )

        scores = {
            "sentiment": sentiment_score,
            "macro": macro_score,
            "industry": industry_score,
            "combined": combined_score,
        }

        logger.info(
            f"Qualitative Scores — Sentiment: {sentiment_score:.2f}, "
            f"Macro: {macro_score:.2f}, Industry: {industry_score:.2f}, "
            f"Combined: {combined_score:.2f}"
        )

        # Don't enter in sideways market
        if regime == "SIDEWAYS":
            return {
                "action": "HOLD",
                "rationale": (
                    f"Market is sideways (ADX < 20). "
                    f"Holding cash. Combined qualitative: {combined_score:.2f}"
                ),
                "scores": scores,
            }

        if regime == "TRANSITIONAL":
            return {
                "action": "HOLD",
                "rationale": (
                    f"Market is in transitional zone. Waiting for clearer signal. "
                    f"Combined qualitative: {combined_score:.2f}"
                ),
                "scores": scores,
            }

        # ── Up Market: Check momentum entry ──
        if regime == "UP_TREND":
            signal, msg = check_up_market_signal(df)

            if signal and "BUY" in msg:
                # Apply qualitative filter
                if combined_score < -0.5:
                    return {
                        "action": "ABORT",
                        "rationale": (
                            f"Technical BUY signal detected, but ABORTING: "
                            f"Combined qualitative score {combined_score:.2f} < -0.5. "
                            f"Macro: {macro_score:.2f}, Sentiment: {sentiment_score:.2f}. "
                            f"Technicals say go, but macro/sentiment veto."
                        ),
                        "scores": scores,
                    }
                elif combined_score > 0.2:
                    return {
                        "action": "BUY",
                        "rationale": (
                            f"Technical BUY signal CONFIRMED: {msg} | "
                            f"Combined qualitative: {combined_score:.2f} > 0.2. "
                            f"All systems go."
                        ),
                        "scores": scores,
                    }
                else:
                    return {
                        "action": "HOLD",
                        "rationale": (
                            f"Technical BUY signal but qualitative neutral "
                            f"({combined_score:.2f}). Waiting for alignment."
                        ),
                        "scores": scores,
                    }

            return {
                "action": "HOLD",
                "rationale": f"No entry signal. {msg}",
                "scores": scores,
            }

        # ── Down Market: Check mean-reversion entry ──
        if regime == "DOWN_TREND":
            signal, msg = check_down_market_signal(df)

            if signal and "BUY" in msg:
                # In a down market, be even more conservative with qualitative filter
                if combined_score < -0.3:
                    return {
                        "action": "ABORT",
                        "rationale": (
                            f"Mean-reversion BUY signal detected, but ABORTING: "
                            f"Combined qualitative score {combined_score:.2f} < -0.3. "
                            f"Too risky to catch falling knife in bearish macro."
                        ),
                        "scores": scores,
                    }
                elif combined_score > 0.1:
                    return {
                        "action": "BUY_DIP",
                        "rationale": (
                            f"Mean-reversion BUY CONFIRMED: {msg} | "
                            f"Qualitative support: {combined_score:.2f}. "
                            f"Scalping bounce with tight stop."
                        ),
                        "scores": scores,
                    }
                else:
                    return {
                        "action": "HOLD",
                        "rationale": (
                            f"Dip detected but {msg} | "
                            f"Qualitative score {combined_score:.2f} too low "
                            f"for safe mean-reversion entry."
                        ),
                        "scores": scores,
                    }

            return {
                "action": "HOLD",
                "rationale": f"No mean-reversion signal. {msg}",
                "scores": scores,
            }

        return {
            "action": "HOLD",
            "rationale": f"Unknown regime: {regime}. No action.",
            "scores": scores,
        }