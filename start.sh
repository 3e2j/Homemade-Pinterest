#!/bin/bash
cd "$(dirname "$0")"

# Setup venv if needed
if [ ! -d ".venv" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -q -r requirements.txt
    echo "Setup complete."
else
    source .venv/bin/activate
fi

python3 -m backend.gallery_server
