"""Configuration and defaults for FileChronicle."""

import os
from pathlib import Path
from typing import List

# Default home storage location
DEFAULT_DATA_DIR = Path.home() / ".filechronicle"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "chronicle.db"

# Environment variable overrides
ENV_DB_PATH = "FILECHRONICLE_DB"
ENV_DATA_DIR = "FILECHRONICLE_HOME"

# Standard default ignore patterns
DEFAULT_IGNORE_PATTERNS: List[str] = [
    ".git",
    ".git/*",
    ".filechronicle",
    ".filechronicle/*",
    ".chronicle",
    ".chronicle/*",
    ".chronicleignore",
    "__pycache__",
    "__pycache__/*",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".pytest_cache",
    ".pytest_cache/*",
    "node_modules",
    "node_modules/*",
    ".venv",
    ".venv/*",
    "venv",
    "venv/*",
    ".env",
    "*.swp",
    "*.swo",
    "*~",
    ".DS_Store",
    "Thumbs.db",
    "*.bak",
    "*.tmp",
]


def get_db_path(override_path: str = None) -> Path:
    """Resolve the active SQLite database path."""
    if override_path:
        return Path(override_path).expanduser().resolve()
    env_override = os.environ.get(ENV_DB_PATH)
    if env_override:
        return Path(env_override).expanduser().resolve()
    return DEFAULT_DB_PATH.resolve()


def get_data_dir() -> Path:
    """Resolve base chronicle data directory."""
    env_dir = os.environ.get(ENV_DATA_DIR)
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return DEFAULT_DATA_DIR.resolve()
