#!/bin/bash

# OpenShift ImageSetConfiguration Generator - Web Application Startup Script

set -e

echo "OpenShift ImageSetConfiguration Generator - Web Application"
echo "==========================================================="

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

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed. Please install Node.js 16 or higher."
    echo "Visit: https://nodejs.org/"
    exit 1
fi

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "Error: npm is not installed. Please install npm."
    exit 1
fi

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Build frontend for production
echo "Building React frontend..."
cd frontend
npm run build
cd ..

# Check if Flask app should run in development mode
FLASK_ENV=${FLASK_ENV:-production}
FLASK_HOST=${FLASK_HOST:-127.0.0.1}
FLASK_PORT=${FLASK_PORT:-5000}

if [ "$FLASK_ENV" = "development" ]; then
    echo "Starting Flask development server..."
    echo "Frontend will be served separately on port 3000"
    echo ""
    echo "In another terminal, run:"
    echo "  cd frontend && npm start"
    echo ""
    python app.py --host $FLASK_HOST --port $FLASK_PORT --debug
else
    echo "Starting Flask production server..."
    echo "Frontend and backend will be served together"
    echo ""
    echo "Access the application at: http://$FLASK_HOST:$FLASK_PORT"
    echo ""
    python app.py --host $FLASK_HOST --port $FLASK_PORT
fi
