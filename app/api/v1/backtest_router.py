"""
Backtest API router for running backtests with ML models.
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.model_service import ModelService
from app.services.dhan_service import DhanService
from app.api.v1.trade_router import get_master_user

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v2/backtest", tags=["Backtest"])


class BacktestRequest(BaseModel):
    """Request model for running a backtest."""
    symbol: str = Field(..., description="Stock symbol to backtest")
    model_id: str = Field(..., description="Model ID to use for predictions")
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(100000, description="Initial capital for backtest")
    slippage: float = Field(0.001, description="Slippage percentage")
    max_trades: int = Field(100, description="Maximum number of trades")


class ModelInfo(BaseModel):
    """Model information."""
    id: str
    name: str
    description: str
    type: str
    features: List[str]


@router.get("/models", response_model=List[ModelInfo])
async def get_available_models() -> List[ModelInfo]:
    """
    Get list of available ML models for backtesting.
    
    Returns:
        List of available models with their metadata
    """
    try:
        model_service = ModelService.get_instance()
        
        # Return information about the LSTM model
        models = [
            {
                "id": "lstm_pytorch",
                "name": "LSTM PyTorch Model",
                "description": "Stacked LSTM model for stock price prediction with 3 layers (64, 32, 16 units)",
                "type": "Deep Learning",
                "features": model_service.prediction_features if hasattr(model_service, 'prediction_features') else [
                    "open", "high", "low", "close", "volume", "volatility_index", "decay"
                ]
            }
        ]
        
        return models
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch models: {str(e)}"
        )


@router.post("/run", response_model=Dict[str, Any])
async def run_backtest(request: BacktestRequest) -> Dict[str, Any]:
    """
    Run a backtest using the specified model and symbol.
    
    Args:
        request: Backtest configuration
        
    Returns:
        Backtest results including trades, metrics, and performance data
    """
    try:
        model_service = ModelService.get_instance()
        
        # Get master user for DHAN API access
        from app.api.v1.trade_router import get_master_user
        master_user = get_master_user()
        dhan_service = DhanService()
        
        # Validate model ID
        if request.model_id != "lstm_pytorch":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model ID: {request.model_id}"
            )
        
        # Set date range - use longer period to ensure enough data
        # Account for weekends and holidays (365 days ≈ 250 trading days)
        end_date = datetime.now()
        # Request 2 years of data to ensure we get at least 60 trading days
        start_date = end_date - timedelta(days=730)
        
        if request.start_date:
            try:
                start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
        
        if request.end_date:
            try:
                end_date = datetime.strptime(request.end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        
        # Resolve security ID
        security_info = model_service.resolve_security(request.symbol)
        if not security_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Symbol not found: {request.symbol}"
            )
        
        security_id = security_info.get("security_id")
        
        # Fetch historical data
        from_date_str = start_date.strftime("%Y-%m-%d")
        to_date_str = end_date.strftime("%Y-%m-%d")
        logger.info(f"Fetching historical data for {request.symbol} ({security_id}) from {from_date_str} to {to_date_str}")
        
        historical_data = await dhan_service.get_historical_data(
            user=master_user,
            security_id=str(security_id),
            exchange_segment="NSE_EQ",
            instrument_type="EQUITY",
            from_date=from_date_str,
            to_date=to_date_str
        )
        
        logger.info(f"📦 DHAN API raw response type: {type(historical_data)}")
        logger.info(f"📦 DHAN API response keys: {historical_data.keys() if isinstance(historical_data, dict) else 'Not a dict'}")
        
        if not historical_data or "data" not in historical_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No historical data found for {request.symbol}"
            )
        
        # DHAN API might return data in different formats
        data = historical_data["data"]
        logger.info(f"📊 Data type: {type(data)}")
        
        # Check if data is a dict with arrays (OHLCV format)
        if isinstance(data, dict):
            logger.info(f"📊 Data is dict with keys: {data.keys()}")
            # Convert dict format to list of candles
            if all(k in data for k in ['open', 'high', 'low', 'close']):
                logger.info(f"📊 Converting OHLCV dict to candle list")
                length = len(data.get('open', []))
                logger.info(f"📊 OHLCV arrays length: {length}")
                candles = []
                for i in range(length):
                    candles.append({
                        'open': data['open'][i] if i < len(data.get('open', [])) else 0,
                        'high': data['high'][i] if i < len(data.get('high', [])) else 0,
                        'low': data['low'][i] if i < len(data.get('low', [])) else 0,
                        'close': data['close'][i] if i < len(data.get('close', [])) else 0,
                        'volume': data.get('volume', [])[i] if i < len(data.get('volume', [])) else 0,
                        'timestamp': data.get('timestamp', [])[i] if i < len(data.get('timestamp', [])) else i
                    })
                logger.info(f"✅ Converted to {len(candles)} candles")
            else:
                candles = []
        elif isinstance(data, list):
            logger.info(f"📊 Data is already a list with {len(data)} items")
            candles = data
        else:
            logger.error(f"❌ Unknown data format: {type(data)}")
            candles = []
        
        logger.info(f"🎯 Final candle count: {len(candles) if candles else 0} for {request.symbol}")
        
        # Check if we have enough data
        if not candles or len(candles) < model_service.lookback:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"DHAN API returned insufficient data for {request.symbol}. Need at least {model_service.lookback} candles, got {len(candles) if candles else 0}. DHAN API may have limited historical data access for this stock."
            )
        
        # Run backtest simulation
        trades = []
        position = None
        capital = request.initial_capital
        equity_curve = [capital]
        
        # Mock orderbook for price calculation
        def create_mock_orderbook(candle):
            price = float(candle.get("close", candle.get("ltp", 0)))
            return {
                "best_bid_price": price * 0.999,
                "best_ask_price": price * 1.001,
                "bids": [{"price": price * 0.999}, {"price": price * 0.998}],
                "asks": [{"price": price * 1.001}, {"price": price * 1.002}]
            }
        
        for i in range(model_service.lookback, len(candles)):
            # Get candle window for prediction
            window = candles[max(0, i - model_service.lookback):i]
            current_candle = candles[i]
            
            # Get model prediction
            try:
                orderbook = create_mock_orderbook(current_candle)
                prediction = model_service.predict(window, orderbook, symbol=request.symbol)
                signal = prediction.get("signal", "HOLD")
                ltp = prediction.get("ltp", float(current_candle.get("close", 0)))
                
            except Exception as e:
                logger.error(f"Prediction error at index {i}: {e}")
                continue
            
            # Execute trades based on signal
            if signal == "BUY" and position is None:
                # Open long position
                entry_price = ltp * (1 + request.slippage)
                quantity = int(capital / entry_price)
                
                if quantity > 0:
                    position = {
                        "type": "LONG",
                        "entry_price": entry_price,
                        "entry_date": current_candle.get("timestamp", i),
                        "quantity": quantity,
                        "entry_index": i
                    }
                    capital -= entry_price * quantity
                    
            elif signal == "SELL" and position is not None:
                # Close long position
                exit_price = ltp * (1 - request.slippage)
                pnl = (exit_price - position["entry_price"]) * position["quantity"]
                
                trades.append({
                    **position,
                    "exit_price": exit_price,
                    "exit_date": current_candle.get("timestamp", i),
                    "pnl": pnl,
                    "return_pct": (pnl / (position["entry_price"] * position["quantity"])) * 100,
                    "holding_period": i - position["entry_index"]
                })
                
                capital += exit_price * position["quantity"]
                position = None
                
                if len(trades) >= request.max_trades:
                    break
            
            # Update equity
            current_equity = capital
            if position:
                current_equity += ltp * position["quantity"]
            equity_curve.append(current_equity)
        
        # Close any open position at the end
        if position:
            last_candle = candles[-1]
            exit_price = float(last_candle.get("close", 0)) * (1 - request.slippage)
            pnl = (exit_price - position["entry_price"]) * position["quantity"]
            
            trades.append({
                **position,
                "exit_price": exit_price,
                "exit_date": last_candle.get("timestamp", len(candles) - 1),
                "pnl": pnl,
                "return_pct": (pnl / (position["entry_price"] * position["quantity"])) * 100,
                "holding_period": len(candles) - 1 - position["entry_index"]
            })
            
            capital += exit_price * position["quantity"]
        
        # Calculate metrics
        if not trades:
            return {
                "status": "completed",
                "symbol": request.symbol,
                "model_id": request.model_id,
                "total_trades": 0,
                "message": "No trades generated during backtest period"
            }
        
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        total_pnl = sum(t["pnl"] for t in trades)
        
        win_rate = (len(wins) / len(trades)) * 100 if trades else 0
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
        
        # Calculate Sharpe ratio
        returns = [t["return_pct"] for t in trades]
        avg_return = sum(returns) / len(returns) if returns else 0
        std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5 if len(returns) > 1 else 0
        sharpe = (avg_return / std_return) * (252 ** 0.5) if std_return != 0 else 0
        
        # Calculate max drawdown
        peak = request.initial_capital
        max_drawdown = 0
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = ((peak - equity) / peak) * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        final_equity = capital
        total_return = ((final_equity - request.initial_capital) / request.initial_capital) * 100
        
        return {
            "status": "completed",
            "symbol": request.symbol,
            "model_id": request.model_id,
            "model_name": "LSTM PyTorch Model",
            "period": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d"),
                "days": (end_date - start_date).days
            },
            "metrics": {
                "total_trades": len(trades),
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "profit_factor": round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0,
                "sharpe_ratio": round(sharpe, 2),
                "max_drawdown": round(max_drawdown, 2),
                "initial_capital": request.initial_capital,
                "final_equity": round(final_equity, 2),
                "total_return_pct": round(total_return, 2)
            },
            "trades": trades[:50],  # Return first 50 trades to avoid large response
            "equity_curve": equity_curve[::10]  # Sample every 10th point
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {str(e)}"
        )


@router.get("/model/{model_id}/info", response_model=Dict[str, Any])
async def get_model_info(model_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific model.
    
    Args:
        model_id: Model identifier
        
    Returns:
        Detailed model information including architecture and parameters
    """
    try:
        if model_id != "lstm_pytorch":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found: {model_id}"
            )
        
        model_service = ModelService.get_instance()
        
        return {
            "id": "lstm_pytorch",
            "name": "LSTM PyTorch Model",
            "type": "Deep Learning",
            "framework": "PyTorch",
            "architecture": {
                "type": "Stacked LSTM",
                "layers": [
                    {"type": "LSTM", "units": 64, "dropout": 0.2},
                    {"type": "LSTM", "units": 32, "dropout": 0.2},
                    {"type": "LSTM", "units": 16, "dropout": 0.0},
                    {"type": "Dense", "units": "output_size"}
                ]
            },
            "parameters": {
                "lookback": model_service.lookback,
                "prediction_features": model_service.prediction_features,
                "device": str(model_service.device)
            },
            "signals": {
                "BUY": "Model predicts price increase > 0.05%",
                "SELL": "Model predicts price decrease > 0.05%",
                "HOLD": "Model predicts price change within ±0.05%"
            },
            "description": "A stacked LSTM neural network trained on historical stock data. Uses 60-day lookback window with features including OHLCV, volatility index, and temporal decay."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching model info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch model info: {str(e)}"
        )
