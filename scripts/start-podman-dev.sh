#!/bin/bash

# OpenShift ImageSetConfiguration Generator - Podman Development Script

set -e

echo "OpenShift ImageSetConfiguration Generator - Podman Development Mode"
echo "=================================================================="

# Check if Podman is installed
if ! command -v podman &> /dev/null; then
    echo "Error: Podman is not installed."
    echo "Please install Podman:"
    echo "  - RHEL/CentOS/Fedora: sudo dnf install podman"
    echo "  - Ubuntu: sudo apt install podman"
    echo "  - Visit: https://podman.io/getting-started/installation"
    exit 1
fi

# Check if the image exists locally
if ! podman image exists imageset-generator:dev; then
    echo "Building development container image..."
    podman build -t imageset-generator:dev .
else
    echo "Development container image already exists, skipping build..."
    echo "To force rebuild, run: podman rmi imageset-generator:dev"
fi

# Stop and remove existing development container if it exists
if podman ps -a --format "{{.Names}}" | grep -q "^imageset-generator-dev$"; then
    echo "Stopping existing development container..."
    podman stop imageset-generator-dev 2>/dev/null || true
    echo "Removing existing development container..."
    podman rm imageset-generator-dev 2>/dev/null || true
fi

# Run the container in development mode
echo "Starting development environment..."
echo "Backend API: http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the development server"
echo ""

podman run -it --rm \
    --name imageset-generator-dev \
    -p 5000:5000 \
    -v "$(pwd):/app:Z" \
    -v /app/frontend/node_modules \
    -e FLASK_ENV=development \
    imageset-generator:dev \
    python app.py --host 0.0.0.0 --port 5000 --debug
