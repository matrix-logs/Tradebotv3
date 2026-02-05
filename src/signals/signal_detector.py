"""
Signal detection module for identifying trading opportunities.
Analyzes price data and indicators to generate trading signals.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from ..utils.data_store import DataStore, PricePoint


class SignalType(Enum):
    """Types of trading signals."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"


class SignalStrength(Enum):
    """Signal strength levels."""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4


@dataclass
class TradingSignal:
    """Represents a trading signal."""
    signal_type: SignalType
    strength: SignalStrength
    confidence: float  # 0.0 to 1.0
    price: float
    timestamp: datetime
    strategy: str
    reasons: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        """Check if signal is strong enough to act on."""
        return (
            self.confidence >= 0.7 and
            self.strength.value >= SignalStrength.MODERATE.value and
            self.signal_type != SignalType.HOLD
        )

    def __repr__(self):
        return (
            f"TradingSignal({self.signal_type.value}, "
            f"strength={self.strength.name}, "
            f"conf={self.confidence:.2f}, "
            f"price={self.price})"
        )


class SignalDetector:
    """
    Detects trading signals from market data.
    Uses multiple indicators and confirmation logic.
    """

    def __init__(
        self,
        data_store: DataStore,
        config: Dict = None
    ):
        """
        Initialize the signal detector.

        Args:
            data_store: DataStore instance for price history
            config: Signal configuration
        """
        self.data_store = data_store
        self.config = config or {}

        # Signal state
        self._last_signal: Optional[TradingSignal] = None
        self._signal_history: List[TradingSignal] = []
        self._cooldown_until: Optional[datetime] = None

        # Configuration
        self.min_confidence = self.config.get("min_confidence", 0.7)
        self.cooldown_seconds = self.config.get("cooldown_seconds", 60)
        self.confirmations_required = self.config.get("confirmations", 3)

        # Confirmation tracking
        self._pending_signals: Dict[str, int] = {}  # signal_type -> confirmation count

    def detect(
        self,
        current_price: float,
        indicators: Dict[str, float] = None
    ) -> TradingSignal:
        """
        Analyze current market state and detect signals.

        Args:
            current_price: Current market price
            indicators: Optional indicator values (RSI, MACD, etc.)

        Returns:
            TradingSignal with detection result
        """
        indicators = indicators or {}
        reasons = []
        signals_detected = []

        # Check cooldown
        if self._cooldown_until and datetime.now() < self._cooldown_until:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                confidence=1.0,
                price=current_price,
                timestamp=datetime.now(),
                strategy="cooldown",
                reasons=["Signal cooldown active"]
            )

        # === Price Momentum Analysis ===
        momentum_signal = self._analyze_momentum(current_price)
        if momentum_signal:
            signals_detected.append(momentum_signal)
            reasons.extend(momentum_signal.reasons)

        # === Indicator Analysis ===
        if "RSI" in indicators:
            rsi_signal = self._analyze_rsi(indicators["RSI"], current_price)
            if rsi_signal:
                signals_detected.append(rsi_signal)
                reasons.extend(rsi_signal.reasons)

        if "MACD" in indicators:
            macd_signal = self._analyze_macd(indicators["MACD"], current_price)
            if macd_signal:
                signals_detected.append(macd_signal)
                reasons.extend(macd_signal.reasons)

        # === Combine Signals ===
        final_signal = self._combine_signals(signals_detected, current_price, reasons)

        # Apply confirmation logic
        final_signal = self._apply_confirmations(final_signal)

        # Store signal
        self._last_signal = final_signal
        if final_signal.is_actionable:
            self._signal_history.append(final_signal)

        return final_signal

    def _analyze_momentum(self, current_price: float) -> Optional[TradingSignal]:
        """Analyze price momentum."""
        # Get price changes over different periods
        change_5s = self.data_store.calculate_price_change(5)
        change_30s = self.data_store.calculate_price_change(30)
        change_60s = self.data_store.calculate_price_change(60)

        if None in (change_5s, change_30s, change_60s):
            return None

        reasons = []
        signal_type = SignalType.HOLD
        strength = SignalStrength.WEAK
        confidence = 0.5

        # Strong upward momentum
        if change_5s > 0.1 and change_30s > 0.3 and change_60s > 0.5:
            signal_type = SignalType.BUY
            strength = SignalStrength.STRONG
            confidence = 0.8
            reasons.append(f"Strong upward momentum: +{change_60s:.2f}% (60s)")

        # Moderate upward momentum
        elif change_30s > 0.2 and change_60s > 0.3:
            signal_type = SignalType.BUY
            strength = SignalStrength.MODERATE
            confidence = 0.65
            reasons.append(f"Moderate upward momentum: +{change_60s:.2f}% (60s)")

        # Strong downward momentum
        elif change_5s < -0.1 and change_30s < -0.3 and change_60s < -0.5:
            signal_type = SignalType.SELL
            strength = SignalStrength.STRONG
            confidence = 0.8
            reasons.append(f"Strong downward momentum: {change_60s:.2f}% (60s)")

        # Moderate downward momentum
        elif change_30s < -0.2 and change_60s < -0.3:
            signal_type = SignalType.SELL
            strength = SignalStrength.MODERATE
            confidence = 0.65
            reasons.append(f"Moderate downward momentum: {change_60s:.2f}% (60s)")

        if signal_type == SignalType.HOLD:
            return None

        return TradingSignal(
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            price=current_price,
            timestamp=datetime.now(),
            strategy="momentum",
            reasons=reasons,
            metadata={"change_5s": change_5s, "change_30s": change_30s, "change_60s": change_60s}
        )

    def _analyze_rsi(self, rsi: float, current_price: float) -> Optional[TradingSignal]:
        """Analyze RSI indicator."""
        reasons = []
        signal_type = SignalType.HOLD
        strength = SignalStrength.WEAK
        confidence = 0.5

        # Oversold
        if rsi < 20:
            signal_type = SignalType.BUY
            strength = SignalStrength.STRONG
            confidence = 0.85
            reasons.append(f"RSI extremely oversold: {rsi:.1f}")
        elif rsi < 30:
            signal_type = SignalType.BUY
            strength = SignalStrength.MODERATE
            confidence = 0.7
            reasons.append(f"RSI oversold: {rsi:.1f}")

        # Overbought
        elif rsi > 80:
            signal_type = SignalType.SELL
            strength = SignalStrength.STRONG
            confidence = 0.85
            reasons.append(f"RSI extremely overbought: {rsi:.1f}")
        elif rsi > 70:
            signal_type = SignalType.SELL
            strength = SignalStrength.MODERATE
            confidence = 0.7
            reasons.append(f"RSI overbought: {rsi:.1f}")

        if signal_type == SignalType.HOLD:
            return None

        return TradingSignal(
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            price=current_price,
            timestamp=datetime.now(),
            strategy="rsi",
            reasons=reasons,
            metadata={"rsi": rsi}
        )

    def _analyze_macd(self, macd_value: float, current_price: float) -> Optional[TradingSignal]:
        """Analyze MACD indicator."""
        # This would typically need MACD line, signal line, and histogram
        # Simplified version using just the value
        reasons = []
        signal_type = SignalType.HOLD

        if macd_value > 0:
            signal_type = SignalType.BUY
            reasons.append(f"MACD positive: {macd_value:.4f}")
        elif macd_value < 0:
            signal_type = SignalType.SELL
            reasons.append(f"MACD negative: {macd_value:.4f}")

        if signal_type == SignalType.HOLD:
            return None

        return TradingSignal(
            signal_type=signal_type,
            strength=SignalStrength.WEAK,
            confidence=0.55,
            price=current_price,
            timestamp=datetime.now(),
            strategy="macd",
            reasons=reasons,
            metadata={"macd": macd_value}
        )

    def _combine_signals(
        self,
        signals: List[TradingSignal],
        current_price: float,
        all_reasons: List[str]
    ) -> TradingSignal:
        """Combine multiple signals into a final signal."""
        if not signals:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                confidence=0.5,
                price=current_price,
                timestamp=datetime.now(),
                strategy="combined",
                reasons=["No clear signals detected"]
            )

        # Count signal types
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]

        # Conflicting signals = HOLD
        if buy_signals and sell_signals:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                confidence=0.5,
                price=current_price,
                timestamp=datetime.now(),
                strategy="combined",
                reasons=["Conflicting signals - holding"]
            )

        # Combine agreeing signals
        if buy_signals:
            avg_confidence = sum(s.confidence for s in buy_signals) / len(buy_signals)
            max_strength = max(s.strength for s in buy_signals)

            # Boost confidence for multiple agreeing signals
            if len(buy_signals) > 1:
                avg_confidence = min(0.95, avg_confidence + 0.1 * (len(buy_signals) - 1))

            return TradingSignal(
                signal_type=SignalType.BUY,
                strength=max_strength,
                confidence=avg_confidence,
                price=current_price,
                timestamp=datetime.now(),
                strategy="combined",
                reasons=all_reasons
            )

        if sell_signals:
            avg_confidence = sum(s.confidence for s in sell_signals) / len(sell_signals)
            max_strength = max(s.strength for s in sell_signals)

            if len(sell_signals) > 1:
                avg_confidence = min(0.95, avg_confidence + 0.1 * (len(sell_signals) - 1))

            return TradingSignal(
                signal_type=SignalType.SELL,
                strength=max_strength,
                confidence=avg_confidence,
                price=current_price,
                timestamp=datetime.now(),
                strategy="combined",
                reasons=all_reasons
            )

        # Default to HOLD
        return TradingSignal(
            signal_type=SignalType.HOLD,
            strength=SignalStrength.WEAK,
            confidence=0.5,
            price=current_price,
            timestamp=datetime.now(),
            strategy="combined",
            reasons=all_reasons or ["No actionable signals"]
        )

    def _apply_confirmations(self, signal: TradingSignal) -> TradingSignal:
        """Apply confirmation logic to reduce false signals."""
        if signal.signal_type == SignalType.HOLD:
            # Reset pending confirmations
            self._pending_signals.clear()
            return signal

        signal_key = signal.signal_type.value

        # Increment confirmation count
        self._pending_signals[signal_key] = self._pending_signals.get(signal_key, 0) + 1

        # Reset opposite signal
        opposite = "SELL" if signal_key == "BUY" else "BUY"
        self._pending_signals[opposite] = 0

        # Check if enough confirmations
        if self._pending_signals[signal_key] < self.confirmations_required:
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                confidence=0.5,
                price=signal.price,
                timestamp=signal.timestamp,
                strategy=signal.strategy,
                reasons=[
                    f"Awaiting confirmation ({self._pending_signals[signal_key]}/{self.confirmations_required})"
                ]
            )

        # Confirmed! Reset and return signal
        self._pending_signals.clear()
        return signal

    def reset_cooldown(self):
        """Reset signal cooldown."""
        self._cooldown_until = None

    def start_cooldown(self):
        """Start signal cooldown period."""
        from datetime import timedelta
        self._cooldown_until = datetime.now() + timedelta(seconds=self.cooldown_seconds)

    @property
    def last_signal(self) -> Optional[TradingSignal]:
        """Get the last detected signal."""
        return self._last_signal

    @property
    def signal_history(self) -> List[TradingSignal]:
        """Get signal history."""
        return self._signal_history.copy()
