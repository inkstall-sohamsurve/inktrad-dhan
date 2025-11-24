#!/usr/bin/env python3
"""
Crude Oil OPTIONS Trading Bot for Dhan API - MCX

⚠️ IMPORTANT: This bot trades OPTIONS only, NOT futures!

EXCHANGE SEGMENTS:
• MCX_COMM: Used for fetching OHLC/LTP data (market data API)
• MCX_FO: Used for placing option orders (order placement API)

INSTRUMENTS:
• Underlying: CRUDEOIL DEC FUT (462523) - for monitoring only
• CE Option: CRUDEOIL-16Dec2025-5800-CE (472826)
• PE Option: CRUDEOIL-16Dec2025-4600-PE (472863)

STRATEGY:
1. Monitor underlying FUTURES LTP to decide which OPTION to trade:
   - If underlying > 5800 → BUY CE OPTION (472826)
   - If underlying < 4600 → BUY PE OPTION (472863)

2. Initial entry: 150 units (75 × 2 batches) of OPTION
   - Target = entry_price + 0.90

3. Averaging down on OPTION LTP drops:
   - Every ₹1 drop in OPTION LTP → Buy 150 more units
   - Adjust target based on drop count:
     * 1st drop → target = current_ltp + 0.90
     * 2nd drop → target = current_ltp + 0.70
     * 3rd drop → target = current_ltp + 0.50
     * 4th+ drops → target = current_ltp + 0.30

4. Exit: When OPTION LTP >= target, exit all positions
"""

import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dhanhq import dhanhq

# =============================================================================
# Configuration
# =============================================================================

# Authentication
CLIENT_ID: str = "1101169575"
ACCESS_TOKEN: str = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzYzODEyOTAwLCJpYXQiOjE3NjM3MjY1MDAsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAxMTY5NTc1In0.n8UNKIAt2QChoqOlPqDo0zfTkPSg-7xcmdbPkwgJwCgxzlG9VCrInldC5L-UHTFgFMQGHzu-PkKZwT1-_T-a8Q"

# Trading Configuration
# Security IDs for Crude Oil Options
CE_OPTION_SECURITY_ID: str = "472826"  # CRUDEOIL-16Dec2025-5800-CE
PE_OPTION_SECURITY_ID: str = "472863"  # CRUDEOIL-16Dec2025-4600-PE
UNDERLYING_SECURITY_ID: str = "462523"  # CRUDEOIL DEC FUT (for price monitoring)

# Exchange Segments
# MCX_COMM: For fetching OHLC/LTP data
# MCX_FO: For placing orders (MCX Futures & Options)
DATA_EXCHANGE: str = "MCX_COMM"  # For OHLC/LTP data fetching
ORDER_EXCHANGE: str = "MCX_FO"  # For placing option orders
PRODUCT_TYPE = None  # Will be set to dhan.INTRA after initialization

# Strategy Parameters
# Crude Oil UNDERLYING price thresholds (in Rupees)
UPPER_THRESHOLD: float = 5800.0  # If underlying > 5800 → BUY CE Option (472826)
LOWER_THRESHOLD: float = 4600.0  # If underlying < 4600 → BUY PE Option (472863)
INITIAL_QUANTITY: int = 150  # Total initial quantity (split as 75 + 75)
SPLIT_SIZE: int = 75  # Size of each split order
AVERAGING_QUANTITY: int = 150  # Quantity to buy on each ₹1 drop
PRICE_DROP_TRIGGER: float = 1.0  # ₹1 drop triggers new buy

# Target adjustments based on number of OPTION LTP drops
# Target = current_option_ltp + adjustment
TARGET_ADJUSTMENTS = {
    0: 0.90,  # Initial entry: target = entry_price + 0.90
    1: 0.90,  # After 1st ₹1 drop: target = current_ltp + 0.90
    2: 0.70,  # After 2nd ₹1 drop: target = current_ltp + 0.70
    3: 0.50,  # After 3rd ₹1 drop: target = current_ltp + 0.50
    4: 0.30,  # After 4th+ ₹1 drop: target = current_ltp + 0.30
}

# Polling and API settings
API_SLEEP: float = 1.0  # Seconds between LTP polls
MAX_API_CALLS_PER_HOUR: int = 20000
MAX_TRADE_BOOK_RETRIES: int = 10
TRADE_BOOK_POLL_INTERVAL: float = 0.5

# =============================================================================
# Logging Setup
# =============================================================================

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("options_trading_bot")

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Position:
    """Represents a single buy position"""
    order_id: str
    buy_price: float
    quantity: int
    buy_time: datetime
    reason: str  # "INITIAL_ENTRY", "AVERAGING_DOWN"
    
    def __repr__(self):
        return f"Position(order_id={self.order_id}, qty={self.quantity}, price={self.buy_price:.2f})"


class TradingState:
    """Maintains the current trading state"""
    def __init__(self):
        self.option_type: Optional[str] = None  # "CE" or "PE"
        self.option_security_id: Optional[str] = None
        self.option_symbol: Optional[str] = None
        self.positions: List[Position] = []
        self.last_buy_price: Optional[float] = None
        self.current_target: Optional[float] = None
        self.drop_count: int = 0  # Number of ₹1 drops executed
        self.has_entered: bool = False
        self.total_quantity: int = 0
        self.cycle_count: int = 0  # Number of completed cycles
        self.cumulative_pnl: float = 0.0  # Total P&L across all cycles
        
    def add_position(self, position: Position):
        """Add a new position and update state"""
        self.positions.append(position)
        self.total_quantity += position.quantity
        self.last_buy_price = position.buy_price
        
    def calculate_average_price(self) -> float:
        """Calculate weighted average buy price"""
        if not self.positions:
            return 0.0
        total_cost = sum(p.buy_price * p.quantity for p in self.positions)
        return total_cost / self.total_quantity
    
    def update_target(self, ltp: float):
        """Update target based on drop count"""
        target_gap = TARGET_ADJUSTMENTS.get(self.drop_count, 0.30)
        self.current_target = ltp + target_gap
        logger.info(
            f"📊 Target updated: LTP={ltp:.2f}, Drop Count={self.drop_count}, "
            f"Target Gap={target_gap:.2f}, New Target={self.current_target:.2f}"
        )


# =============================================================================
# API Helper Functions
# =============================================================================

def create_dhan_client() -> Any:
    """Create and authenticate Dhan client"""
    if not CLIENT_ID or not ACCESS_TOKEN:
        logger.error("CLIENT_ID or ACCESS_TOKEN not configured")
        sys.exit(1)
    
    client = dhanhq(CLIENT_ID, ACCESS_TOKEN)
    logger.info("✅ Successfully created DhanHQ client")
    return client


def fetch_underlying_ltp(dhan_client: Any, security_id: str) -> float:
    """Fetch LTP for underlying instrument (Crude Oil Futures)"""
    try:
        request_body = {"MCX_COMM": [int(security_id)]}
        logger.debug(f"Requesting OHLC data with: {request_body}")
        response = dhan_client.ohlc_data(securities=request_body)
        
        logger.debug(f"Raw API response: {response}")
        
        # Handle different response structures
        response_data = response.get("data", {})
        if "data" in response_data:
            response_data = response_data["data"]
        
        logger.debug(f"Response data after extraction: {response_data}")
        
        segment_data = response_data.get("MCX_COMM", {})
        logger.debug(f"MCX_COMM segment data: {segment_data}")
        
        instrument_data = segment_data.get(str(security_id)) or segment_data.get(int(security_id))
        
        if not instrument_data:
            logger.error(f"Available keys in MCX_COMM segment: {list(segment_data.keys())}")
            logger.error(f"Full response structure: {response}")
            raise ValueError(f"No data found for security_id={security_id}. Market may be closed or security ID is incorrect.")
        
        logger.debug(f"Instrument data: {instrument_data}")
        ltp = float(instrument_data.get("last_price", 0))
        
        if ltp == 0:
            logger.warning(f"LTP is 0 for security_id={security_id}. Market may be closed.")
        
        return ltp
    except Exception as e:
        logger.error(f"Error fetching underlying LTP: {e}")
        raise


def fetch_option_ltp(dhan_client: Any, security_id: str) -> float:
    """Fetch LTP for option contract"""
    try:
        # For MCX_COMM options, use MCX_COMM segment
        request_body = {"MCX_COMM": [int(security_id)]}
        response = dhan_client.ohlc_data(securities=request_body)
        
        response_data = response.get("data", {})
        if "data" in response_data:
            response_data = response_data["data"]
        
        segment_data = response_data.get("MCX_COMM", {})
        instrument_data = segment_data.get(str(security_id)) or segment_data.get(int(security_id))
        
        if not instrument_data:
            raise ValueError(f"No option data found for security_id={security_id}")
        
        ltp = float(instrument_data.get("last_price", 0))
        return ltp
    except Exception as e:
        logger.error(f"Error fetching option LTP: {e}")
        raise


def identify_option_contract(
    dhan_client: Any,
    underlying_price: float,
    option_type: str
) -> Tuple[str, str]:
    """
    Identify the appropriate option contract based on underlying price
    
    Returns:
        (security_id, symbol)
    
    Note: This is a placeholder. In production, you would:
    1. Fetch option chain data
    2. Select ATM or appropriate strike
    3. Choose nearest expiry
    4. Return the security_id and symbol
    """
    # TODO: Implement actual option chain lookup
    # For now, using placeholder values
    # You need to implement this based on Dhan's option chain API
    
    logger.warning(
        "⚠️ Option contract identification is using placeholder logic. "
        "Implement actual option chain lookup for production use."
    )
    
    # Placeholder: You must replace this with actual option chain lookup
    if option_type == "CE":
        # Example: CRUDEOIL 5800 CE
        security_id = "PLACEHOLDER_CE_SECURITY_ID"
        symbol = f"CRUDEOIL {int(underlying_price // 50 * 50)} CE"
    else:
        # Example: CRUDEOIL 4600 PE
        security_id = "PLACEHOLDER_PE_SECURITY_ID"
        symbol = f"CRUDEOIL {int(underlying_price // 50 * 50)} PE"
    
    logger.info(f"📋 Identified option: {symbol} (security_id={security_id})")
    return security_id, symbol


def place_market_order(
    dhan_client: Any,
    security_id: str,
    quantity: int,
    transaction_type: Any,
    order_name: str
) -> Tuple[str, Optional[float], int]:
    """
    Place a market order and wait for execution
    
    Returns:
        (order_id, executed_price, executed_quantity)
    """
    try:
        logger.info(
            f"📤 Placing {order_name} MARKET order: security_id={security_id}, quantity={quantity}"
        )
        
        response = dhan_client.place_order(
            security_id=security_id,
            exchange_segment=ORDER_EXCHANGE,  # MCX_FO for option orders
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=dhan_client.MARKET,
            product_type=PRODUCT_TYPE,
            price=0,
        )
        
        data = response.get("data", {})
        order_id = (
            data.get("orderId") or data.get("order_id") or 
            response.get("orderId") or response.get("order_id")
        )
        
        if not order_id:
            raise RuntimeError(f"Order failed: orderId missing in response: {response}")
        
        logger.info(f"✅ Order placed: order_id={order_id}")
        
        # Wait for execution
        executed_price, executed_quantity = wait_for_trade_fill(
            dhan_client, order_id, order_name
        )
        
        return order_id, executed_price, executed_quantity
        
    except Exception as e:
        logger.error(f"❌ Error placing order: {e}")
        raise


def wait_for_trade_fill(
    dhan_client: Any,
    order_id: str,
    order_name: str
) -> Tuple[Optional[float], int]:
    """
    Poll trade book until order is filled
    
    Returns:
        (average_price, total_quantity)
    """
    for attempt in range(1, MAX_TRADE_BOOK_RETRIES + 1):
        try:
            import time
            time.sleep(TRADE_BOOK_POLL_INTERVAL)
            
            trade_response = dhan_client.get_trade_book(order_id)
            
            if not trade_response:
                logger.debug(f"No trades yet for order {order_id} (attempt {attempt}/{MAX_TRADE_BOOK_RETRIES})")
                continue
            
            trades = trade_response if isinstance(trade_response, list) else [trade_response]
            
            total_quantity = 0
            total_value = 0.0
            
            for trade in trades:
                qty = int(trade.get("tradedQuantity", 0))
                price = float(trade.get("tradedPrice", 0.0))
                if qty > 0:
                    total_quantity += qty
                    total_value += qty * price
            
            if total_quantity > 0:
                avg_price = total_value / total_quantity
                logger.info(
                    f"✅ {order_name} order {order_id} filled: "
                    f"quantity={total_quantity}, avg_price={avg_price:.2f}"
                )
                return avg_price, total_quantity
                
        except Exception as e:
            logger.error(f"Error fetching trade book (attempt {attempt}): {e}")
    
    logger.warning(f"⚠️ Could not confirm execution for order {order_id}")
    return None, 0


# =============================================================================
# Trading Logic
# =============================================================================

async def run_trading_bot(dhan_client: Any):
    """Main trading bot loop"""
    global EXCHANGE_SEGMENT, PRODUCT_TYPE
    
    ORDER_EXCHANGE_SEGMENT = ORDER_EXCHANGE  # MCX_FO for orders
    PRODUCT_TYPE = dhan_client.INTRA
    
    state = TradingState()
    
    logger.info("🚀 Starting Crude Oil OPTIONS Trading Bot - CONTINUOUS MODE")
    logger.info(f"📊 Strategy: Monitor UNDERLYING futures, Trade OPTIONS only")
    logger.info(f"   Data Exchange: {DATA_EXCHANGE} (for OHLC/LTP)")
    logger.info(f"   Order Exchange: {ORDER_EXCHANGE} (for placing orders)")
    logger.info(f"   If underlying > {UPPER_THRESHOLD} → BUY CE Option (472826)")
    logger.info(f"   If underlying < {LOWER_THRESHOLD} → BUY PE Option (472863)")
    logger.info(f"📦 Initial Quantity: {INITIAL_QUANTITY} (split as {SPLIT_SIZE} + {SPLIT_SIZE})")
    logger.info(f"📉 Averaging: {AVERAGING_QUANTITY} units on every ₹{PRICE_DROP_TRIGGER} drop")
    logger.info(f"🔄 Mode: Continuous (will restart after each cycle completion)")
    logger.info(f"⚠️  Press Ctrl+C to stop the bot")
    
    while True:
        try:
            # Step 1: Determine which security to monitor based on entry status
            logger.info("\n" + "="*80)
            logger.info(f"🔄 POLLING CYCLE - Cycle #{state.cycle_count + 1}")
            logger.info("="*80)
            
            # Step 2: Check underlying price and determine which OPTION to trade
            if not state.has_entered:
                logger.info("\n🎯 DECISION POINT: Checking underlying FUTURES price to select OPTION...")
                logger.info(f"   📊 Underlying Futures: {UNDERLYING_SECURITY_ID} (for monitoring only)")
                logger.info(f"   📈 CE Option: {CE_OPTION_SECURITY_ID} (if underlying > ₹{UPPER_THRESHOLD})")
                logger.info(f"   📉 PE Option: {PE_OPTION_SECURITY_ID} (if underlying < ₹{LOWER_THRESHOLD})")
                
                # Fetch LTP for underlying (Crude Oil futures) - FOR DECISION ONLY
                logger.info(f"\n📡 Fetching UNDERLYING Crude Oil Futures price (Security ID: {UNDERLYING_SECURITY_ID})...")
                logger.info(f"   ⚠️ This is FUTURES price (e.g., ~₹5200-5300), used ONLY for CE/PE decision")
                underlying_ltp = fetch_underlying_ltp(dhan_client, UNDERLYING_SECURITY_ID)
                logger.info(f"📈 UNDERLYING Futures LTP: ₹{underlying_ltp:.2f} (for decision making only)")
                
                # Decision logic - select CE or PE option based on underlying price
                if underlying_ltp > UPPER_THRESHOLD:
                    state.option_type = "CE"
                    state.option_security_id = CE_OPTION_SECURITY_ID
                    state.option_symbol = f"CRUDEOIL CE (ID: {CE_OPTION_SECURITY_ID})"
                    logger.info(f"✅ DECISION: Underlying ({underlying_ltp:.2f}) > {UPPER_THRESHOLD} → BUY CE Option ({CE_OPTION_SECURITY_ID})")
                elif underlying_ltp < LOWER_THRESHOLD:
                    state.option_type = "PE"
                    state.option_security_id = PE_OPTION_SECURITY_ID
                    state.option_symbol = f"CRUDEOIL PE (ID: {PE_OPTION_SECURITY_ID})"
                    logger.info(f"✅ DECISION: Underlying ({underlying_ltp:.2f}) < {LOWER_THRESHOLD} → BUY PE Option ({PE_OPTION_SECURITY_ID})")
                else:
                    logger.info(f"⏳ WAITING: Underlying LTP={underlying_ltp:.2f}")
                    logger.info(f"   Need underlying > {UPPER_THRESHOLD} for CE or < {LOWER_THRESHOLD} for PE")
                    logger.info(f"   Sleeping for {API_SLEEP} seconds before next check...")
                    await asyncio.sleep(API_SLEEP)
                    continue
                
                logger.info(f"✅ Selected Option Contract: {state.option_symbol}")
                logger.info(f"   Security ID: {state.option_security_id}")
                logger.info(f"   Option Type: {state.option_type}")
            
            # Step 3: Fetch OPTION LTP (PREMIUM)
            logger.info(f"\n📡 Fetching OPTION PREMIUM for {state.option_symbol}...")
            logger.info(f"   ⚠️ This is OPTION price (e.g., ~₹21.9), used for entry/averaging/exit")
            option_ltp = fetch_option_ltp(dhan_client, state.option_security_id)
            logger.info(f"� OPTION PREMIUM (LTP): ₹{option_ltp:.2f} ← THIS is what we trade!")
            
            # Step 4: Initial Entry (split into 2 orders of 75 each)
            if not state.has_entered:
                logger.info("\n" + "="*80)
                logger.info("🚀 INITIAL ENTRY PHASE")
                logger.info("="*80)
                logger.info(f"📦 Total Quantity to Buy: {INITIAL_QUANTITY} units")
                logger.info(f"🔀 Split Strategy: {SPLIT_SIZE} + {SPLIT_SIZE} (2 orders)")
                logger.info(f"💵 OPTION PREMIUM (Entry Price): ₹{option_ltp:.2f}")
                logger.info(f"   Note: This is OPTION price (~₹21.9), NOT underlying futures price (~₹5250)")
                logger.info(f"💰 Estimated Cost: ₹{option_ltp * INITIAL_QUANTITY:.2f}")
                
                # First split order
                logger.info(f"\n📤 Placing FIRST split order ({SPLIT_SIZE} units)...")
                order_id_1, exec_price_1, exec_qty_1 = place_market_order(
                    dhan_client,
                    state.option_security_id,
                    SPLIT_SIZE,
                    dhan_client.BUY,
                    "INITIAL_BUY_1"
                )
                
                position_1 = Position(
                    order_id=order_id_1,
                    buy_price=exec_price_1 if exec_price_1 else option_ltp,
                    quantity=exec_qty_1 if exec_qty_1 > 0 else SPLIT_SIZE,
                    buy_time=datetime.now(),
                    reason="INITIAL_ENTRY"
                )
                state.add_position(position_1)
                logger.info(f"✅ First split order executed: {exec_qty_1} units @ ₹{exec_price_1:.2f}")
                
                # Second split order
                logger.info(f"\n📤 Placing SECOND split order ({SPLIT_SIZE} units)...")
                order_id_2, exec_price_2, exec_qty_2 = place_market_order(
                    dhan_client,
                    state.option_security_id,
                    SPLIT_SIZE,
                    dhan_client.BUY,
                    "INITIAL_BUY_2"
                )
                
                position_2 = Position(
                    order_id=order_id_2,
                    buy_price=exec_price_2 if exec_price_2 else option_ltp,
                    quantity=exec_qty_2 if exec_qty_2 > 0 else SPLIT_SIZE,
                    buy_time=datetime.now(),
                    reason="INITIAL_ENTRY"
                )
                state.add_position(position_2)
                logger.info(f"✅ Second split order executed: {exec_qty_2} units @ ₹{exec_price_2:.2f}")
                
                # Set initial target
                avg_entry_price = state.calculate_average_price()
                logger.info(f"\n📊 ENTRY SUMMARY:")
                logger.info(f"   Position 1: {exec_qty_1} units @ ₹{exec_price_1:.2f}")
                logger.info(f"   Position 2: {exec_qty_2} units @ ₹{exec_price_2:.2f}")
                logger.info(f"   Total Quantity: {state.total_quantity} units")
                logger.info(f"   Average Entry Price: ₹{avg_entry_price:.2f}")
                logger.info(f"   Total Investment: ₹{avg_entry_price * state.total_quantity:.2f}")
                
                state.update_target(avg_entry_price)
                state.has_entered = True
                
                logger.info(f"\n🎯 INITIAL TARGET SET:")
                logger.info(f"   Target Price: ₹{state.current_target:.2f}")
                logger.info(f"   Target Gap: +₹{TARGET_ADJUSTMENTS[0]:.2f}")
                logger.info(f"   Expected Profit at Target: ₹{(state.current_target - avg_entry_price) * state.total_quantity:.2f}")
                logger.info(f"\n✅ INITIAL ENTRY COMPLETE - Now monitoring for target or price drops...")
            
            # Step 5: Check for exit condition
            if option_ltp >= state.current_target:
                logger.info("\n" + "="*80)
                logger.info("🎯 TARGET HIT! INITIATING EXIT")
                logger.info("="*80)
                logger.info(f"   Current LTP: ₹{option_ltp:.2f}")
                logger.info(f"   Target Price: ₹{state.current_target:.2f}")
                logger.info(f"   Difference: +₹{option_ltp - state.current_target:.2f}")
                logger.info(f"\n🚪 Exiting ALL positions: {state.total_quantity} units")
                logger.info(f"   Average Buy Price: ₹{state.calculate_average_price():.2f}")
                logger.info(f"   Current Exit Price: ₹{option_ltp:.2f}")
                logger.info(f"   Expected Profit: ₹{(option_ltp - state.calculate_average_price()) * state.total_quantity:.2f}")
                
                # Place exit order
                logger.info(f"\n📤 Placing EXIT order for {state.total_quantity} units...")
                exit_order_id, exit_price, exit_qty = place_market_order(
                    dhan_client,
                    state.option_security_id,
                    state.total_quantity,
                    dhan_client.SELL,
                    "EXIT_ALL"
                )
                logger.info(f"✅ Exit order executed: {exit_qty} units @ ₹{exit_price:.2f}")
                
                # Calculate P&L
                avg_buy_price = state.calculate_average_price()
                effective_exit_price = exit_price if exit_price else option_ltp
                pnl = (effective_exit_price - avg_buy_price) * state.total_quantity
                pnl_percent = (pnl / (avg_buy_price * state.total_quantity)) * 100
                
                # Update cycle tracking
                state.cycle_count += 1
                state.cumulative_pnl += pnl
                
                logger.info("=" * 80)
                logger.info(f"📊 TRADE SUMMARY - CYCLE #{state.cycle_count} COMPLETE")
                logger.info("=" * 80)
                logger.info(f"Option: {state.option_symbol}")
                logger.info(f"Total Positions: {len(state.positions)}")
                logger.info(f"Total Quantity: {state.total_quantity}")
                logger.info(f"Average Buy Price: ₹{avg_buy_price:.2f}")
                logger.info(f"Exit Price: ₹{effective_exit_price:.2f}")
                logger.info(f"Cycle P&L: ₹{pnl:.2f} ({pnl_percent:.2f}%)")
                logger.info(f"Drop Count: {state.drop_count}")
                logger.info(f"Cumulative P&L (All Cycles): ₹{state.cumulative_pnl:.2f}")
                logger.info(f"Completed Cycles: {state.cycle_count}")
                logger.info("=" * 80)
                
                # Reset state for new cycle
                logger.info(f"🔄 RESETTING FOR CYCLE #{state.cycle_count + 1}...")
                state.positions.clear()
                state.last_buy_price = None
                state.current_target = None
                state.drop_count = 0
                state.has_entered = False
                state.total_quantity = 0
                # Keep option_type, option_security_id, cycle_count, and cumulative_pnl
                
                logger.info(f"✅ Cycle #{state.cycle_count} completed. Re-entering at current market price for Cycle #{state.cycle_count + 1}...")
                logger.info(f"💰 Session Stats: {state.cycle_count} cycles completed, Total P&L: ₹{state.cumulative_pnl:.2f}")
                
                # Continue to next iteration - will re-enter at current LTP
                await asyncio.sleep(API_SLEEP)
                continue
            
            # Step 6: Check for ₹1 drop and averaging down
            if state.last_buy_price:
                price_diff = state.last_buy_price - option_ltp
                logger.info(f"\n📊 OPTION PREMIUM MONITORING:")
                logger.info(f"   Last Buy Price (OPTION): ₹{state.last_buy_price:.2f}")
                logger.info(f"   Current OPTION LTP: ₹{option_ltp:.2f}")
                logger.info(f"   OPTION Price Drop: ₹{price_diff:.2f}")
                logger.info(f"   Drop Trigger: ₹{PRICE_DROP_TRIGGER:.2f} (in OPTION premium)")
                logger.info(f"   Current Target (OPTION): ₹{state.current_target:.2f}")
                
                if price_diff >= PRICE_DROP_TRIGGER:
                    state.drop_count += 1
                    logger.info("\n" + "="*80)
                    logger.info(f"📉 PRICE DROP DETECTED - DROP #{state.drop_count}")
                    logger.info("="*80)
                    logger.info(f"   Last Buy Price: ₹{state.last_buy_price:.2f}")
                    logger.info(f"   Current LTP: ₹{option_ltp:.2f}")
                    logger.info(f"   Drop Amount: ₹{price_diff:.2f}")
                    logger.info(f"   Total Drops So Far: {state.drop_count}")
                    logger.info(f"\n🔄 AVERAGING DOWN STRATEGY TRIGGERED")
                    logger.info(f"   Buying Additional: {AVERAGING_QUANTITY} units")
                    logger.info(f"   Current Total Quantity: {state.total_quantity} units")
                    logger.info(f"   New Total After Buy: {state.total_quantity + AVERAGING_QUANTITY} units")
                    
                    # Place averaging down order
                    logger.info(f"\n📤 Placing AVERAGING DOWN order #{state.drop_count}...")
                    order_id, exec_price, exec_qty = place_market_order(
                        dhan_client,
                        state.option_security_id,
                        AVERAGING_QUANTITY,
                        dhan_client.BUY,
                        f"AVERAGING_DOWN_{state.drop_count}"
                    )
                    logger.info(f"✅ Averaging order executed: {exec_qty} units @ ₹{exec_price:.2f}")
                    
                    position = Position(
                        order_id=order_id,
                        buy_price=exec_price if exec_price else option_ltp,
                        quantity=exec_qty if exec_qty > 0 else AVERAGING_QUANTITY,
                        buy_time=datetime.now(),
                        reason=f"AVERAGING_DOWN_{state.drop_count}"
                    )
                    old_avg = state.calculate_average_price()
                    state.add_position(position)
                    
                    # Update target
                    old_target = state.current_target
                    state.update_target(option_ltp)
                    
                    avg_price = state.calculate_average_price()
                    logger.info(f"\n📊 AVERAGING DOWN SUMMARY:")
                    logger.info(f"   Previous Avg Price: ₹{old_avg:.2f}")
                    logger.info(f"   New Avg Price: ₹{avg_price:.2f}")
                    logger.info(f"   Avg Price Change: ₹{avg_price - old_avg:.2f}")
                    logger.info(f"   Total Positions: {len(state.positions)}")
                    logger.info(f"   Total Quantity: {state.total_quantity} units")
                    logger.info(f"   Total Investment: ₹{avg_price * state.total_quantity:.2f}")
                    logger.info(f"\n🎯 TARGET ADJUSTED:")
                    logger.info(f"   Old Target: ₹{old_target:.2f}")
                    logger.info(f"   New Target: ₹{state.current_target:.2f}")
                    logger.info(f"   Target Gap: ₹{TARGET_ADJUSTMENTS.get(state.drop_count, 0.30):.2f}")
                    logger.info(f"   Expected Profit at New Target: ₹{(state.current_target - avg_price) * state.total_quantity:.2f}")
                    logger.info(f"\n✅ AVERAGING DOWN COMPLETE - Continuing to monitor...")
                else:
                    logger.info(f"   ✅ No drop trigger - Price difference (₹{price_diff:.2f}) < Trigger (₹{PRICE_DROP_TRIGGER:.2f})")
            
            # Sleep before next poll
            logger.info(f"\n⏸️  Sleeping for {API_SLEEP} seconds before next poll...")
            await asyncio.sleep(API_SLEEP)
            
        except KeyboardInterrupt:
            logger.info("⚠️ KeyboardInterrupt received. Stopping bot...")
            logger.info("=" * 80)
            logger.info("📊 FINAL SESSION SUMMARY")
            logger.info("=" * 80)
            logger.info(f"Total Cycles Completed: {state.cycle_count}")
            logger.info(f"Cumulative P&L: ₹{state.cumulative_pnl:.2f}")
            if state.cycle_count > 0:
                avg_pnl_per_cycle = state.cumulative_pnl / state.cycle_count
                logger.info(f"Average P&L per Cycle: ₹{avg_pnl_per_cycle:.2f}")
            logger.info("=" * 80)
            break
        except Exception as e:
            logger.error(f"❌ Error in trading loop: {e}", exc_info=True)
            await asyncio.sleep(API_SLEEP)


# =============================================================================
# Entry Point
# =============================================================================

async def main():
    """Entry point"""
    try:
        dhan_client = create_dhan_client()
        await run_trading_bot(dhan_client)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
