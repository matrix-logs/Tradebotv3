"""
Strategy manager for coordinating multiple trading strategies.

Now includes TheStrat as the primary strategy for forex/XAU-USD trading.
"""

from datetime import datetime
from typing import Dict, List, Optional, Type

from ..signals.signal_detector import SignalType, TradingSignal
from ..utils.data_store import DataStore
from .base_strategy import BaseStrategy, StrategyState
from .momentum_strategy import MomentumStrategy
from .breakout_strategy import BreakoutStrategy
from .thestrat_strategy import TheStratStrategy
from .market_condition import MarketConditionDetector


# Registry of available strategies
# TheStrat is now the recommended primary strategy
STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {
    "thestrat": TheStratStrategy,  # Primary - based on Rob Smith's methodology
    "momentum": MomentumStrategy,  # Legacy - not recommended per TheStrat principles
    "breakout": BreakoutStrategy,  # Legacy - partially useful
}


class StrategyManager:
    """
    Manages multiple trading strategies and combines their signals.
    """

    def __init__(
        self,
        data_store: DataStore,
        config: Dict = None
    ):
        """
        Initialize strategy manager.

        Args:
            data_store: DataStore for price history
            config: Strategy configuration
        """
        self.data_store = data_store
        self.config = config or {}

        # Active strategies
        self.strategies: Dict[str, BaseStrategy] = {}

        # Get active strategy from config (default to TheStrat)
        self.active_strategy_name = self.config.get("active", "thestrat")

        # Market condition detector for adaptive strategy selection
        self.market_condition_detector: Optional[MarketConditionDetector] = None

        # Initialize configured strategies
        self._init_strategies()

    def _init_strategies(self):
        """Initialize strategies from configuration."""
        strategies_config = self.config.get("strategies", {})

        for name, strategy_config in strategies_config.items():
            if name in STRATEGY_REGISTRY:
                strategy_class = STRATEGY_REGISTRY[name]
                self.strategies[name] = strategy_class(
                    data_store=self.data_store,
                    config=strategy_config
                )

        # Ensure active strategy exists
        if self.active_strategy_name not in self.strategies:
            # Create with defaults
            if self.active_strategy_name in STRATEGY_REGISTRY:
                strategy_class = STRATEGY_REGISTRY[self.active_strategy_name]
                self.strategies[self.active_strategy_name] = strategy_class(
                    data_store=self.data_store,
                    config={}
                )

    def get_signal(
        self,
        current_price: float,
        indicators: Dict[str, float] = None
    ) -> TradingSignal:
        """
        Get trading signal from active strategy.

        Args:
            current_price: Current market price
            indicators: Optional indicator values

        Returns:
            TradingSignal from active strategy
        """
        if self.active_strategy_name not in self.strategies:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=1,
                confidence=0.0,
                price=current_price,
                timestamp=datetime.now(),
                strategy="none",
                reasons=["No active strategy"]
            )

        strategy = self.strategies[self.active_strategy_name]

        if not strategy.is_active:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=1,
                confidence=0.0,
                price=current_price,
                timestamp=datetime.now(),
                strategy=strategy.name,
                reasons=["Strategy is deactivated"]
            )

        return strategy.analyze(current_price, indicators)

    def get_all_signals(
        self,
        current_price: float,
        indicators: Dict[str, float] = None
    ) -> Dict[str, TradingSignal]:
        """
        Get signals from all active strategies.

        Args:
            current_price: Current market price
            indicators: Optional indicator values

        Returns:
            Dict of strategy_name -> TradingSignal
        """
        signals = {}

        for name, strategy in self.strategies.items():
            if strategy.is_active:
                signals[name] = strategy.analyze(current_price, indicators)

        return signals

    def get_consensus_signal(
        self,
        current_price: float,
        indicators: Dict[str, float] = None,
        min_agreement: float = 0.6
    ) -> TradingSignal:
        """
        Get consensus signal from all strategies.

        Args:
            current_price: Current market price
            indicators: Optional indicator values
            min_agreement: Minimum ratio of strategies that must agree

        Returns:
            Combined TradingSignal
        """
        all_signals = self.get_all_signals(current_price, indicators)

        if not all_signals:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=1,
                confidence=0.0,
                price=current_price,
                timestamp=datetime.now(),
                strategy="consensus",
                reasons=["No active strategies"]
            )

        # Count signal types
        buy_signals = [s for s in all_signals.values() if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in all_signals.values() if s.signal_type == SignalType.SELL]
        total = len(all_signals)

        buy_ratio = len(buy_signals) / total
        sell_ratio = len(sell_signals) / total

        reasons = [f"Strategies analyzed: {total}"]
        reasons.append(f"Buy signals: {len(buy_signals)}, Sell signals: {len(sell_signals)}")

        if buy_ratio >= min_agreement:
            avg_confidence = sum(s.confidence for s in buy_signals) / len(buy_signals)
            max_strength = max(s.strength for s in buy_signals)
            return TradingSignal(
                signal_type=SignalType.BUY,
                strength=max_strength,
                confidence=avg_confidence * buy_ratio,
                price=current_price,
                timestamp=datetime.now(),
                strategy="consensus",
                reasons=reasons + [f"Consensus: BUY ({buy_ratio:.0%} agreement)"]
            )

        elif sell_ratio >= min_agreement:
            avg_confidence = sum(s.confidence for s in sell_signals) / len(sell_signals)
            max_strength = max(s.strength for s in sell_signals)
            return TradingSignal(
                signal_type=SignalType.SELL,
                strength=max_strength,
                confidence=avg_confidence * sell_ratio,
                price=current_price,
                timestamp=datetime.now(),
                strategy="consensus",
                reasons=reasons + [f"Consensus: SELL ({sell_ratio:.0%} agreement)"]
            )

        else:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=1,
                confidence=0.5,
                price=current_price,
                timestamp=datetime.now(),
                strategy="consensus",
                reasons=reasons + ["No consensus reached"]
            )

    def set_active_strategy(self, name: str) -> bool:
        """
        Set the active strategy.

        Args:
            name: Strategy name

        Returns:
            True if successful
        """
        if name not in self.strategies:
            return False

        self.active_strategy_name = name
        return True

    def add_strategy(self, name: str, strategy: BaseStrategy):
        """Add a custom strategy."""
        self.strategies[name] = strategy

    def remove_strategy(self, name: str) -> bool:
        """Remove a strategy."""
        if name in self.strategies:
            del self.strategies[name]
            return True
        return False

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """Get a strategy by name."""
        return self.strategies.get(name)

    def get_all_states(self) -> Dict[str, StrategyState]:
        """Get state of all strategies."""
        return {
            name: strategy.get_state()
            for name, strategy in self.strategies.items()
        }

    def reset_all(self):
        """Reset all strategies."""
        for strategy in self.strategies.values():
            strategy.reset()

    def deactivate_all(self):
        """Deactivate all strategies."""
        for strategy in self.strategies.values():
            strategy.deactivate()

    def activate_all(self):
        """Activate all strategies."""
        for strategy in self.strategies.values():
            strategy.activate()

    @property
    def active_strategy(self) -> Optional[BaseStrategy]:
        """Get the currently active strategy."""
        return self.strategies.get(self.active_strategy_name)

    @property
    def available_strategies(self) -> List[str]:
        """Get list of available strategy names."""
        return list(STRATEGY_REGISTRY.keys())
