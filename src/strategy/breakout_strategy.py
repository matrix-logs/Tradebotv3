"""
Breakout trading strategy.
Trades based on price breaking through support/resistance levels.
"""

from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple

from ..signals.signal_detector import SignalStrength, SignalType, TradingSignal
from ..utils.data_store import DataStore
from .base_strategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """
    Breakout trading strategy.

    Detects and trades breakouts from:
    - Automatically detected support/resistance levels
    - Manual price levels
    - Recent price range boundaries
    """

    def __init__(
        self,
        data_store: DataStore,
        config: Dict = None
    ):
        """
        Initialize breakout strategy.

        Args:
            data_store: DataStore for price history
            config: Strategy configuration
        """
        super().__init__("breakout", data_store, config)

        # Configuration
        self.levels_mode = config.get("levels_mode", "auto")
        self.manual_support = config.get("manual_levels", {}).get("support", [])
        self.manual_resistance = config.get("manual_levels", {}).get("resistance", [])
        self.confirmation_candles = config.get("confirmation_candles", 2)
        self.breakout_threshold = config.get("breakout_threshold", 0.1)  # % above/below level

        # Auto-detected levels
        self._support_levels: List[float] = []
        self._resistance_levels: List[float] = []

        # Tracking
        self._recent_highs: Deque[float] = deque(maxlen=100)
        self._recent_lows: Deque[float] = deque(maxlen=100)
        self._breakout_confirmations = 0
        self._pending_breakout: Optional[str] = None
        self._last_breakout_price: Optional[float] = None

    def analyze(
        self,
        current_price: float,
        indicators: Dict[str, float] = None
    ) -> TradingSignal:
        """
        Analyze for breakout opportunities.

        Args:
            current_price: Current market price
            indicators: Optional indicator values

        Returns:
            TradingSignal based on breakout analysis
        """
        indicators = indicators or {}
        reasons = []

        # Update price tracking
        self._update_price_tracking(current_price)

        # Auto-detect levels if needed
        if self.levels_mode == "auto":
            self._auto_detect_levels()

        # Get all levels to check
        support_levels = self._support_levels + self.manual_support
        resistance_levels = self._resistance_levels + self.manual_resistance

        if not support_levels and not resistance_levels:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                confidence=0.5,
                price=current_price,
                timestamp=datetime.now(),
                strategy=self.name,
                reasons=["No levels detected yet"]
            )

        # Check for breakouts
        breakout_type, breakout_level, strength = self._check_breakout(
            current_price, support_levels, resistance_levels
        )

        signal_type = SignalType.HOLD
        confidence = 0.5
        signal_strength = SignalStrength.WEAK

        if breakout_type == "resistance":
            # Bullish breakout above resistance
            if self._pending_breakout == "resistance":
                self._breakout_confirmations += 1
            else:
                self._pending_breakout = "resistance"
                self._breakout_confirmations = 1
                self._last_breakout_price = breakout_level

            if self._breakout_confirmations >= self.confirmation_candles:
                signal_type = SignalType.BUY
                signal_strength = strength
                confidence = 0.75 + (self._breakout_confirmations * 0.05)
                reasons.append(f"Breakout above resistance {breakout_level:.2f}")
                reasons.append(f"Confirmed with {self._breakout_confirmations} readings")
            else:
                reasons.append(
                    f"Potential resistance breakout at {breakout_level:.2f} "
                    f"({self._breakout_confirmations}/{self.confirmation_candles})"
                )

        elif breakout_type == "support":
            # Bearish breakout below support
            if self._pending_breakout == "support":
                self._breakout_confirmations += 1
            else:
                self._pending_breakout = "support"
                self._breakout_confirmations = 1
                self._last_breakout_price = breakout_level

            if self._breakout_confirmations >= self.confirmation_candles:
                signal_type = SignalType.SELL
                signal_strength = strength
                confidence = 0.75 + (self._breakout_confirmations * 0.05)
                reasons.append(f"Breakdown below support {breakout_level:.2f}")
                reasons.append(f"Confirmed with {self._breakout_confirmations} readings")
            else:
                reasons.append(
                    f"Potential support breakdown at {breakout_level:.2f} "
                    f"({self._breakout_confirmations}/{self.confirmation_candles})"
                )

        else:
            # No breakout - price within range
            self._pending_breakout = None
            self._breakout_confirmations = 0
            reasons.append("Price within established range")

            # Report nearby levels
            nearest_support = self._find_nearest_level(current_price, support_levels, "below")
            nearest_resistance = self._find_nearest_level(current_price, resistance_levels, "above")

            if nearest_support:
                reasons.append(f"Support: {nearest_support:.2f}")
            if nearest_resistance:
                reasons.append(f"Resistance: {nearest_resistance:.2f}")

        # Don't signal if already in a position in the same direction
        if signal_type == SignalType.BUY and self.position == "long":
            signal_type = SignalType.HOLD
            reasons.append("Already long")
        elif signal_type == SignalType.SELL and self.position == "short":
            signal_type = SignalType.HOLD
            reasons.append("Already short")

        return TradingSignal(
            signal_type=signal_type,
            strength=signal_strength,
            confidence=min(0.95, confidence),
            price=current_price,
            timestamp=datetime.now(),
            strategy=self.name,
            reasons=reasons,
            metadata={
                "support_levels": support_levels[:5],
                "resistance_levels": resistance_levels[:5],
                "breakout_confirmations": self._breakout_confirmations,
                "pending_breakout": self._pending_breakout
            }
        )

    def _update_price_tracking(self, price: float):
        """Update price tracking for level detection."""
        self._recent_highs.append(price)
        self._recent_lows.append(price)

    def _auto_detect_levels(self):
        """Automatically detect support and resistance levels."""
        if len(self._recent_highs) < 20:
            return

        prices = list(self._recent_highs)

        # Simple pivot point detection
        support = []
        resistance = []

        for i in range(2, len(prices) - 2):
            # Local minimum = support
            if (prices[i] < prices[i-1] and prices[i] < prices[i-2] and
                prices[i] < prices[i+1] and prices[i] < prices[i+2]):
                support.append(prices[i])

            # Local maximum = resistance
            if (prices[i] > prices[i-1] and prices[i] > prices[i-2] and
                prices[i] > prices[i+1] and prices[i] > prices[i+2]):
                resistance.append(prices[i])

        # Keep unique levels (cluster similar ones)
        self._support_levels = self._cluster_levels(support)
        self._resistance_levels = self._cluster_levels(resistance)

    def _cluster_levels(self, levels: List[float], threshold: float = 0.5) -> List[float]:
        """Cluster nearby price levels into single levels."""
        if not levels:
            return []

        sorted_levels = sorted(levels)
        clustered = [sorted_levels[0]]

        for level in sorted_levels[1:]:
            # Check if level is close to last clustered level
            pct_diff = abs(level - clustered[-1]) / clustered[-1] * 100
            if pct_diff > threshold:
                clustered.append(level)
            else:
                # Average with existing level
                clustered[-1] = (clustered[-1] + level) / 2

        return clustered[-5:]  # Keep only 5 most recent

    def _check_breakout(
        self,
        price: float,
        support: List[float],
        resistance: List[float]
    ) -> Tuple[Optional[str], Optional[float], SignalStrength]:
        """
        Check if price has broken through any levels.

        Returns:
            Tuple of (breakout_type, level, strength)
        """
        # Check resistance breakouts
        for level in sorted(resistance):
            pct_above = (price - level) / level * 100
            if pct_above > self.breakout_threshold:
                # Determine strength based on how far above
                if pct_above > 0.5:
                    strength = SignalStrength.VERY_STRONG
                elif pct_above > 0.3:
                    strength = SignalStrength.STRONG
                else:
                    strength = SignalStrength.MODERATE
                return ("resistance", level, strength)

        # Check support breakouts
        for level in sorted(support, reverse=True):
            pct_below = (level - price) / level * 100
            if pct_below > self.breakout_threshold:
                if pct_below > 0.5:
                    strength = SignalStrength.VERY_STRONG
                elif pct_below > 0.3:
                    strength = SignalStrength.STRONG
                else:
                    strength = SignalStrength.MODERATE
                return ("support", level, strength)

        return (None, None, SignalStrength.WEAK)

    def _find_nearest_level(
        self,
        price: float,
        levels: List[float],
        direction: str
    ) -> Optional[float]:
        """Find the nearest level above or below current price."""
        if not levels:
            return None

        if direction == "above":
            above = [l for l in levels if l > price]
            return min(above) if above else None
        else:
            below = [l for l in levels if l < price]
            return max(below) if below else None

    def add_manual_level(self, level: float, level_type: str):
        """Add a manual support or resistance level."""
        if level_type == "support":
            self.manual_support.append(level)
        elif level_type == "resistance":
            self.manual_resistance.append(level)

    def clear_levels(self):
        """Clear all detected and manual levels."""
        self._support_levels.clear()
        self._resistance_levels.clear()
        self.manual_support.clear()
        self.manual_resistance.clear()

    def reset(self):
        """Reset strategy state."""
        super().reset()
        self._breakout_confirmations = 0
        self._pending_breakout = None
        self._last_breakout_price = None
