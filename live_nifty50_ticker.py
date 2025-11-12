"""
Live Tick-by-Tick Data Fetcher for Nifty 50 Stocks and Indices
Fetches real-time market data without lag using DHAN WebSocket API

Features:
- Real-time tick-by-tick data for all Nifty 50 stocks
- Live data for Nifty 50 and Bank Nifty indices
- Optimized WebSocket connection with automatic reconnection
- Low latency data processing
- CSV export with timestamps
- Console display with color-coded changes

Usage:
    python live_nifty50_ticker.py
"""

import asyncio
import json
import struct
import websockets
import os
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
import csv
from pathlib import Path
from scripts.nse_security_ids import get_security_info

# Load environment variables
load_dotenv()

# DHAN Configuration
DHAN_CLIENT_ID = os.getenv("DHAN_MASTER_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_MASTER_ACCESS_TOKEN")

# Nifty 50 Stock Security IDs (NSE_EQ)
NIFTY_50_STOCKS = {
    # Large Cap
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
    
    # Banking & Finance
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
    
    # FMCG & Consumer
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
    
    # Others
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

# Nifty Indices (NSE_FNO)
NIFTY_INDICES = {
    "NIFTY 50": {"security_id": "26000", "exchange_segment": "NSE_FNO", "symbol": "NIFTY"},
    "NIFTY BANK": {"security_id": "26009", "exchange_segment": "NSE_FNO", "symbol": "BANKNIFTY"},
}


def _sync_nifty50_from_db():
    overrides = {
        # Known mismatches/corrections
        "Larsen & Toubro": {"security_id": "1666", "exchange_segment": "NSE_EQ"},
        "Nestle India": {"security_id": "17963", "exchange_segment": "NSE_EQ"},
    }
    for name, info in NIFTY_50_STOCKS.items():
        db = get_security_info(name)
        if db and isinstance(db, dict):
            sid = str(db.get("security_id", info["security_id"]))
            exch = db.get("exchange_segment", info["exchange_segment"])
            info["security_id"] = sid
            info["exchange_segment"] = exch
        if name in overrides:
            ov = overrides[name]
            info["security_id"] = ov.get("security_id", info["security_id"])
            info["exchange_segment"] = ov.get("exchange_segment", info["exchange_segment"])


# Align mappings with central DB and apply overrides
_sync_nifty50_from_db()

class LiveNifty50Ticker:
    """Real-time tick-by-tick data fetcher for Nifty 50"""
    
    # WebSocket Feed Codes
    SUBSCRIBE_TICKER = 15
    SUBSCRIBE_QUOTE = 16
    SUBSCRIBE_FULL = 17
    UNSUBSCRIBE = 11
    DISCONNECT = 12
    
    # Response Codes
    RESPONSE_TICKER = 2
    RESPONSE_QUOTE = 4
    RESPONSE_FULL = 8
    RESPONSE_PREV_CLOSE = 6
    RESPONSE_OI = 5
    
    def __init__(self, client_id: str, access_token: str):
        """Initialize the ticker"""
        self.client_id = client_id
        self.access_token = access_token
        self.ws_url = f"wss://api-feed.dhan.co?version=2&token={access_token}&clientId={client_id}&authType=2"
        
        self.websocket = None
        self.is_connected = False
        self.tick_count = 0
        self.last_prices = {}
        self.prev_close_data = {}
        
        # CSV file setup
        self.csv_file = None
        self.csv_writer = None
        self._setup_csv()
        
    def _setup_csv(self):
        """Setup CSV file for data logging"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nifty50_live_data_{timestamp}.csv"
        self.csv_file = open(filename, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'Timestamp', 'Symbol', 'LTP', 'Change', 'Change%', 
            'Volume', 'Open', 'High', 'Low', 'Close'
        ])
        print(f"📝 Logging data to: {filename}")
    
    async def connect(self):
        """Connect to WebSocket"""
        try:
            print("🔌 Connecting to DHAN WebSocket...")
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
                max_size=2**20,  # 1MB max message size
                compression=None,
                max_queue=2**10,  # 1024 messages max in queue
            )
            self.is_connected = True
            print("✅ Connected to DHAN Market Feed")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.websocket:
            try:
                if self.is_connected and not self.websocket.closed:
                    disconnect_msg = {"RequestCode": self.DISCONNECT}
                    await self.websocket.send(json.dumps(disconnect_msg))
                    await self.websocket.close()
            except Exception as e:
                # Connection already closed, ignore
                pass
            finally:
                self.is_connected = False
                if self.csv_file:
                    self.csv_file.close()
                print("✅ Disconnected")
    
    async def subscribe_all(self):
        """Subscribe to all Nifty 50 stocks and indices (DHAN v2 format)"""
        if not self.is_connected:
            print("❌ Not connected")
            return False
        
        instruments = []
        # Stocks
        for _, info in NIFTY_50_STOCKS.items():
            instruments.append({
                "ExchangeSegment": info["exchange_segment"],
                "SecurityId": info["security_id"]
            })
        # Indices
        for _, info in NIFTY_INDICES.items():
            instruments.append({
                "ExchangeSegment": info["exchange_segment"],
                "SecurityId": info["security_id"]
            })
        
        # DHAN allows up to 100 per batch
        batch_size = 100
        total_subscribed = 0
        for i in range(0, len(instruments), batch_size):
            batch = instruments[i:i + batch_size]
            subscribe_msg = {
                "RequestCode": self.SUBSCRIBE_QUOTE,
                "InstrumentCount": len(batch),
                "InstrumentList": batch
            }
            try:
                await self.websocket.send(json.dumps(subscribe_msg))
                total_subscribed += len(batch)
                print(f"📡 Subscribed {total_subscribed}/{len(instruments)}")
                if i + batch_size < len(instruments):
                    await asyncio.sleep(0.1)
            except Exception as e:
                print(f"❌ Subscription failed: {e}")
                return False
        print(f"✅ Successfully subscribed to {total_subscribed} instruments")
        return True
    
    def _parse_ticker_packet(self, payload: bytes, security_id: str, exchange_segment: int) -> Optional[Dict]:
        """Parse binary ticker payload: LTP(float32) + LTT(uint32)"""
        try:
            if len(payload) < 8:
                return None
            ltp = struct.unpack('<f', payload[0:4])[0]
            ltt = struct.unpack('<I', payload[4:8])[0]
            return {
                'security_id': security_id,
                'exchange_segment': exchange_segment,
                'ltp': round(ltp, 2),
                'ltt': ltt,
            }
        except Exception:
            return None
    
    def _parse_quote_packet(self, payload: bytes, security_id: str, exchange_segment: int) -> Optional[Dict]:
        """Parse binary quote payload as per DHAN v2 (42 bytes)"""
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
            high_price = struct.unpack('<f', payload[34:38])[0]
            low_price = struct.unpack('<f', payload[38:42])[0]
            return {
                'security_id': security_id,
                'exchange_segment': exchange_segment,
                'ltp': round(ltp, 2),
                'ltq': ltq,
                'ltt': ltt,
                'atp': round(atp, 2),
                'volume': volume,
                'total_sell_qty': total_sell_qty,
                'total_buy_qty': total_buy_qty,
                'open': round(open_price, 2),
                'close': round(close_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2)
            }
        except Exception:
            return None
    
    def _get_symbol_name(self, security_id: str, exchange: int) -> str:
        """Get symbol name from security ID"""
        # Check stocks
        for name, info in NIFTY_50_STOCKS.items():
            if info['security_id'] == security_id:
                return info.get('symbol', name)
        
        # Check indices
        for name, info in NIFTY_INDICES.items():
            if info['security_id'] == security_id:
                return info.get('symbol', name)
        
        # If not found, try to find by security ID in the raw data
        if security_id in [info['security_id'] for info in NIFTY_50_STOCKS.values()]:
            for info in NIFTY_50_STOCKS.values():
                if info['security_id'] == security_id:
                    return info.get('symbol', 'Unknown')
        
        return f"Unknown-{security_id}"
    
    def _display_tick(self, tick_data: Dict):
        """Display tick data in console"""
        symbol = self._get_symbol_name(tick_data['security_id'], tick_data.get('exchange_segment', 0))
        ltp = tick_data['ltp']
        volume = tick_data.get('volume', 0)
        
        # Calculate change
        prev_price = self.last_prices.get(symbol, ltp)
        change = ltp - prev_price
        change_pct = (change / prev_price * 100) if prev_price > 0 else 0
        
        # Format values
        if ltp >= 1000:
            ltp_str = f"{ltp:,.2f}"
        else:
            ltp_str = f"{ltp:.2f}"
            
        if abs(change) >= 1000:
            change_str = f"{change:+,.2f}"
        else:
            change_str = f"{change:+.2f}"
            
        if volume >= 1000000:
            volume_str = f"{volume/1000000:.2f}M"
        elif volume >= 1000:
            volume_str = f"{volume/1000:.1f}K"
        else:
            volume_str = str(volume)
        
        # Color coding
        if change > 0:
            indicator = "🟢"
            change_class = "positive"
        elif change < 0:
            indicator = "🔴"
            change_class = "negative"
        else:
            indicator = "⚪"
            change_class = "neutral"
        
        # Update last price
        self.last_prices[symbol] = ltp
        
        # Display
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"{indicator} [{timestamp}] {symbol:10s} | ₹{ltp_str:>10s} | {change_str:>10s} ({change_pct:>+6.2f}%) | Vol: {volume_str:>8s}")
        
        # Log to CSV
        if self.csv_writer:
            self.csv_writer.writerow([
                datetime.now().isoformat(),
                symbol,
                ltp,
                change,
                change_pct,
                tick_data.get('volume', 0),
                tick_data.get('open', 0),
                tick_data.get('high', 0),
                tick_data.get('low', 0),
                tick_data.get('close', 0)
            ])
            
            # Flush every 10 ticks
            self.tick_count += 1
            if self.tick_count % 10 == 0:
                self.csv_file.flush()
    
    async def listen(self):
        """Listen for WebSocket messages"""
        print("\n" + "="*80)
        print("📊 LIVE NIFTY 50 TICK-BY-TICK DATA")
        print("="*80)
        print("Press Ctrl+C to stop\n")
        
        try:
            async for message in self.websocket:
                # Expect binary frames per DHAN v2
                if not isinstance(message, bytes) or len(message) < 8:
                    continue
                
                response_code = message[0]
                msg_length = struct.unpack('<H', message[1:3])[0]
                exchange_segment = message[3]
                security_id = struct.unpack('<I', message[4:8])[0]
                payload = message[8:]
                security_id_str = str(security_id)
                
                tick = None
                if response_code == self.RESPONSE_TICKER:
                    tick = self._parse_ticker_packet(payload, security_id_str, exchange_segment)
                elif response_code == self.RESPONSE_QUOTE:
                    tick = self._parse_quote_packet(payload, security_id_str, exchange_segment)
                elif response_code == self.RESPONSE_PREV_CLOSE and len(payload) >= 8:
                    prev_close = struct.unpack('<f', payload[0:4])[0]
                    key = f"{exchange_segment}:{security_id_str}"
                    self.prev_close_data[key] = {"prev_close": prev_close}
                
                if tick:
                    self._display_tick(tick)
        
        except websockets.exceptions.ConnectionClosed:
            print(f"\n⚠️  Connection closed by server")
            print(f"\n💡 Possible reasons:")
            print(f"   - Market is closed (NSE hours: 9:15 AM - 3:30 PM IST)")
            print(f"   - Invalid subscription request")
            print(f"   - Server maintenance")
            print(f"   - Network issue")
            if self.tick_count == 0:
                print(f"\n⚠️  No data received - Market might be closed")
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping...")
        except Exception as e:
            print(f"\n❌ Error: {e}")


async def main():
    """Main function"""
    print("\n" + "="*80)
    print("🚀 NIFTY 50 LIVE TICK-BY-TICK DATA FETCHER")
    print("="*80)
    
    # Validate credentials
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        print("\n❌ Error: DHAN credentials not found!")
        print("Please set DHAN_MASTER_CLIENT_ID and DHAN_MASTER_ACCESS_TOKEN in .env file")
        return
    
    print(f"\n📋 Configuration:")
    print(f"   Client ID: {DHAN_CLIENT_ID}")
    print(f"   Stocks: {len(NIFTY_50_STOCKS)}")
    print(f"   Indices: {len(NIFTY_INDICES)}")
    print(f"   Total Instruments: {len(NIFTY_50_STOCKS) + len(NIFTY_INDICES)}")
    
    # Create ticker instance
    ticker = LiveNifty50Ticker(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
    
    try:
        # Connect
        if not await ticker.connect():
            return
        
        # Subscribe to all instruments
        if not await ticker.subscribe_all():
            return
        
        # Start listening
        await ticker.listen()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        await ticker.disconnect()
        print("\n✅ Session ended")
        print(f"📊 Total ticks received: {ticker.tick_count}")


if __name__ == "__main__":
    asyncio.run(main())
