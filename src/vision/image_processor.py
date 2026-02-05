"""
Image preprocessing for improved OCR accuracy.
Handles contrast enhancement, denoising, and other transformations.
"""

from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


class ImageProcessor:
    """
    Preprocesses images for optimal OCR performance.
    Particularly tuned for extracting numbers from trading platforms.
    """

    def __init__(
        self,
        scale_factor: float = 2.0,
        contrast_enhance: bool = True,
        denoise: bool = True,
        grayscale: bool = True
    ):
        """
        Initialize the image processor.

        Args:
            scale_factor: Upscale factor for small text
            contrast_enhance: Whether to enhance contrast
            denoise: Whether to apply denoising
            grayscale: Whether to convert to grayscale
        """
        self.scale_factor = scale_factor
        self.contrast_enhance = contrast_enhance
        self.denoise = denoise
        self.grayscale = grayscale

    def process(self, image: np.ndarray) -> np.ndarray:
        """
        Apply full preprocessing pipeline.

        Args:
            image: Input image as NumPy array (BGR or RGB)

        Returns:
            Processed image optimized for OCR
        """
        # Convert to RGB if needed (MSS captures as BGRA)
        if image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        elif len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Upscale for better OCR on small text
        if self.scale_factor != 1.0:
            image = self._upscale(image)

        # Convert to grayscale
        if self.grayscale:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Enhance contrast
        if self.contrast_enhance:
            image = self._enhance_contrast(image)

        # Denoise
        if self.denoise:
            image = self._denoise(image)

        return image

    def _upscale(self, image: np.ndarray) -> np.ndarray:
        """Upscale image using bicubic interpolation."""
        height, width = image.shape[:2]
        new_size = (int(width * self.scale_factor), int(height * self.scale_factor))
        return cv2.resize(image, new_size, interpolation=cv2.INTER_CUBIC)

    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """Enhance image contrast using CLAHE."""
        if len(image.shape) == 2:
            # Grayscale
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(image)
        else:
            # Color image - convert to LAB and enhance L channel
            lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """Apply denoising filter."""
        if len(image.shape) == 2:
            return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
        else:
            return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)

    def binarize(
        self,
        image: np.ndarray,
        method: str = "adaptive"
    ) -> np.ndarray:
        """
        Convert image to binary (black and white).

        Args:
            image: Grayscale input image
            method: "adaptive", "otsu", or "simple"

        Returns:
            Binary image
        """
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        if method == "adaptive":
            return cv2.adaptiveThreshold(
                image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
        elif method == "otsu":
            _, binary = cv2.threshold(
                image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            return binary
        else:  # simple
            _, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
            return binary

    def invert_if_needed(self, image: np.ndarray) -> np.ndarray:
        """
        Invert image if background is darker than foreground.
        OCR typically works better with dark text on light background.
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image

        # Check if image is predominantly dark
        mean_val = np.mean(gray)
        if mean_val < 127:
            return cv2.bitwise_not(image)
        return image

    def crop_to_content(
        self,
        image: np.ndarray,
        padding: int = 5
    ) -> np.ndarray:
        """
        Crop image to content bounds with padding.

        Args:
            image: Input image
            padding: Pixels to add around content

        Returns:
            Cropped image
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image

        # Find content bounds
        coords = cv2.findNonZero(gray)
        if coords is None:
            return image

        x, y, w, h = cv2.boundingRect(coords)

        # Add padding
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)

        return image[y:y+h, x:x+w]

    def extract_text_region(
        self,
        image: np.ndarray,
        text_color: Tuple[int, int, int] = None,
        tolerance: int = 30
    ) -> np.ndarray:
        """
        Extract region containing specific text color.

        Args:
            image: Input RGB image
            text_color: Target text color (R, G, B)
            tolerance: Color matching tolerance

        Returns:
            Mask of text regions
        """
        if text_color is None:
            return image

        # Create color range
        lower = np.array([max(0, c - tolerance) for c in text_color])
        upper = np.array([min(255, c + tolerance) for c in text_color])

        # Create mask
        mask = cv2.inRange(image, lower, upper)

        # Apply mask
        result = cv2.bitwise_and(image, image, mask=mask)
        return result


class TradingScreenProcessor(ImageProcessor):
    """
    Specialized image processor for trading platform screens.
    Includes presets for common trading UI elements.
    """

    @staticmethod
    def process_price_display(image: np.ndarray) -> np.ndarray:
        """
        Process a price display area for optimal number recognition.
        """
        processor = ImageProcessor(
            scale_factor=3.0,
            contrast_enhance=True,
            denoise=True,
            grayscale=True
        )

        processed = processor.process(image)
        processed = processor.invert_if_needed(processed)
        processed = processor.binarize(processed, method="adaptive")

        return processed

    @staticmethod
    def process_indicator(image: np.ndarray) -> np.ndarray:
        """
        Process an indicator area (RSI, MACD, etc.).
        """
        processor = ImageProcessor(
            scale_factor=2.0,
            contrast_enhance=True,
            denoise=True,
            grayscale=True
        )

        return processor.process(image)

    @staticmethod
    def extract_candle_colors(image: np.ndarray) -> dict:
        """
        Analyze candle colors in a chart region.

        Returns:
            Dict with 'bullish_ratio', 'bearish_ratio', 'dominant'
        """
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

        # Green range (bullish)
        green_lower = np.array([35, 50, 50])
        green_upper = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)

        # Red range (bearish)
        red_lower1 = np.array([0, 50, 50])
        red_upper1 = np.array([10, 255, 255])
        red_lower2 = np.array([170, 50, 50])
        red_upper2 = np.array([180, 255, 255])
        red_mask = cv2.inRange(hsv, red_lower1, red_upper1) | \
                   cv2.inRange(hsv, red_lower2, red_upper2)

        green_pixels = np.sum(green_mask > 0)
        red_pixels = np.sum(red_mask > 0)
        total = green_pixels + red_pixels

        if total == 0:
            return {"bullish_ratio": 0.5, "bearish_ratio": 0.5, "dominant": "neutral"}

        bullish_ratio = green_pixels / total
        bearish_ratio = red_pixels / total

        dominant = "bullish" if bullish_ratio > 0.6 else \
                   "bearish" if bearish_ratio > 0.6 else "neutral"

        return {
            "bullish_ratio": bullish_ratio,
            "bearish_ratio": bearish_ratio,
            "dominant": dominant
        }
