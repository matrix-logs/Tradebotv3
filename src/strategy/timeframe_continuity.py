"""
Timeframe Continuity (TFC) Analyzer

Implements Full Timeframe Continuity (FTFC) analysis from TheStrat.

The Second Universal Truth:
"Across multiple timeframes, price moves in the direction of the most Scenario 2s."

When all timeframes align (all green = bullish, all red = bearish),
you have PROOF of directional conviction, not just a guess.

Timeframes typically analyzed:
- Trading: Monthly (M), Weekly (W), Daily (D), 60-minute (60)
- Investing: Yearly (Y), Quarterly (Q), Monthly (M), Weekly (W)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .scenario_detector import Candle, Scenario, ScenarioDetector, ScenarioResult


class TimeframeBias(Enum):
    """Directional bias for a timeframe."""
    BULLISH = "bullish"    # Green - buyers winning
    BEARISH = "bearish"    # Red - sellers winning
    NEUTRAL = "neutral"    # Inside bar or unclear


@dataclass
class TimeframeState:
    """State of a single timeframe."""
    timeframe: str
    bias: TimeframeBias
    scenario: Optional[Scenario]
    candle: Optional[Candle]
    above_open: bool  # Price above timeframe open
    distance_from_open: float  # Percentage from open
    timestamp: datetime

    @property
    def is_bullish(self) -> bool:
        return self.bias == TimeframeBias.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.bias == TimeframeBias.BEARISH

    def __repr__(self):
        symbol = "+" if self.is_bullish else "-" if self.is_bearish else "="
        return f"{self.timeframe}:{symbol}"


@dataclass
class ContinuityResult:
    """Result of timeframe continuity analysis."""
    timestamp: datetime
    timeframe_states: Dict[str, TimeframeState]
    ftfc_direction: str  # "UP", "DOWN", or "MIXED"
    ftfc_strength: float  # 0-1, how aligned are timeframes
    aligned_count: int  # Number of aligned timeframes
    total_count: int  # Total timeframes analyzed
    bullish_count: int
    bearish_count: int
    is_ftfc_up: bool  # Full Timeframe Continuity UP
    is_ftfc_down: bool  # Full Timeframe Continuity DOWN

    @property
    def has_full_continuity(self) -> bool:
        """True if all timeframes align in one direction."""
        return self.is_ftfc_up or self.is_ftfc_down

    @property
    def alignment_ratio(self) -> float:
        """Ratio of aligned timeframes (0-1)."""
        if self.total_count == 0:
            return 0
        return self.aligned_count / self.total_count

    def get_summary(self) -> str:
        """Get human-readable summary."""
        states = " ".join(str(s) for s in self.timeframe_states.values())
        if self.is_ftfc_up:
            return f"FTFC UP ({self.aligned_count}/{self.total_count}) {states}"
        elif self.is_ftfc_down:
            return f"FTFC DOWN ({self.aligned_count}/{self.total_count}) {states}"
        else:
            return f"MIXED ({self.bullish_count}↑ {self.bearish_count}↓) {states}"


class TimeframeContinuityAnalyzer:
    """
    Analyzes timeframe continuity for TheStrat.

    FTFC (Full Timeframe Continuity) is the "magic sauce" - it ensures
    you're on the right side of the market, trading only the strongest signals.

    To have FTFC UP:
    - All timeframe opens must be below current price
    - All timeframes should show bullish (green) candles or 2U scenarios

    To have FTFC DOWN:
    - All timeframe opens must be above current price
    - All timeframes should show bearish (red) candles or 2D scenarios
    """

    # Standard trading timeframes
    TRADING_TIMEFRAMES = ["60", "D", "W", "M"]  # 60min, Daily, Weekly, Monthly

    # Investing timeframes
    INVESTING_TIMEFRAMES = ["W", "M", "Q", "Y"]  # Weekly, Monthly, Quarterly, Yearly

    def __init__(
        self,
        timeframes: List[str] = None,
        scenario_detector: ScenarioDetector = None
    ):
        """
        Initialize the continuity analyzer.

        Args:
            timeframes: List of timeframes to analyze (default: trading TFs)
            scenario_detector: ScenarioDetector instance for scenario analysis
        """
        self.timeframes = timeframes or self.TRADING_TIMEFRAMES
        self.scenario_detector = scenario_detector or ScenarioDetector()

        # Store timeframe data
        self._timeframe_data: Dict[str, Dict] = {}
        # Store opens for each timeframe
        self._timeframe_opens: Dict[str, float] = {}
        # Store last candles
        self._last_candles: Dict[str, Candle] = {}
        self._prev_candles: Dict[str, Candle] = {}

    def update_timeframe(
        self,
        timeframe: str,
        candle: Candle,
        tf_open: float = None
    ):
        """
        Update data for a specific timeframe.

        Args:
            timeframe: Timeframe identifier (e.g., "D", "W", "M")
            candle: Latest candle for this timeframe
            tf_open: Opening price of this timeframe period
        """
        # Store previous candle
        if timeframe in self._last_candles:
            self._prev_candles[timeframe] = self._last_candles[timeframe]

        self._last_candles[timeframe] = candle

        # Update timeframe open (if provided or use candle open)
        if tf_open is not None:
            self._timeframe_opens[timeframe] = tf_open
        elif timeframe not in self._timeframe_opens:
            self._timeframe_opens[timeframe] = candle.open

    def update_from_ohlc(
        self,
        timeframe: str,
        ohlc: Tuple[float, float, float, float],
        tf_open: float = None,
        timestamp: datetime = None
    ):
        """
        Update timeframe from OHLC tuple.

        Args:
            timeframe: Timeframe identifier
            ohlc: (open, high, low, close) tuple
            tf_open: Period opening price
            timestamp: Candle timestamp
        """
        candle = Candle(
            timestamp=timestamp or datetime.now(),
            open=ohlc[0],
            high=ohlc[1],
            low=ohlc[2],
            close=ohlc[3],
            timeframe=timeframe
        )
        self.update_timeframe(timeframe, candle, tf_open)

    def get_timeframe_state(
        self,
        timeframe: str,
        current_price: float = None
    ) -> Optional[TimeframeState]:
        """
        Get the current state of a timeframe.

        Args:
            timeframe: Timeframe to analyze
            current_price: Current market price (uses candle close if not provided)

        Returns:
            TimeframeState or None if no data
        """
        if timeframe not in self._last_candles:
            return None

        candle = self._last_candles[timeframe]
        price = current_price or candle.close

        # Get timeframe open
        tf_open = self._timeframe_opens.get(timeframe, candle.open)

        # Determine if price is above/below the open
        above_open = price > tf_open
        distance_from_open = ((price - tf_open) / tf_open * 100) if tf_open > 0 else 0

        # Get scenario if we have previous candle
        scenario = None
        if timeframe in self._prev_candles:
            result = self.scenario_detector.detect_scenario(
                candle, self._prev_candles[timeframe]
            )
            scenario = result.scenario

        # Determine bias
        # Primary: Is candle bullish or bearish?
        # Secondary: Is price above or below timeframe open?
        if candle.is_bullish and above_open:
            bias = TimeframeBias.BULLISH
        elif candle.is_bearish and not above_open:
            bias = TimeframeBias.BEARISH
        elif above_open:
            # Price above open but candle is bearish - still bullish bias but weaker
            bias = TimeframeBias.BULLISH
        elif not above_open:
            # Price below open but candle is bullish - still bearish bias but weaker
            bias = TimeframeBias.BEARISH
        else:
            bias = TimeframeBias.NEUTRAL

        return TimeframeState(
            timeframe=timeframe,
            bias=bias,
            scenario=scenario,
            candle=candle,
            above_open=above_open,
            distance_from_open=distance_from_open,
            timestamp=datetime.now()
        )

    def analyze_continuity(
        self,
        current_price: float = None
    ) -> ContinuityResult:
        """
        Analyze timeframe continuity across all configured timeframes.

        Args:
            current_price: Current market price

        Returns:
            ContinuityResult with full analysis
        """
        states = {}
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0

        for tf in self.timeframes:
            state = self.get_timeframe_state(tf, current_price)
            if state:
                states[tf] = state
                if state.is_bullish:
                    bullish_count += 1
                elif state.is_bearish:
                    bearish_count += 1
                else:
                    neutral_count += 1

        total = len(states)

        # Determine FTFC status
        is_ftfc_up = (bullish_count == total and total > 0)
        is_ftfc_down = (bearish_count == total and total > 0)

        # Determine direction and strength
        if is_ftfc_up:
            direction = "UP"
            aligned_count = bullish_count
            strength = 1.0
        elif is_ftfc_down:
            direction = "DOWN"
            aligned_count = bearish_count
            strength = 1.0
        else:
            direction = "MIXED"
            aligned_count = max(bullish_count, bearish_count)
            strength = aligned_count / total if total > 0 else 0

        return ContinuityResult(
            timestamp=datetime.now(),
            timeframe_states=states,
            ftfc_direction=direction,
            ftfc_strength=strength,
            aligned_count=aligned_count,
            total_count=total,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            is_ftfc_up=is_ftfc_up,
            is_ftfc_down=is_ftfc_down
        )

    def check_entry_allowed(
        self,
        direction: str,  # "LONG" or "SHORT"
        min_alignment: float = 0.75,
        require_ftfc: bool = False
    ) -> Tuple[bool, str]:
        """
        Check if an entry is allowed based on timeframe continuity.

        Args:
            direction: Trade direction ("LONG" or "SHORT")
            min_alignment: Minimum ratio of aligned timeframes (0-1)
            require_ftfc: Whether to require full continuity

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        continuity = self.analyze_continuity()

        if require_ftfc:
            if direction == "LONG" and continuity.is_ftfc_up:
                return (True, "FTFC UP - all timeframes bullish")
            elif direction == "SHORT" and continuity.is_ftfc_down:
                return (True, "FTFC DOWN - all timeframes bearish")
            else:
                return (False, f"No FTFC for {direction} - continuity is {continuity.ftfc_direction}")

        # Check alignment ratio
        if direction == "LONG":
            ratio = continuity.bullish_count / continuity.total_count if continuity.total_count > 0 else 0
            if ratio >= min_alignment:
                return (True, f"Bullish alignment {ratio:.0%} >= {min_alignment:.0%}")
            else:
                return (False, f"Bullish alignment {ratio:.0%} < {min_alignment:.0%}")

        elif direction == "SHORT":
            ratio = continuity.bearish_count / continuity.total_count if continuity.total_count > 0 else 0
            if ratio >= min_alignment:
                return (True, f"Bearish alignment {ratio:.0%} >= {min_alignment:.0%}")
            else:
                return (False, f"Bearish alignment {ratio:.0%} < {min_alignment:.0%}")

        return (False, "Invalid direction")

    def get_scenario_alignment(self) -> Dict[str, Tuple[str, float]]:
        """
        Get scenario-based direction for each timeframe.

        Uses the rule: "Price moves in direction of most Scenario 2s"

        Returns:
            Dict of timeframe -> (direction, confidence)
        """
        result = {}

        for tf in self.timeframes:
            direction, confidence = self.scenario_detector.get_dominant_direction(tf, count=10)
            result[tf] = (direction, confidence)

        return result

    def get_combined_direction(self) -> Tuple[str, float]:
        """
        Get combined direction from all timeframes.

        Returns:
            Tuple of (direction, confidence)
        """
        continuity = self.analyze_continuity()

        if continuity.is_ftfc_up:
            return ("UP", 1.0)
        elif continuity.is_ftfc_down:
            return ("DOWN", 1.0)
        else:
            # Calculate weighted direction
            total = continuity.total_count
            if total == 0:
                return ("NEUTRAL", 0.5)

            up_ratio = continuity.bullish_count / total
            down_ratio = continuity.bearish_count / total

            if up_ratio > down_ratio:
                return ("UP", up_ratio)
            elif down_ratio > up_ratio:
                return ("DOWN", down_ratio)
            else:
                return ("NEUTRAL", 0.5)

    def set_timeframe_open(self, timeframe: str, open_price: float):
        """Set the opening price for a timeframe period."""
        self._timeframe_opens[timeframe] = open_price

    def reset(self):
        """Reset all stored data."""
        self._timeframe_data.clear()
        self._timeframe_opens.clear()
        self._last_candles.clear()
        self._prev_candles.clear()
