"""Trade execution API endpoints.

This version is configured to use a single DHAN master account from the
environment (.env) and does not require application-level authentication.
"""

import asyncio
from fastapi import APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from starlette.websockets import WebSocketState
from pydantic import BaseModel
from app.models.trade import TradeEntry, TradeExit, TradeStatus, TradeType
from app.models.user import UserInDB
from app.services.trade_service import TradeService
from app.services.dhan_service import DhanService
from app.services.model_service import ModelService
from app.services.dhan_market_feed import DhanMarketFeed
from app.core.config import settings
from app.core.security import encrypt_data
from app.db.database import Database

router = APIRouter(
    prefix="/api/v1",
    tags=["trades"]
)


class AutoTradeRequest(BaseModel):
    symbol: str
    quantity: int = 1
    product_type: str = "MIS"
    trade_type: TradeType = TradeType.INTRADAY


def get_master_user() -> UserInDB:
    """Build a synthetic UserInDB using DHAN master credentials from settings.

    This avoids the need for signup/login while still reusing the existing
    service layer that expects a UserInDB with encrypted DHAN credentials.
    """
    return UserInDB(
        _id="master",
        username="master",
        email="master@example.com",
        hashed_password="!",  # not used
        dhan_client_id=encrypt_data(settings.DHAN_MASTER_CLIENT_ID),
        dhan_access_token=encrypt_data(settings.DHAN_MASTER_ACCESS_TOKEN),
        created_at=datetime.utcnow(),
    )


async def _fetch_orderbook_depth(security_id: str, exchange_segment: str) -> Dict[str, Any]:
    feed = DhanMarketFeed(
        client_id=settings.DHAN_MASTER_CLIENT_ID,
        access_token=settings.DHAN_MASTER_ACCESS_TOKEN,
    )

    connected = await feed.connect()
    if not connected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ORDERBOOK_CONNECT_FAILED",
                "message": "Failed to connect to DHAN market feed for orderbook depth",
            },
        )

    loop = asyncio.get_running_loop()
    depth_future: asyncio.Future = loop.create_future()

    async def on_market_data(data: Dict[str, Any]):
        if (
            isinstance(data, dict)
            and data.get("type") == "full"
            and str(data.get("security_id")) == str(security_id)
            and not depth_future.done()
        ):
            depth_future.set_result(data)

    feed.on_message(on_market_data)

    instruments = [
        {
            "ExchangeSegment": exchange_segment,
            "SecurityId": str(security_id),
        }
    ]

    await feed.subscribe_instruments(instruments, mode="full")

    try:
        market_data = await asyncio.wait_for(depth_future, timeout=3.0)
    except asyncio.TimeoutError:
        await feed.disconnect()
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": "ORDERBOOK_TIMEOUT",
                "message": "Timed out waiting for orderbook depth from DHAN",
            },
        )

    await feed.disconnect()

    return {
        "best_bid_price": market_data.get("best_bid_price"),
        "best_ask_price": market_data.get("best_ask_price"),
        "bids": market_data.get("bids") or [],
        "asks": market_data.get("asks") or [],
    }


@router.get("/trades/dhan/funds", response_model=Dict[str, Any])
async def get_funds() -> Dict[str, Any]:
    """Get funds and margin information from DHAN using master credentials."""
    try:
        user = get_master_user()
        return await DhanService.get_funds(user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "FUNDS_FETCH_FAILED", "message": str(e)}
        )


@router.websocket("/ws/margin")
async def margin_websocket(websocket: WebSocket):
    user = get_master_user()
    await websocket.accept()

    try:
        while True:
            try:
                funds = await DhanService.get_funds(user)
                await websocket.send_json({
                    "type": "margin_update",
                    "data": funds
                })
                await asyncio.sleep(5)  # Update every 5 seconds
            except Exception as e:
                print(f"Error in margin websocket: {e}")
                break
    except WebSocketDisconnect:
        print("Margin websocket disconnected")
    except Exception as e:
        print(f"WebSocket connection failed: {e}")
        try:
            if websocket.application_state == WebSocketState.CONNECTED:
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except RuntimeError:
            pass
    finally:
        try:
            if websocket.application_state == WebSocketState.CONNECTED:
                await websocket.close()
        except RuntimeError:
            pass


@router.post("/trades/execute", response_model=Dict[str, Any])
async def execute_trade(
    trade_entry: TradeEntry,
) -> Dict[str, Any]:
    """
    Execute a new trade with margin and risk checks.
    
    This endpoint will:
    1. Calculate margin required for the trade
    2. Check available margin in the user's account
    3. If sufficient margin is available, place the order
    4. Create a trade record in the database
    
    Returns trade execution details including order ID and margin information.
    """
    user = get_master_user()
    return await TradeService.execute_trade(user, trade_entry)


@router.post("/auto/trade", response_model=Dict[str, Any])
async def auto_trade(request: AutoTradeRequest) -> Dict[str, Any]:
    user = get_master_user()
    model = ModelService.get_instance()

    security_info = model.resolve_security(request.symbol)
    if not security_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "UNKNOWN_SYMBOL",
                "message": f"Could not resolve security ID for symbol {request.symbol}",
            },
        )

    security_id = security_info["security_id"]
    exchange_segment = security_info["exchange_segment"]
    instrument_type = security_info["instrument_type"]

    now = datetime.now()
    from_dt = now - timedelta(minutes=90)
    from_date = from_dt.strftime("%Y-%m-%d %H:%M:%S")
    to_date = now.strftime("%Y-%m-%d %H:%M:%S")

    intraday = await DhanService.get_intraday_data(
        user,
        security_id=security_id,
        exchange_segment=exchange_segment,
        instrument_type=instrument_type,
        from_date=from_date,
        to_date=to_date,
    )

    opens = intraday.get("open") or []
    highs = intraday.get("high") or []
    lows = intraday.get("low") or []
    closes = intraday.get("close") or []
    volumes = intraday.get("volume") or []

    length = min(len(opens), len(highs), len(lows), len(closes))
    if length == 0:
        return {
            "signal": "HOLD",
            "entry": None,
            "sl": None,
            "target": None,
            "limit_price": None,
            "order_response": {
                "status": "NO_TRADE",
                "message": "No intraday data returned from DHAN (0 candles).",
            },
        }

    start_index = max(0, length - 60)
    candles = []
    for i in range(start_index, length):
        volume_value = volumes[i] if i < len(volumes) else 0
        candles.append(
            {
                "open": float(opens[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(closes[i]),
                "volume": float(volume_value),
            }
        )

    # Fetch orderbook depth, but never fail the whole request if it times out.
    try:
        orderbook = await _fetch_orderbook_depth(
            security_id=str(security_id), exchange_segment=exchange_segment
        )
    except HTTPException as e:
        detail = e.detail if isinstance(e.detail, dict) else {"message": str(e.detail)}
        orderbook = {
            "best_bid_price": None,
            "best_ask_price": None,
            "bids": [],
            "asks": [],
            "error": detail,
        }

    prediction = model.predict(candles, orderbook, symbol=request.symbol)
    signal = prediction["signal"]
    limit_price = prediction["limit_price"]
    sl = prediction["stoploss"]
    target = prediction["target"]

    if signal.upper() == "HOLD" or limit_price is None or sl is None or target is None:
        return {
            "signal": signal,
            "entry": prediction.get("ltp"),
            "sl": sl,
            "target": target,
            "limit_price": limit_price,
            "orderbook": orderbook,
            "order_response": {
                "status": "NO_TRADE",
                "message": "Model signalled HOLD or incomplete pricing information",
            },
        }

    trade_response = await TradeService.execute_model_trade(
        user=user,
        symbol=request.symbol,
        security_id=str(security_id),
        exchange_segment=exchange_segment,
        quantity=request.quantity,
        prediction=signal,
        limit_price=float(limit_price),
        sl=float(sl),
        target=float(target),
        product_type=request.product_type,
        trade_type=request.trade_type,
        tick_size=float(prediction.get("tick_size") or 0.05),
        is_simulated=False,
    )

    return {
        "signal": signal,
        "entry": prediction.get("ltp"),
        "sl": sl,
        "target": target,
        "limit_price": limit_price,
        "orderbook": orderbook,
        "order_response": trade_response,
    }


@router.post("/trades/exit/{trade_id}", response_model=Dict[str, Any])
async def exit_trade(
    trade_id: str,
    exit_data: TradeExit,
) -> Dict[str, Any]:
    """
    Exit an existing trade.
    
    This endpoint will:
    1. Find the open trade by ID
    2. Place an exit order
    3. Calculate P&L and charges
    4. Update the trade record with exit details
    
    Returns exit trade details including P&L information.
    """
    user = get_master_user()
    return await TradeService.exit_trade(user, trade_id, exit_data)


@router.get("/trades/sync", response_model=Dict[str, Any])
async def sync_trades() -> Dict[str, Any]:
    """Sync trades from DHAN with local database.

    This only updates existing trades in Mongo that already have a
    ``dhan_order_id``. It does **not** change place/exit behaviour; it just
    reconciles status with the DHAN order book.
    """

    try:
        user = get_master_user()

        # Try to reach DHAN order book, but treat any failure as a no-op so
        # the frontend never breaks because of sync. This keeps execute/exit
        # behaviour intact and only affects optional reconciliation.
        try:
            orders_response = await DhanService.get_order_book(user)
        except Exception:
            # Log-and-ignore style behaviour: nothing is synced, but we
            # still report success so the UI can continue.
            return {
                "status": "success",
                "message": "Skipped DHAN sync (order book unavailable)",
                "updated_count": 0,
            }

        # Normalise into a list of order dicts, handling multiple possible
        # shapes safely so we never iterate over plain strings.
        orders: list[Any] = []  # type: ignore[assignment]
        if isinstance(orders_response, list):
            orders = orders_response
        elif isinstance(orders_response, dict):
            for key in ("data", "orders", "orderList", "order_book"):
                value = orders_response.get(key)
                if isinstance(value, list):
                    orders = value
                    break

        if not isinstance(orders, list) or not orders:
            return {
                "status": "success",
                "message": "No DHAN orders to sync",
                "updated_count": 0,
            }

        trades_collection = Database.get_trades_collection()

        updated_count = 0
        status_map = {
            "EXECUTED": TradeStatus.ENTERED,
            "CANCELLED": TradeStatus.REJECTED,
            "REJECTED": TradeStatus.REJECTED,
        }

        for order in orders:
            if not isinstance(order, dict):
                continue

            order_id = order.get("orderId")
            if not order_id:
                continue

            trade = await trades_collection.find_one({"dhan_order_id": order_id})
            if not trade:
                continue

            order_status = order.get("orderStatus")
            trade_status = status_map.get(order_status)

            if trade_status and trade.get("status") != trade_status:
                await trades_collection.update_one(
                    {"dhan_order_id": order_id},
                    {
                        "$set": {
                            "status": trade_status,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                updated_count += 1

        return {
            "status": "success",
            "message": f"Synced {updated_count} trades with DHAN",
            "updated_count": updated_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TRADE_SYNC_FAILED", "message": str(e)},
        )


@router.get("/trades/history", response_model=Dict[str, Any])
async def get_trade_history(
    limit: int = 10,
    skip: int = 0,
    status: Optional[TradeStatus] = None,
    trade_type: Optional[TradeType] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get user's trade history with filtering and pagination.
    
    Args:
        limit: Number of trades to return (default: 10)
        skip: Number of trades to skip (for pagination)
        status: Filter by trade status (PENDING, ENTERED, EXITED, etc.)
        trade_type: Filter by trade type (INTRADAY, DELIVERY)
        from_date: Filter trades after this date (YYYY-MM-DD)
        to_date: Filter trades before this date (YYYY-MM-DD)
        
    Returns paginated list of trades matching the filters.
    """
    try:
        # Build query filters
        current_user = get_master_user()
        query = {"user_id": str(current_user.id)}
        
        if status:
            query["status"] = status
        if trade_type:
            query["trade_type"] = trade_type
            
        # Date range filtering
        date_query = {}
        if from_date:
            date_query["$gte"] = datetime.strptime(from_date, "%Y-%m-%d")
        if to_date:
            # Include the entire end date
            to_date_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
            date_query["$lt"] = to_date_dt
            
        if date_query:
            query["entry_time"] = date_query
        
        # Get trades with pagination
        trades_collection = Database.get_trades_collection()
        current_user = get_master_user()
        
        # Get total count
        total = await trades_collection.count_documents(query)
        
        # Get paginated trades
        cursor = trades_collection.find(query) \
            .sort("entry_time", -1) \
            .skip(skip) \
            .limit(limit)
        
        trades = []
        async for trade in cursor:
            trade["_id"] = str(trade["_id"])
            trades.append(trade)
        
        return {
            "trades": trades,
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + len(trades)) < total
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TRADE_HISTORY_FETCH_FAILED", "message": str(e)}
        )


@router.get("/trades/{trade_id}", response_model=Dict[str, Any])
async def get_trade_details(
    trade_id: str,
) -> Dict[str, Any]:
    """
    Get details of a specific trade by ID.
    """
    try:
        trades_collection = Database.get_trades_collection()
        current_user = get_master_user()
        trade = await trades_collection.find_one({
            "trade_id": trade_id,
            "user_id": str(current_user.id)
        })
        
        if not trade:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "TRADE_NOT_FOUND", "message": f"Trade {trade_id} not found"}
            )
            
        trade["_id"] = str(trade["_id"])
        return trade
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TRADE_FETCH_FAILED", "message": str(e)}
        )


@router.post("/auto/trade/test", response_model=Dict[str, Any])
async def auto_trade_test(request: AutoTradeRequest) -> Dict[str, Any]:
    """Deterministic auto-trade endpoint for testing target/SL auto-exits without real DHAN orders.

    - Uses fixed intraday candles and a synthetic orderbook.
    - Always creates a simulated BUY model trade with known entry/SL/target.
    - Trades are marked is_simulated=True so the monitor/SL workers will exit them
      but no live orders are sent to DHAN.
    """
    user = get_master_user()

    # Build deterministic candles (60 bars)
    candles: list[dict[str, float]] = []
    base_price = 100.0
    for i in range(60):
        o = base_price + 0.1 * i
        h = o + 0.5
        l = o - 0.5
        c = o + 0.2
        candles.append({"open": o, "high": h, "low": l, "close": c, "volume": 1000 + i})

    # Synthetic orderbook depth with 0.05 tick size
    orderbook: Dict[str, Any] = {
        "best_bid_price": 99.9,
        "best_ask_price": 100.1,
        "bids": [{"price": 99.9 - 0.05 * i, "qty": 100 * (i + 1)} for i in range(5)],
        "asks": [{"price": 100.1 + 0.05 * i, "qty": 100 * (i + 1)} for i in range(5)],
    }

    # Simple deterministic BUY signal around the synthetic candles
    ltp = candles[-1]["close"]
    tick_size = 0.05
    limit_price = ltp - 5 * tick_size
    # Risk: 1.0 point, Reward: 2.0 points for easy visual testing
    sl = limit_price - 1.0
    target = limit_price + 2.0

    signal = "BUY"

    trade_response = await TradeService.execute_model_trade(
        user=user,
        symbol=request.symbol,
        security_id="TEST1333",
        exchange_segment="NSE_EQ",
        quantity=request.quantity,
        prediction=signal,
        limit_price=float(limit_price),
        sl=float(sl),
        target=float(target),
        product_type=request.product_type,
        trade_type=request.trade_type,
        tick_size=tick_size,
        is_simulated=True,
    )

    return {
        "signal": signal,
        "entry": ltp,
        "sl": sl,
        "target": target,
        "limit_price": limit_price,
        "orderbook": orderbook,
        "order_response": trade_response,
    }


@router.get("/trades/stats/summary", response_model=Dict[str, Any])
async def get_trade_stats(
    period: str = "all",  # all, today, week, month, year
) -> Dict[str, Any]:
    """
    Get trading statistics and performance metrics.
    
    Args:
        period: Time period to filter stats (all, today, week, month, year)
        
    Returns statistics including total P&L, win rate, average win/loss, etc.
    """
    try:
        # Calculate date range based on period
        now = datetime.utcnow()
        date_filter = {}
        
        if period != "all":
            if period == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                start_date = now - timedelta(days=now.weekday())
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "month":
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            elif period == "year":
                start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "INVALID_PERIOD", "message": "Invalid period. Use: all, today, week, month, year"}
                )
            
            date_filter["$gte"] = start_date
        
        # Build query
        current_user = get_master_user()
        query = {
            "user_id": str(current_user.id),
            "status": TradeStatus.EXITED
        }
        
        if date_filter:
            query["exit_time"] = date_filter
        
        # Get trades for the period
        trades_collection = Database.get_trades_collection()
        cursor = trades_collection.find(query)
        
        # Calculate statistics
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        total_pnl = 0.0
        total_winning_amount = 0.0
        total_losing_amount = 0.0
        
        async for trade in cursor:
            total_trades += 1
            pnl = trade.get("net_pnl", 0)
            total_pnl += pnl
            
            if pnl > 0:
                winning_trades += 1
                total_winning_amount += pnl
            else:
                losing_trades += 1
                total_losing_amount += abs(pnl)
        
        # Calculate metrics
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        avg_win = (total_winning_amount / winning_trades) if winning_trades > 0 else 0
        avg_loss = (total_losing_amount / losing_trades) if losing_trades > 0 else 0
        profit_factor = (total_winning_amount / total_losing_amount) if total_losing_amount > 0 else float('inf')
        
        return {
            "period": period,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "∞",
            "start_date": start_date.isoformat() if period != "all" else None,
            "end_date": now.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "STATS_FETCH_FAILED", "message": str(e)}
        )

