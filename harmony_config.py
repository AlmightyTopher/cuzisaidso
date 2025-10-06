#!/usr/bin/env python3
"""
Configuration management for Audiobookshelf Metadata Harmony Agent

Loads configuration from environment variables with .env file support.
Validates all settings and provides defaults.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from harmony_models import HarmonyConfig


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


def load_config(env_file: Optional[str] = None) -> HarmonyConfig:
    """
    Load configuration from environment variables.

    Args:
        env_file: Optional path to .env file (default: .env)

    Returns:
        HarmonyConfig instance

    Raises:
        ConfigurationError: If required settings are missing or invalid
    """
    # Load .env file
    if env_file:
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)
        else:
            raise ConfigurationError(f"Environment file not found: {env_file}")
    else:
        # Try default locations
        for default_env in ['.env', '.env.harmony']:
            env_path = Path(default_env)
            if env_path.exists():
                load_dotenv(env_path)
                break

    # Required settings
    abs_url = os.getenv('ABS_URL')
    abs_token = os.getenv('ABS_TOKEN')

    if not abs_url:
        raise ConfigurationError("ABS_URL environment variable is required")
    if not abs_token:
        raise ConfigurationError("ABS_TOKEN environment variable is required")

    # Optional settings with defaults
    dry_run = os.getenv('HARMONY_DRY_RUN', 'true').lower() in ('true', '1', 'yes')
    confidence_threshold = float(os.getenv('HARMONY_CONFIDENCE', '0.8'))
    force_rescan = os.getenv('HARMONY_FORCE_RESCAN', 'false').lower() in ('true', '1', 'yes')
    request_timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
    cache_file = os.getenv('HARMONY_CACHE_FILE', '.harmony_cache.sqlite')
    output_dir = os.getenv('HARMONY_OUTPUT_DIR', './reports')
    verbose = os.getenv('HARMONY_VERBOSE', 'false').lower() in ('true', '1', 'yes')
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    # Validate ranges
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ConfigurationError(
            f"HARMONY_CONFIDENCE must be between 0.0 and 1.0, got {confidence_threshold}"
        )

    if request_timeout < 1:
        raise ConfigurationError(
            f"REQUEST_TIMEOUT must be at least 1 second, got {request_timeout}"
        )

    if log_level not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        raise ConfigurationError(
            f"LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL, got {log_level}"
        )

    # Create config object
    config = HarmonyConfig(
        dry_run=dry_run,
        confidence_threshold=confidence_threshold,
        force_rescan=force_rescan,
        abs_url=abs_url,
        abs_token=abs_token,
        request_timeout=request_timeout,
        cache_file=cache_file,
        output_dir=output_dir,
        verbose=verbose,
        log_level=log_level,
    )

    return config


def setup_logging(config: HarmonyConfig):
    """
    Configure logging based on config settings.

    Args:
        config: HarmonyConfig instance
    """
    import logging
    import sys

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.log_level))

    # Format
    if config.verbose:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(output_dir / 'harmony_agent.log')
    file_handler.setLevel(logging.DEBUG)  # Always debug to file
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)


def print_config_summary(config: HarmonyConfig):
    """
    Print configuration summary.

    Args:
        config: HarmonyConfig instance
    """
    print("=" * 60)
    print("Harmony Agent Configuration")
    print("=" * 60)
    print(f"Mode:               {'DRY-RUN' if config.dry_run else 'LIVE UPDATE'}")
    print(f"Confidence:         {config.confidence_threshold:.2f}")
    print(f"Force Rescan:       {config.force_rescan}")
    print(f"ABS URL:            {config.abs_url}")
    print(f"Cache File:         {config.cache_file}")
    print(f"Output Dir:         {config.output_dir}")
    print(f"Log Level:          {config.log_level}")
    print(f"Verbose:            {config.verbose}")
    print("=" * 60)
    print()


def validate_environment():
    """
    Validate environment setup (API connectivity, file permissions, etc.)

    Returns:
        Tuple of (success: bool, errors: List[str])
    """
    errors = []

    # Check .env file exists and load it
    env_loaded = False
    if Path('.env').exists():
        load_dotenv('.env')
        env_loaded = True
    elif Path('.env.harmony').exists():
        load_dotenv('.env.harmony')
        env_loaded = True

    if not env_loaded:
        errors.append("No .env or .env.harmony file found")

    # Check required environment variables
    if not os.getenv('ABS_URL'):
        errors.append("ABS_URL not set in environment")

    if not os.getenv('ABS_TOKEN'):
        errors.append("ABS_TOKEN not set in environment")

    # Check write permissions for output directory
    try:
        output_dir = Path(os.getenv('HARMONY_OUTPUT_DIR', './reports'))
        output_dir.mkdir(parents=True, exist_ok=True)
        test_file = output_dir / '.test_write'
        test_file.write_text('test')
        test_file.unlink()
    except Exception as e:
        errors.append(f"Cannot write to output directory: {e}")

    # Check write permissions for cache file
    try:
        cache_file = Path(os.getenv('HARMONY_CACHE_FILE', '.harmony_cache.sqlite'))
        if cache_file.exists():
            # Check if we can read it
            if not os.access(cache_file, os.R_OK | os.W_OK):
                errors.append(f"Cannot read/write cache file: {cache_file}")
        else:
            # Check if we can create it
            cache_file.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Cannot access cache file location: {e}")

    return len(errors) == 0, errors


# Export
__all__ = [
    'load_config',
    'setup_logging',
    'print_config_summary',
    'validate_environment',
    'ConfigurationError',
]
