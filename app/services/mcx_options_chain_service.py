"""
MCX Options Chain Service (WebSocket-based)

Builds a live options chain for a single MCX commodity and nearest expiry
using DHAN's WebSocket market feed (DhanMarketFeed) and the local
mcx_securities_full.csv instruments file.

Data provided per strike (CE/PE):
- LTP
- Change / Change % (from previous close)
- Volume
- Open Interest (OI)
- OI Change (vs previous OI)

NOTE:
- Greeks and IV are NOT available from WebSocket, so they are set to 0.
- Best Bid/Ask are not parsed from depth packets for now; set to 0.
"""

import asyncio
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Callable, Dict, Optional

import pandas as pd
from dhanhq import dhanhq

from app.core.config import settings
from app.services.dhan_market_feed import DhanMarketFeed

logger = logging.getLogger(__name__)

# Path to pre-fetched MCX instruments CSV
# __file__ = app/services/mcx_options_chain_service.py
# project root = parent of "app"
MCX_INSTRUMENTS_CSV = (
    Path(__file__).resolve().parents[2] / "scripts" / "mcx_securities_full.csv"
)

# Map UI commodity names to SM_SYMBOL_NAME in instruments file
COMMODITY_SYMBOLS: Dict[str, str] = {
    "CRUDEOIL": "CRUDEOIL",
    "GOLD": "GOLD",
    "SILVER": "SILVER",
    "NATURALGAS": "NATURALGAS",
    "COPPER": "COPPER",
    "ZINC": "ZINC",
}

# Approximate tick / strike steps & lot sizes (can be refined from CSV if needed)
COMMODITY_META: Dict[str, Dict] = {
    "CRUDEOIL": {"name": "Crude Oil", "step": 10, "lot_size": 100},
    "GOLD": {"name": "Gold", "step": 100, "lot_size": 100},
    "SILVER": {"name": "Silver", "step": 100, "lot_size": 30000},
    "NATURALGAS": {"name": "Natural Gas", "step": 5, "lot_size": 1250},
    "COPPER": {"name": "Copper", "step": 5, "lot_size": 1000},
    "ZINC": {"name": "Zinc", "step": 2.5, "lot_size": 5000},
}


class MCXOptionsChainService:
    """Build and stream MCX options chain using DHAN WebSocket feed"""

    def __init__(
        self,
        commodity: str = "GOLD",
        strikes_each_side: int = 10,
        send_callback: Optional[Callable] = None,
    ) -> None:
        self.commodity = commodity.upper()
        if self.commodity not in COMMODITY_SYMBOLS:
            raise ValueError(
                f"Unsupported commodity: {commodity}. Supported: {list(COMMODITY_SYMBOLS.keys())}"
            )

        self.strikes_each_side = strikes_each_side
        self.send_callback = send_callback

        self.running: bool = False
        self.task: Optional[asyncio.Task] = None

        # Instruments & mappings
        self.selected_expiry: Optional[str] = None
        self.underlying_security_id: Optional[str] = None
        self.option_security_ids: Dict[str, Dict] = {}  # sec_id -> {strike, side}

        # Aggregated data structures
        self.spot_price: float = 0.0
        self.strike_data: Dict[float, Dict] = {}  # strike -> {"ce": {...}, "pe": {...}}

        # DHAN WebSocket feed client
        self.feed: Optional[DhanMarketFeed] = None

        # Snapshot interval (seconds) - set to 1.0 for tick-by-tick updates
        self.snapshot_interval: float = 1.0

        logger.info(
            "🏭 Initialized MCXOptionsChainService for %s",
            COMMODITY_META[self.commodity]["name"],
        )

    async def start(self) -> None:
        """Start service: prepare contracts, connect DHAN feed, start snapshot loop."""
        if self.running:
            logger.warning("MCXOptionsChainService already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info("✅ Started MCXOptionsChainService for %s", self.commodity)

    async def stop(self) -> None:
        """Stop service and disconnect from DHAN feed."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        if self.feed and self.feed.is_connected:
            try:
                await self.feed.disconnect()
            except Exception as e:
                logger.error("Error disconnecting DHAN feed: %s", e)

        logger.info("🛑 Stopped MCXOptionsChainService for %s", self.commodity)

    # ------------------------------------------------------------------
    # Core run loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        try:
            # 1) Prepare option contracts from instruments CSV
            prepared = await self._prepare_contracts()
            if not prepared:
                return

            # 2) Connect to DHAN WebSocket feed
            connected = await self._connect_and_subscribe()
            if not connected:
                return

            # 3) Periodic snapshot loop
            logger.info(
                "🔄 Starting MCX options chain snapshot loop (every %.1f seconds)...",
                self.snapshot_interval,
            )
            while self.running:
                try:
                    snapshot = self._build_snapshot()
                    if self.send_callback and snapshot["rows"]:
                        await self.send_callback(snapshot)
                        logger.info(
                            "📤 Sent MCX snapshot: %d strikes, spot=%.2f",
                            len(snapshot["rows"]),
                            snapshot["spot"],
                        )
                except Exception as e:
                    logger.error("Error building/sending snapshot: %s", e, exc_info=True)
                await asyncio.sleep(self.snapshot_interval)

        except Exception as e:
            logger.error("❌ Error in MCXOptionsChainService: %s", e, exc_info=True)

    # ------------------------------------------------------------------
    # Instrument preparation
    # ------------------------------------------------------------------

    async def _prepare_contracts(self) -> bool:
        """Load instruments file and prepare option contracts for one expiry."""
        try:
            if not MCX_INSTRUMENTS_CSV.exists():
                await self._send_error(
                    "MCX Instruments File Missing",
                    f"Expected instruments file not found at {MCX_INSTRUMENTS_CSV}.\n"
                    "Run scripts/fetch_mcx_detailed.py to generate mcx_securities_full.csv.",
                )
                return False

            df = pd.read_csv(MCX_INSTRUMENTS_CSV)
            if df.empty:
                await self._send_error(
                    "MCX Instruments Empty",
                    "mcx_securities_full.csv is empty. Cannot build options chain.",
                )
                return False

            symbol = COMMODITY_SYMBOLS[self.commodity]

            # Filter for this commodity's options (OPTFUT) in MCX segment 'M'
            opt_df = df[
                (df["SEM_EXM_EXCH_ID"] == "MCX")
                & (df["SEM_SEGMENT"] == "M")
                & (df["SEM_INSTRUMENT_NAME"] == "OPTFUT")
                & (df["SM_SYMBOL_NAME"] == symbol)
            ].copy()

            if opt_df.empty:
                await self._send_error(
                    "No MCX Options",
                    f"No MCX option contracts found for {symbol} in instruments file.",
                )
                return False

            # Parse expiry dates and choose nearest expiry >= today
            opt_df["EXP_DATE"] = pd.to_datetime(opt_df["SEM_EXPIRY_DATE"]).dt.date
            today = date.today()
            future_expiries = sorted({d for d in opt_df["EXP_DATE"].unique() if d >= today})
            if future_expiries:
                target_expiry = future_expiries[0]
            else:
                # Fallback: earliest expiry in file
                target_expiry = sorted(opt_df["EXP_DATE"].unique())[0]

            exp_df = opt_df[opt_df["EXP_DATE"] == target_expiry].copy()
            if exp_df.empty:
                await self._send_error(
                    "No Contracts For Expiry",
                    f"No option contracts for {symbol} on {target_expiry}.",
                )
                return False

            self.selected_expiry = target_expiry.isoformat()
            logger.info(
                "📅 Using MCX options expiry %s for %s (contracts: %d)",
                self.selected_expiry,
                symbol,
                len(exp_df),
            )

            # Build option security mapping and per-strike structure
            self.option_security_ids.clear()
            self.strike_data.clear()

            for _, row in exp_df.iterrows():
                sec_id = str(int(row["SEM_SMST_SECURITY_ID"]))
                strike = float(row["SEM_STRIKE_PRICE"])
                opt_type = str(row["SEM_OPTION_TYPE"]).upper()  # CE / PE

                if opt_type not in ("CE", "PE"):
                    continue

                side = "ce" if opt_type == "CE" else "pe"
                self.option_security_ids[sec_id] = {"strike": strike, "side": side}

                if strike not in self.strike_data:
                    self.strike_data[strike] = {
                        "ce": self._empty_side(),
                        "pe": self._empty_side(),
                    }

            if not self.option_security_ids:
                await self._send_error(
                    "No Option Contracts",
                    f"Found no CE/PE option contracts for {symbol} on {self.selected_expiry}.",
                )
                return False

            # Find nearest futures contract as underlying (FUTCOM)
            fut_df = df[
                (df["SEM_EXM_EXCH_ID"] == "MCX")
                & (df["SEM_SEGMENT"] == "M")
                & (df["SEM_INSTRUMENT_NAME"] == "FUTCOM")
                & (df["SM_SYMBOL_NAME"] == symbol)
            ].copy()

            if not fut_df.empty:
                fut_df["EXP_DATE"] = pd.to_datetime(fut_df["SEM_EXPIRY_DATE"]).dt.date
                fut_future_expiries = sorted({d for d in fut_df["EXP_DATE"].unique() if d >= today})
                if fut_future_expiries:
                    fut_target = fut_future_expiries[0]
                else:
                    fut_target = sorted(fut_df["EXP_DATE"].unique())[0]

                fut_row = fut_df[fut_df["EXP_DATE"] == fut_target].iloc[0]
                self.underlying_security_id = str(int(fut_row["SEM_SMST_SECURITY_ID"]))
                logger.info(
                    "🔗 Underlying FUTCOM for %s: %s (sec_id=%s, expiry=%s)",
                    symbol,
                    fut_row["SEM_TRADING_SYMBOL"],
                    self.underlying_security_id,
                    fut_target,
                )
            else:
                logger.warning("No FUTCOM underlying found for %s", symbol)
                self.underlying_security_id = None

            return True

        except Exception as e:
            logger.error("Error preparing MCX contracts: %s", e, exc_info=True)
            await self._send_error(
                "MCX Instruments Error",
                f"Failed to prepare MCX contracts: {e}",
            )
            return False

    # ------------------------------------------------------------------
    # DHAN WebSocket integration
    # ------------------------------------------------------------------

    async def _connect_and_subscribe(self) -> bool:
        """Connect to DHAN feed and subscribe to option + underlying contracts."""
        try:
            if not settings.DHAN_MASTER_CLIENT_ID or not settings.DHAN_MASTER_ACCESS_TOKEN:
                await self._send_error(
                    "DHAN Credentials Missing",
                    "DHAN_MASTER_CLIENT_ID / DHAN_MASTER_ACCESS_TOKEN not configured in .env.",
                )
                return False

            self.feed = DhanMarketFeed(
                client_id=settings.DHAN_MASTER_CLIENT_ID,
                access_token=settings.DHAN_MASTER_ACCESS_TOKEN,
            )

            ok = await self.feed.connect()
            if not ok or not self.feed.is_connected:
                await self._send_error(
                    "DHAN Feed Connection Failed",
                    "Could not connect to DHAN WebSocket market feed.",
                )
                return False

            # Register callback for market data
            async def on_market_data(data: Dict) -> None:
                await self._handle_market_data(data)

            self.feed.on_message(on_market_data)

            # Build instruments list for subscription
            all_sec_ids = list(self.option_security_ids.keys())
            if self.underlying_security_id:
                all_sec_ids.append(self.underlying_security_id)

            instruments = [
                {"ExchangeSegment": dhanhq.MCX, "SecurityId": sec_id}
                for sec_id in all_sec_ids
            ]

            logger.info(
                "📡 Subscribing to %d MCX option contracts (commodity=%s)",
                len(all_sec_ids),
                self.commodity,
            )

            subscribed = await self.feed.subscribe_instruments(instruments, mode="full")
            if not subscribed:
                await self._send_error(
                    "Subscription Failed",
                    "Failed to subscribe to MCX option contracts on DHAN feed.",
                )
                return False

            return True

        except Exception as e:
            logger.error("Error connecting/subscribing to DHAN feed: %s", e, exc_info=True)
            await self._send_error(
                "DHAN Feed Error",
                f"Error connecting/subscribing to DHAN feed: {e}",
            )
            return False

    # ------------------------------------------------------------------
    # Market data handling & snapshot building
    # ------------------------------------------------------------------

    async def _handle_market_data(self, data: Dict) -> None:
        """Update internal state based on incoming market data packet."""
        try:
            sec_id = str(data.get("security_id")) if data.get("security_id") is not None else None
            if not sec_id:
                return

            pkt_type = data.get("type")

            # Underlying future spot price
            if self.underlying_security_id and sec_id == self.underlying_security_id:
                ltp = data.get("ltp")
                if isinstance(ltp, (int, float)):
                    self.spot_price = float(ltp)
                return

            # Option contract updates
            contract = self.option_security_ids.get(sec_id)
            if not contract:
                return

            strike = contract["strike"]
            side = contract["side"]  # "ce" or "pe"

            if strike not in self.strike_data:
                # Should not happen, but guard anyway
                self.strike_data[strike] = {"ce": self._empty_side(), "pe": self._empty_side()}

            entry = self.strike_data[strike][side]

            # Quote / Full data: prices, volume, change, best bid/ask
            if pkt_type in ("quote", "full"):
                ltp = data.get("ltp")
                if isinstance(ltp, (int, float)):
                    entry["ltp"] = float(ltp)

                # Change vs previous close (already computed in DhanMarketFeed)
                chg = data.get("change")
                if isinstance(chg, (int, float)):
                    entry["chg"] = float(chg)

                chg_pct = data.get("change_percent")
                if isinstance(chg_pct, (int, float)):
                    entry["chg_pct"] = float(chg_pct)

                vol = data.get("volume")
                if isinstance(vol, (int, float)):
                    entry["vol"] = int(vol)

                # Best bid / ask from full packet (if available)
                bid = data.get("best_bid_price")
                if isinstance(bid, (int, float)):
                    entry["bid"] = float(bid)

                ask = data.get("best_ask_price")
                if isinstance(ask, (int, float)):
                    entry["ask"] = float(ask)

            # OI packet: open interest
            if pkt_type == "oi":
                oi = data.get("oi")
                if isinstance(oi, (int, float)):
                    entry["oi"] = int(oi)

                    # Try to compute OI change vs previous OI from prev_close_data
                    if self.feed is not None:
                        exch_seg = data.get("exchange_segment")
                        key = f"{exch_seg}:{sec_id}"
                        prev_info = self.feed.prev_close_data.get(key, {})
                        prev_oi = prev_info.get("prev_oi", 0)
                        if isinstance(prev_oi, (int, float)):
                            entry["oi_chg"] = int(oi) - int(prev_oi)

        except Exception as e:
            logger.error("Error handling MCX market data: %s", e, exc_info=True)

    def _build_snapshot(self) -> Dict:
        """Build full option chain snapshot from current state."""
        rows = []

        if not self.strike_data:
            return {
                "type": "snapshot",
                "commodity": self.commodity,
                "name": COMMODITY_META[self.commodity]["name"],
                "expiry": self.selected_expiry,
                "spot": self.spot_price,
                "lot_size": COMMODITY_META[self.commodity]["lot_size"],
                "ts": datetime.now().isoformat(),
                "rows": [],
            }

        # Determine ATM strike based on current spot price
        all_strikes = sorted(self.strike_data.keys())
        if not all_strikes:
            selected_strikes = []
        else:
            if self.spot_price and self.spot_price > 0:
                atm_strike = min(all_strikes, key=lambda s: abs(s - self.spot_price))
            else:
                # Fallback: middle strike if spot not available yet
                atm_strike = all_strikes[len(all_strikes) // 2]

            try:
                atm_index = all_strikes.index(atm_strike)
            except ValueError:
                atm_index = len(all_strikes) // 2

            start_idx = max(0, atm_index - self.strikes_each_side)
            end_idx = min(len(all_strikes), atm_index + self.strikes_each_side + 1)
            selected_strikes = all_strikes[start_idx:end_idx]

        for strike in selected_strikes:
            data = self.strike_data[strike]
            ce = data["ce"]
            pe = data["pe"]

            row = {
                "strike": strike,
                "ce": ce,
                "pe": pe,
            }
            rows.append(row)

        snapshot = {
            "type": "snapshot",
            "commodity": self.commodity,
            "name": COMMODITY_META[self.commodity]["name"],
            "expiry": self.selected_expiry,
            "spot": self.spot_price,
            "lot_size": COMMODITY_META[self.commodity]["lot_size"],
            "ts": datetime.now().isoformat(),
            "rows": rows,
        }
        return snapshot

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _empty_side(self) -> Dict:
        """Return an empty side dict matching the options-chain UI schema."""
        return {
            "ltp": 0.0,
            "chg": 0.0,
            "chg_pct": 0.0,
            "oi": 0,
            "oi_chg": 0,
            "vol": 0,
            "bid": 0.0,
            "ask": 0.0,
            "iv": 0.0,
            "greeks": {},
        }

    async def _send_error(self, message: str, details: str) -> None:
        """Send an error payload to client if callback is set."""
        logger.error("MCXOptionsChainService error: %s - %s", message, details)
        if not self.send_callback:
            return

        payload = {
            "type": "error",
            "commodity": self.commodity,
            "message": message,
            "details": details,
            "ts": datetime.now().isoformat(),
        }
        try:
            await self.send_callback(payload)
        except Exception as e:
            logger.error("Error sending MCX error payload: %s", e, exc_info=True)
