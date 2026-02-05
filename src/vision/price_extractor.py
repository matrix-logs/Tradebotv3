"""
Price extraction module that combines screen capture, processing, and OCR.
Provides a high-level interface for getting prices from the screen.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..capture.screen_capture import ScreenCapture
from .image_processor import ImageProcessor, TradingScreenProcessor
from .ocr_engine import OCREngine


@dataclass
class PriceReading:
    """Represents a price reading from the screen."""
    value: float
    confidence: float
    timestamp: datetime
    region: str
    raw_text: str = ""

    @property
    def is_reliable(self) -> bool:
        """Check if reading is reliable enough to use."""
        return self.confidence >= 0.7


@dataclass
class MarketSnapshot:
    """Complete market data snapshot from screen."""
    timestamp: datetime
    price: Optional[PriceReading] = None
    bid: Optional[PriceReading] = None
    ask: Optional[PriceReading] = None
    spread: Optional[float] = None
    indicators: Dict[str, float] = None

    def __post_init__(self):
        if self.indicators is None:
            self.indicators = {}

        # Calculate spread if bid/ask available
        if self.bid and self.ask and self.spread is None:
            self.spread = self.ask.value - self.bid.value


class PriceExtractor:
    """
    High-level price extraction from trading platform screens.
    Coordinates capture, processing, and OCR.
    """

    def __init__(
        self,
        ocr_engine: str = "easyocr",
        monitor: int = 0,
        preprocessing: bool = True
    ):
        """
        Initialize the price extractor.

        Args:
            ocr_engine: OCR backend to use
            monitor: Monitor index for capture
            preprocessing: Whether to preprocess images
        """
        self.capture = ScreenCapture(monitor=monitor)
        self.ocr = OCREngine(engine=ocr_engine)
        self.processor = ImageProcessor() if preprocessing else None
        self.trading_processor = TradingScreenProcessor()

        # Caching for performance
        self._last_readings: Dict[str, PriceReading] = {}
        self._reading_times: Dict[str, float] = {}

    def extract_price(
        self,
        region: Tuple[int, int, int, int],
        region_name: str = "price",
        min_interval: float = 0.1
    ) -> Optional[PriceReading]:
        """
        Extract price from a screen region.

        Args:
            region: (x, y, width, height) of the region
            region_name: Name identifier for this region
            min_interval: Minimum seconds between readings (for caching)

        Returns:
            PriceReading or None if extraction failed
        """
        # Check cache
        now = time.time()
        if region_name in self._reading_times:
            if now - self._reading_times[region_name] < min_interval:
                return self._last_readings.get(region_name)

        # Capture region
        x, y, width, height = region
        image = self.capture.capture_region(x, y, width, height)

        # Preprocess for price display
        processed = self.trading_processor.process_price_display(image)

        # Extract price
        result = self.ocr.read_price(processed)

        if result is None:
            return None

        price, confidence = result

        reading = PriceReading(
            value=price,
            confidence=confidence,
            timestamp=datetime.now(),
            region=region_name
        )

        # Update cache
        self._last_readings[region_name] = reading
        self._reading_times[region_name] = now

        return reading

    def extract_bid_ask(
        self,
        region: Tuple[int, int, int, int]
    ) -> Tuple[Optional[PriceReading], Optional[PriceReading]]:
        """
        Extract bid and ask prices from a region.

        Args:
            region: (x, y, width, height) of the bid/ask display

        Returns:
            Tuple of (bid_reading, ask_reading)
        """
        x, y, width, height = region
        image = self.capture.capture_region(x, y, width, height)

        # Process image
        processed = self.trading_processor.process_price_display(image)

        # Extract bid/ask
        result = self.ocr.read_bid_ask(processed)

        if result is None:
            return (None, None)

        timestamp = datetime.now()

        bid_reading = PriceReading(
            value=result["bid"][0],
            confidence=result["bid"][1],
            timestamp=timestamp,
            region="bid"
        )

        ask_reading = PriceReading(
            value=result["ask"][0],
            confidence=result["ask"][1],
            timestamp=timestamp,
            region="ask"
        )

        return (bid_reading, ask_reading)

    def extract_indicator(
        self,
        region: Tuple[int, int, int, int],
        indicator_name: str = "indicator"
    ) -> Optional[PriceReading]:
        """
        Extract an indicator value from the screen.

        Args:
            region: Screen region containing the indicator value
            indicator_name: Name of the indicator

        Returns:
            PriceReading with the indicator value
        """
        x, y, width, height = region
        image = self.capture.capture_region(x, y, width, height)

        # Process for indicator display
        processed = self.trading_processor.process_indicator(image)

        # Extract number
        result = self.ocr.read_number(processed)

        if result is None:
            return None

        value, confidence = result

        return PriceReading(
            value=value,
            confidence=confidence,
            timestamp=datetime.now(),
            region=indicator_name
        )

    def get_market_snapshot(
        self,
        regions: Dict[str, Dict]
    ) -> MarketSnapshot:
        """
        Get a complete market snapshot from configured regions.

        Args:
            regions: Dict of region configurations from settings

        Returns:
            MarketSnapshot with all available data
        """
        snapshot = MarketSnapshot(timestamp=datetime.now())

        for name, config in regions.items():
            if not config.get("enabled", False):
                continue

            coords = tuple(config.get("coords", [0, 0, 100, 50]))
            region_type = config.get("type", "price")

            try:
                if region_type == "price":
                    snapshot.price = self.extract_price(coords, name)

                elif region_type == "bid_ask":
                    bid, ask = self.extract_bid_ask(coords)
                    snapshot.bid = bid
                    snapshot.ask = ask

                elif region_type == "indicator":
                    indicator_name = config.get("name", name)
                    reading = self.extract_indicator(coords, indicator_name)
                    if reading:
                        snapshot.indicators[indicator_name] = reading.value

            except Exception as e:
                # Log but continue with other regions
                print(f"Error extracting {name}: {e}")
                continue

        return snapshot

    def get_candle_analysis(
        self,
        region: Tuple[int, int, int, int]
    ) -> Dict:
        """
        Analyze candle colors in a chart region.

        Args:
            region: Screen region containing candles

        Returns:
            Analysis dict with bullish/bearish ratios
        """
        x, y, width, height = region
        image = self.capture.capture_region(x, y, width, height)

        # Convert BGRA to RGB
        if image.shape[2] == 4:
            import cv2
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)

        return self.trading_processor.extract_candle_colors(image)

    def validate_price(
        self,
        price: float,
        expected_range: Tuple[float, float] = None,
        max_change_percent: float = 10.0
    ) -> bool:
        """
        Validate a price reading for sanity.

        Args:
            price: Price to validate
            expected_range: Optional (min, max) expected range
            max_change_percent: Max allowed change from last reading

        Returns:
            True if price seems valid
        """
        if price <= 0:
            return False

        if expected_range:
            if price < expected_range[0] or price > expected_range[1]:
                return False

        # Check against last reading
        last = self._last_readings.get("price")
        if last and last.value > 0:
            change_percent = abs((price - last.value) / last.value) * 100
            if change_percent > max_change_percent:
                return False

        return True

    def close(self):
        """Clean up resources."""
        self.capture.close()
