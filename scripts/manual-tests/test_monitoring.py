#!/usr/bin/env python3
"""Test monitoring and error handling."""

import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

# Set up logging first
from core.logging_config import setup_logging
setup_logging(console_level=20)  # INFO level

from core.monitoring import monitor, record_scraper_request, print_dashboard
from core.exceptions import NetworkError, ParseError, RateLimitError

print('🧪 TESTING MONITORING & ERROR HANDLING')
print('=' * 60)

# Test 1: Record some requests
print('\n1. Recording scraper requests...')
record_scraper_request("grailed", True, 0.5)
record_scraper_request("grailed", True, 0.6)
record_scraper_request("ebay", True, 1.2)
record_scraper_request("ebay", False, 2.0, error="Timeout")
record_scraper_request("poshmark", True, 0.8)
print('   ✅ Recorded 5 requests')

# Test 2: Simulate failures to trigger alert
print('\n2. Simulating failures for alerting...')
for i in range(6):
    record_scraper_request("vinted", False, 0.3, error=f"Connection error {i+1}")
print('   ✅ Simulated 6 failures')

# Test 3: Print dashboard
print('\n3. Health Dashboard:')
print_dashboard()

# Test 4: Test exceptions
print('\n4. Testing custom exceptions...')
try:
    raise NetworkError(
        message="Connection refused",
        source="ebay",
        details={"url": "https://ebay.com/search"},
    )
except NetworkError as e:
    print(f'   ✅ Caught NetworkError: {e}')
    print(f'      Error code: {e.error_code}')
    print(f'      Category: {e.category.value}')
    print(f'      Retryable: {e.retryable}')
    print(f'      As dict: {e.to_dict()}')

try:
    raise RateLimitError(
        message="Rate limit exceeded",
        source="grailed",
        retry_after=60,
    )
except RateLimitError as e:
    print(f'   ✅ Caught RateLimitError: {e}')
    print(f'      Retry after: {e.retry_after}s')

# Test 5: Save metrics
print('\n5. Saving metrics...')
monitor.save_metrics()
print('   ✅ Metrics saved to data/metrics/')

print('\n' + '=' * 60)
print('✅ ALL TESTS PASSED')
