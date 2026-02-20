#!/bin/bash
# Snipe Bot ML Environment Setup Script

echo "🚀 Setting up Snipe Bot ML Environment..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv snipe_bot_env
source snipe_bot_env/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install required packages
echo "Installing ML packages..."
pip install pandas==2.0.3 scikit-learn==1.3.0 joblib==1.3.2 numpy==1.24.3

# Create necessary directories
echo "Creating directories..."
mkdir -p snipe_bot_env/ml_models
mkdir -p snipe_bot_env/data/historical_data
mkdir -p snipe_bot_env/logs

echo "✅ Environment setup complete!"
echo "To activate the environment, run: source snipe_bot_env/bin/activate"