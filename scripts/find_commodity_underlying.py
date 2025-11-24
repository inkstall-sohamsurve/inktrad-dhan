"""
Find the correct underlying security IDs for MCX commodity options
The option_chain API needs the underlying commodity ID, not the futures contract ID
"""

from dhanhq import dhanhq
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

DHAN_CLIENT_ID = os.getenv("DHAN_MASTER_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_MASTER_ACCESS_TOKEN")

def find_underlying_ids():
    """Find underlying security IDs by checking option contracts"""
    
    print("=" * 100)
    print("🔍 FINDING UNDERLYING SECURITY IDs FOR COMMODITY OPTIONS")
    print("=" * 100)
    print()
    
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        print("❌ ERROR: DHAN credentials not found")
        return
    
    try:
        print("📡 Connecting to DHAN API...")
        dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        print("✅ Connected!")
        print()
        
        print("📥 Fetching security list...")
        security_df = dhan.fetch_security_list("compact")
        
        if security_df is None or security_df.empty:
            print("❌ Failed to fetch security list")
            return
        
        print(f"✅ Fetched {len(security_df)} securities")
        print()
        
        # Get MCX segment
        mcx_df = security_df[security_df['SEM_SEGMENT'] == 'M']
        print(f"Found {len(mcx_df)} MCX securities")
        print()
        
        # Get option contracts
        options_df = mcx_df[mcx_df['SEM_INSTRUMENT_NAME'].str.contains('OPT', case=False, na=False)]
        print(f"Found {len(options_df)} option contracts")
        print()
        
        # Check if UNDERLYING_SECURITY_ID column exists
        print("📋 Checking for UNDERLYING_SECURITY_ID column...")
        if 'UNDERLYING_SECURITY_ID' in options_df.columns:
            print("✅ Column exists!")
        else:
            print("❌ Column not found. Available columns:")
            print(options_df.columns.tolist())
            print()
            print("Trying alternative approach - looking at SEM_CUSTOM_SYMBOL...")
        
        print()
        print("=" * 100)
        print("🎯 ANALYZING OPTION CONTRACTS FOR UNDERLYING IDs")
        print("=" * 100)
        print()
        
        commodities = ['CRUDEOIL', 'GOLD', 'SILVER', 'NATURALGAS', 'COPPER', 'ZINC']
        
        for commodity in commodities:
            opt_matches = options_df[options_df['SEM_TRADING_SYMBOL'].str.contains(commodity, case=False, na=False)]
            
            if not opt_matches.empty:
                print(f"🔸 {commodity}:")
                print(f"   Found {len(opt_matches)} option contracts")
                
                # Show first contract details
                first = opt_matches.iloc[0]
                print(f"   Sample Contract:")
                print(f"     Security ID:      {first['SEM_SMST_SECURITY_ID']}")
                print(f"     Trading Symbol:   {first['SEM_TRADING_SYMBOL']}")
                print(f"     Custom Symbol:    {first.get('SEM_CUSTOM_SYMBOL', 'N/A')}")
                
                # Check for underlying ID in various columns
                for col in ['UNDERLYING_SECURITY_ID', 'SEM_UNDERLYING_SECURITY_ID', 'UNDERLYING_SCRIP']:
                    if col in first.index and pd.notna(first[col]):
                        print(f"     {col}: {first[col]}")
                
                # Try to find the underlying by looking at the symbol pattern
                # Options usually reference the underlying in their symbol
                print()
        
        print()
        print("=" * 100)
        print("🔍 TRYING DIRECT API CALLS TO FIND VALID IDs")
        print("=" * 100)
        print()
        
        # Try different potential underlying IDs
        test_ids = {
            "CRUDEOIL": [462523, 1, 100, 200],  # Try futures ID and some common IDs
            "GOLD": [467742, 2, 101, 201],
            "SILVER": [440938, 3, 102, 202],
        }
        
        for commodity, ids_to_test in test_ids.items():
            print(f"Testing {commodity}:")
            for test_id in ids_to_test:
                try:
                    print(f"  Trying Security ID {test_id}...", end=" ")
                    result = dhan.expiry_list(
                        under_security_id=test_id,
                        under_exchange_segment="M"
                    )
                    
                    if result and result.get("status") == "success":
                        print(f"✅ SUCCESS!")
                        print(f"     Valid underlying ID for {commodity}: {test_id}")
                        expiry_data = result.get("data", {})
                        if isinstance(expiry_data, dict):
                            expiry_data = expiry_data.get("data", [])
                        print(f"     Available expiries: {expiry_data[:3] if expiry_data else 'None'}")
                        print()
                        break
                    else:
                        print(f"❌ Failed: {result.get('data', {})}")
                except Exception as e:
                    print(f"❌ Error: {str(e)[:50]}")
            print()
        
        print()
        print("=" * 100)
        print("💡 ALTERNATIVE: Check DHAN Web Platform")
        print("=" * 100)
        print()
        print("If API doesn't provide underlying IDs, you can:")
        print("1. Log into DHAN web platform")
        print("2. Go to MCX commodity options")
        print("3. Inspect network requests when loading option chain")
        print("4. Look for the 'UnderlyingScrip' parameter in API calls")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    find_underlying_ids()
