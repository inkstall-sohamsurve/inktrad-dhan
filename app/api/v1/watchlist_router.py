"""
Watchlist management router for creating and managing watchlists.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime
from bson import ObjectId
from app.api.deps import get_current_user
from app.models.user import UserInDB
from app.models.watchlist import (
    WatchlistCreate, WatchlistResponse, AddInstrumentRequest,
    RemoveInstrumentRequest, WatchlistUpdate
)
from app.db.database import Database


router = APIRouter(prefix="/api/v2/watchlist", tags=["Watchlist"])


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    watchlist_data: WatchlistCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Create a new watchlist for the authenticated user.
    
    - **name**: Name of the watchlist (e.g., "Nifty 50", "Bank Nifty Options")
    - **instruments**: Optional list of initial instruments to add
    """
    watchlists_collection = Database.get_watchlists_collection()
    
    # Check if watchlist with same name already exists for this user
    existing = await watchlists_collection.find_one({
        "user_id": current_user.id,
        "name": watchlist_data.name
    })
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Watchlist with name '{watchlist_data.name}' already exists"
        )
    
    # Create watchlist document
    now = datetime.utcnow()
    watchlist_doc = {
        "user_id": current_user.id,
        "name": watchlist_data.name,
        "instruments": [inst.model_dump() for inst in watchlist_data.instruments],
        "created_at": now,
        "updated_at": now
    }
    
    # Insert into database
    result = await watchlists_collection.insert_one(watchlist_doc)
    watchlist_doc["_id"] = result.inserted_id
    
    # Return response
    return WatchlistResponse(
        id=str(result.inserted_id),
        name=watchlist_data.name,
        instruments=watchlist_data.instruments,
        created_at=now,
        updated_at=now
    )


@router.get("", response_model=List[WatchlistResponse])
async def get_watchlists(
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get all watchlists for the authenticated user.
    """
    watchlists_collection = Database.get_watchlists_collection()
    
    # Find all watchlists for the user
    cursor = watchlists_collection.find({"user_id": current_user.id})
    watchlists = await cursor.to_list(length=100)
    
    # Convert to response models
    response_list = []
    for wl in watchlists:
        response_list.append(WatchlistResponse(
            id=str(wl["_id"]),
            name=wl["name"],
            instruments=wl.get("instruments", []),
            created_at=wl["created_at"],
            updated_at=wl["updated_at"]
        ))
    
    return response_list


@router.get("/{watchlist_id}", response_model=WatchlistResponse)
async def get_watchlist(
    watchlist_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get a specific watchlist by ID.
    """
    watchlists_collection = Database.get_watchlists_collection()
    
    # Validate ObjectId
    if not ObjectId.is_valid(watchlist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid watchlist ID"
        )
    
    # Find watchlist
    watchlist = await watchlists_collection.find_one({
        "_id": ObjectId(watchlist_id),
        "user_id": current_user.id
    })
    
    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )
    
    return WatchlistResponse(
        id=str(watchlist["_id"]),
        name=watchlist["name"],
        instruments=watchlist.get("instruments", []),
        created_at=watchlist["created_at"],
        updated_at=watchlist["updated_at"]
    )


@router.put("/{watchlist_id}", response_model=WatchlistResponse)
async def update_watchlist(
    watchlist_id: str,
    update_data: WatchlistUpdate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Update a watchlist's name.
    """
    watchlists_collection = Database.get_watchlists_collection()
    
    # Validate ObjectId
    if not ObjectId.is_valid(watchlist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid watchlist ID"
        )
    
    # Check if watchlist exists
    watchlist = await watchlists_collection.find_one({
        "_id": ObjectId(watchlist_id),
        "user_id": current_user.id
    })
    
    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )
    
    # Update watchlist
    update_fields = {"updated_at": datetime.utcnow()}
    
    if update_data.name is not None:
        # Check if new name conflicts with existing watchlist
        existing = await watchlists_collection.find_one({
            "user_id": current_user.id,
            "name": update_data.name,
            "_id": {"$ne": ObjectId(watchlist_id)}
        })
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Watchlist with name '{update_data.name}' already exists"
            )
        
        update_fields["name"] = update_data.name
    
    await watchlists_collection.update_one(
        {"_id": ObjectId(watchlist_id)},
        {"$set": update_fields}
    )
    
    # Fetch updated watchlist
    updated_watchlist = await watchlists_collection.find_one({"_id": ObjectId(watchlist_id)})
    
    return WatchlistResponse(
        id=str(updated_watchlist["_id"]),
        name=updated_watchlist["name"],
        instruments=updated_watchlist.get("instruments", []),
        created_at=updated_watchlist["created_at"],
        updated_at=updated_watchlist["updated_at"]
    )


@router.post("/{watchlist_id}/add", response_model=WatchlistResponse)
async def add_instrument_to_watchlist(
    watchlist_id: str,
    request: AddInstrumentRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Add an instrument to a specific watchlist.
    
    - **instrument**: Instrument details (security_id, symbol, exchange_segment)
    """
    watchlists_collection = Database.get_watchlists_collection()
    
    # Validate ObjectId
    if not ObjectId.is_valid(watchlist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid watchlist ID"
        )
    
    # Check if watchlist exists
    watchlist = await watchlists_collection.find_one({
        "_id": ObjectId(watchlist_id),
        "user_id": current_user.id
    })
    
    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )
    
    # Check if instrument already exists in watchlist
    instruments = watchlist.get("instruments", [])
    for inst in instruments:
        if inst.get("security_id") == request.instrument.security_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Instrument already exists in watchlist"
            )
    
    # Add instrument
    await watchlists_collection.update_one(
        {"_id": ObjectId(watchlist_id)},
        {
            "$push": {"instruments": request.instrument.model_dump()},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    # Fetch updated watchlist
    updated_watchlist = await watchlists_collection.find_one({"_id": ObjectId(watchlist_id)})
    
    return WatchlistResponse(
        id=str(updated_watchlist["_id"]),
        name=updated_watchlist["name"],
        instruments=updated_watchlist.get("instruments", []),
        created_at=updated_watchlist["created_at"],
        updated_at=updated_watchlist["updated_at"]
    )


@router.delete("/{watchlist_id}/remove", response_model=WatchlistResponse)
async def remove_instrument_from_watchlist(
    watchlist_id: str,
    request: RemoveInstrumentRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Remove an instrument from a watchlist.
    
    - **security_id**: Security ID of the instrument to remove
    """
    watchlists_collection = Database.get_watchlists_collection()
    
    # Validate ObjectId
    if not ObjectId.is_valid(watchlist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid watchlist ID"
        )
    
    # Check if watchlist exists
    watchlist = await watchlists_collection.find_one({
        "_id": ObjectId(watchlist_id),
        "user_id": current_user.id
    })
    
    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )
    
    # Remove instrument
    await watchlists_collection.update_one(
        {"_id": ObjectId(watchlist_id)},
        {
            "$pull": {"instruments": {"security_id": request.security_id}},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    # Fetch updated watchlist
    updated_watchlist = await watchlists_collection.find_one({"_id": ObjectId(watchlist_id)})
    
    return WatchlistResponse(
        id=str(updated_watchlist["_id"]),
        name=updated_watchlist["name"],
        instruments=updated_watchlist.get("instruments", []),
        created_at=updated_watchlist["created_at"],
        updated_at=updated_watchlist["updated_at"]
    )


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    watchlist_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Delete a watchlist.
    """
    watchlists_collection = Database.get_watchlists_collection()
    
    # Validate ObjectId
    if not ObjectId.is_valid(watchlist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid watchlist ID"
        )
    
    # Delete watchlist
    result = await watchlists_collection.delete_one({
        "_id": ObjectId(watchlist_id),
        "user_id": current_user.id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )
    
    return None
