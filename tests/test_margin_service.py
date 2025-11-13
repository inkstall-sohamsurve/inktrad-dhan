"""
Test cases for margin calculation service.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.margin_service import MarginService
from app.models.margin import ProductType


def test_equity_margin_calculations():
    """Test equity margin calculations for different product types."""
    print("=" * 60)
    print("🧮 TESTING EQUITY MARGIN CALCULATIONS")
    print("=" * 60)
    
    # Test data
    stock_price = 2500.50
    quantity = 10
    
    print(f"\n📊 Stock: ₹{stock_price} | Quantity: {quantity}")
    print(f"📈 Trade Value: ₹{stock_price * quantity:,.2f}")
    print("-" * 40)
    
    # Test INTRADAY margin calculation
    print("\n🔸 INTRADAY Trading:")
    intraday_result = MarginService.calculate_equity_margin(
        stock_price=stock_price,
        quantity=quantity,
        product_type="INTRADAY",
        var_margin=15.0,
        elm_margin=5.0
    )
    
    print(f"  VAR Margin: {intraday_result['var_margin']}%")
    print(f"  ELM Margin: {intraday_result['elm_margin']}%")
    print(f"  Total Margin: {intraday_result['margin_percentage']}%")
    print(f"  Margin Required: ₹{intraday_result['margin_required']:,.2f}")
    print(f"  Leverage: {intraday_result['leverage']:.2f}x")
    
    # Test CNC (Delivery) margin calculation
    print("\n🔸 CNC (Delivery) Trading:")
    cnc_result = MarginService.calculate_equity_margin(
        stock_price=stock_price,
        quantity=quantity,
        product_type="CNC"
    )
    
    print(f"  Margin Required: ₹{cnc_result['margin_required']:,.2f}")
    print(f"  Margin Percentage: {cnc_result['margin_percentage']}%")
    print(f"  Leverage: {cnc_result['leverage']:.2f}x")
    
    # Test MTF margin calculation
    print("\n🔸 MTF (Margin Trading Facility):")
    mtf_result = MarginService.calculate_equity_margin(
        stock_price=stock_price,
        quantity=quantity,
        product_type="MTF"
    )
    
    print(f"  Margin Required: ₹{mtf_result['margin_required']:,.2f}")
    print(f"  Margin Percentage: {mtf_result['margin_percentage']}%")
    print(f"  Leverage: {mtf_result['leverage']:.2f}x")
    
    return {
        "intraday": intraday_result,
        "cnc": cnc_result,
        "mtf": mtf_result
    }


def test_mtf_interest_calculations():
    """Test MTF interest calculations for different amounts and durations."""
    print("\n" + "=" * 60)
    print("💰 TESTING MTF INTEREST CALCULATIONS")
    print("=" * 60)
    
    test_amounts = [100000, 750000, 1500000, 3000000, 6000000]  # Different slabs
    test_days = [1, 7, 30, 90]
    
    for amount in test_amounts:
        print(f"\n💵 Funded Amount: ₹{amount:,.2f}")
        print("-" * 30)
        
        for days in test_days:
            result = MarginService.calculate_mtf_interest(
                funded_amount=amount,
                days=days
            )
            
            print(f"  {days:2d} days: Interest Rate {result['interest_rate_pa']:5.2f}% p.a. | "
                  f"Total Interest: ₹{result['total_interest']:8.2f}")


def test_margin_validation_scenarios():
    """Test different margin validation scenarios."""
    print("\n" + "=" * 60)
    print("✅ TESTING MARGIN VALIDATION SCENARIOS")
    print("=" * 60)
    
    # Mock user funds data
    mock_funds = {
        'availablecash': 50000,  # ₹50,000 available
        'utilisedmargin': 30000   # ₹30,000 used
    }
    
    scenarios = [
        {
            "name": "✅ Valid Intraday Trade",
            "stock_price": 1000,
            "quantity": 5,
            "product_type": "INTRADAY",
            "expected_valid": True
        },
        {
            "name": "❌ Insufficient Margin",
            "stock_price": 5000,
            "quantity": 20,
            "product_type": "INTRADAY",
            "expected_valid": False
        },
        {
            "name": "✅ Small CNC Trade",
            "stock_price": 500,
            "quantity": 10,
            "product_type": "CNC",
            "expected_valid": False  # CNC requires 100% margin
        },
        {
            "name": "✅ MTF Trade",
            "stock_price": 2000,
            "quantity": 10,
            "product_type": "MTF",
            "expected_valid": True
        }
    ]
    
    for scenario in scenarios:
        print(f"\n🔍 {scenario['name']}")
        print(f"   Stock: ₹{scenario['stock_price']} x {scenario['quantity']} = ₹{scenario['stock_price'] * scenario['quantity']:,.2f}")
        
        # Calculate margin
        margin_calc = MarginService.calculate_equity_margin(
            stock_price=scenario['stock_price'],
            quantity=scenario['quantity'],
            product_type=scenario['product_type']
        )
        
        required_margin = margin_calc['margin_required']
        available_margin = mock_funds['availablecash']
        
        is_sufficient = available_margin >= required_margin
        
        print(f"   Required Margin: ₹{required_margin:,.2f}")
        print(f"   Available Margin: ₹{available_margin:,.2f}")
        print(f"   Status: {'✅ VALID' if is_sufficient else '❌ INVALID'}")
        
        if not is_sufficient:
            shortage = required_margin - available_margin
            print(f"   Shortage: ₹{shortage:,.2f}")


def test_risk_management_limits():
    """Test risk management limits and validations."""
    print("\n" + "=" * 60)
    print("⚠️  TESTING RISK MANAGEMENT LIMITS")
    print("=" * 60)
    
    # Test single stock exposure limit
    print(f"\n📊 Single Stock Exposure Limit: ₹{float(MarginService.MAX_SINGLE_STOCK_EXPOSURE):,.2f}")
    
    high_value_trades = [
        {"price": 5000, "quantity": 500, "value": 2500000},  # ₹25L - Exceeds limit
        {"price": 2000, "quantity": 800, "value": 1600000},  # ₹16L - Within limit
        {"price": 10000, "quantity": 250, "value": 2500000}  # ₹25L - Exceeds limit
    ]
    
    for trade in high_value_trades:
        trade_value = trade['price'] * trade['quantity']
        within_limit = trade_value <= float(MarginService.MAX_SINGLE_STOCK_EXPOSURE)
        
        print(f"   Trade: ₹{trade['price']} x {trade['quantity']} = ₹{trade_value:,.2f} "
              f"{'✅' if within_limit else '❌'}")
    
    # Test MTF funding limit
    print(f"\n💰 MTF Funding Limit: ₹{float(MarginService.MAX_MTF_FUNDING):,.2f}")
    print(f"   Minimum Coverage: {float(MarginService.MIN_MARGIN_COVERAGE)}%")


def demonstrate_margin_calculator():
    """Demonstrate the complete margin calculator functionality."""
    print("\n" + "=" * 80)
    print("🚀 INKTRAD MARGIN CALCULATOR DEMONSTRATION")
    print("=" * 80)
    
    print("\n📋 This margin calculator implements Dhan's margin calculation formula:")
    print("   • Equity Intraday: VAR + ELM margin")
    print("   • Equity Delivery: 100% margin (no leverage)")
    print("   • MTF: Configurable margin with interest charges")
    print("   • Risk management limits and validations")
    
    # Run all tests
    margin_results = test_equity_margin_calculations()
    test_mtf_interest_calculations()
    test_margin_validation_scenarios()
    test_risk_management_limits()
    
    print("\n" + "=" * 80)
    print("✅ MARGIN CALCULATOR DEMONSTRATION COMPLETED")
    print("=" * 80)
    
    print("\n📊 SUMMARY:")
    print(f"   • Intraday Leverage: {margin_results['intraday']['leverage']:.1f}x")
    print(f"   • CNC Leverage: {margin_results['cnc']['leverage']:.1f}x")
    print(f"   • MTF Leverage: {margin_results['mtf']['leverage']:.1f}x")
    
    print("\n🔗 API Endpoints Available:")
    endpoints = [
        "POST /api/v1/margin/calculate",
        "POST /api/v1/margin/validate", 
        "GET  /api/v1/margin/stock/{security_id}",
        "POST /api/v1/margin/mtf/interest",
        "GET  /api/v1/margin/portfolio/summary",
        "POST /api/v1/margin/bulk/calculate"
    ]
    
    for endpoint in endpoints:
        print(f"   • {endpoint}")
    
    print(f"\n📖 Documentation: http://localhost:8000/docs")
    print(f"🧪 Test the API: http://localhost:8000/api/features")


if __name__ == "__main__":
    try:
        demonstrate_margin_calculator()
    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
