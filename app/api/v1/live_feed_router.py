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
from app.core.config import settings
from app.services.dhan_market_feed import DhanMarketFeed

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
        
        # Subscribe to quote data (includes OHLC, volume, etc.)
        subscribe_success = await dhan_feed.subscribe_instruments(instruments, mode="quote")
        
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
    Fetch live market quotes for NIFTY 50 stocks using DHAN REST API
    This is a polling-based alternative to WebSocket for better reliability
    """
    try:
        # Check credentials
        if not settings.DHAN_MASTER_CLIENT_ID or not settings.DHAN_MASTER_ACCESS_TOKEN:
            raise HTTPException(
                status_code=400,
                detail="DHAN credentials not configured. Please update .env file."
            )
        
        # Prepare request headers
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "access-token": settings.DHAN_MASTER_ACCESS_TOKEN,
            "clientId": settings.DHAN_MASTER_CLIENT_ID
        }
        
        # Prepare payload with all NIFTY 50 security IDs
        payload = {
            "NSE_EQ": list(NIFTY_50_STOCKS.keys())
        }
        
        # Make request to DHAN API
        response = requests.post(
            "https://api.dhan.co/v2/marketfeed/quote",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            logger.error(f"DHAN API error: {error_data}")
            
            return {
                "status": "error",
                "message": f"DHAN API returned {response.status_code}",
                "error_details": error_data,
                "timestamp": datetime.now().isoformat()
            }
        
        # Parse response
        data = response.json()
        
        if data.get("status") != "success":
            return {
                "status": "error",
                "message": "DHAN API request failed",
                "error_details": data,
                "timestamp": datetime.now().isoformat()
            }
        
        # Process quotes and add stock info
        quotes = data.get("data", {}).get("NSE_EQ", {})
        processed_quotes = []
        
        for security_id, quote_data in quotes.items():
            if security_id in NIFTY_50_STOCKS:
                stock_info = NIFTY_50_STOCKS[security_id]
                
                # Calculate change and change percent
                ltp = quote_data.get("LTP", 0)
                prev_close = quote_data.get("prev_close_price", 0) or quote_data.get("close_price", 0)
                
                change = 0
                change_percent = 0
                if prev_close and prev_close > 0:
                    change = ltp - prev_close
                    change_percent = (change / prev_close) * 100
                
                processed_quotes.append({
                    "security_id": security_id,
                    "symbol": stock_info["symbol"],
                    "name": stock_info["name"],
                    "ltp": ltp,
                    "open": quote_data.get("open", 0),
                    "high": quote_data.get("high", 0),
                    "low": quote_data.get("low", 0),
                    "close": quote_data.get("close_price", 0),
                    "prev_close": prev_close,
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2),
                    "volume": quote_data.get("volume", 0),
                    "last_trade_time": quote_data.get("LTT", 0),
                    "timestamp": datetime.now().isoformat()
                })
        
        return {
            "status": "success",
            "message": f"Fetched {len(processed_quotes)} stock quotes",
            "data": processed_quotes,
            "total_stocks": len(processed_quotes),
            "timestamp": datetime.now().isoformat()
        }
        
    except requests.exceptions.Timeout:
        logger.error("DHAN API request timed out")
        return {
            "status": "error",
            "message": "Request to DHAN API timed out",
            "timestamp": datetime.now().isoformat()
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"DHAN API request failed: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to connect to DHAN API: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching live quotes: {str(e)}")
        return {
            "status": "error",
            "message": f"Internal error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
