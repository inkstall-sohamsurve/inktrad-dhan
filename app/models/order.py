"""
Pydantic models for Order entity.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class TransactionType(str, Enum):
    """Order transaction type."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_MARKET = "STOP_LOSS_MARKET"


class ProductType(str, Enum):
    """Product type."""
    INTRADAY = "INTRADAY"
    CNC = "CNC"
    MARGIN = "MARGIN"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "PENDING"
    TRANSIT = "TRANSIT"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    TRADED = "TRADED"
    EXPIRED = "EXPIRED"


class PlaceOrderRequest(BaseModel):
    """Request model for placing an order."""
    security_id: str = Field(..., description="Security ID of the instrument")
    exchange_segment: str = Field(..., description="Exchange segment (NSE_EQ, BSE_EQ, etc.)")
    transaction_type: TransactionType = Field(..., description="BUY or SELL")
    quantity: int = Field(..., gt=0, description="Order quantity")
    order_type: OrderType = Field(..., description="Order type")
    product_type: ProductType = Field(..., description="Product type")
    price: Optional[float] = Field(None, ge=0, description="Limit price (required for LIMIT orders)")
    trigger_price: Optional[float] = Field(None, ge=0, description="Trigger price (for stop loss orders)")
    disclosed_quantity: Optional[int] = Field(0, ge=0, description="Disclosed quantity")
    validity: str = Field("DAY", description="Order validity (DAY, IOC)")
    amo_time: Optional[str] = Field(None, description="AMO order time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "security_id": "1333",
                "exchange_segment": "NSE_EQ",
                "transaction_type": "BUY",
                "quantity": 1,
                "order_type": "LIMIT",
                "product_type": "INTRADAY",
                "price": 2500.50,
                "validity": "DAY"
            }
        }


class ModifyOrderRequest(BaseModel):
    """Request model for modifying an order."""
    order_id: str = Field(..., description="Order ID to modify")
    quantity: Optional[int] = Field(None, gt=0, description="New quantity")
    price: Optional[float] = Field(None, ge=0, description="New limit price")
    trigger_price: Optional[float] = Field(None, ge=0, description="New trigger price")
    order_type: Optional[OrderType] = Field(None, description="New order type")
    validity: Optional[str] = Field(None, description="New validity")
    disclosed_quantity: Optional[int] = Field(None, ge=0, description="New disclosed quantity")


class OrderResponse(BaseModel):
    """Response model for order operations."""
    order_id: Optional[str] = None
    status: str
    message: str
    data: Optional[dict] = None


class OrderInDB(BaseModel):
    """Order model as stored in database (orders_log collection)."""
    id: str = Field(alias="_id")
    user_id: str
    dhan_order_id: str
    symbol: str
    security_id: str
    exchange_segment: str
    transaction_type: str
    quantity: int
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    order_type: str
    product_type: str
    status: str
    timestamp: datetime
    
    class Config:
        populate_by_name = True
