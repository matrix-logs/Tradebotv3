"""
Base strategy class that all trading strategies inherit from.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from ..signals.signal_detector import SignalType, TradingSignal
from ..utils.data_store import DataStore


@dataclass
class StrategyState:
    """Current state of a trading strategy."""
    name: str
    is_active: bool
    position: str  # "long", "short", "flat"
    entry_price: Optional[float]
    entry_time: Optional[datetime]
    unrealized_pnl: float
    trade_count: int
    win_count: int
    loss_count: int

    @property
    def win_rate(self) -> float:
        if self.trade_count == 0:
            return 0.0
        return self.win_count / self.trade_count


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.
    All strategies must implement the analyze() method.
    """

    def __init__(
        self,
        name: str,
        data_store: DataStore,
        config: Dict = None
    ):
        """
        Initialize the strategy.

        Args:
            name: Strategy identifier
            data_store: DataStore for price history
            config: Strategy-specific configuration
        """
        self.name = name
        self.data_store = data_store
        self.config = config or {}

        # State tracking
        self.is_active = True
        self.position = "flat"  # "long", "short", or "flat"
        self.entry_price: Optional[float] = None
        self.entry_time: Optional[datetime] = None

        # Performance tracking
        self.trade_count = 0
        self.win_count = 0
        self.loss_count = 0
        self.total_pnl = 0.0

        # Trade history
        self._trade_history: List[Dict] = []

    @abstractmethod
    def analyze(
        self,
        current_price: float,
        indicators: Dict[str, float] = None
    ) -> TradingSignal:
        """
        Analyze market conditions and generate trading signal.

        Args:
            current_price: Current market price
            indicators: Optional indicator values

        Returns:
            TradingSignal with recommendation
        """
        pass

    def on_signal(self, signal: TradingSignal) -> Optional[Dict]:
        """
        Handle a trading signal and update position.

        Args:
            signal: Signal to process

        Returns:
            Trade action dict if trade executed, None otherwise
        """
        if not signal.is_actionable:
            return None

        action = None

        if signal.signal_type == SignalType.BUY:
            if self.position == "flat":
                # Enter long
                self.position = "long"
                self.entry_price = signal.price
                self.entry_time = signal.timestamp
                action = {
                    "action": "BUY",
                    "price": signal.price,
                    "time": signal.timestamp,
                    "reason": "Enter long position"
                }
            elif self.position == "short":
                # Close short
                pnl = self.entry_price - signal.price
                self._record_trade(pnl)
                self.position = "flat"
                self.entry_price = None
                self.entry_time = None
                action = {
                    "action": "BUY",
                    "price": signal.price,
                    "time": signal.timestamp,
                    "reason": "Close short position",
                    "pnl": pnl
                }

        elif signal.signal_type == SignalType.SELL:
            if self.position == "flat":
                # Enter short
                self.position = "short"
                self.entry_price = signal.price
                self.entry_time = signal.timestamp
                action = {
                    "action": "SELL",
                    "price": signal.price,
                    "time": signal.timestamp,
                    "reason": "Enter short position"
                }
            elif self.position == "long":
                # Close long
                pnl = signal.price - self.entry_price
                self._record_trade(pnl)
                self.position = "flat"
                self.entry_price = None
                self.entry_time = None
                action = {
                    "action": "SELL",
                    "price": signal.price,
                    "time": signal.timestamp,
                    "reason": "Close long position",
                    "pnl": pnl
                }

        if action:
            self._trade_history.append(action)

        return action

    def _record_trade(self, pnl: float):
        """Record trade result."""
        self.trade_count += 1
        self.total_pnl += pnl

        if pnl > 0:
            self.win_count += 1
        else:
            self.loss_count += 1

    def get_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L for current position."""
        if self.position == "flat" or self.entry_price is None:
            return 0.0

        if self.position == "long":
            return current_price - self.entry_price
        else:  # short
            return self.entry_price - current_price

    def get_state(self) -> StrategyState:
        """Get current strategy state."""
        return StrategyState(
            name=self.name,
            is_active=self.is_active,
            position=self.position,
            entry_price=self.entry_price,
            entry_time=self.entry_time,
            unrealized_pnl=0.0,  # Would need current price
            trade_count=self.trade_count,
            win_count=self.win_count,
            loss_count=self.loss_count
        )

    def reset(self):
        """Reset strategy state."""
        self.position = "flat"
        self.entry_price = None
        self.entry_time = None

    def deactivate(self):
        """Deactivate strategy."""
        self.is_active = False

    def activate(self):
        """Activate strategy."""
        self.is_active = True
