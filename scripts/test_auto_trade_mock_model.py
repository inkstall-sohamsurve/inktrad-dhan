"""Standalone test script for /api/v1/auto/trade using mocked dependencies.

This script calls the FastAPI route handler function for /api/v1/auto/trade
with fully mocked model, intraday data, orderbook depth, and trade execution,
so you can validate the end-to-end logic without hitting real DHAN APIs or
placing live orders.

Usage (from project root):

    python scripts/test_auto_trade_mock_model.py

"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List
from unittest.mock import patch

# Ensure the project root is on sys.path when running as a script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.api.v1.trade_router import AutoTradeRequest, auto_trade
from app.services import model_service, dhan_service, trade_service
from app.api.v1 import trade_router


class MockModelService:
    """Mock implementation of ModelService for deterministic behavior."""

    def resolve_security(self, symbol: str) -> Dict[str, Any]:
        # Return a fixed, valid security mapping
        return {
            "security_id": "1333",        # HDFC Bank, for example
            "exchange_segment": "NSE_EQ",
            "instrument_type": "EQUITY",
        }

    def predict(self, candles: List[Any], orderbook: Dict[str, Any]) -> Dict[str, Any]:
        # Deterministic BUY signal with fixed prices
        return {
            "signal": "BUY",
            "limit_price": 100.0,
            "stoploss": 98.0,
            "target": 104.0,
            "ltp": 99.5,
            "best_bid_price": orderbook.get("best_bid_price", 99.9),
            "best_ask_price": orderbook.get("best_ask_price", 100.1),
        }


async def _run_auto_trade_test() -> None:
    # Build mock intraday data with exactly 60 candles
    candles_count = 60
    mock_intraday: Dict[str, List[float]] = {
        "open": [100.0 + i * 0.1 for i in range(candles_count)],
        "high": [100.5 + i * 0.1 for i in range(candles_count)],
        "low": [99.5 + i * 0.1 for i in range(candles_count)],
        "close": [100.2 + i * 0.1 for i in range(candles_count)],
        "volume": [1000 + i for i in range(candles_count)],
    }

    mock_orderbook: Dict[str, Any] = {
        "best_bid_price": 99.9,
        "best_ask_price": 100.1,
        "bids": [
            {"price": 99.9 - 0.05 * i, "qty": 100 * (i + 1)} for i in range(5)
        ],
        "asks": [
            {"price": 100.1 + 0.05 * i, "qty": 100 * (i + 1)} for i in range(5)
        ],
    }

    async def mock_get_intraday_data(
        user: Any,
        security_id: str,
        exchange_segment: str,
        instrument_type: str,
        from_date: str,
        to_date: str,
    ) -> Dict[str, Any]:
        # Ignore parameters and return fixed intraday data
        return mock_intraday

    async def mock_execute_model_trade(
        user: Any,
        symbol: str,
        security_id: str,
        exchange_segment: str,
        quantity: int,
        prediction: str,
        limit_price: float,
        sl: float,
        target: float,
        product_type: str,
        trade_type: Any,
    ) -> Dict[str, Any]:
        # Simulate a successful trade execution without touching DHAN
        return {
            "status": "SUCCESS",
            "trade_id": "MOCK_TRADE_1",
            "order_id": "MOCK_ORDER_1",
            "message": "Mock trade executed successfully",
            "details": {
                "security_id": security_id,
                "quantity": quantity,
                "entry_price": limit_price,
                "stop_loss": sl,
                "target": target,
                "margin_required": 1234.56,
                "available_margin": 999999.0,
                "signal": prediction,
            },
        }

    async def mock_fetch_orderbook_depth(security_id: str, exchange_segment: str) -> Dict[str, Any]:
        # Ignore parameters and return fixed orderbook depth
        return mock_orderbook

    # Apply patches so the /auto/trade handler uses our mocks
    with patch.object(
        model_service.ModelService,
        "get_instance",
        return_value=MockModelService(),
    ), patch.object(
        dhan_service.DhanService,
        "get_intraday_data",
        side_effect=mock_get_intraday_data,
    ), patch.object(
        trade_service.TradeService,
        "execute_model_trade",
        side_effect=mock_execute_model_trade,
    ), patch.object(
        trade_router,
        "_fetch_orderbook_depth",
        side_effect=mock_fetch_orderbook_depth,
    ):

        request = AutoTradeRequest(
            symbol="HDFCBANK",
            quantity=1,
            product_type="MIS",
            # trade_type left as default (INTRADAY)
        )

        response = await auto_trade(request)

        print("=== /api/v1/auto/trade response (mocked) ===")
        print(json.dumps(response, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_run_auto_trade_test())
