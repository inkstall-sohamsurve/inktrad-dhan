"""
Trade execution service for handling trade lifecycle including margin calculation,
order placement, and P&L tracking.
"""
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import uuid
from fastapi import HTTPException, status
from app.models.user import UserInDB
from app.models.trade import TradeEntry, TradeExit, TradeStatus, TradeType
from app.models.dhan_order import DhanOrderRequest, TransactionType, OrderType, Validity
from app.models.order import PlaceOrderRequest
from app.services.dhan_service import DhanService
from app.db.database import Database
from app.core.security import decrypt_data
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
        
        # Prepare exit order
        exit_order = DhanOrderRequest(
            dhan_client_id=decrypt_data(user.dhan_client_id),
            transaction_type=TransactionType.SELL,
            exchange_segment=trade["exchange_segment"],
            product_type=trade["product_type"],
            order_type=OrderType.MARKET if exit_data.exit_price is None else OrderType.LIMIT,
            validity=Validity.DAY if trade["trade_type"] == TradeType.INTRADAY else Validity.IOC,
            trading_symbol=trade["trading_symbol"],
            security_id=trade["security_id"],
            quantity=trade["quantity"],
            disclosed_quantity=0,
            price=exit_data.exit_price,
            after_market_order=False
        )
        
        try:
            # Place exit order using direct HTTP client
            import http.client
            import json
            
            # Get decrypted access token
            access_token = decrypt_data(user.dhan_access_token)
            
            conn = http.client.HTTPSConnection("api.dhan.co")

            # Convert order request to DHAN API format
            # DHAN requires correlationId to be at most 25 characters.
            correlation_id = uuid.uuid4().hex[:24]

            # Map internal product types (MIS/CNC/NRML) to DHAN API productType
            internal_product_type = trade["product_type"]
            if internal_product_type == "MIS":
                dhan_product_type = "INTRADAY"
            elif internal_product_type == "NRML":
                dhan_product_type = "MARGIN"
            elif internal_product_type == "CNC":
                dhan_product_type = "CNC"
            else:
                # Fallback to whatever is stored
                dhan_product_type = internal_product_type

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
                "price": exit_order.price,
                "triggerPrice": None,
                "afterMarketOrder": False,
                "amoTime": "OPEN"
            }

            headers = {
                'access-token': access_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
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
            
            # Calculate P&L and charges
            entry_value = trade["quantity"] * trade["entry_price"]
            exit_value = trade["quantity"] * exit_data.exit_price
            pnl = exit_value - entry_value if trade["transaction_type"] == "BUY" else entry_value - exit_value
            pnl_percentage = (pnl / entry_value) * 100
            
            # Calculate charges for both entry and exit
            entry_charges = await TradeService.calculate_charges(entry_value)
            exit_charges = await TradeService.calculate_charges(exit_value)
            
            total_charges = entry_charges["total_charges"] + exit_charges["total_charges"]
            net_pnl = pnl - total_charges
            
            # Update trade with exit details
            update_data = {
                "exit_price": exit_data.exit_price,
                "exit_time": datetime.utcnow(),
                "status": TradeStatus.EXITED,
                "exit_reason": exit_data.exit_reason,
                "pnl": round(pnl, 2),
                "pnl_percentage": round(pnl_percentage, 2),
                "brokerage": round(entry_charges["brokerage"] + exit_charges["brokerage"], 2),
                "taxes": round(entry_charges["total_charges"] + exit_charges["total_charges"] - 
                              (entry_charges["brokerage"] + exit_charges["brokerage"]), 2),
                "net_pnl": round(net_pnl, 2),
                "updated_at": datetime.utcnow()
            }
            
            await trades_collection.update_one(
                {"trade_id": trade_id},
                {"$set": update_data}
            )
            
            # Get updated trade
            updated_trade = await trades_collection.find_one({"trade_id": trade_id})
            
            return {
                "status": "SUCCESS",
                "trade_id": trade_id,
                "order_id": order_response.get("orderId"),
                "message": "Trade exited successfully",
                "pnl": pnl,
                "pnl_percentage": pnl_percentage,
                "charges": total_charges,
                "net_pnl": net_pnl
            }

        except HTTPException:
            # Propagate DHAN HTTP errors without wrapping
            raise
        except Exception as e:
            logger.error(f"Error exiting trade: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "TRADE_EXIT_FAILED", "message": str(e)}
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

