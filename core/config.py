#!/usr/bin/env python3
"""
Archive Arbitrage - Configuration Management

Validates and manages environment configuration.
Provides clear error messages for missing or invalid configuration.
"""

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse


class ConfigError(Exception):
    """Raised when configuration is invalid."""
    pass


@dataclass
class ConfigField:
    """Definition of a configuration field."""
    name: str
    required: bool = True
    secret: bool = False
    pattern: Optional[str] = None
    example: str = ""
    description: str = ""
    default: Any = None


# Configuration schema
CONFIG_SCHEMA = [
    # Critical - Service won't start without these
    ConfigField(
        name="TELEGRAM_BOT_TOKEN",
        required=True,
        secret=True,
        pattern=r"^\d+:[A-Za-z0-9_-]+$",
        example="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        description="Telegram bot token from @BotFather",
    ),
    ConfigField(
        name="DATABASE_URL",
        required=True,
        pattern=r"^(sqlite|postgresql)://",
        example="sqlite:///data/archive.db",
        description="Database connection URL",
        default="sqlite:///data/archive.db",
    ),
    
    # Required for full functionality
    ConfigField(
        name="STRIPE_SECRET_KEY",
        required=False,
        secret=True,
        pattern=r"^sk_(live|test)_",
        example="sk_live_...",
        description="Stripe secret key for billing",
    ),
    ConfigField(
        name="STRIPE_PRICE_ID",
        required=False,
        pattern=r"^price_",
        example="price_1T34ax...",
        description="Stripe price ID for subscriptions",
    ),
    ConfigField(
        name="STRIPE_WEBHOOK_SECRET",
        required=False,
        secret=True,
        pattern=r"^whsec_",
        example="whsec_...",
        description="Stripe webhook endpoint secret",
    ),
    ConfigField(
        name="DISCORD_WEBHOOK_URL",
        required=False,
        secret=True,
        pattern=r"^https://discord\.com/api/webhooks/",
        example="https://discord.com/api/webhooks/...",
        description="Discord webhook URL for alerts",
    ),
    ConfigField(
        name="WHOP_API_KEY",
        required=False,
        secret=True,
        pattern=r"^apik_",
        example="apik_...",
        description="Whop API key for community posts",
    ),
    ConfigField(
        name="WHOP_EXPERIENCE_ID",
        required=False,
        pattern=r"^exp_",
        example="exp_c8acBs3P3KyJKa",
        description="Whop experience ID",
    ),
    
    # Grailed API
    ConfigField(
        name="GRAILED_ALGOLIA_APP_ID",
        required=False,
        example="MNRWEFSS2Q",
        description="Grailed Algolia App ID",
        default="MNRWEFSS2Q",
    ),
    ConfigField(
        name="GRAILED_ALGOLIA_API_KEY",
        required=False,
        secret=True,
        example="a3a4de2e05d9e9b463911705fb6323ad",
        description="Grailed Algolia API Key",
        default="a3a4de2e05d9e9b463911705fb6323ad",
    ),
    
    # Proxy configuration
    ConfigField(
        name="PROXY_HOST",
        required=False,
        example="p.webshare.io",
        description="Proxy hostname for Vinted",
    ),
    ConfigField(
        name="PROXY_PORT",
        required=False,
        example="10000",
        description="Proxy port",
        default="10000",
    ),
    ConfigField(
        name="PROXY_USERNAME",
        required=False,
        secret=True,
        example="eaidpwsx-rotate",
        description="Proxy username",
    ),
    ConfigField(
        name="PROXY_PASSWORD",
        required=False,
        secret=True,
        example="rx24trb5szdc",
        description="Proxy password",
    ),
    
    # Alert thresholds (optional, have defaults)
    ConfigField(
        name="ALERT_MIN_PROFIT",
        required=False,
        example="50",
        description="Minimum profit for alerts",
        default="50",
    ),
    ConfigField(
        name="ALERT_MIN_MARGIN",
        required=False,
        example="0.25",
        description="Minimum margin for alerts",
        default="0.25",
    ),
    ConfigField(
        name="GAP_MIN_PERCENT",
        required=False,
        example="0.33",
        description="Minimum gap percentage",
        default="0.33",
    ),
    ConfigField(
        name="GAP_MIN_PROFIT",
        required=False,
        example="150",
        description="Minimum profit for gap deals",
        default="150",
    ),
]


class ConfigValidator:
    """Validates environment configuration."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all configuration.
        
        Returns:
            (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        for field in CONFIG_SCHEMA:
            self._validate_field(field)
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _validate_field(self, field: ConfigField):
        """Validate a single configuration field."""
        value = os.getenv(field.name)
        
        # Check if required
        if field.required and not value:
            self.errors.append(
                f"❌ {field.name} is required but not set\n"
                f"   Description: {field.description}\n"
                f"   Example: {field.example}"
            )
            return
        
        # Use default if not set
        if not value and field.default:
            os.environ[field.name] = field.default
            value = field.default
            self.warnings.append(
                f"⚠️  {field.name} not set, using default: {field.default}"
            )
            return
        
        # Skip validation if not required and not set
        if not value and not field.required:
            return
        
        # Validate pattern
        if field.pattern and value:
            if not re.match(field.pattern, value):
                self.errors.append(
                    f"❌ {field.name} has invalid format\n"
                    f"   Expected pattern: {field.pattern}\n"
                    f"   Example: {field.example}\n"
                    f"   Current value: {self._mask_secret(value, field.secret)}"
                )
    
    def _mask_secret(self, value: str, is_secret: bool) -> str:
        """Mask secret values for display."""
        if not is_secret or not value:
            return value
        if len(value) <= 8:
            return "***"
        return value[:4] + "..." + value[-4:]
    
    def print_help(self):
        """Print configuration help."""
        print("\n" + "=" * 70)
        print("CONFIGURATION HELP")
        print("=" * 70)
        print("\nRequired environment variables:\n")
        
        for field in CONFIG_SCHEMA:
            if field.required:
                print(f"  {field.name}")
                print(f"    Description: {field.description}")
                print(f"    Example: {field.example}")
                print()
        
        print("\nOptional environment variables:\n")
        for field in CONFIG_SCHEMA:
            if not field.required:
                default_str = f" (default: {field.default})" if field.default else ""
                print(f"  {field.name}{default_str}")
                print(f"    Description: {field.description}")
                if field.example:
                    print(f"    Example: {field.example}")
                print()
        
        print("\n" + "=" * 70)
        print("SETUP INSTRUCTIONS")
        print("=" * 70)
        print("""
1. Copy the example environment file:
   cp .env.example .env.local

2. Edit .env.local and fill in your credentials:
   - Get Telegram bot token from @BotFather
   - Get Stripe keys from https://dashboard.stripe.com
   - Get Discord webhook from channel settings
   - Get Whop API key from https://whop.com/dashboard

3. Never commit .env.local to git - it's already in .gitignore

4. Run validation:
   python3 -c "from core.config import ConfigValidator; ConfigValidator().validate()"
""")


def validate_config(exit_on_error: bool = True) -> bool:
    """
    Validate configuration and optionally exit on error.
    
    Args:
        exit_on_error: If True, exit the program if validation fails
        
    Returns:
        True if configuration is valid
    """
    validator = ConfigValidator()
    is_valid, errors, warnings = validator.validate()
    
    # Print warnings
    for warning in warnings:
        print(warning)
    
    if not is_valid:
        print("\n" + "=" * 70)
        print("CONFIGURATION ERRORS")
        print("=" * 70 + "\n")
        
        for error in errors:
            print(error)
            print()
        
        print("=" * 70)
        print("FIX THESE ERRORS TO CONTINUE")
        print("=" * 70)
        print("\nRun with --help-config for more information.\n")
        
        if exit_on_error:
            sys.exit(1)
        return False
    
    return True


def print_config_help():
    """Print configuration help."""
    validator = ConfigValidator()
    validator.print_help()


# Convenience function for checking specific values
def get_required_env(name: str, description: str = "") -> str:
    """Get a required environment variable with clear error message."""
    value = os.getenv(name)
    if not value:
        print(f"❌ ERROR: {name} is required but not set")
        if description:
            print(f"   {description}")
        print(f"   Add it to your .env.local file")
        sys.exit(1)
    return value


def get_optional_env(name: str, default: Any = None) -> Any:
    """Get an optional environment variable with default."""
    return os.getenv(name, default)
