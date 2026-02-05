#!/usr/bin/env python3
"""
Screen-Based Trading Bot
========================
A trading bot that uses screen capture and OCR to read market data
instead of traditional exchange APIs.

Usage:
    python main.py              # Run with default config
    python main.py --setup      # Run setup wizard
    python main.py --config custom.yaml  # Use custom config
    python main.py --mode alert_only     # Override execution mode
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    parser = argparse.ArgumentParser(
        description="Screen-Based Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                        Run bot with default settings
  python main.py --setup                Run interactive setup wizard
  python main.py --select-regions       Select screen regions interactively
  python main.py --test-ocr             Test OCR on current screen
  python main.py --mode alert_only      Run in alert-only mode
  python main.py --strategy momentum    Use momentum strategy
        """
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        default="./config/settings.yaml",
        help="Path to configuration file"
    )

    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run interactive setup wizard"
    )

    parser.add_argument(
        "--select-regions",
        action="store_true",
        help="Interactively select screen regions"
    )

    parser.add_argument(
        "--test-ocr",
        action="store_true",
        help="Test OCR on a screen capture"
    )

    parser.add_argument(
        "--mode", "-m",
        choices=["alert_only", "semi_auto", "full_auto"],
        help="Override execution mode"
    )

    parser.add_argument(
        "--strategy", "-s",
        choices=["momentum", "breakout"],
        help="Override active strategy"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Handle special modes
    if args.setup:
        run_setup_wizard()
        return

    if args.select_regions:
        run_region_selector()
        return

    if args.test_ocr:
        run_ocr_test()
        return

    # Run the bot
    run_bot(args)


def run_setup_wizard():
    """Run the interactive setup wizard."""
    print("\n" + "=" * 60)
    print("SCREEN TRADING BOT - SETUP WIZARD")
    print("=" * 60)

    from src.capture.region_selector import RegionSelector
    from src.utils.config_loader import ConfigLoader

    print("\nThis wizard will help you configure the trading bot.")
    print("You'll need to:")
    print("  1. Select screen regions for price data")
    print("  2. Configure alert settings")
    print("  3. Choose a trading strategy")

    input("\nPress Enter to continue...")

    # Step 1: Region selection
    print("\n--- STEP 1: Screen Region Selection ---")
    print("You'll select areas of your trading platform to monitor.")

    selector = RegionSelector()

    regions_to_select = [
        ("price", "Main price display (where the current price is shown)"),
    ]

    add_more = True
    while add_more:
        for name, desc in regions_to_select:
            print(f"\nSelect: {desc}")
            input("Position your trading platform and press Enter...")
            selector.select_region_interactive(name)

        more = input("\nAdd another region? (y/n): ").lower()
        if more == 'y':
            name = input("Region name: ")
            desc = input("Description: ")
            regions_to_select = [(name, desc)]
        else:
            add_more = False

    # Save regions
    selector.save_regions("./config/regions.json")
    print("\nRegions saved!")

    # Step 2: Strategy selection
    print("\n--- STEP 2: Strategy Selection ---")
    print("Available strategies:")
    print("  1. Momentum - Trades based on price movement speed")
    print("  2. Breakout - Trades when price breaks key levels")

    choice = input("\nSelect strategy (1 or 2): ")
    strategy = "momentum" if choice == "1" else "breakout"

    # Step 3: Mode selection
    print("\n--- STEP 3: Execution Mode ---")
    print("Execution modes:")
    print("  1. Alert Only - Send notifications only (safest)")
    print("  2. Semi-Auto - Position mouse, you click")
    print("  3. Full Auto - Automatic execution (risky!)")

    choice = input("\nSelect mode (1, 2, or 3): ")
    modes = {"1": "alert_only", "2": "semi_auto", "3": "full_auto"}
    mode = modes.get(choice, "alert_only")

    # Update config
    config = ConfigLoader()
    config.set("strategy.active", strategy)
    config.set("actions.mode", mode)
    config.save()

    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print(f"\nStrategy: {strategy}")
    print(f"Mode: {mode}")
    print("\nRun the bot with: python main.py")


def run_region_selector():
    """Run the region selector tool."""
    from src.capture.region_selector import run_region_setup
    run_region_setup()


def run_ocr_test():
    """Test OCR on current screen."""
    print("\n--- OCR Test ---")
    print("This will capture a region and test text extraction.\n")

    from src.capture.screen_capture import ScreenCapture
    from src.vision.ocr_engine import OCREngine
    from src.vision.image_processor import TradingScreenProcessor

    # Get region
    print("Enter the region coordinates:")
    x = int(input("X: "))
    y = int(input("Y: "))
    width = int(input("Width: "))
    height = int(input("Height: "))

    # Capture
    capture = ScreenCapture()
    image = capture.capture_region(x, y, width, height)

    # Process
    processed = TradingScreenProcessor.process_price_display(image)

    # OCR
    print("\nTesting OCR engines...\n")

    try:
        ocr = OCREngine(engine="easyocr")
        results = ocr.read_text(processed)
        print("EasyOCR results:")
        for r in results:
            print(f"  '{r.text}' (confidence: {r.confidence:.2f})")

        price = ocr.read_price(processed)
        if price:
            print(f"\nDetected price: {price[0]} (confidence: {price[1]:.2f})")
    except Exception as e:
        print(f"EasyOCR error: {e}")

    try:
        ocr = OCREngine(engine="tesseract")
        results = ocr.read_text(processed)
        print("\nTesseract results:")
        for r in results:
            print(f"  '{r.text}' (confidence: {r.confidence:.2f})")
    except Exception as e:
        print(f"Tesseract error: {e}")

    capture.close()
    print("\nOCR test complete!")


def run_bot(args):
    """Run the trading bot with given arguments."""
    from src.bot import ScreenTradingBot
    from src.utils.config_loader import ConfigLoader

    # Load and potentially override config
    config = ConfigLoader(args.config)

    if args.debug:
        config.set("general.log_level", "DEBUG")

    if args.mode:
        config.set("actions.mode", args.mode)

    if args.strategy:
        config.set("strategy.active", args.strategy)

    # Save any overrides
    config.save()

    # Create and run bot
    bot = ScreenTradingBot(args.config)

    print("\n" + "=" * 60)
    print("SCREEN TRADING BOT")
    print("=" * 60)
    print(f"\nStrategy: {bot.strategy_manager.active_strategy_name}")
    print(f"Mode: {bot.action_executor.mode.value}")
    print(f"Config: {args.config}")
    print("\nPress Ctrl+C to stop")
    print("=" * 60 + "\n")

    bot.start()


if __name__ == "__main__":
    main()
