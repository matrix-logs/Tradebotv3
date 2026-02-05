"""
Market Condition Detector

Analyzes current market conditions to determine:
1. When to trade (favorable conditions)
2. Which strategy/approach to use
3. Position sizing adjustments
4. Risk level assessment

Based on TheStrat principles:
- Trade only with timeframe continuity
- Avoid Scenario 1 (chop) on higher timeframes
- Recognize broadening formations for targets
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .scenario_detector import Scenario, ScenarioDetector
from .timeframe_continuity import ContinuityResult, TimeframeContinuityAnalyzer


class MarketRegime(Enum):
    """Overall market regime."""
    STRONG_UPTREND = "strong_uptrend"      # FTFC UP, all green
    WEAK_UPTREND = "weak_uptrend"          # Mostly bullish but not FTFC
    STRONG_DOWNTREND = "strong_downtrend"  # FTFC DOWN, all red
    WEAK_DOWNTREND = "weak_downtrend"      # Mostly bearish but not FTFC
    CONSOLIDATION = "consolidation"        # Mixed, inside bars dominant
    REVERSAL_FORMING = "reversal_forming"  # Signs of trend change


class TradingCondition(Enum):
    """Trading condition assessment."""
    EXCELLENT = "excellent"  # FTFC aligned, clear setup
    GOOD = "good"           # Most TFs aligned, setup present
    FAIR = "fair"           # Mixed alignment, setup present
    POOR = "poor"           # Against continuity or no setup
    AVOID = "avoid"         # High chop, no edge


@dataclass
class MarketConditionResult:
    """Result of market condition analysis."""
    timestamp: datetime
    regime: MarketRegime
    condition: TradingCondition
    continuity: ContinuityResult
    dominant_scenario: str  # Most common scenario across TFs
    volatility_level: str  # "low", "medium", "high"
    recommendation: str
    long_bias: float  # 0-1, strength of bullish case
    short_bias: float  # 0-1, strength of bearish case
    details: Dict

    @property
    def should_trade(self) -> bool:
        """Whether conditions are favorable for trading."""
        return self.condition in (TradingCondition.EXCELLENT, TradingCondition.GOOD)

    @property
    def is_trending(self) -> bool:
        """Whether market is in a clear trend."""
        return self.regime in (
            MarketRegime.STRONG_UPTREND,
            MarketRegime.STRONG_DOWNTREND,
            MarketRegime.WEAK_UPTREND,
            MarketRegime.WEAK_DOWNTREND
        )

    @property
    def is_choppy(self) -> bool:
        """Whether market is choppy/consolidating."""
        return self.regime == MarketRegime.CONSOLIDATION

    def get_trade_direction(self) -> Optional[str]:
        """Get recommended trade direction or None if should avoid."""
        if not self.should_trade:
            return None
        if self.long_bias > self.short_bias:
            return "LONG"
        elif self.short_bias > self.long_bias:
            return "SHORT"
        return None


class MarketConditionDetector:
    """
    Detects and analyzes market conditions.

    Uses TheStrat principles to determine:
    - Market regime (trending vs consolidation)
    - Trading conditions (when to trade)
    - Directional bias (long vs short)
    - Risk assessment
    """

    def __init__(
        self,
        continuity_analyzer: TimeframeContinuityAnalyzer = None,
        scenario_detector: ScenarioDetector = None
    ):
        """
        Initialize the market condition detector.

        Args:
            continuity_analyzer: For timeframe continuity analysis
            scenario_detector: For scenario detection
        """
        self.scenario_detector = scenario_detector or ScenarioDetector()
        self.continuity_analyzer = continuity_analyzer or TimeframeContinuityAnalyzer(
            scenario_detector=self.scenario_detector
        )

        # Track recent conditions for change detection
        self._condition_history: List[MarketConditionResult] = []

    def analyze(
        self,
        current_price: float = None
    ) -> MarketConditionResult:
        """
        Analyze current market conditions.

        Args:
            current_price: Current market price

        Returns:
            MarketConditionResult with full analysis
        """
        # Get timeframe continuity
        continuity = self.continuity_analyzer.analyze_continuity(current_price)

        # Get scenario counts across timeframes
        scenario_counts = self._get_aggregate_scenario_counts()

        # Determine dominant scenario
        dominant_scenario = self._get_dominant_scenario(scenario_counts)

        # Determine market regime
        regime = self._determine_regime(continuity, dominant_scenario, scenario_counts)

        # Assess trading conditions
        condition = self._assess_trading_condition(continuity, regime, scenario_counts)

        # Calculate directional bias
        long_bias, short_bias = self._calculate_bias(continuity, scenario_counts)

        # Assess volatility
        volatility = self._assess_volatility(scenario_counts)

        # Generate recommendation
        recommendation = self._generate_recommendation(
            regime, condition, continuity, long_bias, short_bias
        )

        result = MarketConditionResult(
            timestamp=datetime.now(),
            regime=regime,
            condition=condition,
            continuity=continuity,
            dominant_scenario=dominant_scenario,
            volatility_level=volatility,
            recommendation=recommendation,
            long_bias=long_bias,
            short_bias=short_bias,
            details={
                "scenario_counts": scenario_counts,
                "ftfc_direction": continuity.ftfc_direction,
                "bullish_tfs": continuity.bullish_count,
                "bearish_tfs": continuity.bearish_count,
            }
        )

        # Store in history
        self._condition_history.append(result)
        if len(self._condition_history) > 100:
            self._condition_history = self._condition_history[-50:]

        return result

    def _get_aggregate_scenario_counts(self) -> Dict[str, int]:
        """Get scenario counts aggregated across all timeframes."""
        total_counts = {"1": 0, "2U": 0, "2D": 0, "3": 0}

        for tf in self.continuity_analyzer.timeframes:
            counts = self.scenario_detector.get_scenario_counts(tf, count=5)
            for key in total_counts:
                total_counts[key] += counts.get(key, 0)

        return total_counts

    def _get_dominant_scenario(self, counts: Dict[str, int]) -> str:
        """Get the most common scenario type."""
        if not counts:
            return "UNKNOWN"

        # Group 2U and 2D together as "trending"
        trending = counts.get("2U", 0) + counts.get("2D", 0)
        inside = counts.get("1", 0)
        outside = counts.get("3", 0)

        if trending >= inside and trending >= outside:
            if counts.get("2U", 0) > counts.get("2D", 0):
                return "2U"
            elif counts.get("2D", 0) > counts.get("2U", 0):
                return "2D"
            else:
                return "2"
        elif inside > outside:
            return "1"
        else:
            return "3"

    def _determine_regime(
        self,
        continuity: ContinuityResult,
        dominant_scenario: str,
        counts: Dict[str, int]
    ) -> MarketRegime:
        """Determine the current market regime."""
        # Strong trends: FTFC aligned
        if continuity.is_ftfc_up:
            return MarketRegime.STRONG_UPTREND
        elif continuity.is_ftfc_down:
            return MarketRegime.STRONG_DOWNTREND

        # Check for weak trends
        if continuity.bullish_count > continuity.bearish_count:
            if dominant_scenario in ("2U", "2"):
                return MarketRegime.WEAK_UPTREND
        elif continuity.bearish_count > continuity.bullish_count:
            if dominant_scenario in ("2D", "2"):
                return MarketRegime.WEAK_DOWNTREND

        # Check for reversal forming
        if counts.get("3", 0) > 2:  # Multiple outside bars
            return MarketRegime.REVERSAL_FORMING

        # Default to consolidation
        if dominant_scenario == "1" or counts.get("1", 0) > counts.get("2U", 0) + counts.get("2D", 0):
            return MarketRegime.CONSOLIDATION

        return MarketRegime.CONSOLIDATION

    def _assess_trading_condition(
        self,
        continuity: ContinuityResult,
        regime: MarketRegime,
        counts: Dict[str, int]
    ) -> TradingCondition:
        """Assess how favorable conditions are for trading."""
        # Excellent: FTFC + trending scenarios
        if continuity.has_full_continuity and regime in (
            MarketRegime.STRONG_UPTREND, MarketRegime.STRONG_DOWNTREND
        ):
            return TradingCondition.EXCELLENT

        # Good: Most TFs aligned + some trending
        if continuity.alignment_ratio >= 0.75:
            return TradingCondition.GOOD

        # Fair: Some alignment
        if continuity.alignment_ratio >= 0.5:
            return TradingCondition.FAIR

        # Poor: Choppy or consolidation
        if regime == MarketRegime.CONSOLIDATION:
            return TradingCondition.POOR

        # Avoid: Heavy consolidation (many Scenario 1s)
        if counts.get("1", 0) > counts.get("2U", 0) + counts.get("2D", 0) + counts.get("3", 0):
            return TradingCondition.AVOID

        return TradingCondition.FAIR

    def _calculate_bias(
        self,
        continuity: ContinuityResult,
        counts: Dict[str, int]
    ) -> Tuple[float, float]:
        """Calculate long and short bias scores (0-1)."""
        total = continuity.total_count
        if total == 0:
            return (0.5, 0.5)

        # Base bias from continuity
        long_bias = continuity.bullish_count / total
        short_bias = continuity.bearish_count / total

        # Adjust based on scenario counts
        total_2s = counts.get("2U", 0) + counts.get("2D", 0)
        if total_2s > 0:
            up_2_ratio = counts.get("2U", 0) / total_2s
            down_2_ratio = counts.get("2D", 0) / total_2s

            # Weight scenario direction
            long_bias = (long_bias + up_2_ratio) / 2
            short_bias = (short_bias + down_2_ratio) / 2

        return (long_bias, short_bias)

    def _assess_volatility(self, counts: Dict[str, int]) -> str:
        """Assess volatility level from scenario counts."""
        # High volatility: Many Scenario 3s (outside bars)
        # Low volatility: Many Scenario 1s (inside bars)
        # Medium: Mostly Scenario 2s (trending)

        total = sum(counts.values())
        if total == 0:
            return "medium"

        inside_ratio = counts.get("1", 0) / total
        outside_ratio = counts.get("3", 0) / total

        if outside_ratio > 0.3:
            return "high"
        elif inside_ratio > 0.4:
            return "low"
        else:
            return "medium"

    def _generate_recommendation(
        self,
        regime: MarketRegime,
        condition: TradingCondition,
        continuity: ContinuityResult,
        long_bias: float,
        short_bias: float
    ) -> str:
        """Generate a trading recommendation string."""
        if condition == TradingCondition.EXCELLENT:
            if regime == MarketRegime.STRONG_UPTREND:
                return "STRONG BUY - FTFC UP, all timeframes bullish. Look for inside bar breaks and add to longs."
            elif regime == MarketRegime.STRONG_DOWNTREND:
                return "STRONG SELL - FTFC DOWN, all timeframes bearish. Look for inside bar breaks and add to shorts."

        if condition == TradingCondition.GOOD:
            if long_bias > short_bias:
                return f"BUY BIAS - {continuity.bullish_count}/{continuity.total_count} TFs bullish. Wait for setup confirmation."
            else:
                return f"SELL BIAS - {continuity.bearish_count}/{continuity.total_count} TFs bearish. Wait for setup confirmation."

        if condition == TradingCondition.FAIR:
            return "MIXED - Wait for clearer alignment or trade smaller size. Failed 2s may work well here."

        if condition == TradingCondition.POOR:
            return "CAUTION - Consolidation/chop detected. Consider waiting for breakout or clarity."

        return "AVOID - No edge present. Stay flat and wait for conditions to improve."

    def get_strategy_recommendation(self) -> Dict[str, any]:
        """
        Get recommendation for which strategy approach to use.

        Returns:
            Dict with strategy recommendations
        """
        condition = self.analyze()

        recommendations = {
            "should_trade": condition.should_trade,
            "direction": condition.get_trade_direction(),
            "regime": condition.regime.value,
            "condition": condition.condition.value,
            "strategy_notes": []
        }

        # Strategy-specific recommendations based on regime
        if condition.regime in (MarketRegime.STRONG_UPTREND, MarketRegime.STRONG_DOWNTREND):
            recommendations["strategy_notes"].append(
                "Use continuation setups (inside bar breaks in trend direction)"
            )
            recommendations["strategy_notes"].append(
                "Add to winners on pullbacks that hold"
            )
            recommendations["position_sizing"] = "full"

        elif condition.regime in (MarketRegime.WEAK_UPTREND, MarketRegime.WEAK_DOWNTREND):
            recommendations["strategy_notes"].append(
                "Wait for Failed 2s or 2-2 reversals for higher probability"
            )
            recommendations["strategy_notes"].append(
                "Be quicker to take profits"
            )
            recommendations["position_sizing"] = "reduced"

        elif condition.regime == MarketRegime.CONSOLIDATION:
            recommendations["strategy_notes"].append(
                "Avoid trading inside bars - wait for breakout"
            )
            recommendations["strategy_notes"].append(
                "Watch for Scenario 3 to indicate direction"
            )
            recommendations["position_sizing"] = "minimal"

        elif condition.regime == MarketRegime.REVERSAL_FORMING:
            recommendations["strategy_notes"].append(
                "Watch for Failed 2s at extremes"
            )
            recommendations["strategy_notes"].append(
                "2-2 reversals may signal trend change"
            )
            recommendations["position_sizing"] = "reduced"

        return recommendations

    def has_condition_changed(self) -> bool:
        """Check if market condition has significantly changed."""
        if len(self._condition_history) < 2:
            return False

        current = self._condition_history[-1]
        previous = self._condition_history[-2]

        # Check for regime change
        if current.regime != previous.regime:
            return True

        # Check for condition change
        if current.condition != previous.condition:
            return True

        # Check for FTFC flip
        if current.continuity.is_ftfc_up != previous.continuity.is_ftfc_up:
            return True
        if current.continuity.is_ftfc_down != previous.continuity.is_ftfc_down:
            return True

        return False
