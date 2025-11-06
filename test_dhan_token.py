"""
Test if DHAN access token is valid by making a simple API call.
"""
import requests
from app.core.config import settings

def test_dhan_token():
    """Test if the DHAN access token is valid."""
    
    print("="*80)
    print("TESTING DHAN ACCESS TOKEN")
    print("="*80)
    
    # Check if credentials exist
    if not settings.DHAN_MASTER_CLIENT_ID:
        print("❌ DHAN_MASTER_CLIENT_ID not found in .env file")
        return False
    
    if not settings.DHAN_MASTER_ACCESS_TOKEN:
        print("❌ DHAN_MASTER_ACCESS_TOKEN not found in .env file")
        return False
    
    print(f"\n✅ Client ID found: {settings.DHAN_MASTER_CLIENT_ID}")
    print(f"✅ Access Token found: {settings.DHAN_MASTER_ACCESS_TOKEN[:30]}...")
    
    # Test with a simple market quote API call
    print("\n" + "-"*80)
    print("Testing DHAN API with a simple request...")
    print("-"*80)
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "access-token": settings.DHAN_MASTER_ACCESS_TOKEN,
        "clientId": settings.DHAN_MASTER_CLIENT_ID
    }
    
    # Try to fetch quote for a single stock (HDFC Bank - 1333)
    payload = {
        "NSE_EQ": ["1333"]
    }
    
    try:
        response = requests.post(
            "https://api.dhan.co/v2/marketfeed/quote",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"\nResponse Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Status: {data.get('status')}")
            
            if data.get('status') == 'success':
                print("\n" + "="*80)
                print("✅ SUCCESS! Your DHAN token is VALID and working!")
                print("="*80)
                
                # Show sample data
                if 'data' in data and '1333' in data['data']:
                    stock_data = data['data']['1333']
                    print(f"\nSample Data (HDFC Bank):")
                    print(f"  LTP: {stock_data.get('LTP', 'N/A')}")
                    print(f"  Open: {stock_data.get('open', 'N/A')}")
                    print(f"  High: {stock_data.get('high', 'N/A')}")
                    print(f"  Low: {stock_data.get('low', 'N/A')}")
                    print(f"  Volume: {stock_data.get('volume', 'N/A')}")
                
                return True
            else:
                print("\n" + "="*80)
                print("❌ FAILED! DHAN API returned failure status")
                print("="*80)
                print(f"\nResponse: {data}")
                return False
                
        elif response.status_code == 401:
            print("\n" + "="*80)
            print("❌ AUTHENTICATION FAILED! (HTTP 401)")
            print("="*80)
            print("\nYour access token is INVALID or EXPIRED.")
            print("\nWhat to do:")
            print("1. Go to https://api.dhan.co")
            print("2. Login to your DHAN account")
            print("3. Generate a NEW access token")
            print("4. Update your .env file with the new token")
            print("5. Restart the server (python run.py)")
            
            try:
                error_data = response.json()
                print(f"\nError details: {error_data}")
            except:
                print(f"\nResponse text: {response.text}")
            
            return False
        else:
            print(f"\n❌ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out")
        return False
    except requests.exceptions.ConnectionError:
        print("\n❌ Connection error - check your internet connection")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False


if __name__ == "__main__":
    test_dhan_token()
