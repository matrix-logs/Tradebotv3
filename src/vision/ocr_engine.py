"""
OCR Engine for extracting text from trading platform screenshots.
Supports both Tesseract and EasyOCR backends.
"""

import re
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

# Try to import OCR libraries
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False


class OCRResult:
    """Represents an OCR detection result."""

    def __init__(
        self,
        text: str,
        confidence: float,
        bbox: Optional[Tuple[int, int, int, int]] = None
    ):
        self.text = text
        self.confidence = confidence
        self.bbox = bbox  # (x, y, width, height)

    def __repr__(self):
        return f"OCRResult('{self.text}', conf={self.confidence:.2f})"


class OCREngine:
    """
    Unified OCR engine supporting multiple backends.
    Optimized for reading numbers and prices from trading screens.
    """

    def __init__(
        self,
        engine: str = "easyocr",
        language: str = "en",
        gpu: bool = False
    ):
        """
        Initialize the OCR engine.

        Args:
            engine: "easyocr" or "tesseract"
            language: Language code
            gpu: Whether to use GPU acceleration (EasyOCR only)
        """
        self.engine_name = engine
        self.language = language

        if engine == "easyocr":
            if not HAS_EASYOCR:
                raise ImportError("EasyOCR not installed. Run: pip install easyocr")
            self._reader = easyocr.Reader([language], gpu=gpu)
        elif engine == "tesseract":
            if not HAS_TESSERACT:
                raise ImportError("pytesseract not installed. Run: pip install pytesseract")
            # Tesseract config for numbers
            self._tesseract_config = "--psm 7 -c tessedit_char_whitelist=0123456789.,-$"
        else:
            raise ValueError(f"Unknown OCR engine: {engine}")

    def read_text(
        self,
        image: np.ndarray,
        detail: bool = True
    ) -> List[OCRResult]:
        """
        Read all text from an image.

        Args:
            image: Input image as NumPy array
            detail: Whether to include bounding boxes

        Returns:
            List of OCRResult objects
        """
        if self.engine_name == "easyocr":
            return self._read_easyocr(image, detail)
        else:
            return self._read_tesseract(image, detail)

    def _read_easyocr(
        self,
        image: np.ndarray,
        detail: bool
    ) -> List[OCRResult]:
        """Read text using EasyOCR."""
        results = self._reader.readtext(image, detail=1)

        ocr_results = []
        for detection in results:
            bbox, text, confidence = detection

            # Convert bbox from points to (x, y, w, h)
            if bbox:
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                x, y = min(x_coords), min(y_coords)
                w, h = max(x_coords) - x, max(y_coords) - y
                bbox_rect = (int(x), int(y), int(w), int(h))
            else:
                bbox_rect = None

            ocr_results.append(OCRResult(
                text=text,
                confidence=confidence,
                bbox=bbox_rect if detail else None
            ))

        return ocr_results

    def _read_tesseract(
        self,
        image: np.ndarray,
        detail: bool
    ) -> List[OCRResult]:
        """Read text using Tesseract."""
        # Get detailed output
        data = pytesseract.image_to_data(
            image,
            config=self._tesseract_config,
            output_type=pytesseract.Output.DICT
        )

        ocr_results = []
        n_boxes = len(data["text"])

        for i in range(n_boxes):
            text = data["text"][i].strip()
            if not text:
                continue

            confidence = float(data["conf"][i]) / 100.0
            if confidence < 0:
                confidence = 0

            bbox = None
            if detail:
                bbox = (
                    data["left"][i],
                    data["top"][i],
                    data["width"][i],
                    data["height"][i]
                )

            ocr_results.append(OCRResult(
                text=text,
                confidence=confidence,
                bbox=bbox
            ))

        return ocr_results

    def read_number(
        self,
        image: np.ndarray,
        allow_negative: bool = True,
        allow_decimals: bool = True
    ) -> Optional[Tuple[float, float]]:
        """
        Read a single number from an image.

        Args:
            image: Input image containing a number
            allow_negative: Whether to allow negative numbers
            allow_decimals: Whether to allow decimal numbers

        Returns:
            Tuple of (number, confidence) or None if no number found
        """
        results = self.read_text(image, detail=False)

        if not results:
            return None

        # Combine all text and find numbers
        all_text = " ".join(r.text for r in results)

        # Clean up common OCR errors in numbers
        all_text = all_text.replace("O", "0").replace("o", "0")
        all_text = all_text.replace("l", "1").replace("I", "1")
        all_text = all_text.replace(",", "")  # Remove thousand separators
        all_text = all_text.replace(" ", "")

        # Build regex pattern
        if allow_decimals:
            if allow_negative:
                pattern = r"-?\d+\.?\d*"
            else:
                pattern = r"\d+\.?\d*"
        else:
            if allow_negative:
                pattern = r"-?\d+"
            else:
                pattern = r"\d+"

        matches = re.findall(pattern, all_text)

        if not matches:
            return None

        # Take the first (or largest) number found
        try:
            number = float(matches[0])
            avg_confidence = sum(r.confidence for r in results) / len(results)
            return (number, avg_confidence)
        except ValueError:
            return None

    def read_price(
        self,
        image: np.ndarray
    ) -> Optional[Tuple[float, float]]:
        """
        Read a price value from an image.
        Handles currency symbols and formatting.

        Args:
            image: Input image containing a price

        Returns:
            Tuple of (price, confidence) or None
        """
        results = self.read_text(image, detail=False)

        if not results:
            return None

        all_text = " ".join(r.text for r in results)

        # Remove currency symbols
        all_text = re.sub(r"[$\u00A3\u20AC\u00A5]", "", all_text)

        # Clean up
        all_text = all_text.replace(",", "").replace(" ", "")
        all_text = all_text.replace("O", "0").replace("o", "0")
        all_text = all_text.replace("l", "1").replace("I", "1")

        # Find price pattern (including pips notation like 1.23456)
        matches = re.findall(r"\d+\.?\d*", all_text)

        if not matches:
            return None

        try:
            # Take the most likely price (often the largest number)
            prices = [float(m) for m in matches if m]
            if not prices:
                return None

            price = max(prices)  # Usually the main price is larger
            avg_confidence = sum(r.confidence for r in results) / len(results)
            return (price, avg_confidence)
        except ValueError:
            return None

    def read_bid_ask(
        self,
        image: np.ndarray
    ) -> Optional[Dict[str, Tuple[float, float]]]:
        """
        Read bid and ask prices from an image.

        Args:
            image: Input image containing bid/ask display

        Returns:
            Dict with 'bid' and 'ask' tuples of (price, confidence)
        """
        results = self.read_text(image, detail=True)

        if len(results) < 2:
            return None

        # Sort results by x position (left = bid, right = ask typically)
        results_with_bbox = [r for r in results if r.bbox]

        if len(results_with_bbox) < 2:
            return None

        sorted_results = sorted(results_with_bbox, key=lambda r: r.bbox[0])

        # Extract numbers from sorted results
        numbers = []
        for result in sorted_results:
            text = result.text.replace(",", "").replace("$", "")
            try:
                num = float(text)
                numbers.append((num, result.confidence))
            except ValueError:
                continue

        if len(numbers) < 2:
            return None

        # Bid is usually lower, Ask is higher
        if numbers[0][0] < numbers[1][0]:
            return {"bid": numbers[0], "ask": numbers[1]}
        else:
            return {"bid": numbers[1], "ask": numbers[0]}


class NumberReader:
    """Specialized reader for extracting numbers quickly."""

    def __init__(self):
        # Use tesseract for fast number reading
        if HAS_TESSERACT:
            self.engine = "tesseract"
        elif HAS_EASYOCR:
            self.engine = "easyocr"
            self._reader = easyocr.Reader(["en"], gpu=False)
        else:
            raise ImportError("No OCR engine available")

    def read(self, image: np.ndarray) -> Optional[float]:
        """Quick number read from image."""
        if self.engine == "tesseract":
            config = "--psm 7 -c tessedit_char_whitelist=0123456789.,-"
            text = pytesseract.image_to_string(image, config=config)
        else:
            results = self._reader.readtext(image, detail=0)
            text = " ".join(results)

        # Clean and extract number
        text = text.replace(",", "").replace(" ", "").strip()
        text = text.replace("O", "0").replace("o", "0")
        text = text.replace("l", "1").replace("I", "1")

        match = re.search(r"-?\d+\.?\d*", text)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass

        return None
