"""
Standalone script to fetch MCX commodity security IDs from DHAN API
No app dependencies required - just dhanhq library
"""

from dhanhq import dhanhq
import pandas as pd
import os
from pathlib import Path

# DHAN API Credentials - Update these with your credentials
DHAN_CLIENT_ID = os.getenv("DHAN_MASTER_CLIENT_ID", "YOUR_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_MASTER_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")

def fetch_mcx_securities():
    """Fetch and display all MCX commodity securities from DHAN"""
    
    print("=" * 100)
    print("🏭 FETCHING MCX COMMODITY SECURITIES FROM DHAN API")
    print("=" * 100)
    print()
    
    # Check credentials
    if DHAN_CLIENT_ID == "YOUR_CLIENT_ID" or DHAN_ACCESS_TOKEN == "YOUR_ACCESS_TOKEN":
        print("⚠️  WARNING: Using placeholder credentials!")
        print("Please set environment variables:")
        print("  DHAN_MASTER_CLIENT_ID")
        print("  DHAN_MASTER_ACCESS_TOKEN")
        print()
        print("Or edit this script to add your credentials directly.")
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
        
        # Show available columns
        print("📋 Available columns in security list:")
        print(security_df.columns.tolist())
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
                      'ALUMINIUM', 'LEAD', 'NICKEL', 'GOLDM', 'SILVERM']
        
        print("Searching for commodity contracts...")
        print()
        
        commodity_results = {}
        
        for commodity in commodities:
            # Search in trading symbol
            matches = mcx_df[mcx_df['SEM_TRADING_SYMBOL'].str.contains(commodity, case=False, na=False)]
            
            if not matches.empty:
                print(f"🔸 {commodity}:")
                print(f"   Found {len(matches)} contracts")
                
                # Group by instrument type
                inst_types = matches['SEM_INSTRUMENT_NAME'].unique()
                print(f"   Instrument types: {list(inst_types)}")
                
                # Show first few contracts
                for _, row in matches.head(3).iterrows():
                    print(f"   ├─ Security ID: {row['SEM_SMST_SECURITY_ID']}")
                    print(f"   │  Symbol:      {row['SEM_TRADING_SYMBOL']}")
                    print(f"   │  Instrument:  {row['SEM_INSTRUMENT_NAME']}")
                    print(f"   │  Expiry:      {row.get('SEM_EXPIRY_DATE', 'N/A')}")
                    print(f"   │  Lot Size:    {row.get('SEM_LOT_UNITS', 'N/A')}")
                    print()
                
                # Store for later
                commodity_results[commodity] = matches
        
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
        print("✅ DONE!")
        print("=" * 100)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fetch_mcx_securities()
