"""
Commodity Options Chain Service
Fetches real-time commodity options data from DHAN API for MCX traded commodities

NOTE: As of now, DHAN's option_chain API does not support MCX commodities.
This service is designed for future compatibility when MCX support is added.
For now, it will return an error message explaining the limitation.

Alternative: Use WebSocket feed to subscribe to individual MCX option contracts.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable
from dhanhq import dhanhq
from app.core.config import settings

logger = logging.getLogger(__name__)

# MCX Commodity Underlying Mapping
# Security IDs fetched from DHAN API (nearest futures contracts)
# Exchange segment 'M' represents MCX
COMMODITY_UNDERLYING = {
    "CRUDEOIL": {
        "name": "Crude Oil",
        "security_id": 462523,  # CRUDEOIL-18Dec2025-FUT
        "exchange_segment": "M",
        "step": 10,  # Strike price step
        "lot_size": 100
    },
    "GOLD": {
        "name": "Gold",
        "security_id": 467742,  # GOLDTEN-28Nov2025-FUT
        "exchange_segment": "M",
        "step": 100,
        "lot_size": 100
    },
    "SILVER": {
        "name": "Silver",
        "security_id": 440938,  # SILVERM-28Nov2025-FUT
        "exchange_segment": "M",
        "step": 100,
        "lot_size": 30000
    },
    "NATURALGAS": {
        "name": "Natural Gas",
        "security_id": 458147,  # NATURALGAS-24Nov2025-FUT
        "exchange_segment": "M",
        "step": 5,
        "lot_size": 1250
    },
    "COPPER": {
        "name": "Copper",
        "security_id": 463272,  # COPPER-28Nov2025-FUT
        "exchange_segment": "M",
        "step": 5,
        "lot_size": 1000
    },
    "ZINC": {
        "name": "Zinc",
        "security_id": 463277,  # ZINC-28Nov2025-FUT
        "exchange_segment": "M",
        "step": 2.5,
        "lot_size": 5000
    }
}


class CommodityOptionsService:
    """Service to fetch and stream commodity options chain data from DHAN API"""
    
    def __init__(
        self,
        commodity: str = "CRUDEOIL",
        strikes_each_side: int = 10,
        send_callback: Optional[Callable] = None
    ):
        """
        Initialize commodity options service
        
        Args:
            commodity: Commodity name (CRUDEOIL, GOLD, SILVER, etc.)
            strikes_each_side: Number of strikes to show on each side of ATM
            send_callback: Async callback to send snapshots to client
        """
        self.commodity = commodity.upper()
        if self.commodity not in COMMODITY_UNDERLYING:
            raise ValueError(f"Unsupported commodity: {commodity}. Supported: {list(COMMODITY_UNDERLYING.keys())}")
        
        self.strikes_each_side = strikes_each_side
        self.send_callback = send_callback
        self.running = False
        self.selected_expiry = None
        self.task = None
        
        logger.info(f"🏭 Initialized CommodityOptionsService for {COMMODITY_UNDERLYING[self.commodity]['name']}")
    
    async def start(self):
        """Start the commodity options chain service"""
        if self.running:
            logger.warning("Service already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._fetch_and_stream())
        logger.info(f"✅ Started commodity options service for {self.commodity}")
    
    async def stop(self):
        """Stop the commodity options chain service"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info(f"🛑 Stopped commodity options service for {self.commodity}")
    
    async def _fetch_and_stream(self):
        """Main loop to fetch and stream commodity options data"""
        try:
            # Initialize Dhan REST API client
            dhan = dhanhq(settings.DHAN_MASTER_CLIENT_ID, settings.DHAN_MASTER_ACCESS_TOKEN)
            
            logger.info(f"📊 Attempting to fetch commodity options chain for {self.commodity}...")
            logger.info(f"Using Security ID: {COMMODITY_UNDERLYING[self.commodity]['security_id']}")
            
            # Send error message to client
            error_message = {
                "type": "error",
                "commodity": self.commodity,
                "message": "MCX Commodity Options Not Supported",
                "details": (
                    f"DHAN's option_chain API currently does not support MCX commodity options for {COMMODITY_UNDERLYING[self.commodity]['name']}. "
                    "The API is designed for NSE equity options (NIFTY, BANKNIFTY, etc.). "
                    "\n\nAlternative approaches:"
                    "\n1. Use DHAN WebSocket to subscribe to individual MCX option contracts"
                    "\n2. Use NSE commodity derivatives if available"
                    "\n3. Wait for DHAN to add MCX support to the option_chain API"
                    f"\n\nWe found {len([1 for c in ['CRUDEOIL', 'GOLD', 'SILVER', 'NATURALGAS', 'COPPER', 'ZINC']])} MCX commodities with option contracts, "
                    "but they cannot be accessed via the option_chain endpoint at this time."
                ),
                "ts": datetime.now().isoformat()
            }
            
            if self.send_callback:
                await self.send_callback(error_message)
            
            logger.warning(f"⚠️ MCX commodity options not supported by DHAN option_chain API")
            logger.info(f"💡 Alternative: Use WebSocket to subscribe to individual option contracts")
            return
            
            # The code below is kept for future when MCX support is added
            # Get expiry list for the commodity
            expiry_response = dhan.expiry_list(
                under_security_id=COMMODITY_UNDERLYING[self.commodity]["security_id"],
                under_exchange_segment=COMMODITY_UNDERLYING[self.commodity]["exchange_segment"]
            )
            
            logger.info(f"📋 Expiry list response: {expiry_response}")
            
            if not expiry_response or expiry_response.get("status") != "success":
                logger.error(f"❌ Failed to get expiry list: {expiry_response}")
                return
            
            # Parse expiry dates
            expiry_dates = expiry_response.get("data", {})
            if isinstance(expiry_dates, dict):
                expiry_dates = expiry_dates.get("data", [])
            
            if not expiry_dates or not isinstance(expiry_dates, list):
                logger.error(f"❌ No expiry dates available for {self.commodity}")
                return
            
            self.selected_expiry = expiry_dates[0]  # Use nearest expiry
            logger.info(f"📅 Using expiry: {self.selected_expiry}")
            
            # Start polling loop - fetch option chain every 1 second
            logger.info("🔄 Starting commodity options chain polling (every 1 second)...")
            while self.running:
                try:
                    # Fetch fresh option chain data
                    chain_response = dhan.option_chain(
                        under_security_id=COMMODITY_UNDERLYING[self.commodity]["security_id"],
                        under_exchange_segment=COMMODITY_UNDERLYING[self.commodity]["exchange_segment"],
                        expiry=self.selected_expiry
                    )
                    
                    if not chain_response or chain_response.get("status") != "success":
                        logger.error(f"❌ Failed to get option chain: {chain_response}")
                        await asyncio.sleep(1)
                        continue
                    
                    # Parse option chain data
                    chain_data = chain_response.get("data", {})
                    if "data" in chain_data and isinstance(chain_data["data"], dict):
                        chain_data = chain_data["data"]
                    
                    spot_price = chain_data.get("last_price", 0)
                    oc_dict = chain_data.get("oc", {})
                    
                    if not oc_dict:
                        logger.error(f"❌ No option chain data in response")
                        await asyncio.sleep(1)
                        continue
                    
                    # Calculate strike range
                    step = COMMODITY_UNDERLYING[self.commodity]["step"]
                    atm_strike = round(spot_price / step) * step if spot_price > 0 else 0
                    min_strike = atm_strike - (self.strikes_each_side * step)
                    max_strike = atm_strike + (self.strikes_each_side * step)
                    
                    # Build and send snapshot
                    await self._build_snapshot_from_chain(oc_dict, spot_price, min_strike, max_strike)
                    
                    # Wait 1 second before next fetch
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Error in polling loop: {e}", exc_info=True)
                    await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"❌ Error in commodity options service: {e}", exc_info=True)
    
    async def _build_snapshot_from_chain(self, oc_dict: dict, spot_price: float, min_strike: float, max_strike: float):
        """Build and send snapshot from option chain data"""
        try:
            rows = []
            
            # Iterate through strikes
            for strike_str, strike_data in oc_dict.items():
                try:
                    strike = float(strike_str)
                    
                    # Filter by strike range
                    if strike < min_strike or strike > max_strike:
                        continue
                    
                    ce_data = strike_data.get("ce", {})
                    pe_data = strike_data.get("pe", {})
                    
                    # Build row data with all available fields
                    row = {
                        "strike": strike,
                        "ce": {
                            "ltp": ce_data.get("last_price", 0),
                            "chg": ce_data.get("last_price", 0) - ce_data.get("previous_close_price", 0),
                            "chg_pct": ((ce_data.get("last_price", 0) - ce_data.get("previous_close_price", 1)) / ce_data.get("previous_close_price", 1) * 100) if ce_data.get("previous_close_price", 0) > 0 else 0,
                            "oi": ce_data.get("oi", 0),
                            "oi_chg": ce_data.get("oi", 0) - ce_data.get("previous_oi", 0),
                            "vol": ce_data.get("volume", 0),
                            "bid": ce_data.get("top_bid_price", 0),
                            "ask": ce_data.get("top_ask_price", 0),
                            "iv": ce_data.get("implied_volatility", 0),
                            "greeks": ce_data.get("greeks", {})
                        },
                        "pe": {
                            "ltp": pe_data.get("last_price", 0),
                            "chg": pe_data.get("last_price", 0) - pe_data.get("previous_close_price", 0),
                            "chg_pct": ((pe_data.get("last_price", 0) - pe_data.get("previous_close_price", 1)) / pe_data.get("previous_close_price", 1) * 100) if pe_data.get("previous_close_price", 0) > 0 else 0,
                            "oi": pe_data.get("oi", 0),
                            "oi_chg": pe_data.get("oi", 0) - pe_data.get("previous_oi", 0),
                            "vol": pe_data.get("volume", 0),
                            "bid": pe_data.get("top_bid_price", 0),
                            "ask": pe_data.get("top_ask_price", 0),
                            "iv": pe_data.get("implied_volatility", 0),
                            "greeks": pe_data.get("greeks", {})
                        }
                    }
                    rows.append(row)
                    
                except (ValueError, KeyError) as e:
                    continue
            
            # Sort by strike
            rows.sort(key=lambda x: x["strike"])
            
            # Build and send snapshot
            snapshot = {
                "type": "snapshot",
                "commodity": self.commodity,
                "name": COMMODITY_UNDERLYING[self.commodity]["name"],
                "expiry": self.selected_expiry,
                "spot": spot_price,
                "lot_size": COMMODITY_UNDERLYING[self.commodity]["lot_size"],
                "ts": datetime.now().isoformat(),
                "rows": rows
            }
            
            if self.send_callback:
                await self.send_callback(snapshot)
                logger.info(f"📤 Sent commodity snapshot: {len(rows)} strikes, spot={spot_price:.2f}")
            
        except Exception as e:
            logger.error(f"❌ Error building snapshot: {e}", exc_info=True)
