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
import os
from pathlib import Path

# Create directories if they don't exist
os.makedirs('ml', exist_ok=True)
os.makedirs('ml/memory', exist_ok=True)

# Feature names for the ML model
feature_names = [
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

# Generate synthetic training data
print("📊 Generating synthetic training data...")

# Create 1000 synthetic token records
data = []
for i in range(1000):
    # Generate random token data
    token = {
        'symbol': ''.join(np.random.choice(list('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'), np.random.randint(3, 10))),
        'initial_liquidity_sol': np.random.uniform(0.001, 0.5),
        'token_symbol_length': np.random.randint(3, 10),
        'has_numbers': np.random.choice([0, 1]),
        'has_special_chars': np.random.choice([0, 1]),
        'market_cap_estimate': np.random.uniform(1000, 50000),
        'social_mentions_24h': np.random.poisson(5),
        'launch_hour': np.random.randint(0, 24),
        'day_of_week': np.random.randint(0, 7),
        'gas_price_sol': np.random.uniform(0.00001, 0.0001),
        'has_verified_contract': np.random.choice([0, 1]),
        'num_holders_initial': np.random.randint(1, 100),
        'is_meme_token': np.random.choice([0, 1]),
        'similar_tokens_count': np.random.randint(0, 5)
    }
    
    # Determine success based on certain factors
    success_score = (
        token['initial_liquidity_sol'] * 100 +
        token['has_verified_contract'] * 50 +
        token['social_mentions_24h'] * 10 +
        token['num_holders_initial'] * 5
    )
    
    # Success probability
    token['success'] = 1 if success_score > 200 else 0
    data.append(token)

# Create DataFrame
df = pd.DataFrame(data)

# Save to CSV
df.to_csv('ml/historical_tokens.csv', index=False)
print(f"✅ Saved {len(df)} records to ml/historical_tokens.csv")

# Prepare features and target
X = df[feature_names]
y = df['success']

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Scale features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Train model
model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, class_weight='balanced')
model.fit(X_train_scaled, y_train)

# Evaluate
y_pred = model.predict(X_test_scaled)
accuracy = accuracy_score(y_test, y_pred)
print(f"✅ Model trained with accuracy: {accuracy:.2%}")

# Feature importance
feature_importance = dict(zip(feature_names, model.feature_importances_))
print("🔍 Feature importance:")
for feat, imp in sorted(feature_importance.items(), key=lambda x: -x[1])[:5]:
    print(f"   {feat}: {imp:.3f}")

# Save model and scaler
joblib.dump(model, 'ml/memory/model.pkl')
joblib.dump(scaler, 'ml/memory/scaler.pkl')
print("✅ Model and scaler saved to ml/memory/")

# Test with a sample token
print("\n🧪 Testing model with sample token...")
test_token = {
    'symbol': 'TESTAI',
    'initial_liquidity_sol': 0.1,
    'token_symbol_length': 6,
    'has_numbers': 0,
    'has_special_chars': 0,
    'market_cap_estimate': 25000,
    'social_mentions_24h': 20,
    'launch_hour': 15,
    'day_of_week': 2,
    'gas_price_sol': 0.00005,
    'has_verified_contract': 1,
    'num_holders_initial': 50,
    'is_meme_token': 0,
    'similar_tokens_count': 2
}

# Prepare test data
test_df = pd.DataFrame([test_token])
X_test_sample = test_df[feature_names]
X_test_scaled_sample = scaler.transform(X_test_sample)

# Predict
prediction = model.predict(X_test_scaled_sample)[0]
probability = model.predict_proba(X_test_scaled_sample)[0][1]

print(f"🎯 Prediction for {test_token['symbol']}: {'SUCCESS' if prediction == 1 else 'FAIL'}")
print(f"📊 Confidence: {probability:.1%}")

# Save results
results = {
    'accuracy': accuracy,
    'feature_importance': feature_importance,
    'test_prediction': {
        'symbol': test_token['symbol'],
        'prediction': 'SUCCESS' if prediction == 1 else 'FAIL',
        'confidence': float(probability)
    },
    'timestamp': datetime.now().isoformat()
}

with open('ml/training_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print("🎉 ML model training complete!")