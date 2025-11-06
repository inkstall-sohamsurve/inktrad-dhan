"""
Fetch Historical Options Data for Multiple Indices
Fetches expired options data for NIFTY, BANKNIFTY, NIFTY IT, and NIFTY FINANCIAL SERVICES

This script uses DHAN's Rolling Options API to fetch historical options data with:
- Open, High, Low, Close prices
- Implied Volatility (IV)
- Volume and Open Interest (OI)
- Spot price information
- Strike-wise data (ATM, ATM+/-N)

Usage:
    python scripts/fetch_options_historical.py
"""
import os
import requests
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
from typing import Dict, Any, List

# Load environment variables
load_dotenv()

# Index configurations with security IDs
INDICES = {
    "NIFTY": {
        "security_id": 13,
        "name": "NIFTY",
        "display_name": "NIFTY 50"
    },
    "BANKNIFTY": {
        "security_id": 26009,
        "name": "BANKNIFTY",
        "display_name": "NIFTY BANK"
    },
    "NIFTY_IT": {
        "security_id": 26001,
        "name": "NIFTY_IT",
        "display_name": "NIFTY IT"
    },
    "NIFTY_FINANCIAL": {
        "security_id": 26074,
        "name": "NIFTY_FINANCIAL",
        "display_name": "NIFTY FINANCIAL SERVICES"
    }
}


def print_separator(char="=", length=100):
    """Print a separator line."""
    print(char * length)


def fetch_options_data(
    access_token: str,
    security_id: int,
    index_name: str,
    from_date: str,
    to_date: str,
    interval: str = "1",
    expiry_flag: str = "MONTH",
    expiry_code: int = 1,
    strike: str = "ATM",
    option_type: str = "CALL"
) -> Dict[str, Any]:
    """
    Fetch options data from DHAN API.
    
    Args:
        access_token: DHAN access token
        security_id: Security ID of the index
        index_name: Name of the index for display
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        interval: Time interval (1, 5, 15, 25, 60 minutes)
        expiry_flag: WEEK or MONTH
        expiry_code: 1, 2, 3 (near, next, far expiry)
        strike: ATM, ATM+1, ATM-1, etc.
        option_type: CALL or PUT
        
    Returns:
        Dict containing the API response
    """
    payload = {
        "exchangeSegment": "NSE_FNO",
        "interval": str(interval),
        "securityId": security_id,
        "instrument": "OPTIDX",
        "expiryFlag": expiry_flag,
        "expiryCode": expiry_code,
        "strike": strike,
        "drvOptionType": option_type,
        "requiredData": ["open", "high", "low", "close", "volume", "iv", "oi", "spot"],
        "fromDate": from_date,
        "toDate": to_date
    }
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "access-token": access_token
    }
    
    try:
        print(f"  📡 Fetching {option_type} options for {index_name} ({strike})...")
        response = requests.post(
            "https://api.dhan.co/v2/charts/rollingoption",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Successfully fetched {option_type} data")
            return {
                "status": "success",
                "data": data.get("data", {}),
                "request_parameters": payload
            }
        else:
            error_data = response.json() if response.text else {}
            print(f"  ❌ Error: {response.status_code}")
            return {
                "status": "error",
                "message": f"API returned error: {response.status_code}",
                "error_details": error_data,
                "request_parameters": payload
            }
            
    except requests.exceptions.Timeout:
        print(f"  ⏱️ Request timeout")
        return {
            "status": "error",
            "message": "Request timeout",
            "request_parameters": payload
        }
    except Exception as e:
        print(f"  ❌ Exception: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "request_parameters": payload
        }


def fetch_all_indices_options(
    access_token: str,
    from_date: str,
    to_date: str,
    strikes: List[str] = ["ATM", "ATM+1", "ATM-1"],
    option_types: List[str] = ["CALL", "PUT"]
) -> Dict[str, Any]:
    """
    Fetch options data for all configured indices.
    
    Args:
        access_token: DHAN access token
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        strikes: List of strike prices to fetch
        option_types: List of option types (CALL, PUT)
        
    Returns:
        Dict containing all fetched data organized by index
    """
    results = {}
    
    for index_key, index_config in INDICES.items():
        print(f"\n{'='*80}")
        print(f"📊 Fetching data for {index_config['display_name']}")
        print(f"{'='*80}")
        
        index_results = {
            "security_id": index_config["security_id"],
            "display_name": index_config["display_name"],
            "data": {}
        }
        
        for strike in strikes:
            for option_type in option_types:
                key = f"{strike}_{option_type}"
                result = fetch_options_data(
                    access_token=access_token,
                    security_id=index_config["security_id"],
                    index_name=index_config["display_name"],
                    from_date=from_date,
                    to_date=to_date,
                    strike=strike,
                    option_type=option_type
                )
                index_results["data"][key] = result
        
        results[index_key] = index_results
        print(f"✅ Completed {index_config['display_name']}")
    
    return results


def display_summary(results: Dict[str, Any]):
    """Display a summary of fetched data."""
    print("\n")
    print_separator("=")
    print("📈 FETCH SUMMARY")
    print_separator("=")
    
    for index_key, index_data in results.items():
        print(f"\n{index_data['display_name']}:")
        print(f"  Security ID: {index_data['security_id']}")
        
        success_count = 0
        error_count = 0
        
        for key, result in index_data["data"].items():
            if result["status"] == "success":
                success_count += 1
                # Check if data has candles
                data = result.get("data", {})
                if "open" in data:
                    candle_count = len(data["open"])
                    print(f"  ✅ {key}: {candle_count} candles")
                else:
                    print(f"  ✅ {key}: No candle data")
            else:
                error_count += 1
                print(f"  ❌ {key}: {result.get('message', 'Unknown error')}")
        
        print(f"  Total: {success_count} successful, {error_count} failed")


def save_results_to_file(results: Dict[str, Any], filename: str = None):
    """Save results to a JSON file."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"options_data_{timestamp}.json"
    
    filepath = os.path.join("data", filename)
    os.makedirs("data", exist_ok=True)
    
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {filepath}")
    return filepath


def main():
    """Main function to fetch options data for all indices."""
    print("\n")
    print_separator("=")
    print("🚀 FETCHING HISTORICAL OPTIONS DATA FOR MULTIPLE INDICES")
    print_separator("=")
    
    # Get credentials from environment
    access_token = os.getenv("DHAN_MASTER_ACCESS_TOKEN")
    
    if not access_token:
        print("\n❌ ERROR: DHAN_MASTER_ACCESS_TOKEN not found!")
        print("Please set DHAN_MASTER_ACCESS_TOKEN in your .env file")
        return
    
    # Calculate date range (last 30 days)
    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)
    
    from_date_str = from_date.strftime("%Y-%m-%d")
    to_date_str = to_date.strftime("%Y-%m-%d")
    
    print(f"\n📅 Date Range: {from_date_str} to {to_date_str}")
    print(f"📊 Indices: {', '.join([idx['display_name'] for idx in INDICES.values()])}")
    print(f"🎯 Strikes: ATM, ATM+1, ATM-1")
    print(f"📈 Option Types: CALL, PUT")
    
    # Fetch data for all indices
    results = fetch_all_indices_options(
        access_token=access_token,
        from_date=from_date_str,
        to_date=to_date_str,
        strikes=["ATM", "ATM+1", "ATM-1"],
        option_types=["CALL", "PUT"]
    )
    
    # Display summary
    display_summary(results)
    
    # Save to file
    save_results_to_file(results)
    
    print("\n")
    print_separator("=")
    print("✨ COMPLETED! All indices options data fetched successfully.")
    print_separator("=")
    print("\n")


if __name__ == "__main__":
    main()
