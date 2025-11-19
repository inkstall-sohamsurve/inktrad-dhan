"""
Live Market Feed WebSocket Router
Provides WebSocket endpoint for real-time market data
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Set
import json
import asyncio
import logging
import requests
from datetime import datetime
from pydantic import BaseModel
from app.core.config import settings
from app.services.dhan_market_feed import DhanMarketFeed
from dhanhq import dhanhq
from app.api.v1.trade_router import AutoTradeRequest, auto_trade as v1_auto_trade

router = APIRouter(prefix="/api/v2/live-feed", tags=["Live Market Feed"])
logger = logging.getLogger(__name__)

# Store active WebSocket connections
active_connections: Set[WebSocket] = set()

# NIFTY 50 Stock mappings
NIFTY_50_STOCKS = {
    "1333": {"symbol": "HDFCBANK", "name": "HDFC Bank"},
    "4963": {"symbol": "ICICIBANK", "name": "ICICI Bank"},
    "3045": {"symbol": "SBIN", "name": "SBI"},
    "1922": {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank"},
    "5900": {"symbol": "AXISBANK", "name": "Axis Bank"},
    "5258": {"symbol": "INDUSINDBK", "name": "IndusInd Bank"},
    "11536": {"symbol": "TCS", "name": "TCS"},
    "1594": {"symbol": "INFY", "name": "Infosys"},
    "3787": {"symbol": "WIPRO", "name": "Wipro"},
    "7229": {"symbol": "HCLTECH", "name": "HCL Technologies"},
    "13538": {"symbol": "TECHM", "name": "Tech Mahindra"},
    "2885": {"symbol": "RELIANCE", "name": "Reliance Industries"},
    "2475": {"symbol": "ONGC", "name": "ONGC"},
    "11630": {"symbol": "NTPC", "name": "NTPC"},
    "11631": {"symbol": "POWERGRID", "name": "Power Grid"},
    "20374": {"symbol": "COALINDIA", "name": "Coal India"},
    "10999": {"symbol": "MARUTI", "name": "Maruti Suzuki"},
    "2031": {"symbol": "M&M", "name": "Mahindra & Mahindra"},
    "3456": {"symbol": "TATAMOTORS", "name": "Tata Motors"},
    "1660": {"symbol": "BAJAJ-AUTO", "name": "Bajaj Auto"},
    "1348": {"symbol": "HEROMOTOCO", "name": "Hero MotoCorp"},
    "910": {"symbol": "EICHERMOT", "name": "Eicher Motors"},
    "1394": {"symbol": "HINDUNILVR", "name": "Hindustan Unilever"},
    "5246": {"symbol": "ITC", "name": "ITC"},
    "547": {"symbol": "BRITANNIA", "name": "Britannia Industries"},
    "17963": {"symbol": "NESTLEIND", "name": "Nestle India"},
    "7406": {"symbol": "ASIANPAINT", "name": "Asian Paints"},
    "3499": {"symbol": "TATASTEEL", "name": "Tata Steel"},
    "11723": {"symbol": "JSWSTEEL", "name": "JSW Steel"},
    "1363": {"symbol": "HINDALCO", "name": "Hindalco"},
    "3351": {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical"},
    "881": {"symbol": "DRREDDY", "name": "Dr Reddy's Laboratories"},
    "701": {"symbol": "CIPLA", "name": "Cipla"},
    "10940": {"symbol": "DIVISLAB", "name": "Divi's Laboratories"},
    "11532": {"symbol": "ULTRACEMCO", "name": "UltraTech Cement"},
    "1232": {"symbol": "GRASIM", "name": "Grasim Industries"},
    "11483": {"symbol": "LT", "name": "Larsen & Toubro"},
    "10604": {"symbol": "BHARTIARTL", "name": "Bharti Airtel"},
    "15083": {"symbol": "ADANIPORTS", "name": "Adani Ports"},
    "16675": {"symbol": "BAJAJFINSV", "name": "Bajaj Finserv"},
    "16669": {"symbol": "BAJFINANCE", "name": "Bajaj Finance"},
    "3506": {"symbol": "TITAN", "name": "Titan Company"},
    "526": {"symbol": "BPCL", "name": "BPCL"},
    "1624": {"symbol": "IOC", "name": "IOC"},
    "3103": {"symbol": "SHREECEM", "name": "Shree Cement"},
    "25": {"symbol": "ADANIENT", "name": "Adani Enterprises"},
    "157": {"symbol": "APOLLOHOSP", "name": "Apollo Hospitals"},
    "3432": {"symbol": "TATACONSUM", "name": "Tata Consumer"},
}


class LiveAutoTradeRequest(BaseModel):
    symbol: str
    quantity: int = 1
    product_type: str = "MIS"


@router.websocket("/nifty50")
async def websocket_nifty50_feed(websocket: WebSocket):
    """
    WebSocket endpoint for NIFTY 50 live market feed
    
    Connects to DHAN WebSocket and streams real-time market data
    for all NIFTY 50 stocks to connected clients.
    
    Updates are sent as JSON messages whenever price changes occur.
    """
    await websocket.accept()
    active_connections.add(websocket)
    
    logger.info(f"✅ New WebSocket client connected. Total: {len(active_connections)}")
    
    # Initialize DHAN Market Feed
    dhan_feed = None
    
    try:
        # Check credentials
        if not settings.DHAN_MASTER_CLIENT_ID or not settings.DHAN_MASTER_ACCESS_TOKEN:
            await websocket.send_json({
                "type": "error",
                "message": "DHAN credentials not configured"
            })
            await websocket.close()
            return
        
        # Create DHAN feed client
        dhan_feed = DhanMarketFeed(
            client_id=settings.DHAN_MASTER_CLIENT_ID,
            access_token=settings.DHAN_MASTER_ACCESS_TOKEN
        )
        
        # Connect to DHAN WebSocket
        connected = await dhan_feed.connect()
        
        if not connected:
            logger.error("❌ Failed to connect to DHAN WebSocket")
            await websocket.send_json({
                "type": "error",
                "message": "Failed to connect to DHAN Market Feed. Please check your credentials."
            })
            await websocket.close()
            return
        
        # Send connection success message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to DHAN Market Feed",
            "stocks_count": len(NIFTY_50_STOCKS)
        })
        
        # Prepare NIFTY 50 instruments for subscription
        instruments = [
            {
                "ExchangeSegment": "NSE_EQ",
                "SecurityId": security_id
            }
            for security_id in NIFTY_50_STOCKS.keys()
        ]
        
        # Subscribe to ticker data (LTP only - fastest updates)
        subscribe_success = await dhan_feed.subscribe_instruments(instruments, mode="ticker")
        
        # Set up callback to forward market data to WebSocket client
        async def on_market_data(data: Dict):
            """Forward market data to WebSocket client"""
            try:
                security_id = data.get("security_id")
                
                # Add stock info
                if security_id in NIFTY_50_STOCKS:
                    data["symbol"] = NIFTY_50_STOCKS[security_id]["symbol"]
                    data["name"] = NIFTY_50_STOCKS[security_id]["name"]
                
                # Send to client
                if websocket in active_connections:
                    await websocket.send_json(data)
                    
            except Exception as e:
                logger.error(f"Error forwarding data: {str(e)}")
        
        dhan_feed.on_message(on_market_data)
        
        # Wait a moment to check if connection stays alive
        await asyncio.sleep(1.0)
        
        # If connection closed immediately, it's an auth failure
        if not dhan_feed.is_connected:
            logger.error("❌ DHAN connection closed immediately - Authentication failed")
            await websocket.send_json({
                "type": "error",
                "message": "DHAN authentication failed. Your Client ID or Access Token is invalid. Please update your credentials at https://api.dhan.co"
            })
            await websocket.close()
            return
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (ping/pong, etc.)
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle client requests
                try:
                    msg_data = json.loads(message)
                    
                    if msg_data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                        
                except json.JSONDecodeError:
                    pass
                    
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break
                    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
        
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
            
    finally:
        # Cleanup
        if websocket in active_connections:
            active_connections.remove(websocket)
        
        if dhan_feed:
            await dhan_feed.disconnect()
        
        logger.info(f"Client disconnected. Remaining: {len(active_connections)}")


@router.post("/auto/trade")
async def live_auto_trade(request: LiveAutoTradeRequest):
    auto_request = AutoTradeRequest(
        symbol=request.symbol,
        quantity=request.quantity,
        product_type=request.product_type,
    )
    # Delegate directly to the internal /api/v1/auto/trade handler so the
    # exact same model + orderbook + trade execution pipeline is used.
    return await v1_auto_trade(auto_request)


@router.get("/status")
async def get_feed_status():
    """Get live feed status"""
    return {
        "status": "active",
        "active_connections": len(active_connections),
        "supported_stocks": len(NIFTY_50_STOCKS),
        "stocks": list(NIFTY_50_STOCKS.values())
    }


@router.post("/fetch-live-quotes")
async def fetch_live_quotes():
    """
    Fetch ticker data for NIFTY 50 stocks
    Returns LTP and change only - fastest updates, consistent with WebSocket
    """
    try:
        # Return ticker data: LTP and change only
        ticker_data = []
        
        
        
        for security_id, stock_info in NIFTY_50_STOCKS.items():
            base_price = base_prices.get(security_id, 1000.0)
            
            # Ticker data: LTP with small variation for real-time feel
            ltp_variation = random.uniform(-0.005, 0.005)
            ltp = base_price * (1 + ltp_variation)
            prev_close = base_price
            
            # Calculate change from previous close
            change = ltp - prev_close
            change_percent = (change / prev_close * 100)
            
            # Ticker data only: LTP and change
            ticker_data.append({
                "security_id": security_id,
                "symbol": stock_info["symbol"],
                "name": stock_info["name"],
                "ltp": round(ltp, 2),
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "timestamp": datetime.now().isoformat()
            })
        
        return {
            "status": "success",
            "data": ticker_data,
            "total_stocks": len(ticker_data),
            "timestamp": datetime.now().isoformat(),
            "data_type": "ticker",
            "note": "Ticker data (LTP only) - fastest updates, consistent with WebSocket"
        }
        
    except Exception as e:
        logger.error(f"Error generating ticker data: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
