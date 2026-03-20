#!/bin/bash
# Run all tests with coverage report

echo "🧪 Running Archive Arbitrage Test Suite"
echo "========================================"

# Run unit tests
echo ""
echo "📦 Running Unit Tests..."
python -m pytest tests/unit/ -v --tb=short

# Run integration tests
echo ""
echo "🔗 Running Integration Tests..."
python -m pytest tests/integration/ -v --tb=short

# Generate coverage report
echo ""
echo "📊 Generating Coverage Report..."
python -m pytest tests/ --cov=core --cov=scrapers --cov-report=term-missing --cov-report=html

echo ""
echo "✅ Test run complete!"
echo "📄 HTML coverage report: htmlcov/index.html"
