from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class TransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class ExchangeSegment(str, Enum):
    NSE_EQ = "NSE_EQ"
    NSE_FO = "NSE_FO"
    BSE_EQ = "BSE_EQ"

class ProductType(str, Enum):
    CNC = "CNC"  # Delivery
    MIS = "MIS"  # Intraday
    NRML = "NRML"  # F&O Normal

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL_M"

class Validity(str, Enum):
    DAY = "DAY"
    IOC = "IOC"

class AMOTime(str, Enum):
    OPEN = "OPEN"
    OPEN_30 = "OPEN_30"
    OPEN_60 = "OPEN_60"

class OptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"

class DhanOrderRequest(BaseModel):
    """DHAN official order request model."""
    dhan_client_id: str = Field(..., description="DHAN client ID")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracking")
    transaction_type: TransactionType
    exchange_segment: ExchangeSegment
    product_type: ProductType
    order_type: OrderType
    validity: Validity = Field(default=Validity.DAY)
    trading_symbol: str
    security_id: str
    quantity: int = Field(..., gt=0)
    disclosed_quantity: int = Field(default=0)
    price: Optional[float] = Field(None, ge=0)
    trigger_price: Optional[float] = Field(None, ge=0)
    after_market_order: bool = Field(default=False)
    amo_time: Optional[AMOTime] = None
    bo_profit_value: Optional[float] = Field(None, ge=0)
    bo_stop_loss_value: Optional[float] = Field(None, ge=0)
    drv_expiry_date: Optional[str] = None
    drv_option_type: Optional[OptionType] = None
    drv_strike_price: Optional[float] = Field(None, ge=0)

    class Config:
        json_schema_extra = {
            "example": {
                "dhan_client_id": "DHANCLIENT123",
                "correlation_id": "ORDER123",
                "transaction_type": "BUY",
                "exchange_segment": "NSE_EQ",
                "product_type": "CNC",
                "order_type": "LIMIT",
                "validity": "DAY",
                "trading_symbol": "RELIANCE",
                "security_id": "2885",
                "quantity": 1,
                "disclosed_quantity": 0,
                "price": 2500.50,
                "trigger_price": 0,
                "after_market_order": False,
                "amo_time": None,
                "bo_profit_value": None,
                "bo_stop_loss_value": None
            }
        }
