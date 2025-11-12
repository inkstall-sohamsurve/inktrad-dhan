import asyncio
import csv
import os
import struct
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

import requests
import re
import websockets
from dotenv import load_dotenv

load_dotenv()

DHAN_CLIENT_ID = os.getenv("DHAN_MASTER_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_MASTER_ACCESS_TOKEN")

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

WS_URL_TMPL = "wss://api-feed.dhan.co?version=2&token={token}&clientId={cid}&authType=2"

SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
SCRIP_CACHE = "dhan_scrip_master.csv"

INDEX_UNDERLYING = {
    "NIFTY": {"security_id": "26000", "step": 50},
    "BANKNIFTY": {"security_id": "26009", "step": 100},
}


@dataclass
class Contract:
    sec_id: str
    index: str
    strike: int
    option_type: str  # CE/PE
    expiry: str


class OptionsChainLive:
    def __init__(self, indices: List[str] = ("NIFTY", "BANKNIFTY"), strikes_each_side: int = 10):
        self.indices = indices
        self.strikes_each_side = strikes_each_side
        self.ws = None
        self.is_connected = False
        self.ws_url = WS_URL_TMPL.format(token=DHAN_ACCESS_TOKEN, cid=DHAN_CLIENT_ID)
        self.contracts: Dict[str, Contract] = {}
        self.underlying_ltp: Dict[str, float] = {}
        self.prev_close: Dict[str, float] = {}
        self.quote: Dict[str, Dict] = {}
        self.oi: Dict[str, int] = {}
        self._last_print = 0.0
        self._print_interval = 1.5

    async def connect(self) -> bool:
        try:
            self.ws = await websockets.connect(self.ws_url, ping_interval=20, ping_timeout=10)
            self.is_connected = True
            return True
        except Exception as e:
            print(f"❌ WebSocket connect failed: {e}")
            return False

    async def disconnect(self):
        if self.ws and self.is_connected:
            try:
                await self.ws.send(self._json({"RequestCode": DISCONNECT}))
            except Exception:
                pass
            try:
                await self.ws.close()
            except Exception:
                pass
            self.is_connected = False

    def _json(self, obj: Dict) -> str:
        import json
        return json.dumps(obj)

    async def subscribe(self, instruments: List[Dict], request_code: int = SUBSCRIBE_QUOTE):
        batch_size = 100
        for i in range(0, len(instruments), batch_size):
            batch = instruments[i:i + batch_size]
            msg = {
                "RequestCode": request_code,
                "InstrumentCount": len(batch),
                "InstrumentList": batch,
            }
            await self.ws.send(self._json(msg))
            await asyncio.sleep(0.05)

    async def subscribe_underlyings(self):
        inst = []
        for idx in self.indices:
            sec = INDEX_UNDERLYING[idx]["security_id"]
            inst.append({"ExchangeSegment": "NSE_FNO", "SecurityId": sec})
        await self.subscribe(inst, SUBSCRIBE_TICKER)

    async def listen(self):
        try:
            printer = asyncio.create_task(self._printer())
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
                    pc = struct.unpack('<f', payload[0:4])[0]
                    self.prev_close[sec_id] = pc
                elif resp == RESPONSE_OI and len(payload) >= 4:
                    self.oi[sec_id] = struct.unpack('<I', payload[0:4])[0]
            printer.cancel()
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"❌ Listen error: {e}")

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
        ts = datetime.now().isoformat()
        self.quote[sec_id] = {
            "ltp": round(ltp, 2),
            "ltq": ltq,
            "ltt": ltt,
            "atp": round(atp, 2),
            "volume": vol,
            "timestamp": ts,
        }

    async def _printer(self):
        while True:
            now = time.time()
            if now - self._last_print >= self._print_interval:
                self._print_snapshot()
                self._last_print = now
            await asyncio.sleep(0.25)

    def _print_snapshot(self):
        os.system("")  # enable ANSI on Windows terminals
        print("\n" + "=" * 100)
        print("📊 LIVE OPTIONS CHAIN (NSE_FNO / OPTIDX)")
        print("=" * 100)
        for idx in self.indices:
            print(f"\n[{idx}] Spot: {self.underlying_ltp.get(idx, 0):.2f}  Expiry: {self._selected_expiry.get(idx, 'AUTO')}")
            rows = self._rows_for_index(idx)
            if not rows:
                print("(building chain...)")
                continue
            header = f"{'Strike':>8}  {'CE LTP':>8} {'CE Chg%':>8} {'CE Vol':>9} {'CE OI':>9}   ||   {'PE LTP':>8} {'PE Chg%':>8} {'PE Vol':>9} {'PE OI':>9}"
            print(header)
            print("-" * len(header))
            for r in rows:
                print(r)
        print("\nPress Ctrl+C to stop\n")

    def _rows_for_index(self, idx: str) -> List[str]:
        rows = []
        strikes = sorted({c.strike for c in self.contracts.values() if c.index == idx})
        if not strikes:
            return rows
        for k in strikes:
            ce = self._find(idx, k, "CE")
            pe = self._find(idx, k, "PE")
            ce_q = self.quote.get(ce.sec_id) if ce else None
            pe_q = self.quote.get(pe.sec_id) if pe else None
            ce_pc = self.prev_close.get(ce.sec_id) if ce else None
            pe_pc = self.prev_close.get(pe.sec_id) if pe else None
            ce_chg = ((ce_q["ltp"] - ce_pc) / ce_pc * 100) if (ce_q and ce_pc and ce_pc > 0) else 0.0
            pe_chg = ((pe_q["ltp"] - pe_pc) / pe_pc * 100) if (pe_q and pe_pc and pe_pc > 0) else 0.0
            ce_oi = self.oi.get(ce.sec_id, 0) if ce else 0
            pe_oi = self.oi.get(pe.sec_id, 0) if pe else 0
            rows.append(
                f"{k:>8}  "
                f"{(ce_q['ltp'] if ce_q else 0):>8.2f} {ce_chg:>8.2f} {(ce_q['volume'] if ce_q else 0):>9,} {ce_oi:>9,}   ||   "
                f"{(pe_q['ltp'] if pe_q else 0):>8.2f} {pe_chg:>8.2f} {(pe_q['volume'] if pe_q else 0):>9,} {pe_oi:>9,}"
            )
        return rows

    def _find(self, idx: str, strike: int, cp: str) -> Optional[Contract]:
        for c in self.contracts.values():
            if c.index == idx and c.strike == strike and c.option_type == cp:
                return c
        return None

    async def build_chain(self):
        master = load_scrip_master()
        today = date.today()
        self._selected_expiry: Dict[str, str] = {}

        for idx in self.indices:
            spot = await self._get_spot(idx)
            step = INDEX_UNDERLYING[idx]["step"]
            atm = int(round(spot / step) * step) if spot > 0 else (22500 if idx == "NIFTY" else 50000)
            expiry = nearest_expiry(master, idx, today)
            self._selected_expiry[idx] = expiry or "AUTO"
            strikes = [atm + i * step for i in range(-self.strikes_each_side, self.strikes_each_side + 1)]
            contracts = find_option_contracts(master, idx, expiry, strikes)
            for c in contracts:
                self.contracts[c.sec_id] = c

        inst = [{"ExchangeSegment": "NSE_FNO", "SecurityId": sid} for sid in self.contracts.keys()]
        await self.subscribe(inst, SUBSCRIBE_QUOTE)

    async def _get_spot(self, idx: str) -> float:
        # Try to use latest underlying ticker if already received; else wait briefly
        for _ in range(12):
            val = self.underlying_ltp.get(idx)
            if val and val > 0:
                return val
            await asyncio.sleep(0.25)
        # Fallback
        return 0.0


def load_scrip_master(path: str = SCRIP_CACHE) -> List[Dict]:
    def download(url: str, target: str) -> bool:
        try:
            print(f"🔍 Downloading scrip master...")
            r = requests.get(url, timeout=25)
            print(f"📡 Response status: {r.status_code}")
            if r.status_code != 200:
                print(f"❌ Error response: {r.text}")
                return False
            if r.text:
                with open(target, "w", encoding="utf-8", newline="") as f:
                    f.write(r.text)
                return True
            print("❌ Empty response body")
            return False
        except Exception as e:
            print(f"❌ Download error: {e}")
            return False

    # Always download fresh copy
    ok = download(SCRIP_MASTER_URL, path)
    if not ok:
        raise RuntimeError("Failed to download DHAN scrip master. Please check your DHAN credentials.")

    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        print(f"📃 CSV Headers: {headers}")
        print("📄 First few rows:")
        for i, r in enumerate(reader):
            if i < 3:
                print(f"   Row {i + 1}: {r}")
            rows.append({k.strip(): v.strip() for k, v in r.items()})
        print(f"📋 Total rows: {len(rows)}")
    return rows


def _is_symbol_for_index(sym: str) -> Dict[str, bool]:
    """Return flags whether symbol corresponds to NIFTY or BANKNIFTY exactly (token-based)."""
    u = sym.upper()
    # Separate letter and digit segments so that 'NIFTY28NOV24' becomes ['NIFTY','28','NOV','24'].
    # This avoids false positives like FINNIFTY or NIFTYIT while correctly catching plain NIFTY/BANKNIFTY.
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
    print(f"🔍 Finding {idx} options in {len(master)} rows...")
    found = 0
    for r in master[:500000]:  # guard if very large
        m = normalize_header_map(r)
        
        # Get all relevant fields
        exch = _get_field(r, m, ["exchangesegment"]) 
        seg = _get_field(r, m, ["segment"])
        instr = _get_field(r, m, ["instrument", "instrumenttype"]) 
        sym = _get_field(r, m, ["symbolname", "symbol"]) 
        exp = _get_field(r, m, ["expiry"]) 
        opt = _get_field(r, m, ["optiontype"])
        
        # Debug first few rows
        if found < 5:
            is_fno = _is_fno_segment(exch, seg)
            is_opt = _is_optidx(instr, opt)
            is_idx = _is_symbol_for_index(sym)
            if is_fno or is_opt or any(is_idx.values()):
                print(f"   Row {found + 1}:")
                print(f"      Exchange: {exch}, Segment: {seg} (FNO? {is_fno})")
                print(f"      Instrument: {instr}, Option: {opt} (OPTIDX? {is_opt})")
                print(f"      Symbol: {sym} (Index? {is_idx})")
                print(f"      Expiry: {exp}")
                found += 1
        
        # Must be F&O segment and index option
        if not (_is_fno_segment(exch, seg) and _is_optidx(instr, opt)):
            continue
            
        # Must match the index we're looking for
        flags = _is_symbol_for_index(sym)
        if not flags.get(idx, False):
            continue
        # parse date
        try:
            # try YYYY-MM-DD first
            d = datetime.strptime(exp[:10], "%Y-%m-%d").date()
        except Exception:
            try:
                d = datetime.strptime(exp[:11].strip(), "%d-%b-%Y").date()
            except Exception:
                continue
        if d >= today:
            out.append(d.isoformat())
    return min(out) if out else None


def find_option_contracts(master: List[Dict], idx: str, expiry: str, strikes: List[float]) -> List[Contract]:
    out = []
    found = 0
    print(f"🔍 Finding {idx} option contracts for expiry {expiry}...")
    print(f"   Looking for strikes: {strikes}")
    
    for r in master[:500000]:  # guard if very large
        m = normalize_header_map(r)
        exch = _get_field(r, m, ["exchangesegment"]) 
        seg = _get_field(r, m, ["segment"])
        instr = _get_field(r, m, ["instrument", "instrumenttype"]) 
        sym = _get_field(r, m, ["symbolname", "symbol"]) 
        exp = _get_field(r, m, ["expiry"]) 
        secid = _get_field(r, m, ["securityid"]) 
        strike_val = _get_field(r, m, ["strike"]) 
        opttype = _get_field(r, m, ["optiontype"]) 
        
        # Debug first few potential matches
        if found < 3:
            is_fno = _is_fno_segment(exch, seg)
            is_opt = _is_optidx(instr, opttype)
            is_idx = _is_symbol_for_index(sym)
            if is_fno or is_opt or any(is_idx.values()):
                print(f"   Row {found + 1}:")
                print(f"      Exchange: {exch}, Segment: {seg} (FNO? {is_fno})")
                print(f"      Instrument: {instr}, Option: {opttype} (OPTIDX? {is_opt})")
                print(f"      Symbol: {sym} (Index? {is_idx})")
                print(f"      Expiry: {exp}")
                print(f"      Strike: {strike_val}")
                found += 1
        
        if not (_is_fno_segment(exch, seg) and _is_optidx(instr, opttype)) or not secid or not strike_val or not opttype:
            continue
        flags = _is_symbol_for_index(sym)
        if not flags.get(idx, False):
            continue
        if exp != expiry:
            continue
        try:
            strike = float(strike_val)
            if strike not in strikes:
                continue
            out.append(Contract(
                sec_id=secid,
                strike=strike,
                opt_type=opttype,
            ))
        except Exception:
            continue
    
    print(f"   Found {len(out)} contracts")
    return out


async def main():
    print("\n" + "=" * 100)
    print("🚀 LIVE OPTIONS CHAIN - NIFTY & BANKNIFTY (DHAN v2)")
    print("=" * 100)
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        print("❌ Missing DHAN credentials in .env")
        return

    chain = OptionsChainLive()
    print("🔌 Connecting WebSocket...")
    if not await chain.connect():
        return

    try:
        print("📡 Subscribing underlyings (ticker)...")
        await chain.subscribe_underlyings()
        print("🧱 Building option chain from scrip master...")
        await chain.build_chain()
        print(f"📡 Subscribed {len(chain.contracts)} option contracts (QUOTE)")
        print("🎛️ Listening...")
        await chain.listen()
    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")
    finally:
        await chain.disconnect()
        print("✅ Disconnected")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
