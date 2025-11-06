"""
Test script to fetch live market data for NIFTY 50 stocks.

This script demonstrates how to use the /demo/live-market-data endpoint
to fetch real-time market quotes.

Usage:
    python test_live_market.py
"""
import requests
import json
from datetime import datetime


def fetch_live_market_data(stocks=None, batch_size=10):
    """
    Fetch live market data from the API.
    
    Args:
        stocks: List of stock names (optional). If None, fetches all NIFTY 50 stocks.
        batch_size: Number of stocks to fetch per API call (default: 10, max: 50)
    
    Returns:
        dict: API response with live market data
    """
    url = "http://localhost:8000/api/v2/dhan/demo/live-market-data"
    
    payload = {
        "batch_size": batch_size
    }
    
    if stocks:
        payload["stocks"] = stocks
    
    try:
        print(f"\n🔍 Fetching live market data...")
        print(f"   Batch size: {batch_size}")
        if stocks:
            print(f"   Stocks: {len(stocks)} selected")
        else:
            print(f"   Stocks: All NIFTY 50")
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"\n❌ Error: HTTP {response.status_code}")
            print(response.text)
            return None
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to the server.")
        print("   Make sure the FastAPI server is running on http://localhost:8000")
        return None
    except requests.exceptions.Timeout:
        print("\n❌ Error: Request timed out")
        return None
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return None


def display_results(data):
    """Display the results in a formatted way."""
    if not data:
        return
    
    print("\n" + "="*100)
    print("LIVE MARKET DATA - NIFTY 50 STOCKS")
    print("="*100)
    
    # Display summary
    summary = data.get("summary", {})
    print(f"\n📊 Summary:")
    print(f"   Total stocks: {summary.get('total_stocks', 0)}")
    print(f"   Successful: {summary.get('successful', 0)}")
    print(f"   Failed: {summary.get('failed', 0)}")
    print(f"   Batches processed: {summary.get('batches_processed', 0)}")
    print(f"   Timestamp: {summary.get('timestamp', 'N/A')}")
    
    # Display stock data
    results = data.get("results", {})
    
    if not results:
        print("\n⚠️  No stock data available")
        return
    
    # Separate successful and failed stocks
    successful_stocks = {k: v for k, v in results.items() if v.get("status") == "success"}
    failed_stocks = {k: v for k, v in results.items() if v.get("status") == "error"}
    
    # Display successful stocks
    if successful_stocks:
        print("\n" + "-"*100)
        print("✅ SUCCESSFUL STOCKS")
        print("-"*100)
        print(f"{'Stock Name':<25} {'Symbol':<12} {'LTP':<10} {'Change':<10} {'Change %':<10} {'Volume':<15}")
        print("-"*100)
        
        # Sort by change percentage (descending)
        sorted_stocks = sorted(
            successful_stocks.items(),
            key=lambda x: x[1].get("change_percent", 0) or 0,
            reverse=True
        )
        
        for stock_name, stock_data in sorted_stocks:
            ltp = stock_data.get("ltp", 0)
            change = stock_data.get("change", 0)
            change_percent = stock_data.get("change_percent", 0)
            volume = stock_data.get("volume", 0)
            symbol = stock_data.get("symbol", "N/A")
            
            # Color code based on change
            change_indicator = "🟢" if change and change > 0 else "🔴" if change and change < 0 else "⚪"
            
            print(f"{stock_name:<25} {symbol:<12} {ltp:<10.2f} {change_indicator} {change:<8.2f} {change_percent:<9.2f}% {volume:<15,}")
    
    # Display failed stocks
    if failed_stocks:
        print("\n" + "-"*100)
        print("❌ FAILED STOCKS")
        print("-"*100)
        print(f"{'Stock Name':<25} {'Symbol':<12} {'Security ID':<12} {'Error Message':<40}")
        print("-"*100)
        
        for stock_name, stock_data in failed_stocks.items():
            symbol = stock_data.get("symbol", "N/A")
            security_id = stock_data.get("security_id", "N/A")
            message = stock_data.get("message", "Unknown error")
            
            print(f"{stock_name:<25} {symbol:<12} {security_id:<12} {message:<40}")
    
    print("\n" + "="*100 + "\n")


def main():
    """Main function."""
    print("\n" + "="*100)
    print("NIFTY 50 LIVE MARKET DATA FETCHER")
    print("="*100)
    
    print("\nOptions:")
    print("1. Fetch all NIFTY 50 stocks (batch size: 10)")
    print("2. Fetch all NIFTY 50 stocks (batch size: 25)")
    print("3. Fetch selected stocks (top 10)")
    print("4. Custom selection")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == "1":
        data = fetch_live_market_data(batch_size=10)
        display_results(data)
    
    elif choice == "2":
        data = fetch_live_market_data(batch_size=25)
        display_results(data)
    
    elif choice == "3":
        # Top 10 stocks by market cap
        top_stocks = [
            "Reliance Industries",
            "TCS",
            "HDFC Bank",
            "Infosys",
            "ICICI Bank",
            "Bharti Airtel",
            "SBI",
            "Hindustan Unilever",
            "ITC",
            "Larsen & Toubro"
        ]
        data = fetch_live_market_data(stocks=top_stocks, batch_size=10)
        display_results(data)
    
    elif choice == "4":
        print("\nEnter stock names separated by commas:")
        print("Example: HDFC Bank, TCS, Reliance Industries")
        stock_input = input("\nStocks: ").strip()
        
        if stock_input:
            stocks = [s.strip() for s in stock_input.split(",")]
            batch_size = int(input("Batch size (1-50, default 10): ").strip() or "10")
            batch_size = min(max(batch_size, 1), 50)
            
            data = fetch_live_market_data(stocks=stocks, batch_size=batch_size)
            display_results(data)
        else:
            print("\n❌ No stocks entered!")
    
    else:
        print("\n❌ Invalid choice!")
    
    print("\n✨ Done!")


if __name__ == "__main__":
    main()
