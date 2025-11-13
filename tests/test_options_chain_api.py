"""
Test script for the new options chain API endpoint
"""
import requests
import json

def test_options_chain_api():
    """Test the new options chain API endpoint"""
    base_url = "http://localhost:8000"

    print("🧪 Testing Options Chain API...")
    print("=" * 50)

    try:
        # Test NIFTY
        print("📈 Testing NIFTY options chain...")
        response = requests.get(f"{base_url}/api/v2/options-chain/live?index=NIFTY")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ API Response successful!")
            print(f"Status: {data.get('status')}")
            print(f"Timestamp: {data.get('timestamp')}")

            # Check if data exists
            if data.get('data'):
                print("✅ Data received!")
                # Show a few sample strikes
                strikes = list(data['data'].keys())[:3]
                print(f"Sample strikes: {strikes}")
            else:
                print("❌ No data in response")
        else:
            print(f"❌ API Error: {response.text}")

        print("\n" + "-" * 30)

        # Test BANKNIFTY
        print("📈 Testing BANKNIFTY options chain...")
        response = requests.get(f"{base_url}/api/v2/options-chain/live?index=BANKNIFTY")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ API Response successful!")
            print(f"Status: {data.get('status')}")

            if data.get('data'):
                print("✅ Data received!")
                strikes = list(data['data'].keys())[:3]
                print(f"Sample strikes: {strikes}")
            else:
                print("❌ No data in response")
        else:
            print(f"❌ API Error: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_options_chain_api()
