"""Config loader for CrateDigger — reads ~/.cratedigger/config.yaml."""

from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".cratedigger" / "config.yaml"


def get_config(config_path: Path | None = None) -> dict:
    """Load config from YAML file.

    Args:
        config_path: Override path (mainly for testing).

    Returns:
        Parsed config dict.

    Raises:
        FileNotFoundError: If config file does not exist.
        ValueError: If config file is empty or invalid.
    """
    path = config_path or CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Config not found: {path}\n"
            f"Create it with your API credentials:\n\n"
            f"  spotify:\n"
            f"    client_id: \"...\"\n"
            f"    client_secret: \"...\"\n"
            f"  youtube:\n"
            f"    client_id: \"...\"\n"
            f"    client_secret: \"...\"\n"
            f"    auth_json: \"~/.cratedigger/youtube_oauth.json\"\n"
        )
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config file: {path} (expected YAML mapping)")
    return data
