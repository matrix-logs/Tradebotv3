"""
Configuration loader for the trading bot.
Handles loading and validating YAML configuration files.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigLoader:
    """Loads and manages configuration from YAML files."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the config loader.

        Args:
            config_path: Path to the configuration file.
                        Defaults to config/settings.yaml
        """
        if config_path is None:
            # Find project root and use default config
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "settings.yaml"

        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )

        with open(self.config_path, "r") as f:
            self._config = yaml.safe_load(f) or {}

        # Create required directories
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        dirs_to_create = [
            self.get("general.data_dir", "./data"),
            self.get("general.screenshots_dir", "./data/screenshots"),
        ]

        for dir_path in dirs_to_create:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key: Dot-separated key path (e.g., "screen.monitor")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.

        Args:
            key: Dot-separated key path
            value: Value to set
        """
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def save(self) -> None:
        """Save current configuration back to file."""
        with open(self.config_path, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()

    @property
    def all(self) -> Dict[str, Any]:
        """Get entire configuration dictionary."""
        return self._config.copy()

    def get_region(self, region_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific screen region configuration.

        Args:
            region_name: Name of the region (e.g., "price", "bid_ask")

        Returns:
            Region configuration dict or None
        """
        regions = self.get("screen.regions", {})
        return regions.get(region_name)

    def get_enabled_regions(self) -> Dict[str, Dict[str, Any]]:
        """Get all enabled screen regions."""
        regions = self.get("screen.regions", {})
        return {
            name: config
            for name, config in regions.items()
            if config.get("enabled", False)
        }
