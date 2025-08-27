#!/bin/bash

# Navigate to the directory this script lives in
cd "$(dirname "$0")"

python3 gallery_server.py #> /dev/null 2>&1