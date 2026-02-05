"""
Interactive region selector for defining screen capture areas.
Helps users select the areas of their trading platform to monitor.
"""

import json
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import messagebox
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

from PIL import Image, ImageDraw, ImageTk
import mss


class RegionSelector:
    """
    Interactive tool for selecting screen regions.
    Creates a transparent overlay for users to draw selection boxes.
    """

    def __init__(self):
        self.regions: Dict[str, Tuple[int, int, int, int]] = {}
        self.current_region: Optional[str] = None
        self._start_x = 0
        self._start_y = 0

    def select_region_interactive(
        self,
        region_name: str = "region",
        callback: Optional[Callable] = None
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Open an interactive window to select a screen region.

        Args:
            region_name: Name for this region
            callback: Optional callback when selection is complete

        Returns:
            Tuple of (x, y, width, height) or None if cancelled
        """
        if not HAS_TKINTER:
            print("ERROR: tkinter not available. Use select_region_manual() instead.")
            return None

        self.current_region = region_name
        result = [None]

        # Capture current screen
        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # Create fullscreen transparent window
        root = tk.Tk()
        root.attributes("-fullscreen", True)
        root.attributes("-alpha", 0.3)
        root.configure(cursor="cross")

        # Store coordinates
        start = [0, 0]
        rect_id = [None]

        canvas = tk.Canvas(root, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        # Draw semi-transparent overlay
        photo = ImageTk.PhotoImage(img)
        canvas.create_image(0, 0, anchor=tk.NW, image=photo)

        # Instructions
        canvas.create_text(
            img.width // 2, 30,
            text=f"Select region: {region_name} (Click and drag, then release)",
            fill="white",
            font=("Arial", 20, "bold")
        )
        canvas.create_text(
            img.width // 2, 60,
            text="Press ESC to cancel",
            fill="white",
            font=("Arial", 14)
        )

        def on_press(event):
            start[0] = event.x
            start[1] = event.y
            if rect_id[0]:
                canvas.delete(rect_id[0])

        def on_drag(event):
            if rect_id[0]:
                canvas.delete(rect_id[0])
            rect_id[0] = canvas.create_rectangle(
                start[0], start[1], event.x, event.y,
                outline="red", width=3
            )

        def on_release(event):
            x1, y1 = start
            x2, y2 = event.x, event.y

            # Normalize coordinates
            x = min(x1, x2)
            y = min(y1, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)

            if width > 10 and height > 10:
                result[0] = (x, y, width, height)
                self.regions[region_name] = result[0]

            root.destroy()

        def on_escape(event):
            root.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        root.bind("<Escape>", on_escape)

        root.mainloop()

        if callback and result[0]:
            callback(region_name, result[0])

        return result[0]

    def select_region_manual(
        self,
        region_name: str = "region"
    ) -> Tuple[int, int, int, int]:
        """
        Manually input region coordinates via terminal.

        Args:
            region_name: Name for this region

        Returns:
            Tuple of (x, y, width, height)
        """
        print(f"\n=== Manual Region Selection: {region_name} ===")
        print("Enter the coordinates for this region.")
        print("Tip: Use a screenshot tool to find pixel coordinates.\n")

        x = int(input("X (left edge): "))
        y = int(input("Y (top edge): "))
        width = int(input("Width: "))
        height = int(input("Height: "))

        coords = (x, y, width, height)
        self.regions[region_name] = coords

        print(f"\nRegion '{region_name}' set to: {coords}")
        return coords

    def select_multiple_regions(
        self,
        region_names: List[str],
        interactive: bool = True
    ) -> Dict[str, Tuple[int, int, int, int]]:
        """
        Select multiple regions one after another.

        Args:
            region_names: List of region names to select
            interactive: Use interactive mode if available

        Returns:
            Dict of region_name -> coordinates
        """
        for name in region_names:
            print(f"\n>>> Select region: {name}")

            if interactive and HAS_TKINTER:
                coords = self.select_region_interactive(name)
            else:
                coords = self.select_region_manual(name)

            if coords:
                print(f"Region '{name}': {coords}")
            else:
                print(f"Region '{name}' selection cancelled.")

            time.sleep(0.5)  # Brief pause between selections

        return self.regions

    def save_regions(self, filepath: str) -> None:
        """Save selected regions to a JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(self.regions, f, indent=2)

        print(f"Regions saved to: {filepath}")

    def load_regions(self, filepath: str) -> Dict[str, Tuple[int, int, int, int]]:
        """Load regions from a JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)

        # Convert lists back to tuples
        self.regions = {k: tuple(v) for k, v in data.items()}
        return self.regions

    def preview_regions(self, output_path: str = "./data/region_preview.png") -> str:
        """
        Capture screen and draw all defined regions for preview.

        Args:
            output_path: Where to save the preview image

        Returns:
            Path to saved preview image
        """
        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        draw = ImageDraw.Draw(img)

        colors = ["red", "green", "blue", "yellow", "cyan", "magenta"]
        for i, (name, (x, y, w, h)) in enumerate(self.regions.items()):
            color = colors[i % len(colors)]
            # Draw rectangle
            draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
            # Draw label
            draw.text((x + 5, y + 5), name, fill=color)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)

        print(f"Region preview saved to: {output_path}")
        return output_path


def run_region_setup():
    """Run interactive region setup wizard."""
    print("\n" + "=" * 50)
    print("SCREEN TRADING BOT - REGION SETUP")
    print("=" * 50)

    selector = RegionSelector()

    # Define regions to set up
    regions_to_select = [
        ("price", "Main price display"),
        ("bid_ask", "Bid/Ask spread area"),
        ("indicator_1", "First indicator (e.g., RSI)"),
    ]

    print("\nYou'll select the following screen regions:")
    for name, desc in regions_to_select:
        print(f"  - {name}: {desc}")

    input("\nPress Enter to begin selection...")

    for name, desc in regions_to_select:
        print(f"\n>>> Now select: {desc}")
        if HAS_TKINTER:
            selector.select_region_interactive(name)
        else:
            selector.select_region_manual(name)

    # Save and preview
    selector.save_regions("./config/regions.json")
    selector.preview_regions()

    print("\n" + "=" * 50)
    print("Region setup complete!")
    print("=" * 50)

    return selector.regions


if __name__ == "__main__":
    run_region_setup()
