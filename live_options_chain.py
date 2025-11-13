import os
import time
from datetime import datetime
from typing import Dict, List
from dhanhq import dhanhq
from dotenv import load_dotenv
import json

load_dotenv()

DHAN_CLIENT_ID = os.getenv("DHAN_MASTER_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_MASTER_ACCESS_TOKEN")

# Index configuration for option chain
INDEX_CONFIG = {
    "NIFTY": {
        "under_security_id": 13,
        "under_exchange_segment": "IDX_I",
        "display_name": "NIFTY"
    },
    "BANKNIFTY": {
        "under_security_id": 25,
        "under_exchange_segment": "IDX_I",
        "display_name": "BANKNIFTY"
    }
}


class OptionsChainLive:
    def __init__(self, indices: List[str] = ["NIFTY", "BANKNIFTY"], expiry: str = None):
        """
        Initialize Options Chain Live fetcher
        
        Args:
            indices: List of indices to fetch (NIFTY, BANKNIFTY)
            expiry: Expiry date in YYYY-MM-DD format (e.g., "2024-10-31")
        """
        self.indices = indices
        self.expiry = expiry
        self.dhan = None
        self.option_chain_data: Dict[str, Dict] = {}

    def connect(self) -> bool:
        """Initialize Dhan client"""
        try:
            if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
                print("❌ Missing DHAN credentials in .env")
                return False
            
            # Try to initialize dhanhq client
            # Different versions have different initialization methods
            try:
                # Try v1.x style (client_id, access_token)
                self.dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
            except TypeError:
                # Try v2.x style (with DhanContext)
                try:
                    from dhanhq import DhanContext
                    dhan_context = DhanContext(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
                    self.dhan = dhanhq(dhan_context)
                except ImportError:
                    raise Exception("Unable to initialize dhanhq client. Please check your dhanhq version.")
            
            print("✅ Dhan client initialized successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize Dhan client: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_expiry_list(self, index_name: str) -> list:
        """
        Fetch available expiry dates for an index
        
        Args:
            index_name: Name of the index (NIFTY or BANKNIFTY)
            
        Returns:
            List of available expiry dates
        """
        try:
            config = INDEX_CONFIG.get(index_name)
            if not config:
                return []
            
            response = self.dhan.expiry_list(
                under_security_id=config["under_security_id"],
                under_exchange_segment=config["under_exchange_segment"]
            )
            
            # Debug: print(f"   📋 Expiry list response: {response}")
            
            if isinstance(response, dict):
                if response.get('status') == 'success':
                    data = response.get('data', {})
                    # Try different possible keys for expiry data
                    expiries = data.get('data', []) or data.get('expiry', [])
                    if expiries:
                        print(f"   ✅ Found {len(expiries)} expiries: {expiries[:5]}")  # Show first 5
                        return expiries
                else:
                    print(f"   ⚠️  API returned status: {response.get('status')}")
            return []
        except Exception as e:
            print(f"   ❌ Error fetching expiry list: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def fetch_option_chain(self, index_name: str) -> Dict:
        """
        Fetch option chain data for a specific index
        
        Args:
            index_name: Name of the index (NIFTY or BANKNIFTY)
            
        Returns:
            Dictionary containing option chain data
        """
        try:
            config = INDEX_CONFIG.get(index_name)
            if not config:
                print(f"❌ Unknown index: {index_name}")
                return {}
            
            print(f"\n🔍 Fetching option chain for {index_name}...")
            print(f"   Security ID: {config['under_security_id']}")
            print(f"   Exchange Segment: {config['under_exchange_segment']}")
            
            # If no expiry specified, get the first available expiry
            expiry_to_use = self.expiry
            if not expiry_to_use:
                print("   📅 No expiry specified, fetching available expiries...")
                expiries = self.get_expiry_list(index_name)
                if expiries:
                    expiry_to_use = expiries[0]
                    print(f"   ✅ Using first available expiry: {expiry_to_use}")
                else:
                    print("   ❌ Could not fetch expiry list")
                    return {}
            else:
                print(f"   Expiry: {expiry_to_use}")
            
            params = {
                "under_security_id": config["under_security_id"],
                "under_exchange_segment": config["under_exchange_segment"],
                "expiry": expiry_to_use
            }
            
            response = self.dhan.option_chain(**params)
            
            # Check if the response is successful
            if isinstance(response, dict):
                status = response.get('status', '')
                if status == 'failure':
                    print(f"   ⚠️  API returned failure status")
                    remarks = response.get('remarks', {})
                    if remarks:
                        print(f"   Error details: {remarks}")
                    print(f"   This might be due to:")
                    print(f"      - Invalid expiry date (must be a valid trading expiry)")
                    print(f"      - Market is closed")
                    print(f"      - Invalid credentials")
                elif status == 'success':
                    print(f"   ✅ Successfully fetched data")
            
            # Store the data
            self.option_chain_data[index_name] = response
            
            return response
            
        except Exception as e:
            print(f"❌ Error fetching option chain for {index_name}: {e}")
            return {}
    
    def fetch_all_chains(self) -> Dict[str, Dict]:
        """Fetch option chains for all configured indices"""
        results = {}
        for i, index_name in enumerate(self.indices):
            data = self.fetch_option_chain(index_name)
            results[index_name] = data
            # Add delay between requests to avoid rate limiting (except for last request)
            if i < len(self.indices) - 1:
                print(f"\n⏳ Waiting 5 seconds before next request to avoid rate limiting...")
                time.sleep(5)
        return results
    
    def print_option_chain_data(self):
        """Print the fetched option chain data in a readable format"""
        print("\n" + "=" * 100)
        print("📊 LIVE OPTIONS CHAIN DATA")
        print("=" * 100)
        
        for index_name, data in self.option_chain_data.items():
            print(f"\n{'='*50}")
            print(f"INDEX: {index_name}")
            print(f"{'='*50}")
            
            if not data:
                print("❌ No data available")
                continue
            
            # Print the raw response structure
            print(f"\n📋 Response Keys: {list(data.keys())}")
            
            # Pretty print the entire response
            print(f"\n📄 Full Response:")
            print(json.dumps(data, indent=2, default=str))
            
            print(f"\n{'-'*50}\n")


def main():
    """Main function to fetch and display option chain data"""
    print("\n" + "=" * 100)
    print("🚀 LIVE OPTIONS CHAIN - NIFTY & BANKNIFTY (DHAN API)")
    print("=" * 100)
    
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        print("❌ Missing DHAN credentials in .env")
        print("   Please set DHAN_MASTER_CLIENT_ID and DHAN_MASTER_ACCESS_TOKEN in your .env file")
        return
    
    # Specify an expiry date or leave as None to auto-fetch the nearest expiry
    # Set to None to automatically use the first available expiry from the API
    # Or specify a date like: "2024-11-14" or "14-11-2024"
    
    expiry = None  # Will automatically fetch and use the first available expiry
    
    if expiry:
        print(f"📅 Using specified expiry date: {expiry}\n")
    else:
        print(f"📅 Will auto-fetch the nearest available expiry date\n")
    
    # Initialize the options chain fetcher
    chain = OptionsChainLive(indices=["NIFTY", "BANKNIFTY"], expiry=expiry)
    
    print("🔌 Initializing Dhan client...")
    if not chain.connect():
        return
    
    try:
        print("\n📡 Fetching option chains...")
        chain.fetch_all_chains()
        
        print("\n📊 Displaying fetched data...")
        chain.print_option_chain_data()
        
        print("\n✅ Data fetch completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        pass
