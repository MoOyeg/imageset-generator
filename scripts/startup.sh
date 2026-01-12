#!/bin/bash

echo "Fetching OCP releases using oc-mirror..."
echo "Available OpenShift releases:"
echo "================================"

# Try to fetch releases list with timeout
timeout 30 oc-mirror list releases 2>/dev/null || {
    echo "Warning: Could not fetch releases list (network issue or timeout)"
    echo "The application will continue without the releases list"
}

echo "================================"
echo ""
echo "Starting OpenShift ImageSetConfiguration Generator Web API..."

# Start the Flask application
exec python3.11 app.py --host 0.0.0.0 --port 5000
