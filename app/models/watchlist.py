"""
Pydantic models for Watchlist entity.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class Instrument(BaseModel):
    """Model for an instrument in a watchlist."""
    security_id: str = Field(..., description="Security ID of the instrument")
    symbol: Optional[str] = Field(None, description="Symbol name")
    exchange_segment: Optional[str] = Field(None, description="Exchange segment")
    
    class Config:
        json_schema_extra = {
            "example": {
                "security_id": "1333",
                "symbol": "RELIANCE",
                "exchange_segment": "NSE_EQ"
            }
        }


class WatchlistCreate(BaseModel):
    """Request model for creating a watchlist."""
    name: str = Field(..., min_length=1, max_length=100, description="Watchlist name")
    instruments: Optional[List[Instrument]] = Field(default_factory=list, description="Initial instruments")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Nifty 50",
                "instruments": [
                    {
                        "security_id": "1333",
                        "symbol": "RELIANCE",
                        "exchange_segment": "NSE_EQ"
                    }
                ]
            }
        }


class WatchlistUpdate(BaseModel):
    """Request model for updating a watchlist."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class AddInstrumentRequest(BaseModel):
    """Request model for adding an instrument to a watchlist."""
    instrument: Instrument


class RemoveInstrumentRequest(BaseModel):
    """Request model for removing an instrument from a watchlist."""
    security_id: str = Field(..., description="Security ID to remove")


class WatchlistInDB(BaseModel):
    """Watchlist model as stored in database."""
    id: str = Field(alias="_id")
    user_id: str
    name: str
    instruments: List[Instrument] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


class WatchlistResponse(BaseModel):
    """Watchlist model for API responses."""
    id: str
    name: str
    instruments: List[Instrument]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
