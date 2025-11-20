"""
DHAN API service for interacting with DHANHQ trading API.
"""
from dhanhq import dhanhq
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from app.core.security import decrypt_data
from app.models.user import UserInDB
from app.models.order import PlaceOrderRequest, ModifyOrderRequest


class DhanService:
    """Service class for DHAN API operations."""
    
    @staticmethod
    def get_dhan_client(user: UserInDB) -> dhanhq:
        """
        Initialize and return a DHAN client for the user.
        
        Args:
            user: User with encrypted DHAN credentials
            
        Returns:
            dhanhq: Initialized DHAN client
            
        Raises:
            HTTPException: If credentials are missing or invalid
        """
        if not user.dhan_client_id or not user.dhan_access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="DHAN credentials not configured"
            )
        
        try:
            # Decrypt credentials
            client_id = decrypt_data(user.dhan_client_id)
            access_token = decrypt_data(user.dhan_access_token)
            
            # Initialize DHAN client
            dhan = dhanhq(client_id, access_token)
            return dhan
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize DHAN client: {str(e)}"
            )
    
    @staticmethod
    async def get_profile(user: UserInDB) -> Dict[str, Any]:
        """Get user's DHAN trading profile."""
        try:
            dhan = DhanService.get_dhan_client(user)
            response = dhan.get_fund_limits()
            return response
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch profile: {str(e)}"
            )
    
    @staticmethod
    async def get_funds(user: UserInDB) -> Dict[str, Any]:
        """Get user's available funds and margin."""
        try:
            import http.client
            import json
            
            # Get decrypted access token
            access_token = decrypt_data(user.dhan_access_token)
            
            conn = http.client.HTTPSConnection("api.dhan.co")
            headers = {
                'access-token': access_token,
                'Accept': 'application/json'
            }
            
            conn.request("GET", "/fundlimit", headers=headers)
            res = conn.getresponse()
            data = json.loads(res.read().decode("utf-8"))
            
            # Transform response to match our schema
            return {
                'dhan_client_id': data.get('dhanClientId'),
                'available_balance': data.get('availabelBalance', 0),
                'sod_limit': data.get('sodLimit', 0),
                'collateral_amount': data.get('collateralAmount', 0),
                'receiveable_amount': data.get('receiveableAmount', 0),
                'utilized_amount': data.get('utilizedAmount', 0),
                'blocked_payout_amount': data.get('blockedPayoutAmount', 0),
                'withdrawable_balance': data.get('withdrawableBalance', 0)
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch funds: {str(e)}"
            )
    
    @staticmethod
    async def get_positions(user: UserInDB) -> Dict[str, Any]:
        """Get user's current open positions."""
        try:
            dhan = DhanService.get_dhan_client(user)
            response = dhan.get_positions()
            return response
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch positions: {str(e)}"
            )
    
    @staticmethod
    async def get_holdings(user: UserInDB) -> Dict[str, Any]:
        """Get user's long-term holdings."""
        try:
            dhan = DhanService.get_dhan_client(user)
            response = dhan.get_holdings()
            return response
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch holdings: {str(e)}"
            )
    
    @staticmethod
    async def get_order_book(user: UserInDB) -> Dict[str, Any]:
        """Get user's order book for the day."""
        try:
            dhan = DhanService.get_dhan_client(user)
            response = dhan.get_order_list()
            return response
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch order book: {str(e)}"
            )
    
    @staticmethod
    async def get_trade_book(user: UserInDB) -> Dict[str, Any]:
        """Get user's trade book for the day."""
        try:
            dhan = DhanService.get_dhan_client(user)
            response = dhan.get_trade_book()
            return response
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch trade book: {str(e)}"
            )
    
    @staticmethod
    async def place_order(user: UserInDB, order_request: PlaceOrderRequest) -> Dict[str, Any]:
        """
        Place a new order.
        
        Args:
            user: User placing the order
            order_request: Order details
            
        Returns:
            Dict containing order response from DHAN
        """
        try:
            dhan = DhanService.get_dhan_client(user)
            
            # Prepare order parameters
            order_params = {
                'security_id': order_request.security_id,
                'exchange_segment': order_request.exchange_segment,
                'transaction_type': order_request.transaction_type.value,
                'quantity': order_request.quantity,
                'order_type': order_request.order_type.value,
                'product_type': order_request.product_type.value,
                'validity': order_request.validity,
                'disclosed_quantity': order_request.disclosed_quantity or 0
            }
            
            # Add price for limit orders
            if order_request.price is not None:
                order_params['price'] = order_request.price
            
            # Add trigger price for stop loss orders
            if order_request.trigger_price is not None:
                order_params['trigger_price'] = order_request.trigger_price
            
            # Add AMO time if provided
            if order_request.amo_time:
                order_params['amo_time'] = order_request.amo_time
            
            # Place order
            response = dhan.place_order(**order_params)
            
            return response
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to place order: {str(e)}"
            )
    
    @staticmethod
    async def modify_order(user: UserInDB, modify_request: ModifyOrderRequest) -> Dict[str, Any]:
        """
        Modify an existing pending order.
        
        Args:
            user: User modifying the order
            modify_request: Modified order details
            
        Returns:
            Dict containing modification response from DHAN
        """
        try:
            dhan = DhanService.get_dhan_client(user)
            
            # Prepare modification parameters
            modify_params = {
                'order_id': modify_request.order_id
            }
            
            if modify_request.quantity is not None:
                modify_params['quantity'] = modify_request.quantity
            
            if modify_request.price is not None:
                modify_params['price'] = modify_request.price
            
            if modify_request.trigger_price is not None:
                modify_params['trigger_price'] = modify_request.trigger_price
            
            if modify_request.order_type is not None:
                modify_params['order_type'] = modify_request.order_type.value
            
            if modify_request.validity is not None:
                modify_params['validity'] = modify_request.validity
            
            if modify_request.disclosed_quantity is not None:
                modify_params['disclosed_quantity'] = modify_request.disclosed_quantity
            
            # Modify order
            response = dhan.modify_order(**modify_params)
            
            return response
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to modify order: {str(e)}"
            )
    
    @staticmethod
    async def cancel_order(user: UserInDB, order_id: str) -> Dict[str, Any]:
        """
        Cancel a pending order.
        
        Args:
            user: User canceling the order
            order_id: ID of the order to cancel
            
        Returns:
            Dict containing cancellation response from DHAN
        """
        try:
            dhan = DhanService.get_dhan_client(user)
            response = dhan.cancel_order(order_id)
            return response
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel order: {str(e)}"
            )
    
    @staticmethod
    async def get_historical_data(
        user: UserInDB,
        security_id: str,
        exchange_segment: str,
        instrument_type: str,
        from_date: str,
        to_date: str
    ) -> Dict[str, Any]:
        """
        Get daily historical data (OHLC & Volume).
        
        Args:
            user: User requesting the data
            security_id: Security ID of the instrument
            exchange_segment: Exchange segment (e.g., NSE_EQ, BSE_EQ)
            instrument_type: Instrument type (e.g., EQUITY, FUTIDX, OPTIDX)
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            
        Returns:
            Dict containing historical OHLC data
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"🔍 DHAN API Request:")
            logger.info(f"  Security ID: {security_id}")
            logger.info(f"  Exchange: {exchange_segment}")
            logger.info(f"  Type: {instrument_type}")
            logger.info(f"  From: {from_date}")
            logger.info(f"  To: {to_date}")
            
            dhan = DhanService.get_dhan_client(user)
            response = dhan.historical_daily_data(
                security_id=security_id,
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                from_date=from_date,
                to_date=to_date
            )
            
            logger.info(f"📊 DHAN API Response:")
            logger.info(f"  Response type: {type(response)}")
            logger.info(f"  Response keys: {response.keys() if isinstance(response, dict) else 'Not a dict'}")
            if isinstance(response, dict) and 'data' in response:
                data = response['data']
                logger.info(f"  Data type: {type(data)}")
                if isinstance(data, list):
                    logger.info(f"  Data length: {len(data)}")
                    if len(data) > 0:
                        logger.info(f"  First candle: {data[0]}")
                        logger.info(f"  Last candle: {data[-1]}")
                elif isinstance(data, dict):
                    logger.info(f"  Data keys: {data.keys()}")
                    for key in ['open', 'high', 'low', 'close', 'volume']:
                        if key in data:
                            logger.info(f"  {key} length: {len(data[key]) if isinstance(data[key], list) else 'Not a list'}")
            
            logger.info(f"  Full response: {response}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ DHAN API Error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch historical data: {str(e)}"
            )
    
    @staticmethod
    async def get_intraday_data(
        user: UserInDB,
        security_id: str,
        exchange_segment: str,
        instrument_type: str,
        from_date: str,
        to_date: str
    ) -> Dict[str, Any]:
        """
        Get intraday minute data (1-minute candles).
        
        Args:
            user: User requesting the data
            security_id: Security ID of the instrument
            exchange_segment: Exchange segment (e.g., NSE_EQ, BSE_EQ)
            instrument_type: Instrument type (e.g., EQUITY, FUTIDX, OPTIDX)
            from_date: Start date in YYYY-MM-DD HH:MM:SS format
            to_date: End date in YYYY-MM-DD HH:MM:SS format
            
        Returns:
            Dict containing intraday OHLC data
        """
        try:
            dhan = DhanService.get_dhan_client(user)
            response = dhan.intraday_minute_data(
                security_id=security_id,
                exchange_segment=exchange_segment,
                instrument_type=instrument_type,
                from_date=from_date,
                to_date=to_date,
            )

            # Normalise DHAN's shape ({"status":"success","data":{...}})
            # to a flat OHLC structure that the rest of the app expects.
            if isinstance(response, dict) and response.get("status") == "success":
                data = response.get("data")
                if isinstance(data, dict):
                    if any(k in data for k in ("open", "high", "low", "close", "volume")):
                        return {
                            "open": data.get("open") or [],
                            "high": data.get("high") or [],
                            "low": data.get("low") or [],
                            "close": data.get("close") or [],
                            "volume": data.get("volume") or [],
                            "timestamp": data.get("timestamp") or [],
                        }

            # Fallback: return raw response (error cases, unexpected shapes, etc.)
            return response
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch intraday data: {str(e)}"
            )
