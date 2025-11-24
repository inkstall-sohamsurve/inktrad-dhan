import asyncio
import logging
import struct
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional

import websockets
from dhanhq import dhanhq
from app.core.config import settings

logger = logging.getLogger(__name__)


SUBSCRIBE_TICKER = 15
SUBSCRIBE_QUOTE = 16
SUBSCRIBE_FULL = 17
UNSUBSCRIBE = 11
DISCONNECT = 12

RESPONSE_TICKER = 2
RESPONSE_QUOTE = 4
RESPONSE_FULL = 8
RESPONSE_PREV_CLOSE = 6
RESPONSE_OI = 5

# Index configurations for Dhan option chain API
INDEX_UNDERLYING = {
    "NIFTY": {
        "security_id": 13,  # Nifty (must be int, not string)
        "step": 50,
        "exchange_segment": "IDX_I"
    },
    "BANKNIFTY": {
        "security_id": 25,  # BankNifty (must be int, not string)
        "step": 100,
        "exchange_segment": "IDX_I"
    }
}


@dataclass
class Contract:
    sec_id: str
    index: str
    strike: int
    option_type: str  # CE/PE
    expiry: str


def _json(obj: Dict) -> str:
    import json
    return json.dumps(obj)


class OptionsChainService:
    def __init__(self, index: str, strikes_each_side: int, send_callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        self.index = index
        self.strikes_each_side = strikes_each_side
        self.send_callback = send_callback
        self.ws = None
        self.is_connected = False
        self.ws_url = (
            f"wss://api-feed.dhan.co?version=2&token={settings.DHAN_MASTER_ACCESS_TOKEN}"
            f"&clientId={settings.DHAN_MASTER_CLIENT_ID}&authType=2"
        )
        self.contracts: Dict[str, Contract] = {}
        self.prev_close: Dict[str, float] = {}
        self.prev_oi: Dict[str, int] = {}
        self.oi: Dict[str, int] = {}
        self.quote: Dict[str, Dict] = {}
        self.underlying_ltp: Dict[str, float] = {}
        self.selected_expiry: Optional[str] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._snapshot_task: Optional[asyncio.Task] = None

    async def start(self):
        await self._connect()
        await self._subscribe_underlying()
        await self._build_and_subscribe_chain()
        self._listen_task = asyncio.create_task(self._listen())
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())

    async def stop(self):
        try:
            if self._snapshot_task:
                self._snapshot_task.cancel()
            if self._listen_task:
                self._listen_task.cancel()
        except Exception:
            pass
        await self._disconnect()

    async def _connect(self):
        self.ws = await websockets.connect(self.ws_url, ping_interval=20, ping_timeout=10)
        self.is_connected = True

    async def _disconnect(self):
        if self.ws and self.is_connected:
            try:
                await self.ws.send(_json({"RequestCode": DISCONNECT}))
            except Exception:
                pass
            try:
                await self.ws.close()
            except Exception:
                pass
            self.is_connected = False

    async def _subscribe(self, instruments: List[Dict], request_code: int):
        batch = 100
        for i in range(0, len(instruments), batch):
            part = instruments[i:i + batch]
            msg = {
                "RequestCode": request_code,
                "InstrumentCount": len(part),
                "InstrumentList": part,
            }
            await self.ws.send(_json(msg))
            await asyncio.sleep(0.05)

    async def _build_snapshot_from_chain(self, oc_dict: dict, spot_ltp: float, min_strike: int, max_strike: int):
        """Build and send snapshot from option chain data"""
        try:
            rows = []
            
            # Iterate through strikes
            for strike_str, strike_data in oc_dict.items():
                try:
                    strike = int(float(strike_str))
                    
                    # Filter by strike range
                    if strike < min_strike or strike > max_strike:
                        continue
                    
                    ce_data = strike_data.get("ce", {})
                    pe_data = strike_data.get("pe", {})
                    
                    # Build row data
                    row = {
                        "strike": strike,
                        "ce": {
                            "ltp": ce_data.get("ltp", 0),
                            "chg": ce_data.get("chg", 0),
                            "chg_pct": ce_data.get("chg_pct", 0),
                            "oi": ce_data.get("oi", 0),
                            "oi_chg": ce_data.get("oi_chg", 0),
                            "vol": ce_data.get("volume", 0),
                        },
                        "pe": {
                            "ltp": pe_data.get("ltp", 0),
                            "chg": pe_data.get("chg", 0),
                            "chg_pct": pe_data.get("chg_pct", 0),
                            "oi": pe_data.get("oi", 0),
                            "oi_chg": pe_data.get("oi_chg", 0),
                            "vol": pe_data.get("volume", 0),
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
                "index": self.index,
                "expiry": self.selected_expiry,
                "spot": spot_ltp,
                "ts": datetime.now().isoformat(),
                "rows": rows
            }
            
            if self.send_callback:
                await self.send_callback(snapshot)
                logger.info(f"📤 Sent snapshot: {len(rows)} strikes, spot={spot_ltp:.2f}")
            
        except Exception as e:
            logger.error(f"❌ Error building snapshot: {e}", exc_info=True)

    async def _build_and_subscribe_chain(self):
        """Fetch option chain from DHAN API - poll every 3 seconds for updates"""
        try:
            # Initialize Dhan REST API client
            dhan = dhanhq(settings.DHAN_MASTER_CLIENT_ID, settings.DHAN_MASTER_ACCESS_TOKEN)
            
            logger.info(f"📊 Fetching option chain for {self.index}...")
            
            # Get expiry list
            expiry_response = dhan.expiry_list(
                under_security_id=INDEX_UNDERLYING[self.index]["security_id"],
                under_exchange_segment=INDEX_UNDERLYING[self.index]["exchange_segment"]
            )
            
            logger.info(f"📋 Expiry list response: {expiry_response}")
            
            if not expiry_response or expiry_response.get("status") != "success":
                logger.error(f"❌ Failed to get expiry list: {expiry_response}")
                return
            
            # Get nearest expiry (first in list)
            # The response structure is: {"data": {"data": ["2025-11-25", ...], "status": "success"}, "status": "success"}
            expiry_dates = expiry_response.get("data", {})
            
            # Handle nested structure: data.data
            if isinstance(expiry_dates, dict):
                expiry_dates = expiry_dates.get("data", [])
            
            if not expiry_dates or not isinstance(expiry_dates, list):
                logger.error(f"❌ No expiry dates available. Full response: {expiry_response}")
                return
            
            self.selected_expiry = expiry_dates[0]  # Use nearest expiry
            logger.info(f"📅 Using expiry: {self.selected_expiry}")
            
            # Start polling loop - fetch option chain every 3 seconds
            logger.info("� Starting option chain polling (every 3 seconds)...")
            while self.running:
                try:
                    # Fetch fresh option chain data
                    chain_response = dhan.option_chain(
                        under_security_id=INDEX_UNDERLYING[self.index]["security_id"],
                        under_exchange_segment=INDEX_UNDERLYING[self.index]["exchange_segment"],
                        expiry=self.selected_expiry
                    )
                    
                    if not chain_response or chain_response.get("status") != "success":
                        logger.error(f"❌ Failed to get option chain: {chain_response}")
                        await asyncio.sleep(3)
                        continue
                    
                    # Parse option chain data
                    chain_data = chain_response.get("data", {})
                    if "data" in chain_data and isinstance(chain_data["data"], dict):
                        chain_data = chain_data["data"]
                    
                    spot_ltp = chain_data.get("last_price", 0)
                    oc_dict = chain_data.get("oc", {})
                    
                    if not oc_dict:
                        logger.error(f"❌ No option chain data in response")
                        await asyncio.sleep(3)
                        continue
                    
                    # Calculate strike range
                    step = INDEX_UNDERLYING[self.index]["step"]
                    atm_strike = round(spot_ltp / step) * step if spot_ltp > 0 else 0
                    min_strike = atm_strike - (self.strikes_each_side * step)
                    max_strike = atm_strike + (self.strikes_each_side * step)
                    
                    # Build snapshot
                    await self._build_snapshot_from_chain(oc_dict, spot_ltp, min_strike, max_strike)
                    
                    # Wait 3 seconds before next fetch (DHAN API limit)
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"❌ Error in polling loop: {e}", exc_info=True)
                    await asyncio.sleep(3)
            
        except Exception as e:
            logger.error(f"❌ Error building option chain: {e}", exc_info=True)

    async def _listen(self):
        try:
            async for message in self.ws:
                if not isinstance(message, bytes) or len(message) < 8:
                    continue
                resp = message[0]
                # msg_len = struct.unpack('<H', message[1:3])[0]
                exchange = message[3]
                sec_id = str(struct.unpack('<I', message[4:8])[0])
                payload = message[8:]

                if resp == RESPONSE_TICKER:
                    self._handle_ticker(sec_id, payload)
                elif resp == RESPONSE_QUOTE:
                    self._handle_quote(sec_id, payload)
                elif resp == RESPONSE_PREV_CLOSE and len(payload) >= 4:
                    # prev close packet: float32 prev_close + uint32 prev_oi (when available)
                    self.prev_close[sec_id] = struct.unpack('<f', payload[0:4])[0]
                    if len(payload) >= 8:
                        self.prev_oi[sec_id] = struct.unpack('<I', payload[4:8])[0]
                elif resp == RESPONSE_OI and len(payload) >= 4:
                    self.oi[sec_id] = struct.unpack('<I', payload[0:4])[0]
        except Exception:
            pass

    def _handle_ticker(self, sec_id: str, payload: bytes):
        if len(payload) < 8:
            return
        ltp = struct.unpack('<f', payload[0:4])[0]
        # Map to index by underlying sec id
        for name, meta in INDEX_UNDERLYING.items():
            if meta["security_id"] == sec_id:
                self.underlying_ltp[name] = ltp
                break

    def _handle_quote(self, sec_id: str, payload: bytes):
        if len(payload) < 42:
            return
        ltp = struct.unpack('<f', payload[0:4])[0]
        ltq = struct.unpack('<H', payload[4:6])[0]
        ltt = struct.unpack('<I', payload[6:10])[0]
        atp = struct.unpack('<f', payload[10:14])[0]
        vol = struct.unpack('<I', payload[14:18])[0]
        self.quote[sec_id] = {
            "ltp": round(ltp, 2),
            "ltq": ltq,
            "ltt": ltt,
            "atp": round(atp, 2),
            "volume": vol,
            "ts": datetime.now().isoformat(),
        }

    async def _snapshot_loop(self):
        while True:
            try:
                snap = self._build_snapshot()
                if snap:
                    await self.send_callback(snap)
            except Exception:
                pass
            await asyncio.sleep(1.0)

    def _build_snapshot(self) -> Optional[Dict[str, Any]]:
        idx = self.index
        spot = round(self.underlying_ltp.get(idx, 0.0), 2)
        expiry = self.selected_expiry or "AUTO"
        strikes = sorted({c.strike for c in self.contracts.values() if c.index == idx})
        if not strikes:
            return None
        rows = []
        for k in strikes:
            ce = self._find(idx, k, "CE")
            pe = self._find(idx, k, "PE")
            ce_q = self.quote.get(ce.sec_id) if ce else None
            pe_q = self.quote.get(pe.sec_id) if pe else None
            ce_pc = self.prev_close.get(ce.sec_id) if ce else None
            pe_pc = self.prev_close.get(pe.sec_id) if pe else None
            ce_chg_abs = ((ce_q["ltp"] - ce_pc)) if (ce_q and ce_pc and ce_pc > 0) else 0.0
            pe_chg_abs = ((pe_q["ltp"] - pe_pc)) if (pe_q and pe_pc and pe_pc > 0) else 0.0
            ce_chg = ((ce_q["ltp"] - ce_pc) / ce_pc * 100) if (ce_q and ce_pc and ce_pc > 0) else 0.0
            pe_chg = ((pe_q["ltp"] - pe_pc) / pe_pc * 100) if (pe_q and pe_pc and pe_pc > 0) else 0.0
            ce_oi = self.oi.get(ce.sec_id, 0) if ce else 0
            pe_oi = self.oi.get(pe.sec_id, 0) if pe else 0
            ce_prev_oi = self.prev_oi.get(ce.sec_id, 0) if ce else 0
            pe_prev_oi = self.prev_oi.get(pe.sec_id, 0) if pe else 0
            ce_oi_chg = ce_oi - ce_prev_oi
            pe_oi_chg = pe_oi - pe_prev_oi
            rows.append(
                {
                    "strike": k,
                    "ce": {
                        "ltp": ce_q["ltp"] if ce_q else 0.0,
                        "chg": round(ce_chg_abs, 2),
                        "chg_pct": round(ce_chg, 2),
                        "vol": ce_q["volume"] if ce_q else 0,
                        "oi": ce_oi,
                        "oi_chg": ce_oi_chg,
                    },
                    "pe": {
                        "ltp": pe_q["ltp"] if pe_q else 0.0,
                        "chg": round(pe_chg_abs, 2),
                        "chg_pct": round(pe_chg, 2),
                        "vol": pe_q["volume"] if pe_q else 0,
                        "oi": pe_oi,
                        "oi_chg": pe_oi_chg,
                    },
                }
            )
        return {"type": "snapshot", "index": idx, "spot": spot, "expiry": expiry, "rows": rows, "ts": datetime.now().isoformat()}

    def _find(self, idx: str, strike: int, cp: str) -> Optional[Contract]:
        for c in self.contracts.values():
            if c.index == idx and c.strike == strike and c.option_type == cp:
                return c
        return None
