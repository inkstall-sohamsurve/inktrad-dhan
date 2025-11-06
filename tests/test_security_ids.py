#!/usr/bin/env python3
"""
Quick test script to check security ID validation
"""
import requests
import json

def test_security_id(security_id):
    """Test a security ID with the demo API"""
    url = f"http://localhost:8000/api/v2/dhan/demo/historical-data?security_id={security_id}"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        print(f"\n🔍 Testing Security ID: {security_id}")
        print(f"Status Code: {response.status_code}")

        if data.get('status') == 'error':
            print(f"❌ Error: {data.get('message', 'Unknown error')}")
            if 'common_stocks' in data:
                print("📋 Common stocks available:")
                for stock, sid in data['common_stocks'].items():
                    print(f"  {sid}: {stock}")
        else:
            print("✅ Success! Data retrieved"            if 'data' in data and 'open' in data['data']:
                num_candles = len(data['data']['open'])
                print(f"   📊 Candles: {num_candles}")

    except Exception as e:
        print(f"❌ Network error: {e}")

if __name__ == "__main__":
    print("Testing DHAN Security IDs...")

    # Test known working ID
    test_security_id("1333")  # HDFC Bank

    # Test problematic ID
    test_security_id("1335")  # Unknown

    # Test another known ID
    test_security_id("738")   # Reliance
