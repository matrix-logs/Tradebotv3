"""
Data storage utilities for the trading bot.
Handles price history, trade records, and performance metrics.
"""

import csv
import json
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional


@dataclass
class PricePoint:
    """Represents a single price observation."""
    timestamp: datetime
    price: float
    source: str = "screen"
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "source": self.source,
            "confidence": self.confidence
        }


@dataclass
class TradeRecord:
    """Represents a trade execution."""
    timestamp: datetime
    action: str  # "BUY" or "SELL"
    price: float
    quantity: float
    signal_confidence: float
    strategy: str
    pnl: Optional[float] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "price": self.price,
            "quantity": self.quantity,
            "signal_confidence": self.signal_confidence,
            "strategy": self.strategy,
            "pnl": self.pnl,
            "notes": self.notes
        }


class DataStore:
    """Manages data storage for the trading bot."""

    def __init__(self, data_dir: str = "./data", max_history: int = 10000):
        """
        Initialize the data store.

        Args:
            data_dir: Directory for data files
            max_history: Maximum price points to keep in memory
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.max_history = max_history
        self.price_history: Deque[PricePoint] = deque(maxlen=max_history)
        self.trades: List[TradeRecord] = []

        # File paths
        self.trades_file = self.data_dir / "trades.csv"
        self.prices_file = self.data_dir / "prices.jsonl"

        # Initialize CSV if needed
        self._init_trades_csv()

    def _init_trades_csv(self) -> None:
        """Initialize trades CSV with headers if it doesn't exist."""
        if not self.trades_file.exists():
            with open(self.trades_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "action", "price", "quantity",
                    "signal_confidence", "strategy", "pnl", "notes"
                ])

    def add_price(self, price: float, confidence: float = 1.0, source: str = "screen") -> PricePoint:
        """
        Add a new price observation.

        Args:
            price: The observed price
            confidence: OCR confidence score
            source: Data source identifier

        Returns:
            The created PricePoint
        """
        point = PricePoint(
            timestamp=datetime.now(),
            price=price,
            source=source,
            confidence=confidence
        )
        self.price_history.append(point)

        # Append to file
        with open(self.prices_file, "a") as f:
            f.write(json.dumps(point.to_dict()) + "\n")

        return point

    def get_recent_prices(self, count: int = 100) -> List[PricePoint]:
        """Get the most recent price observations."""
        return list(self.price_history)[-count:]

    def get_price_at(self, seconds_ago: int) -> Optional[PricePoint]:
        """Get the price from approximately N seconds ago."""
        if not self.price_history:
            return None

        target_time = datetime.now().timestamp() - seconds_ago

        # Find closest price point
        closest = None
        min_diff = float("inf")

        for point in self.price_history:
            diff = abs(point.timestamp.timestamp() - target_time)
            if diff < min_diff:
                min_diff = diff
                closest = point

        return closest

    def calculate_price_change(self, seconds: int = 30) -> Optional[float]:
        """
        Calculate price change over the specified period.

        Args:
            seconds: Lookback period in seconds

        Returns:
            Percentage change or None if insufficient data
        """
        if len(self.price_history) < 2:
            return None

        current = self.price_history[-1]
        past = self.get_price_at(seconds)

        if past is None or past.price == 0:
            return None

        return ((current.price - past.price) / past.price) * 100

    def add_trade(self, trade: TradeRecord) -> None:
        """Record a trade execution."""
        self.trades.append(trade)

        # Append to CSV
        with open(self.trades_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                trade.timestamp.isoformat(),
                trade.action,
                trade.price,
                trade.quantity,
                trade.signal_confidence,
                trade.strategy,
                trade.pnl,
                trade.notes
            ])

    def get_trade_stats(self) -> Dict[str, Any]:
        """Calculate trading statistics."""
        if not self.trades:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "total_pnl": 0
            }

        trades_with_pnl = [t for t in self.trades if t.pnl is not None]
        wins = [t for t in trades_with_pnl if t.pnl > 0]
        losses = [t for t in trades_with_pnl if t.pnl < 0]

        return {
            "total_trades": len(self.trades),
            "trades_with_pnl": len(trades_with_pnl),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(trades_with_pnl) if trades_with_pnl else 0,
            "total_pnl": sum(t.pnl for t in trades_with_pnl),
            "avg_win": sum(t.pnl for t in wins) / len(wins) if wins else 0,
            "avg_loss": sum(t.pnl for t in losses) / len(losses) if losses else 0
        }

    def get_today_trades(self) -> List[TradeRecord]:
        """Get all trades from today."""
        today = datetime.now().date()
        return [t for t in self.trades if t.timestamp.date() == today]

    def clear_history(self) -> None:
        """Clear in-memory price history."""
        self.price_history.clear()
