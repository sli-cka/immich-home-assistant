"""Constants for the immich integration."""
from typing import Final

DOMAIN: Final[str] = "immich"
"""The domain used for this integration."""

CONF_WATCHED_ALBUMS: Final[str] = "watched_albums"
"""Configuration key for watched albums."""

# API-related constants
API_TIMEOUT: Final[int] = 30
"""Timeout in seconds for API requests."""

# Platform constants
PLATFORMS: Final[list[str]] = ["image", "sensor"]
"""List of platforms supported by this integration."""

# Default values
DEFAULT_SCAN_INTERVAL: Final[int] = 300
"""Default interval in seconds between updates."""
