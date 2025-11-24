"""
Script to fetch MCX commodity security IDs from DHAN API
Loads credentials from .env file
"""

from dhanhq import dhanhq
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Get DHAN credentials from environment
DHAN_CLIENT_ID = os.getenv("DHAN_MASTER_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_MASTER_ACCESS_TOKEN")

def fetch_mcx_securities():
    """Fetch and display all MCX commodity securities from DHAN"""
    
    print("=" * 100)
    print("🏭 FETCHING MCX COMMODITY SECURITIES FROM DHAN API")
    print("=" * 100)
    print()
    
    # Check credentials
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        print("❌ ERROR: DHAN credentials not found!")
        print(f"Looking for .env file at: {env_path}")
        print()
        print("Please ensure your .env file contains:")
        print("  DHAN_MASTER_CLIENT_ID=your_client_id")
        print("  DHAN_MASTER_ACCESS_TOKEN=your_access_token")
        print()
        return
    
    try:
        # Initialize DHAN client
        print("📡 Connecting to DHAN API...")
        print(f"Client ID: {DHAN_CLIENT_ID[:10]}...")
        dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        print("✅ Connected successfully!")
        print()
        
        # Fetch security list
        print("📥 Fetching security list (this may take a moment)...")
        security_df = dhan.fetch_security_list("compact")
        
        if security_df is None or security_df.empty:
            print("❌ Failed to fetch security list")
            return
        
        print(f"✅ Fetched {len(security_df)} total securities")
        print()
        
        # Show available segments
        print("📊 Available segments:")
        unique_segments = security_df['SEM_SEGMENT'].unique()
        for seg in sorted(unique_segments):
            count = len(security_df[security_df['SEM_SEGMENT'] == seg])
            print(f"  {seg:20} {count:6} securities")
        print()
        
        # Filter for MCX segment
        print("🔍 Filtering for MCX commodities...")
        mcx_segments = [seg for seg in unique_segments if 'MCX' in seg]
        
        if not mcx_segments:
            print("❌ No MCX segments found")
            return
        
        print(f"Found MCX segments: {mcx_segments}")
        print()
        
        mcx_df = security_df[security_df['SEM_SEGMENT'].isin(mcx_segments)]
        
        if mcx_df.empty:
            print("❌ No MCX securities found")
            return
        
        print(f"✅ Found {len(mcx_df)} MCX securities")
        print()
        
        # Group by segment and instrument type
        print("📊 MCX Securities by Segment and Instrument Type:")
        print("-" * 100)
        
        for segment in mcx_segments:
            seg_df = mcx_df[mcx_df['SEM_SEGMENT'] == segment]
            print(f"\n🔹 Segment: {segment} ({len(seg_df)} securities)")
            
            instrument_groups = seg_df.groupby('SEM_INSTRUMENT_NAME')
            for instrument_type, group in instrument_groups:
                print(f"   📌 {instrument_type}: {len(group)} securities")
        
        print()
        print("=" * 100)
        print("🎯 COMMODITY UNDERLYING SECURITIES")
        print("=" * 100)
        print()
        
        # Find underlying commodities
        commodities = ['CRUDEOIL', 'GOLD', 'SILVER', 'NATURALGAS', 'COPPER', 'ZINC', 
                      'ALUMINIUM', 'LEAD', 'NICKEL', 'GOLDM', 'SILVERM', 'GOLDPETAL']
        
        print("Searching for commodity contracts...")
        print()
        
        for commodity in commodities:
            # Search in trading symbol
            matches = mcx_df[mcx_df['SEM_TRADING_SYMBOL'].str.contains(commodity, case=False, na=False)]
            
            if not matches.empty:
                print(f"🔸 {commodity}:")
                print(f"   Found {len(matches)} contracts")
                
                # Group by instrument type
                inst_types = matches['SEM_INSTRUMENT_NAME'].unique()
                print(f"   Instrument types: {list(inst_types)}")
                
                # Show first few contracts with different instrument types
                shown = set()
                count = 0
                for _, row in matches.iterrows():
                    inst_name = row['SEM_INSTRUMENT_NAME']
                    if inst_name not in shown and count < 3:
                        print(f"   ├─ [{inst_name}]")
                        print(f"   │  Security ID: {row['SEM_SMST_SECURITY_ID']}")
                        print(f"   │  Symbol:      {row['SEM_TRADING_SYMBOL']}")
                        print(f"   │  Expiry:      {row.get('SEM_EXPIRY_DATE', 'N/A')}")
                        print(f"   │  Lot Size:    {row.get('SEM_LOT_UNITS', 'N/A')}")
                        print()
                        shown.add(inst_name)
                        count += 1
                
                print()
        
        print()
        print("=" * 100)
        print("📝 COMMODITY FUTURES (for option chain underlying)")
        print("=" * 100)
        print()
        
        # Look for FUTCOM (Futures Commodity) instruments
        futcom_df = mcx_df[mcx_df['SEM_INSTRUMENT_NAME'].str.contains('FUT', case=False, na=False)]
        
        if not futcom_df.empty:
            print(f"Found {len(futcom_df)} futures contracts")
            print()
            
            for commodity in commodities:
                fut_matches = futcom_df[futcom_df['SEM_TRADING_SYMBOL'].str.contains(commodity, case=False, na=False)]
                
                if not fut_matches.empty:
                    # Get the nearest expiry
                    if 'SEM_EXPIRY_DATE' in fut_matches.columns:
                        fut_matches_sorted = fut_matches.sort_values('SEM_EXPIRY_DATE')
                        nearest = fut_matches_sorted.iloc[0]
                        
                        print(f"✅ {commodity} (Nearest Futures):")
                        print(f"   Security ID:  {nearest['SEM_SMST_SECURITY_ID']}")
                        print(f"   Symbol:       {nearest['SEM_TRADING_SYMBOL']}")
                        print(f"   Expiry:       {nearest['SEM_EXPIRY_DATE']}")
                        print(f"   Lot Size:     {nearest.get('SEM_LOT_UNITS', 'N/A')}")
                        print(f"   Segment:      {nearest['SEM_SEGMENT']}")
                        print()
        
        # Look for OPTFUT (Options on Futures)
        print()
        print("=" * 100)
        print("📝 COMMODITY OPTIONS (OPTFUT)")
        print("=" * 100)
        print()
        
        optfut_df = mcx_df[mcx_df['SEM_INSTRUMENT_NAME'].str.contains('OPT', case=False, na=False)]
        
        if not optfut_df.empty:
            print(f"Found {len(optfut_df)} option contracts")
            print()
            
            for commodity in commodities:
                opt_matches = optfut_df[optfut_df['SEM_TRADING_SYMBOL'].str.contains(commodity, case=False, na=False)]
                
                if not opt_matches.empty:
                    print(f"✅ {commodity} Options: {len(opt_matches)} contracts")
                    
                    # Show underlying security ID (should be same for all options of same commodity)
                    if 'UNDERLYING_SECURITY_ID' in opt_matches.columns:
                        underlying_ids = opt_matches['UNDERLYING_SECURITY_ID'].unique()
                        print(f"   Underlying Security IDs: {underlying_ids}")
                    
                    # Show sample
                    sample = opt_matches.head(2)
                    for _, row in sample.iterrows():
                        print(f"   ├─ {row['SEM_TRADING_SYMBOL']}")
                        print(f"   │  Security ID: {row['SEM_SMST_SECURITY_ID']}")
                        print(f"   │  Strike:      {row.get('SEM_STRIKE_PRICE', 'N/A')}")
                        print(f"   │  Type:        {row.get('SEM_OPTION_TYPE', 'N/A')}")
                        print(f"   │  Expiry:      {row.get('SEM_EXPIRY_DATE', 'N/A')}")
                    print()
        
        # Save to CSV
        output_file = Path(__file__).parent / "mcx_securities.csv"
        mcx_df.to_csv(output_file, index=False)
        print(f"💾 Full MCX securities list saved to: {output_file}")
        print()
        
        # Summary
        print("=" * 100)
        print("📈 SUMMARY")
        print("=" * 100)
        print(f"Total MCX Securities:     {len(mcx_df)}")
        print(f"Segments:                 {mcx_segments}")
        print(f"Instrument Types:         {mcx_df['SEM_INSTRUMENT_NAME'].nunique()}")
        print(f"Unique Trading Symbols:   {mcx_df['SEM_TRADING_SYMBOL'].nunique()}")
        print()
        
        print("Instrument Type Breakdown:")
        instrument_counts = mcx_df['SEM_INSTRUMENT_NAME'].value_counts()
        for inst_type, count in instrument_counts.items():
            print(f"  {inst_type:30} {count:6} securities")
        
        print()
        print("=" * 100)
        print("✅ DONE! Check mcx_securities.csv for full details.")
        print("=" * 100)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fetch_mcx_securities()
