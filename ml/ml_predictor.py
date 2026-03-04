"""
ML Prediction Module for Snipe Bot
Uses historical data to predict token success before sniping
"""

import pandas as pd
import numpy as np
import pickle
import re
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report
import joblib
from datetime import datetime, timedelta
import asyncio
import json

class MLPredictor:
    """Machine learning module for predicting token success."""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = [
            'initial_liquidity_sol',
            'token_symbol_length',
            'has_numbers',
            'has_special_chars',
            'market_cap_estimate',
            'social_mentions_24h',
            'launch_hour',
            'day_of_week',
            'gas_price_sol',
            'has_verified_contract',
            'num_holders_initial',
            'is_meme_token',
            'similar_tokens_count'
        ]
        
    def extract_features(self, token_data: dict) -> np.ndarray:
        """Extract features from token data."""
        features = []
        
        # 1. Initial liquidity in SOL
        features.append(token_data.get('initial_liquidity', 0))
        
        # 2. Token symbol analysis
        symbol = token_data.get('symbol', '').upper()
        features.append(len(symbol))
        features.append(1 if any(char.isdigit() for char in symbol) else 0)
        features.append(1 if any(char in symbol for char in ['1','2','3','4','5','6','7','8','9','0']) else 0)
        
        # 3. Market cap estimate (using liquidity multiplier)
        liquidity = token_data.get('initial_liquidity', 0)
        features.append(liquidity * 1000)  # Rough estimate
        
        # 4. Social mentions
        features.append(token_data.get('social_mentions', 0))
        
        # 5. Launch time patterns
        launch_time = token_data.get('launch_time', datetime.now())
        features.append(launch_time.hour if isinstance(launch_time, datetime) else 12)
        features.append(launch_time.weekday() if isinstance(launch_time, datetime) else 0)
        
        # 6. Gas price
        features.append(token_data.get('gas_price', 0.00001))
        
        # 7. Contract verification
        features.append(1 if token_data.get('verified_contract', False) else 0)
        
        # 8. Initial holders
        features.append(token_data.get('initial_holders', 1))
        
        # 9. Meme token detection
        meme_keywords = ['MEME', 'DOGE', 'SHIB', 'PEPE', 'ELON', 'BABYDOGE']
        features.append(1 if any(keyword in symbol for keyword in meme_keywords) else 0)
        
        # 10. Similar tokens count
        features.append(token_data.get('similar_tokens', 0))
        
        return np.array(features).reshape(1, -1)
    
    def train_model(self, data_path: str) -> dict:
        """Train the ML model on historical data."""
        print("🧠 Starting ML model training...")
        
        # Load synthetic historical data (in production, this would be real data)
        df = pd.read_csv(data_path)
        
        # Prepare features and target
        X = df[self.feature_names]
        y = df['success']  # 1 = successful, 0 = failed
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight='balanced'
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"✅ Model trained with accuracy: {accuracy:.2%}")
        
        # Feature importance
        feature_importance = dict(zip(
            self.feature_names,
            self.model.feature_importances_
        ))
        
        # Save model
        joblib.dump(self.model, 'ml/memory/model.pkl')
        joblib.dump(self.scaler, 'ml/memory/scaler.pkl')
        
        return {
            'accuracy': accuracy,
            'feature_importance': feature_importance,
            'training_samples': len(df)
        }
    
    def predict_token(self, token_data: dict) -> dict:
        """Predict if a token will be successful."""
        if self.model is None:
            raise ValueError("Model not trained or loaded")
        
        features = self.extract_features(token_data)
        features_scaled = self.scaler.transform(features)
        
        # Get prediction
        prediction = self.model.predict(features_scaled)[0]
        probability = self.model.predict_proba(features_scaled)[0][1]
        
        return {
            'symbol': token_data.get('symbol', 'UNKNOWN'),
            'prediction': 'SUCCESS' if prediction == 1 else 'FAIL',
            'confidence': float(probability),
            'features': dict(zip(self.feature_names, features[0]))
        }
    
    def load_model(self, model_path: str = 'ml/memory/model.pkl', 
                   scaler_path: str = 'ml/memory/scaler.pkl'):
        """Load trained model from disk."""
        try:
            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            print("🤖 Model loaded successfully")
        except Exception as e:
            print(f"⚠️ Model loading failed: {e}")
    
    async def real_time_prediction(self, token_stream: asyncio.Queue) -> asyncio.Queue:
        """Process tokens in real-time and return predictions."""
        prediction_queue = asyncio.Queue()
        
        while True:
            token_data = await token_stream.get()
            
            if token_data:
                prediction = self.predict_token(token_data)
                await prediction_queue.put(prediction)
                
                # Log prediction
                print(f"🔮 Predicted {prediction['symbol']}: {prediction['prediction']} "
                      f"(confidence: {prediction['confidence']:.2%})")
        
        return prediction_queue

# Example usage and testing
if __name__ == "__main__":
    predictor = MLPredictor()
    
    # Create synthetic training data
    print("📊 Generating synthetic training data...")
    
    # Generate 1000 samples of historical tokens
    data = []
    for i in range(1000):
        # Random token data
        token = {
            'initial_liquidity': np.random.uniform(0.001, 0.5),
            'symbol_length': np.random.randint(3, 10),
            'has_numbers': np.random.choice([0, 1]),
            'has_special_chars': np.random.choice([0, 1]),
            'market_cap_estimate': np.random.uniform(1000, 50000),
            'social_mentions_24h': np.random.poisson(5),
            'launch_hour': np.random.randint(0, 24),
            'day_of_week': np.random.randint(0, 7),
            'gas_price': np.random.uniform(0.00001, 0.0001),
            'has_verified_contract': np.random.choice([0, 1]),
            'num_holders_initial': np.random.randint(1, 100),
            'is_meme_token': np.random.choice([0, 1]),
            'similar_tokens_count': np.random.randint(0, 5)
        }
        
        # Determine success based on features (simplified rules)
        success_score = (
            token['initial_liquidity'] * 100 +
            token['has_verified_contract'] * 50 +
            token['social_mentions_24h'] * 10 +
            token['num_holders_initial'] * 5
        )
        
        token['success'] = 1 if success_score > 200 else 0
        data.append(token)
    
    # Save to CSV
    df = pd.DataFrame(data)
    df.to_csv('ml/historical_tokens.csv', index=False)
    
    # Train model
    metrics = predictor.train_model('ml/historical_tokens.csv')
    print(f"📈 Training complete. Accuracy: {metrics['accuracy']:.2%}")
    
    # Test with new token
    test_token = {
        'symbol': 'TESTAI',
        'initial_liquidity': 0.1,
        'verified_contract': True,
        'social_mentions_24h': 20,
        'launch_time': datetime.now(),
        'gas_price': 0.00005
    }
    
    prediction = predictor.predict_token(test_token)
    print(f"🎯 Test prediction for {prediction['symbol']}: {prediction['prediction']} "
          f"(confidence: {prediction['confidence']:.2%})")