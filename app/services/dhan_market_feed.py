"""
DHAN WebSocket Market Feed Service
Handles real-time market data via WebSocket connection
"""
import asyncio
import json
import struct
import websockets
from typing import Dict, List, Callable, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DhanMarketFeed:
    """
    DHAN WebSocket Market Feed Client
    Connects to DHAN's WebSocket feed and processes binary market data packets
    """
    
    # Feed Request Codes
    SUBSCRIBE_TICKER = 15      # Subscribe to Ticker Data (LTP + LTT)
    SUBSCRIBE_QUOTE = 16       # Subscribe to Quote Data (Full trade data)
    SUBSCRIBE_FULL = 17        # Subscribe to Full Data (with Market Depth)
    UNSUBSCRIBE = 11           # Unsubscribe from instruments
    DISCONNECT = 12            # Disconnect WebSocket
    
    # Feed Response Codes
    RESPONSE_TICKER = 2        # Ticker packet
    RESPONSE_QUOTE = 4         # Quote packet
    RESPONSE_FULL = 8          # Full packet
    RESPONSE_PREV_CLOSE = 6    # Previous close packet
    RESPONSE_OI = 5            # Open Interest packet
    RESPONSE_DISCONNECT = 50   # Disconnection packet
    
    def __init__(self, client_id: str, access_token: str):
        """
        Initialize DHAN Market Feed client
        
        Args:
            client_id: DHAN client ID
            access_token: DHAN access token
        """
        self.client_id = client_id
        self.access_token = access_token
        self.ws_url = f"wss://api-feed.dhan.co?version=2&token={access_token}&clientId={client_id}&authType=2"
        
        self.websocket = None
        self.is_connected = False
        self.subscribed_instruments = {}
        self.callbacks = {}
        self.prev_close_data = {}
        
    async def connect(self):
        """Establish WebSocket connection to DHAN"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            self.is_connected = True
            logger.info("✅ Connected to DHAN Market Feed WebSocket")
            
            # Start listening for messages
            asyncio.create_task(self._listen())
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to DHAN WebSocket: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.websocket and self.is_connected:
            # Send disconnect message
            disconnect_msg = {"RequestCode": self.DISCONNECT}
            await self.websocket.send(json.dumps(disconnect_msg))
            await self.websocket.close()
            self.is_connected = False
            logger.info("✅ Disconnected from DHAN Market Feed")
    
    async def subscribe_instruments(self, instruments: List[Dict], mode: str = "quote"):
        """
        Subscribe to instruments for live market data
        
        Args:
            instruments: List of instruments [{"ExchangeSegment": "NSE_EQ", "SecurityId": "1333"}, ...]
            mode: Data mode - "ticker", "quote", or "full"
        """
        if not self.is_connected:
            logger.error("❌ Not connected to WebSocket")
            return False
        
        # Determine request code based on mode
        request_code_map = {
            "ticker": self.SUBSCRIBE_TICKER,
            "quote": self.SUBSCRIBE_QUOTE,
            "full": self.SUBSCRIBE_FULL
        }
        request_code = request_code_map.get(mode, self.SUBSCRIBE_QUOTE)
        
        # Split instruments into batches of 100 (DHAN limit)
        batch_size = 100
        for i in range(0, len(instruments), batch_size):
            batch = instruments[i:i + batch_size]
            
            subscribe_msg = {
                "RequestCode": request_code,
                "InstrumentCount": len(batch),
                "InstrumentList": batch
            }
            
            try:
                await self.websocket.send(json.dumps(subscribe_msg))
                logger.info(f"📡 Subscribed to {len(batch)} instruments (mode: {mode})")
                
                # Store subscribed instruments
                for inst in batch:
                    key = f"{inst['ExchangeSegment']}:{inst['SecurityId']}"
                    self.subscribed_instruments[key] = inst
                
                # Small delay between batches
                if i + batch_size < len(instruments):
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"❌ Failed to subscribe: {str(e)}")
                return False
        
        return True
    
    def on_message(self, callback: Callable):
        """Register callback for market data messages"""
        self.callbacks['message'] = callback
    
    def on_error(self, callback: Callable):
        """Register callback for errors"""
        self.callbacks['error'] = callback
    
    async def _listen(self):
        """Listen for WebSocket messages"""
        try:
            async for message in self.websocket:
                # All responses are binary
                if isinstance(message, bytes):
                    await self._process_binary_message(message)
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning("⚠️ WebSocket connection closed")
            
            # Check if connection closed immediately (authentication failure)
            if e.code == 1000 or e.code == 1006:
                logger.error("❌ DHAN rejected connection - Invalid credentials (Client ID or Access Token)")
                logger.error("   Please verify your DHAN_MASTER_CLIENT_ID and DHAN_MASTER_ACCESS_TOKEN")
                logger.error("   Generate new credentials at: https://api.dhan.co")
            
            self.is_connected = False
        except Exception as e:
            logger.error(f"❌ Error in WebSocket listener: {str(e)}")
            if 'error' in self.callbacks:
                await self.callbacks['error'](str(e))
    
    async def _process_binary_message(self, data: bytes):
        """
        Process binary market data packet
        
        Binary format (Little Endian):
        - Byte 0: Feed Response Code
        - Bytes 1-2: Message Length (int16)
        - Byte 3: Exchange Segment
        - Bytes 4-7: Security ID (int32)
        - Bytes 8+: Payload (varies by response code)
        """
        try:
            # Parse header (8 bytes)
            if len(data) < 8:
                return
            
            response_code = data[0]
            msg_length = struct.unpack('<H', data[1:3])[0]  # Little endian int16
            exchange_segment = data[3]
            security_id = struct.unpack('<I', data[4:8])[0]  # Little endian int32
            
            # Convert security_id to string
            security_id_str = str(security_id)
            
            # Process based on response code
            if response_code == self.RESPONSE_TICKER:
                market_data = self._parse_ticker_packet(data[8:], security_id_str, exchange_segment)
            elif response_code == self.RESPONSE_QUOTE:
                market_data = self._parse_quote_packet(data[8:], security_id_str, exchange_segment)
            elif response_code == self.RESPONSE_FULL:
                market_data = self._parse_full_packet(data[8:], security_id_str, exchange_segment)
            elif response_code == self.RESPONSE_PREV_CLOSE:
                market_data = self._parse_prev_close_packet(data[8:], security_id_str, exchange_segment)
            elif response_code == self.RESPONSE_OI:
                market_data = self._parse_oi_packet(data[8:], security_id_str, exchange_segment)
            elif response_code == self.RESPONSE_DISCONNECT:
                disconnect_code = struct.unpack('<H', data[8:10])[0]
                logger.warning(f"⚠️ Disconnected by server: Code {disconnect_code}")
                return
            else:
                logger.debug(f"Unknown response code: {response_code}")
                return
            
            # Call message callback
            if 'message' in self.callbacks and market_data:
                await self.callbacks['message'](market_data)
                
        except Exception as e:
            logger.error(f"❌ Error processing binary message: {str(e)}")
    
    def _parse_ticker_packet(self, payload: bytes, security_id: str, exchange_segment: int) -> Dict:
        """Parse Ticker packet (LTP + LTT)"""
        if len(payload) < 8:
            return None
        
        # Ticker packet structure (8 bytes after header)
        ltp = struct.unpack('<f', payload[0:4])[0]  # 9-12: Last Traded Price (float32)
        ltt = struct.unpack('<I', payload[4:8])[0]  # 13-16: Last Trade Time (int32)
        
        return {
            "type": "ticker",
            "security_id": security_id,
            "exchange_segment": exchange_segment,
            "ltp": round(ltp, 2),
            "last_trade_time": ltt,
            "timestamp": datetime.now().isoformat()
        }
    
    def _parse_quote_packet(self, payload: bytes, security_id: str, exchange_segment: int) -> Dict:
        """Parse Quote packet (Full trade data)"""
        if len(payload) < 42:
            return None
        
        # Quote packet structure (42 bytes total after header)
        ltp = struct.unpack('<f', payload[0:4])[0]          # 9-12: LTP (float32)
        ltq = struct.unpack('<H', payload[4:6])[0]          # 13-14: Last Traded Quantity (int16)
        ltt = struct.unpack('<I', payload[6:10])[0]         # 15-18: Last Trade Time (int32)
        atp = struct.unpack('<f', payload[10:14])[0]        # 19-22: Average Trade Price (float32)
        volume = struct.unpack('<I', payload[14:18])[0]     # 23-26: Volume (int32)
        total_sell_qty = struct.unpack('<I', payload[18:22])[0]  # 27-30: Total Sell Quantity (int32)
        total_buy_qty = struct.unpack('<I', payload[22:26])[0]   # 31-34: Total Buy Quantity (int32)
        open_price = struct.unpack('<f', payload[26:30])[0]       # 35-38: Open (float32)
        close_price = struct.unpack('<f', payload[30:34])[0]      # 39-42: Close (float32)
        high_price = struct.unpack('<f', payload[34:38])[0]       # 43-46: High (float32)
        low_price = struct.unpack('<f', payload[38:42])[0]        # 47-50: Low (float32)
        
        # Calculate change if we have prev close
        key = f"{exchange_segment}:{security_id}"
        prev_close = self.prev_close_data.get(key, {}).get('prev_close', 0)
        
        change = 0
        change_percent = 0
        if prev_close > 0:
            change = ltp - prev_close
            change_percent = (change / prev_close) * 100
        
        return {
            "type": "quote",
            "security_id": security_id,
            "exchange_segment": exchange_segment,
            "ltp": round(ltp, 2),
            "ltq": ltq,
            "last_trade_time": ltt,
            "atp": round(atp, 2),
            "volume": volume,
            "total_sell_qty": total_sell_qty,
            "total_buy_qty": total_buy_qty,
            "open": round(open_price, 2),
            "close": round(close_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "prev_close": round(prev_close, 2) if prev_close else None,
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "timestamp": datetime.now().isoformat()
        }
    
    def _parse_full_packet(self, payload: bytes, security_id: str, exchange_segment: int) -> Dict:
        """Parse Full packet (with Market Depth)"""
        # Similar to quote but with market depth (100 bytes)
        # For now, parse the basic quote part
        return self._parse_quote_packet(payload[:42], security_id, exchange_segment)
    
    def _parse_prev_close_packet(self, payload: bytes, security_id: str, exchange_segment: int) -> Dict:
        """Parse Previous Close packet"""
        if len(payload) < 8:
            return None
        
        # Prev Close packet structure (8 bytes after header)
        prev_close = struct.unpack('<f', payload[0:4])[0]  # 9-12: Previous day closing price (float32)
        prev_oi = struct.unpack('<I', payload[4:8])[0]     # 13-16: Open Interest - previous day (int32)
        
        # Store for change calculation
        key = f"{exchange_segment}:{security_id}"
        self.prev_close_data[key] = {
            "prev_close": prev_close,
            "prev_oi": prev_oi
        }
        
        return {
            "type": "prev_close",
            "security_id": security_id,
            "exchange_segment": exchange_segment,
            "prev_close": round(prev_close, 2),
            "prev_oi": prev_oi,
            "timestamp": datetime.now().isoformat()
        }
    
    def _parse_oi_packet(self, payload: bytes, security_id: str, exchange_segment: int) -> Dict:
        """Parse Open Interest packet"""
        if len(payload) < 4:
            return None
        
        # OI packet structure (4 bytes after header)
        oi = struct.unpack('<I', payload[0:4])[0]  # 9-12: Open Interest of the contract (int32)
        
        return {
            "type": "oi",
            "security_id": security_id,
            "exchange_segment": exchange_segment,
            "oi": oi,
            "timestamp": datetime.now().isoformat()
        }
