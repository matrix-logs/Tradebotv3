#!/usr/bin/env python3
"""
OCR Test Tool
=============
Test OCR capabilities on screen captures or image files.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import mss
import numpy as np
from PIL import Image


def test_ocr_on_region(x: int, y: int, width: int, height: int):
    """Test OCR on a screen region."""
    print(f"\nCapturing region: ({x}, {y}) {width}x{height}")

    # Capture
    with mss.mss() as sct:
        region = {"left": x, "top": y, "width": width, "height": height}
        screenshot = sct.grab(region)
        image = np.array(screenshot)

    # Save raw capture
    raw_img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    raw_img.save("./data/ocr_test_raw.png")
    print("Raw capture saved to: ./data/ocr_test_raw.png")

    # Process image
    from src.vision.image_processor import TradingScreenProcessor
    processed = TradingScreenProcessor.process_price_display(image)

    # Save processed
    proc_img = Image.fromarray(processed)
    proc_img.save("./data/ocr_test_processed.png")
    print("Processed image saved to: ./data/ocr_test_processed.png")

    # Test EasyOCR
    print("\n--- EasyOCR Results ---")
    try:
        from src.vision.ocr_engine import OCREngine
        ocr = OCREngine(engine="easyocr")

        results = ocr.read_text(processed)
        for r in results:
            print(f"  Text: '{r.text}' | Confidence: {r.confidence:.2%}")

        price_result = ocr.read_price(processed)
        if price_result:
            print(f"\n  Detected Price: ${price_result[0]:,.2f} ({price_result[1]:.2%} confidence)")
        else:
            print("\n  No price detected")

    except ImportError as e:
        print(f"  EasyOCR not available: {e}")
    except Exception as e:
        print(f"  EasyOCR error: {e}")

    # Test Tesseract
    print("\n--- Tesseract Results ---")
    try:
        from src.vision.ocr_engine import OCREngine
        ocr = OCREngine(engine="tesseract")

        results = ocr.read_text(processed)
        for r in results:
            print(f"  Text: '{r.text}' | Confidence: {r.confidence:.2%}")

        price_result = ocr.read_price(processed)
        if price_result:
            print(f"\n  Detected Price: ${price_result[0]:,.2f} ({price_result[1]:.2%} confidence)")
        else:
            print("\n  No price detected")

    except ImportError as e:
        print(f"  Tesseract not available: {e}")
    except Exception as e:
        print(f"  Tesseract error: {e}")


def test_ocr_on_file(filepath: str):
    """Test OCR on an image file."""
    print(f"\nTesting OCR on: {filepath}")

    img = Image.open(filepath)
    image = np.array(img)

    # Process image
    from src.vision.image_processor import TradingScreenProcessor

    # Convert RGB to BGR if needed
    if len(image.shape) == 3 and image.shape[2] == 3:
        import cv2
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    processed = TradingScreenProcessor.process_price_display(image)

    # Test OCR
    print("\n--- OCR Results ---")
    try:
        from src.vision.ocr_engine import OCREngine
        ocr = OCREngine(engine="easyocr")

        results = ocr.read_text(processed)
        for r in results:
            print(f"  Text: '{r.text}' | Confidence: {r.confidence:.2%}")

    except Exception as e:
        print(f"  OCR error: {e}")


def main():
    print("\n" + "=" * 50)
    print("OCR TEST TOOL")
    print("=" * 50)

    # Ensure data directory exists
    Path("./data").mkdir(exist_ok=True)

    print("\nOptions:")
    print("  1. Test OCR on screen region")
    print("  2. Test OCR on image file")

    choice = input("\nSelect option: ")

    if choice == "1":
        print("\nEnter region coordinates:")
        x = int(input("X: "))
        y = int(input("Y: "))
        width = int(input("Width: "))
        height = int(input("Height: "))
        test_ocr_on_region(x, y, width, height)

    elif choice == "2":
        filepath = input("Image file path: ")
        test_ocr_on_file(filepath)


if __name__ == "__main__":
    main()
