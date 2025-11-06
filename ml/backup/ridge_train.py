import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import SGDRegressor
from sklearn.metrics import mean_squared_error, r2_score

def train_models(csv_path, epochs=10):
    """
    Trains two Ridge Regression models with epochs: one for opening price and one for closing price.
    
    Args:
        csv_path (str): Path to the CSV file.
        epochs (int): Number of training epochs (iterations). Default is 100.
    
    Returns:
        tuple: (open_model, close_model, df) - trained models and dataframe
    """
    try:
        df = pd.read_csv(csv_path)
        df.dropna(subset=['symbol', 'open', 'close'], inplace=True)
    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found.")
        return None, None, None
    
    print(f"Training models for opening and closing price prediction with {epochs} epochs...\n")
    
    # For opening price prediction, we use: symbol, high, low, volume
    # For closing price prediction, we use: symbol, open, high, low, volume
    
    # === Train Opening Price Model ===
    print("[1/2] Training Opening Price Model...")
    X_open = df[['symbol', 'high', 'low', 'volume']]
    y_open = df['open']
    
    X_train_open, X_test_open, y_train_open, y_test_open = train_test_split(
        X_open, y_open, test_size=0.2, random_state=42
    )
    
    preprocessor_open = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), ['high', 'low', 'volume']),
            ('cat', OneHotEncoder(handle_unknown='ignore'), ['symbol'])
        ])
    
    # SGDRegressor with Ridge (L2) regularization supports epochs
    open_model = Pipeline(steps=[
        ('preprocessor', preprocessor_open),
        ('regressor', SGDRegressor(
            penalty='l2',           # Ridge regularization
            alpha=0.0001,           # Regularization strength
            max_iter=epochs,        # Number of epochs
            tol=1e-3,
            random_state=42,
            learning_rate='invscaling',
            eta0=0.01,
            verbose=1               # Show training progress
        ))
    ])
    
    print(f"   Training for {epochs} epochs...")
    open_model.fit(X_train_open, y_train_open)
    y_pred_open = open_model.predict(X_test_open)
    mse_open = mean_squared_error(y_test_open, y_pred_open)
    r2_open = r2_score(y_test_open, y_pred_open)
    
    print(f"   Training complete! MSE: {mse_open:.2f}, R²: {r2_open:.2f}\n")
    
    # === Train Closing Price Model ===
    print("[2/2] Training Closing Price Model...")
    X_close = df[['symbol', 'open', 'high', 'low', 'volume']]
    y_close = df['close']
    
    X_train_close, X_test_close, y_train_close, y_test_close = train_test_split(
        X_close, y_close, test_size=0.2, random_state=42
    )
    
    preprocessor_close = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), ['open', 'high', 'low', 'volume']),
            ('cat', OneHotEncoder(handle_unknown='ignore'), ['symbol'])
        ])
    
    close_model = Pipeline(steps=[
        ('preprocessor', preprocessor_close),
        ('regressor', SGDRegressor(
            penalty='l2',           # Ridge regularization
            alpha=0.0001,           # Regularization strength
            max_iter=epochs,        # Number of epochs
            tol=1e-3,
            random_state=42,
            learning_rate='invscaling',
            eta0=0.01,
            verbose=1               # Show training progress
        ))
    ])
    
    print(f"   Training for {epochs} epochs...")
    close_model.fit(X_train_close, y_train_close)
    y_pred_close = close_model.predict(X_test_close)
    mse_close = mean_squared_error(y_test_close, y_pred_close)
    r2_close = r2_score(y_test_close, y_pred_close)
    
    print(f"   Training complete! MSE: {mse_close:.2f}, R²: {r2_close:.2f}\n")
    print("=" * 50)
    print("Models trained successfully!")
    print("=" * 50)
    print()
    
    return open_model, close_model, df

def predict_stock_prices(open_model, close_model, df):
    """
    Interactive function to predict opening and closing prices based on stock symbol.
    """
    if open_model is None or close_model is None:
        print("Models are not available.")
        return
    
    # Get unique stock symbols from the dataset
    available_symbols = sorted(df['symbol'].unique())
    print(f"Available stock symbols: {', '.join(available_symbols)}\n")
    
    while True:
        print("=" * 50)
        stock_symbol = input("Enter Stock Symbol (or 'exit' to quit): ").strip().upper()
        
        if stock_symbol.lower() == 'exit':
            print("Exiting prediction mode. Goodbye!")
            break
        
        if not stock_symbol:
            print("Stock symbol cannot be empty.\n")
            continue
        
        # Check if the symbol exists in the dataset
        if stock_symbol not in available_symbols:
            print(f"Symbol '{stock_symbol}' not found in dataset.")
            print(f"Available symbols: {', '.join(available_symbols)}\n")
            continue
        
        # Get the most recent data for this stock
        stock_data = df[df['symbol'] == stock_symbol].sort_values('timestamp', ascending=False)
        latest = stock_data.iloc[0]
        
        # Predict Opening Price
        # For opening price, we use average of historical high, low, and volume
        open_input = pd.DataFrame({
            'symbol': [stock_symbol],
            'high': [latest['high']],
            'low': [latest['low']],
            'volume': [latest['volume']]
        })
        predicted_open = open_model.predict(open_input)[0]
        
        # Predict Closing Price
        # For closing price, we use the predicted opening price
        close_input = pd.DataFrame({
            'symbol': [stock_symbol],
            'open': [predicted_open],
            'high': [latest['high']],
            'low': [latest['low']],
            'volume': [latest['volume']]
        })
        predicted_close = close_model.predict(close_input)[0]
        
        # Display results
        print(f"\n{'='*50}")
        print(f"  PREDICTION RESULTS FOR: {stock_symbol}")
        print(f"{'='*50}")
        print(f"\nLatest Historical Data (Date: {latest['timestamp']}):")
        print(f"  - Open:   {latest['open']:.2f}")
        print(f"  - High:   {latest['high']:.2f}")
        print(f"  - Low:    {latest['low']:.2f}")
        print(f"  - Close:  {latest['close']:.2f}")
        print(f"  - Volume: {latest['volume']:,}")
        print(f"\nPREDICTED PRICES:")
        print(f"  - Predicted Opening Price:  ₹{predicted_open:.2f}")
        print(f"  - Predicted Closing Price:  ₹{predicted_close:.2f}")
        print(f"\n{'='*50}\n")

if __name__ == '__main__':
    csv_file_path = './stocks.csv'
    
    # You can change the number of epochs here (default is 100)
    EPOCHS = 100
    
    # Train the models with specified epochs
    print(f"Starting training with {EPOCHS} epochs...\n")
    open_model, close_model, df = train_models(csv_file_path, epochs=EPOCHS)
    
    # Start interactive prediction
    if open_model and close_model:
        predict_stock_prices(open_model, close_model, df)
