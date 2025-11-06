import pandas as pd
import json

def convert_json_to_dataframe(json_path):
    """
    Loads a nested JSON file containing stock data and converts it into a 
    flattened Pandas DataFrame.

    The function expands the nested 'data' object so that each entry in the 
    'open', 'high', 'low', 'close', 'volume', and 'transdate' lists becomes a 
    separate row in the DataFrame, associated with its parent stock's metadata.

    Args:
        json_path (str): The file path for the input JSON file.

    Returns:
        pandas.DataFrame: A DataFrame containing the flattened stock data.
    """
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {json_path} was not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_path}.")
        return None

    records = []
    # Iterate over each stock (e.g., "HDFC Bank") in the top-level dictionary
    for stock_name, stock_data in data.items():
        # The actual candle data is in a nested dictionary
        candle_data = stock_data.get('data', {})
        
        # Create a list of dictionaries, one for each time step
        num_candles = len(candle_data.get('open', []))
        for i in range(num_candles):
            # Get the timestamp and convert from Unix epoch to datetime string
            timestamp_unix = candle_data.get('timestamp', [])[i] if i < len(candle_data.get('timestamp', [])) else None
            timestamp_formatted = None
            if timestamp_unix:
                # Convert Unix timestamp to datetime and format as YYYY-MM-DD HH:MM:SS
                timestamp_formatted = pd.to_datetime(timestamp_unix, unit='s').strftime('%Y-%m-%d %H:%M:%S')
            
            record = {
                'stock_name': stock_name,
                'symbol': stock_data.get('symbol'),
                'security_id': stock_data.get('security_id'),
                'timestamp': timestamp_formatted,
                'open': candle_data.get('open', [])[i] if i < len(candle_data.get('open', [])) else None,
                'high': candle_data.get('high', [])[i] if i < len(candle_data.get('high', [])) else None,
                'low': candle_data.get('low', [])[i] if i < len(candle_data.get('low', [])) else None,
                'close': candle_data.get('close', [])[i] if i < len(candle_data.get('close', [])) else None,
                'volume': candle_data.get('volume', [])[i] if i < len(candle_data.get('volume', [])) else None,
            }
            records.append(record)

    df = pd.DataFrame(records)
    
    return df

if __name__ == '__main__':
    # The JSON file is in the parent directory relative to this script
    json_file_path = '../stocks.json'
    
    # Convert the JSON to a DataFrame
    stocks_df = convert_json_to_dataframe(json_file_path)
    
    if stocks_df is not None:
        print("Successfully converted JSON to DataFrame.")
        print("\nDataFrame Info:")
        stocks_df.info()
        print("\nDataFrame Head:")
        print(stocks_df.head()) #to get 1st 5 records

        # Save the DataFrame to a CSV file
        output_csv_path = 'stocks.csv'
        try:
            stocks_df.to_csv(output_csv_path, index=False)
            print(f"\nDataFrame successfully saved to {output_csv_path}")
        except Exception as e:
            print(f"\nError saving DataFrame to CSV: {e}")
