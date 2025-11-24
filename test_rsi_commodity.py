"""
Test script to demonstrate RSI calculation for commodities
Shows RSI values for Crude Oil with sample data
"""

import asyncio
import logging
from datetime import datetime
from app.services.commodity_options_service import CommodityOptionsService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_rsi_calculation():
    """Test RSI calculation with sample commodity data"""
    
    print("\n" + "="*70)
    print("🧪 RSI CALCULATION TEST FOR CRUDE OIL")
    print("="*70)
    
    # Sample callback to receive snapshots
    async def print_snapshot(snapshot):
        """Print snapshot with RSI data"""
        if snapshot.get("type") == "snapshot":
            print(f"\n📊 Commodity: {snapshot['name']} ({snapshot['commodity']})")
            print(f"💰 Spot Price: ₹{snapshot['spot']:.2f}")
            print(f"📅 Expiry: {snapshot.get('expiry', 'N/A')}")
            
            rsi_data = snapshot.get('rsi', {})
            if rsi_data.get('value'):
                print(f"\n📈 RSI INDICATORS:")
                print(f"   RSI({rsi_data['period']}): {rsi_data['value']:.2f}")
                print(f"   Signal: {rsi_data['signal']}")
                
                # Interpretation
                if rsi_data['signal'] == 'OVERSOLD':
                    print(f"   💡 Interpretation: Market is OVERSOLD (RSI < 30) - Potential BUY opportunity")
                elif rsi_data['signal'] == 'OVERBOUGHT':
                    print(f"   💡 Interpretation: Market is OVERBOUGHT (RSI > 70) - Potential SELL opportunity")
                else:
                    print(f"   💡 Interpretation: Market is NEUTRAL (30 < RSI < 70) - No strong signal")
            else:
                print(f"\n⏳ RSI: Collecting historical data...")
            
            print(f"\n⏰ Timestamp: {snapshot['ts']}")
            print(f"📦 Option Strikes: {len(snapshot.get('rows', []))} strikes")
            
        elif snapshot.get("type") == "error":
            print(f"\n❌ Error: {snapshot['message']}")
            print(f"   Details: {snapshot.get('details', 'N/A')}")
    
    try:
        # Test with different RSI periods
        for rsi_period in [14, 9, 21]:
            print(f"\n{'='*70}")
            print(f"Testing with RSI Period: {rsi_period}")
            print(f"{'='*70}")
            
            # Create service instance
            service = CommodityOptionsService(
                commodity="CRUDEOIL",
                strikes_each_side=5,
                send_callback=print_snapshot,
                rsi_period=rsi_period
            )
            
            # Start service
            await service.start()
            
            # Let it run for a few seconds to fetch data
            await asyncio.sleep(10)
            
            # Stop service
            await service.stop()
            
            print(f"\n✅ Test completed for RSI({rsi_period})")
            
            # Wait before next test
            if rsi_period != 21:
                await asyncio.sleep(2)
        
        print("\n" + "="*70)
        print("🎉 ALL RSI TESTS COMPLETED")
        print("="*70)
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)


async def test_rsi_formula():
    """Test RSI calculation formula with known data"""
    
    print("\n" + "="*70)
    print("🧮 RSI FORMULA TEST WITH SAMPLE DATA")
    print("="*70)
    
    # Sample closing prices (14 days + 1 for calculation)
    sample_closes = [
        6500, 6520, 6510, 6530, 6540, 6535, 6550, 6560,
        6555, 6570, 6580, 6575, 6590, 6600, 6595
    ]
    
    print(f"\n📊 Sample Closing Prices (15 days):")
    print(f"   {sample_closes}")
    
    # Create a service instance just to use the RSI calculation method
    service = CommodityOptionsService(commodity="CRUDEOIL")
    
    # Calculate RSI
    rsi = service._calculate_rsi(sample_closes, period=14)
    
    print(f"\n📈 RSI Calculation Results:")
    print(f"   Period: 14")
    print(f"   RSI Value: {rsi:.2f}")
    
    if rsi < 30:
        print(f"   Signal: OVERSOLD 🔴")
    elif rsi > 70:
        print(f"   Signal: OVERBOUGHT 🔴")
    else:
        print(f"   Signal: NEUTRAL 🟢")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    print("\n🚀 Starting RSI Tests for Commodity Options Service")
    print("="*70)
    
    # Run formula test first (no API calls)
    asyncio.run(test_rsi_formula())
    
    # Then run live test (requires valid DHAN credentials)
    print("\n\n⚠️  Note: Live test requires valid DHAN credentials in .env file")
    print("Press Ctrl+C to skip live test, or wait 5 seconds to continue...")
    
    try:
        import time
        time.sleep(5)
        asyncio.run(test_rsi_calculation())
    except KeyboardInterrupt:
        print("\n\n⏭️  Skipped live test")
    
    print("\n✅ All tests completed!\n")
