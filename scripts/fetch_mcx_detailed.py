"""
Script to fetch MCX commodity security IDs from DHAN API
Detailed analysis of segment 'M' (MCX)
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

def fetch_mcx_securities():
    """Fetch and display MCX commodity securities"""
    
    print("=" * 100)
    print("🏭 FETCHING MCX COMMODITY SECURITIES FROM DHAN API")
    print("=" * 100)
    print()
    
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        print("❌ ERROR: DHAN credentials not found in .env file")
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
        
        # Check segment M (MCX)
        print("🔍 Analyzing Segment 'M' (MCX)...")
        mcx_df = security_df[security_df['SEM_SEGMENT'] == 'M']
        
        if mcx_df.empty:
            print("❌ No securities in segment M")
            return
        
        print(f"✅ Found {len(mcx_df)} securities in segment M")
        print()
        
        # Show instrument types
        print("📊 Instrument Types in Segment M:")
        print("-" * 80)
        inst_counts = mcx_df['SEM_INSTRUMENT_NAME'].value_counts()
        for inst_type, count in inst_counts.items():
            print(f"  {inst_type:40} {count:6} securities")
        print()
        
        # Show exchange info
        print("📊 Exchange Info:")
        print(f"  Exchange IDs: {mcx_df['SEM_EXM_EXCH_ID'].unique()}")
        print()
        
        # Search for specific commodities
        commodities = ['CRUDEOIL', 'GOLD', 'SILVER', 'NATURALGAS', 'COPPER', 'ZINC']
        
        print("=" * 100)
        print("🎯 SEARCHING FOR MAJOR COMMODITIES")
        print("=" * 100)
        print()
        
        for commodity in commodities:
            matches = mcx_df[mcx_df['SEM_TRADING_SYMBOL'].str.contains(commodity, case=False, na=False)]
            
            if not matches.empty:
                print(f"🔸 {commodity}: {len(matches)} contracts found")
                print("-" * 80)
                
                # Group by instrument type
                for inst_type in matches['SEM_INSTRUMENT_NAME'].unique():
                    inst_matches = matches[matches['SEM_INSTRUMENT_NAME'] == inst_type]
                    print(f"\n   📌 {inst_type} ({len(inst_matches)} contracts):")
                    
                    # Show first 3 examples
                    for idx, (_, row) in enumerate(inst_matches.head(3).iterrows()):
                        print(f"      Example {idx+1}:")
                        print(f"        Security ID:  {row['SEM_SMST_SECURITY_ID']}")
                        print(f"        Symbol:       {row['SEM_TRADING_SYMBOL']}")
                        print(f"        Expiry:       {row.get('SEM_EXPIRY_DATE', 'N/A')}")
                        print(f"        Strike:       {row.get('SEM_STRIKE_PRICE', 'N/A')}")
                        print(f"        Option Type:  {row.get('SEM_OPTION_TYPE', 'N/A')}")
                        print(f"        Lot Size:     {row.get('SEM_LOT_UNITS', 'N/A')}")
                        
                        # Check for underlying security ID
                        if 'UNDERLYING_SECURITY_ID' in row and pd.notna(row['UNDERLYING_SECURITY_ID']):
                            print(f"        Underlying:   {row['UNDERLYING_SECURITY_ID']}")
                        print()
                
                print()
        
        # Find futures contracts (for option chain underlying)
        print("=" * 100)
        print("🎯 FUTURES CONTRACTS (for Option Chain Underlying)")
        print("=" * 100)
        print()
        
        futures_df = mcx_df[mcx_df['SEM_INSTRUMENT_NAME'].str.contains('FUTCOM', case=False, na=False)]
        
        if not futures_df.empty:
            print(f"Found {len(futures_df)} FUTCOM contracts")
            print()
            
            for commodity in commodities:
                fut_matches = futures_df[futures_df['SEM_TRADING_SYMBOL'].str.contains(commodity, case=False, na=False)]
                
                if not fut_matches.empty:
                    # Sort by expiry to get nearest
                    if 'SEM_EXPIRY_DATE' in fut_matches.columns:
                        fut_sorted = fut_matches.sort_values('SEM_EXPIRY_DATE')
                        nearest = fut_sorted.iloc[0]
                        
                        print(f"✅ {commodity}:")
                        print(f"   Security ID:  {nearest['SEM_SMST_SECURITY_ID']}")
                        print(f"   Symbol:       {nearest['SEM_TRADING_SYMBOL']}")
                        print(f"   Expiry:       {nearest['SEM_EXPIRY_DATE']}")
                        print(f"   Lot Size:     {nearest.get('SEM_LOT_UNITS', 'N/A')}")
                        print()
        
        # Check for options
        print("=" * 100)
        print("🎯 OPTION CONTRACTS")
        print("=" * 100)
        print()
        
        options_df = mcx_df[mcx_df['SEM_INSTRUMENT_NAME'].str.contains('OPT', case=False, na=False)]
        
        if not options_df.empty:
            print(f"Found {len(options_df)} option contracts")
            print()
            
            # Check if UNDERLYING_SECURITY_ID exists
            if 'UNDERLYING_SECURITY_ID' in options_df.columns:
                print("✅ UNDERLYING_SECURITY_ID column exists!")
                
                for commodity in commodities:
                    opt_matches = options_df[options_df['SEM_TRADING_SYMBOL'].str.contains(commodity, case=False, na=False)]
                    
                    if not opt_matches.empty:
                        underlying_ids = opt_matches['UNDERLYING_SECURITY_ID'].dropna().unique()
                        print(f"\n{commodity} Options:")
                        print(f"  Total contracts: {len(opt_matches)}")
                        print(f"  Underlying IDs:  {underlying_ids}")
            else:
                print("⚠️  UNDERLYING_SECURITY_ID column not found")
        
        # Save full MCX data
        output_file = Path(__file__).parent / "mcx_securities_full.csv"
        mcx_df.to_csv(output_file, index=False)
        print()
        print(f"💾 Full MCX data saved to: {output_file}")
        
        # Create summary for commodity options
        print()
        print("=" * 100)
        print("📋 SUMMARY FOR COMMODITY OPTIONS SERVICE")
        print("=" * 100)
        print()
        
        print("Use these Security IDs for option_chain API:")
        print()
        
        for commodity in commodities:
            # Find futures contract (underlying for options)
            fut_matches = futures_df[futures_df['SEM_TRADING_SYMBOL'].str.contains(commodity, case=False, na=False)]
            
            if not fut_matches.empty:
                fut_sorted = fut_matches.sort_values('SEM_EXPIRY_DATE')
                nearest = fut_sorted.iloc[0]
                
                print(f"{commodity:15} Security ID: {nearest['SEM_SMST_SECURITY_ID']:10} | Segment: M | Expiry: {nearest['SEM_EXPIRY_DATE']}")
        
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
