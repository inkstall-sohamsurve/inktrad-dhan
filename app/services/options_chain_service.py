import asyncio
import csv
import os
import re
import struct
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import requests
import websockets
from app.core.config import settings


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
        "security_id": "13",  # Nifty
        "step": 50,
        "exchange_segment": "IDX_I"
    },
    "BANKNIFTY": {
        "security_id": "23",  # BankNifty
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


def _is_symbol_for_index(sym: str) -> Dict[str, bool]:
    u = sym.upper()
    # Split symbol into alphabetic and numeric segments. This makes
    # 'NIFTY28NOV25CE' -> ['NIFTY','28','NOV','25','CE'] and avoids
    # accidental matches like FINNIFTY or NIFTYIT.
    tokens = re.findall(r"[A-Z]+|[0-9]+", u)
    has_nifty = "NIFTY" in tokens
    has_banknifty = "BANKNIFTY" in tokens
    return {"NIFTY": has_nifty and not has_banknifty, "BANKNIFTY": has_banknifty}


def normalize_header_map(sample_row: Dict) -> Dict[str, str]:
    """Map standard field names to actual CSV headers."""
    m = {
        # New DHAN format
        "exchangesegment": "SEM_EXM_EXCH_ID",
        "segment": "SEM_SEGMENT",
        "securityid": "SEM_SMST_SECURITY_ID",
        "instrument": "SEM_INSTRUMENT_NAME",
        "symbol": "SEM_TRADING_SYMBOL",
        "expiry": "SEM_EXPIRY_DATE",
        "strike": "SEM_STRIKE_PRICE",
        "optiontype": "SEM_OPTION_TYPE",
        "instrumenttype": "SEM_EXCH_INSTRUMENT_TYPE",
        "symbolname": "SM_SYMBOL_NAME",
        "customsymbol": "SEM_CUSTOM_SYMBOL",
    }
    for k in sample_row.keys():
        nk = k.lower().replace(" ", "").replace("_", "")
        m[nk] = k
    return m


def _get_field(r: Dict, m: Dict[str, str], keys: List[str]) -> str:
    for k in keys:
        if k in m:
            v = r.get(m[k], "")
            if v:
                return v
    return ""


def _is_fno_segment(exch_val: str, seg_val: str) -> bool:
    """Check if this is an F&O segment using both exchange and segment fields."""
    u_exch = (exch_val or "").upper()
    u_seg = (seg_val or "").upper()
    
    # Check segment first
    if u_seg in {"FO", "F", "NFO", "NSE FO", "NSEFO", "D"}:
        return True
    
    # Then check exchange
    if u_exch == "NSE" and u_seg in {"F", "D", "FO"}:
        return True
    
    # Also check BSE derivatives
    if u_exch == "BSE" and u_seg in {"D"}:
        return True
        
    return False


def _is_optidx(instr_val: str, opt_type: str) -> bool:
    """Check if this is an index option using instrument type and option type."""
    u_instr = (instr_val or "").upper()
    u_opt = (opt_type or "").upper()
    
    # First check option type
    if u_opt in {"CE", "PE", "C", "P"}:
        # Then check if it's an index option
        return (
            u_instr in {"OPTIDX", "INDEX OPTION", "INDEX OPTIONS"} or
            "IDX" in u_instr or
            "INDEX" in u_instr
        )
    return False

def nearest_expiry(master: List[Dict], idx: str, today: date) -> Optional[str]:
    out = []
    for r in master[:500000]:
        m = normalize_header_map(r)
        exch = _get_field(r, m, ["exchangesegment", "exchange", "exchgsegment"]) 
        seg = _get_field(r, m, ["segment"]) 
        instr = _get_field(r, m, ["instrument", "instrumenttype", "instrumentname"]) 
        sym = _get_field(r, m, ["symbolname", "tradingsymbol", "symbol"]) 
        exp = _get_field(r, m, ["expirydate", "expiry", "expdate"]) 
        opt = _get_field(r, m, ["optiontype", "opttype", "option"]) 
        if not _is_fno_segment(exch, seg):
            continue
        uinstr = (instr or "").upper()
        if not ("OPT" in uinstr and ("IDX" in uinstr or "INDEX" in uinstr)):
            continue
        flags = _is_symbol_for_index(sym)
        if not flags.get(idx, False):
            continue
        try:
            d = datetime.strptime(exp[:10], "%Y-%m-%d").date()
        except Exception:
            try:
                d = datetime.strptime(exp[:11].strip(), "%d-%b-%Y").date()
            except Exception:
                continue
        if d >= today:
            out.append(d.isoformat())
    return min(out) if out else None


def find_option_contracts(master: List[Dict], idx: str, expiry: Optional[str], strikes: List[int]) -> List[Contract]:
    result: Dict[Tuple[int, str], Contract] = {}
    for r in master:
        m = normalize_header_map(r)
        exch = _get_field(r, m, ["exchangesgment", "exchangesegment", "exchange", "exchgsegment"]) 
        seg = _get_field(r, m, ["segment"]) 
        instr = _get_field(r, m, ["instrument", "instrumenttype", "instrumentname"]) 
        sym = _get_field(r, m, ["symbolname", "tradingsymbol", "symbol"]) 
        secid = _get_field(r, m, ["securityid", "security_id", "token"]) 
        opttype = _get_field(r, m, ["optiontype", "opttype", "option"]) 
        strike_val = _get_field(r, m, ["strikeprice", "strike", "strike_price"]) 
        exp = _get_field(r, m, ["expirydate", "expiry", "expdate"]) 
        if not _is_fno_segment(exch, seg):
            continue
        uinstr = (instr or "").upper()
        if not ("OPT" in uinstr and ("IDX" in uinstr or "INDEX" in uinstr)):
            continue
        if not secid or not strike_val or not opttype:
            continue
        flags = _is_symbol_for_index(sym)
        if not flags.get(idx, False):
            continue
        if expiry and exp[:10] != expiry:
            try:
                d = datetime.strptime(exp[:11].strip(), "%d-%b-%Y").date().isoformat()
                if d != expiry:
                    continue
            except Exception:
                continue
        try:
            st = int(round(float(strike_val)))
        except Exception:
            continue
        if st not in strikes:
            continue
        cp = (opttype or "").upper()
        if cp in ("C", "CALL"):
            cp = "CE"
        elif cp in ("P", "PUT"):
            cp = "PE"
        if cp not in ("CE", "PE"):
            continue
        key = (st, cp)
        if key not in result:
            result[key] = Contract(sec_id=str(secid), index=idx, strike=st, option_type=cp, expiry=expiry or exp[:10])
    return list(result.values())


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

    async def _subscribe_underlying(self):
        sec = INDEX_UNDERLYING[self.index]["security_id"]
        await self._subscribe([{"ExchangeSegment": "NSE_FNO", "SecurityId": sec}], SUBSCRIBE_TICKER)

    async def _build_and_subscribe_chain(self):
        today = date.today()
        
        if not self.is_connected:
            if not await self.connect():
                print("❌ Failed to connect to WebSocket")
                return

        try:
            # Initialize Dhan client
            dhan = dhanhq(self.client_id, self.access_token)
            
            for idx in ("NIFTY", "BANKNIFTY"):
                # Get expiry
                expiry_date = today + timedelta(days=(3 - today.weekday() + 7))
                exp = expiry_date.isoformat()
                self.expiries[idx] = exp
                
                if idx not in self.snapshots:
                    self.snapshots[idx] = {}
                
                # Get spot price
                spot = await self._get_spot(idx)
                
                # Get option chain from Dhan API
                chain = dhan.option_chain(
                    under_security_id=INDEX_UNDERLYING[idx]["security_id"],
                    under_exchange_segment=INDEX_UNDERLYING[idx]["exchange_segment"],
                    expiry=exp
                )
                
                if not chain or "data" not in chain:
                    print(f"❌ Failed to get {idx} option chain: {chain}")
                    continue
                    
                # Parse contracts
                for opt in chain["data"]:
                    try:
                        contract = Contract(
                            sec_id=str(opt["security_id"]),
                            index=idx,
                            strike=float(opt["strike_price"]),
                            option_type=opt["option_type"],
                            expiry=exp
                        )
                        self.contracts[contract.sec_id] = contract
                    except (KeyError, ValueError) as e:
                        print(f"⚠️ Error parsing option: {e}")
                        continue
            
            # Subscribe to all contracts
            inst = []
            for c in self.contracts.values():
                inst.append({"ExchangeSegment": "NSE_FNO", "SecurityId": c.sec_id})
            for idx in self.indices:
                inst.append({"ExchangeSegment": "NSE_FNO", "SecurityId": INDEX_UNDERLYING[idx]["security_id"]})
            
            if not await self.subscribe(inst, SUBSCRIBE_QUOTE):
                return
                
        except Exception as e:
            print(f"❌ Error building option chain: {e}")

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
