"""
SQLite database manager for the multi-agent crypto trading bot.

Provides:
- Schema initialization (agent_decisions, trades, portfolio_snapshots,
  pnl_history, bot_status)
- CRUD operations for all tables
- Helper query methods for the dashboard (latest state, aggregate stats)

All timestamps are stored as ISO 8601 UTC strings.
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional


class DatabaseManager:
    """Manages all SQLite operations for the trading bot."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get a connection with row factory for dict-like access."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # better concurrent access
        return conn

    def initialize(self):
        """Create all tables if they don't exist."""
        if self._initialized:
            return
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agent_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    score REAL,
                    rationale TEXT,
                    raw_output TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_agent_decisions_timestamp
                    ON agent_decisions(timestamp DESC);

                CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent
                    ON agent_decisions(agent_name);

                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'SIMULATED'
                        CHECK(status IN ('EXECUTED', 'SIMULATED', 'ABORTED')),
                    paper_trading INTEGER NOT NULL DEFAULT 1,
                    regime TEXT,
                    entry_rationale TEXT,
                    exit_rationale TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_trades_timestamp
                    ON trades(timestamp DESC);

                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_value_usd REAL NOT NULL,
                    cash_usd REAL NOT NULL,
                    crypto_value_usd REAL NOT NULL,
                    btc_balance REAL DEFAULT 0,
                    usdc_balance REAL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp
                    ON portfolio_snapshots(timestamp DESC);

                CREATE TABLE IF NOT EXISTS pnl_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    realized_pnl REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    roi_percentage REAL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_pnl_timestamp
                    ON pnl_history(timestamp DESC);

                CREATE TABLE IF NOT EXISTS bot_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL
                        CHECK(status IN ('RUNNING','PAUSED','STOPPED','ERROR')),
                    current_regime TEXT DEFAULT 'UNKNOWN',
                    last_loop_time TEXT,
                    message TEXT
                );
            """)
            conn.commit()
            self._initialized = True
        finally:
            conn.close()

    # ─── Agent Decision Logging ─────────────────────────────────────────────

    def log_agent_decision(
        self,
        agent_name: str,
        decision: str,
        score: Optional[float] = None,
        rationale: Optional[str] = None,
        raw_output: Optional[str] = None,
    ) -> int:
        """Insert a new agent decision and return its ID."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO agent_decisions
                   (timestamp, agent_name, decision, score, rationale, raw_output)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    agent_name,
                    decision,
                    score,
                    rationale,
                    raw_output,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_recent_decisions(self, limit: int = 50) -> list[dict]:
        """Return the most recent agent decisions for the dashboard."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """SELECT * FROM agent_decisions
                   ORDER BY timestamp DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ─── Trade Logging ──────────────────────────────────────────────────────

    def log_trade(
        self,
        pair: str,
        side: str,
        amount: float,
        price: float,
        status: str = "SIMULATED",
        paper_trading: bool = True,
        regime: Optional[str] = None,
        entry_rationale: Optional[str] = None,
        exit_rationale: Optional[str] = None,
    ) -> int:
        """Record a trade execution or simulation."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO trades
                   (timestamp, pair, side, amount, price, status,
                    paper_trading, regime, entry_rationale, exit_rationale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    pair,
                    side,
                    amount,
                    price,
                    status,
                    1 if paper_trading else 0,
                    regime,
                    entry_rationale,
                    exit_rationale,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_trades(self, limit: int = 100) -> list[dict]:
        """Return recent trades."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_trade_stats(self) -> dict:
        """Return aggregate trade statistics."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                """SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN side='BUY' THEN 1 ELSE 0 END) as buys,
                    SUM(CASE WHEN side='SELL' THEN 1 ELSE 0 END) as sells,
                    SUM(CASE WHEN status='EXECUTED' THEN 1 ELSE 0 END)
                        as executed,
                    SUM(CASE WHEN status='ABORTED' THEN 1 ELSE 0 END) as aborted
                   FROM trades"""
            ).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    # ─── Portfolio Snapshots ────────────────────────────────────────────────

    def save_portfolio_snapshot(
        self,
        total_value_usd: float,
        cash_usd: float,
        crypto_value_usd: float,
        btc_balance: float = 0,
        usdc_balance: float = 0,
    ):
        """Record a portfolio state at a point in time."""
        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT INTO portfolio_snapshots
                   (timestamp, total_value_usd, cash_usd, crypto_value_usd,
                    btc_balance, usdc_balance)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    total_value_usd,
                    cash_usd,
                    crypto_value_usd,
                    btc_balance,
                    usdc_balance,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_portfolio_history(self, limit: int = 500) -> list[dict]:
        """Return portfolio snapshots for charting."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM portfolio_snapshots ORDER BY timestamp ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_latest_portfolio(self) -> Optional[dict]:
        """Return the most recent portfolio snapshot."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ─── PnL History ────────────────────────────────────────────────────────

    def save_pnl(
        self,
        realized_pnl: float = 0,
        unrealized_pnl: float = 0,
        total_pnl: float = 0,
        roi_percentage: float = 0,
    ):
        """Record a PnL snapshot."""
        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT INTO pnl_history
                   (timestamp, realized_pnl, unrealized_pnl, total_pnl,
                    roi_percentage)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    realized_pnl,
                    unrealized_pnl,
                    total_pnl,
                    roi_percentage,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_pnl_history(self, limit: int = 500) -> list[dict]:
        """Return PnL history for charting."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM pnl_history ORDER BY timestamp ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_latest_pnl(self) -> Optional[dict]:
        """Return the most recent PnL record."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM pnl_history ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ─── Bot Status ─────────────────────────────────────────────────────────

    def update_bot_status(
        self,
        status: str,
        current_regime: str = "UNKNOWN",
        last_loop_time: Optional[str] = None,
        message: Optional[str] = None,
    ):
        """Set the current bot status."""
        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT INTO bot_status
                   (timestamp, status, current_regime, last_loop_time, message)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    status,
                    current_regime,
                    last_loop_time or datetime.now(timezone.utc).isoformat(),
                    message,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_latest_status(self) -> Optional[dict]:
        """Return the most recent bot status."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM bot_status ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()