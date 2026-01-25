"""Configuration loader for Dynamo CLI tools."""

import os
from pathlib import Path
from typing import Any, Optional

import yaml

_config: Optional[dict] = None
_config_path: Optional[Path] = None


def find_config_file() -> Path:
    """Find the dynamo.yaml config file.

    Searches in order:
    1. DYNAMO_CONFIG environment variable
    2. ./config/dynamo.yaml (relative to cwd)
    3. ../config/dynamo.yaml (relative to this file)
    """
    # Check environment variable
    env_path = os.environ.get("DYNAMO_CONFIG")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    # Check relative to cwd
    cwd_path = Path.cwd() / "config" / "dynamo.yaml"
    if cwd_path.exists():
        return cwd_path

    # Check relative to this file
    file_path = Path(__file__).parent.parent.parent / "config" / "dynamo.yaml"
    if file_path.exists():
        return file_path

    raise FileNotFoundError(
        "Could not find dynamo.yaml config file. "
        "Set DYNAMO_CONFIG environment variable or create config/dynamo.yaml"
    )


def load_config(config_path: Optional[str] = None) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Optional path to config file. If None, searches default locations.

    Returns:
        Configuration dictionary.
    """
    global _config, _config_path

    if config_path:
        path = Path(config_path)
    else:
        path = find_config_file()

    with open(path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)
    _config_path = path

    return _config


def get_config() -> dict:
    """Get the loaded configuration, loading if necessary."""
    global _config
    if _config is None:
        load_config()
    return _config


def get_dynamo_cli_path() -> str:
    """Get the path to DynamoCLI.exe."""
    config = get_config()
    return config["dynamo"]["cli_path"]


def get_dynamo_engine() -> str:
    """Get the Python engine name (e.g., CPython3)."""
    config = get_config()
    return config["dynamo"]["engine"]


def get_default_timeout() -> int:
    """Get the default execution timeout in seconds."""
    config = get_config()
    return config["dynamo"].get("default_timeout", 300)


def get_node_template(node_type: str) -> dict:
    """Get a node template by type (python, number, string).

    Args:
        node_type: One of 'python', 'number', 'string'

    Returns:
        Node template dictionary with ConcreteType, NodeType, etc.
    """
    config = get_config()
    templates = config.get("node_templates", {})

    if node_type not in templates:
        raise ValueError(f"Unknown node type: {node_type}. Available: {list(templates.keys())}")

    return templates[node_type].copy()
