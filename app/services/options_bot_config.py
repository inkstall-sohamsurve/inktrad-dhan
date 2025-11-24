"""
Configuration file for Options Trading Bot

Modify these settings based on your trading requirements
"""

# =============================================================================
# Dhan API Credentials
# =============================================================================
CLIENT_ID = "1101169575"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzYzODAzMTIzLCJpYXQiOjE3NjM3MTY3MjMsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAxMTY5NTc1In0.sXbHgUfV2vt7Pn35n7bfc7N9cop0K1Vx4UtoOfA5aC8ZfVD2XKDPCJZvbI6kPQoKai4oUUAR5QPbgGm4MM9gtA"

# =============================================================================
# Underlying Instrument
# =============================================================================
# Security IDs for CE and PE options
CE_SECURITY_ID = "486545"  # Security ID for CE option (when price > 5800)
PE_SECURITY_ID = "486546"  # Security ID for PE option (when price < 4600)
UNDERLYING_EXCHANGE = "MCX"

# =============================================================================
# Strategy Thresholds
# =============================================================================f
# If underlying price > UPPER_THRESHOLD → Buy CE
# If underlying price < LOWER_THRESHOLD → Buy PE
UPPER_THRESHOLD = 5800.0
LOWER_THRESHOLD = 4600.0

# =============================================================================
# Position Sizing
# =============================================================================
# Initial entry: Total quantity split into 2 orders
INITIAL_QUANTITY = 150
SPLIT_SIZE = 75  # Each split order size (INITIAL_QUANTITY / 2)

# Averaging down: Quantity to buy on each ₹1 drop
AVERAGING_QUANTITY = 150

# =============================================================================
# Price Drop Trigger
# =============================================================================
# Trigger averaging down when price drops by this amount
PRICE_DROP_TRIGGER = 1.0  # ₹1

# =============================================================================
# Target Adjustments
# =============================================================================
# Target gap above LTP based on number of drops
TARGET_ADJUSTMENTS = {
    0: 0.90,  # Initial entry target: LTP + ₹0.90
    1: 0.70,  # After 1st ₹1 drop: LTP + ₹0.70
    2: 0.50,  # After 2nd ₹1 drop: LTP + ₹0.50
    3: 0.30,  # After 3rd+ ₹1 drops: LTP + ₹0.30
}

# =============================================================================
# API Settings
# =============================================================================
# Polling interval (seconds between LTP checks)
API_SLEEP = 1.0

# Rate limiting
MAX_API_CALLS_PER_HOUR = 20000

# Trade confirmation settings
MAX_TRADE_BOOK_RETRIES = 10
TRADE_BOOK_POLL_INTERVAL = 0.5  # Seconds between trade book polls

# =============================================================================
# Option Selection (Advanced)
# =============================================================================
# Strike selection method: "ATM", "OTM", "ITM"
STRIKE_SELECTION = "ATM"

# Strike offset (for OTM/ITM selection)
# Positive = OTM, Negative = ITM
STRIKE_OFFSET = 0

# Expiry selection: "NEAREST", "WEEKLY", "MONTHLY"
EXPIRY_SELECTION = "NEAREST"

# =============================================================================
# Risk Management
# =============================================================================
# Maximum number of averaging down iterations
MAX_AVERAGING_ITERATIONS = 10

# Maximum total position size
MAX_TOTAL_QUANTITY = 1500

# Stop loss (optional, set to None to disable)
STOP_LOSS_PERCENT = None  # e.g., 10.0 for 10% stop loss

# =============================================================================
# Logging
# =============================================================================
# Log level: "DEBUG", "INFO", "WARNING", "ERROR"
LOG_LEVEL = "INFO"

# Log to file
LOG_TO_FILE = True
LOG_FILE_PATH = "options_trading_bot.log"
