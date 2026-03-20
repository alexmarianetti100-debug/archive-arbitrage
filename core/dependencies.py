#!/usr/bin/env python3
"""
Archive Arbitrage - Dependency Validator

Validates that all required dependencies are installed and functional.
Run this on startup to provide helpful error messages if deps are missing.
"""

import sys
import importlib
from typing import List, Tuple, Optional


# Core dependencies that must be present for the service to function
REQUIRED_DEPENDENCIES = [
    ("httpx", "0.26.0", "HTTP client for API calls"),
    ("bs4", "4.12.0", "HTML parsing (BeautifulSoup)"),
    ("lxml", "5.1.0", "Fast HTML parser"),
    ("dotenv", "1.0.0", "Environment variable loading"),
    ("tenacity", "8.2.0", "Retry logic"),
    ("PIL", "10.0.0", "Image processing (Pillow)"),
    ("imagehash", "4.3.0", "Perceptual image hashing"),
    ("playwright", "1.40.0", "Browser automation"),
    ("aiosqlite", "0.19.0", "Async SQLite"),
    ("flask", "3.1.0", "Web framework"),
    ("fastapi", "0.109.0", "API framework"),
    ("pydantic", "2.6.0", "Data validation"),
    ("sqlalchemy", "2.0.25", "Database ORM"),
    ("alembic", "1.13.0", "Database migrations"),
]

# Optional dependencies - service can function without these
OPTIONAL_DEPENDENCIES = [
    ("vinted", None, "Vinted scraper (currently broken)"),
    ("curl_cffi", "0.6.0", "Vinted bypass (optional)"),
    ("numpy", "1.26.0", "ML/data processing"),
    ("pandas", "2.2.0", "Data analysis"),
    ("sklearn", "1.4.0", "Machine learning"),
]

# Development-only dependencies
DEV_DEPENDENCIES = [
    ("pytest", "7.4.0", "Testing framework"),
    ("pytest_asyncio", "0.23.0", "Async test support"),
    ("black", "24.0.0", "Code formatting"),
    ("flake8", "7.0.0", "Linting"),
    ("mypy", "1.8.0", "Type checking"),
]


class DependencyError(Exception):
    """Raised when required dependencies are missing."""
    pass


def check_dependency(name: str, min_version: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Check if a dependency is installed and meets version requirements.
    
    Returns:
        (is_installed, error_message)
    """
    try:
        # Handle special cases
        if name == "bs4":
            module = importlib.import_module("bs4")
            actual_name = "beautifulsoup4"
        elif name == "PIL":
            module = importlib.import_module("PIL")
            actual_name = "Pillow"
        elif name == "sklearn":
            module = importlib.import_module("sklearn")
            actual_name = "scikit-learn"
        elif name == "dotenv":
            module = importlib.import_module("dotenv")
            actual_name = "python-dotenv"
        else:
            module = importlib.import_module(name)
            actual_name = name
        
        # Check version if specified
        if min_version and hasattr(module, "__version__"):
            installed_version = module.__version__
            # Simple version comparison (may not handle all semver cases)
            if installed_version.split(".")[0] < min_version.split(".")[0]:
                return False, f"{actual_name} {installed_version} installed, but >= {min_version} required"
        
        return True, None
        
    except ImportError:
        return False, f"{name} not installed"


def validate_dependencies(
    deps: List[Tuple[str, Optional[str], str]],
    critical: bool = True
) -> Tuple[bool, List[str]]:
    """
    Validate a list of dependencies.
    
    Returns:
        (all_ok, list of error messages)
    """
    errors = []
    
    for name, min_version, description in deps:
        is_ok, error = check_dependency(name, min_version)
        if not is_ok:
            errors.append(f"  ❌ {name}: {error} ({description})")
        else:
            # Only print successes in verbose mode or if there are errors
            pass
    
    return len(errors) == 0, errors


def print_install_command(missing: List[str]):
    """Print pip install command for missing packages."""
    packages = []
    for error in missing:
        # Extract package name from error message
        if "not installed" in error:
            pkg = error.split(":")[0].strip().replace("  ❌ ", "")
            # Map back to pip package names
            pip_name = {
                "bs4": "beautifulsoup4",
                "PIL": "Pillow",
                "sklearn": "scikit-learn",
                "dotenv": "python-dotenv",
            }.get(pkg, pkg)
            packages.append(pip_name)
    
    if packages:
        print("\n📦 To install missing packages, run:")
        print(f"   pip install {' '.join(packages)}")
        print("\n   Or install all requirements:")
        print("   pip install -r requirements.txt")


def validate_all(critical_only: bool = False) -> bool:
    """
    Validate all dependencies.
    
    Args:
        critical_only: Only check required deps, skip optional
        
    Returns:
        True if all critical dependencies are present
    """
    print("🔍 Checking Archive Arbitrage dependencies...\n")
    
    # Check required dependencies
    print("Required dependencies:")
    ok, errors = validate_dependencies(REQUIRED_DEPENDENCIES, critical=True)
    
    if not ok:
        print("\n".join(errors))
        print("\n" + "=" * 60)
        print("❌ CRITICAL DEPENDENCIES MISSING")
        print("=" * 60)
        print_install_command(errors)
        print("\nThe service cannot start without these dependencies.")
        return False
    else:
        print("  ✅ All required dependencies present")
    
    if critical_only:
        return True
    
    # Check optional dependencies
    print("\nOptional dependencies:")
    ok, errors = validate_dependencies(OPTIONAL_DEPENDENCIES, critical=False)
    
    if errors:
        print("\n".join(errors))
        print("\n  ⚠️  Some optional dependencies are missing.")
        print("      The service will work but some features may be limited.")
    else:
        print("  ✅ All optional dependencies present")
    
    print("\n" + "=" * 60)
    print("✅ Dependency check passed!")
    print("=" * 60)
    
    return True


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Archive Arbitrage dependencies")
    parser.add_argument(
        "--critical-only",
        action="store_true",
        help="Only check required dependencies"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Also check development dependencies"
    )
    
    args = parser.parse_args()
    
    ok = validate_all(critical_only=args.critical_only)
    
    if args.dev:
        print("\nDevelopment dependencies:")
        dev_ok, dev_errors = validate_dependencies(DEV_DEPENDENCIES, critical=False)
        if dev_errors:
            print("\n".join(dev_errors))
        else:
            print("  ✅ All development dependencies present")
    
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
