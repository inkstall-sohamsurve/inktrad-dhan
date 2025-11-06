"""
WebSocket management system for live market data.
Implements dual architecture:
1. ConnectionManager: Manages WebSocket connections to React clients
2. DhanWebSocketManager: Manages connection to DHANHQ WebSocket feed
"""
import asyncio
import json
from typing import Dict, Set, List, Optional
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections to React frontend clients.
    Tracks which clients are subscribed to which instruments.
    """
    
    def __init__(self):
        # Active WebSocket connections: {websocket: Set[security_ids]}
        self.active_connections: Dict[WebSocket, Set[str]] = {}
        
        # Reverse mapping: {security_id: Set[websockets]}
        self.instrument_subscribers: Dict[str, Set[WebSocket]] = {}
        
        # Reference to DhanWebSocketManager
        self.dhan_ws_manager: Optional['DhanWebSocketManager'] = None
    
    def set_dhan_manager(self, dhan_manager: 'DhanWebSocketManager'):
        """Set reference to DHAN WebSocket manager."""
        self.dhan_ws_manager = dhan_manager
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection from React client."""
        try:
            # Validate WebSocket connection
            if websocket.client_state != WebSocketState.CONNECTING:
                logger.warning(f"WebSocket not in connecting state: {websocket.client_state}")
                return

            await websocket.accept()
            self.active_connections[websocket] = set()
            logger.info(f"New WebSocket connection. Total connections: {len(self.active_connections)}")

        except Exception as e:
            logger.error(f"Failed to accept WebSocket connection: {e}")
            raise
    
    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection and clean up subscriptions.
        """
        if websocket not in self.active_connections:
            return
        
        # Get all instruments this client was subscribed to
        subscribed_instruments = self.active_connections[websocket]
        
        # Remove client from instrument subscribers
        for security_id in subscribed_instruments:
            if security_id in self.instrument_subscribers:
                self.instrument_subscribers[security_id].discard(websocket)
                
                # If no more clients for this instrument, unsubscribe from DHAN
                if len(self.instrument_subscribers[security_id]) == 0:
                    del self.instrument_subscribers[security_id]
                    
                    if self.dhan_ws_manager:
                        asyncio.create_task(
                            self.dhan_ws_manager.unsubscribe_instruments([security_id])
                        )
        
        # Remove connection
        del self.active_connections[websocket]
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def subscribe(self, websocket: WebSocket, instruments: List[str]):
        """
        Subscribe a client to specific instruments.
        
        Args:
            websocket: Client WebSocket connection
            instruments: List of security IDs to subscribe to
        """
        if websocket not in self.active_connections:
            return
        
        new_instruments = []
        
        for security_id in instruments:
            # Add to client's subscriptions
            self.active_connections[websocket].add(security_id)
            
            # Add to instrument subscribers
            if security_id not in self.instrument_subscribers:
                self.instrument_subscribers[security_id] = set()
                new_instruments.append(security_id)
            
            self.instrument_subscribers[security_id].add(websocket)
        
        # Subscribe to new instruments on DHAN feed
        if new_instruments and self.dhan_ws_manager:
            await self.dhan_ws_manager.subscribe_instruments(new_instruments)
        
        logger.info(f"Client subscribed to {len(instruments)} instruments")
    
    async def unsubscribe(self, websocket: WebSocket, instruments: List[str]):
        """
        Unsubscribe a client from specific instruments.
        
        Args:
            websocket: Client WebSocket connection
            instruments: List of security IDs to unsubscribe from
        """
        if websocket not in self.active_connections:
            return
        
        instruments_to_remove = []
        
        for security_id in instruments:
            # Remove from client's subscriptions
            self.active_connections[websocket].discard(security_id)
            
            # Remove from instrument subscribers
            if security_id in self.instrument_subscribers:
                self.instrument_subscribers[security_id].discard(websocket)
                
                # If no more clients for this instrument, mark for removal
                if len(self.instrument_subscribers[security_id]) == 0:
                    del self.instrument_subscribers[security_id]
                    instruments_to_remove.append(security_id)
        
        # Unsubscribe from DHAN feed if no more clients
        if instruments_to_remove and self.dhan_ws_manager:
            await self.dhan_ws_manager.unsubscribe_instruments(instruments_to_remove)
        
        logger.info(f"Client unsubscribed from {len(instruments)} instruments")
    
    async def broadcast_tick(self, security_id: str, tick_data: dict):
        """
        Broadcast tick data to all clients subscribed to this instrument.
        
        Args:
            security_id: Security ID of the instrument
            tick_data: Tick data to broadcast
        """
        if security_id not in self.instrument_subscribers:
            return
        
        # Get all subscribers for this instrument
        subscribers = self.instrument_subscribers[security_id].copy()
        
        # Prepare message
        message = json.dumps({
            "type": "tick",
            "security_id": security_id,
            "data": tick_data
        })
        
        # Send to all subscribers
        disconnected = []
        for websocket in subscribers:
            try:
                # Check if websocket is still connected
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(message)
                else:
                    disconnected.append(websocket)
            except Exception as e:
                logger.debug(f"Error sending to client: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def send_message(self, websocket: WebSocket, message: dict):
        """Send a message to a specific client."""
        try:
            # Check if websocket is still connected
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.debug("WebSocket not connected, skipping message")
                return
                
            await websocket.send_json(message)
        except Exception as e:
            logger.debug(f"Error sending message: {e}")
            # Remove disconnected websocket
            self.disconnect(websocket)


class DhanWebSocketManager:
    """
    Manages connection to DHANHQ WebSocket feed.
    Singleton class that maintains one persistent connection to DHAN.
    Note: This is a simplified version that doesn't use DHAN's WebSocket feed
    as it requires additional configuration. For production, integrate with DHAN's
    actual WebSocket API according to their latest documentation.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DhanWebSocketManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.dhan_feed = None
        self.connection_manager: Optional[ConnectionManager] = None
        self.subscribed_instruments: Set[str] = set()
        self.is_connected = False
        self.reconnect_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._running = False
    
    def set_connection_manager(self, connection_manager: ConnectionManager):
        """Set reference to ConnectionManager."""
        self.connection_manager = connection_manager
    
    async def connect(self):
        """
        Connect to DHAN WebSocket feed.
        Note: This is a placeholder implementation. The DHAN marketfeed library
        has event loop conflicts when used with FastAPI. For production, you should:
        1. Use DHAN's REST API polling for quotes
        2. Or implement a separate process for WebSocket feed
        3. Or wait for DHAN to provide async-compatible library
        """
        try:
            logger.info("Initializing DHAN WebSocket manager...")
            
            # Check if credentials are configured
            if not settings.DHAN_MASTER_CLIENT_ID or not settings.DHAN_MASTER_ACCESS_TOKEN:
                logger.warning("⚠️  DHAN credentials not configured. WebSocket feed will not be active.")
                logger.warning("   Add DHAN_MASTER_CLIENT_ID and DHAN_MASTER_ACCESS_TOKEN to .env file")
                logger.info("✅ REST API endpoints are still available for historical data")
                return
            
            # Mark as connected (placeholder mode)
            self.is_connected = False
            logger.info("✅ DHAN WebSocket manager initialized (placeholder mode)")
            logger.info("   Note: Live feed requires additional setup. See DHAN_WEBSOCKET_INTEGRATION.md")
            logger.info("   Historical data API is fully functional via REST endpoints")
            
        except Exception as e:
            logger.error(f"Failed to initialize DHAN WebSocket: {e}")
            self.is_connected = False
    
    async def _run_feed_async(self):
        """Run the DHAN feed in an asynchronous loop (placeholder)."""
        # This is a placeholder. Actual implementation would poll DHAN's REST API
        # or use a separate process for WebSocket feed to avoid event loop conflicts
        pass
    
    def _on_connect(self):
        """Callback when connected to DHAN."""
        logger.info("🔗 DHAN WebSocket connection established")
        self.is_connected = True
    
    def _on_close(self):
        """Callback when DHAN connection closes."""
        logger.warning("DHAN WebSocket connection closed")
        self.is_connected = False
    
    def _on_error(self, error):
        """Callback when DHAN encounters an error."""
        logger.error(f"DHAN WebSocket error: {error}")
    
    def _on_message(self, message):
        """Handle incoming messages from DHAN."""
        try:
            # Process the message asynchronously
            asyncio.create_task(self._process_feed_data(message))
        except Exception as e:
            logger.error(f"Error processing DHAN message: {e}")
    
    async def _process_feed_data(self, data):
        """Process incoming feed data and broadcast to clients."""
        try:
            if isinstance(data, dict) and 'data' in data:
                ticks = data['data']
                for tick in ticks:
                    security_id = str(tick.get('security_id', ''))
                    
                    if security_id and self.connection_manager:
                        # Broadcast to connected clients
                        await self.connection_manager.broadcast_tick(security_id, tick)
                        
            elif isinstance(data, list):
                # Handle list of ticks
                for tick in data:
                    security_id = str(tick.get('security_id', ''))
                    
                    if security_id and self.connection_manager:
                        # Broadcast to connected clients
                        await self.connection_manager.broadcast_tick(security_id, tick)
                        
        except Exception as e:
            logger.error(f"Error processing feed data: {e}")
    
    async def subscribe_instruments(self, instruments: List[str]):
        """
        Subscribe to instruments on DHAN feed.
        
        Args:
            instruments: List of security IDs to subscribe to
        """
        async with self._lock:
            if not self.dhan_feed:
                logger.warning("DHAN feed not initialized. Cannot subscribe to instruments.")
                return
            
            # Filter out already subscribed instruments
            new_instruments = [inst for inst in instruments if inst not in self.subscribed_instruments]
            
            if not new_instruments:
                return
            
            try:
                # Import marketfeed for constants
                from dhanhq import marketfeed
                
                # Convert to DHAN format: [(exchange, security_id, subscription_type)]
                # Assuming NSE for now - adjust based on your needs
                sub_instruments = [(marketfeed.NSE, inst, marketfeed.Ticker) for inst in new_instruments]
                
                # Subscribe using DHAN feed
                self.dhan_feed.subscribe_symbols(sub_instruments)
                
                # Update subscribed set
                self.subscribed_instruments.update(new_instruments)
                logger.info(f"✅ Subscribed to {len(new_instruments)} instruments on DHAN feed")
                logger.info(f"Instruments: {new_instruments}")
                
            except Exception as e:
                logger.error(f"Error subscribing to instruments: {e}")
                # Still add to subscribed set for tracking
                self.subscribed_instruments.update(new_instruments)
    
    async def unsubscribe_instruments(self, instruments: List[str]):
        """
        Unsubscribe from instruments on DHAN feed.
        
        Args:
            instruments: List of security IDs to unsubscribe from
        """
        async with self._lock:
            if not self.dhan_feed:
                return
            
            # Filter instruments that are actually subscribed
            to_unsubscribe = [inst for inst in instruments if inst in self.subscribed_instruments]
            
            if not to_unsubscribe:
                return
            
            try:
                # Import marketfeed for constants
                from dhanhq import marketfeed
                
                # Convert to DHAN format: [(exchange, security_id, subscription_type)]
                unsub_instruments = [(marketfeed.NSE, inst, marketfeed.Ticker) for inst in to_unsubscribe]
                
                # Unsubscribe using DHAN feed
                self.dhan_feed.unsubscribe_symbols(unsub_instruments)
                
                # Update subscribed set
                self.subscribed_instruments.difference_update(to_unsubscribe)
                logger.info(f"✅ Unsubscribed from {len(to_unsubscribe)} instruments")
                
            except Exception as e:
                logger.error(f"Error unsubscribing from instruments: {e}")
                # Still remove from subscribed set for tracking
                self.subscribed_instruments.difference_update(to_unsubscribe)
    
    async def disconnect(self):
        """Disconnect from DHAN WebSocket feed."""
        try:
            self._running = False
            
            if self.dhan_feed:

                self.dhan_feed = None
                
            logger.info("DHAN WebSocket manager disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting from DHAN: {e}")


# Global instances
connection_manager = ConnectionManager()
dhan_ws_manager = DhanWebSocketManager()

# Link them together
connection_manager.set_dhan_manager(dhan_ws_manager)
dhan_ws_manager.set_connection_manager(connection_manager)
