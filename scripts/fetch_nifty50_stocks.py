"""
Fetch Historical Data for NIFTY 50 Stocks
Fetches daily OHLCV data for all NIFTY 50 constituent stocks

This script uses DHAN API to fetch historical data for NIFTY 50 stocks.
Results are saved to a JSON file and can be used for analysis, backtesting, etc.

Usage:
    python scripts/fetch_nifty50_stocks.py
"""
import os
from dhanhq import dhanhq
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
from typing import Dict, Any, List
import time

# Load environment variables
load_dotenv()

# NIFTY 50 Stocks with Security IDs (as of Nov 2024)
NIFTY_50_STOCKS = {
    # Banking & Financial Services
    "HDFC Bank": {"security_id": "1333", "symbol": "HDFCBANK"},
    "ICICI Bank": {"security_id": "4963", "symbol": "ICICIBANK"},
    "SBI": {"security_id": "3045", "symbol": "SBIN"},
    "Kotak Mahindra Bank": {"security_id": "1922", "symbol": "KOTAKBANK"},
    "Axis Bank": {"security_id": "5900", "symbol": "AXISBANK"},
    "IndusInd Bank": {"security_id": "5258", "symbol": "INDUSINDBK"},
    
    # IT & Technology
    "TCS": {"security_id": "11536", "symbol": "TCS"},
    "Infosys": {"security_id": "1594", "symbol": "INFY"},
    "Wipro": {"security_id": "3787", "symbol": "WIPRO"},
    "HCL Technologies": {"security_id": "7229", "symbol": "HCLTECH"},
    "Tech Mahindra": {"security_id": "13538", "symbol": "TECHM"},
    
    # Energy & Oil & Gas
    "Reliance Industries": {"security_id": "2885", "symbol": "RELIANCE"},
    "ONGC": {"security_id": "2475", "symbol": "ONGC"},
    "NTPC": {"security_id": "11630", "symbol": "NTPC"},
    "Power Grid": {"security_id": "11631", "symbol": "POWERGRID"},
    "Coal India": {"security_id": "20374", "symbol": "COALINDIA"},
    
    # Automobile
    "Maruti Suzuki": {"security_id": "10999", "symbol": "MARUTI"},
    "Mahindra & Mahindra": {"security_id": "2031", "symbol": "M&M"},
    "Tata Motors": {"security_id": "3456", "symbol": "TATAMOTORS"},
    "Bajaj Auto": {"security_id": "1660", "symbol": "BAJAJ-AUTO"},
    "Hero MotoCorp": {"security_id": "1348", "symbol": "HEROMOTOCO"},
    "Eicher Motors": {"security_id": "910", "symbol": "EICHERMOT"},
    
    # FMCG & Consumer Goods
    "Hindustan Unilever": {"security_id": "1394", "symbol": "HINDUNILVR"},
    "ITC": {"security_id": "1660", "symbol": "ITC"},
    "Britannia Industries": {"security_id": "547", "symbol": "BRITANNIA"},
    "Nestle India": {"security_id": "1232", "symbol": "NESTLEIND"},
    "Asian Paints": {"security_id": "7406", "symbol": "ASIANPAINT"},
    
    # Metals & Mining
    "Tata Steel": {"security_id": "3499", "symbol": "TATASTEEL"},
    "JSW Steel": {"security_id": "11723", "symbol": "JSWSTEEL"},
    "Hindalco": {"security_id": "1363", "symbol": "HINDALCO"},
    
    # Pharmaceuticals
    "Sun Pharmaceutical": {"security_id": "3351", "symbol": "SUNPHARMA"},
    "Dr Reddy's Laboratories": {"security_id": "881", "symbol": "DRREDDY"},
    "Cipla": {"security_id": "701", "symbol": "CIPLA"},
    "Divi's Laboratories": {"security_id": "10940", "symbol": "DIVISLAB"},
    
    # Cement & Construction
    "UltraTech Cement": {"security_id": "11532", "symbol": "ULTRACEMCO"},
    "Grasim Industries": {"security_id": "1232", "symbol": "GRASIM"},
    "Larsen & Toubro": {"security_id": "11483", "symbol": "LT"},
    
    # Telecom
    "Bharti Airtel": {"security_id": "10604", "symbol": "BHARTIARTL"},
    
    # Others
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
    "Bharat Electronics": {"security_id": "383", "symbol": "BEL"},
    "InterGlobe Aviation": {"security_id": "18652", "symbol": "INDIGO"}
}


def print_separator(char="=", length=100):
    """Print a separator line."""
    print(char * length)


def fetch_stock_data(
    dhan: dhanhq,
    stock_name: str,
    security_id: str,
    symbol: str,
    from_date: str,
    to_date: str
) -> Dict[str, Any]:
    """
    Fetch historical data for a single stock.
    
    Args:
        dhan: DHAN client instance
        stock_name: Name of the stock
        security_id: Security ID
        symbol: Stock symbol
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        
    Returns:
        Dict containing the stock data
    """
    try:
        print(f"  📡 Fetching {stock_name} ({symbol})...")
        
        response = dhan.historical_daily_data(
            security_id=security_id,
            exchange_segment="NSE_EQ",
            instrument_type="EQUITY",
            from_date=from_date,
            to_date=to_date
        )
        
        # Check if data is available
        if isinstance(response, dict) and 'data' in response:
            data = response['data']
            if 'open' in data and len(data['open']) > 0:
                candle_count = len(data['open'])
                print(f"  ✅ {stock_name}: {candle_count} candles fetched")
                return {
                    "status": "success",
                    "stock_name": stock_name,
                    "symbol": symbol,
                    "security_id": security_id,
                    "candle_count": candle_count,
                    "data": data
                }
            else:
                print(f"  ⚠️  {stock_name}: No data available")
                return {
                    "status": "no_data",
                    "stock_name": stock_name,
                    "symbol": symbol,
                    "security_id": security_id,
                    "message": "No data available for the specified date range"
                }
        else:
            print(f"  ❌ {stock_name}: Unexpected response format")
            return {
                "status": "error",
                "stock_name": stock_name,
                "symbol": symbol,
                "security_id": security_id,
                "message": "Unexpected response format",
                "response": response
            }
            
    except Exception as e:
        print(f"  ❌ {stock_name}: Error - {str(e)}")
        return {
            "status": "error",
            "stock_name": stock_name,
            "symbol": symbol,
            "security_id": security_id,
            "message": str(e),
            "error_type": type(e).__name__
        }


def fetch_all_nifty50_stocks(
    dhan: dhanhq,
    from_date: str,
    to_date: str,
    delay_seconds: float = 0.5
) -> Dict[str, Any]:
    """
    Fetch historical data for all NIFTY 50 stocks.
    
    Args:
        dhan: DHAN client instance
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        delay_seconds: Delay between requests to avoid rate limits
        
    Returns:
        Dict containing all stock data
    """
    results = {}
    total_stocks = len(NIFTY_50_STOCKS)
    
    print(f"\n{'='*80}")
    print(f"📊 Fetching data for {total_stocks} NIFTY 50 stocks")
    print(f"{'='*80}\n")
    
    for idx, (stock_name, stock_info) in enumerate(NIFTY_50_STOCKS.items(), 1):
        print(f"[{idx}/{total_stocks}] ", end="")
        
        result = fetch_stock_data(
            dhan=dhan,
            stock_name=stock_name,
            security_id=stock_info["security_id"],
            symbol=stock_info["symbol"],
            from_date=from_date,
            to_date=to_date
        )
        
        results[stock_name] = result
        
        # Add delay to avoid rate limits (except for last request)
        if idx < total_stocks:
            time.sleep(delay_seconds)
    
    return results


def display_summary(results: Dict[str, Any], from_date: str, to_date: str):
    """Display a summary of fetched data."""
    print("\n")
    print_separator("=")
    print("📈 FETCH SUMMARY")
    print_separator("=")
    
    success_count = 0
    no_data_count = 0
    error_count = 0
    total_candles = 0
    
    successful_stocks = []
    failed_stocks = []
    
    for stock_name, result in results.items():
        if result["status"] == "success":
            success_count += 1
            total_candles += result["candle_count"]
            successful_stocks.append(f"{stock_name} ({result['candle_count']} candles)")
        elif result["status"] == "no_data":
            no_data_count += 1
            failed_stocks.append(f"{stock_name} (No data)")
        else:
            error_count += 1
            failed_stocks.append(f"{stock_name} (Error: {result.get('message', 'Unknown')})")
    
    print(f"\n📊 Overall Statistics:")
    print(f"  Total Stocks: {len(results)}")
    print(f"  ✅ Successful: {success_count}")
    print(f"  ⚠️  No Data: {no_data_count}")
    print(f"  ❌ Errors: {error_count}")
    print(f"  📈 Total Candles: {total_candles:,}")
    print(f"  📅 Date Range: {from_date} to {to_date}")
    
    if successful_stocks:
        print(f"\n✅ Successfully Fetched ({success_count} stocks):")
        for stock in successful_stocks[:10]:  # Show first 10
            print(f"  • {stock}")
        if len(successful_stocks) > 10:
            print(f"  ... and {len(successful_stocks) - 10} more")
    
    if failed_stocks:
        print(f"\n❌ Failed/No Data ({len(failed_stocks)} stocks):")
        for stock in failed_stocks:
            print(f"  • {stock}")


def save_results_to_file(results: Dict[str, Any], from_date: str, to_date: str, filename: str = None):
    """Save results to a JSON file."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nifty50_stocks_{from_date}_to_{to_date}_{timestamp}.json"
    
    # Create data directory if it doesn't exist
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    
    filepath = os.path.join(data_dir, filename)
    
    # Prepare data for saving
    save_data = {
        "metadata": {
            "fetch_date": datetime.now().isoformat(),
            "from_date": from_date,
            "to_date": to_date,
            "total_stocks": len(results),
            "index": "NIFTY 50"
        },
        "stocks": results
    }
    
    with open(filepath, "w") as f:
        json.dump(save_data, f, indent=2)
    
    print(f"\n💾 Results saved to: {filepath}")
    return filepath


def main():
    """Main function to fetch NIFTY 50 stocks data."""
    print("\n")
    print_separator("=")
    print("🚀 FETCHING NIFTY 50 STOCKS HISTORICAL DATA")
    print_separator("=")
    
    # Get credentials from environment
    client_id = os.getenv("DHAN_MASTER_CLIENT_ID")
    access_token = os.getenv("DHAN_MASTER_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        print("\n❌ ERROR: DHAN credentials not found!")
        print("Please set DHAN_MASTER_CLIENT_ID and DHAN_MASTER_ACCESS_TOKEN in your .env file")
        print("\nHow to get credentials:")
        print("1. Login to https://www.dhan.co")
        print("2. Go to Settings → API")
        print("3. Generate Access Token")
        print("4. Copy Client ID and Access Token to .env file")
        return
    
    # Calculate date range (last 90 days by default)
    to_date = datetime.now()
    from_date = to_date - timedelta(days=90)
    
    from_date_str = from_date.strftime("%Y-%m-%d")
    to_date_str = to_date.strftime("%Y-%m-%d")
    
    print(f"\n📅 Date Range: {from_date_str} to {to_date_str}")
    print(f"📊 Total Stocks: {len(NIFTY_50_STOCKS)}")
    print(f"🏢 Exchange: NSE_EQ")
    print(f"📈 Instrument Type: EQUITY")
    
    try:
        # Initialize DHAN client
        print(f"\n📡 Initializing DHAN client...")
        dhan = dhanhq(client_id, access_token)
        print("✅ Client initialized successfully!")
        
        # Fetch data for all stocks
        results = fetch_all_nifty50_stocks(
            dhan=dhan,
            from_date=from_date_str,
            to_date=to_date_str,
            delay_seconds=0.5  # 500ms delay between requests
        )
        
        # Display summary
        display_summary(results, from_date_str, to_date_str)
        
        # Save to file
        save_results_to_file(results, from_date_str, to_date_str)
        
        print("\n")
        print_separator("=")
        print("✨ COMPLETED! All NIFTY 50 stocks data fetched successfully.")
        print_separator("=")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
