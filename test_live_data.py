"""
Test script to fetch live market data for NIFTY 50 stocks.
"""
import requests
import json
from datetime import datetime

# API endpoint
BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/v2/dhan/demo/live-market-data"

def fetch_live_data(stocks=None):
    """
    Fetch live market data for specified stocks or all NIFTY 50 stocks.
    
    Args:
        stocks (list): List of stock names. If None, fetches all NIFTY 50 stocks.
    """
    payload = {"batch_size": 10}
    if stocks:
        payload["stocks"] = stocks
    
    print(f"Fetching live market data...")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        response = requests.post(ENDPOINT, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") == "success":
            summary = data.get("summary", {})
            results = data.get("results", {})
            
            print(f"\n📊 SUMMARY:")
            print(f"   Total Stocks: {summary.get('total_stocks')}")
            print(f"   Successful: {summary.get('successful')}")
            print(f"   Failed: {summary.get('failed')}")
            print(f"   Timestamp: {summary.get('timestamp')}")
            print("\n" + "=" * 80)
            
            # Display results
            print(f"\n📈 LIVE MARKET DATA:\n")
            
            for stock_name, stock_data in results.items():
                if stock_data.get("status") == "success":
                    ltp = stock_data.get("ltp")
                    change = stock_data.get("change_percent")
                    volume = stock_data.get("volume")
                    
                    # Format values safely
                    ltp_str = f"{ltp:>10.2f}" if isinstance(ltp, (int, float)) else "N/A".rjust(10)
                    change_str = f"{change:+.2f}%" if isinstance(change, (int, float)) else "N/A"
                    volume_str = f"{volume:>12,}" if isinstance(volume, (int, float)) else "N/A".rjust(12)
                    indicator = "🟢" if isinstance(change, (int, float)) and change > 0 else "🔴" if isinstance(change, (int, float)) and change < 0 else "⚪"
                    
                    print(f"{indicator} {stock_name:30s} | LTP: ₹{ltp_str} | Change: {change_str:>8} | Volume: {volume_str}")
                else:
                    print(f"❌ {stock_name:30s} | Error: {stock_data.get('message', 'Unknown error')}")
            
            print("\n" + "=" * 80)
            
            # Save to file
            output_file = f"live_market_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"\n💾 Data saved to: {output_file}")
            
        else:
            print(f"❌ Error: {data.get('message')}")
            if 'hint' in data:
                print(f"💡 Hint: {data.get('hint')}")
    
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server.")
        print("💡 Make sure the FastAPI server is running on http://localhost:8000")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    # Example 1: Fetch all NIFTY 50 stocks
    print("\n🔍 Fetching ALL NIFTY 50 stocks...\n")
    fetch_live_data()
    
    # Example 2: Fetch specific stocks (uncomment to use)
    # print("\n🔍 Fetching specific stocks...\n")
    # fetch_live_data(stocks=["HDFC Bank", "TCS", "Reliance Industries", "Infosys", "ICICI Bank"])
