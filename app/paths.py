"""Path utilities for locating project resources."""

from pathlib import Path

# Get the app directory (where this module is)
APP_DIR = Path(__file__).parent.resolve()

# Get the project root (parent of app directory)
PROJECT_ROOT = APP_DIR.parent.resolve()

# Common paths
CONFIG_FILE = PROJECT_ROOT / "config.json"
OUTPUT_DIR = PROJECT_ROOT / "output"
SRC_DIR = PROJECT_ROOT / "src"
