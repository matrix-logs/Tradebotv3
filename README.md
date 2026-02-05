# Screen-Based Trading Bot

A trading bot that uses **screen capture and OCR** to read market data directly from your trading platform, eliminating the need for traditional exchange APIs.

## Why Screen-Based?

- **No API Rate Limits** - Read prices as fast as your screen refreshes
- **Works with ANY Platform** - Even platforms without public APIs
- **See What You See** - Same data, same timing as manual trading
- **No API Keys Required** - No security risks from stored credentials
- **Platform Agnostic** - Works with MT4/MT5, TradingView, broker websites, etc.

## Features

- **Real-time Screen Capture** - Fast, low-latency screen region capture
- **Advanced OCR** - EasyOCR + Tesseract for accurate price extraction
- **Multiple Strategies** - Momentum and Breakout strategies included
- **Flexible Execution** - Alert-only, semi-auto, or fully automatic modes
- **Risk Management** - Built-in trade limits and safety controls
- **Multi-Channel Alerts** - Desktop, Discord, and Telegram notifications

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd Tradebotv3

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# For OCR (choose one or both):
# EasyOCR (recommended, deep learning based)
pip install easyocr

# Tesseract (traditional OCR)
# Linux: sudo apt install tesseract-ocr
# Mac: brew install tesseract
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
pip install pytesseract
```

### 2. Setup

Run the interactive setup wizard:

```bash
python main.py --setup
```

Or manually configure:

1. **Find Screen Coordinates** - Use the helper tool to identify where prices appear:
   ```bash
   python tools/region_helper.py
   ```

2. **Test OCR** - Verify text extraction works:
   ```bash
   python tools/ocr_test.py
   ```

3. **Edit Configuration** - Update `config/settings.yaml` with your regions

### 3. Run

```bash
# Run with default settings (alert-only mode)
python main.py

# Run with specific mode
python main.py --mode alert_only    # Just notifications
python main.py --mode semi_auto     # Position mouse, you click
python main.py --mode full_auto     # Automatic execution (careful!)

# Run with specific strategy
python main.py --strategy momentum
python main.py --strategy breakout

# Debug mode
python main.py --debug
```

## Configuration

### Screen Regions (`config/settings.yaml`)

Define which parts of your screen to monitor:

```yaml
screen:
  monitor: 0  # Primary monitor
  fps: 2      # Captures per second

  regions:
    price:
      enabled: true
      coords: [100, 200, 200, 50]  # [x, y, width, height]
      type: "price"

    indicator_1:
      enabled: true
      coords: [100, 400, 150, 50]
      type: "indicator"
      name: "RSI"
```

### Execution Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `alert_only` | Sends notifications only | Learning, paper trading |
| `semi_auto` | Positions mouse over buttons | Assisted trading |
| `full_auto` | Clicks buttons automatically | **Use with extreme caution** |

### Strategies

**Momentum Strategy**
- Trades based on price movement velocity
- Best for trending markets
- Configurable confirmation periods

**Breakout Strategy**
- Trades when price breaks support/resistance
- Auto-detects key price levels
- Supports manual level input

### Alerts

Configure notifications in `config/settings.yaml`:

```yaml
actions:
  alerts:
    desktop_notification: true
    sound_alert: true

    discord:
      enabled: true
      webhook_url: "https://discord.com/api/webhooks/..."

    telegram:
      enabled: true
      bot_token: "your-bot-token"
      chat_id: "your-chat-id"
```

## Project Structure

```
Tradebotv3/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── config/
│   └── settings.yaml       # Configuration
├── src/
│   ├── bot.py             # Main bot orchestrator
│   ├── capture/           # Screen capture modules
│   │   ├── screen_capture.py
│   │   └── region_selector.py
│   ├── vision/            # OCR and image processing
│   │   ├── ocr_engine.py
│   │   ├── image_processor.py
│   │   └── price_extractor.py
│   ├── signals/           # Signal detection
│   │   ├── signal_detector.py
│   │   └── pattern_recognizer.py
│   ├── strategy/          # Trading strategies
│   │   ├── base_strategy.py
│   │   ├── momentum_strategy.py
│   │   ├── breakout_strategy.py
│   │   └── strategy_manager.py
│   ├── actions/           # Execution and alerts
│   │   ├── action_executor.py
│   │   └── alert_manager.py
│   └── utils/             # Utilities
│       ├── config_loader.py
│       ├── logger.py
│       └── data_store.py
├── tools/
│   ├── region_helper.py   # Find screen coordinates
│   └── ocr_test.py        # Test OCR accuracy
└── data/                  # Logs and saved data
```

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    SCREEN TRADING BOT                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Screen  │───▶│   OCR    │───▶│  Price   │              │
│  │ Capture  │    │ Engine   │    │ Extractor│              │
│  └──────────┘    └──────────┘    └──────────┘              │
│       │                               │                     │
│       ▼                               ▼                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Pattern  │    │  Signal  │◀───│  Data    │              │
│  │Recognizer│───▶│ Detector │    │  Store   │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│                       │                                     │
│                       ▼                                     │
│                 ┌──────────┐                                │
│                 │ Strategy │                                │
│                 │ Manager  │                                │
│                 └──────────┘                                │
│                       │                                     │
│                       ▼                                     │
│                 ┌──────────┐    ┌──────────┐              │
│                 │  Action  │───▶│  Alert   │              │
│                 │ Executor │    │ Manager  │              │
│                 └──────────┘    └──────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Safety Features

- **Execution Confirmation** - Required delay before auto-execution
- **Trade Rate Limiting** - Maximum trades per minute/day
- **Consecutive Loss Limits** - Auto-pause after losing streak
- **Trading Hours** - Only trade during specified times
- **Mouse Failsafe** - Move mouse to corner to abort (pyautogui)

## Tips for Best Results

1. **Optimize Screen Regions**
   - Make regions as small as possible (just the price text)
   - Avoid overlapping UI elements
   - Use high contrast themes on your trading platform

2. **OCR Accuracy**
   - Use EasyOCR for better number recognition
   - Increase scale_factor in config for small text
   - Test with `python tools/ocr_test.py` before going live

3. **Start Safe**
   - Always start in `alert_only` mode
   - Paper trade to validate signals
   - Use `semi_auto` before `full_auto`

4. **Monitor Performance**
   - Check logs in `./data/logs/`
   - Review trades in `./data/trades.csv`
   - Watch for OCR confidence drops

## Disclaimer

This software is for educational purposes only. Trading involves substantial risk of loss. The authors are not responsible for any financial losses incurred through the use of this software. Always test thoroughly with paper trading before using real money.

## License

MIT License - See LICENSE file for details.
