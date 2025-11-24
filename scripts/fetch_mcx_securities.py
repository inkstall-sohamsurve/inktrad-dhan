"""
Script to fetch MCX commodity security IDs from DHAN API
This will help identify the correct security IDs for commodity options trading
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dhanhq import dhanhq
from app.core.config import settings
import pandas as pd

def fetch_mcx_securities():
    """Fetch and display all MCX commodity securities from DHAN"""
    
    print("=" * 100)
    print("🏭 FETCHING MCX COMMODITY SECURITIES FROM DHAN API")
    print("=" * 100)
    print()
    
    try:
        # Initialize DHAN client
        print("📡 Connecting to DHAN API...")
        dhan = dhanhq(settings.DHAN_MASTER_CLIENT_ID, settings.DHAN_MASTER_ACCESS_TOKEN)
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
        
        # Filter for MCX segment
        print("🔍 Filtering for MCX commodities...")
        mcx_df = security_df[security_df['SEM_SEGMENT'] == 'MCX_COMM']
        
        if mcx_df.empty:
            print("❌ No MCX_COMM securities found. Checking available segments...")
            unique_segments = security_df['SEM_SEGMENT'].unique()
            print(f"Available segments: {sorted(unique_segments)}")
            
            # Try MCX related segments
            mcx_related = [seg for seg in unique_segments if 'MCX' in seg]
            if mcx_related:
                print(f"\n🔍 Found MCX-related segments: {mcx_related}")
                print("Fetching all MCX-related securities...")
                mcx_df = security_df[security_df['SEM_SEGMENT'].isin(mcx_related)]
        
        if mcx_df.empty:
            print("❌ No MCX securities found in any segment")
            return
        
        print(f"✅ Found {len(mcx_df)} MCX securities")
        print()
        
        # Group by instrument type
        print("📊 MCX Securities by Instrument Type:")
        print("-" * 100)
        
        instrument_groups = mcx_df.groupby('SEM_INSTRUMENT_NAME')
        
        for instrument_type, group in instrument_groups:
            print(f"\n🔹 {instrument_type} ({len(group)} securities)")
            print("-" * 100)
            
            # Display relevant columns
            display_df = group[[
                'SEM_SMST_SECURITY_ID',
                'SEM_TRADING_SYMBOL',
                'SEM_CUSTOM_SYMBOL',
                'SEM_EXPIRY_DATE',
                'SEM_STRIKE_PRICE',
                'SEM_OPTION_TYPE',
                'SEM_LOT_UNITS'
            ]].copy()
            
            # Rename for better readability
            display_df.columns = ['Security_ID', 'Trading_Symbol', 'Custom_Symbol', 'Expiry', 'Strike', 'Option_Type', 'Lot_Size']
            
            # Show first 20 rows
            print(display_df.head(20).to_string(index=False))
            
            if len(group) > 20:
                print(f"\n... and {len(group) - 20} more")
        
        print()
        print("=" * 100)
        print("🎯 COMMODITY UNDERLYING SECURITIES (for option chain)")
        print("=" * 100)
        print()
        
        # Find underlying commodities (usually FUTCOM or similar)
        commodities = ['CRUDEOIL', 'GOLD', 'SILVER', 'NATURALGAS', 'COPPER', 'ZINC', 'ALUMINIUM', 'LEAD', 'NICKEL']
        
        print("Searching for underlying commodity securities...")
        print()
        
        for commodity in commodities:
            # Search in trading symbol
            matches = mcx_df[mcx_df['SEM_TRADING_SYMBOL'].str.contains(commodity, case=False, na=False)]
            
            if not matches.empty:
                print(f"🔸 {commodity}:")
                
                # Get unique security IDs and their details
                for _, row in matches.head(5).iterrows():
                    print(f"   Security ID: {row['SEM_SMST_SECURITY_ID']}")
                    print(f"   Symbol:      {row['SEM_TRADING_SYMBOL']}")
                    print(f"   Instrument:  {row['SEM_INSTRUMENT_NAME']}")
                    print(f"   Expiry:      {row['SEM_EXPIRY_DATE']}")
                    print(f"   Lot Size:    {row['SEM_LOT_UNITS']}")
                    print()
                
                if len(matches) > 5:
                    print(f"   ... and {len(matches) - 5} more contracts")
                    print()
        
        # Save to CSV for reference
        output_file = Path(__file__).parent / "mcx_securities.csv"
        mcx_df.to_csv(output_file, index=False)
        print(f"💾 Full MCX securities list saved to: {output_file}")
        print()
        
        # Summary statistics
        print("=" * 100)
        print("📈 SUMMARY")
        print("=" * 100)
        print(f"Total MCX Securities:     {len(mcx_df)}")
        print(f"Instrument Types:         {mcx_df['SEM_INSTRUMENT_NAME'].nunique()}")
        print(f"Unique Trading Symbols:   {mcx_df['SEM_TRADING_SYMBOL'].nunique()}")
        print(f"Segments:                 {mcx_df['SEM_SEGMENT'].unique().tolist()}")
        print()
        
        # Show instrument type breakdown
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
