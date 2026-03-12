#!/usr/bin/env python3
"""
Debug what's actually in your source dictionaries
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def check_source_dictionaries():
    """Check what's actually in the source dictionaries"""
    print("🔍 Debugging Source Dictionaries")
    print("=" * 40)
    
    try:
        # Import the source dictionaries
        from pipeline import ALL_SOURCES, ACTIVE_SOURCES
        
        print("ALL_SOURCES contents:")
        for key, value in ALL_SOURCES.items():
            print(f"  {key}: {value} (type: {type(value)})")
            if hasattr(value, '__name__'):
                print(f"    -> Has name: {value.__name__}")
            if callable(value):
                print(f"    -> Is callable: YES")
            else:
                print(f"    -> Is callable: NO")
        
        print("\nACTIVE_SOURCES contents:")
        for key, value in ACTIVE_SOURCES.items():
            print(f"  {key}: {value} (type: {type(value)})")
            if hasattr(value, '__name__'):
                print(f"    -> Has name: {value.__name__}")
            if callable(value):
                print(f"    -> Is callable: YES")
            else:
                print(f"    -> Is callable: NO")
        
        # Now test actual execution
        print("\nTesting actual scraper invocation...")
        from scrapers.grailed import GrailedScraper
        print(f"GrailedScraper class: {GrailedScraper}")
        print(f"Is callable: {callable(GrailedScraper)}")
        
        # Test what the pipeline would do
        print("\nSimulation of what pipeline does:")
        try:
            # This is what your pipeline tries to do
            scraper_to_use = ACTIVE_SOURCES.get("grailed")
            print(f"scraper_to_use = {scraper_to_use}")
            print(f"Type: {type(scraper_to_use)}")
            print(f"Is string: {isinstance(scraper_to_use, str)}")
            if callable(scraper_to_use):
                print("✓ Would be callable")
            else:
                print("✗ Would NOT be callable")
        except Exception as e:
            print(f"Error in simulation: {e}")
            
    except Exception as e:
        print(f"Debug error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_source_dictionaries()