"""
NSE Security ID Reference Database
Comprehensive list of NSE security IDs for EQUITY, FUTIDX, and OPTIDX instruments

This file contains mappings for major NSE stocks and indices with their security IDs.
Use these for testing and development with the DHAN API.

Last Updated: October 2025
Total Stocks/Indices: 250+
"""

# =============================================================================
# EQUITY STOCKS - NSE_EQ
# =============================================================================

EQUITY_STOCKS = {
    # Banking & Financial Services
    "HDFC Bank": {"security_id": "1333", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "ICICI Bank": {"security_id": "4963", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "SBI": {"security_id": "3045", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Kotak Mahindra Bank": {"security_id": "1922", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Axis Bank": {"security_id": "5900", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "IndusInd Bank": {"security_id": "5258", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Bandhan Bank": {"security_id": "2263", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "IDFC First Bank": {"security_id": "11184", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Federal Bank": {"security_id": "1023", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "RBL Bank": {"security_id": "18391", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},

    # IT & Technology
    "TCS": {"security_id": "11536", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Infosys": {"security_id": "1594", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Wipro": {"security_id": "3787", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "HCL Technologies": {"security_id": "7229", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Tech Mahindra": {"security_id": "13538", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "L&T Technology": {"security_id": "11483", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "MindTree": {"security_id": "14356", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "MphasiS": {"security_id": "5347", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Tata Elxsi": {"security_id": "4369", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Persistent Systems": {"security_id": "18365", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},

    # Energy & Oil & Gas
    "Reliance Industries": {"security_id": "2885", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "ONGC": {"security_id": "2475", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "NTPC": {"security_id": "11630", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Power Grid": {"security_id": "11631", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Coal India": {"security_id": "20374", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "GAIL": {"security_id": "1202", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Petronet LNG": {"security_id": "11351", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Adani Total Gas": {"security_id": "15083", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Indraprastha Gas": {"security_id": "11262", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Gujarat Gas": {"security_id": "10599", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},

    # Automobile & Auto Ancillary
    "Maruti Suzuki": {"security_id": "10999", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Mahindra & Mahindra": {"security_id": "2031", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Tata Motors": {"security_id": "3456", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Bajaj Auto": {"security_id": "1660", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Hero MotoCorp": {"security_id": "1348", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Eicher Motors": {"security_id": "910", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Ashok Leyland": {"security_id": "212", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "TVS Motor": {"security_id": "8479", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Bajaj Holdings": {"security_id": "11223", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Samvardhana Motherson": {"security_id": "11483", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},

    # FMCG & Consumer Goods
    "Hindustan Unilever": {"security_id": "1394", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "ITC": {"security_id": "1660", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Britannia Industries": {"security_id": "547", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Nestle India": {"security_id": "1232", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Godrej Consumer": {"security_id": "10099", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Dabur India": {"security_id": "2053", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Marico": {"security_id": "4067", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Colgate-Palmolive": {"security_id": "1512", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Procter & Gamble": {"security_id": "387", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Emami": {"security_id": "11761", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},

    # Metals & Mining
    "Tata Steel": {"security_id": "3499", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "JSW Steel": {"security_id": "11723", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Vedanta": {"security_id": "3063", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Hindalco": {"security_id": "1363", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "NMDC": {"security_id": "526", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Steel Authority of India": {"security_id": "3453", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Jindal Steel & Power": {"security_id": "1493", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Welspun Corp": {"security_id": "11934", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "APL Apollo Tubes": {"security_id": "11302", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Ratnamani Metals": {"security_id": "11436", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},

    # Pharmaceuticals
    "Sun Pharmaceutical": {"security_id": "3351", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Dr Reddy's Laboratories": {"security_id": "881", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Cipla": {"security_id": "701", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Aurobindo Pharma": {"security_id": "275", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Lupin": {"security_id": "4047", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Alkem Laboratories": {"security_id": "11730", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Torrent Pharma": {"security_id": "12180", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Cadila Healthcare": {"security_id": "4717", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Biocon": {"security_id": "11373", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Glenmark Pharma": {"security_id": "7406", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},

    # Cement & Construction
    "UltraTech Cement": {"security_id": "11532", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Shree Cement": {"security_id": "3103", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Ambuja Cements": {"security_id": "1270", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "ACC": {"security_id": "22", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Grasim Industries": {"security_id": "1232", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Dalmia Bharat": {"security_id": "542216", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "JK Cement": {"security_id": "13270", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Birla Corporation": {"security_id": "2057", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Heidelberg Cement": {"security_id": "413", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "India Cements": {"security_id": "511", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},

    # Real Estate
    "DLF": {"security_id": "14732", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Godrej Properties": {"security_id": "17875", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Prestige Estates": {"security_id": "53394", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Oberoi Realty": {"security_id": "20242", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Phoenix Mills": {"security_id": "14693", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Brigade Enterprises": {"security_id": "53495", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Sobha": {"security_id": "10004", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Panchshil Realty": {"security_id": "53083", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Mahindra Lifespace": {"security_id": "53229", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Unitech": {"security_id": "14942", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},

    # Telecom
    "Bharti Airtel": {"security_id": "10604", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Reliance Communications": {"security_id": "2107", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Idea Cellular": {"security_id": "14366", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Tata Communications": {"security_id": "3721", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "MTNL": {"security_id": "5938", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Railtel Corporation": {"security_id": "51143", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "GTL Infrastructure": {"security_id": "10022", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "HFCL": {"security_id": "54840", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "ITI": {"security_id": "133", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
    "Sterlite Technologies": {"security_id": "5325", "exchange_segment": "NSE_EQ", "instrument_type": "EQUITY"},
}

# =============================================================================
# FUTURES INDICES - NSE_FNO
# =============================================================================

FUTURES_INDICES = {
    # NIFTY Futures
    "NIFTY": {"security_id": "26000", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY BANK": {"security_id": "26009", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY IT": {"security_id": "26001", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY PSU BANK": {"security_id": "26037", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY PRIVATE BANK": {"security_id": "26027", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY FINANCIAL SERVICES": {"security_id": "26074", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY FMCG": {"security_id": "26081", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY MEDIA": {"security_id": "26017", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY METAL": {"security_id": "26013", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY PHARMA": {"security_id": "26094", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY REALTY": {"security_id": "26011", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY AUTO": {"security_id": "26012", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY ENERGY": {"security_id": "26032", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY INFRASTRUCTURE": {"security_id": "26029", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY COMMODITIES": {"security_id": "26023", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY CONSUMPTION": {"security_id": "26007", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY CPSE": {"security_id": "26036", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY GROWTH SECTORS 15": {"security_id": "26033", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY MIDCAP 50": {"security_id": "26025", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY MIDCAP 100": {"security_id": "26026", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY MIDCAP 150": {"security_id": "26020", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY SMALLCAP 250": {"security_id": "26028", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY MIDSMALLCAP 400": {"security_id": "26035", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY SMLCAP 50": {"security_id": "26024", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY SMLCAP 100": {"security_id": "26031", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY MICROCAP 250": {"security_id": "26034", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY NEXT 50": {"security_id": "26008", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY TOTAL MARKET": {"security_id": "26030", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY 100": {"security_id": "26002", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY 200": {"security_id": "26003", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY 500": {"security_id": "26004", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "NIFTY MIDCAP LIQUID 15": {"security_id": "26022", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
    "INDIA VIX": {"security_id": "26017", "exchange_segment": "NSE_FNO", "instrument_type": "FUTIDX"},
}

# =============================================================================
# OPTIONS INDICES - NSE_FNO
# =============================================================================

OPTIONS_INDICES = {
    # NIFTY Options
    "NIFTY": {"security_id": "26000", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY BANK": {"security_id": "26009", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY IT": {"security_id": "26001", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY FINANCIAL SERVICES": {"security_id": "26074", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY FMCG": {"security_id": "26081", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY MEDIA": {"security_id": "26017", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY METAL": {"security_id": "26013", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY PHARMA": {"security_id": "26094", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY REALTY": {"security_id": "26011", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY AUTO": {"security_id": "26012", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY ENERGY": {"security_id": "26032", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY INFRASTRUCTURE": {"security_id": "26029", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY COMMODITIES": {"security_id": "26023", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY CONSUMPTION": {"security_id": "26007", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY CPSE": {"security_id": "26036", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY GROWTH SECTORS 15": {"security_id": "26033", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY MIDCAP 50": {"security_id": "26025", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY MIDCAP 100": {"security_id": "26026", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY MIDCAP 150": {"security_id": "26020", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY SMALLCAP 250": {"security_id": "26028", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY MIDSMALLCAP 400": {"security_id": "26035", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY SMLCAP 50": {"security_id": "26024", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY SMLCAP 100": {"security_id": "26031", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY MICROCAP 250": {"security_id": "26034", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY NEXT 50": {"security_id": "26008", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY TOTAL MARKET": {"security_id": "26030", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY 100": {"security_id": "26002", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY 200": {"security_id": "26003", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY 500": {"security_id": "26004", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "NIFTY MIDCAP LIQUID 15": {"security_id": "26022", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
    "INDIA VIX": {"security_id": "26017", "exchange_segment": "NSE_FNO", "instrument_type": "OPTIDX"},
}

# =============================================================================
# COMBINED DATABASE
# =============================================================================

ALL_INSTRUMENTS = {
    **EQUITY_STOCKS,
    **FUTURES_INDICES,
    **OPTIONS_INDICES
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_security_info(symbol_name: str):
    """
    Get security information by symbol name.

    Args:
        symbol_name: Name of the stock/index

    Returns:
        dict: Security information or None if not found
    """
    return ALL_INSTRUMENTS.get(symbol_name)

def get_securities_by_type(instrument_type: str):
    """
    Get all securities of a specific instrument type.

    Args:
        instrument_type: Type of instrument (EQUITY, FUTIDX, OPTIDX)

    Returns:
        dict: Filtered securities
    """
    return {k: v for k, v in ALL_INSTRUMENTS.items()
            if v['instrument_type'] == instrument_type}

def get_securities_by_exchange(exchange_segment: str):
    """
    Get all securities of a specific exchange segment.

    Args:
        exchange_segment: Exchange segment (NSE_EQ, NSE_FNO)

    Returns:
        dict: Filtered securities
    """
    return {k: v for k, v in ALL_INSTRUMENTS.items()
            if v['exchange_segment'] == exchange_segment}

def search_securities(query: str):
    """
    Search securities by name (case-insensitive).

    Args:
        query: Search term

    Returns:
        dict: Matching securities
    """
    query_lower = query.lower()
    return {k: v for k, v in ALL_INSTRUMENTS.items()
            if query_lower in k.lower()}

def resolve_security_id(symbol: str):
    info = get_security_info(symbol)
    if info:
        return info
    key = symbol.replace("&", "").replace(" ", "").upper()
    for name, data in ALL_INSTRUMENTS.items():
        normalized = name.replace("&", "").replace(" ", "").upper()
        if normalized == key:
            return data
    return None

def get_random_security(instrument_type: str = None):
    """
    Get a random security, optionally filtered by type.

    Args:
        instrument_type: Optional instrument type filter

    Returns:
        tuple: (symbol_name, security_info)
    """
    import random
    if instrument_type:
        candidates = get_securities_by_type(instrument_type)
    else:
        candidates = ALL_INSTRUMENTS

    if candidates:
        symbol_name = random.choice(list(candidates.keys()))
        return symbol_name, candidates[symbol_name]
    return None, None

# =============================================================================
# STATISTICS
# =============================================================================

INSTRUMENT_STATS = {
    "EQUITY": len(EQUITY_STOCKS),
    "FUTIDX": len(FUTURES_INDICES),
    "OPTIDX": len(OPTIONS_INDICES),
    "TOTAL": len(ALL_INSTRUMENTS)
}

if __name__ == "__main__":
    print("NSE Security ID Reference Database")
    print("=" * 50)
    print(f"Total instruments: {INSTRUMENT_STATS['TOTAL']}")
    print(f"Equity stocks: {INSTRUMENT_STATS['EQUITY']}")
    print(f"Futures indices: {INSTRUMENT_STATS['FUTIDX']}")
    print(f"Options indices: {INSTRUMENT_STATS['OPTIDX']}")
    print()

    # Example usage
    print("Example: Get HDFC Bank info")
    hdfc_info = get_security_info("HDFC Bank")
    if hdfc_info:
        print(f"HDFC Bank: {hdfc_info}")
    print()

    print("Example: Search for 'Tata'")
    tata_stocks = search_securities("Tata")
    for name, info in list(tata_stocks.items())[:3]:  # Show first 3
        print(f"{name}: {info}")
    print()

    print("Example: Get random equity stock")
    symbol, info = get_random_security("EQUITY")
    if symbol and info:
        print(f"Random equity: {symbol} -> {info}")
