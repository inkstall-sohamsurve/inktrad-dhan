import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
import xgboost as xgb
from sklearn.multioutput import MultiOutputRegressor

def load_data(csv_path):
    """Loads stock data and filters it for the last 5 years."""
    try:
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        five_years_ago = pd.Timestamp.now() - pd.DateOffset(years=5)
        df = df[df['timestamp'] >= five_years_ago]
        return df
    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found.")
        return None

def create_xgboost_model():
    """
    Builds a Multi-Output XGBoost model.
    """
    # Define the XGBoost regressor with optimized parameters
    xgb_reg = xgb.XGBRegressor(objective='reg:squarederror',
                               n_estimators=10,
                               learning_rate=0.1,
                               max_depth=5,
                               subsample=0.8,
                               colsample_bytree=0.8,
                               random_state=42)
    
    # Wrap it with MultiOutputRegressor for multi-target prediction (OHLC)
    model = MultiOutputRegressor(xgb_reg)
    return model

def train_model_for_stock(df, stock_symbol):
    """Trains an XGBoost model for a single stock."""
    stock_data = df[df['symbol'] == stock_symbol].copy()
    ohlc_data = stock_data[['open', 'high', 'low', 'close']].values

    if len(ohlc_data) < 60:
        print(f"Skipping {stock_symbol}: not enough data.")
        return None, None

    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(ohlc_data)

    X, y = [], []
    for i in range(60, len(scaled_data)):
        # Flatten the 60x4 window into a single feature vector of size 240
        X.append(scaled_data[i-60:i].flatten())
        y.append(scaled_data[i])
    X, y = np.array(X), np.array(y)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = create_xgboost_model()
    model.fit(X_train, y_train)
    
    return model, scaler

def main():
    """Main function to train models and then enter a prediction loop."""
    csv_file_path = './stocks.csv'
    df = load_data(csv_file_path)
    if df is None:
        return

    available_symbols = sorted(df['symbol'].unique())
    trained_models = {}
    scalers = {}

    print("Starting model training for all stocks (last 5 years). This may take a while...")
    for symbol in available_symbols:
        print(f"[+] Training XGBoost Model for {symbol}... ")
        model, scaler = train_model_for_stock(df, symbol)
        if model:
            trained_models[symbol] = model
            scalers[symbol] = scaler
    print("\nAll models trained successfully!\n")

    while True:
        print("======================================================================")
        stock_symbol = input("Enter Stock Symbol (or 'exit' to quit): ").strip().upper()
        if stock_symbol.lower() == 'exit':
            print("Exiting program.")
            break

        if stock_symbol not in trained_models:
            print(f"Error: Model for '{stock_symbol}' is not available.")
            continue

        model = trained_models[stock_symbol]
        scaler = scalers[stock_symbol]
        
        # Prepare the last 60 days of data for prediction
        stock_data = df[df['symbol'] == stock_symbol][['open', 'high', 'low', 'close']].values
        last_60_days_scaled = scaler.transform(stock_data[-60:])
        # Flatten the data for XGBoost
        X_pred = np.array([last_60_days_scaled.flatten()])

        # Predict OHLC
        pred_ohlc_scaled = model.predict(X_pred)
        pred_ohlc = scaler.inverse_transform(pred_ohlc_scaled)

        print(f"\nPREDICTION RESULTS FOR: {stock_symbol} (Date: 2025-11-03 18:30:00)")
        print("======================================================================")
        print("XGBoost Predicted DATA:")
        print(f"           {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10}")
        print(f"              {pred_ohlc[0][0]:<10.2f} {pred_ohlc[0][1]:<10.2f} {pred_ohlc[0][2]:<10.2f} {pred_ohlc[0][3]:<10.2f}")
        print("======================================================================\n")

if __name__ == '__main__':
    main()
