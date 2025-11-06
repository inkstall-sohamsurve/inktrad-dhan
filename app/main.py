"""
Main FastAPI application for Inktrad trading platform.
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db.database import Database
from app.api.v1 import auth_router, dhan_router, watchlist_router, live_feed_router
from app.services.websocket_manager import connection_manager, dhan_ws_manager

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
cors_origins = settings.cors_origins_list + ["null"]
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
    """Serve the live market feed page with real-time NIFTY 50 data."""
    html_path = Path(__file__).parent / "static" / "live_feed.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"error": "Live feed page not found"}


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": "connected" if Database.db else "disconnected",
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
                    "/api/v2/ws/live-feed"
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


@app.websocket("/api/v2/ws/live-feed")
async def websocket_live_feed(websocket: WebSocket):
    """
    WebSocket endpoint for real-time market data feed.
    """
    connection_accepted = False

    try:
        # Accept connection first - this is crucial
        await connection_manager.connect(websocket)
        connection_accepted = True

        # Send welcome message
        await connection_manager.send_message(websocket, {
            "type": "connection",
            "status": "connected",
            "message": "Connected to Inktrad live feed"
        })

        # Listen for messages from client
        while True:
            # Check if websocket is still connected before trying to receive
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.info("WebSocket client disconnected - breaking message loop")
                break

            try:
                # Receive message with timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                action = message.get("action")

                if action == "subscribe":
                    instruments = message.get("instruments", [])
                    await connection_manager.subscribe(websocket, instruments)
                    await connection_manager.send_message(websocket, {
                        "type": "subscription", "status": "success", "action": "subscribed", "instruments": instruments
                    })

                elif action == "unsubscribe":
                    instruments = message.get("instruments", [])
                    await connection_manager.unsubscribe(websocket, instruments)
                    await connection_manager.send_message(websocket, {
                        "type": "subscription", "status": "success", "action": "unsubscribed", "instruments": instruments
                    })

                elif action == "ping":
                    await connection_manager.send_message(websocket, {
                        "type": "pong", "timestamp": message.get("timestamp")
                    })

                else:
                    await connection_manager.send_message(websocket, {
                        "type": "error", "message": f"Unknown action: {action}"
                    })

            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await connection_manager.send_message(websocket, {"type": "ping"})

            except json.JSONDecodeError:
                await connection_manager.send_message(websocket, {
                    "type": "error", "message": "Invalid JSON format"
                })

            except WebSocketDisconnect:
                logger.info("WebSocket disconnect detected in message loop")
                break

            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                # Don't break loop for minor errors, but log them

    except Exception as e:
        # This catches errors from the initial connect call or any other issues
        logger.error(f"WebSocket error: {e}")

    finally:
        # Clean up connection safely
        logger.info("Cleaning up WebSocket connection...")

        # Only try to disconnect if we actually accepted the connection
        if connection_accepted:
            connection_manager.disconnect(websocket)

            # Ensure the connection is closed from server-side
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.close()
                    logger.info("WebSocket connection closed from server-side")
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")


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
