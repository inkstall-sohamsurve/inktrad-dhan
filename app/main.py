"""
Main FastAPI application for Inktrad trading platform.
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.websockets import WebSocketState
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db.database import Database
from app.api.v1 import auth_router, dhan_router, watchlist_router, live_feed_router, trade_router, backtest_router
from app.services.websocket_manager import connection_manager, dhan_ws_manager
from app.services.options_chain_service import OptionsChainService
from app.services.mcx_options_chain_service import MCXOptionsChainService
from app.services.model_service import ModelService
from app.services.trade_service import TradeService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("=" * 80)
    logger.info("🚀 Starting Inktrad Backend...")
    logger.info("=" * 80)
    
    # Connect to MongoDB
    logger.info("📦 Connecting to MongoDB...")
    await Database.connect_db()
    logger.info("✅ MongoDB connected")

    ModelService.initialize()

    # Start DHAN WebSocket feed in background
    logger.info("📡 Starting DHAN WebSocket feed...")
    asyncio.create_task(dhan_ws_manager.connect())

    # Start trailing stop-loss and trade monitor workers (use master DHAN credentials)
    try:
        from app.api.v1.trade_router import get_master_user

        master_user = get_master_user()
        asyncio.create_task(TradeService.run_trailing_sl_worker(master_user, interval_seconds=1))
        asyncio.create_task(TradeService.run_trade_monitor_worker(master_user, interval_seconds=1))
        logger.info("🛡️  Trailing SL worker started")
        logger.info("🔍 Trade monitor worker started")
    except Exception as e:
        logger.error(f"Failed to start background trade workers: {e}")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ Inktrad Backend started successfully!")
    logger.info("=" * 80)
    logger.info("")
    logger.info("📊 Available Features:")
    logger.info("  ✅ Authentication & User Management")
    logger.info("  ✅ Order Placement & Management")
    logger.info("  ✅ Portfolio & Holdings")
    logger.info("  ✅ Historical Data (Daily & Intraday)")
    logger.info("  ✅ Live Market Feed (WebSocket)")
    logger.info("  ✅ Watchlist Management")
    logger.info("")
    logger.info("📖 API Documentation:")
    logger.info(f"  Swagger UI: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info(f"  ReDoc:      http://{settings.HOST}:{settings.PORT}/redoc")
    logger.info(f"  Features:   http://{settings.HOST}:{settings.PORT}/api/v2/features")
    logger.info("")
    logger.info("🔗 Quick Access:")
    logger.info(f"  Live Feed:          http://{settings.HOST}:{settings.PORT}/live-feed")
    logger.info(f"  Options Chain:      http://{settings.HOST}:{settings.PORT}/options-chain")
    logger.info(f"  Commodity Options:  http://{settings.HOST}:{settings.PORT}/commodity-options")
    logger.info(f"  Historical:         http://{settings.HOST}:{settings.PORT}/test-historical")
    logger.info(f"  Health:             http://{settings.HOST}:{settings.PORT}/health")
    logger.info("")
    logger.info("💡 Tip: Open http://localhost:8000/commodity-options for live commodity options data!")
    logger.info("")
    logger.info("=" * 80)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Inktrad Backend...")
    
    # Disconnect from DHAN WebSocket
    await dhan_ws_manager.disconnect()
    
    # Close MongoDB connection
    await Database.close_db()
    
    logger.info("✅ Inktrad Backend shut down successfully!")


# Create FastAPI application
app = FastAPI(
    title="Inktrad Trading Platform API",
    description="Backend API for Inktrad - A modern trading platform with real-time market data",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
# Add "null" origin to support file:// protocol (for direct HTML file access)
# Add common development ports to support Vite dev server on any port
cors_origins = settings.cors_origins_list + [
    "null",
    "http://localhost:5174",  # Vite alternate port
    "http://localhost:5175",  # Vite alternate port
    "http://localhost:5176",  # Vite alternate port
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Include routers
app.include_router(auth_router.router)
app.include_router(dhan_router.router)
app.include_router(watchlist_router.router)
app.include_router(live_feed_router.router)
app.include_router(trade_router.router)
app.include_router(backtest_router.router)

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API health check."""
    return {
        "message": "Welcome to Inktrad Trading Platform API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "test_pages": {
            "historical_data": "/test-historical",
            "live_market_data": "/test-live-market"
        }
    }

@app.get("/test-historical", tags=["Testing"])
async def test_historical_page():
    """Serve the historical data test page."""
    html_path = Path(__file__).parent / "static" / "test_historical.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"error": "Test page not found"}


@app.get("/live-feed", tags=["Testing"])
async def live_feed_page():
    html_path = Path(__file__).parent / "static" / "live_feed.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"error": "Live feed page not found"}

@app.get("/options-chain", tags=["Testing"])
async def options_chain_page():
    html_path = Path(__file__).parent / "static" / "options_chain.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"error": "Options chain page not found"}

@app.get("/commodity-options", tags=["Testing"])
async def commodity_options_page():
    """Serve the commodity options chain test page."""
    html_path = Path(__file__).parent / "static" / "commodity_options.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"error": "Commodity options page not found"}


@app.get("/auto-trade", tags=["Testing"])
async def auto_trade_page():
    html_path = Path(__file__).parent / "static" / "auto_trade.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"error": "Auto trade page not found"}


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": "connected" if Database.db is not None else "disconnected",
        "dhan_websocket": "connected" if dhan_ws_manager.is_connected else "disconnected",
        "active_connections": len(connection_manager.active_connections),
        "subscribed_instruments": len(dhan_ws_manager.subscribed_instruments)
    }


@app.get("/api/v2/features", tags=["Info"])
async def get_features():
    """Get list of available API features."""
    return {
        "status": "success",
        "features": {
            "authentication": {
                "endpoints": ["/api/v2/auth/register", "/api/v2/auth/login"],
                "description": "User registration and authentication"
            },
            "trading": {
                "endpoints": [
                    "/api/v2/dhan/place-order",
                    "/api/v2/dhan/modify-order",
                    "/api/v2/dhan/cancel-order/{order_id}"
                ],
                "description": "Place, modify, and cancel orders"
            },
            "portfolio": {
                "endpoints": [
                    "/api/v2/dhan/positions",
                    "/api/v2/dhan/holdings",
                    "/api/v2/dhan/funds"
                ],
                "description": "Get positions, holdings, and fund information"
            },
            "historical_data": {
                "endpoints": [
                    "/api/v2/dhan/historical-data",
                    "/api/v2/dhan/intraday-data"
                ],
                "description": "Fetch historical and intraday market data",
                "status": "✅ Available"
            },
            "order_tracking": {
                "endpoints": [
                    "/api/v2/dhan/order-book",
                    "/api/v2/dhan/trade-book"
                ],
                "description": "View order book and trade history"
            },
            "watchlist": {
                "endpoints": [
                    "/api/v2/watchlist",
                    "/api/v2/watchlist/{watchlist_id}"
                ],
                "description": "Manage watchlists"
            },
            "live_feed": {
                "endpoints": [
                    "/api/v2/live-feed/nifty50",
                    "/api/v2/ws/live-feed",
                    "/api/v2/ws/options-chain"
                ],
                "description": "Real-time market data via WebSocket",
                "type": "WebSocket"
            }
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get("/api/v2/options-chain/live", tags=["Options Chain"])
async def get_live_options_chain(index: str = "NIFTY", expiry: str = None):
    """
    Get live options chain data using Dhan API
    
    Args:
        index: Index name (NIFTY or BANKNIFTY)
        expiry: Expiry date in YYYY-MM-DD format (optional, auto-fetches if not provided)
    
    Returns:
        Live options chain data
    """
    try:
        # Import the OptionsChainLive class
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        
        # Import the standalone functionality
        from live_options_chain import OptionsChainLive
        
        logger.info(f"📊 Fetching options chain for {index}, expiry: {expiry}")
        
        # Initialize the options chain fetcher
        chain = OptionsChainLive(indices=[index], expiry=expiry)
        
        # Initialize Dhan client
        if not chain.connect():
            logger.error("Failed to initialize Dhan client")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize Dhan client. Check DHAN credentials."
            )
        
        # Fetch option chain data
        results = chain.fetch_all_chains()
        
        logger.info(f"Results keys: {list(results.keys())}")
        
        # Check if we got data
        if index in results:
            data = results[index]
            logger.info(f"Data type: {type(data)}, Has data: {bool(data)}")
            
            # Check if data is valid (not empty dict or None)
            if data and isinstance(data, dict):
                # Check if it's an error response from DHAN API
                if data.get('status') == 'failure':
                    error_msg = data.get('remarks', {}).get('error_message', 'Unknown error')
                    logger.error(f"DHAN API error: {error_msg}")
                    return {
                        "status": "error",
                        "message": f"DHAN API error: {error_msg}",
                        "data": {},
                        "timestamp": datetime.now().isoformat()
                    }
                
                # Return the data as-is from DHAN API
                return {
                    "status": "success",
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.warning(f"No data or empty data for {index}")
                return {
                    "status": "error",
                    "message": f"No options chain data available for {index}. Market might be closed or invalid expiry.",
                    "data": {},
                    "timestamp": datetime.now().isoformat()
                }
        else:
            logger.error(f"Index {index} not found in results")
            return {
                "status": "error",
                "message": f"Index {index} not found in results",
                "data": {},
                "timestamp": datetime.now().isoformat()
            }
            
    except ImportError as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import options chain module: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error fetching options chain: {str(e)}",
            "data": {},
            "timestamp": datetime.now().isoformat()
        }

@app.websocket("/api/v2/ws/options-chain")
async def websocket_options_chain(websocket: WebSocket):
    """
    WebSocket endpoint for live options chain data.
    
    Provides continuous real-time updates for option chain data including:
    - Live option prices (LTP, bid/ask)
    - Open Interest (OI) and OI changes
    - Volume
    - Greeks (if available)
    - Underlying spot price
    
    Client should send initial config:
    {
        "action": "start",
        "index": "NIFTY" or "BANKNIFTY",
        "strikesEachSide": 10  (number of strikes on each side of ATM)
    }
    """
    service: OptionsChainService | None = None
    try:
        await connection_manager.connect(websocket)
        logger.info("📡 New options chain WebSocket client connected")
        
        # Expect an initial config message
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
            import json
            msg = json.loads(raw)
            
            if isinstance(msg, dict) and msg.get("action") in ("start", "subscribe"):
                index = (msg.get("index") or "NIFTY").upper()
                if index not in ("NIFTY", "BANKNIFTY"):
                    logger.warning(f"⚠️ Invalid index {index}, defaulting to NIFTY")
                    index = "NIFTY"
                
                strikes = int(msg.get("strikesEachSide") or 10)
                logger.info(f"📊 Starting options chain for {index}, strikes: ±{strikes}")
                
                async def send_cb(payload):
                    """Send data to client if still connected"""
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(payload)
                
                # Initialize and start the service
                service = OptionsChainService(
                    index=index,
                    strikes_each_side=strikes,
                    send_callback=send_cb
                )
                
                await service.start()
                
                await websocket.send_json({
                    "type": "connection",
                    "status": "started",
                    "index": index,
                    "strikesEachSide": strikes,
                    "message": f"Live options chain started for {index}"
                })
                logger.info(f"✅ Options chain service started for {index}")
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid message. Send {action:'start', index:'NIFTY|BANKNIFTY', strikesEachSide:10}"
                })
                return
                
        except asyncio.TimeoutError:
            await websocket.send_json({
                "type": "error",
                "message": "No config received within 15 seconds. Send {action:'start', index:'NIFTY|BANKNIFTY', strikesEachSide:10}"
            })
            return
        except json.JSONDecodeError:
            await websocket.send_json({
                "type": "error",
                "message": "Invalid JSON message"
            })
            return
        
        # Keep the connection alive and process control messages
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                import json
                msg = json.loads(raw)
                
                if msg.get("action") == "stop":
                    logger.info("🛑 Client requested stop")
                    break
                    
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong", "ts": datetime.now().isoformat()})
                    
            except asyncio.TimeoutError:
                # Send periodic keep-alive ping
                if websocket.client_state != WebSocketState.CONNECTED:
                    break
                await websocket.send_json({"type": "ping"})
                
            except WebSocketDisconnect:
                logger.info("📴 Client disconnected")
                break
                
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON
                
    except Exception as e:
        logger.error(f"❌ Options chain WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
        except:
            pass
    finally:
        # Cleanup
        try:
            if service:
                logger.info("🧹 Stopping options chain service...")
                await service.stop()
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
        
        connection_manager.disconnect(websocket)
        logger.info("✅ Options chain WebSocket connection closed")


@app.websocket("/api/v2/ws/commodity-options")
async def websocket_commodity_options(websocket: WebSocket):
    """
    WebSocket endpoint for live commodity options chain data (MCX).
    
    Provides continuous real-time updates for commodity option chain data including:
    - Live option prices (LTP, bid/ask)
    - Open Interest (OI) and OI changes
    - Volume
    - Greeks (Delta, Gamma, Theta, Vega)
    - Implied Volatility (IV)
    - Underlying commodity spot price
    
    Client should send initial config:
    {
        "action": "start",
        "commodity": "CRUDEOIL" | "GOLD" | "SILVER" | "NATURALGAS" | "COPPER" | "ZINC",
        "strikesEachSide": 10  (number of strikes on each side of ATM)
    }
    """
    service: MCXOptionsChainService | None = None
    try:
        await connection_manager.connect(websocket)
        logger.info("📡 New commodity options WebSocket client connected")
        
        # Expect an initial config message
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
            import json
            msg = json.loads(raw)
            
            if isinstance(msg, dict) and msg.get("action") in ("start", "subscribe"):
                commodity = (msg.get("commodity") or "CRUDEOIL").upper()
                supported_commodities = ["CRUDEOIL", "GOLD", "SILVER", "NATURALGAS", "COPPER", "ZINC"]
                
                if commodity not in supported_commodities:
                    logger.warning(f"⚠️ Invalid commodity {commodity}, defaulting to CRUDEOIL")
                    commodity = "CRUDEOIL"
                
                strikes = int(msg.get("strikesEachSide") or 10)
                logger.info(f"🏭 Starting commodity options chain for {commodity}, strikes: ±{strikes}")
                
                async def send_cb(payload):
                    """Send data to client if still connected"""
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(payload)
                
                # Initialize and start the MCX options chain service (WebSocket-based)
                service = MCXOptionsChainService(
                    commodity=commodity,
                    strikes_each_side=strikes,
                    send_callback=send_cb,
                )
                await service.start()
                
                await websocket.send_json({
                    "type": "connection",
                    "status": "started",
                    "commodity": commodity,
                    "strikesEachSide": strikes,
                    "message": f"Commodity options chain service started for {commodity}"
                })
                logger.info(f"✅ Commodity options service started for {commodity}")
                
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Send {action:'start', commodity:'CRUDEOIL|GOLD|SILVER|NATURALGAS|COPPER|ZINC', strikesEachSide:10}"
                })
                return
                
        except asyncio.TimeoutError:
            await websocket.send_json({
                "type": "error",
                "message": "No config received. Send {action:'start', commodity:'CRUDEOIL', strikesEachSide:10}"
            })
            return
        except json.JSONDecodeError:
            await websocket.send_json({
                "type": "error",
                "message": "Invalid JSON message"
            })
            return
        
        # Keep the connection alive and process control messages
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                import json
                msg = json.loads(raw)
                
                if msg.get("action") == "stop":
                    logger.info("🛑 Client requested stop")
                    break
                    
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong", "ts": datetime.now().isoformat()})
                    
            except asyncio.TimeoutError:
                # Send periodic keep-alive ping
                if websocket.client_state != WebSocketState.CONNECTED:
                    break
                await websocket.send_json({"type": "ping"})
                
            except WebSocketDisconnect:
                logger.info("📴 Client disconnected")
                break
                
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON
                
    except Exception as e:
        logger.error(f"❌ Commodity options WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
        except:
            pass
    finally:
        # Cleanup
        try:
            if service:
                logger.info("🧹 Stopping commodity options service...")
                await service.stop()
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
        
        connection_manager.disconnect(websocket)
        logger.info("✅ Commodity options WebSocket connection closed")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.RELOAD else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level="info"
    )
