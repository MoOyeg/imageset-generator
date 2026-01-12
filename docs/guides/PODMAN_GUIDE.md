# Podman Deployment Guide

This guide explains how to deploy the OpenShift ImageSetConfiguration Generator using Podman containers.

## Prerequisites

### Install Podman

#### Red Hat Enterprise Linux / CentOS / Fedora
```bash
sudo dnf install podman
```

#### Ubuntu / Debian
```bash
sudo apt update
sudo apt install podman
```

#### macOS
```bash
# Using Homebrew
brew install podman

# Initialize and start the machine
podman machine init
podman machine start
```

#### Windows
Download and install from: https://podman.io/getting-started/installation

## Quick Deployment

### Using Provided Scripts (Recommended)

**Production Deployment:**
```bash
./start-podman.sh
```

**Development Deployment:**
```bash
./start-podman-dev.sh
```

### Manual Podman Commands

**Build the image:**
```bash
podman build -t imageset-generator:latest .
```

**Run the container:**
```bash
podman run -d \
  --name imageset-generator \
  -p 5000:5000 \
  --restart unless-stopped \
  imageset-generator:latest
```

**Development mode:**
```bash
podman run -it --rm \
  --name imageset-generator-dev \
  -p 5000:5000 \
  -v "$(pwd):/app:Z" \
  -e FLASK_ENV=development \
  imageset-generator:latest \
  python app.py --host 0.0.0.0 --port 5000 --debug
```

## Container Management

### View running containers
```bash
podman ps
```

### View logs
```bash
podman logs -f imageset-generator
```

### Stop the container
```bash
podman stop imageset-generator
```

### Remove the container
```bash
podman rm imageset-generator
```

### Remove the image
```bash
podman rmi imageset-generator:latest
```

## Container Management Commands

### Check container status
```bash
podman ps                    # Running containers
podman ps -a                 # All containers
```

### Manage containers
```bash
podman start imageset-generator     # Start stopped container
podman restart imageset-generator   # Restart container
podman exec -it imageset-generator bash  # Access container shell
```

### Clean up
```bash
# Remove all stopped containers
podman container prune

# Remove unused images  
podman image prune

# Remove everything unused
podman system prune -a
```

## Accessing the Application

Once deployed, access the web interface at:
- **Local:** http://localhost:5000
- **Network:** http://YOUR_SERVER_IP:5000

## Troubleshooting

### Port already in use
If port 5000 is already in use, modify the port mapping:
```bash
podman run -d -p 8080:5000 --name imageset-generator imageset-generator:latest
```

### SELinux issues (RHEL/CentOS/Fedora)
If you encounter SELinux issues with volume mounts, add the `:Z` flag:
```bash
podman run -d -v ./config:/app/config:ro,Z imageset-generator:latest
```

### Permission issues
Ensure the container user has proper permissions:
```bash
# Check container user
podman run --rm imageset-generator:latest id

# Fix ownership if needed
sudo chown -R 1001:1001 ./config
```

### Container won't start
Check the logs for errors:
```bash
podman logs imageset-generator
```

Common issues:
- Missing dependencies in requirements.txt
- Frontend build failures
- Port conflicts
- Permission issues

## Security Considerations

### Running as non-root user
The container runs as a non-root user (`app`) for security.

### Network security
- The container only exposes port 5000
- Consider using a reverse proxy (nginx, Apache) for production
- Use TLS/SSL in production environments

### Image security
Regularly update the base images:
```bash
podman pull python:3.11-slim
podman pull node:18-alpine
podman build --no-cache -t imageset-generator:latest .
```

## Production Deployment Tips

### Use a reverse proxy
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Systemd service
Create `/etc/systemd/system/imageset-generator.service`:
```ini
[Unit]
Description=ImageSet Generator Container
After=network.target

[Service]
Type=notify
ExecStart=/usr/bin/podman run --name imageset-generator -p 5000:5000 imageset-generator:latest
ExecReload=/usr/bin/podman restart imageset-generator
ExecStop=/usr/bin/podman stop imageset-generator
KillMode=none
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable imageset-generator.service
sudo systemctl start imageset-generator.service
```

## Resource Requirements

**Minimum:**
- CPU: 1 core
- Memory: 512MB RAM
- Storage: 1GB

**Recommended:**
- CPU: 2 cores
- Memory: 1GB RAM
- Storage: 2GB
