from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class TradeStatus(str, Enum):
    PENDING = "PENDING"
    ENTERED = "ENTERED"
    EXITED = "EXITED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class TradeType(str, Enum):
    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"

class TradeEntry(BaseModel):
    """Model for trade entry details."""
    security_id: str = Field(..., description="Security ID of the instrument")
    trading_symbol: str = Field(..., description="Trading symbol of the instrument")
    exchange_segment: str = Field(..., description="Exchange segment (NSE_EQ, NSE_FO, etc.)")
    quantity: int = Field(..., gt=0, description="Quantity to trade")
    entry_price: float = Field(..., gt=0, description="Entry price per unit")
    stop_loss: Optional[float] = Field(None, gt=0, description="Stop loss price")
    target: Optional[float] = Field(None, gt=0, description="Target price")
    trade_type: TradeType = Field(..., description="Type of trade (INTRADAY/DELIVERY)")
    product_type: str = Field(..., description="Product type (MIS, NRML, CNC, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "security_id": "1333",
                "trading_symbol": "RELIANCE",
                "exchange_segment": "NSE_EQ",
                "quantity": 1,
                "entry_price": 2500.50,
                "stop_loss": 2450.00,
                "target": 2600.00,
                "trade_type": "INTRADAY",
                "product_type": "MIS"
            }
        }

class TradeExit(BaseModel):
    """Model for trade exit details."""
    exit_price: float = Field(..., gt=0, description="Exit price per unit")
    exit_reason: Optional[str] = Field(None, description="Reason for exit")

class TradeInDB(BaseModel):
    """Trade model as stored in the database."""
    id: str = Field(alias="_id")
    user_id: str
    trade_id: str
    security_id: str
    trading_symbol: str
    exchange_segment: str
    quantity: int
    entry_price: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    status: TradeStatus
    trade_type: TradeType
    product_type: str
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None
    brokerage: Optional[float] = None
    taxes: Optional[float] = None
    net_pnl: Optional[float] = None
    
    class Config:
        populate_by_name = True
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "trade_id": "TRADE12345",
                "user_id": "user123",
                "security_id": "1333",
                "exchange_segment": "NSE_EQ",
                "quantity": 1,
                "entry_price": 2500.50,
                "entry_time": "2025-01-01T10:00:00Z",
                "exit_price": 2550.25,
                "exit_time": "2025-01-01T15:30:00Z",
                "stop_loss": 2450.00,
                "target": 2600.00,
                "status": "EXITED",
                "trade_type": "INTRADAY",
                "product_type": "MIS",
                "exit_reason": "Target hit",
                "pnl": 49.75,
                "pnl_percentage": 1.99,
                "brokerage": 20.00,
                "taxes": 10.50,
                "net_pnl": 19.25
            }
        }
