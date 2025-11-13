"""
API router for margin calculation and validation endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, Optional
from app.models.margin import (
    MarginCalculationRequest, MarginCalculationResponse,
    MarginValidationRequest, MarginValidationResponse,
    StockMarginData, MTFInterestRequest, MTFInterestResponse,
    PortfolioMarginSummary, BulkMarginCalculationRequest,
    BulkMarginCalculationResponse
)
from app.models.user import UserInDB
from app.services.margin_service import MarginService
from app.api.deps import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/margin", tags=["Margin"])


@router.post("/calculate", response_model=MarginCalculationResponse)
async def calculate_margin(
    request: MarginCalculationRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Calculate margin required for a stock trade.
    
    This endpoint calculates the margin required based on:
    - Stock price and quantity
    - Product type (INTRADAY, CNC, MTF)
    - Current VAR and ELM margins for the stock
    """
    try:
        # Get margin data for the stock
        margin_data = await MarginService.get_stock_margin_data(
            user=current_user,
            security_id=request.security_id,
            exchange_segment=request.exchange_segment
        )
        
        # Calculate margin
        result = MarginService.calculate_equity_margin(
            stock_price=request.stock_price,
            quantity=request.quantity,
            product_type=request.product_type.value,
            var_margin=margin_data.get('var_margin'),
            elm_margin=margin_data.get('elm_margin')
        )
        
        return MarginCalculationResponse(**result)
        
    except Exception as e:
        logger.error(f"Error calculating margin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate margin: {str(e)}"
        )


@router.post("/validate", response_model=MarginValidationResponse)
async def validate_margin(
    request: MarginValidationRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Validate if sufficient margin is available for a trade.
    
    This endpoint checks:
    - Available margin in user's account
    - Required margin for the trade
    - Risk management limits
    - Stock eligibility for the product type
    """
    try:
        result = await MarginService.validate_margin_availability(
            user=current_user,
            stock_price=request.stock_price,
            quantity=request.quantity,
            product_type=request.product_type.value,
            security_id=request.security_id,
            transaction_type=request.transaction_type.value
        )
        
        return MarginValidationResponse(**result)
        
    except Exception as e:
        logger.error(f"Error validating margin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate margin: {str(e)}"
        )


@router.get("/stock/{security_id}", response_model=StockMarginData)
async def get_stock_margin_data(
    security_id: str,
    exchange_segment: str = Query("NSE_EQ", description="Exchange segment"),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get margin data for a specific stock.
    
    Returns VAR, ELM, and MTF margin percentages for the stock.
    """
    try:
        result = await MarginService.get_stock_margin_data(
            user=current_user,
            security_id=security_id,
            exchange_segment=exchange_segment
        )
        
        return StockMarginData(**result)
        
    except Exception as e:
        logger.error(f"Error getting stock margin data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stock margin data: {str(e)}"
        )


@router.post("/mtf/interest", response_model=MTFInterestResponse)
async def calculate_mtf_interest(
    request: MTFInterestRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Calculate MTF interest charges based on funded amount and duration.
    
    Uses Dhan's interest slab structure:
    - Up to ₹5L: 12.49% p.a.
    - ₹5L to ₹10L: 13.49% p.a.
    - ₹10L to ₹25L: 14.49% p.a.
    - ₹25L to ₹50L: 15.49% p.a.
    - Above ₹50L: 16.49% p.a.
    """
    try:
        result = MarginService.calculate_mtf_interest(
            funded_amount=request.funded_amount,
            days=request.days
        )
        
        return MTFInterestResponse(**result)
        
    except Exception as e:
        logger.error(f"Error calculating MTF interest: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate MTF interest: {str(e)}"
        )


@router.get("/portfolio/summary", response_model=PortfolioMarginSummary)
async def get_portfolio_margin_summary(
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get comprehensive margin summary for user's portfolio.
    
    Includes:
    - Total and available margin
    - Current utilization
    - Open positions and holdings count
    - Risk management limits
    """
    try:
        result = await MarginService.get_portfolio_margin_summary(current_user)
        return PortfolioMarginSummary(**result)
        
    except Exception as e:
        logger.error(f"Error getting portfolio margin summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolio margin summary: {str(e)}"
        )


@router.post("/bulk/calculate", response_model=BulkMarginCalculationResponse)
async def bulk_calculate_margin(
    request: BulkMarginCalculationRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Calculate margin for multiple trades in a single request.
    
    Useful for portfolio analysis and batch trade planning.
    Maximum 50 trades per request.
    """
    try:
        calculations = []
        errors = []
        successful_count = 0
        total_margin = 0.0
        
        for i, trade in enumerate(request.trades):
            try:
                # Get margin data for the stock
                margin_data = await MarginService.get_stock_margin_data(
                    user=current_user,
                    security_id=trade.security_id,
                    exchange_segment=trade.exchange_segment
                )
                
                # Calculate margin
                result = MarginService.calculate_equity_margin(
                    stock_price=trade.stock_price,
                    quantity=trade.quantity,
                    product_type=trade.product_type.value,
                    var_margin=margin_data.get('var_margin'),
                    elm_margin=margin_data.get('elm_margin')
                )
                
                calculations.append(MarginCalculationResponse(**result))
                total_margin += result['margin_required']
                successful_count += 1
                
            except Exception as e:
                errors.append({
                    "trade_index": i,
                    "security_id": trade.security_id,
                    "error": str(e)
                })
        
        return BulkMarginCalculationResponse(
            total_trades=len(request.trades),
            successful_calculations=successful_count,
            failed_calculations=len(errors),
            total_margin_required=total_margin,
            calculations=calculations,
            errors=errors
        )
        
    except Exception as e:
        logger.error(f"Error in bulk margin calculation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate bulk margins: {str(e)}"
        )


@router.get("/limits")
async def get_margin_limits(
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get current margin limits and risk management parameters.
    """
    try:
        return {
            "max_single_stock_exposure": float(MarginService.MAX_SINGLE_STOCK_EXPOSURE),
            "max_mtf_funding": float(MarginService.MAX_MTF_FUNDING),
            "min_margin_coverage": float(MarginService.MIN_MARGIN_COVERAGE),
            "default_intraday_margin": float(MarginService.DEFAULT_EQUITY_INTRADAY_MARGIN),
            "default_delivery_margin": float(MarginService.DEFAULT_EQUITY_DELIVERY_MARGIN),
            "default_mtf_margin": float(MarginService.DEFAULT_MTF_MARGIN),
            "mtf_interest_slabs": [
                {"limit": 500000, "rate": 12.49, "description": "Up to ₹5 Lakh"},
                {"limit": 1000000, "rate": 13.49, "description": "₹5L to ₹10L"},
                {"limit": 2500000, "rate": 14.49, "description": "₹10L to ₹25L"},
                {"limit": 5000000, "rate": 15.49, "description": "₹25L to ₹50L"},
                {"limit": float('inf'), "rate": 16.49, "description": "Above ₹50L"}
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting margin limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get margin limits: {str(e)}"
        )


@router.get("/health")
async def margin_service_health():
    """
    Health check endpoint for margin service.
    """
    return {
        "status": "healthy",
        "service": "margin_service",
        "version": "1.0.0",
        "features": [
            "margin_calculation",
            "margin_validation", 
            "mtf_interest_calculation",
            "portfolio_summary",
            "bulk_calculations",
            "stock_margin_data"
        ]
    }
