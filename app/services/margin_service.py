"""
Margin calculation service for individual stock trading.
Implements Dhan's margin calculation formula and validation logic.
"""
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException, status
from app.services.dhan_service import DhanService
from app.models.user import UserInDB
import logging

logger = logging.getLogger(__name__)


class MarginService:
    """Service class for margin calculations and validations."""
    
    # Default margin percentages (can be overridden by exchange data)
    DEFAULT_EQUITY_INTRADAY_MARGIN = Decimal('20.0')  # 20% (5x leverage)
    DEFAULT_EQUITY_DELIVERY_MARGIN = Decimal('100.0')  # 100% (no leverage)
    DEFAULT_MTF_MARGIN = Decimal('25.0')  # 25% (4x leverage)
    
    # Risk management limits
    MAX_SINGLE_STOCK_EXPOSURE = Decimal('2000000')  # Rs. 20 Lakh
    MAX_MTF_FUNDING = Decimal('10000000')  # Rs. 1 Crore
    MIN_MARGIN_COVERAGE = Decimal('20.0')  # 20% minimum coverage
    
    @staticmethod
    def calculate_equity_margin(
        stock_price: float,
        quantity: int,
        product_type: str,
        var_margin: Optional[float] = None,
        elm_margin: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate margin required for equity trading.
        
        Args:
            stock_price: Current stock price
            quantity: Number of shares
            product_type: 'INTRADAY', 'CNC', or 'MTF'
            var_margin: Value at Risk margin percentage (optional)
            elm_margin: Extreme Loss Margin percentage (optional)
            
        Returns:
            Dict containing margin calculation details
        """
        try:
            # Convert to Decimal for precise calculations
            price = Decimal(str(stock_price))
            qty = Decimal(str(quantity))
            trade_value = price * qty
            
            if product_type.upper() == 'INTRADAY':
                # For intraday: VAR + ELM margin
                if var_margin is not None and elm_margin is not None:
                    total_margin_pct = Decimal(str(var_margin)) + Decimal(str(elm_margin))
                else:
                    total_margin_pct = MarginService.DEFAULT_EQUITY_INTRADAY_MARGIN
                    
                margin_required = (trade_value * total_margin_pct / Decimal('100')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                leverage = Decimal('100') / total_margin_pct
                
            elif product_type.upper() == 'CNC':
                # For delivery: 100% margin (no leverage)
                total_margin_pct = MarginService.DEFAULT_EQUITY_DELIVERY_MARGIN
                margin_required = trade_value
                leverage = Decimal('1')
                
            elif product_type.upper() == 'MTF':
                # For MTF: Based on MTF margin percentage
                total_margin_pct = MarginService.DEFAULT_MTF_MARGIN
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
            
        except Exception as e:
            logger.error(f"Error calculating equity margin: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to calculate margin: {str(e)}"
            )
    
    @staticmethod
    async def get_stock_margin_data(
        user: UserInDB,
        security_id: str,
        exchange_segment: str = "NSE_EQ"
    ) -> Dict[str, Any]:
        """
        Get margin data for a specific stock from DHAN API.
        
        Args:
            user: User with DHAN credentials
            security_id: Security ID of the stock
            exchange_segment: Exchange segment (default: NSE_EQ)
            
        Returns:
            Dict containing margin data from DHAN
        """
        try:
            # This would typically call DHAN API to get real-time margin data
            # For now, we'll return default values
            # In a real implementation, you'd call dhan.get_margin_calculator() or similar
            
            dhan = DhanService.get_dhan_client(user)
            
            # Note: DHAN API might not have a direct margin calculator endpoint
            # You might need to use their margin calculator web service or 
            # implement based on their documented formulas
            
            # For now, returning default margin data structure
            return {
                "security_id": security_id,
                "exchange_segment": exchange_segment,
                "var_margin": 15.0,  # Default VAR margin %
                "elm_margin": 5.0,   # Default ELM margin %
                "total_margin": 20.0,  # VAR + ELM
                "mtf_eligible": True,
                "mtf_margin": 25.0,
                "last_updated": "2024-11-04T10:10:00Z"
            }
            
        except Exception as e:
            logger.error(f"Error fetching margin data for {security_id}: {e}")
            # Return default values if API call fails
            return {
                "security_id": security_id,
                "exchange_segment": exchange_segment,
                "var_margin": 15.0,
                "elm_margin": 5.0,
                "total_margin": 20.0,
                "mtf_eligible": False,
                "mtf_margin": 25.0,
                "last_updated": "2024-11-04T10:10:00Z",
                "error": str(e)
            }
    
    @staticmethod
    async def validate_margin_availability(
        user: UserInDB,
        stock_price: float,
        quantity: int,
        product_type: str,
        security_id: str,
        transaction_type: str = "BUY"
    ) -> Dict[str, Any]:
        """
        Validate if sufficient margin is available for the trade.
        
        Args:
            user: User with DHAN credentials
            stock_price: Current stock price
            quantity: Number of shares
            product_type: 'INTRADAY', 'CNC', or 'MTF'
            security_id: Security ID of the stock
            transaction_type: 'BUY' or 'SELL'
            
        Returns:
            Dict containing validation result and details
        """
        try:
            # Get user's fund limits
            funds_data = await DhanService.get_funds(user)
            available_margin = Decimal(str(funds_data.get('availablecash', 0)))
            
            # Get margin data for the stock
            margin_data = await MarginService.get_stock_margin_data(
                user, security_id
            )
            
            # Calculate required margin
            margin_calc = MarginService.calculate_equity_margin(
                stock_price=stock_price,
                quantity=quantity,
                product_type=product_type,
                var_margin=margin_data.get('var_margin'),
                elm_margin=margin_data.get('elm_margin')
            )
            
            required_margin = Decimal(str(margin_calc['margin_required']))
            trade_value = Decimal(str(margin_calc['trade_value']))
            
            # Validation checks
            validations = {
                "sufficient_margin": available_margin >= required_margin,
                "within_exposure_limit": trade_value <= MarginService.MAX_SINGLE_STOCK_EXPOSURE,
                "mtf_eligible": margin_data.get('mtf_eligible', False) if product_type.upper() == 'MTF' else True,
                "valid_product_type": product_type.upper() in ['INTRADAY', 'CNC', 'MTF']
            }
            
            # Overall validation result
            is_valid = all(validations.values())
            
            # Calculate margin utilization
            margin_utilization = (required_margin / available_margin * Decimal('100')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ) if available_margin > 0 else Decimal('100')
            
            # Prepare validation messages
            messages = []
            if not validations["sufficient_margin"]:
                shortage = required_margin - available_margin
                messages.append(f"Insufficient margin. Shortage: ₹{float(shortage):,.2f}")
            
            if not validations["within_exposure_limit"]:
                messages.append(f"Trade value exceeds single stock limit of ₹{float(MarginService.MAX_SINGLE_STOCK_EXPOSURE):,.2f}")
            
            if not validations["mtf_eligible"] and product_type.upper() == 'MTF':
                messages.append("Stock not eligible for MTF trading")
            
            if not validations["valid_product_type"]:
                messages.append(f"Invalid product type: {product_type}")
            
            if not messages:
                messages.append("All validations passed. Trade can be executed.")
            
            return {
                "is_valid": is_valid,
                "available_margin": float(available_margin),
                "required_margin": float(required_margin),
                "margin_utilization": float(margin_utilization),
                "trade_details": margin_calc,
                "validations": validations,
                "messages": messages,
                "can_sell": transaction_type.upper() == "SELL" or is_valid,
                "timestamp": "2024-11-04T10:10:00Z"
            }
            
        except Exception as e:
            logger.error(f"Error validating margin availability: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to validate margin: {str(e)}"
            )
    
    @staticmethod
    def calculate_mtf_interest(
        funded_amount: float,
        days: int = 1
    ) -> Dict[str, Any]:
        """
        Calculate MTF interest charges based on Dhan's interest slabs.
        
        Args:
            funded_amount: Amount funded through MTF
            days: Number of days (default: 1)
            
        Returns:
            Dict containing interest calculation details
        """
        try:
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
            
        except Exception as e:
            logger.error(f"Error calculating MTF interest: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to calculate MTF interest: {str(e)}"
            )
    
    @staticmethod
    async def get_portfolio_margin_summary(user: UserInDB) -> Dict[str, Any]:
        """
        Get comprehensive margin summary for user's portfolio.
        
        Args:
            user: User with DHAN credentials
            
        Returns:
            Dict containing portfolio margin summary
        """
        try:
            # Get user's funds, positions, and holdings
            funds_data = await DhanService.get_funds(user)
            positions_data = await DhanService.get_positions(user)
            holdings_data = await DhanService.get_holdings(user)
            
            available_cash = Decimal(str(funds_data.get('availablecash', 0)))
            used_margin = Decimal(str(funds_data.get('utilisedmargin', 0)))
            total_margin = available_cash + used_margin
            
            # Calculate margin utilization
            margin_utilization = (used_margin / total_margin * Decimal('100')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ) if total_margin > 0 else Decimal('0')
            
            # Count positions and holdings
            open_positions = len(positions_data.get('data', [])) if positions_data.get('data') else 0
            total_holdings = len(holdings_data.get('data', [])) if holdings_data.get('data') else 0
            
            return {
                "total_margin": float(total_margin),
                "available_margin": float(available_cash),
                "used_margin": float(used_margin),
                "margin_utilization": float(margin_utilization),
                "open_positions": open_positions,
                "total_holdings": total_holdings,
                "max_exposure_limit": float(MarginService.MAX_SINGLE_STOCK_EXPOSURE),
                "max_mtf_limit": float(MarginService.MAX_MTF_FUNDING),
                "min_coverage_required": float(MarginService.MIN_MARGIN_COVERAGE),
                "timestamp": "2024-11-04T10:10:00Z"
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio margin summary: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get portfolio margin summary: {str(e)}"
            )
