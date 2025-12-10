#!/bin/bash

# Development startup script - runs frontend and backend separately

set -e

echo "OpenShift ImageSetConfiguration Generator - Development Mode"
echo "============================================================"

# Setup logging
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend-$(date +%Y%m%d-%H%M%S).log"
FRONTEND_LOG="$LOG_DIR/frontend-$(date +%Y%m%d-%H%M%S).log"

echo "Logs will be written to:"
echo "  Backend:  $BACKEND_LOG"
echo "  Frontend: $FRONTEND_LOG"

# Check if we're already in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    # Check if Python virtual environment exists
    if [ ! -d ".venv" ]; then
        echo "Creating Python virtual environment..."
        python3 -m venv .venv
    fi
    
    # Activate virtual environment
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "Using existing virtual environment: $VIRTUAL_ENV"
fi

# Upgrade pip and install/upgrade Python dependencies
echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing/upgrading Python dependencies..."
pip install --upgrade -r requirements.txt

# Check for Node.js and npm
if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
    echo "Error: Node.js and npm are required for development mode."
    echo "Visit: https://nodejs.org/"
    exit 1
fi

# Install frontend dependencies
echo "Checking frontend dependencies..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Ensure http-proxy-middleware is installed for setupProxy.js
if ! npm list http-proxy-middleware > /dev/null 2>&1; then
    echo "Installing http-proxy-middleware..."
    npm install --save-dev http-proxy-middleware
fi
cd ..

echo ""
echo "Starting development servers..."
echo "Backend API: http://localhost:5000"
echo "Frontend Dev Server: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Function to kill background processes on exit
cleanup() {
    echo "Stopping servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    wait
}

trap cleanup EXIT

# Start backend in background with Flask development mode
echo "Starting Flask backend in development mode..."
export FLASK_APP=app.py
export FLASK_ENV=development
export FLASK_DEBUG=1
export PYTHONUNBUFFERED=1

# Kill any existing process on port 5000
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Killing existing process on port 5000..."
    kill -9 $(lsof -Pi :5000 -sTCP:LISTEN -t) 2>/dev/null || true
    sleep 2
fi

# Start Flask with explicit IPv4 options
python -m flask run --host 127.0.0.1 --port 5000 --reload --with-threads 2>&1 | tee -a "$BACKEND_LOG" | sed 's/^/[Backend] /' &
BACKEND_PID=$!

# Give Flask a moment to initialize
sleep 3

# Wait for backend to be ready
echo "Waiting for backend to start..."
BACKEND_READY=false
for i in {1..30}; do
    if curl -s http://127.0.0.1:5000/api/health > /dev/null 2>&1; then
        echo "Backend is ready!"
        BACKEND_READY=true
        break
    fi
    if [ $((i % 5)) -eq 0 ]; then
        echo "Still waiting... (${i}s)"
    fi
    sleep 1
done

if [ "$BACKEND_READY" = false ]; then
    echo "ERROR: Backend failed to start after 30 seconds"
    echo "Check the backend logs at: $BACKEND_LOG"
    echo ""
    echo "Last 20 lines of backend log:"
    tail -n 20 "$BACKEND_LOG"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# Test the operators/mappings endpoint specifically
echo "Testing /api/operators/mappings endpoint..."
if curl -s http://127.0.0.1:5000/api/operators/mappings > /dev/null 2>&1; then
    echo "✓ Backend API endpoints are accessible"
else
    echo "WARNING: /api/operators/mappings endpoint may not be working"
    echo "The frontend may experience proxy errors"
fi

# Kill any existing process on port 3000
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Killing existing process on port 3000..."
    kill -9 $(lsof -Pi :3000 -sTCP:LISTEN -t) 2>/dev/null || true
    sleep 1
fi

# Start frontend in background
echo "Starting React frontend..."
cd frontend

# Remove any problematic .env.local file
if [ -f .env.local ]; then
    rm .env.local
fi

npm start 2>&1 | tee -a "../$FRONTEND_LOG" | sed 's/^/[Frontend] /' &
FRONTEND_PID=$!
cd ..

# Wait for both processes
wait
