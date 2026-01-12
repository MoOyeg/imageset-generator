#!/bin/bash

# Development startup script - runs frontend and backend separately

set -e

echo "OpenShift ImageSetConfiguration Generator - Development Mode"
echo "============================================================"

# Check if Python virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Check for Node.js and npm
if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
    echo "Error: Node.js and npm are required for development mode."
    echo "Visit: https://nodejs.org/"
    exit 1
fi

# Install frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

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

# Start backend in background
echo "Starting Flask backend..."
python app.py --host 127.0.0.1 --port 5000 --debug &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start frontend in background
echo "Starting React frontend..."
cd frontend
npm start &
FRONTEND_PID=$!
cd ..

# Wait for both processes
wait
