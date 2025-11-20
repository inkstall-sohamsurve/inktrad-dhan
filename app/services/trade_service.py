"""
Trade execution service for handling trade lifecycle including margin calculation,
order placement, and P&L tracking.
"""
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import uuid
import asyncio
from fastapi import HTTPException, status
from app.models.user import UserInDB
from app.models.trade import TradeEntry, TradeExit, TradeStatus, TradeType
from app.models.dhan_order import DhanOrderRequest, TransactionType, OrderType, Validity
from app.models.order import PlaceOrderRequest, ModifyOrderRequest
from app.services.dhan_service import DhanService
from app.db.database import Database
from app.core.security import decrypt_data
from scripts.nse_security_ids import resolve_security_id
import logging

logger = logging.getLogger(__name__)

class TradeService:
    """Service for handling trade execution and management."""
    
    # Brokerage and charges (example values, should be configured)
    BROKERAGE_RATE = 0.03  # 0.03% of trade value
    STT_CTT = 0.01  # 0.01% of trade value
    GST = 0.18  # 18% of brokerage
    SEBI_CHARGES = 0.0001  # 0.01% of trade value
    STAMP_DUTY = 0.0003  # 0.003% of trade value (varies by state)
    EXCHANGE_TRANSACTION_CHARGE = 0.003  # 0.003% of trade value
    
    # Margin requirements (example values, should be configured based on product type)
    MARGIN_REQUIREMENTS = {
        "MIS": 0.10,  # 10% for intraday
        "NRML": 0.50,  # 50% for delivery
        "CNC": 1.00   # 100% for delivery (CNC)
    }
    
    @staticmethod
    async def calculate_margin_required(entry: TradeEntry) -> float:
        """
        Calculate the margin required for a trade.
        
        Args:
            entry: Trade entry details
            
        Returns:
            float: Margin amount required
        """
        trade_value = entry.quantity * entry.entry_price
        margin_percentage = TradeService.MARGIN_REQUIREMENTS.get(entry.product_type, 1.0)
        return trade_value * margin_percentage
    
    @staticmethod
    async def calculate_charges(trade_value: float) -> Dict[str, float]:
        """
        Calculate all charges for a trade.
        
        Args:
            trade_value: Total value of the trade
            
        Returns:
            Dict containing breakdown of all charges
        """
        brokerage = min(TradeService.BROKERAGE_RATE * trade_value / 100, 20)  # Max Rs. 20 per order
        stt_ctt = TradeService.STT_CTT * trade_value / 100
        gst = brokerage * TradeService.GST
        sebi_charges = TradeService.SEBI_CHARGES * trade_value / 100
        stamp_duty = TradeService.STAMP_DUTY * trade_value / 100
        exchange_charges = TradeService.EXCHANGE_TRANSACTION_CHARGE * trade_value / 100
        
        total_charges = brokerage + stt_ctt + gst + sebi_charges + stamp_duty + exchange_charges
        
        return {
            "brokerage": round(brokerage, 2),
            "stt_ctt": round(stt_ctt, 2),
            "gst": round(gst, 2),
            "sebi_charges": round(sebi_charges, 2),
            "stamp_duty": round(stamp_duty, 2),
            "exchange_charges": round(exchange_charges, 2),
            "total_charges": round(total_charges, 2)
        }
    
    @staticmethod
    async def check_available_margin(user: UserInDB, required_margin: float) -> Tuple[bool, float, str]:
        """
        Check if user has sufficient margin available.
        
        Args:
            user: User placing the trade
            required_margin: Margin required for the trade
            
        Returns:
            Tuple of (has_sufficient_margin, available_amount, message)
        """
        try:
            # Get available funds using our normalized DHAN funds endpoint
            funds = await DhanService.get_funds(user)

            # Available margin is the sum of available balance and utilized amount
            available_balance = float(funds.get("available_balance", 0))
            utilized_amount = float(funds.get("utilized_amount", 0))
            total_available = available_balance + utilized_amount

            if total_available >= required_margin:
                return True, total_available, "Sufficient margin available"
            else:
                additional_needed = required_margin - total_available
                return False, total_available, f"Insufficient funds. Add ₹{additional_needed:.2f} to place this trade."

        except Exception as e:
            logger.error(f"Error checking available margin: {str(e)}")
            return False, 0, f"Error checking margin: {str(e)}"

    @staticmethod
    def apply_trailing_sl(current_price: float, sl_level: float, direction: str) -> float:
        side = direction.upper()
        if side == "BUY":
            if current_price <= sl_level:
                return sl_level
            distance = current_price - sl_level
            new_sl = current_price - distance * 0.5
            if new_sl > sl_level:
                return new_sl
            return sl_level
        if side == "SELL":
            if current_price >= sl_level:
                return sl_level
            distance = sl_level - current_price
            new_sl = current_price + distance * 0.5
            if new_sl < sl_level:
                return new_sl
            return sl_level
        return sl_level
    
    @staticmethod
    async def execute_trade(user: UserInDB, entry: TradeEntry) -> Dict[str, Any]:
        """
        Execute a new trade with proper margin and risk checks.
        
        Args:
            user: User executing the trade
            entry: Trade entry details
            
        Returns:
            Dict containing trade execution result
        """
        # Calculate required margin
        margin_required = await TradeService.calculate_margin_required(entry)
        
        # Check available margin
        has_margin, available, message = await TradeService.check_available_margin(user, margin_required)
        if not has_margin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INSUFFICIENT_MARGIN", "message": message, "required": margin_required, "available": available}
            )
        
        try:
            # Get DHAN client

            # Create DHAN order request
            dhan_order = DhanOrderRequest(
                dhan_client_id=decrypt_data(user.dhan_client_id),
                transaction_type=TransactionType.BUY,
                exchange_segment=entry.exchange_segment,
                product_type=entry.product_type,
                order_type=OrderType.MARKET if entry.entry_price is None else OrderType.LIMIT,
                validity=Validity.DAY if entry.trade_type == TradeType.INTRADAY else Validity.IOC,
                trading_symbol=entry.trading_symbol,
                security_id=entry.security_id,
                quantity=entry.quantity,
                disclosed_quantity=0,
                price=entry.entry_price,
                trigger_price=entry.stop_loss,
                after_market_order=False
            )
            
            # Create a new trade record
            trades_collection = Database.get_trades_collection()
            
            trade_data = {
                "user_id": str(user.id),
                "trade_id": f"TRADE{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "security_id": entry.security_id,
                "trading_symbol": entry.trading_symbol,
                "exchange_segment": entry.exchange_segment,
                "quantity": entry.quantity,
                "entry_price": entry.entry_price,
                "entry_time": datetime.utcnow(),
                "stop_loss": entry.stop_loss,
                "target": entry.target,
                "status": TradeStatus.ENTERED,
                "trade_type": entry.trade_type,
                "product_type": entry.product_type,
                "transaction_type": TransactionType.BUY,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Insert trade record
            result = await trades_collection.insert_one(trade_data)
            trade_data["_id"] = str(result.inserted_id)
            
            # Place the order using direct HTTP client
            import http.client
            import json
            
            # Get decrypted access token
            access_token = decrypt_data(user.dhan_access_token)
            
            conn = http.client.HTTPSConnection("api.dhan.co")

            # Map internal product types (MIS/CNC/NRML) to DHAN API productType
            internal_product_type = entry.product_type
            if internal_product_type == "MIS":
                dhan_product_type = "INTRADAY"
            elif internal_product_type == "NRML":
                dhan_product_type = "MARGIN"
            elif internal_product_type == "CNC":
                dhan_product_type = "CNC"
            else:
                # Fallback to whatever is provided
                dhan_product_type = internal_product_type

            # Convert order request to DHAN API format
            # DHAN requires correlationId to be at most 25 characters.
            correlation_id = uuid.uuid4().hex[:24]
            payload = {
                "dhanClientId": decrypt_data(user.dhan_client_id),
                "correlationId": correlation_id,
                "transactionType": dhan_order.transaction_type.value,
                "exchangeSegment": dhan_order.exchange_segment,
                "productType": dhan_product_type,
                "orderType": dhan_order.order_type.value,
                "validity": dhan_order.validity,
                "tradingSymbol": dhan_order.trading_symbol,
                "securityId": dhan_order.security_id,
                "quantity": dhan_order.quantity,
                "disclosedQuantity": dhan_order.disclosed_quantity or 0,
                "price": dhan_order.price,
                "triggerPrice": dhan_order.trigger_price,
                "afterMarketOrder": False,
                "amoTime": "OPEN"
            }

            headers = {
                'access-token': access_token,
                'client-id': decrypt_data(user.dhan_client_id),
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            conn.request("POST", "/orders", json.dumps(payload), headers)
            res = conn.getresponse()
            order_response = json.loads(res.read().decode("utf-8"))

            if res.status != 200:
                # Surface DHAN's response back to the client so the reason is visible
                error_message = (
                    order_response.get("message")
                    or order_response.get("errorMessage")
                    or order_response.get("error")
                    or order_response.get("remarks")
                    or json.dumps(order_response)
                    or "Failed to place order"
                )
                logger.error(
                    f"DHAN order placement failed: status={res.status}, "
                    f"message={error_message}, response={order_response}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "DHAN_ORDER_FAILED",
                        "message": error_message,
                        "status_code": res.status,
                        "response": order_response,
                    },
                )
            
            # Update trade with order ID
            await trades_collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"dhan_order_id": order_response.get("orderId")}}
            )
            
            return {
                "status": "SUCCESS",
                "trade_id": trade_data["trade_id"],
                "order_id": order_response.get("orderId"),
                "message": "Trade executed successfully",
                "details": {
                    "security_id": entry.security_id,
                    "quantity": entry.quantity,
                    "entry_price": entry.entry_price,
                    "margin_required": margin_required,
                    "available_margin": available
                }
            }

        except HTTPException:
            # Propagate HTTP errors (e.g. DHAN rejections) without wrapping
            raise
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "TRADE_EXECUTION_FAILED", "message": str(e)}
            )

    @staticmethod
    async def execute_model_trade(
        user: UserInDB,
        symbol: str,
        security_id: str,
        exchange_segment: str,
        quantity: int,
        prediction: str,
        limit_price: float,
        sl: float,
        target: float,
        product_type: str = "MIS",
        trade_type: TradeType = TradeType.INTRADAY,
        tick_size: Optional[float] = None,
        is_simulated: bool = False,
    ) -> Dict[str, Any]:
        side = prediction.upper()
        if side not in ("BUY", "SELL"):
            return {
                "status": "NO_TRADE",
                "message": "Model signalled HOLD or unknown direction",
                "signal": prediction,
            }

        entry = TradeEntry(
            security_id=security_id,
            trading_symbol=symbol,
            exchange_segment=exchange_segment,
            quantity=quantity,
            entry_price=limit_price,
            stop_loss=sl,
            target=target,
            trade_type=trade_type,
            product_type=product_type,
        )

        margin_required = await TradeService.calculate_margin_required(entry)
        has_margin, available, message = await TradeService.check_available_margin(user, margin_required)
        if not has_margin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INSUFFICIENT_MARGIN",
                    "message": message,
                    "required": margin_required,
                    "available": available,
                },
            )

        adjusted_sl = TradeService.apply_trailing_sl(limit_price, sl, side)
        entry.stop_loss = adjusted_sl

        try:
            transaction_type = TransactionType.BUY if side == "BUY" else TransactionType.SELL

            trades_collection = Database.get_trades_collection()

            trade_data = {
                "user_id": str(user.id),
                "trade_id": f"TRADE{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "security_id": entry.security_id,
                "trading_symbol": entry.trading_symbol,
                "exchange_segment": entry.exchange_segment,
                "quantity": entry.quantity,
                "entry_price": entry.entry_price,
                "entry_time": datetime.utcnow(),
                "stop_loss": entry.stop_loss,
                "target": entry.target,
                "status": TradeStatus.ENTERED,
                "trade_type": entry.trade_type,
                "product_type": entry.product_type,
                "transaction_type": transaction_type,
                "tick_size": tick_size,
                "is_simulated": is_simulated,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            result = await trades_collection.insert_one(trade_data)
            trade_data["_id"] = str(result.inserted_id)
            if is_simulated:
                logger.info("📊 Created simulated model trade %s (no DHAN order)", trade_data["trade_id"])
                return {
                    "status": "SIMULATED",
                    "trade_id": trade_data["trade_id"],
                    "order_id": None,
                    "message": "Simulated model trade created (no DHAN order placed)",
                    "details": {
                        "security_id": entry.security_id,
                        "quantity": entry.quantity,
                        "entry_price": entry.entry_price,
                        "stop_loss": entry.stop_loss,
                        "target": entry.target,
                        "tick_size": tick_size,
                        "margin_required": margin_required,
                        "available_margin": available,
                        "signal": prediction,
                    },
                }

            import http.client
            import json

            access_token = decrypt_data(user.dhan_access_token)

            conn = http.client.HTTPSConnection("api.dhan.co")

            internal_product_type = entry.product_type
            if internal_product_type == "MIS":
                dhan_product_type = "INTRADAY"
            elif internal_product_type == "NRML":
                dhan_product_type = "MARGIN"
            elif internal_product_type == "CNC":
                dhan_product_type = "CNC"
            else:
                dhan_product_type = internal_product_type

            dhan_order = DhanOrderRequest(
                dhan_client_id=decrypt_data(user.dhan_client_id),
                transaction_type=transaction_type,
                exchange_segment=entry.exchange_segment,
                product_type=entry.product_type,
                order_type=OrderType.LIMIT,
                validity=Validity.DAY if entry.trade_type == TradeType.INTRADAY else Validity.IOC,
                trading_symbol=entry.trading_symbol,
                security_id=entry.security_id,
                quantity=entry.quantity,
                disclosed_quantity=0,
                price=entry.entry_price,
                trigger_price=entry.stop_loss,
                after_market_order=False,
            )

            correlation_id = uuid.uuid4().hex[:24]
            payload = {
                "dhanClientId": decrypt_data(user.dhan_client_id),
                "correlationId": correlation_id,
                "transactionType": dhan_order.transaction_type.value,
                "exchangeSegment": dhan_order.exchange_segment,
                "productType": dhan_product_type,
                "orderType": dhan_order.order_type.value,
                "validity": dhan_order.validity,
                "tradingSymbol": dhan_order.trading_symbol,
                "securityId": dhan_order.security_id,
                "quantity": dhan_order.quantity,
                "disclosedQuantity": dhan_order.disclosed_quantity or 0,
                "price": dhan_order.price,
                "triggerPrice": dhan_order.trigger_price,
                "afterMarketOrder": False,
                "amoTime": "OPEN",
            }

            headers = {
                "access-token": access_token,
                "client-id": decrypt_data(user.dhan_client_id),
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            conn.request("POST", "/orders", json.dumps(payload), headers)
            res = conn.getresponse()
            order_response = json.loads(res.read().decode("utf-8"))

            if res.status != 200:
                error_message = (
                    order_response.get("message")
                    or order_response.get("errorMessage")
                    or order_response.get("error")
                    or order_response.get("remarks")
                    or json.dumps(order_response)
                    or "Failed to place order"
                )
                logger.error(
                    f"DHAN model order placement failed: status={res.status}, "
                    f"message={error_message}, response={order_response}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "DHAN_ORDER_FAILED",
                        "message": error_message,
                        "status_code": res.status,
                        "response": order_response,
                    },
                )

            await trades_collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {"dhan_order_id": order_response.get("orderId")}},
            )

            return {
                "status": "SUCCESS",
                "trade_id": trade_data["trade_id"],
                "order_id": order_response.get("orderId"),
                "message": "Model trade executed successfully",
                "details": {
                    "security_id": entry.security_id,
                    "quantity": entry.quantity,
                    "entry_price": entry.entry_price,
                    "stop_loss": entry.stop_loss,
                    "target": entry.target,
                    "tick_size": tick_size,
                    "margin_required": margin_required,
                    "available_margin": available,
                    "signal": prediction,
                },
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error executing model trade: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "MODEL_TRADE_EXECUTION_FAILED", "message": str(e)},
            )

    @staticmethod
    async def _get_current_price_for_trade(user: UserInDB, trade: Dict[str, Any]) -> Optional[float]:
        security_id = str(trade.get("security_id") or "")
        exchange_segment = trade.get("exchange_segment")
        symbol = trade.get("trading_symbol")
        if not security_id or not exchange_segment or not symbol:
            return None
        info = resolve_security_id(symbol)
        instrument_type: Optional[str] = None
        if info:
            instrument_type = info.get("instrument_type")
        if not instrument_type:
            if exchange_segment == "NSE_EQ":
                instrument_type = "EQUITY"
            else:
                instrument_type = "EQUITY"
        now = datetime.now()
        from_dt = now - timedelta(minutes=5)
        from_date = from_dt.strftime("%Y-%m-%d %H:%M:%S")
        to_date = now.strftime("%Y-%m-%d %H:%M:%S")
        try:
            intraday = await DhanService.get_intraday_data(
                user,
                security_id=security_id,
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                from_date=from_date,
                to_date=to_date,
            )
        except HTTPException:
            return None
        closes = intraday.get("close") or []
        if not closes:
            return None
        try:
            return float(closes[-1])
        except Exception:
            return None

    @staticmethod
    async def run_trailing_sl_worker(user: UserInDB, interval_seconds: int = 1) -> None:
        try:
            trades_collection = Database.get_trades_collection()
        except RuntimeError:
            return
        user_id = str(user.id)
        while True:
            try:
                cursor = trades_collection.find(
                    {
                        "user_id": user_id,
                        "status": TradeStatus.ENTERED,
                    }
                )
                async for trade in cursor:
                    order_id = trade.get("dhan_order_id")
                    sl = trade.get("stop_loss")
                    if not order_id or sl is None:
                        continue
                    raw_trade_type = trade.get("trade_type")
                    if isinstance(raw_trade_type, TradeType):
                        trade_type_value = raw_trade_type.value
                    else:
                        trade_type_value = str(raw_trade_type or "")
                    if trade_type_value != TradeType.INTRADAY.value:
                        continue
                    raw_side = trade.get("transaction_type")
                    if isinstance(raw_side, TransactionType):
                        side = raw_side.value.upper()
                    else:
                        side = str(raw_side or "").upper()
                    if side not in ("BUY", "SELL"):
                        continue
                    try:
                        current_price = await TradeService._get_current_price_for_trade(user, trade)
                    except Exception:
                        continue
                    if current_price is None:
                        continue
                    try:
                        sl_value = float(sl)
                    except Exception:
                        continue
                    # If price has already crossed the SL in the adverse direction, exit immediately.
                    try:
                        if side == "BUY" and current_price <= sl_value:
                            logger.info("🛑 STOP-LOSS HIT (trailing) for trade %s at %.2f (side=%s, sl=%.2f)", trade.get("trade_id"), current_price, side, sl_value)
                            from app.models.trade import TradeExit  # local import to avoid circular
                            await TradeService.exit_trade(
                                user,
                                trade_id=str(trade.get("trade_id")),
                                exit_data=TradeExit(exit_price=float(current_price), exit_reason="STOP-LOSS HIT"),
                            )
                            continue
                        if side == "SELL" and current_price >= sl_value:
                            logger.info("🛑 STOP-LOSS HIT (trailing) for trade %s at %.2f (side=%s, sl=%.2f)", trade.get("trade_id"), current_price, side, sl_value)
                            from app.models.trade import TradeExit  # local import to avoid circular
                            await TradeService.exit_trade(
                                user,
                                trade_id=str(trade.get("trade_id")),
                                exit_data=TradeExit(exit_price=float(current_price), exit_reason="STOP-LOSS HIT"),
                            )
                            continue
                    except HTTPException:
                        continue
                    except Exception:
                        continue
                    new_sl = TradeService.apply_trailing_sl(float(current_price), sl_value, side)
                    if new_sl == sl_value:
                        continue
                    modify_request = ModifyOrderRequest(order_id=order_id, trigger_price=new_sl)
                    try:
                        await DhanService.modify_order(user, modify_request)
                    except HTTPException:
                        continue
                    except Exception:
                        continue
                    await trades_collection.update_one(
                        {"_id": trade["_id"]},
                        {"$set": {"stop_loss": new_sl, "updated_at": datetime.utcnow()}},
                    )
            except Exception as e:
                logger.error(f"Error in trailing SL worker loop: {str(e)}")
            await asyncio.sleep(interval_seconds)

    @staticmethod
    async def run_trade_monitor_worker(user: UserInDB, interval_seconds: int = 1) -> None:
        """Monitor active trades and exit immediately when SL or target is hit."""
        try:
            trades_collection = Database.get_trades_collection()
        except RuntimeError:
            return
        user_id = str(user.id)
        from app.models.trade import TradeExit  # local import to avoid circular

        while True:
            try:
                cursor = trades_collection.find(
                    {
                        "user_id": user_id,
                        "status": TradeStatus.ENTERED,
                    }
                )
                async for trade in cursor:
                    trade_id = str(trade.get("trade_id") or "")
                    if not trade_id:
                        continue
                    sl = trade.get("stop_loss")
                    target = trade.get("target")
                    raw_side = trade.get("transaction_type")
                    if isinstance(raw_side, TransactionType):
                        side = raw_side.value.upper()
                    else:
                        side = str(raw_side or "").upper()
                    if side not in ("BUY", "SELL"):
                        continue
                    if sl is None and target is None:
                        continue
                    try:
                        current_price = await TradeService._get_current_price_for_trade(user, trade)
                    except Exception:
                        continue
                    if current_price is None:
                        continue
                    hit_reason: Optional[str] = None
                    try:
                        sl_value = float(sl) if sl is not None else None
                    except Exception:
                        sl_value = None
                    try:
                        target_value = float(target) if target is not None else None
                    except Exception:
                        target_value = None

                    if side == "BUY":
                        if target_value is not None and current_price >= target_value:
                            hit_reason = "TARGET HIT"
                        elif sl_value is not None and current_price <= sl_value:
                            hit_reason = "STOP-LOSS HIT"
                    elif side == "SELL":
                        if target_value is not None and current_price <= target_value:
                            hit_reason = "TARGET HIT"
                        elif sl_value is not None and current_price >= sl_value:
                            hit_reason = "STOP-LOSS HIT"

                    if not hit_reason:
                        continue

                    if "TARGET" in hit_reason:
                        logger.info(
                            "🎯 TARGET HIT for trade %s at %.2f (side=%s, target=%s, sl=%s)",
                            trade_id,
                            current_price,
                            side,
                            target_value,
                            sl_value,
                        )
                    else:
                        logger.info(
                            "🛑 STOP-LOSS HIT for trade %s at %.2f (side=%s, target=%s, sl=%s)",
                            trade_id,
                            current_price,
                            side,
                            target_value,
                            sl_value,
                        )

                    try:
                        await TradeService.exit_trade(
                            user,
                            trade_id=trade_id,
                            exit_data=TradeExit(exit_price=float(current_price), exit_reason=hit_reason),
                        )
                    except HTTPException as e:
                        detail = getattr(e, "detail", {})
                        if isinstance(detail, dict) and detail.get("error") in {"TRADE_ALREADY_EXITED", "TRADE_NOT_FOUND"}:
                            continue
                        logger.error("Error exiting trade %s in monitor worker: %s", trade_id, e)
                    except Exception as e:
                        logger.error("Unexpected error exiting trade %s in monitor worker: %s", trade_id, e)
            except Exception as e:
                logger.error("Error in trade monitor worker loop: %s", str(e))
            await asyncio.sleep(interval_seconds)

    @staticmethod
    async def exit_trade(user: UserInDB, trade_id: str, exit_data: TradeExit) -> Dict[str, Any]:
        """
        Exit an existing trade.
        
        Args:
            user: User exiting the trade
            trade_id: ID of the trade to exit
            exit_data: Exit details
            
        Returns:
            Dict containing exit trade result
        """
        trades_collection = Database.get_trades_collection()
        
        # Get the trade
        trade = await trades_collection.find_one({"trade_id": trade_id, "user_id": str(user.id)})
        if not trade:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "TRADE_NOT_FOUND", "message": f"Trade {trade_id} not found"}
            )
        
        if trade["status"] == TradeStatus.EXITED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "TRADE_ALREADY_EXITED", "message": f"Trade {trade_id} is already exited"}
            )
        
        is_simulated = bool(trade.get("is_simulated", False))
        raw_side = trade.get("transaction_type")
        if isinstance(raw_side, TransactionType):
            side = raw_side.value.upper()
        else:
            side = str(raw_side or "").upper()
        exit_side = TransactionType.SELL if side != "SELL" else TransactionType.BUY

        # Calculate P&L and charges using the provided exit price
        try:
            exit_price_value = float(exit_data.exit_price)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_EXIT_PRICE", "message": "Exit price must be a valid number"},
            )

        entry_value = trade["quantity"] * trade["entry_price"]
        exit_value = trade["quantity"] * exit_price_value
        pnl = exit_value - entry_value if side == "BUY" else entry_value - exit_value
        pnl_percentage = (pnl / entry_value) * 100 if entry_value != 0 else 0.0

        # Calculate charges for both entry and exit
        entry_charges = await TradeService.calculate_charges(entry_value)
        exit_charges = await TradeService.calculate_charges(exit_value)
        total_charges = entry_charges["total_charges"] + exit_charges["total_charges"]
        net_pnl = pnl - total_charges

        update_data = {
            "exit_price": exit_price_value,
            "exit_time": datetime.utcnow(),
            "status": TradeStatus.EXITED,
            "exit_reason": exit_data.exit_reason,
            "pnl": round(pnl, 2),
            "pnl_percentage": round(pnl_percentage, 2),
            "brokerage": round(entry_charges["brokerage"] + exit_charges["brokerage"], 2),
            "taxes": round(
                entry_charges["total_charges"]
                + exit_charges["total_charges"]
                - (entry_charges["brokerage"] + exit_charges["brokerage"]),
                2,
            ),
            "net_pnl": round(net_pnl, 2),
            "updated_at": datetime.utcnow(),
        }

        # For simulated trades, just update DB and skip DHAN
        if is_simulated:
            await trades_collection.update_one({"trade_id": trade_id}, {"$set": update_data})
            logger.info("✅ Simulated trade %s exited locally (no DHAN order)", trade_id)
            return {
                "status": "SUCCESS",
                "trade_id": trade_id,
                "order_id": None,
                "message": "Simulated trade exited successfully",
                "pnl": pnl,
                "pnl_percentage": pnl_percentage,
                "charges": total_charges,
                "net_pnl": net_pnl,
            }

        # Real DHAN exit: always market order with price 0
        try:
            import http.client
            import json

            access_token = decrypt_data(user.dhan_access_token)
            conn = http.client.HTTPSConnection("api.dhan.co")

            correlation_id = uuid.uuid4().hex[:24]
            internal_product_type = trade["product_type"]
            if internal_product_type == "MIS":
                dhan_product_type = "INTRADAY"
            elif internal_product_type == "NRML":
                dhan_product_type = "MARGIN"
            elif internal_product_type == "CNC":
                dhan_product_type = "CNC"
            else:
                dhan_product_type = internal_product_type

            exit_order = DhanOrderRequest(
                dhan_client_id=decrypt_data(user.dhan_client_id),
                transaction_type=exit_side,
                exchange_segment=trade["exchange_segment"],
                product_type=trade["product_type"],
                order_type=OrderType.MARKET,
                validity=Validity.DAY if trade["trade_type"] == TradeType.INTRADAY else Validity.IOC,
                trading_symbol=trade["trading_symbol"],
                security_id=trade["security_id"],
                quantity=trade["quantity"],
                disclosed_quantity=0,
                price=0.0,
                after_market_order=False,
            )

            payload = {
                "dhanClientId": decrypt_data(user.dhan_client_id),
                "correlationId": correlation_id,
                "transactionType": exit_order.transaction_type.value,
                "exchangeSegment": exit_order.exchange_segment,
                "productType": dhan_product_type,
                "orderType": exit_order.order_type.value,
                "validity": exit_order.validity,
                "tradingSymbol": exit_order.trading_symbol,
                "securityId": exit_order.security_id,
                "quantity": exit_order.quantity,
                "disclosedQuantity": exit_order.disclosed_quantity or 0,
                "price": 0,
                "triggerPrice": 0,
                "afterMarketOrder": False,
                "amoTime": "OPEN",
            }

            headers = {
                "access-token": access_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            conn.request("POST", "/orders", json.dumps(payload), headers)
            res = conn.getresponse()
            order_response = json.loads(res.read().decode("utf-8"))

            if res.status != 200:
                error_message = (
                    order_response.get("message")
                    or order_response.get("errorMessage")
                    or order_response.get("error")
                    or order_response.get("remarks")
                    or json.dumps(order_response)
                    or "Failed to place exit order"
                )
                logger.error(
                    f"DHAN exit order failed: status={res.status}, "
                    f"message={error_message}, response={order_response}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "DHAN_EXIT_ORDER_FAILED",
                        "message": error_message,
                        "status_code": res.status,
                        "response": order_response,
                    },
                )

            await trades_collection.update_one({"trade_id": trade_id}, {"$set": update_data})

            return {
                "status": "SUCCESS",
                "trade_id": trade_id,
                "order_id": order_response.get("orderId"),
                "message": "Trade exited successfully",
                "pnl": pnl,
                "pnl_percentage": pnl_percentage,
                "charges": total_charges,
                "net_pnl": net_pnl,
            }

        except HTTPException:
            # Propagate DHAN HTTP errors without wrapping
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "TRADE_EXIT_FAILED", "message": str(e)},
            )

    @staticmethod
    async def get_trade_history(user: UserInDB, limit: int = 10, skip: int = 0) -> Dict[str, Any]:
        """
        Get user's trade history.
        
        Args:
            user: User whose trades to fetch
            limit: Number of trades to return
            skip: Number of trades to skip
            
        Returns:
            Dict containing list of trades and pagination info
        """
        try:
            trades_collection = Database.get_trades_collection()
            
            # Get total count
            total = await trades_collection.count_documents({"user_id": str(user.id)})
            
            # Get paginated trades
            cursor = trades_collection.find({"user_id": str(user.id)}) \
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
            logger.error(f"Error fetching trade history: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "TRADE_HISTORY_FETCH_FAILED", "message": str(e)}
            )

