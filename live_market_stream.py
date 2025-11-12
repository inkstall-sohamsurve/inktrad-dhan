"""
Advanced Live Market Data Stream for Nifty 50
Real-time tick-by-tick data with advanced features:
- Auto-reconnection on disconnection
- Multiple data modes (ticker/quote/full)
- Real-time statistics and analytics
- Multiple export formats (CSV, JSON)
- Performance monitoring
- Error recovery

Usage:
    python live_market_stream.py --mode ticker --export csv
"""

import asyncio
import json
import struct
import websockets
import os
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dotenv import load_dotenv
import csv
from pathlib import Path
from collections import defaultdict
import time

# Load environment variables
load_dotenv()

# DHAN Configuration
DHAN_CLIENT_ID = os.getenv("DHAN_MASTER_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_MASTER_ACCESS_TOKEN")

# Complete Nifty 50 Stock List with correct Security IDs
NIFTY_50_STOCKS = {
    "Reliance Industries": {"security_id": "2885", "exchange_segment": "NSE_EQ", "symbol": "RELIANCE"},
    "TCS": {"security_id": "11536", "exchange_segment": "NSE_EQ", "symbol": "TCS"},
    "HDFC Bank": {"security_id": "1333", "exchange_segment": "NSE_EQ", "symbol": "HDFCBANK"},
    "Infosys": {"security_id": "1594", "exchange_segment": "NSE_EQ", "symbol": "INFY"},
    "ICICI Bank": {"security_id": "4963", "exchange_segment": "NSE_EQ", "symbol": "ICICIBANK"},
    "Hindustan Unilever": {"security_id": "1394", "exchange_segment": "NSE_EQ", "symbol": "HINDUNILVR"},
    "ITC": {"security_id": "1660", "exchange_segment": "NSE_EQ", "symbol": "ITC"},
    "SBI": {"security_id": "3045", "exchange_segment": "NSE_EQ", "symbol": "SBIN"},
    "Bharti Airtel": {"security_id": "10604", "exchange_segment": "NSE_EQ", "symbol": "BHARTIARTL"},
    "Kotak Mahindra Bank": {"security_id": "1922", "exchange_segment": "NSE_EQ", "symbol": "KOTAKBANK"},
    "Axis Bank": {"security_id": "5900", "exchange_segment": "NSE_EQ", "symbol": "AXISBANK"},
    "Larsen & Toubro": {"security_id": "1666", "exchange_segment": "NSE_EQ", "symbol": "LT"},
    "HCL Technologies": {"security_id": "7229", "exchange_segment": "NSE_EQ", "symbol": "HCLTECH"},
    "Asian Paints": {"security_id": "234", "exchange_segment": "NSE_EQ", "symbol": "ASIANPAINT"},
    "Maruti Suzuki": {"security_id": "10999", "exchange_segment": "NSE_EQ", "symbol": "MARUTI"},
    "Bajaj Finance": {"security_id": "317", "exchange_segment": "NSE_EQ", "symbol": "BAJFINANCE"},
    "Mahindra & Mahindra": {"security_id": "2031", "exchange_segment": "NSE_EQ", "symbol": "M&M"},
    "Sun Pharmaceutical": {"security_id": "3351", "exchange_segment": "NSE_EQ", "symbol": "SUNPHARMA"},
    "Titan Company": {"security_id": "3506", "exchange_segment": "NSE_EQ", "symbol": "TITAN"},
    "UltraTech Cement": {"security_id": "11532", "exchange_segment": "NSE_EQ", "symbol": "ULTRACEMCO"},
    "Nestle India": {"security_id": "17963", "exchange_segment": "NSE_EQ", "symbol": "NESTLEIND"},
    "Tata Steel": {"security_id": "3499", "exchange_segment": "NSE_EQ", "symbol": "TATASTEEL"},
    "Bajaj Finserv": {"security_id": "16675", "exchange_segment": "NSE_EQ", "symbol": "BAJAJFINSV"},
    "Power Grid": {"security_id": "11631", "exchange_segment": "NSE_EQ", "symbol": "POWERGRID"},
    "NTPC": {"security_id": "11630", "exchange_segment": "NSE_EQ", "symbol": "NTPC"},
    "Tech Mahindra": {"security_id": "13538", "exchange_segment": "NSE_EQ", "symbol": "TECHM"},
    "Wipro": {"security_id": "3787", "exchange_segment": "NSE_EQ", "symbol": "WIPRO"},
    "ONGC": {"security_id": "2475", "exchange_segment": "NSE_EQ", "symbol": "ONGC"},
    "Coal India": {"security_id": "20374", "exchange_segment": "NSE_EQ", "symbol": "COALINDIA"},
    "Tata Motors": {"security_id": "3456", "exchange_segment": "NSE_EQ", "symbol": "TATAMOTORS"},
    "Adani Ports": {"security_id": "15083", "exchange_segment": "NSE_EQ", "symbol": "ADANIPORTS"},
    "JSW Steel": {"security_id": "11723", "exchange_segment": "NSE_EQ", "symbol": "JSWSTEEL"},
    "Grasim Industries": {"security_id": "1232", "exchange_segment": "NSE_EQ", "symbol": "GRASIM"},
    "Hindalco": {"security_id": "1363", "exchange_segment": "NSE_EQ", "symbol": "HINDALCO"},
    "Britannia Industries": {"security_id": "547", "exchange_segment": "NSE_EQ", "symbol": "BRITANNIA"},
    "Cipla": {"security_id": "701", "exchange_segment": "NSE_EQ", "symbol": "CIPLA"},
    "Eicher Motors": {"security_id": "910", "exchange_segment": "NSE_EQ", "symbol": "EICHERMOT"},
    "Hero MotoCorp": {"security_id": "1348", "exchange_segment": "NSE_EQ", "symbol": "HEROMOTOCO"},
    "Shree Cement": {"security_id": "3103", "exchange_segment": "NSE_EQ", "symbol": "SHREECEM"},
    "Bajaj Auto": {"security_id": "16669", "exchange_segment": "NSE_EQ", "symbol": "BAJAJ-AUTO"},
    "Dr Reddy's Laboratories": {"security_id": "881", "exchange_segment": "NSE_EQ", "symbol": "DRREDDY"},
    "Divi's Laboratories": {"security_id": "10940", "exchange_segment": "NSE_EQ", "symbol": "DIVISLAB"},
    "IndusInd Bank": {"security_id": "5258", "exchange_segment": "NSE_EQ", "symbol": "INDUSINDBK"},
    "Adani Enterprises": {"security_id": "25", "exchange_segment": "NSE_EQ", "symbol": "ADANIENT"},
    "Tata Consumer": {"security_id": "3432", "exchange_segment": "NSE_EQ", "symbol": "TATACONSUM"},
    "Apollo Hospitals": {"security_id": "157", "exchange_segment": "NSE_EQ", "symbol": "APOLLOHOSP"},
    "BPCL": {"security_id": "526", "exchange_segment": "NSE_EQ", "symbol": "BPCL"},
    "SBI Life": {"security_id": "21808", "exchange_segment": "NSE_EQ", "symbol": "SBILIFE"},
    "HDFC Life": {"security_id": "501937", "exchange_segment": "NSE_EQ", "symbol": "HDFCLIFE"},
    "UPL": {"security_id": "11287", "exchange_segment": "NSE_EQ", "symbol": "UPL"},
}

# Nifty Indices
NIFTY_INDICES = {
    "NIFTY 50": {"security_id": "26000", "exchange_segment": "NSE_FNO", "symbol": "NIFTY"},
    "NIFTY BANK": {"security_id": "26009", "exchange_segment": "NSE_FNO", "symbol": "BANKNIFTY"},
}


class MarketDataStats:
    """Track real-time statistics"""
    
    def __init__(self):
        self.tick_count = 0
        self.start_time = time.time()
        self.symbol_ticks = defaultdict(int)
        self.errors = 0
        self.reconnections = 0
        
    def add_tick(self, symbol: str):
        """Add a tick"""
        self.tick_count += 1
        self.symbol_ticks[symbol] += 1
    
    def get_ticks_per_second(self) -> float:
        """Calculate ticks per second"""
        elapsed = time.time() - self.start_time
        return self.tick_count / elapsed if elapsed > 0 else 0
    
    def get_summary(self) -> str:
        """Get statistics summary"""
        elapsed = time.time() - self.start_time
        tps = self.get_ticks_per_second()
        
        return (
            f"\n📊 Statistics:\n"
            f"   Total Ticks: {self.tick_count:,}\n"
            f"   Elapsed Time: {timedelta(seconds=int(elapsed))}\n"
            f"   Ticks/Second: {tps:.2f}\n"
            f"   Errors: {self.errors}\n"
            f"   Reconnections: {self.reconnections}\n"
            f"   Active Symbols: {len(self.symbol_ticks)}"
        )


class LiveMarketStream:
    """Advanced live market data stream"""
    
    # WebSocket Codes
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
    
    def __init__(self, client_id: str, access_token: str, mode: str = "ticker", export_format: str = "csv"):
        """Initialize stream"""
        self.client_id = client_id
        self.access_token = access_token
        self.mode = mode
        self.export_format = export_format
        self.ws_url = f"wss://api-feed.dhan.co?version=2&token={access_token}&clientId={client_id}&authType=2"
        
        self.websocket = None
        self.is_connected = False
        self.should_reconnect = True
        self.last_prices = {}
        self.stats = MarketDataStats()
        
        # Export setup
        self.csv_file = None
        self.csv_writer = None
        self.json_buffer = []
        self._setup_export()
        
        # Security ID to symbol/name mapping
        self.id_to_name = {}
        for name, info in {**NIFTY_50_STOCKS, **NIFTY_INDICES}.items():
            self.id_to_name[info['security_id']] = info.get('symbol', name)
    
    def _setup_export(self):
        """Setup data export"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.export_format == "csv":
            filename = f"market_data_{self.mode}_{timestamp}.csv"
            self.csv_file = open(filename, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            
            if self.mode == "ticker":
                self.csv_writer.writerow(['Timestamp', 'Symbol', 'LTP', 'Change', 'Change%'])
            else:
                self.csv_writer.writerow([
                    'Timestamp', 'Symbol', 'LTP', 'Change', 'Change%',
                    'Volume', 'Open', 'High', 'Low', 'Close'
                ])
            
            print(f"📝 Exporting to: {filename}")
    
    async def connect(self) -> bool:
        """Connect to WebSocket with retry"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"🔌 Connecting... (Attempt {attempt + 1}/{max_retries})")
                self.websocket = await websockets.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=10
                )
                self.is_connected = True
                print("✅ Connected to DHAN WebSocket")
                return True
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                if attempt < max_retries - 1:
                    print(f"⏳ Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
        
        return False
    
    async def disconnect(self):
        """Disconnect gracefully"""
        self.should_reconnect = False
        
        if self.websocket:
            try:
                if self.is_connected and not self.websocket.closed:
                    disconnect_msg = {"RequestCode": self.DISCONNECT}
                    await self.websocket.send(json.dumps(disconnect_msg))
                    await self.websocket.close()
            except Exception:
                # Connection already closed, ignore
                pass
            finally:
                self.is_connected = False
        
        if self.csv_file:
            self.csv_file.close()
        
        print("✅ Disconnected")
    
    async def subscribe_all(self) -> bool:
        """Subscribe to all instruments"""
        if not self.is_connected:
            return False
        
        # Prepare instruments
        instruments = []
        for name, info in {**NIFTY_50_STOCKS, **NIFTY_INDICES}.items():
            instruments.append({
                "ExchangeSegment": info["exchange_segment"],
                "SecurityId": info["security_id"]
            })
        
        # Determine request code
        request_codes = {
            "ticker": self.SUBSCRIBE_TICKER,
            "quote": self.SUBSCRIBE_QUOTE,
            "full": self.SUBSCRIBE_FULL
        }
        request_code = request_codes.get(self.mode, self.SUBSCRIBE_TICKER)
        
        # Subscribe in batches
        batch_size = 100
        total = 0
        
        for i in range(0, len(instruments), batch_size):
            batch = instruments[i:i + batch_size]
            
            msg = {
                "RequestCode": request_code,
                "InstrumentCount": len(batch),
                "InstrumentList": batch
            }
            
            try:
                await self.websocket.send(json.dumps(msg))
                total += len(batch)
                print(f"📡 Subscribed: {total}/{len(instruments)}")
                await asyncio.sleep(0.05)
            except Exception as e:
                print(f"❌ Subscription error: {e}")
                self.stats.errors += 1
                return False
        
        print(f"✅ Subscribed to {total} instruments (mode: {self.mode})")
        return True
    
    def _parse_ticker(self, payload: bytes, security_id: str, exchange: int) -> Optional[Dict]:
        """Parse ticker payload (float32 LTP, uint32 LTT)"""
        try:
            if len(payload) < 8:
                return None
            ltp = struct.unpack('<f', payload[0:4])[0]
            ltt = struct.unpack('<I', payload[4:8])[0]
            return {
                'security_id': security_id,
                'ltp': round(ltp, 2),
                'ltt': ltt,
                'exchange': exchange
            }
        except Exception:
            return None
    
    def _parse_quote(self, payload: bytes, security_id: str, exchange: int) -> Optional[Dict]:
        """Parse quote payload (42 bytes) with float32 fields"""
        try:
            if len(payload) < 42:
                return None
            ltp = struct.unpack('<f', payload[0:4])[0]
            ltq = struct.unpack('<H', payload[4:6])[0]
            ltt = struct.unpack('<I', payload[6:10])[0]
            atp = struct.unpack('<f', payload[10:14])[0]
            volume = struct.unpack('<I', payload[14:18])[0]
            total_sell_qty = struct.unpack('<I', payload[18:22])[0]
            total_buy_qty = struct.unpack('<I', payload[22:26])[0]
            open_price = struct.unpack('<f', payload[26:30])[0]
            close_price = struct.unpack('<f', payload[30:34])[0]
            high = struct.unpack('<f', payload[34:38])[0]
            low = struct.unpack('<f', payload[38:42])[0]
            return {
                'security_id': security_id,
                'ltp': round(ltp, 2),
                'ltq': ltq,
                'ltt': ltt,
                'atp': round(atp, 2),
                'volume': volume,
                'total_sell_qty': total_sell_qty,
                'total_buy_qty': total_buy_qty,
                'open': round(open_price, 2),
                'close': round(close_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'exchange': exchange
            }
        except Exception:
            return None
    
    def _process_tick(self, tick: Dict):
        """Process and display tick"""
        security_id = tick['security_id']
        symbol = self.id_to_name.get(security_id, f"Unknown-{security_id}")
        ltp = tick['ltp']
        
        # Calculate change
        prev = self.last_prices.get(symbol, ltp)
        change = ltp - prev
        change_pct = (change / prev * 100) if prev > 0 else 0
        
        self.last_prices[symbol] = ltp
        self.stats.add_tick(symbol)
        
        # Display
        indicator = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        if self.mode == "ticker":
            print(f"{indicator} [{timestamp}] {symbol:30s} | ₹{ltp:>10.2f} | {change:>+8.2f} ({change_pct:>6.2f}%)")
        else:
            vol = tick.get('volume', 0)
            print(f"{indicator} [{timestamp}] {symbol:25s} | ₹{ltp:>10.2f} | {change:>+7.2f} ({change_pct:>5.2f}%) | Vol: {vol:>12,}")
        
        # Export
        if self.csv_writer:
            if self.mode == "ticker":
                self.csv_writer.writerow([
                    datetime.now().isoformat(), symbol, ltp, change, change_pct
                ])
            else:
                self.csv_writer.writerow([
                    datetime.now().isoformat(), symbol, ltp, change, change_pct,
                    tick.get('volume', 0), tick.get('open', 0),
                    tick.get('high', 0), tick.get('low', 0), tick.get('close', 0)
                ])
            
            if self.stats.tick_count % 20 == 0:
                self.csv_file.flush()
    
    async def listen(self):
        """Listen for messages"""
        print("\n" + "="*80)
        print(f"📊 LIVE MARKET STREAM - {self.mode.upper()} MODE")
        print("="*80)
        print("Press Ctrl+C to stop\n")
        
        try:
            async for message in self.websocket:
                if isinstance(message, bytes) and len(message) >= 8:
                    response_type = message[0]
                    # Header (v2)
                    # len_field = struct.unpack('<H', message[1:3])[0]
                    exchange = message[3]
                    security_id = str(struct.unpack('<I', message[4:8])[0])
                    payload = message[8:]

                    tick = None
                    if response_type == self.RESPONSE_TICKER:
                        tick = self._parse_ticker(payload, security_id, exchange)
                    elif response_type == self.RESPONSE_QUOTE:
                        tick = self._parse_quote(payload, security_id, exchange)

                    if tick:
                        self._process_tick(tick)

                    # Print stats every 100 ticks
                    if self.stats.tick_count % 100 == 0 and self.stats.tick_count > 0:
                        print(f"\n{self.stats.get_summary()}\n")
                        
        except websockets.exceptions.ConnectionClosed:
            print(f"\n⚠️  Connection closed by server")
            print(f"\n💡 Possible reasons:")
            print(f"   - Market is closed (NSE hours: 9:15 AM - 3:30 PM IST)")
            print(f"   - Invalid subscription request")
            print(f"   - Server maintenance")
            print(f"   - Network issue")
            if self.stats.tick_count == 0:
                print(f"\n⚠️  No data received - Market might be closed")
            if self.should_reconnect and self.stats.tick_count > 0:
                print("🔄 Reconnecting...")
                self.stats.reconnections += 1
                await self.reconnect()
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping...")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            self.stats.errors += 1
    
    async def reconnect(self):
        """Reconnect and resume"""
        self.is_connected = False
        await asyncio.sleep(2)
        
        if await self.connect():
            if await self.subscribe_all():
                await self.listen()


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Live Nifty 50 Market Data Stream")
    parser.add_argument("--mode", choices=["ticker", "quote", "full"], default="ticker",
                        help="Data mode (ticker=fastest, quote=detailed, full=complete)")
    parser.add_argument("--export", choices=["csv", "json", "none"], default="csv",
                        help="Export format")
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🚀 NIFTY 50 LIVE MARKET DATA STREAM")
    print("="*80)
    
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        print("\n❌ Error: DHAN credentials not found in .env file")
        return
    
    print(f"\n📋 Configuration:")
    print(f"   Mode: {args.mode.upper()}")
    print(f"   Export: {args.export.upper()}")
    print(f"   Stocks: {len(NIFTY_50_STOCKS)}")
    print(f"   Indices: {len(NIFTY_INDICES)}")
    
    stream = LiveMarketStream(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN, args.mode, args.export)
    
    try:
        if await stream.connect():
            if await stream.subscribe_all():
                await stream.listen()
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrupted")
    finally:
        await stream.disconnect()
        print(stream.stats.get_summary())
        print("\n✅ Session ended")


if __name__ == "__main__":
    asyncio.run(main())
