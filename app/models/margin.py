"""
Pydantic models for Margin calculations and validations.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ProductType(str, Enum):
    """Product types for margin calculation."""
    INTRADAY = "INTRADAY"
    CNC = "CNC"
    MTF = "MTF"


class TransactionType(str, Enum):
    """Transaction types."""
    BUY = "BUY"
    SELL = "SELL"


class MarginCalculationRequest(BaseModel):
    """Request model for margin calculation."""
    security_id: str = Field(..., description="Security ID of the stock")
    exchange_segment: str = Field("NSE_EQ", description="Exchange segment")
    stock_price: float = Field(..., gt=0, description="Current stock price")
    quantity: int = Field(..., gt=0, description="Number of shares")
    product_type: ProductType = Field(..., description="Product type for trading")
    
    class Config:
        json_schema_extra = {
            "example": {
                "security_id": "1333",
                "exchange_segment": "NSE_EQ",
                "stock_price": 2500.50,
                "quantity": 10,
                "product_type": "INTRADAY"
            }
        }


class MarginValidationRequest(BaseModel):
    """Request model for margin validation."""
    security_id: str = Field(..., description="Security ID of the stock")
    exchange_segment: str = Field("NSE_EQ", description="Exchange segment")
    stock_price: float = Field(..., gt=0, description="Current stock price")
    quantity: int = Field(..., gt=0, description="Number of shares")
    product_type: ProductType = Field(..., description="Product type for trading")
    transaction_type: TransactionType = Field(..., description="BUY or SELL")
    
    class Config:
        json_schema_extra = {
            "example": {
                "security_id": "1333",
                "exchange_segment": "NSE_EQ",
                "stock_price": 2500.50,
                "quantity": 10,
                "product_type": "INTRADAY",
                "transaction_type": "BUY"
            }
        }


class MarginCalculationResponse(BaseModel):
    """Response model for margin calculation."""
    stock_price: float = Field(..., description="Stock price used in calculation")
    quantity: int = Field(..., description="Quantity of shares")
    trade_value: float = Field(..., description="Total trade value")
    margin_required: float = Field(..., description="Margin required for the trade")
    margin_percentage: float = Field(..., description="Margin percentage applied")
    leverage: float = Field(..., description="Leverage available")
    product_type: str = Field(..., description="Product type")
    var_margin: Optional[float] = Field(None, description="VAR margin percentage")
    elm_margin: Optional[float] = Field(None, description="ELM margin percentage")


class MarginValidationResponse(BaseModel):
    """Response model for margin validation."""
    is_valid: bool = Field(..., description="Whether the trade is valid")
    available_margin: float = Field(..., description="Available margin in account")
    required_margin: float = Field(..., description="Required margin for trade")
    margin_utilization: float = Field(..., description="Margin utilization percentage")
    trade_details: MarginCalculationResponse = Field(..., description="Trade calculation details")
    validations: Dict[str, bool] = Field(..., description="Individual validation results")
    messages: List[str] = Field(..., description="Validation messages")
    can_sell: bool = Field(..., description="Whether selling is allowed")
    timestamp: str = Field(..., description="Validation timestamp")


class StockMarginData(BaseModel):
    """Model for stock-specific margin data."""
    security_id: str = Field(..., description="Security ID")
    exchange_segment: str = Field(..., description="Exchange segment")
    var_margin: float = Field(..., description="VAR margin percentage")
    elm_margin: float = Field(..., description="ELM margin percentage")
    total_margin: float = Field(..., description="Total margin percentage (VAR + ELM)")
    mtf_eligible: bool = Field(..., description="Whether stock is eligible for MTF")
    mtf_margin: float = Field(..., description="MTF margin percentage")
    last_updated: str = Field(..., description="Last update timestamp")
    error: Optional[str] = Field(None, description="Error message if any")


class MTFInterestRequest(BaseModel):
    """Request model for MTF interest calculation."""
    funded_amount: float = Field(..., gt=0, description="Amount funded through MTF")
    days: int = Field(1, gt=0, le=365, description="Number of days")
    
    class Config:
        json_schema_extra = {
            "example": {
                "funded_amount": 100000.0,
                "days": 7
            }
        }


class MTFInterestResponse(BaseModel):
    """Response model for MTF interest calculation."""
    funded_amount: float = Field(..., description="Funded amount")
    interest_rate_pa: float = Field(..., description="Interest rate per annum")
    daily_interest_rate: float = Field(..., description="Daily interest rate")
    daily_interest: float = Field(..., description="Daily interest amount")
    days: int = Field(..., description="Number of days")
    total_interest: float = Field(..., description="Total interest for the period")
    total_amount: float = Field(..., description="Total amount including interest")


class PortfolioMarginSummary(BaseModel):
    """Model for portfolio margin summary."""
    total_margin: float = Field(..., description="Total margin available")
    available_margin: float = Field(..., description="Available margin for new trades")
    used_margin: float = Field(..., description="Currently used margin")
    margin_utilization: float = Field(..., description="Margin utilization percentage")
    open_positions: int = Field(..., description="Number of open positions")
    total_holdings: int = Field(..., description="Number of holdings")
    max_exposure_limit: float = Field(..., description="Maximum single stock exposure limit")
    max_mtf_limit: float = Field(..., description="Maximum MTF funding limit")
    min_coverage_required: float = Field(..., description="Minimum coverage required percentage")
    timestamp: str = Field(..., description="Summary timestamp")


class MarginAlertLevel(str, Enum):
    """Margin alert levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MarginAlert(BaseModel):
    """Model for margin alerts."""
    alert_level: MarginAlertLevel = Field(..., description="Alert severity level")
    message: str = Field(..., description="Alert message")
    current_utilization: float = Field(..., description="Current margin utilization")
    threshold: float = Field(..., description="Alert threshold")
    action_required: str = Field(..., description="Recommended action")
    timestamp: str = Field(..., description="Alert timestamp")


class BulkMarginCalculationRequest(BaseModel):
    """Request model for bulk margin calculations."""
    trades: List[MarginCalculationRequest] = Field(..., description="List of trades to calculate")
    
    @validator('trades')
    def validate_trades_limit(cls, v):
        if len(v) > 50:  # Limit to 50 trades per request
            raise ValueError("Maximum 50 trades allowed per request")
        return v


class BulkMarginCalculationResponse(BaseModel):
    """Response model for bulk margin calculations."""
    total_trades: int = Field(..., description="Total number of trades")
    successful_calculations: int = Field(..., description="Number of successful calculations")
    failed_calculations: int = Field(..., description="Number of failed calculations")
    total_margin_required: float = Field(..., description="Total margin required for all trades")
    calculations: List[MarginCalculationResponse] = Field(..., description="Individual calculation results")
    errors: List[Dict[str, Any]] = Field(..., description="Errors for failed calculations")


class MarginUtilizationHistory(BaseModel):
    """Model for historical margin utilization."""
    date: str = Field(..., description="Date of the record")
    total_margin: float = Field(..., description="Total margin available")
    used_margin: float = Field(..., description="Used margin")
    utilization_percentage: float = Field(..., description="Utilization percentage")
    peak_utilization: float = Field(..., description="Peak utilization during the day")


class MarginRiskMetrics(BaseModel):
    """Model for margin risk metrics."""
    current_utilization: float = Field(..., description="Current margin utilization")
    average_utilization_7d: float = Field(..., description="7-day average utilization")
    peak_utilization_30d: float = Field(..., description="30-day peak utilization")
    margin_calls_count: int = Field(..., description="Number of margin calls in last 30 days")
    risk_score: float = Field(..., ge=0, le=100, description="Risk score (0-100)")
    risk_level: str = Field(..., description="Risk level (LOW/MEDIUM/HIGH/CRITICAL)")
    recommendations: List[str] = Field(..., description="Risk management recommendations")
