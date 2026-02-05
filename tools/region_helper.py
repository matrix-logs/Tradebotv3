#!/usr/bin/env python3
"""
Region Helper Tool
==================
Interactive tool for finding and testing screen region coordinates.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import mss
    from PIL import Image
    import numpy as np
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install mss Pillow numpy")
    sys.exit(1)


def get_mouse_position():
    """Get current mouse position."""
    try:
        import pyautogui
        return pyautogui.position()
    except ImportError:
        print("Install pyautogui for mouse tracking: pip install pyautogui")
        return None


def capture_at_mouse():
    """Capture a region around the mouse cursor."""
    pos = get_mouse_position()
    if not pos:
        return

    print(f"\nMouse position: ({pos.x}, {pos.y})")

    size = int(input("Capture size (pixels around cursor): ") or "100")
    half = size // 2

    x = max(0, pos.x - half)
    y = max(0, pos.y - half)

    with mss.mss() as sct:
        region = {
            "left": x,
            "top": y,
            "width": size,
            "height": size
        }
        screenshot = sct.grab(region)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    # Save capture
    output_path = Path("./data/test_capture.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)

    print(f"Saved capture to: {output_path}")
    print(f"Region: x={x}, y={y}, width={size}, height={size}")

    return (x, y, size, size)


def track_mouse():
    """Continuously track and display mouse position."""
    try:
        import pyautogui
    except ImportError:
        print("Install pyautogui: pip install pyautogui")
        return

    print("\n--- Mouse Tracker ---")
    print("Move your mouse to identify coordinates.")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            pos = pyautogui.position()
            print(f"\rPosition: ({pos.x:4d}, {pos.y:4d})    ", end="", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nTracking stopped.")


def test_region_capture():
    """Test capturing a specific region."""
    print("\n--- Test Region Capture ---")

    x = int(input("X coordinate: "))
    y = int(input("Y coordinate: "))
    width = int(input("Width: "))
    height = int(input("Height: "))

    with mss.mss() as sct:
        region = {
            "left": x,
            "top": y,
            "width": width,
            "height": height
        }

        for i in range(3):
            start = time.time()
            screenshot = sct.grab(region)
            elapsed = time.time() - start
            print(f"Capture {i+1}: {elapsed*1000:.1f}ms")

        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    output_path = Path("./data/test_region.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)

    print(f"\nSaved to: {output_path}")


def main():
    print("\n" + "=" * 50)
    print("SCREEN REGION HELPER")
    print("=" * 50)

    while True:
        print("\nOptions:")
        print("  1. Track mouse position")
        print("  2. Capture at mouse location")
        print("  3. Test specific region")
        print("  4. Exit")

        choice = input("\nSelect option: ")

        if choice == "1":
            track_mouse()
        elif choice == "2":
            capture_at_mouse()
        elif choice == "3":
            test_region_capture()
        elif choice == "4":
            break
        else:
            print("Invalid option")


if __name__ == "__main__":
    main()
