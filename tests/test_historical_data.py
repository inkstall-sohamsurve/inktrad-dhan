"""
Test script to fetch historical data from Dhan API.
Run this script to see historical data in the console.

Usage:
    python test_historical_data.py
"""
import asyncio
from dhanhq import dhanhq
from datetime import datetime, timedelta
import json
from typing import Dict, Any


def format_historical_data(data: Dict[str, Any]) -> None:
    """Format and print historical data in a readable format."""
    if not data:
        print("No data received")
        return
    
    print("\n" + "="*80)
    print("HISTORICAL DATA")
    print("="*80)
    
    # Check if data contains the expected fields
    if 'open' in data and 'high' in data and 'low' in data and 'close' in data:
        num_candles = len(data['open'])
        print(f"\nTotal candles: {num_candles}\n")
        
        # Print header
        print(f"{'Date/Time':<20} {'Open':<12} {'High':<12} {'Low':<12} {'Close':<12} {'Volume':<15}")
        print("-" * 80)
        
        # Print each candle
        for i in range(min(num_candles, 20)):  # Show first 20 candles
            timestamp = data.get('timestamp', [])[i] if i < len(data.get('timestamp', [])) else 'N/A'
            open_price = data['open'][i]
            high_price = data['high'][i]
            low_price = data['low'][i]
            close_price = data['close'][i]
            volume = data.get('volume', [])[i] if i < len(data.get('volume', [])) else 'N/A'
            
            # Convert timestamp if it's a number
            if isinstance(timestamp, (int, float)):
                # Dhan uses custom epoch from 1980-01-01
                base_date = datetime(1980, 1, 1)
                date_str = (base_date + timedelta(seconds=timestamp)).strftime('%Y-%m-%d %H:%M')
            else:
                date_str = str(timestamp)
            
            print(f"{date_str:<20} {open_price:<12.2f} {high_price:<12.2f} {low_price:<12.2f} {close_price:<12.2f} {str(volume):<15}")
        
        if num_candles > 20:
            print(f"\n... and {num_candles - 20} more candles")
    else:
        print("\nRaw data:")
        print(json.dumps(data, indent=2))
    
    print("\n" + "="*80 + "\n")


async def fetch_daily_historical_data(client_id: str, access_token: str):
    """Fetch daily historical data."""
    print("\n🔍 Fetching DAILY historical data...")
    
    try:
        # Initialize Dhan client
        dhan = dhanhq(client_id, access_token)
        
        # Calculate dates (last 30 days)
        to_date = datetime.now()
        from_date = to_date - timedelta(days=30)
        
        # Fetch historical data for HDFC Bank (security_id: 1333)
        # You can change this to any other security_id
        response = dhan.historical_daily_data(
            security_id="1333",  # HDFC Bank
            exchange_segment="NSE_EQ",
            instrument_type="EQUITY",
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d")
        )
        
        print(f"\n✅ Successfully fetched data for HDFC Bank (1333)")
        print(f"Date range: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
        
        format_historical_data(response)
        
        return response
        
    except Exception as e:
        print(f"\n❌ Error fetching daily historical data: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return None


async def fetch_intraday_data(client_id: str, access_token: str):
    """Fetch intraday historical data."""
    print("\n🔍 Fetching INTRADAY historical data (5-min candles)...")
    
    try:
        # Initialize Dhan client
        dhan = dhanhq(client_id, access_token)
        
        # Calculate dates (last 5 days)
        to_date = datetime.now()
        from_date = to_date - timedelta(days=5)
        
        # Fetch intraday data for HDFC Bank (security_id: 1333)
        response = dhan.intraday_minute_data(
            security_id="1333",  # HDFC Bank
            exchange_segment="NSE_EQ",
            instrument_type="EQUITY",
            from_date=from_date.strftime("%Y-%m-%d 09:15:00"),
            to_date=to_date.strftime("%Y-%m-%d 15:30:00")
        )
        
        print(f"\n✅ Successfully fetched intraday data for HDFC Bank (1333)")
        print(f"Date range: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
        print(f"Interval: 5 minutes")
        
        format_historical_data(response)
        
        return response
        
    except Exception as e:
        print(f"\n❌ Error fetching intraday data: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return None


async def main():
    """Main function to test historical data fetching."""
    print("\n" + "="*80)
    print("DHAN HISTORICAL DATA TEST SCRIPT")
    print("="*80)
    
    # Get credentials from user
    print("\nPlease enter your Dhan credentials:")
    client_id = input("Client ID: ").strip()
    access_token = input("Access Token: ").strip()
    
    if not client_id or not access_token:
        print("\n❌ Error: Client ID and Access Token are required!")
        return
    
    print("\n" + "-"*80)
    print("Choose an option:")
    print("1. Fetch Daily Historical Data (last 30 days)")
    print("2. Fetch Intraday Data (5-min candles, last 5 days)")
    print("3. Fetch Both")
    print("-"*80)
    
    choice = input("\nEnter your choice (1/2/3): ").strip()
    
    if choice == "1":
        await fetch_daily_historical_data(client_id, access_token)
    elif choice == "2":
        await fetch_intraday_data(client_id, access_token)
    elif choice == "3":
        await fetch_daily_historical_data(client_id, access_token)
        await fetch_intraday_data(client_id, access_token)
    else:
        print("\n❌ Invalid choice!")
    
    print("\n✨ Test completed!")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
