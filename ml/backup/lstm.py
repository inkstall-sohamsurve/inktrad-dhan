import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input
from tensorflow.keras.layers import LSTM, Dropout, Dense

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

def create_lstm_model(timesteps, features):
    """
    Builds a stacked LSTM model using the Keras Functional API.
    """
    # Define the input layer
    inputs = Input(shape=(timesteps, features))
    
    # Build the LSTM layers
    x = LSTM(units=50, return_sequences=True)(inputs)
    x = Dropout(0.2)(x)
    x = LSTM(units=50, return_sequences=True)(x)
    x = Dropout(0.2)(x)
    x = LSTM(units=50)(x)
    x = Dropout(0.2)(x)
    
    # Define the output layer
    outputs = Dense(units=4)(x)  # Output layer for OHLC
    
    # Create and compile the model
    model = Model(inputs=inputs, outputs=outputs)
    model.compile(optimizer='adam', loss='mean_squared_error')
    return model

def train_model_for_stock(df, stock_symbol):
    """Trains an LSTM model for a single stock."""
    stock_data = df[df['symbol'] == stock_symbol].copy()
    ohlc_data = stock_data[['open', 'high', 'low', 'close']].values

    if len(ohlc_data) < 60:
        print(f"Skipping {stock_symbol}: not enough data.")
        return None, None

    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(ohlc_data)

    X, y = [], []
    for i in range(60, len(scaled_data)):
        X.append(scaled_data[i-60:i])
        y.append(scaled_data[i])
    X, y = np.array(X), np.array(y)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = create_lstm_model(timesteps=X_train.shape[1], features=X_train.shape[2])
    model.fit(X_train, y_train, batch_size=32, epochs=10, validation_data=(X_test, y_test), verbose=0)
    
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
        print(f"[+] Training LSTM Model for {symbol}... ")
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
        X_pred = np.array([last_60_days_scaled])

        # Predict OHLC
        pred_ohlc_scaled = model.predict(X_pred)
        pred_ohlc = scaler.inverse_transform(pred_ohlc_scaled)

        print(f"\nPREDICTION RESULTS FOR: {stock_symbol} (Date: 2025-11-03 18:30:00)")
        print("======================================================================")
        print("LSTM Predicted DATA:")
        print(f"           {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10}")
        print(f"              {pred_ohlc[0][0]:<10.2f} {pred_ohlc[0][1]:<10.2f} {pred_ohlc[0][2]:<10.2f} {pred_ohlc[0][3]:<10.2f}")
        print("======================================================================\n")

if __name__ == '__main__':
    main()
