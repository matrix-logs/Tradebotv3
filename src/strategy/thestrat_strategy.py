"""
TheStrat Trading Strategy Implementation

A complete implementation of Rob Smith's TheStrat methodology.

Core Principles:
1. Only three scenarios exist: Inside (1), Trending (2), Outside (3)
2. Trade in direction of timeframe continuity
3. Use specific setups: Inside bar breaks, Failed 2s, 2-2 reversals
4. Add to winners, cut losers quickly

Winning trades happen only 3 ways:
- Scenario 2 in your favor
- Scenario 3 in your favor
- Full Timeframe Continuity in your favor

Losing trades happen only 4 ways:
- Buying during Scenario 1 (chop)
- Buying during Scenario 2 against you
- Scenario 3 against you
- Timeframe Continuity against you
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..signals.signal_detector import SignalStrength, SignalType, TradingSignal
from ..utils.data_store import DataStore
from .base_strategy import BaseStrategy
from .scenario_detector import Candle, Scenario, ScenarioDetector, ScenarioResult
from .timeframe_continuity import (
    ContinuityResult,
    TimeframeBias,
    TimeframeContinuityAnalyzer,
    TimeframeState,
)


class SetupType(Enum):
    """TheStrat setup types."""
    INSIDE_BAR_BREAKOUT = "inside_bar_breakout"
    FAILED_2U = "failed_2u"
    FAILED_2D = "failed_2d"
    REVERSAL_2U_2D = "2u_2d_reversal"
    REVERSAL_2D_2U = "2d_2u_reversal"
    CONTINUATION_2U = "continuation_2u"
    CONTINUATION_2D = "continuation_2d"
    SCENARIO_3_EXPANSION = "scenario_3_expansion"


@dataclass
class StratSetup:
    """A detected TheStrat setup."""
    setup_type: SetupType
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    stop_loss: float
    target: Optional[float]
    timeframe: str
    scenario: ScenarioResult
    confidence: float
    timestamp: datetime
    details: Dict = None

    @property
    def risk_reward(self) -> float:
        """Calculate risk/reward ratio."""
        if not self.target or self.entry_price == self.stop_loss:
            return 0
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.target - self.entry_price)
        return reward / risk if risk > 0 else 0

    def __repr__(self):
        return f"Setup({self.setup_type.value}, {self.direction}, conf={self.confidence:.0%})"


class TheStratStrategy(BaseStrategy):
    """
    TheStrat trading strategy.

    Focuses on two primary setups (as recommended in the PDFs):
    1. Inside Bar breakouts - trade the break of compression
    2. Failed 2s - trade when breakout traders get trapped

    Additional setups:
    - 2-2 Reversals (2U-2D, 2D-2U)
    - Scenario 3 expansions
    - Continuations with FTFC

    Entry Rules:
    - Only trade in direction of timeframe continuity
    - Wait for specific setups to form
    - Use candle levels for entries and stops

    Exit Rules:
    - Stop loss at opposite side of setup candle
    - Target: Previous swing high/low or broadening formation level
    - Exit on Scenario 3 against position
    """

    def __init__(
        self,
        data_store: DataStore,
        config: Dict = None
    ):
        """
        Initialize TheStrat strategy.

        Args:
            data_store: DataStore for price history
            config: Strategy configuration
        """
        super().__init__("thestrat", data_store, config)

        # Initialize components
        self.scenario_detector = ScenarioDetector()
        self.continuity_analyzer = TimeframeContinuityAnalyzer(
            timeframes=config.get("timeframes", ["60", "D", "W", "M"]),
            scenario_detector=self.scenario_detector
        )

        # Configuration
        self.require_ftfc = config.get("require_ftfc", False)
        self.min_continuity = config.get("min_continuity", 0.75)  # 75% alignment
        self.trade_inside_bars = config.get("trade_inside_bars", True)
        self.trade_failed_2s = config.get("trade_failed_2s", True)
        self.trade_reversals = config.get("trade_reversals", True)

        # Candle history by timeframe
        self._candle_history: Dict[str, List[Candle]] = {}

        # Active setups
        self._active_setups: List[StratSetup] = []

        # Track broadening formation levels
        self._swing_highs: List[float] = []
        self._swing_lows: List[float] = []

    def add_candle(
        self,
        timeframe: str,
        candle: Candle,
        tf_open: float = None
    ):
        """
        Add a new candle for a timeframe.

        Args:
            timeframe: Timeframe identifier
            candle: Candle data
            tf_open: Timeframe period opening price
        """
        if timeframe not in self._candle_history:
            self._candle_history[timeframe] = []

        self._candle_history[timeframe].append(candle)

        # Keep history manageable
        if len(self._candle_history[timeframe]) > 500:
            self._candle_history[timeframe] = self._candle_history[timeframe][-250:]

        # Update continuity analyzer
        self.continuity_analyzer.update_timeframe(timeframe, candle, tf_open)

        # Update swing levels
        self._update_swing_levels(candle)

    def add_candle_ohlc(
        self,
        timeframe: str,
        ohlc: Tuple[float, float, float, float],
        tf_open: float = None,
        timestamp: datetime = None
    ):
        """Add candle from OHLC tuple."""
        candle = Candle(
            timestamp=timestamp or datetime.now(),
            open=ohlc[0],
            high=ohlc[1],
            low=ohlc[2],
            close=ohlc[3],
            timeframe=timeframe
        )
        self.add_candle(timeframe, candle, tf_open)

    def _update_swing_levels(self, candle: Candle):
        """Track swing highs and lows for broadening formation."""
        # Simple swing detection - keep recent highs/lows
        self._swing_highs.append(candle.high)
        self._swing_lows.append(candle.low)

        # Keep last 20 swings
        if len(self._swing_highs) > 20:
            self._swing_highs = self._swing_highs[-20:]
        if len(self._swing_lows) > 20:
            self._swing_lows = self._swing_lows[-20:]

    def detect_setups(
        self,
        timeframe: str = "D"
    ) -> List[StratSetup]:
        """
        Detect all active setups on a timeframe.

        Args:
            timeframe: Timeframe to scan for setups

        Returns:
            List of detected setups
        """
        setups = []

        candles = self._candle_history.get(timeframe, [])
        if len(candles) < 3:
            return setups

        # Get continuity for direction filter
        continuity = self.continuity_analyzer.analyze_continuity()

        # Detect Inside Bar setups
        if self.trade_inside_bars:
            inside_setup = self._detect_inside_bar_setup(candles, timeframe, continuity)
            if inside_setup:
                setups.append(inside_setup)

        # Detect Failed 2 setups
        if self.trade_failed_2s:
            failed_2 = self._detect_failed_2_setup(candles, timeframe, continuity)
            if failed_2:
                setups.append(failed_2)

        # Detect 2-2 Reversals
        if self.trade_reversals:
            reversal = self._detect_reversal_setup(candles, timeframe, continuity)
            if reversal:
                setups.append(reversal)

        # Store active setups
        self._active_setups = setups

        return setups

    def _detect_inside_bar_setup(
        self,
        candles: List[Candle],
        timeframe: str,
        continuity: ContinuityResult
    ) -> Optional[StratSetup]:
        """Detect inside bar breakout setup."""
        if len(candles) < 2:
            return None

        current = candles[-1]
        previous = candles[-2]

        scenario = self.scenario_detector.detect_scenario(current, previous)

        if scenario.scenario != Scenario.SCENARIO_1:
            return None

        # Inside bar detected - determine direction based on continuity
        if continuity.is_ftfc_up or continuity.bullish_count > continuity.bearish_count:
            # Look for long breakout
            return StratSetup(
                setup_type=SetupType.INSIDE_BAR_BREAKOUT,
                direction="LONG",
                entry_price=current.high,  # Break above inside bar high
                stop_loss=current.low,  # Below inside bar low
                target=max(self._swing_highs) if self._swing_highs else current.high * 1.02,
                timeframe=timeframe,
                scenario=scenario,
                confidence=0.7 if continuity.has_full_continuity else 0.5,
                timestamp=datetime.now(),
                details={
                    "setup": "Inside bar - waiting for breakout above high",
                    "continuity": continuity.get_summary()
                }
            )

        elif continuity.is_ftfc_down or continuity.bearish_count > continuity.bullish_count:
            # Look for short breakout
            return StratSetup(
                setup_type=SetupType.INSIDE_BAR_BREAKOUT,
                direction="SHORT",
                entry_price=current.low,  # Break below inside bar low
                stop_loss=current.high,  # Above inside bar high
                target=min(self._swing_lows) if self._swing_lows else current.low * 0.98,
                timeframe=timeframe,
                scenario=scenario,
                confidence=0.7 if continuity.has_full_continuity else 0.5,
                timestamp=datetime.now(),
                details={
                    "setup": "Inside bar - waiting for breakout below low",
                    "continuity": continuity.get_summary()
                }
            )

        return None

    def _detect_failed_2_setup(
        self,
        candles: List[Candle],
        timeframe: str,
        continuity: ContinuityResult
    ) -> Optional[StratSetup]:
        """
        Detect Failed 2 setup.

        Failed 2U: Broke higher (2U) but closed bearish - trapped buyers
        Failed 2D: Broke lower (2D) but closed bullish - trapped sellers
        """
        if len(candles) < 2:
            return None

        current = candles[-1]
        previous = candles[-2]

        scenario = self.scenario_detector.detect_scenario(current, previous)

        # Failed 2U: Made higher high but closed bearish
        if scenario.scenario == Scenario.SCENARIO_2_UP and current.is_bearish:
            # Only trade if continuity supports short
            if continuity.is_ftfc_down or continuity.bearish_count >= continuity.bullish_count:
                return StratSetup(
                    setup_type=SetupType.FAILED_2U,
                    direction="SHORT",
                    entry_price=current.low,  # Break below the failed 2U
                    stop_loss=current.high,  # Above the failed breakout high
                    target=previous.low,  # Target previous low
                    timeframe=timeframe,
                    scenario=scenario,
                    confidence=0.8,  # Failed 2s are high-probability
                    timestamp=datetime.now(),
                    details={
                        "setup": "Failed 2U - buyers trapped, expecting reversal down",
                        "trapped_at": current.high,
                        "continuity": continuity.get_summary()
                    }
                )

        # Failed 2D: Made lower low but closed bullish
        if scenario.scenario == Scenario.SCENARIO_2_DOWN and current.is_bullish:
            # Only trade if continuity supports long
            if continuity.is_ftfc_up or continuity.bullish_count >= continuity.bearish_count:
                return StratSetup(
                    setup_type=SetupType.FAILED_2D,
                    direction="LONG",
                    entry_price=current.high,  # Break above the failed 2D
                    stop_loss=current.low,  # Below the failed breakdown low
                    target=previous.high,  # Target previous high
                    timeframe=timeframe,
                    scenario=scenario,
                    confidence=0.8,  # Failed 2s are high-probability
                    timestamp=datetime.now(),
                    details={
                        "setup": "Failed 2D - sellers trapped, expecting reversal up",
                        "trapped_at": current.low,
                        "continuity": continuity.get_summary()
                    }
                )

        return None

    def _detect_reversal_setup(
        self,
        candles: List[Candle],
        timeframe: str,
        continuity: ContinuityResult
    ) -> Optional[StratSetup]:
        """
        Detect 2-2 Reversal setup.

        2U-2D: Uptrend failed, reversing down
        2D-2U: Downtrend failed, reversing up
        """
        if len(candles) < 3:
            return None

        current = candles[-1]
        previous = candles[-2]
        before = candles[-3]

        prev_scenario = self.scenario_detector.detect_scenario(previous, before)
        curr_scenario = self.scenario_detector.detect_scenario(current, previous)

        # 2U-2D: Bearish reversal
        if (prev_scenario.scenario == Scenario.SCENARIO_2_UP and
            curr_scenario.scenario == Scenario.SCENARIO_2_DOWN):

            # Confirm with continuity (or allow counter-trend for reversals)
            return StratSetup(
                setup_type=SetupType.REVERSAL_2U_2D,
                direction="SHORT",
                entry_price=current.low,
                stop_loss=previous.high,  # Above the 2U high
                target=before.low,
                timeframe=timeframe,
                scenario=curr_scenario,
                confidence=0.75,
                timestamp=datetime.now(),
                details={
                    "setup": "2U-2D Reversal - uptrend failed",
                    "reversal_high": previous.high,
                    "continuity": continuity.get_summary()
                }
            )

        # 2D-2U: Bullish reversal
        if (prev_scenario.scenario == Scenario.SCENARIO_2_DOWN and
            curr_scenario.scenario == Scenario.SCENARIO_2_UP):

            return StratSetup(
                setup_type=SetupType.REVERSAL_2D_2U,
                direction="LONG",
                entry_price=current.high,
                stop_loss=previous.low,  # Below the 2D low
                target=before.high,
                timeframe=timeframe,
                scenario=curr_scenario,
                confidence=0.75,
                timestamp=datetime.now(),
                details={
                    "setup": "2D-2U Reversal - downtrend failed",
                    "reversal_low": previous.low,
                    "continuity": continuity.get_summary()
                }
            )

        return None

    def analyze(
        self,
        current_price: float,
        indicators: Dict[str, float] = None
    ) -> TradingSignal:
        """
        Analyze market and generate trading signal.

        Args:
            current_price: Current market price
            indicators: Optional indicators (not used - TheStrat is pure price action)

        Returns:
            TradingSignal based on TheStrat analysis
        """
        reasons = []

        # Get continuity analysis
        continuity = self.continuity_analyzer.analyze_continuity(current_price)
        reasons.append(f"Continuity: {continuity.get_summary()}")

        # Check if we should trade at all
        # Rule: Don't trade during Scenario 1 on higher timeframes (chop)
        direction, alignment = self.continuity_analyzer.get_combined_direction()

        if direction == "NEUTRAL":
            reasons.append("Market is neutral/mixed - waiting for clarity")
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                confidence=0.3,
                price=current_price,
                timestamp=datetime.now(),
                strategy=self.name,
                reasons=reasons
            )

        # Detect setups on primary timeframe
        primary_tf = self.config.get("primary_timeframe", "D")
        setups = self.detect_setups(primary_tf)

        if not setups:
            reasons.append(f"No setups on {primary_tf} timeframe")
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                confidence=0.4,
                price=current_price,
                timestamp=datetime.now(),
                strategy=self.name,
                reasons=reasons
            )

        # Find best setup aligned with continuity
        best_setup = None
        for setup in setups:
            # Filter: Only trade setups aligned with continuity
            if self.require_ftfc:
                if setup.direction == "LONG" and not continuity.is_ftfc_up:
                    continue
                if setup.direction == "SHORT" and not continuity.is_ftfc_down:
                    continue
            else:
                if setup.direction == "LONG" and continuity.bearish_count > continuity.bullish_count:
                    continue
                if setup.direction == "SHORT" and continuity.bullish_count > continuity.bearish_count:
                    continue

            # Prioritize Failed 2s (highest probability per the PDF)
            if best_setup is None:
                best_setup = setup
            elif setup.setup_type in (SetupType.FAILED_2U, SetupType.FAILED_2D):
                if best_setup.setup_type not in (SetupType.FAILED_2U, SetupType.FAILED_2D):
                    best_setup = setup
            elif setup.confidence > best_setup.confidence:
                best_setup = setup

        if best_setup is None:
            reasons.append("No setups aligned with timeframe continuity")
            return TradingSignal(
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                confidence=0.4,
                price=current_price,
                timestamp=datetime.now(),
                strategy=self.name,
                reasons=reasons
            )

        # Generate signal from best setup
        reasons.append(f"Setup: {best_setup.setup_type.value}")
        reasons.append(f"Entry: {best_setup.entry_price:.2f}, Stop: {best_setup.stop_loss:.2f}")

        if best_setup.details:
            reasons.append(best_setup.details.get("setup", ""))

        # Convert setup to signal
        if best_setup.direction == "LONG":
            # Check if price has triggered entry
            if current_price >= best_setup.entry_price:
                signal_type = SignalType.BUY
                strength = SignalStrength.STRONG if continuity.has_full_continuity else SignalStrength.MODERATE
            else:
                signal_type = SignalType.HOLD
                strength = SignalStrength.WEAK
                reasons.append(f"Waiting for break above {best_setup.entry_price:.2f}")

        else:  # SHORT
            if current_price <= best_setup.entry_price:
                signal_type = SignalType.SELL
                strength = SignalStrength.STRONG if continuity.has_full_continuity else SignalStrength.MODERATE
            else:
                signal_type = SignalType.HOLD
                strength = SignalStrength.WEAK
                reasons.append(f"Waiting for break below {best_setup.entry_price:.2f}")

        # Check for exit conditions if in position
        if self.position == "long":
            # Exit on Scenario 3 down or FTFC reversal
            if continuity.is_ftfc_down:
                signal_type = SignalType.SELL
                strength = SignalStrength.STRONG
                reasons.append("FTFC reversed DOWN - exit long")
            elif current_price < self.entry_price * 0.98:  # 2% stop
                signal_type = SignalType.SELL
                strength = SignalStrength.MODERATE
                reasons.append("Stop loss triggered")

        elif self.position == "short":
            # Exit on Scenario 3 up or FTFC reversal
            if continuity.is_ftfc_up:
                signal_type = SignalType.BUY
                strength = SignalStrength.STRONG
                reasons.append("FTFC reversed UP - exit short")
            elif current_price > self.entry_price * 1.02:  # 2% stop
                signal_type = SignalType.BUY
                strength = SignalStrength.MODERATE
                reasons.append("Stop loss triggered")

        return TradingSignal(
            signal_type=signal_type,
            strength=strength,
            confidence=best_setup.confidence,
            price=current_price,
            timestamp=datetime.now(),
            strategy=self.name,
            reasons=reasons,
            metadata={
                "setup": best_setup.setup_type.value,
                "direction": best_setup.direction,
                "entry": best_setup.entry_price,
                "stop": best_setup.stop_loss,
                "target": best_setup.target,
                "continuity": continuity.ftfc_direction,
                "ftfc": continuity.has_full_continuity
            }
        )

    def get_active_setups(self) -> List[StratSetup]:
        """Get currently active setups."""
        return self._active_setups

    def get_continuity_status(self) -> ContinuityResult:
        """Get current timeframe continuity status."""
        return self.continuity_analyzer.analyze_continuity()

    def reset(self):
        """Reset strategy state."""
        super().reset()
        self._candle_history.clear()
        self._active_setups.clear()
        self._swing_highs.clear()
        self._swing_lows.clear()
        self.continuity_analyzer.reset()
