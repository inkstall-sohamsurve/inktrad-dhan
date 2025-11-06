import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import SGDRegressor
from sklearn.metrics import mean_squared_error, r2_score
import matplotlib.pyplot as plt

def train_models(csv_path, epochs=10):
    """
    Trains four regression models: Lasso and Ridge for both opening and closing prices.
    
    Args:
        csv_path (str): Path to the CSV file.
        epochs (int): Number of training epochs.
    
    Returns:
        tuple: Contains all four trained models (lasso_open, lasso_close, ridge_open, ridge_close) and the dataframe.
    """
    try:
        df = pd.read_csv(csv_path)
        df.dropna(subset=['symbol', 'open', 'close'], inplace=True)
    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found.")
        return None, None, None, None, None

    X_open_features = df[['symbol', 'high', 'low', 'volume']]
    y_open_target = df['open']
    X_close_features = df[['symbol', 'open', 'high', 'low', 'volume']]
    y_close_target = df['close']

    X_train_open, X_test_open, y_train_open, y_test_open = train_test_split(X_open_features, y_open_target, test_size=0.2, random_state=42)
    X_train_close, X_test_close, y_train_close, y_test_close = train_test_split(X_close_features, y_close_target, test_size=0.2, random_state=42)

    preprocessor_open = ColumnTransformer(transformers=[('num', StandardScaler(), ['high', 'low', 'volume']), ('cat', OneHotEncoder(handle_unknown='ignore'), ['symbol'])])
    preprocessor_close = ColumnTransformer(transformers=[('num', StandardScaler(), ['open', 'high', 'low', 'volume']), ('cat', OneHotEncoder(handle_unknown='ignore'), ['symbol'])])

    models = {}
    for model_type in ['lasso', 'ridge']:
        penalty = 'l1' if model_type == 'lasso' else 'l2'
        print(f"[+] Training {model_type.title()} Models...")
        
        # Train Opening Price Model
        open_model = Pipeline(steps=[
            ('preprocessor', preprocessor_open),
            ('regressor', SGDRegressor(penalty=penalty, alpha=0.0001, max_iter=epochs, tol=1e-3, random_state=42, learning_rate='invscaling', eta0=0.01, verbose=0))
        ])
        open_model.fit(X_train_open, y_train_open)
        models[f'{model_type}_open'] = open_model

        # Train Closing Price Model
        close_model = Pipeline(steps=[
            ('preprocessor', preprocessor_close),
            ('regressor', SGDRegressor(penalty=penalty, alpha=0.0001, max_iter=epochs, tol=1e-3, random_state=42, learning_rate='invscaling', eta0=0.01, verbose=0))
        ])
        close_model.fit(X_train_close, y_train_close)
        models[f'{model_type}_close'] = close_model

    print("\nModels trained successfully!\n")
    return models['lasso_open'], models['lasso_close'], models['ridge_open'], models['ridge_close'], df

def plot_predictions(stock_symbol, latest, predictions):
    """
    Plots historical and predicted OHLC data using matplotlib as a line chart.
    """
    labels = ['Open', 'High', 'Low', 'Close']
    
    historical_data = [latest['open'], latest['high'], latest['low'], latest['close']]
    lasso_preds = [predictions['lasso']['open'], predictions['lasso']['high'], predictions['lasso']['low'], predictions['lasso']['close']]
    ridge_preds = [predictions['ridge']['open'], predictions['ridge']['high'], predictions['ridge']['low'], predictions['ridge']['close']]

    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plotting the lines
    ax.plot(x, historical_data, marker='o', linestyle='-', label='Historical', color='blue')
    ax.plot(x, lasso_preds, marker='x', linestyle='--', label='Lasso', color='red')
    ax.plot(x, ridge_preds, marker='s', linestyle=':', label='Ridge', color='green')

    ax.set_ylabel('Price (₹)')
    ax.set_title(f'OHLC Price Prediction for {stock_symbol}')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(True)

    # Adding text labels for each point to improve readability
    for i, txt in enumerate(historical_data):
        ax.annotate(f'{txt:.2f}', (x[i], historical_data[i]), textcoords="offset points", xytext=(0,10), ha='center')
    for i, txt in enumerate(lasso_preds):
        ax.annotate(f'{txt:.2f}', (x[i], lasso_preds[i]), textcoords="offset points", xytext=(0,10), ha='center')
    for i, txt in enumerate(ridge_preds):
        ax.annotate(f'{txt:.2f}', (x[i], ridge_preds[i]), textcoords="offset points", xytext=(0,-15), ha='center')

    fig.tight_layout()
    plt.show()

def predict_stock_prices(models, df):
    """
    Interactive function to predict stock prices using both Lasso and Ridge models.
    """
    if not all(models):
        print("Models are not available.")
        return

    lasso_open_model, lasso_close_model, ridge_open_model, ridge_close_model = models
    available_symbols = sorted(df['symbol'].unique())
    print(f"Available stock symbols: {', '.join(available_symbols)}\n")

    while True:
        print("=" * 50)
        stock_symbol = input("Enter Stock Symbol (or 'exit' to quit): ").strip().upper()
        
        if stock_symbol.lower() == 'exit':
            print("Exiting prediction mode. Goodbye!")
            break
        
        if stock_symbol not in available_symbols:
            print(f"Symbol '{stock_symbol}' not found.\nAvailable: {', '.join(available_symbols)}\n")
            continue

        latest = df[df['symbol'] == stock_symbol].sort_values('timestamp', ascending=False).iloc[0]
        open_input = pd.DataFrame({'symbol': [stock_symbol], 'high': [latest['high']], 'low': [latest['low']], 'volume': [latest['volume']]})

        predictions = {'lasso': {}, 'ridge': {}}

        # Get predictions from both models
        for model_type, open_model, close_model in [('lasso', lasso_open_model, lasso_close_model), ('ridge', ridge_open_model, ridge_close_model)]:
            # Predict open price
            pred_open = open_model.predict(open_input)[0]
            
            # For high and low, we'll use a simple approach: 
            # high = max(open, close) * random(1.0, 1.02)
            # low = min(open, close) * random(0.98, 1.0)
            # This is a simplified approach - in a real scenario, you might want to predict these values
            
            # First predict close price using the predicted open
            close_input = pd.DataFrame({
                'symbol': [stock_symbol], 
                'open': [pred_open], 
                'high': [latest['high']], 
                'low': [latest['low']], 
                'volume': [latest['volume']]
            })
            pred_close = close_model.predict(close_input)[0]
            
            # Calculate high and low based on open and close
            high = max(pred_open, pred_close) * (1 + 0.01 * np.random.random())
            low = min(pred_open, pred_close) * (1 - 0.01 * np.random.random())
            
            # Store all predictions
            predictions[model_type] = {
                'open': pred_open,
                'high': high,
                'low': low,
                'close': pred_close
            }

        # Display results with OHLC data
        print(f"\n{'='*70}")
        print(f"PREDICTION RESULTS FOR: {stock_symbol} (Date: {latest['timestamp']})")
        print(f"{'='*70}")
        
        # Historical data
        print("\nHISTORICAL DATA:")
        print(f"  {'':<8} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10}")
        print(f"  {'':<8} {latest['open']:>10.2f} {latest['high']:>10.2f} {latest['low']:>10.2f} {latest['close']:>10.2f}")
        
        # Lasso predictions
        print("\nLASSO PREDICTIONS:")
        print(f"  {'':<8} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10}")
        print(f"  {'':<8} {predictions['lasso']['open']:>10.2f} {predictions['lasso']['high']:>10.2f} "
              f"{predictions['lasso']['low']:>10.2f} {predictions['lasso']['close']:>10.2f}")
        
        # Ridge predictions
        print("\nRIDGE PREDICTIONS:")
        print(f"  {'':<8} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10}")
        print(f"  {'':<8} {predictions['ridge']['open']:>10.2f} {predictions['ridge']['high']:>10.2f} "
              f"{predictions['ridge']['low']:>10.2f} {predictions['ridge']['close']:>10.2f}")
        
        print(f"\n{'='*70}\n")
        
        plot_predictions(stock_symbol, latest, predictions)

if __name__ == '__main__':
    csv_file_path = './stocks.csv'
    EPOCHS = 100
    
    print(f"Starting training with {EPOCHS} epochs...\n")
    models = train_models(csv_file_path, epochs=EPOCHS)
    
    if models[-1] is not None:
        predict_stock_prices(models[:-1], models[-1])
