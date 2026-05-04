#!/bin/bash
set -e

cd "$(dirname "$0")"

# Check for required tools
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed."
    exit 1
fi

echo "Starting Homemade Pinterest..."
echo ""

# Setup Python venv if needed
if [ ! -d ".venv" ]; then
    echo "Setting up Python virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -q -r requirements.txt
    echo "✓ Python setup complete"
else
    source .venv/bin/activate
fi

# Setup Node dependencies if needed
if [ ! -d "server/node_modules" ]; then
    echo "Installing Node.js dependencies..."
    cd server
    npm install -q
    cd ..
    echo "✓ Node.js setup complete"
fi

# Check if port 8000 is already in use and kill it
if command -v lsof &> /dev/null; then
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "Port 8000 already in use. Stopping existing server..."
        kill $(lsof -t -i:8000) 2>/dev/null
        sleep 1
    fi
elif command -v netstat &> /dev/null; then
    if netstat -tuln 2>/dev/null | grep -q ":8000 "; then
        echo "Port 8000 already in use. Stopping existing server..."
        pkill -f "node server.js" 2>/dev/null || true
        sleep 1
    fi
fi

# Start Node.js server
echo ""
echo "Starting web server..."
cd server
npm start &
SERVER_PID=$!
cd ..

# Wait for server to start
# TODO: Change to get a confirm message instead of this
sleep 0.5

# Verify server is running
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "❌ Failed to start server"
    exit 1
fi

# Open browser (cross-platform)
echo "Opening browser..."
if command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open http://localhost:8000 2>/dev/null &
elif command -v open &> /dev/null; then
    # macOS
    open http://localhost:8000 2>/dev/null &
elif command -v start &> /dev/null; then
    # Windows
    start http://localhost:8000
fi

echo ""
echo "   Homemade Pinterest is running!"
echo "   Open http://localhost:8000 in your browser"
echo "   Press Ctrl+C to stop the server"
echo ""

# Keep the script running and show server logs
wait $SERVER_PID
