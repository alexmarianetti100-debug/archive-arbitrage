#!/bin/bash
# Archive Arbitrage - Setup Validation Script
# Run this after cloning the repo to verify your environment

set -e

echo "🔧 Archive Arbitrage Setup Validator"
echo "===================================="
echo ""

# Check if we're using the correct Python (venv vs system)
echo "Checking Python executable..."
python_cmd="python3"
if [[ -n "$VIRTUAL_ENV" ]]; then
    # We're in a venv, prefer 'python' over 'python3'
    if command -v python &> /dev/null; then
        python_cmd="python"
        echo "  ✅ Using venv Python: $(which python)"
    else
        echo "  ⚠️  Venv active but 'python' command not found, using 'python3'"
        echo "     This may cause dependency issues if python3 is system Python"
    fi
fi

# Check Python version
echo ""
echo "Checking Python version..."
python_version=$($python_cmd --version 2>&1 | awk '{print $2}')
echo "  Found Python $python_version"

if $python_cmd -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
    echo "  ✅ Python 3.11+ required"
else
    echo "  ❌ Python 3.11+ required, found $python_version"
    exit 1
fi

# Check if we're in a virtual environment
echo ""
echo "Checking virtual environment..."
if [[ -n "$VIRTUAL_ENV" ]]; then
    echo "  ✅ Virtual environment active: $VIRTUAL_ENV"
else
    echo "  ⚠️  No virtual environment detected"
    echo "     Recommended: python3 -m venv venv && source venv/bin/activate"
fi

# Check pip
echo ""
echo "Checking pip..."
pip_cmd="pip3"
if [[ "$python_cmd" == "python" ]]; then
    pip_cmd="pip"
fi

if command -v $pip_cmd &> /dev/null; then
    pip_version=$($pip_cmd --version | awk '{print $2}')
    echo "  ✅ pip $pip_version found"
else
    echo "  ❌ $pip_cmd not found"
    exit 1
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
if [ -f "requirements.txt" ]; then
    $pip_cmd install -q -r requirements.txt
    echo "  ✅ Production dependencies installed"
else
    echo "  ❌ requirements.txt not found"
    exit 1
fi

# Run dependency validation
echo ""
echo "Validating dependencies..."
$python_cmd core/dependencies.py --critical-only

# Check .env file
echo ""
echo "Checking environment configuration..."
if [ -f ".env" ]; then
    echo "  ✅ .env file exists"
    
    # Check for placeholder values
    if grep -q "your_" .env 2>/dev/null; then
        echo "  ⚠️  .env contains placeholder values - update with your actual credentials"
    fi
else
    echo "  ⚠️  .env file not found"
    echo "     Copy .env.example to .env and fill in your credentials:"
    echo "     cp .env.example .env"
fi

# Check data directory
echo ""
echo "Checking data directory..."
if [ -d "data" ]; then
    echo "  ✅ data/ directory exists"
else
    echo "  Creating data/ directory..."
    mkdir -p data/trends
    echo "  ✅ data/ directory created"
fi

# Check Playwright browsers
echo ""
echo "Checking Playwright browsers..."
if $python_cmd -c "import playwright; print(playwright.__version__)" 2>/dev/null; then
    if [ -d "$HOME/.cache/ms-playwright" ] || [ -d "$HOME/Library/Caches/ms-playwright" ]; then
        echo "  ✅ Playwright browsers installed"
    else
        echo "  ⚠️  Playwright browsers not installed"
        echo "     Run: $python_cmd -m playwright install chromium"
    fi
else
    echo "  ❌ Playwright not installed"
fi

# Final summary
echo ""
echo "===================================="
echo "✅ Setup validation complete!"
echo ""
echo "Next steps:"
echo "  1. Update .env with your actual credentials"
echo "  2. Run: $python_cmd -m playwright install chromium"
echo "  3. Test: $python_cmd gap_hunter.py --once"
echo ""

# Warn about venv
if [[ -n "$VIRTUAL_ENV" && "$python_cmd" == "python3" ]]; then
    echo "⚠️  WARNING: You have a venv activated but 'python3' is using system Python!"
    echo "   To fix: Use 'python' (without the 3) instead of 'python3'"
    echo "   Or: $(which python) gap_hunter.py --once"
    echo ""
fi
