"""
Simple script to fetch and display historical data from Dhan API.
Uses environment variables for credentials.

Make sure to set these in your .env file:
- DHAN_MASTER_CLIENT_ID
- DHAN_MASTER_ACCESS_TOKEN

Usage:
    python fetch_historical_simple.py
"""
import os
from dhanhq import dhanhq
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def print_separator(char="=", length=100):
    """Print a separator line."""
    print(char * length)


def fetch_and_display_historical_data():
    """Fetch and display historical data."""
    
    # Get credentials from environment
    client_id = os.getenv("DHAN_MASTER_CLIENT_ID")
    access_token = os.getenv("DHAN_MASTER_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        print("\n❌ ERROR: Dhan credentials not found!")
        print("Please set DHAN_MASTER_CLIENT_ID and DHAN_MASTER_ACCESS_TOKEN in your .env file")
        return
    
    print("\n")
    print_separator()
    print("FETCHING HISTORICAL DATA FROM DHAN API")
    print_separator()
    
    try:
        # Initialize Dhan client
        print("\n📡 Initializing Dhan client...")
        dhan = dhanhq(client_id, access_token)
        print("✅ Client initialized successfully!")
        
        # Calculate dates
        to_date = datetime.now()
        from_date = to_date - timedelta(days=30)
        
        print(f"\n📅 Fetching data from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
        print(f"📊 Instrument: HDFC Bank (Security ID: 1333)")
        print(f"🏢 Exchange: NSE_EQ")
        
        # Fetch historical data
        print("\n⏳ Fetching daily historical data...")
        response = dhan.historical_daily_data(
            security_id="1333",  # HDFC Bank
            exchange_segment="NSE_EQ",
            instrument_type="EQUITY",
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d")
        )
        
        print("✅ Data fetched successfully!\n")
        
        # Display the data
        print_separator("-")
        print("HISTORICAL DATA RESPONSE")
        print_separator("-")
        
        if isinstance(response, dict):
            # Check if response has the status/data wrapper
            data = response.get('data', response)
            
            # Pretty print the JSON response
            print(json.dumps(response, indent=2))
            
            # If data contains OHLC arrays, display in table format
            if 'open' in data and len(data['open']) > 0:
                print("\n")
                print_separator("-")
                print("DATA IN TABLE FORMAT (First 10 candles)")
                print_separator("-")
                print(f"\n{'Index':<8} {'Open':<12} {'High':<12} {'Low':<12} {'Close':<12} {'Volume':<15}")
                print("-" * 75)
                
                num_candles = min(len(data['open']), 10)
                for i in range(num_candles):
                    open_price = data['open'][i]
                    high_price = data['high'][i]
                    low_price = data['low'][i]
                    close_price = data['close'][i]
                    volume = data.get('volume', [])[i] if i < len(data.get('volume', [])) else 'N/A'
                    
                    print(f"{i:<8} {open_price:<12.2f} {high_price:<12.2f} {low_price:<12.2f} {close_price:<12.2f} {str(volume):<15}")
                
                total_candles = len(data['open'])
                if total_candles > 10:
                    print(f"\n... and {total_candles - 10} more candles (total: {total_candles})")
        else:
            print(response)
        
        print("\n")
        print_separator()
        print("✨ SUCCESS! Historical data fetched and displayed.")
        print_separator()
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    fetch_and_display_historical_data()
