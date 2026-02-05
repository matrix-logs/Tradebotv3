"""
Pattern recognition for visual chart analysis.
Detects common chart patterns from screen captures.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


class PatternType(Enum):
    """Types of chart patterns."""
    # Bullish patterns
    DOUBLE_BOTTOM = "double_bottom"
    BULLISH_ENGULFING = "bullish_engulfing"
    HAMMER = "hammer"
    MORNING_STAR = "morning_star"

    # Bearish patterns
    DOUBLE_TOP = "double_top"
    BEARISH_ENGULFING = "bearish_engulfing"
    SHOOTING_STAR = "shooting_star"
    EVENING_STAR = "evening_star"

    # Neutral patterns
    DOJI = "doji"
    INSIDE_BAR = "inside_bar"

    # Trend patterns
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    CONSOLIDATION = "consolidation"


@dataclass
class PatternDetection:
    """Represents a detected chart pattern."""
    pattern_type: PatternType
    confidence: float
    timestamp: datetime
    location: Tuple[int, int, int, int]  # x, y, width, height in image
    is_bullish: bool
    metadata: Dict = None

    def __repr__(self):
        direction = "bullish" if self.is_bullish else "bearish"
        return f"Pattern({self.pattern_type.value}, {direction}, conf={self.confidence:.2f})"


class PatternRecognizer:
    """
    Recognizes chart patterns from visual analysis.
    Uses color detection and shape analysis.
    """

    def __init__(self, config: Dict = None):
        """
        Initialize pattern recognizer.

        Args:
            config: Pattern detection configuration
        """
        self.config = config or {}

        # Color definitions (BGR format for OpenCV)
        self.bullish_colors = self.config.get("bullish_colors", [
            (0, 200, 0),    # Green
            (0, 255, 0),
            (50, 205, 50),  # Lime green
        ])
        self.bearish_colors = self.config.get("bearish_colors", [
            (0, 0, 200),    # Red
            (0, 0, 255),
            (60, 60, 255),  # Light red
        ])

        self._detected_patterns: List[PatternDetection] = []

    def analyze_chart(
        self,
        image: np.ndarray
    ) -> List[PatternDetection]:
        """
        Analyze a chart image for patterns.

        Args:
            image: Chart screenshot as numpy array

        Returns:
            List of detected patterns
        """
        patterns = []

        # Detect candle colors
        candle_analysis = self._analyze_candle_distribution(image)
        patterns.extend(candle_analysis)

        # Detect trend
        trend_pattern = self._detect_trend(image)
        if trend_pattern:
            patterns.append(trend_pattern)

        # Store patterns
        self._detected_patterns.extend(patterns)

        return patterns

    def _analyze_candle_distribution(
        self,
        image: np.ndarray
    ) -> List[PatternDetection]:
        """Analyze the distribution and pattern of candles."""
        patterns = []

        # Convert to HSV for better color detection
        if len(image.shape) == 2:
            # Grayscale, convert to BGR first
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Detect green (bullish) regions
        green_lower = np.array([35, 50, 50])
        green_upper = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)

        # Detect red (bearish) regions
        red_lower1 = np.array([0, 50, 50])
        red_upper1 = np.array([10, 255, 255])
        red_lower2 = np.array([170, 50, 50])
        red_upper2 = np.array([180, 255, 255])
        red_mask = cv2.inRange(hsv, red_lower1, red_upper1) | \
                   cv2.inRange(hsv, red_lower2, red_upper2)

        # Find contours for each color
        green_contours, _ = cv2.findContours(
            green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        red_contours, _ = cv2.findContours(
            red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Count and analyze candles
        green_candles = self._filter_candle_contours(green_contours)
        red_candles = self._filter_candle_contours(red_contours)

        total_candles = len(green_candles) + len(red_candles)

        if total_candles == 0:
            return patterns

        green_ratio = len(green_candles) / total_candles

        # Detect engulfing patterns (looking at the rightmost candles)
        if green_candles and red_candles:
            # Sort by x position (rightmost = most recent)
            all_candles = [
                (c, True) for c in green_candles
            ] + [
                (c, False) for c in red_candles
            ]
            all_candles.sort(key=lambda x: cv2.boundingRect(x[0])[0], reverse=True)

            if len(all_candles) >= 2:
                current_candle, current_bullish = all_candles[0]
                prev_candle, prev_bullish = all_candles[1]

                current_rect = cv2.boundingRect(current_candle)
                prev_rect = cv2.boundingRect(prev_candle)

                # Check for engulfing (current larger than previous)
                if current_rect[3] > prev_rect[3] * 1.2:  # Height comparison
                    if current_bullish and not prev_bullish:
                        patterns.append(PatternDetection(
                            pattern_type=PatternType.BULLISH_ENGULFING,
                            confidence=0.7,
                            timestamp=datetime.now(),
                            location=current_rect,
                            is_bullish=True,
                            metadata={"green_ratio": green_ratio}
                        ))
                    elif not current_bullish and prev_bullish:
                        patterns.append(PatternDetection(
                            pattern_type=PatternType.BEARISH_ENGULFING,
                            confidence=0.7,
                            timestamp=datetime.now(),
                            location=current_rect,
                            is_bullish=False,
                            metadata={"green_ratio": green_ratio}
                        ))

        # Detect overall sentiment
        if green_ratio > 0.7:
            patterns.append(PatternDetection(
                pattern_type=PatternType.UPTREND,
                confidence=green_ratio,
                timestamp=datetime.now(),
                location=(0, 0, image.shape[1], image.shape[0]),
                is_bullish=True,
                metadata={"green_candles": len(green_candles), "red_candles": len(red_candles)}
            ))
        elif green_ratio < 0.3:
            patterns.append(PatternDetection(
                pattern_type=PatternType.DOWNTREND,
                confidence=1 - green_ratio,
                timestamp=datetime.now(),
                location=(0, 0, image.shape[1], image.shape[0]),
                is_bullish=False,
                metadata={"green_candles": len(green_candles), "red_candles": len(red_candles)}
            ))
        else:
            patterns.append(PatternDetection(
                pattern_type=PatternType.CONSOLIDATION,
                confidence=0.5,
                timestamp=datetime.now(),
                location=(0, 0, image.shape[1], image.shape[0]),
                is_bullish=True,  # Neutral
                metadata={"green_candles": len(green_candles), "red_candles": len(red_candles)}
            ))

        return patterns

    def _filter_candle_contours(
        self,
        contours,
        min_area: int = 50,
        min_height: int = 10
    ) -> List:
        """Filter contours to keep only candle-like shapes."""
        candles = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            if h < min_height:
                continue

            # Candles are typically taller than wide
            aspect_ratio = h / w if w > 0 else 0
            if aspect_ratio < 0.5:  # Too wide for a candle
                continue

            candles.append(contour)

        return candles

    def _detect_trend(self, image: np.ndarray) -> Optional[PatternDetection]:
        """Detect overall trend direction using edge detection."""
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Apply edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find lines using Hough transform
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=50,
            minLineLength=30, maxLineGap=10
        )

        if lines is None or len(lines) < 3:
            return None

        # Analyze line slopes
        slopes = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 != 0:
                slope = (y2 - y1) / (x2 - x1)
                # Filter out near-vertical lines
                if abs(slope) < 10:
                    slopes.append(slope)

        if not slopes:
            return None

        avg_slope = np.mean(slopes)

        # Negative slope = uptrend (y decreases as x increases in screen coords)
        # Positive slope = downtrend
        if avg_slope < -0.1:
            return PatternDetection(
                pattern_type=PatternType.UPTREND,
                confidence=min(0.9, abs(avg_slope)),
                timestamp=datetime.now(),
                location=(0, 0, image.shape[1], image.shape[0]),
                is_bullish=True,
                metadata={"avg_slope": avg_slope}
            )
        elif avg_slope > 0.1:
            return PatternDetection(
                pattern_type=PatternType.DOWNTREND,
                confidence=min(0.9, abs(avg_slope)),
                timestamp=datetime.now(),
                location=(0, 0, image.shape[1], image.shape[0]),
                is_bullish=False,
                metadata={"avg_slope": avg_slope}
            )

        return None

    def get_trading_bias(self) -> Tuple[str, float]:
        """
        Get overall trading bias from recent patterns.

        Returns:
            Tuple of (bias: "bullish"/"bearish"/"neutral", confidence)
        """
        if not self._detected_patterns:
            return ("neutral", 0.5)

        # Look at recent patterns
        recent = self._detected_patterns[-10:]

        bullish_score = sum(
            p.confidence for p in recent if p.is_bullish
        )
        bearish_score = sum(
            p.confidence for p in recent if not p.is_bullish
        )

        total = bullish_score + bearish_score
        if total == 0:
            return ("neutral", 0.5)

        if bullish_score > bearish_score * 1.5:
            return ("bullish", bullish_score / total)
        elif bearish_score > bullish_score * 1.5:
            return ("bearish", bearish_score / total)
        else:
            return ("neutral", 0.5)

    def clear_history(self):
        """Clear pattern detection history."""
        self._detected_patterns.clear()
