#!/bin/bash

# OpenShift ImageSetConfiguration Generator - Podman Deployment Script

set -e

echo "OpenShift ImageSetConfiguration Generator - Podman Deployment"
echo "=============================================================="

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
if ! podman image exists imageset-generator:latest; then
    echo "Building container image..."
    podman build -t imageset-generator:latest .
else
    echo "Container image already exists, skipping build..."
    echo "To force rebuild, run: podman rmi imageset-generator:latest"
fi

# Stop and remove existing container if it exists
if podman ps -a --format "{{.Names}}" | grep -q "^imageset-generator$"; then
    echo "Stopping existing container..."
    podman stop imageset-generator 2>/dev/null || true
    echo "Removing existing container..."
    podman rm imageset-generator 2>/dev/null || true
fi

# Run the container
echo "Starting the application..."
podman run -d \
    --name imageset-generator \
    -p 5000:5000 \
    --restart unless-stopped \
    imageset-generator:latest

echo ""
echo "Application started successfully!"
echo "Access the web interface at: http://localhost:5000"
echo ""
echo "To view logs: podman logs -f imageset-generator"
echo "To stop: podman stop imageset-generator"
echo "To remove: podman rm imageset-generator"

echo ""
echo "Container deployment completed!"
