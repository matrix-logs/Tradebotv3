"""
Momentum-based trading strategy.
Trades based on price momentum and trend strength.
"""

from datetime import datetime
from typing import Dict, Optional

from ..signals.signal_detector import SignalStrength, SignalType, TradingSignal
from ..utils.data_store import DataStore
from .base_strategy import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """
    Momentum trading strategy.

    Generates signals based on:
    - Price change velocity over multiple timeframes
    - Acceleration of price movement
    - Confirmation across timeframes
    """

    def __init__(
        self,
        data_store: DataStore,
        config: Dict = None
    ):
        """
        Initialize momentum strategy.

        Args:
            data_store: DataStore for price history
            config: Strategy configuration
        """
        super().__init__("momentum", data_store, config)

        # Configuration
        self.price_change_threshold = config.get("price_change_threshold", 0.5)
        self.lookback_seconds = config.get("lookback_seconds", 30)
        self.confirmations = config.get("confirmations", 3)

        # Internal state
        self._confirmation_count = 0
        self._last_direction: Optional[str] = None

    def analyze(
        self,
        current_price: float,
        indicators: Dict[str, float] = None
    ) -> TradingSignal:
        """
        Analyze momentum and generate signal.

        Args:
            current_price: Current market price
            indicators: Optional indicator values

        Returns:
            TradingSignal based on momentum analysis
        """
        indicators = indicators or {}
        reasons = []

        # Calculate momentum across timeframes
        change_5s = self.data_store.calculate_price_change(5)
        change_15s = self.data_store.calculate_price_change(15)
        change_30s = self.data_store.calculate_price_change(30)
        change_60s = self.data_store.calculate_price_change(60)

        # Check if we have enough data
        if change_30s is None:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                confidence=0.5,
                price=current_price,
                timestamp=datetime.now(),
                strategy=self.name,
                reasons=["Insufficient price history"]
            )

        # Calculate momentum score
        momentum_score = self._calculate_momentum_score(
            change_5s, change_15s, change_30s, change_60s
        )

        # Determine signal direction
        signal_type = SignalType.HOLD
        strength = SignalStrength.WEAK
        confidence = 0.5

        if momentum_score > 0.6:
            # Strong bullish momentum
            direction = "BUY"

            if momentum_score > 0.8:
                signal_type = SignalType.BUY
                strength = SignalStrength.VERY_STRONG
                confidence = 0.9
                reasons.append(f"Very strong bullish momentum: {momentum_score:.2f}")
            elif momentum_score > 0.7:
                signal_type = SignalType.BUY
                strength = SignalStrength.STRONG
                confidence = 0.8
                reasons.append(f"Strong bullish momentum: {momentum_score:.2f}")
            else:
                signal_type = SignalType.BUY
                strength = SignalStrength.MODERATE
                confidence = 0.7
                reasons.append(f"Moderate bullish momentum: {momentum_score:.2f}")

        elif momentum_score < -0.6:
            # Strong bearish momentum
            direction = "SELL"

            if momentum_score < -0.8:
                signal_type = SignalType.SELL
                strength = SignalStrength.VERY_STRONG
                confidence = 0.9
                reasons.append(f"Very strong bearish momentum: {momentum_score:.2f}")
            elif momentum_score < -0.7:
                signal_type = SignalType.SELL
                strength = SignalStrength.STRONG
                confidence = 0.8
                reasons.append(f"Strong bearish momentum: {momentum_score:.2f}")
            else:
                signal_type = SignalType.SELL
                strength = SignalStrength.MODERATE
                confidence = 0.7
                reasons.append(f"Moderate bearish momentum: {momentum_score:.2f}")
        else:
            direction = None
            reasons.append(f"Neutral momentum: {momentum_score:.2f}")

        # Apply confirmation logic
        if direction:
            if direction == self._last_direction:
                self._confirmation_count += 1
            else:
                self._confirmation_count = 1
                self._last_direction = direction

            if self._confirmation_count < self.confirmations:
                # Not enough confirmations yet
                reasons.append(
                    f"Awaiting confirmation ({self._confirmation_count}/{self.confirmations})"
                )
                signal_type = SignalType.HOLD
                strength = SignalStrength.WEAK
        else:
            self._confirmation_count = 0
            self._last_direction = None

        # Add momentum details to reasons
        reasons.append(f"5s: {change_5s:+.2f}%" if change_5s else "5s: N/A")
        reasons.append(f"30s: {change_30s:+.2f}%" if change_30s else "30s: N/A")

        # Consider existing position
        if signal_type == SignalType.BUY and self.position == "long":
            signal_type = SignalType.HOLD
            reasons.append("Already in long position")
        elif signal_type == SignalType.SELL and self.position == "short":
            signal_type = SignalType.HOLD
            reasons.append("Already in short position")

        # Check for exit signals
        if self.position == "long" and momentum_score < -0.3:
            signal_type = SignalType.SELL
            strength = SignalStrength.MODERATE
            confidence = 0.7
            reasons.append("Momentum reversal - exit long")

        elif self.position == "short" and momentum_score > 0.3:
            signal_type = SignalType.BUY
            strength = SignalStrength.MODERATE
            confidence = 0.7
            reasons.append("Momentum reversal - exit short")

        return TradingSignal(
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            price=current_price,
            timestamp=datetime.now(),
            strategy=self.name,
            reasons=reasons,
            metadata={
                "momentum_score": momentum_score,
                "change_5s": change_5s,
                "change_15s": change_15s,
                "change_30s": change_30s,
                "change_60s": change_60s,
                "confirmations": self._confirmation_count
            }
        )

    def _calculate_momentum_score(
        self,
        change_5s: Optional[float],
        change_15s: Optional[float],
        change_30s: Optional[float],
        change_60s: Optional[float]
    ) -> float:
        """
        Calculate a normalized momentum score from -1 to 1.

        Weights:
        - Short-term (5s): 40% weight
        - Medium-term (15s, 30s): 40% weight
        - Long-term (60s): 20% weight
        """
        score = 0.0
        weights_used = 0.0

        # Short-term component
        if change_5s is not None:
            # Normalize to -1 to 1 (assuming max 2% change in 5s is extreme)
            normalized = max(-1, min(1, change_5s / 2))
            score += normalized * 0.4
            weights_used += 0.4

        # Medium-term components
        if change_15s is not None:
            normalized = max(-1, min(1, change_15s / 3))
            score += normalized * 0.2
            weights_used += 0.2

        if change_30s is not None:
            normalized = max(-1, min(1, change_30s / 4))
            score += normalized * 0.2
            weights_used += 0.2

        # Long-term component
        if change_60s is not None:
            normalized = max(-1, min(1, change_60s / 5))
            score += normalized * 0.2
            weights_used += 0.2

        # Normalize by weights used
        if weights_used > 0:
            score = score / weights_used

        # Check for acceleration (short-term outpacing long-term)
        if change_5s is not None and change_60s is not None:
            if abs(change_5s) > abs(change_60s) * 0.3:
                # Acceleration detected - boost score
                score *= 1.2
                score = max(-1, min(1, score))

        return score

    def reset(self):
        """Reset strategy state."""
        super().reset()
        self._confirmation_count = 0
        self._last_direction = None
