#!/bin/bash
# Fix broken venv - recreate with correct Python version

echo "🔧 Fixing Virtual Environment"
echo "=============================="
echo ""

# Check if venv exists
if [ -d "venv" ]; then
    echo "Backing up old venv to venv.bak..."
    mv venv venv.bak
    echo "  ✅ Old venv backed up"
fi

# Find Python 3.11
echo ""
echo "Looking for Python 3.11..."
if command -v python3.11 &> /dev/null; then
    PYTHON=python3.11
elif python3 --version 2>&1 | grep -q "3\.11"; then
    PYTHON=python3
else
    echo "❌ Python 3.11 not found"
    echo "   Please install Python 3.11:"
    echo "   brew install python@3.11"
    exit 1
fi

echo "  ✅ Found Python 3.11: $PYTHON"

# Create new venv
echo ""
echo "Creating new virtual environment..."
$PYTHON -m venv venv
echo "  ✅ venv created"

# Activate and install
echo ""
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "  ✅ Dependencies installed"

# Install Playwright
echo ""
echo "Installing Playwright browsers..."
playwright install chromium
echo "  ✅ Playwright installed"

# Test
echo ""
echo "Testing installation..."
python -c "import aiosqlite; print('  ✅ aiosqlite:', aiosqlite.__version__)"
python -c "import httpx; print('  ✅ httpx:', httpx.__version__)"

echo ""
echo "=============================="
echo "✅ Fix complete!"
echo ""
echo "The venv has been recreated with Python 3.11"
echo "Your old venv is backed up as venv.bak"
echo ""
echo "To use:"
echo "  source venv/bin/activate"
echo "  python gap_hunter.py --once"
