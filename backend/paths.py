"""Path utilities for locating project resources."""

from pathlib import Path

# Get the backend directory (where this module is)
BACKEND_DIR = Path(__file__).parent.resolve()

# Get the project root (parent of backend directory)
PROJECT_ROOT = BACKEND_DIR.parent.resolve()

# Common paths
CONFIG_FILE = PROJECT_ROOT / "config.json"
OUTPUT_DIR = PROJECT_ROOT / "output"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
