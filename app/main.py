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
from app.api.v1 import auth_router, dhan_router, watchlist_router, margin_router
from app.api.v1 import auth_router, dhan_router, watchlist_router, live_feed_router
from app.services.websocket_manager import connection_manager, dhan_ws_manager
from app.services.options_chain_service import OptionsChainService

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
    
    # Start DHAN WebSocket feed in background
    logger.info("📡 Starting DHAN WebSocket feed...")
    asyncio.create_task(dhan_ws_manager.connect())
    
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
    logger.info(f"  Live Feed:     http://{settings.HOST}:{settings.PORT}/live-feed")
    logger.info(f"  Historical:    http://{settings.HOST}:{settings.PORT}/test-historical")
    logger.info(f"  Health:        http://{settings.HOST}:{settings.PORT}/health")
    logger.info("")
    logger.info("💡 Tip: Open http://localhost:8000/live-feed for real-time NIFTY 50 data!")
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
app.include_router(margin_router.router)
app.include_router(live_feed_router.router)


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
            "test_margin_calculator": "/test-margin",
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

@app.get("/test-margin", tags=["Testing"])
async def test_margin_page():
    """Serve the margin calculator test page."""
    html_path = Path(__file__).parent / "static" / "test_margin_calculator.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"error": "Margin calculator test page not found"}


@app.get("/live-feed", tags=["Testing"])
async def live_feed_page():
    """Serve the live market feed page with real-time NIFTY 50 data."""
    html_path = Path(__file__).parent / "static" / "live_feed.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"error": "Live feed page not found"}

@app.get("/options-chain", tags=["Testing"])
async def options_chain_page():
    """Serve the live options chain page (NIFTY / BANKNIFTY)."""
    html_path = Path(__file__).parent / "static" / "options_chain.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"error": "Options chain page not found"}


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
            "margin_calculation": {
                "endpoints": [
                    "/api/v1/margin/calculate",
                    "/api/v1/margin/validate",
                    "/api/v1/margin/stock/{security_id}",
                    "/api/v1/margin/mtf/interest",
                    "/api/v1/margin/portfolio/summary"
                ],
                "description": "Margin calculations and validations for trading",
                "status": "✅ Available"
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
    """WebSocket endpoint for live options chain snapshots."""
    service: OptionsChainService | None = None
    try:
        await connection_manager.connect(websocket)
        # Expect an initial config message
        cfg = None
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
            import json
            msg = json.loads(raw)
            if isinstance(msg, dict) and msg.get("action") in ("start", "subscribe"):
                index = (msg.get("index") or "NIFTY").upper()
                if index not in ("NIFTY", "BANKNIFTY"):
                    index = "NIFTY"
                strikes = int(msg.get("strikesEachSide") or 10)
                async def send_cb(payload):
                    # Send only if still connected
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(payload)
                service = OptionsChainService(index=index, strikes_each_side=strikes, send_callback=send_cb)
                await service.start()
                await websocket.send_json({"type": "connection", "status": "started", "index": index, "strikesEachSide": strikes})
            else:
                await websocket.send_json({"type": "error", "message": "Send {action:'start', index:'NIFTY|BANKNIFTY', strikesEachSide:10}"})
        except asyncio.TimeoutError:
            await websocket.send_json({"type": "error", "message": "No config received. Send {action:'start', ...}"})
        # Keep the connection alive and process simple control messages
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                import json
                msg = json.loads(raw)
                if msg.get("action") == "stop":
                    break
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong", "ts": datetime.now().isoformat()})
            except asyncio.TimeoutError:
                # periodic keep-alive
                if websocket.client_state != WebSocketState.CONNECTED:
                    break
                await websocket.send_json({"type": "ping"})
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"Options chain WS error: {e}")
    finally:
        try:
            if service:
                await service.stop()
        except Exception:
            pass
        connection_manager.disconnect(websocket)


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
