"""
Fetch 1-Minute Intraday Data for NIFTY 50 Stocks
Fetches 1-minute candle OHLCV data for all NIFTY 50 constituent stocks

This script handles DHAN API's 90-day limit by automatically batching requests
for custom date ranges (including 5 years of historical data).

Usage:
    # Fetch last 5 years
    python scripts/fetch_nifty50_intraday.py --years 5
    
    # Fetch custom date range
    python scripts/fetch_nifty50_intraday.py --from 2023-01-01 --to 2024-01-01
    
    # Fetch specific stocks only
    python scripts/fetch_nifty50_intraday.py --stocks "HDFC Bank,TCS,Reliance Industries"
"""
import os
from dhanhq import dhanhq
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
from typing import Dict, Any, List
import time
import argparse

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
    "ITC": {"security_id": "5246", "symbol": "ITC"},
    "Britannia Industries": {"security_id": "547", "symbol": "BRITANNIA"},
    "Nestle India": {"security_id": "17963", "symbol": "NESTLEIND"},
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


def generate_date_batches(from_date: datetime, to_date: datetime, max_days: int = 89) -> List[tuple]:
    """
    Generate date batches respecting DHAN's 90-day limit for intraday data.
    
    Args:
        from_date: Start date
        to_date: End date
        max_days: Maximum days per batch (default 89 to stay under 90-day limit)
        
    Returns:
        List of (from_date, to_date) tuples
    """
    batches = []
    current_start = from_date
    
    while current_start < to_date:
        current_end = min(current_start + timedelta(days=max_days), to_date)
        batches.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    
    return batches


def merge_candle_data(batches_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge multiple batches of candle data into a single dataset.
    
    Args:
        batches_data: List of data dictionaries from different batches
        
    Returns:
        Merged data dictionary
    """
    if not batches_data:
        return {}
    
    if len(batches_data) == 1:
        return batches_data[0]
    
    # Initialize merged data with first batch
    merged = {
        "timestamp": [],
        "open": [],
        "high": [],
        "low": [],
        "close": [],
        "volume": []
    }
    
    # Merge all batches
    for batch_data in batches_data:
        if isinstance(batch_data, dict):
            for key in ["timestamp", "open", "high", "low", "close", "volume"]:
                if key in batch_data and isinstance(batch_data[key], list):
                    merged[key].extend(batch_data[key])
    
    return merged


def fetch_stock_intraday_batched(
    dhan: dhanhq,
    stock_name: str,
    security_id: str,
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    delay_between_batches: float = 1.0
) -> Dict[str, Any]:
    """
    Fetch 1-minute intraday data for a stock with automatic batching.
    
    Args:
        dhan: DHAN client instance
        stock_name: Name of the stock
        security_id: Security ID
        symbol: Stock symbol
        from_date: Start date
        to_date: End date
        delay_between_batches: Delay between batch requests (seconds)
        
    Returns:
        Dict containing the merged stock data
    """
    try:
        # Generate date batches (89 days each to stay under 90-day limit)
        batches = generate_date_batches(from_date, to_date, max_days=89)
        total_batches = len(batches)
        
        print(f"  📡 Fetching {stock_name} ({symbol}) - {total_batches} batch(es)...")
        
        all_batch_data = []
        successful_batches = 0
        
        for batch_idx, (batch_start, batch_end) in enumerate(batches, 1):
            try:
                # Format dates for DHAN API (with time)
                from_date_str = batch_start.strftime("%Y-%m-%d 09:15:00")
                to_date_str = batch_end.strftime("%Y-%m-%d 15:30:00")
                
                print(f"    Batch {batch_idx}/{total_batches}: {batch_start.date()} to {batch_end.date()}", end="")
                
                response = dhan.intraday_minute_data(
                    security_id=security_id,
                    exchange_segment="NSE_EQ",
                    instrument_type="EQUITY",
                    from_date=from_date_str,
                    to_date=to_date_str
                )
                
                # Check if data is available
                if isinstance(response, dict) and 'data' in response:
                    data = response['data']
                    if 'open' in data and len(data['open']) > 0:
                        candle_count = len(data['open'])
                        
                        # Extract timestamps from DHAN API response
                        # DHAN API returns 'start_time' field with Unix timestamps
                        if 'start_time' in data and isinstance(data['start_time'], list):
                            data['timestamp'] = data['start_time']
                        else:
                            # Fallback: generate timestamps if not provided by API
                            data['timestamp'] = [None] * candle_count
                        
                        print(f" ✅ {candle_count} candles")
                        all_batch_data.append(data)
                        successful_batches += 1
                    else:
                        print(f" ⚠️ No data")
                else:
                    print(f" ❌ Invalid response")
                
                # Delay between batches (except last one)
                if batch_idx < total_batches:
                    time.sleep(delay_between_batches)
                    
            except Exception as batch_error:
                print(f" ❌ Error: {str(batch_error)[:50]}")
                continue
        
        # Merge all batches
        if all_batch_data:
            merged_data = merge_candle_data(all_batch_data)
            total_candles = len(merged_data.get('open', []))
            
            print(f"  ✅ {stock_name}: {total_candles:,} total candles from {successful_batches}/{total_batches} batches")
            
            return {
                "status": "success",
                "stock_name": stock_name,
                "symbol": symbol,
                "security_id": security_id,
                "candle_count": total_candles,
                "batches_fetched": successful_batches,
                "total_batches": total_batches,
                "data": merged_data
            }
        else:
            print(f"  ⚠️ {stock_name}: No data available for any batch")
            return {
                "status": "no_data",
                "stock_name": stock_name,
                "symbol": symbol,
                "security_id": security_id,
                "message": "No data available for the specified date range"
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


def fetch_all_nifty50_intraday(
    dhan: dhanhq,
    from_date: datetime,
    to_date: datetime,
    selected_stocks: List[str] = None,
    delay_between_stocks: float = 2.0,
    delay_between_batches: float = 1.0
) -> Dict[str, Any]:
    """
    Fetch 1-minute intraday data for all (or selected) NIFTY 50 stocks.
    
    Args:
        dhan: DHAN client instance
        from_date: Start date
        to_date: End date
        selected_stocks: List of stock names to fetch (None = all)
        delay_between_stocks: Delay between different stocks (seconds)
        delay_between_batches: Delay between batches for same stock (seconds)
        
    Returns:
        Dict containing all stock data
    """
    # Filter stocks if specific ones are requested
    if selected_stocks:
        stocks_to_fetch = {k: v for k, v in NIFTY_50_STOCKS.items() if k in selected_stocks}
    else:
        stocks_to_fetch = NIFTY_50_STOCKS
    
    results = {}
    total_stocks = len(stocks_to_fetch)
    
    print(f"\n{'='*100}")
    print(f"📊 Fetching 1-MINUTE INTRADAY data for {total_stocks} NIFTY 50 stocks")
    print(f"📅 Date Range: {from_date.date()} to {to_date.date()}")
    print(f"{'='*100}\n")
    
    for idx, (stock_name, stock_info) in enumerate(stocks_to_fetch.items(), 1):
        print(f"[{idx}/{total_stocks}] ", end="")
        
        result = fetch_stock_intraday_batched(
            dhan=dhan,
            stock_name=stock_name,
            security_id=stock_info["security_id"],
            symbol=stock_info["symbol"],
            from_date=from_date,
            to_date=to_date,
            delay_between_batches=delay_between_batches
        )
        
        results[stock_name] = result
        
        # Add delay between stocks (except for last one)
        if idx < total_stocks:
            time.sleep(delay_between_stocks)
    
    return results


def display_summary(results: Dict[str, Any], from_date: datetime, to_date: datetime):
    """Display a summary of fetched data."""
    print("\n")
    print("="*100)
    print("📈 FETCH SUMMARY")
    print("="*100)
    
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
            successful_stocks.append(
                f"{stock_name} ({result['candle_count']:,} candles, "
                f"{result['batches_fetched']}/{result['total_batches']} batches)"
            )
        elif result["status"] == "no_data":
            no_data_count += 1
            failed_stocks.append(f"{stock_name} (No data)")
        else:
            error_count += 1
            failed_stocks.append(f"{stock_name} (Error: {result.get('message', 'Unknown')[:50]})")
    
    print(f"\n📊 Overall Statistics:")
    print(f"  Total Stocks: {len(results)}")
    print(f"  ✅ Successful: {success_count}")
    print(f"  ⚠️  No Data: {no_data_count}")
    print(f"  ❌ Errors: {error_count}")
    print(f"  📈 Total Candles: {total_candles:,}")
    print(f"  📅 Date Range: {from_date.date()} to {to_date.date()}")
    print(f"  ⏱️  Interval: 1 minute")
    
    if successful_stocks:
        print(f"\n✅ Successfully Fetched ({success_count} stocks):")
        for stock in successful_stocks[:15]:  # Show first 15
            print(f"  • {stock}")
        if len(successful_stocks) > 15:
            print(f"  ... and {len(successful_stocks) - 15} more")
    
    if failed_stocks:
        print(f"\n❌ Failed/No Data ({len(failed_stocks)} stocks):")
        for stock in failed_stocks:
            print(f"  • {stock}")


def save_results_to_json(results: Dict[str, Any], from_date: datetime, to_date: datetime, filename: str = None):
    """Save results to a JSON file."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        from_str = from_date.strftime("%Y%m%d")
        to_str = to_date.strftime("%Y%m%d")
        filename = f"nifty50_intraday_1min_{from_str}_to_{to_str}_{timestamp}.json"
    
    # Create data directory if it doesn't exist
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    
    filepath = os.path.join(data_dir, filename)
    
    # Prepare data for saving
    save_data = {
        "metadata": {
            "fetch_timestamp": datetime.now().isoformat(),
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "total_stocks": len(results),
            "index": "NIFTY 50",
            "interval": "1 minute",
            "exchange": "NSE_EQ",
            "instrument_type": "EQUITY"
        },
        "stocks": results
    }
    
    with open(filepath, "w") as f:
        json.dump(save_data, f, indent=2)
    
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"\n💾 Results saved to: {filepath}")
    print(f"📦 File size: {file_size_mb:.2f} MB")
    return filepath


def main():
    """Main function to fetch NIFTY 50 intraday data."""
    parser = argparse.ArgumentParser(description="Fetch 1-minute intraday data for NIFTY 50 stocks")
    parser.add_argument("--years", type=int, help="Fetch data for last N years (e.g., --years 5)")
    parser.add_argument("--from", dest="from_date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--stocks", type=str, help="Comma-separated stock names (e.g., 'HDFC Bank,TCS')")
    parser.add_argument("--output", type=str, help="Output filename")
    
    args = parser.parse_args()
    
    print("\n")
    print("="*100)
    print("🚀 FETCHING NIFTY 50 STOCKS 1-MINUTE INTRADAY DATA")
    print("="*100)
    
    # Get credentials from environment
    client_id = os.getenv("DHAN_MASTER_CLIENT_ID")
    access_token = os.getenv("DHAN_MASTER_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        print("\n❌ ERROR: DHAN credentials not found!")
        print("Please set DHAN_MASTER_CLIENT_ID and DHAN_MASTER_ACCESS_TOKEN in your .env file")
        print("\nHow to get credentials:")
        print("1. Login to https://api.dhan.co (LIVE portal)")
        print("2. Generate Access Token")
        print("3. Copy Client ID and Access Token to .env file")
        return
    
    # Determine date range
    to_date = datetime.now()
    
    if args.from_date and args.to_date:
        # Custom date range
        from_date = datetime.strptime(args.from_date, "%Y-%m-%d")
        to_date = datetime.strptime(args.to_date, "%Y-%m-%d")
    elif args.years:
        # Last N years
        from_date = to_date - timedelta(days=args.years * 365)
    else:
        # Default: last 90 days
        from_date = to_date - timedelta(days=90)
    
    # Parse selected stocks if provided
    selected_stocks = None
    if args.stocks:
        selected_stocks = [s.strip() for s in args.stocks.split(",")]
        print(f"\n📋 Selected Stocks: {', '.join(selected_stocks)}")
    
    print(f"\n📅 Date Range: {from_date.date()} to {to_date.date()}")
    print(f"📊 Total Days: {(to_date - from_date).days}")
    print(f"🏢 Exchange: NSE_EQ")
    print(f"📈 Instrument Type: EQUITY")
    print(f"⏱️  Interval: 1 minute")
    
    # Calculate estimated batches
    total_days = (to_date - from_date).days
    estimated_batches_per_stock = (total_days // 89) + 1
    total_stocks = len(selected_stocks) if selected_stocks else len(NIFTY_50_STOCKS)
    estimated_total_batches = estimated_batches_per_stock * total_stocks
    
    print(f"\n⚙️  Estimated batches per stock: {estimated_batches_per_stock}")
    print(f"⚙️  Estimated total API calls: {estimated_total_batches}")
    print(f"⏳ Estimated time: ~{estimated_total_batches * 1.5 / 60:.1f} minutes")
    
    try:
        # Initialize DHAN client
        print(f"\n📡 Initializing DHAN client...")
        dhan = dhanhq(client_id, access_token)
        print("✅ Client initialized successfully!")
        
        # Fetch data for all stocks
        results = fetch_all_nifty50_intraday(
            dhan=dhan,
            from_date=from_date,
            to_date=to_date,
            selected_stocks=selected_stocks,
            delay_between_stocks=2.0,  # 2 seconds between stocks
            delay_between_batches=1.0   # 1 second between batches
        )
        
        # Display summary
        display_summary(results, from_date, to_date)
        
        # Save to file
        save_results_to_json(results, from_date, to_date, filename=args.output)
        
        print("\n")
        print("="*100)
        print("✨ COMPLETED! All NIFTY 50 intraday data fetched successfully.")
        print("="*100)
        print("\n")
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
