"""
Screen capture module using MSS for fast, cross-platform screen grabbing.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mss
import numpy as np
from PIL import Image


class ScreenCapture:
    """
    High-performance screen capture using MSS.
    Captures specific regions of the screen for OCR processing.
    """

    def __init__(self, monitor: int = 0):
        """
        Initialize the screen capture.

        Args:
            monitor: Monitor index (0 = all monitors, 1 = primary, etc.)
        """
        self.sct = mss.mss()
        self.monitor = monitor
        self._last_capture_time = 0
        self._capture_count = 0

    def get_monitor_info(self) -> Dict:
        """Get information about available monitors."""
        monitors = self.sct.monitors
        return {
            "count": len(monitors) - 1,  # Exclude the "all monitors" entry
            "monitors": monitors[1:],    # Skip index 0 (all monitors combined)
            "all": monitors[0]
        }

    def capture_full_screen(self) -> np.ndarray:
        """
        Capture the entire screen.

        Returns:
            NumPy array of the screen image (BGR format)
        """
        monitor = self.sct.monitors[self.monitor]
        screenshot = self.sct.grab(monitor)
        return np.array(screenshot)

    def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> np.ndarray:
        """
        Capture a specific region of the screen.

        Args:
            x: Left coordinate
            y: Top coordinate
            width: Region width
            height: Region height

        Returns:
            NumPy array of the captured region
        """
        region = {
            "left": x,
            "top": y,
            "width": width,
            "height": height
        }
        screenshot = self.sct.grab(region)
        self._last_capture_time = time.time()
        self._capture_count += 1
        return np.array(screenshot)

    def capture_regions(
        self,
        regions: Dict[str, Tuple[int, int, int, int]]
    ) -> Dict[str, np.ndarray]:
        """
        Capture multiple regions in one pass.

        Args:
            regions: Dict of region_name -> (x, y, width, height)

        Returns:
            Dict of region_name -> captured image array
        """
        captures = {}
        for name, (x, y, width, height) in regions.items():
            captures[name] = self.capture_region(x, y, width, height)
        return captures

    def capture_to_pil(
        self,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> Image.Image:
        """
        Capture a region and return as PIL Image.

        Args:
            x, y, width, height: Region coordinates

        Returns:
            PIL Image object
        """
        arr = self.capture_region(x, y, width, height)
        # MSS returns BGRA, convert to RGB
        return Image.fromarray(arr[:, :, :3][:, :, ::-1])

    def save_capture(
        self,
        image: np.ndarray,
        filepath: str,
        timestamp: bool = True
    ) -> str:
        """
        Save a captured image to disk.

        Args:
            image: NumPy array of the image
            filepath: Base path for the file
            timestamp: Whether to add timestamp to filename

        Returns:
            Actual filepath where image was saved
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        if timestamp:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filepath = path.parent / f"{path.stem}_{ts}{path.suffix}"
        else:
            filepath = path

        # Convert BGRA to RGB and save
        img = Image.fromarray(image[:, :, :3][:, :, ::-1])
        img.save(filepath)

        return str(filepath)

    @property
    def stats(self) -> Dict:
        """Get capture statistics."""
        return {
            "total_captures": self._capture_count,
            "last_capture": self._last_capture_time
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Clean up resources."""
        self.sct.close()


class RegionCapture:
    """Convenience class for capturing a specific pre-defined region."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str = "region"
    ):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.name = name
        self._capture = ScreenCapture()

    def capture(self) -> np.ndarray:
        """Capture this region."""
        return self._capture.capture_region(
            self.x, self.y, self.width, self.height
        )

    def capture_pil(self) -> Image.Image:
        """Capture this region as PIL Image."""
        return self._capture.capture_to_pil(
            self.x, self.y, self.width, self.height
        )

    @property
    def coords(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def __repr__(self):
        return f"RegionCapture('{self.name}': {self.coords})"
