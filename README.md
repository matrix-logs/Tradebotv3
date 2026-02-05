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

**TheStrat Strategy (Recommended)**
- Based on Rob Smith's Universal Truths methodology
- Three Scenarios: Inside Bar (1), Trending (2U/2D), Outside Bar (3)
- Full Timeframe Continuity (FTFC) analysis across M, W, D, 60min
- Setups: Inside bar breakouts, Failed 2s, 2-2 Reversals
- Optimized for XAU/USD and forex pairs

**Momentum Strategy** (Legacy)
- Trades based on price movement velocity
- Best for trending markets
- Configurable confirmation periods

**Breakout Strategy** (Legacy)
- Trades when price breaks support/resistance
- Auto-detects key price levels
- Supports manual level input

### TheStrat Methodology

TheStrat is based on three Universal Truths:

1. **Scenario 1 (Inside Bar)** - Current candle is contained within prior candle
   - Indicates consolidation/coiling
   - Sets up for breakout plays

2. **Scenario 2 (Trending)** - Takes out one side of prior candle
   - 2U = Takes out high (bullish)
   - 2D = Takes out low (bearish)

3. **Scenario 3 (Outside Bar)** - Takes out both sides of prior candle
   - Indicates reversal or expansion

**Full Timeframe Continuity (FTFC):**
- When all timeframes (M, W, D, 60min) align in same direction
- FTFC UP = All green/bullish = Strong long bias
- FTFC DOWN = All red/bearish = Strong short bias

### Market Condition Detection

The bot includes adaptive market condition detection:

- **Regime Detection**: Strong/Weak Uptrend, Downtrend, Consolidation, Reversal
- **Volatility Analysis**: High, Normal, Low volatility states
- **Session Awareness**: London, New York, Asian session detection
- **Trading Conditions**: Favorable, Caution, Avoid recommendations

### AI Brain (Groq Integration)

The bot features an AI-powered analysis engine using Groq's free, ultra-fast LLM inference:

**Setup:**
1. Get a free API key at https://console.groq.com
2. Set in config or environment variable:
   ```bash
   export GROQ_API_KEY="your-key-here"
   ```

**Features:**
- Real-time TheStrat analysis using LLM reasoning
- Multi-timeframe interpretation
- Risk assessment and confidence scoring
- Entry/exit suggestions with reasoning

**Available Models (all free):**
| Model | Speed | Reasoning |
|-------|-------|-----------|
| llama3-70b | Fast | Best |
| llama3-8b | Fastest | Good |
| mixtral | Fast | Good |
| gemma2 | Fast | Good |

**Configuration:**
```yaml
ai:
  enabled: true
  model: "llama3-70b"
  analysis_interval_ticks: 60  # ~30 seconds
  decision_weight: 0.7  # How much to trust AI vs rules
```

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
│   │   ├── thestrat_strategy.py   # TheStrat (recommended)
│   │   ├── scenario_detector.py   # Scenario 1/2/3 detection
│   │   ├── timeframe_continuity.py # FTFC analysis
│   │   ├── market_condition.py    # Market regime detection
│   │   ├── momentum_strategy.py   # Legacy
│   │   ├── breakout_strategy.py   # Legacy
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
