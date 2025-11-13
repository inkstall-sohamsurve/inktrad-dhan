"""
Standalone test for margin calculation logic (without FastAPI dependencies).
"""
from decimal import Decimal, ROUND_HALF_UP


class StandaloneMarginCalculator:
    """Standalone margin calculator for testing purposes."""
    
    # Default margin percentages
    DEFAULT_EQUITY_INTRADAY_MARGIN = Decimal('20.0')  # 20% (5x leverage)
    DEFAULT_EQUITY_DELIVERY_MARGIN = Decimal('100.0')  # 100% (no leverage)
    DEFAULT_MTF_MARGIN = Decimal('25.0')  # 25% (4x leverage)
    
    # Risk management limits
    MAX_SINGLE_STOCK_EXPOSURE = Decimal('2000000')  # Rs. 20 Lakh
    MAX_MTF_FUNDING = Decimal('10000000')  # Rs. 1 Crore
    MIN_MARGIN_COVERAGE = Decimal('20.0')  # 20% minimum coverage
    
    @staticmethod
    def calculate_equity_margin(stock_price, quantity, product_type, var_margin=None, elm_margin=None):
        """Calculate margin required for equity trading."""
        # Convert to Decimal for precise calculations
        price = Decimal(str(stock_price))
        qty = Decimal(str(quantity))
        trade_value = price * qty
        
        if product_type.upper() == 'INTRADAY':
            # For intraday: VAR + ELM margin
            if var_margin is not None and elm_margin is not None:
                total_margin_pct = Decimal(str(var_margin)) + Decimal(str(elm_margin))
            else:
                total_margin_pct = StandaloneMarginCalculator.DEFAULT_EQUITY_INTRADAY_MARGIN
                
            margin_required = (trade_value * total_margin_pct / Decimal('100')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            leverage = Decimal('100') / total_margin_pct
            
        elif product_type.upper() == 'CNC':
            # For delivery: 100% margin (no leverage)
            total_margin_pct = StandaloneMarginCalculator.DEFAULT_EQUITY_DELIVERY_MARGIN
            margin_required = trade_value
            leverage = Decimal('1')
            
        elif product_type.upper() == 'MTF':
            # For MTF: Based on MTF margin percentage
            total_margin_pct = StandaloneMarginCalculator.DEFAULT_MTF_MARGIN
            margin_required = (trade_value * total_margin_pct / Decimal('100')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            leverage = Decimal('100') / total_margin_pct
            
        else:
            raise ValueError(f"Invalid product type: {product_type}")
        
        return {
            "stock_price": float(price),
            "quantity": int(qty),
            "trade_value": float(trade_value),
            "margin_required": float(margin_required),
            "margin_percentage": float(total_margin_pct),
            "leverage": float(leverage.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            "product_type": product_type.upper(),
            "var_margin": var_margin,
            "elm_margin": elm_margin
        }
    
    @staticmethod
    def calculate_mtf_interest(funded_amount, days=1):
        """Calculate MTF interest charges based on Dhan's interest slabs."""
        amount = Decimal(str(funded_amount))
        
        # Dhan's MTF interest slabs (per annum)
        interest_slabs = [
            (Decimal('500000'), Decimal('12.49')),      # Up to 5 Lakh: 12.49%
            (Decimal('1000000'), Decimal('13.49')),     # 5L to 10L: 13.49%
            (Decimal('2500000'), Decimal('14.49')),     # 10L to 25L: 14.49%
            (Decimal('5000000'), Decimal('15.49')),     # 25L to 50L: 15.49%
            (Decimal('999999999'), Decimal('16.49'))    # Above 50L: 16.49%
        ]
        
        # Find applicable interest rate
        interest_rate = Decimal('12.49')  # Default
        for limit, rate in interest_slabs:
            if amount <= limit:
                interest_rate = rate
                break
        
        # Calculate daily interest
        daily_rate = interest_rate / Decimal('365')
        daily_interest = (amount * daily_rate / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        total_interest = (daily_interest * Decimal(str(days))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        return {
            "funded_amount": float(amount),
            "interest_rate_pa": float(interest_rate),
            "daily_interest_rate": float(daily_rate.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)),
            "daily_interest": float(daily_interest),
            "days": days,
            "total_interest": float(total_interest),
            "total_amount": float(amount + total_interest)
        }


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
    intraday_result = StandaloneMarginCalculator.calculate_equity_margin(
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
    cnc_result = StandaloneMarginCalculator.calculate_equity_margin(
        stock_price=stock_price,
        quantity=quantity,
        product_type="CNC"
    )
    
    print(f"  Margin Required: ₹{cnc_result['margin_required']:,.2f}")
    print(f"  Margin Percentage: {cnc_result['margin_percentage']}%")
    print(f"  Leverage: {cnc_result['leverage']:.2f}x")
    
    # Test MTF margin calculation
    print("\n🔸 MTF (Margin Trading Facility):")
    mtf_result = StandaloneMarginCalculator.calculate_equity_margin(
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
            result = StandaloneMarginCalculator.calculate_mtf_interest(
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
    available_margin = 50000  # ₹50,000 available
    
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
            "name": "❌ Large CNC Trade",
            "stock_price": 500,
            "quantity": 200,
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
        margin_calc = StandaloneMarginCalculator.calculate_equity_margin(
            stock_price=scenario['stock_price'],
            quantity=scenario['quantity'],
            product_type=scenario['product_type']
        )
        
        required_margin = margin_calc['margin_required']
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
    print(f"\n📊 Single Stock Exposure Limit: ₹{float(StandaloneMarginCalculator.MAX_SINGLE_STOCK_EXPOSURE):,.2f}")
    
    high_value_trades = [
        {"price": 5000, "quantity": 500, "value": 2500000},  # ₹25L - Exceeds limit
        {"price": 2000, "quantity": 800, "value": 1600000},  # ₹16L - Within limit
        {"price": 10000, "quantity": 250, "value": 2500000}  # ₹25L - Exceeds limit
    ]
    
    for trade in high_value_trades:
        trade_value = trade['price'] * trade['quantity']
        within_limit = trade_value <= float(StandaloneMarginCalculator.MAX_SINGLE_STOCK_EXPOSURE)
        
        print(f"   Trade: ₹{trade['price']} x {trade['quantity']} = ₹{trade_value:,.2f} "
              f"{'✅' if within_limit else '❌'}")
    
    # Test MTF funding limit
    print(f"\n💰 MTF Funding Limit: ₹{float(StandaloneMarginCalculator.MAX_MTF_FUNDING):,.2f}")
    print(f"   Minimum Coverage: {float(StandaloneMarginCalculator.MIN_MARGIN_COVERAGE)}%")


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
    print(f"🧪 Test the Calculator: http://localhost:8000/test-margin")
    print(f"🧪 Test Features: http://localhost:8000/api/features")


if __name__ == "__main__":
    try:
        demonstrate_margin_calculator()
    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
