# """
# Mock live market data endpoint for testing without DHAN credentials.
# This generates realistic-looking sample data for NIFTY 50 stocks.
# """
# from fastapi import APIRouter
# from typing import Dict, Any
# from datetime import datetime
# import random

# router = APIRouter(prefix="/api/v2/dhan", tags=["Mock Demo"])


# @router.post("/demo/mock-live-market-data")
# async def mock_live_market_data(request: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Generate mock live market data for NIFTY 50 stocks.
    
#     **No DHAN credentials required!**
    
#     This endpoint generates realistic sample data for testing purposes.
#     Data is randomly generated and updates on each request.
    
#     **Request Format:**
#     ```json
#     {
#         "stocks": ["HDFC Bank", "TCS", "Reliance Industries"],
#         "batch_size": 10
#     }
#     ```
    
#     **Returns:** Mock live market data with realistic prices and changes
#     """
    
#     # NIFTY 50 Stocks with base prices
#     NIFTY_50_STOCKS = {
#         "HDFC Bank": {"security_id": "1333", "symbol": "HDFCBANK", "base_price": 1650.00},
#         "ICICI Bank": {"security_id": "4963", "symbol": "ICICIBANK", "base_price": 1050.00},
#         "SBI": {"security_id": "3045", "symbol": "SBIN", "base_price": 750.00},
#         "Kotak Mahindra Bank": {"security_id": "1922", "symbol": "KOTAKBANK", "base_price": 1800.00},
#         "Axis Bank": {"security_id": "5900", "symbol": "AXISBANK", "base_price": 1100.00},
#         "IndusInd Bank": {"security_id": "5258", "symbol": "INDUSINDBK", "base_price": 1400.00},
#         "TCS": {"security_id": "11536", "symbol": "TCS", "base_price": 3850.00},
#         "Infosys": {"security_id": "1594", "symbol": "INFY", "base_price": 1750.00},
#         "Wipro": {"security_id": "3787", "symbol": "WIPRO", "base_price": 550.00},
#         "HCL Technologies": {"security_id": "7229", "symbol": "HCLTECH", "base_price": 1450.00},
#         "Tech Mahindra": {"security_id": "13538", "symbol": "TECHM", "base_price": 1650.00},
#         "Reliance Industries": {"security_id": "2885", "symbol": "RELIANCE", "base_price": 2850.00},
#         "ONGC": {"security_id": "2475", "symbol": "ONGC", "base_price": 250.00},
#         "NTPC": {"security_id": "11630", "symbol": "NTPC", "base_price": 350.00},
#         "Power Grid": {"security_id": "11631", "symbol": "POWERGRID", "base_price": 300.00},
#         "Coal India": {"security_id": "20374", "symbol": "COALINDIA", "base_price": 450.00},
#         "Maruti Suzuki": {"security_id": "10999", "symbol": "MARUTI", "base_price": 12500.00},
#         "Mahindra & Mahindra": {"security_id": "2031", "symbol": "M&M", "base_price": 2800.00},
#         "Tata Motors": {"security_id": "3456", "symbol": "TATAMOTORS", "base_price": 950.00},
#         "Bajaj Auto": {"security_id": "1660", "symbol": "BAJAJ-AUTO", "base_price": 9500.00},
#         "Hero MotoCorp": {"security_id": "1348", "symbol": "HEROMOTOCO", "base_price": 4800.00},
#         "Eicher Motors": {"security_id": "910", "symbol": "EICHERMOT", "base_price": 4500.00},
#         "Hindustan Unilever": {"security_id": "1394", "symbol": "HINDUNILVR", "base_price": 2400.00},
#         "ITC": {"security_id": "5246", "symbol": "ITC", "base_price": 450.00},
#         "Britannia Industries": {"security_id": "547", "symbol": "BRITANNIA", "base_price": 5200.00},
#         "Nestle India": {"security_id": "17963", "symbol": "NESTLEIND", "base_price": 2400.00},
#         "Asian Paints": {"security_id": "7406", "symbol": "ASIANPAINT", "base_price": 2900.00},
#         "Tata Steel": {"security_id": "3499", "symbol": "TATASTEEL", "base_price": 140.00},
#         "JSW Steel": {"security_id": "11723", "symbol": "JSWSTEEL", "base_price": 900.00},
#         "Hindalco": {"security_id": "1363", "symbol": "HINDALCO", "base_price": 650.00},
#         "Sun Pharmaceutical": {"security_id": "3351", "symbol": "SUNPHARMA", "base_price": 1750.00},
#         "Dr Reddy's Laboratories": {"security_id": "881", "symbol": "DRREDDY", "base_price": 6200.00},
#         "Cipla": {"security_id": "701", "symbol": "CIPLA", "base_price": 1450.00},
#         "Divi's Laboratories": {"security_id": "10940", "symbol": "DIVISLAB", "base_price": 5800.00},
#         "UltraTech Cement": {"security_id": "11532", "symbol": "ULTRACEMCO", "base_price": 10500.00},
#         "Grasim Industries": {"security_id": "1232", "symbol": "GRASIM", "base_price": 2400.00},
#         "Larsen & Toubro": {"security_id": "11483", "symbol": "LT", "base_price": 3600.00},
#         "Bharti Airtel": {"security_id": "10604", "symbol": "BHARTIARTL", "base_price": 1550.00},
#         "Adani Ports": {"security_id": "15083", "symbol": "ADANIPORTS", "base_price": 1250.00},
#         "Bajaj Finserv": {"security_id": "16675", "symbol": "BAJAJFINSV", "base_price": 1650.00},
#         "Bajaj Finance": {"security_id": "16669", "symbol": "BAJFINANCE", "base_price": 7000.00},
#         "Titan Company": {"security_id": "3506", "symbol": "TITAN", "base_price": 3400.00},
#         "BPCL": {"security_id": "526", "symbol": "BPCL", "base_price": 300.00},
#         "IOC": {"security_id": "1624", "symbol": "IOC", "base_price": 140.00},
#         "Shree Cement": {"security_id": "3103", "symbol": "SHREECEM", "base_price": 26000.00},
#         "Adani Enterprises": {"security_id": "25", "symbol": "ADANIENT", "base_price": 2800.00},
#         "Apollo Hospitals": {"security_id": "157", "symbol": "APOLLOHOSP", "base_price": 6500.00},
#         "Tata Consumer": {"security_id": "3432", "symbol": "TATACONSUM", "base_price": 1050.00},
#     }
    
#     # Parse request parameters
#     requested_stocks = request.get("stocks", list(NIFTY_50_STOCKS.keys()))
#     batch_size = min(request.get("batch_size", 10), 50)
    
#     # Validate requested stocks
#     invalid_stocks = [stock for stock in requested_stocks if stock not in NIFTY_50_STOCKS]
#     if invalid_stocks:
#         return {
#             "status": "error",
#             "message": f"Invalid stocks: {', '.join(invalid_stocks)}",
#             "valid_stocks": list(NIFTY_50_STOCKS.keys())
#         }
    
#     # Generate mock data for each stock
#     results = {}
    
#     for stock_name in requested_stocks:
#         stock_info = NIFTY_50_STOCKS[stock_name]
#         base_price = stock_info["base_price"]
        
#         # Generate realistic price variations
#         price_change_percent = random.uniform(-3.0, 3.0)  # -3% to +3%
#         # price_change = base_price * (price_change_percent / 100)
        
#         prev_close = base_price
#         ltp = round(base_price + price_change, 2)
        
#         # Generate OHLC data
#         open_price = round(prev_close + random.uniform(-10, 10), 2)
#         high_price = round(max(open_price, ltp) + random.uniform(0, 20), 2)
#         low_price = round(min(open_price, ltp) - random.uniform(0, 20), 2)
        
#         # Generate volume (in lakhs)
#         volume = random.randint(100000, 10000000)
        
#         # Calculate change
#         change = round(ltp - prev_close, 2)
#         change_percent = round((change / prev_close) * 100, 2)
        
#         # Generate bid/ask
#         bid_price = round(ltp - random.uniform(0.5, 2.0), 2)
#         ask_price = round(ltp + random.uniform(0.5, 2.0), 2)
        
#         results[stock_name] = {
#             "status": "success",
#             "symbol": stock_info["symbol"],
#             "security_id": stock_info["security_id"],
#             "ltp": ltp,
#             "open": open_price,
#             "high": high_price,
#             "low": low_price,
#             "close": ltp,
#             "prev_close": prev_close,
#             "volume": volume,
#             "change": change,
#             "change_percent": change_percent,
#             "bid_price": bid_price,
#             "ask_price": ask_price,
#             "oi": None,
#             "last_update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         }
    
#     # Calculate summary
#     success_count = len(results)
    
#     summary = {
#         "total_stocks": len(requested_stocks),
#         "successful": success_count,
#         "failed": 0,
#         "batches_processed": (len(requested_stocks) + batch_size - 1) // batch_size,
#         "batch_size": batch_size,
#         "timestamp": datetime.now().isoformat(),
#         "note": "⚠️ This is MOCK DATA for testing. Not real market data!"
#     }
    
#     return {
#         "status": "success",
#         "summary": summary,
#         "results": results
#     }
