"""
DHAN API proxy router for trading operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from app.api.deps import get_current_user_with_dhan_credentials
from app.models.user import UserInDB
from app.models.order import PlaceOrderRequest, ModifyOrderRequest, OrderResponse
from app.services.dhan_service import DhanService
from app.db.database import Database
from datetime import datetime
from bson import ObjectId


router = APIRouter(prefix="/api/v2/dhan", tags=["DHAN API"])


@router.get("/profile")
async def get_profile(
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Get the user's DHAN trading profile and fund limits.
    """
    return await DhanService.get_profile(current_user)


@router.get("/funds")
async def get_funds(
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Get the user's available funds and margin details.
    """
    return await DhanService.get_funds(current_user)


@router.get("/positions")
async def get_positions(
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Get the user's current open positions.
    """
    return await DhanService.get_positions(current_user)


@router.get("/holdings")
async def get_holdings(
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Get the user's long-term holdings.
    """
    return await DhanService.get_holdings(current_user)


@router.get("/order-book")
async def get_order_book(
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Get the user's order book for the day.
    """
    return await DhanService.get_order_book(current_user)


@router.get("/trade-book")
async def get_trade_book(
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Get the user's trade book for the day.
    """
    return await DhanService.get_trade_book(current_user)


@router.post("/place-order")
async def place_order(
    order_request: PlaceOrderRequest,
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Place a new order (Market, Limit, Stop Loss, etc.).
    
    The order will be placed via DHAN API and logged in the database.
    """
    # Place order via DHAN API
    response = await DhanService.place_order(current_user, order_request)
    
    # Log order in database
    try:
        orders_collection = Database.get_orders_log_collection()
        
        order_log = {
            "user_id": current_user.id,
            "dhan_order_id": response.get("orderId", ""),
            "symbol": order_request.security_id,  # You might want to resolve this to actual symbol
            "security_id": order_request.security_id,
            "exchange_segment": order_request.exchange_segment,
            "transaction_type": order_request.transaction_type.value,
            "quantity": order_request.quantity,
            "price": order_request.price,
            "trigger_price": order_request.trigger_price,
            "order_type": order_request.order_type.value,
            "product_type": order_request.product_type.value,
            "status": response.get("orderStatus", "PENDING"),
            "timestamp": datetime.utcnow()
        }
        
        await orders_collection.insert_one(order_log)
        
    except Exception as e:
        # Log error but don't fail the request since order was placed
        print(f"Failed to log order in database: {str(e)}")
    
    return response


@router.put("/modify-order")
async def modify_order(
    modify_request: ModifyOrderRequest,
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Modify an existing pending order.
    
    You can modify quantity, price, trigger price, order type, validity, and disclosed quantity.
    """
    response = await DhanService.modify_order(current_user, modify_request)
    
    # Update order log in database
    try:
        orders_collection = Database.get_orders_log_collection()
        
        update_fields = {
            "timestamp": datetime.utcnow()
        }
        
        if modify_request.quantity is not None:
            update_fields["quantity"] = modify_request.quantity
        
        if modify_request.price is not None:
            update_fields["price"] = modify_request.price
        
        if modify_request.trigger_price is not None:
            update_fields["trigger_price"] = modify_request.trigger_price
        
        await orders_collection.update_one(
            {
                "user_id": current_user.id,
                "dhan_order_id": modify_request.order_id
            },
            {"$set": update_fields}
        )
        
    except Exception as e:
        print(f"Failed to update order log in database: {str(e)}")
    
    return response


@router.delete("/cancel-order/{order_id}")
async def cancel_order(
    order_id: str,
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Cancel a pending order.
    
    - **order_id**: The DHAN order ID to cancel
    """
    response = await DhanService.cancel_order(current_user, order_id)
    
    # Update order status in database
    try:
        orders_collection = Database.get_orders_log_collection()
        
        await orders_collection.update_one(
            {
                "user_id": current_user.id,
                "dhan_order_id": order_id
            },
            {
                "$set": {
                    "status": "CANCELLED",
                    "timestamp": datetime.utcnow()
                }
            }
        )
        
    except Exception as e:
        print(f"Failed to update order status in database: {str(e)}")
    
    return response


@router.get("/historical-data")
async def get_historical_data(
    security_id: str,
    exchange_segment: str,
    instrument_type: str,
    from_date: str,
    to_date: str,
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Get daily historical data (OHLC & Volume).
    
    - **security_id**: Security ID of the instrument (e.g., "1333" for HDFC Bank)
    - **exchange_segment**: Exchange segment (e.g., NSE_EQ, BSE_EQ, NSE_FNO)
    - **instrument_type**: Instrument type (e.g., EQUITY, FUTIDX, OPTIDX)
    - **from_date**: Start date in YYYY-MM-DD format
    - **to_date**: End date in YYYY-MM-DD format
    """
    return await DhanService.get_historical_data(
        current_user,
        security_id,
        exchange_segment,
        instrument_type,
        from_date,
        to_date
    )


@router.get("/intraday-data")
async def get_intraday_data(
    security_id: str,
    exchange_segment: str,
    instrument_type: str,
    from_date: str,
    to_date: str,
    current_user: UserInDB = Depends(get_current_user_with_dhan_credentials)
) -> Dict[str, Any]:
    """
    Get intraday minute data (1-minute candles).
    
    - **security_id**: Security ID of the instrument (e.g., "1333" for HDFC Bank)
    - **exchange_segment**: Exchange segment (e.g., NSE_EQ, BSE_EQ, NSE_FNO)
    - **instrument_type**: Instrument type (e.g., EQUITY, FUTIDX, OPTIDX)
    - **from_date**: Start date in YYYY-MM-DD HH:MM:SS format
    - **to_date**: End date in YYYY-MM-DD HH:MM:SS format
    
    Note: Returns 1-minute candle data.
    """
    return await DhanService.get_intraday_data(
        current_user,
        security_id,
        exchange_segment,
        instrument_type,
        from_date,
        to_date
    )


@router.get("/demo/historical-data", tags=["Demo"])
async def demo_get_historical_data(
    security_id: str = "1333",
    exchange_segment: str = "NSE_EQ",
    instrument_type: str = "EQUITY",
    from_date: str = None,
    to_date: str = None
) -> Dict[str, Any]:
    """
    Demo endpoint to fetch historical data without authentication.
    Uses master DHAN credentials from environment variables.
    
    **No authentication required!**
    
    **Common Security IDs (NSE_EQ):**
    - HDFC Bank: 1333
    - Reliance Industries: 738
    - TCS: 11536
    - Infosys: 1594
    - ICICI Bank: 4963
    - SBI: 3045
    - Tata Steel: 3499
    - NTPC: 11630
    - Power Grid: 11631
    - Coal India: 20374
    - Wipro: 3787
    - Hindustan Unilever: 5197
    - ITC: 5246
    - Bajaj Auto: 1660
    - Maruti Suzuki: 10999
    
    - **security_id**: Security ID of the instrument (default: "1333" for HDFC Bank)
    - **exchange_segment**: Exchange segment (default: NSE_EQ)
    - **instrument_type**: Instrument type (default: EQUITY)
    - **from_date**: Start date in YYYY-MM-DD format (default: 30 days ago)
    - **to_date**: End date in YYYY-MM-DD format (default: today)
    """
    from datetime import datetime, timedelta
    
    # Set default dates if not provided
    if not from_date or not to_date:
        today = datetime.now()
        from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
    
    # Validate security_id format
    if not security_id or not security_id.isdigit():
        return {
            "status": "error",
            "message": "Invalid security_id. Must be a numeric string.",
            "hint": "Use valid NSE security IDs like: 1333 (HDFC), 738 (Reliance), 11536 (TCS)",
            "common_stocks": {
                "HDFC Bank": "1333",
                "Reliance Industries": "738", 
                "TCS": "11536",
                "Infosys": "1594",
                "ICICI Bank": "4963",
                "SBI": "3045",
                "Tata Steel": "3499",
                "NTPC": "11630",
                "Power Grid": "11631",
                "Coal India": "20374"
            }
        }
    
    from dhanhq import dhanhq
    from app.core.config import settings
    
    try:
        # Check if master credentials are configured
        if not settings.DHAN_MASTER_CLIENT_ID or not settings.DHAN_MASTER_ACCESS_TOKEN:
            return {
                "status": "error",
                "message": "DHAN master credentials not configured in .env file",
                "hint": "Add DHAN_MASTER_CLIENT_ID and DHAN_MASTER_ACCESS_TOKEN to your .env"
            }
        
        # Initialize DHAN client with master credentials
        dhan = dhanhq(
            settings.DHAN_MASTER_CLIENT_ID,
            settings.DHAN_MASTER_ACCESS_TOKEN
        )
        
        # Fetch historical data
        response = dhan.historical_daily_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            from_date=from_date,
            to_date=to_date
        )
        
        return response
        
    except Exception as e:
        error_msg = str(e)
        
        # Check if it's a security ID related error
        if "DH-905" in error_msg or "Input_Exception" in error_msg:
            return {
                "status": "error",
                "message": f"Invalid security_id '{security_id}' or parameters. Please check the security ID.",
                "hint": "Use valid NSE security IDs. Common ones:",
                "common_stocks": {
                    "HDFC Bank": "1333",
                    "Reliance Industries": "738",
                    "TCS": "11536", 
                    "Infosys": "1594",
                    "ICICI Bank": "4963",
                    "SBI": "3045",
                    "Tata Steel": "3499",
                    "NTPC": "11630",
                    "Power Grid": "11631",
                    "Coal India": "20374",
                    "Wipro": "3787",
                    "Hindustan Unilever": "5197",
                    "ITC": "5246",
                    "Bajaj Auto": "1660",
                    "Maruti Suzuki": "10999"
                },
                "error_details": error_msg,
                "parameters_used": {
                    "security_id": security_id,
                    "exchange_segment": exchange_segment,
                    "instrument_type": instrument_type,
                    "from_date": from_date,
                    "to_date": to_date
                }
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to fetch historical data: {error_msg}",
                "error_type": type(e).__name__,
                "parameters_used": {
                    "security_id": security_id,
                    "exchange_segment": exchange_segment,
                    "instrument_type": instrument_type,
                    "from_date": from_date,
                    "to_date": to_date
                }
            }


@router.get("/demo/intraday-data", tags=["Demo"])
async def demo_get_intraday_data(
    security_id: str = "1333",
    exchange_segment: str = "NSE_EQ",
    instrument_type: str = "EQUITY",
    from_date: str = None,
    to_date: str = None
) -> Dict[str, Any]:
    """
    Demo endpoint to fetch intraday data without authentication.
    Uses master DHAN credentials from environment variables.
    
    **No authentication required!**
    
    **Common Security IDs (NSE_EQ):**
    - HDFC Bank: 1333
    - Reliance Industries: 738
    - TCS: 11536
    - Infosys: 1594
    - ICICI Bank: 4963
    - SBI: 3045
    - Tata Steel: 3499
    - NTPC: 11630
    - Power Grid: 11631
    - Coal India: 20374
    - Wipro: 3787
    - Hindustan Unilever: 5197
    - ITC: 5246
    - Bajaj Auto: 1660
    - Maruti Suzuki: 10999
    
    - **security_id**: Security ID of the instrument (default: "1333" for HDFC Bank)
    - **exchange_segment**: Exchange segment (default: NSE_EQ)
    - **instrument_type**: Instrument type (default: EQUITY)
    - **from_date**: Start date in YYYY-MM-DD HH:MM:SS format (default: 5 days ago, 9:15 AM)
    - **to_date**: End date in YYYY-MM-DD HH:MM:SS format (default: today, 3:30 PM)
    """
    from datetime import datetime, timedelta
    
    # Set default dates if not provided
    if not from_date or not to_date:
        today = datetime.now()
        from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d 09:15:00")
        to_date = today.strftime("%Y-%m-%d 15:30:00")
    
    # Validate security_id format
    if not security_id or not security_id.isdigit():
        return {
            "status": "error",
            "message": "Invalid security_id. Must be a numeric string.",
            "hint": "Use valid NSE security IDs like: 1333 (HDFC), 738 (Reliance), 11536 (TCS)",
            "common_stocks": {
                "HDFC Bank": "1333",
                "Reliance Industries": "738", 
                "TCS": "11536",
                "Infosys": "1594",
                "ICICI Bank": "4963",
                "SBI": "3045",
                "Tata Steel": "3499",
                "NTPC": "11630",
                "Power Grid": "11631",
                "Coal India": "20374"
            }
        }
    
    from dhanhq import dhanhq
    from app.core.config import settings
    
    try:
        # Check if master credentials are configured
        if not settings.DHAN_MASTER_CLIENT_ID or not settings.DHAN_MASTER_ACCESS_TOKEN:
            return {
                "status": "error",
                "message": "DHAN master credentials not configured in .env file",
                "hint": "Add DHAN_MASTER_CLIENT_ID and DHAN_MASTER_ACCESS_TOKEN to your .env"
            }
        
        # Initialize DHAN client with master credentials
        dhan = dhanhq(
            settings.DHAN_MASTER_CLIENT_ID,
            settings.DHAN_MASTER_ACCESS_TOKEN
        )
        
        # Fetch intraday data
        response = dhan.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            from_date=from_date,
            to_date=to_date
        )
        
        return response
        
    except Exception as e:
        error_msg = str(e)
        
        # Check if it's a security ID related error
        if "DH-905" in error_msg or "Input_Exception" in error_msg:
            # Check for specific 90-day limit error
            if "90 days at a time" in error_msg:
                return {
                    "status": "error",
                    "message": "Intraday data request exceeds DHAN API limit of 90 days.",
                    "hint": "DHAN API allows maximum 90 days of intraday data per request. Try smaller date ranges or multiple requests.",
                    "solution": "Reduce the date range to 90 days or less. For example: from_date=2025-01-01 to_date=2025-03-31 (90 days)",
                    "error_details": error_msg,
                    "parameters_used": {
                        "security_id": security_id,
                        "exchange_segment": exchange_segment,
                        "instrument_type": instrument_type,
                        "from_date": from_date,
                        "to_date": to_date
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": f"Invalid security_id '{security_id}' or parameters. Please check the security ID.",
                    "hint": "Use valid NSE security IDs. Common ones:",
                    "common_stocks": {
                        "HDFC Bank": "1333",
                        "Reliance Industries": "738",
                        "TCS": "11536", 
                        "Infosys": "1594",
                        "ICICI Bank": "4963",
                        "SBI": "3045",
                        "Tata Steel": "3499",
                        "NTPC": "11630",
                        "Power Grid": "11631",
                        "Coal India": "20374",
                        "Wipro": "3787",
                        "Hindustan Unilever": "5197",
                        "ITC": "5246",
                        "Bajaj Auto": "1660",
                        "Maruti Suzuki": "10999"
                    },
                    "error_details": error_msg,
                    "parameters_used": {
                        "security_id": security_id,
                        "exchange_segment": exchange_segment,
                        "instrument_type": instrument_type,
                        "from_date": from_date,
                        "to_date": to_date
                    }
                }
        else:
            return {
                "status": "error",
                "message": f"Failed to fetch intraday data: {error_msg}",
                "error_type": type(e).__name__,
                "parameters_used": {
                    "security_id": security_id,
                    "exchange_segment": exchange_segment,
                    "instrument_type": instrument_type,
                    "from_date": from_date,
                    "to_date": to_date
                }
            }

@router.post("/demo/expired-options", tags=["Demo"])
async def demo_get_expired_options(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch expired options contract data using DHAN's Rolling Options API.
    
    This endpoint provides historical expired options data with:
    - Open, High, Low, Close prices
    - Implied Volatility (IV)
    - Volume and Open Interest (OI)
    - Spot price information
    - Up to 5 years of historical data
    - Strike-wise data (ATM, ATM+10, ATM-10)
    
    **Request Format:**
    ```json
    {
        "exchangeSegment": "NSE_FNO",
        "interval": "1",
        "securityId": 13,
        "instrument": "OPTIDX",
        "expiryFlag": "MONTH",
        "expiryCode": 1,
        "strike": "ATM",
        "drvOptionType": "CALL",
        "requiredData": ["open", "high", "low", "close", "volume", "iv", "oi", "spot"],
        "fromDate": "2024-08-01",
        "toDate": "2024-09-01"
    }
    ```
    
    **Parameters:**
    - exchangeSegment: NSE_FNO
    - interval: 1, 5, 15, 25, 60 (minutes)
    - securityId: Underlying security ID (13 for NIFTY, 26009 for BANKNIFTY)
    - instrument: OPTIDX (index options) or OPTFUT (stock options)
    - expiryFlag: WEEK or MONTH
    - expiryCode: 1, 2, 3 (near, next, far expiry)
    - strike: ATM, ATM+1, ATM-1, etc. (up to ATM+10/ATM-10)
    - drvOptionType: CALL or PUT
    - requiredData: Array of data fields
    - fromDate/toDate: Date range (max 30 days per request)
    
    **Returns:** Expired options data with CE/PE information
    """
    import requests
    from app.core.config import settings
    
    try:
        # Validate required fields
        required_fields = ["exchangeSegment", "securityId", "instrument", "fromDate", "toDate"]
        for field in required_fields:
            if field not in request:
                return {
                    "status": "error",
                    "message": f"Missing required field: {field}",
                    "required_fields": required_fields
                }
        
        # Check if master credentials are configured
        if not settings.DHAN_MASTER_ACCESS_TOKEN:
            return {
                "status": "error",
                "message": "DHAN master access token not configured in .env file",
                "hint": "Add DHAN_MASTER_ACCESS_TOKEN to your .env"
            }
        
        # Prepare request payload
        payload = {
            "exchangeSegment": request.get("exchangeSegment", "NSE_FNO"),
            "interval": str(request.get("interval", "1")),
            "securityId": request.get("securityId"),
            "instrument": request.get("instrument", "OPTIDX"),
            "expiryFlag": request.get("expiryFlag", "MONTH"),
            "expiryCode": request.get("expiryCode", 1),
            "strike": request.get("strike", "ATM"),
            "drvOptionType": request.get("drvOptionType", "CALL"),
            "requiredData": request.get("requiredData", ["open", "high", "low", "close", "volume"]),
            "fromDate": request.get("fromDate"),
            "toDate": request.get("toDate")
        }
        
        # Make request to DHAN's Rolling Options API
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "access-token": settings.DHAN_MASTER_ACCESS_TOKEN,
            "clientId": settings.DHAN_MASTER_CLIENT_ID
        }
        
        response = requests.post(
            "https://api.dhan.co/v2/charts/rollingoption",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        # Parse response
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "data": data.get("data", {}),
                "request_parameters": payload
            }
        else:
            error_data = response.json() if response.text else {}
            return {
                "status": "error",
                "message": f"DHAN API returned error: {response.status_code}",
                "error_details": error_data,
                "request_parameters": payload
            }
            
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Request timeout - DHAN API took too long to respond",
            "hint": "Try a smaller date range or try again later"
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Network error: {str(e)}",
            "hint": "Check your internet connection and try again"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch expired options data: {str(e)}",
            "error_type": type(e).__name__,
            "request_parameters": request
        }


@router.post("/demo/expired-options-multi", tags=["Demo"])
async def demo_get_expired_options_multi(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch expired options data for multiple indices (NIFTY, BANKNIFTY, NIFTY IT, NIFTY FINANCIAL).
    
    This endpoint fetches historical options data for all major indices in a single request.
    
    **Request Format:**
    ```json
    {
        "fromDate": "2024-08-01",
        "toDate": "2024-09-01",
        "interval": "1",
        "expiryFlag": "MONTH",
        "expiryCode": 1,
        "strikes": ["ATM", "ATM+1", "ATM-1"],
        "optionTypes": ["CALL", "PUT"],
        "indices": ["NIFTY", "BANKNIFTY", "NIFTY_IT", "NIFTY_FINANCIAL"]
    }
    ```
    
    **Parameters:**
    - fromDate: Start date (YYYY-MM-DD)
    - toDate: End date (YYYY-MM-DD)
    - interval: 1, 5, 15, 25, 60 (minutes) - default: "1"
    - expiryFlag: WEEK or MONTH - default: "MONTH"
    - expiryCode: 1, 2, 3 (near, next, far expiry) - default: 1
    - strikes: Array of strikes (e.g., ["ATM", "ATM+1", "ATM-1"]) - default: ["ATM"]
    - optionTypes: Array of option types (["CALL", "PUT"]) - default: ["CALL", "PUT"]
    - indices: Array of indices to fetch - default: all four indices
    
    **Available Indices:**
    - NIFTY (Security ID: 13)
    - BANKNIFTY (Security ID: 26009)
    - NIFTY_IT (Security ID: 26001)
    - NIFTY_FINANCIAL (Security ID: 26074)
    
    **Returns:** Options data for all requested indices organized by index name
    """
    import requests
    from app.core.config import settings
    
    # Index configurations
    INDICES = {
        "NIFTY": {"security_id": 13, "display_name": "NIFTY 50"},
        "BANKNIFTY": {"security_id": 26009, "display_name": "NIFTY BANK"},
        "NIFTY_IT": {"security_id": 26001, "display_name": "NIFTY IT"},
        "NIFTY_FINANCIAL": {"security_id": 26074, "display_name": "NIFTY FINANCIAL SERVICES"}
    }
    
    try:
        # Validate required fields
        if "fromDate" not in request or "toDate" not in request:
            return {
                "status": "error",
                "message": "Missing required fields: fromDate and toDate",
                "required_fields": ["fromDate", "toDate"]
            }
        
        # Check if master credentials are configured
        if not settings.DHAN_MASTER_ACCESS_TOKEN:
            return {
                "status": "error",
                "message": "DHAN master access token not configured in .env file",
                "hint": "Add DHAN_MASTER_ACCESS_TOKEN to your .env"
            }
        
        # Parse request parameters
        from_date = request.get("fromDate")
        to_date = request.get("toDate")
        interval = str(request.get("interval", "1"))
        expiry_flag = request.get("expiryFlag", "MONTH")
        expiry_code = request.get("expiryCode", 1)
        strikes = request.get("strikes", ["ATM"])
        option_types = request.get("optionTypes", ["CALL", "PUT"])
        requested_indices = request.get("indices", list(INDICES.keys()))
        
        # Validate requested indices
        invalid_indices = [idx for idx in requested_indices if idx not in INDICES]
        if invalid_indices:
            return {
                "status": "error",
                "message": f"Invalid indices: {', '.join(invalid_indices)}",
                "valid_indices": list(INDICES.keys())
            }
        
        # Prepare headers
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "access-token": settings.DHAN_MASTER_ACCESS_TOKEN,
            "clientId": settings.DHAN_MASTER_CLIENT_ID
        }
        
        # Fetch data for all requested indices
        results = {}
        
        for index_key in requested_indices:
            index_config = INDICES[index_key]
            index_results = {
                "security_id": index_config["security_id"],
                "display_name": index_config["display_name"],
                "data": {}
            }
            
            # Fetch data for each strike and option type combination
            for strike in strikes:
                for option_type in option_types:
                    key = f"{strike}_{option_type}"
                    
                    payload = {
                        "exchangeSegment": "NSE_FNO",
                        "interval": interval,
                        "securityId": index_config["security_id"],
                        "instrument": "OPTIDX",
                        "expiryFlag": expiry_flag,
                        "expiryCode": expiry_code,
                        "strike": strike,
                        "drvOptionType": option_type,
                        "requiredData": ["open", "high", "low", "close", "volume", "iv", "oi", "spot"],
                        "fromDate": from_date,
                        "toDate": to_date
                    }
                    
                    try:
                        response = requests.post(
                            "https://api.dhan.co/v2/charts/rollingoption",
                            json=payload,
                            headers=headers,
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            index_results["data"][key] = {
                                "status": "success",
                                "data": data.get("data", {}),
                                "strike": strike,
                                "option_type": option_type
                            }
                        else:
                            error_data = response.json() if response.text else {}
                            index_results["data"][key] = {
                                "status": "error",
                                "message": f"API error: {response.status_code}",
                                "error_details": error_data,
                                "strike": strike,
                                "option_type": option_type
                            }
                    except Exception as e:
                        index_results["data"][key] = {
                            "status": "error",
                            "message": str(e),
                            "strike": strike,
                            "option_type": option_type
                        }
            
            results[index_key] = index_results
        
        # Calculate summary statistics
        summary = {
            "total_indices": len(requested_indices),
            "total_requests": len(requested_indices) * len(strikes) * len(option_types),
            "date_range": {"from": from_date, "to": to_date},
            "indices_fetched": requested_indices
        }
        
        return {
            "status": "success",
            "summary": summary,
            "results": results
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch multi-index options data: {str(e)}",
            "error_type": type(e).__name__
        }


@router.post("/demo/nifty50-stocks", tags=["Demo"])
async def demo_get_nifty50_stocks(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch historical data for NIFTY 50 stocks.
    
    This endpoint fetches daily OHLCV data for all or selected NIFTY 50 constituent stocks.
    
    **Request Format:**
    ```json
    {
        "fromDate": "2024-08-01",
        "toDate": "2024-11-01",
        "stocks": ["HDFC Bank", "Reliance Industries", "TCS"]
    }
    ```
    
    **Parameters:**
    - fromDate: Start date (YYYY-MM-DD)
    - toDate: End date (YYYY-MM-DD)
    - stocks: Optional array of stock names. If not provided, fetches all NIFTY 50 stocks
    
    **Available Stocks:** HDFC Bank, ICICI Bank, SBI, Reliance Industries, TCS, Infosys, and 44 more
    
    **Returns:** Historical OHLCV data for requested stocks
    """
    from dhanhq import dhanhq
    from app.core.config import settings
    import time
    
    # NIFTY 50 Stocks
    NIFTY_50_STOCKS = {
        "HDFC Bank": {"security_id": "1333", "symbol": "HDFCBANK"},
        "ICICI Bank": {"security_id": "4963", "symbol": "ICICIBANK"},
        "SBI": {"security_id": "3045", "symbol": "SBIN"},
        "Kotak Mahindra Bank": {"security_id": "1922", "symbol": "KOTAKBANK"},
        "Axis Bank": {"security_id": "5900", "symbol": "AXISBANK"},
        "IndusInd Bank": {"security_id": "5258", "symbol": "INDUSINDBK"},
        "TCS": {"security_id": "11536", "symbol": "TCS"},
        "Infosys": {"security_id": "1594", "symbol": "INFY"},
        "Wipro": {"security_id": "3787", "symbol": "WIPRO"},
        "HCL Technologies": {"security_id": "7229", "symbol": "HCLTECH"},
        "Tech Mahindra": {"security_id": "13538", "symbol": "TECHM"},
        "Reliance Industries": {"security_id": "2885", "symbol": "RELIANCE"},
        "ONGC": {"security_id": "2475", "symbol": "ONGC"},
        "NTPC": {"security_id": "11630", "symbol": "NTPC"},
        "Power Grid": {"security_id": "11631", "symbol": "POWERGRID"},
        "Coal India": {"security_id": "20374", "symbol": "COALINDIA"},
        "Maruti Suzuki": {"security_id": "10999", "symbol": "MARUTI"},
        "Mahindra & Mahindra": {"security_id": "2031", "symbol": "M&M"},
        "Tata Motors": {"security_id": "3456", "symbol": "TATAMOTORS"},
        "Bajaj Auto": {"security_id": "1660", "symbol": "BAJAJ-AUTO"},
        "Hero MotoCorp": {"security_id": "1348", "symbol": "HEROMOTOCO"},
        "Eicher Motors": {"security_id": "910", "symbol": "EICHERMOT"},
        "Hindustan Unilever": {"security_id": "1394", "symbol": "HINDUNILVR"},
        "ITC": {"security_id": "1660", "symbol": "ITC"},
        "Britannia Industries": {"security_id": "547", "symbol": "BRITANNIA"},
        "Nestle India": {"security_id": "1232", "symbol": "NESTLEIND"},
        "Asian Paints": {"security_id": "7406", "symbol": "ASIANPAINT"},
        "Tata Steel": {"security_id": "3499", "symbol": "TATASTEEL"},
        "JSW Steel": {"security_id": "11723", "symbol": "JSWSTEEL"},
        "Hindalco": {"security_id": "1363", "symbol": "HINDALCO"},
        "Sun Pharmaceutical": {"security_id": "3351", "symbol": "SUNPHARMA"},
        "Dr Reddy's Laboratories": {"security_id": "881", "symbol": "DRREDDY"},
        "Cipla": {"security_id": "701", "symbol": "CIPLA"},
        "Divi's Laboratories": {"security_id": "10940", "symbol": "DIVISLAB"},
        "UltraTech Cement": {"security_id": "11532", "symbol": "ULTRACEMCO"},
        "Grasim Industries": {"security_id": "1232", "symbol": "GRASIM"},
        "Larsen & Toubro": {"security_id": "11483", "symbol": "LT"},
        "Bharti Airtel": {"security_id": "10604", "symbol": "BHARTIARTL"},
        "Adani Ports": {"security_id": "15083", "symbol": "ADANIPORTS"},
        "Bajaj Finserv": {"security_id": "16675", "symbol": "BAJAJFINSV"},
        "Bajaj Finance": {"security_id": "16669", "symbol": "BAJFINANCE"},
        "Titan Company": {"security_id": "3506", "symbol": "TITAN"},
        "BPCL": {"security_id": "526", "symbol": "BPCL"},
        "IOC": {"security_id": "1624", "symbol": "IOC"},
        "Shree Cement": {"security_id": "3103", "symbol": "SHREECEM"},
        "Adani Enterprises": {"security_id": "25", "symbol": "ADANIENT"},
        "Apollo Hospitals": {"security_id": "157", "symbol": "APOLLOHOSP"},
        "Tata Consumer": {"security_id": "3432", "symbol": "TATACONSUM"},
    }
    
    try:
        # Validate required fields
        if "fromDate" not in request or "toDate" not in request:
            return {
                "status": "error",
                "message": "Missing required fields: fromDate and toDate",
                "required_fields": ["fromDate", "toDate"]
            }
        
        # Check if master credentials are configured
        if not settings.DHAN_MASTER_ACCESS_TOKEN:
            return {
                "status": "error",
                "message": "DHAN master access token not configured in .env file",
                "hint": "Add DHAN_MASTER_ACCESS_TOKEN to your .env"
            }
        
        # Parse request parameters
        from_date = request.get("fromDate")
        to_date = request.get("toDate")
        requested_stocks = request.get("stocks", list(NIFTY_50_STOCKS.keys()))
        
        # Validate requested stocks
        invalid_stocks = [stock for stock in requested_stocks if stock not in NIFTY_50_STOCKS]
        if invalid_stocks:
            return {
                "status": "error",
                "message": f"Invalid stocks: {', '.join(invalid_stocks)}",
                "valid_stocks": list(NIFTY_50_STOCKS.keys())
            }
        
        # Initialize DHAN client
        dhan = dhanhq(settings.DHAN_MASTER_CLIENT_ID, settings.DHAN_MASTER_ACCESS_TOKEN)
        
        # Fetch data for all requested stocks
        results = {}
        
        for stock_name in requested_stocks:
            stock_info = NIFTY_50_STOCKS[stock_name]
            
            try:
                response = dhan.historical_daily_data(
                    security_id=stock_info["security_id"],
                    exchange_segment="NSE_EQ",
                    instrument_type="EQUITY",
                    from_date=from_date,
                    to_date=to_date
                )
                
                # Check if data is available
                if isinstance(response, dict) and 'data' in response:
                    data = response['data']
                    if 'open' in data and len(data['open']) > 0:
                        results[stock_name] = {
                            "status": "success",
                            "symbol": stock_info["symbol"],
                            "security_id": stock_info["security_id"],
                            "candle_count": len(data['open']),
                            "data": data
                        }
                    else:
                        results[stock_name] = {
                            "status": "no_data",
                            "symbol": stock_info["symbol"],
                            "security_id": stock_info["security_id"],
                            "message": "No data available for the specified date range",
                            "debug_info": {
                                "has_data_key": 'data' in response,
                                "has_open_key": 'open' in data if data else False,
                                "response_keys": list(response.keys()) if response else [],
                                "data_keys": list(data.keys()) if data else []
                            }
                        }
                else:
                    results[stock_name] = {
                        "status": "error",
                        "symbol": stock_info["symbol"],
                        "security_id": stock_info["security_id"],
                        "message": "Unexpected response format",
                        "debug_info": {
                            "response_type": str(type(response)),
                            "response_keys": list(response.keys()) if isinstance(response, dict) else "Not a dict"
                        }
                    }
                    
            except Exception as e:
                error_msg = str(e)
                
                # Check if it's a DH-905 error (incorrect security ID)
                if "DH-905" in error_msg or "Input_Exception" in error_msg:
                    results[stock_name] = {
                        "status": "error",
                        "symbol": stock_info["symbol"],
                        "security_id": stock_info["security_id"],
                        "message": f"Invalid or outdated security ID: {stock_info['security_id']}",
                        "error_code": "DH-905",
                        "hint": "The security ID may be incorrect. Please verify from DHAN instrument master file.",
                        "download_link": "https://api.dhan.co/v2/instrument/NSE_EQ",
                        "error_type": type(e).__name__,
                        "debug_info": {
                            "full_error": error_msg,
                            "parameters": {
                                "security_id": stock_info["security_id"],
                                "exchange_segment": "NSE_EQ",
                                "instrument_type": "EQUITY",
                                "from_date": from_date,
                                "to_date": to_date
                            }
                        }
                    }
                else:
                    results[stock_name] = {
                        "status": "error",
                        "symbol": stock_info["symbol"],
                        "security_id": stock_info["security_id"],
                        "message": error_msg,
                        "error_type": type(e).__name__,
                        "debug_info": {
                            "full_error": error_msg,
                            "parameters": {
                                "security_id": stock_info["security_id"],
                                "exchange_segment": "NSE_EQ",
                                "instrument_type": "EQUITY",
                                "from_date": from_date,
                                "to_date": to_date
                            }
                        }
                    }
            
            # Small delay to avoid rate limits
            time.sleep(0.3)
        
        # Calculate summary statistics
        success_count = sum(1 for r in results.values() if r["status"] == "success")
        total_candles = sum(r.get("candle_count", 0) for r in results.values() if r["status"] == "success")
        
        summary = {
            "total_stocks": len(requested_stocks),
            "successful": success_count,
            "failed": len(requested_stocks) - success_count,
            "total_candles": total_candles,
            "date_range": {"from": from_date, "to": to_date}
        }
        
        return {
            "status": "success",
            "summary": summary,
            "results": results
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch NIFTY 50 stocks data: {str(e)}",
            "error_type": type(e).__name__
        }


@router.post("/demo/live-market-data", tags=["Demo"])
async def demo_get_live_market_data(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch live market data (LTP, volume, OHLC) for NIFTY 50 stocks in batches.
    
    **No authentication required!**
    
    This endpoint fetches real-time market quotes including:
    - Last Traded Price (LTP)
    - Open, High, Low, Close
    - Volume
    - Change percentage
    - Bid/Ask prices
    
    **Request Format:**
    ```json
    {
        "stocks": ["HDFC Bank", "TCS", "Reliance Industries"],
        "batch_size": 10
    }
    ```
    
    **Parameters:**
    - stocks: Optional array of stock names. If not provided, fetches all NIFTY 50 stocks
    - batch_size: Number of stocks to fetch per API call (default: 10, max: 50)
    
    **Returns:** Live market data for requested stocks
    """
    from app.core.config import settings
    import requests
    import asyncio
    
    # NIFTY 50 Stocks
    NIFTY_50_STOCKS = {
        "HDFC Bank": {"security_id": "1333", "symbol": "HDFCBANK"},
        "ICICI Bank": {"security_id": "4963", "symbol": "ICICIBANK"},
        "SBI": {"security_id": "3045", "symbol": "SBIN"},
        "Kotak Mahindra Bank": {"security_id": "1922", "symbol": "KOTAKBANK"},
        "Axis Bank": {"security_id": "5900", "symbol": "AXISBANK"},
        "IndusInd Bank": {"security_id": "5258", "symbol": "INDUSINDBK"},
        "TCS": {"security_id": "11536", "symbol": "TCS"},
        "Infosys": {"security_id": "1594", "symbol": "INFY"},
        "Wipro": {"security_id": "3787", "symbol": "WIPRO"},
        "HCL Technologies": {"security_id": "7229", "symbol": "HCLTECH"},
        "Tech Mahindra": {"security_id": "13538", "symbol": "TECHM"},
        "Reliance Industries": {"security_id": "2885", "symbol": "RELIANCE"},
        "ONGC": {"security_id": "2475", "symbol": "ONGC"},
        "NTPC": {"security_id": "11630", "symbol": "NTPC"},
        "Power Grid": {"security_id": "11631", "symbol": "POWERGRID"},
        "Coal India": {"security_id": "20374", "symbol": "COALINDIA"},
        "Maruti Suzuki": {"security_id": "10999", "symbol": "MARUTI"},
        "Mahindra & Mahindra": {"security_id": "2031", "symbol": "M&M"},
        "Tata Motors": {"security_id": "3456", "symbol": "TATAMOTORS"},
        "Bajaj Auto": {"security_id": "1660", "symbol": "BAJAJ-AUTO"},
        "Hero MotoCorp": {"security_id": "1348", "symbol": "HEROMOTOCO"},
        "Eicher Motors": {"security_id": "910", "symbol": "EICHERMOT"},
        "Hindustan Unilever": {"security_id": "1394", "symbol": "HINDUNILVR"},
        "ITC": {"security_id": "5246", "symbol": "ITC"},
        "Britannia Industries": {"security_id": "547", "symbol": "BRITANNIA"},
        "Nestle India": {"security_id": "17963", "symbol": "NESTLEIND"},
        "Asian Paints": {"security_id": "7406", "symbol": "ASIANPAINT"},
        "Tata Steel": {"security_id": "3499", "symbol": "TATASTEEL"},
        "JSW Steel": {"security_id": "11723", "symbol": "JSWSTEEL"},
        "Hindalco": {"security_id": "1363", "symbol": "HINDALCO"},
        "Sun Pharmaceutical": {"security_id": "3351", "symbol": "SUNPHARMA"},
        "Dr Reddy's Laboratories": {"security_id": "881", "symbol": "DRREDDY"},
        "Cipla": {"security_id": "701", "symbol": "CIPLA"},
        "Divi's Laboratories": {"security_id": "10940", "symbol": "DIVISLAB"},
        "UltraTech Cement": {"security_id": "11532", "symbol": "ULTRACEMCO"},
        "Grasim Industries": {"security_id": "1232", "symbol": "GRASIM"},
        "Larsen & Toubro": {"security_id": "11483", "symbol": "LT"},
        "Bharti Airtel": {"security_id": "10604", "symbol": "BHARTIARTL"},
        "Adani Ports": {"security_id": "15083", "symbol": "ADANIPORTS"},
        "Bajaj Finserv": {"security_id": "16675", "symbol": "BAJAJFINSV"},
        "Bajaj Finance": {"security_id": "16669", "symbol": "BAJFINANCE"},
        "Titan Company": {"security_id": "3506", "symbol": "TITAN"},
        "BPCL": {"security_id": "526", "symbol": "BPCL"},
        "IOC": {"security_id": "1624", "symbol": "IOC"},
        "Shree Cement": {"security_id": "3103", "symbol": "SHREECEM"},
        "Adani Enterprises": {"security_id": "25", "symbol": "ADANIENT"},
        "Apollo Hospitals": {"security_id": "157", "symbol": "APOLLOHOSP"},
        "Tata Consumer": {"security_id": "3432", "symbol": "TATACONSUM"},
    }
    
    try:
        # Check if master credentials are configured
        if not settings.DHAN_MASTER_ACCESS_TOKEN:
            return {
                "status": "error",
                "message": "DHAN master access token not configured in .env file",
                "hint": "Add DHAN_MASTER_ACCESS_TOKEN to your .env"
            }
        
        # Parse request parameters
        requested_stocks = request.get("stocks", list(NIFTY_50_STOCKS.keys()))
        batch_size = min(request.get("batch_size", 10), 50)  # Max 50 per batch
        
        # Validate requested stocks
        invalid_stocks = [stock for stock in requested_stocks if stock not in NIFTY_50_STOCKS]
        if invalid_stocks:
            return {
                "status": "error",
                "message": f"Invalid stocks: {', '.join(invalid_stocks)}",
                "valid_stocks": list(NIFTY_50_STOCKS.keys())
            }
        
        # Prepare headers for API calls
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "access-token": settings.DHAN_MASTER_ACCESS_TOKEN
        }
        
        # Create a mapping of security_id to stock name for later lookup
        security_to_stock = {}
        for stock_name in requested_stocks:
            security_to_stock[NIFTY_50_STOCKS[stock_name]["security_id"]] = stock_name
        
        # Split stocks into batches
        stock_batches = [requested_stocks[i:i + batch_size] for i in range(0, len(requested_stocks), batch_size)]
        
        results = {}
        
        # Fetch data in batches
        for batch_idx, batch in enumerate(stock_batches):
            # Prepare security IDs for this batch
            security_ids = [NIFTY_50_STOCKS[stock]["security_id"] for stock in batch]
            
            # Prepare request payload for market quote API
            payload = {
                "NSE_EQ": security_ids
            }
            
            try:
                # Call DHAN market quote API
                response = requests.post(
                    "https://api.dhan.co/v2/marketfeed/quote",
                    json=payload,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if response is successful
                    if data.get("status") == "success" and "data" in data:
                        quote_data = data["data"]
                        
                        # Process each stock in the batch
                        if isinstance(quote_data, dict):
                            for security_id, stock_data in quote_data.items():
                                stock_name = security_to_stock.get(security_id)
                                if stock_name and isinstance(stock_data, dict):
                                    stock_info = NIFTY_50_STOCKS[stock_name]
                                    
                                    # Extract market data
                                    ltp = stock_data.get("LTP") or stock_data.get("last_price") or 0
                                    prev_close = stock_data.get("prev_close") or stock_data.get("close_price") or 0
                                    
                                    # Calculate change percentage
                                    change_percent = None
                                    change_value = None
                                    if ltp and prev_close and prev_close > 0:
                                        change_value = ltp - prev_close
                                        change_percent = (change_value / prev_close) * 100
                                    
                                    results[stock_name] = {
                                        "status": "success",
                                        "symbol": stock_info["symbol"],
                                        "security_id": stock_info["security_id"],
                                        "ltp": ltp,
                                        "open": stock_data.get("open") or stock_data.get("open_price"),
                                        "high": stock_data.get("high") or stock_data.get("high_price"),
                                        "low": stock_data.get("low") or stock_data.get("low_price"),
                                        "close": stock_data.get("close") or stock_data.get("close_price"),
                                        "prev_close": prev_close,
                                        "volume": stock_data.get("volume") or stock_data.get("traded_volume"),
                                        "change": round(change_value, 2) if change_value else None,
                                        "change_percent": round(change_percent, 2) if change_percent else None,
                                        "bid_price": stock_data.get("bid_price"),
                                        "ask_price": stock_data.get("ask_price"),
                                        "oi": stock_data.get("OI") or stock_data.get("open_interest"),
                                        "last_update_time": stock_data.get("last_update_time") or stock_data.get("timestamp")
                                    }
                    else:
                        # API returned failure status
                        error_info = data.get("remarks", {}) or data.get("data", {})
                        error_msg = "API returned failure status"
                        
                        if isinstance(error_info, dict):
                            error_msg = error_info.get("error_message", error_msg)
                        
                        # Mark all stocks in this batch as failed
                        for stock_name in batch:
                            stock_info = NIFTY_50_STOCKS[stock_name]
                            results[stock_name] = {
                                "status": "error",
                                "symbol": stock_info["symbol"],
                                "security_id": stock_info["security_id"],
                                "message": error_msg,
                                "batch_index": batch_idx
                            }
                else:
                    # HTTP error
                    error_data = response.json() if response.text else {}
                    error_msg = f"HTTP {response.status_code}"
                    
                    if isinstance(error_data, dict):
                        remarks = error_data.get("remarks", {})
                        if isinstance(remarks, dict):
                            error_msg = remarks.get("error_message", error_msg)
                    
                    # Mark all stocks in this batch as failed
                    for stock_name in batch:
                        stock_info = NIFTY_50_STOCKS[stock_name]
                        results[stock_name] = {
                            "status": "error",
                            "symbol": stock_info["symbol"],
                            "security_id": stock_info["security_id"],
                            "message": error_msg,
                            "batch_index": batch_idx
                        }
                        
            except requests.exceptions.Timeout:
                # Timeout error
                for stock_name in batch:
                    stock_info = NIFTY_50_STOCKS[stock_name]
                    results[stock_name] = {
                        "status": "error",
                        "symbol": stock_info["symbol"],
                        "security_id": stock_info["security_id"],
                        "message": "Request timeout",
                        "batch_index": batch_idx
                    }
            except Exception as e:
                # Other errors
                for stock_name in batch:
                    stock_info = NIFTY_50_STOCKS[stock_name]
                    results[stock_name] = {
                        "status": "error",
                        "symbol": stock_info["symbol"],
                        "security_id": stock_info["security_id"],
                        "message": str(e),
                        "error_type": type(e).__name__,
                        "batch_index": batch_idx
                    }
            
            # Small delay between batches to avoid rate limits
            if batch_idx < len(stock_batches) - 1:
                await asyncio.sleep(0.5)
        
        # Calculate summary statistics
        success_count = sum(1 for r in results.values() if r["status"] == "success")
        
        summary = {
            "total_stocks": len(requested_stocks),
            "successful": success_count,
            "failed": len(requested_stocks) - success_count,
            "batches_processed": len(stock_batches),
            "batch_size": batch_size,
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "summary": summary,
            "results": results
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch live market data: {str(e)}",
            "error_type": type(e).__name__
        }
