"""
Quick test script to verify DHAN WebSocket connection and credentials
Tests connection without subscribing to instruments
"""

import asyncio
import websockets
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DHAN_CLIENT_ID = os.getenv("DHAN_MASTER_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_MASTER_ACCESS_TOKEN")


async def test_connection():
    """Test DHAN WebSocket connection"""
    
    print("\n" + "="*60)
    print("🧪 DHAN WebSocket Connection Test")
    print("="*60)
    
    # Check credentials
    print("\n1️⃣ Checking credentials...")
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        print("❌ FAIL: Credentials not found in .env file")
        print("\nPlease set:")
        print("  DHAN_MASTER_CLIENT_ID=your_client_id")
        print("  DHAN_MASTER_ACCESS_TOKEN=your_access_token")
        return False
    
    print(f"✅ Client ID: {DHAN_CLIENT_ID[:10]}...")
    print(f"✅ Access Token: {DHAN_ACCESS_TOKEN[:20]}...")
    
    # Test connection
    print("\n2️⃣ Testing WebSocket connection...")
    ws_url = f"wss://api-feed.dhan.co?version=2&token={DHAN_ACCESS_TOKEN}&clientId={DHAN_CLIENT_ID}&authType=2"
    
    try:
        async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as websocket:
            print("✅ WebSocket connection successful!")
            
            # Wait for a moment to ensure connection is stable
            await asyncio.sleep(1)
            
            print("\n3️⃣ Connection details:")
            print(f"   URL: wss://api-feed.dhan.co")
            print(f"   State: Connected")
            print(f"   Protocol: WebSocket v2")
            
            print("\n✅ All tests passed!")
            print("\n📝 Next steps:")
            print("   1. Run: python live_nifty50_ticker.py")
            print("   2. Or: python live_market_stream.py --mode ticker")
            
            return True
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ FAIL: Invalid status code - {e}")
        print("\n💡 Possible issues:")
        print("   - Invalid access token")
        print("   - Expired token")
        print("   - Invalid client ID")
        print("\n🔧 Solution:")
        print("   - Generate new access token from DHAN portal")
        print("   - Update .env file with new credentials")
        return False
        
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ FAIL: WebSocket error - {e}")
        print("\n💡 Possible issues:")
        print("   - Network connectivity problem")
        print("   - Firewall blocking WebSocket")
        print("   - DHAN API temporarily down")
        return False
        
    except Exception as e:
        print(f"❌ FAIL: Unexpected error - {e}")
        print(f"\n💡 Error type: {type(e).__name__}")
        return False


async def main():
    """Main function"""
    success = await test_connection()
    
    print("\n" + "="*60)
    if success:
        print("🎉 Connection test PASSED - Ready to fetch live data!")
    else:
        print("⚠️  Connection test FAILED - Please fix issues above")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
