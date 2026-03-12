#!/usr/bin/env python3
"""Test config validation directly."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from core.config import ConfigValidator, print_config_help

# Test validation
print("Testing configuration validation...\n")
validator = ConfigValidator()
is_valid, errors, warnings = validator.validate()

print(f"Validation result: {'✅ PASS' if is_valid else '❌ FAIL'}")
print(f"Warnings: {len(warnings)}")
print(f"Errors: {len(errors)}")

if warnings:
    print("\nWarnings:")
    for w in warnings:
        print(f"  {w}")

if errors:
    print("\nErrors:")
    for e in errors:
        print(f"  {e}")

# Test help
print("\n" + "="*70)
print("Testing config help...")
print("="*70)
print_config_help()
