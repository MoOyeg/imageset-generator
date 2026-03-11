#!/bin/bash

# OpenShift ImageSetConfiguration Generator - Automated Data Update Script
# Runs the container, resets all data, and pushes updated data files to git.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"
PULL_SECRET="/home/moyo/pull-secret.json"
CONTAINER_NAME="imageset-generator"
IMAGE_NAME="imageset-generator:latest"
LOG_FILE="${SCRIPT_DIR}/logs/update-data-$(date +%Y%m%d-%H%M%S).log"

mkdir -p "${SCRIPT_DIR}/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cleanup() {
    log "Stopping container..."
    podman stop "$CONTAINER_NAME" 2>/dev/null || true
    podman rm "$CONTAINER_NAME" 2>/dev/null || true
    # Clean up temp pull secret copy
    if [ -n "${PULL_SECRET_TMP:-}" ] && [ -f "${PULL_SECRET_TMP:-}" ]; then
        rm -f "$PULL_SECRET_TMP"
        rmdir "$(dirname "$PULL_SECRET_TMP")" 2>/dev/null || true
    fi
}

trap cleanup EXIT

log "=== Starting automated data update ==="

# Validate pull secret exists
if [ ! -f "$PULL_SECRET" ]; then
    log "ERROR: Pull secret not found at ${PULL_SECRET}"
    exit 1
fi

# Ensure data directory exists
mkdir -p "$DATA_DIR"

# Build the container image if it doesn't exist
if ! podman image exists "$IMAGE_NAME"; then
    log "Building container image..."
    podman build -t "$IMAGE_NAME" "$SCRIPT_DIR" >> "$LOG_FILE" 2>&1
fi

# Stop any existing container
log "Cleaning up any existing container..."
podman stop "$CONTAINER_NAME" 2>/dev/null || true
podman rm "$CONTAINER_NAME" 2>/dev/null || true

# Copy pull secret to a temp location with correct permissions for container user
PULL_SECRET_TMP=$(mktemp -d)/config.json
cp "$PULL_SECRET" "$PULL_SECRET_TMP"
chmod 644 "$PULL_SECRET_TMP"

# Start container with data mount and pull secret mounted
# The app user's home is /home/app, mount pull secret to ~/.docker/config.json
log "Starting container with data mount and pull secret..."
podman run -d \
    --name "$CONTAINER_NAME" \
    -p 5000:5000 \
    -v "${DATA_DIR}:/app/data:Z" \
    -v "${PULL_SECRET_TMP}:/home/app/.docker/config.json:Z,ro" \
    --restart no \
    "$IMAGE_NAME"

# Wait for the app to be ready
log "Waiting for application to start..."
for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:5000/api/health > /dev/null 2>&1; then
        log "Application is ready."
        break
    fi
    if [ "$i" -eq 60 ]; then
        log "ERROR: Application failed to start after 60 seconds."
        podman logs "$CONTAINER_NAME" >> "$LOG_FILE" 2>&1
        exit 1
    fi
    sleep 2
done

# Verify pull secret is accessible inside the container
PS_STATUS=$(curl -sf http://127.0.0.1:5000/api/pull-secret/status 2>&1) || true
log "Pull secret status: ${PS_STATUS}"

# Trigger full data reset and stream output
log "Triggering data reset (this may take a while)..."
RESET_STATUS="unknown"
SSE_EVENT=""

while IFS= read -r line; do
    # Track SSE event type
    if [[ "$line" == event:* ]]; then
        SSE_EVENT="${line#event: }"
        SSE_EVENT="${SSE_EVENT#event:}"
        continue
    fi

    # Parse data lines
    if [[ "$line" == data:* ]]; then
        EVENT_DATA="${line#data: }"
        EVENT_DATA="${EVENT_DATA#data:}"

        # Log messages (plain text data from "log" events)
        if [[ "$SSE_EVENT" == "log" || "$SSE_EVENT" == "progress" ]]; then
            if [ -n "$EVENT_DATA" ]; then
                log "  [reset] $EVENT_DATA"
            fi
        fi

        # Check for completion/error events (JSON payload)
        if [[ "$SSE_EVENT" == "complete" ]]; then
            MSG=$(echo "$EVENT_DATA" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('message','done'))" 2>/dev/null || echo "$EVENT_DATA")
            STATUS=$(echo "$EVENT_DATA" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")
            log "  [reset] COMPLETE: $MSG (status: $STATUS)"
            RESET_STATUS="$STATUS"
        fi

        if [[ "$SSE_EVENT" == "error" ]]; then
            MSG=$(echo "$EVENT_DATA" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('message','unknown error'))" 2>/dev/null || echo "$EVENT_DATA")
            log "  [reset] ERROR: $MSG"
            RESET_STATUS="error"
        fi

        SSE_EVENT=""
    fi
done < <(curl -sf -N -X POST http://127.0.0.1:5000/api/reset --max-time 3600 2>&1)

log "Data reset finished with status: ${RESET_STATUS}"

if [ "$RESET_STATUS" == "error" ]; then
    log "ERROR: Data reset failed. Check logs for details."
    exit 1
fi

# Stop the container
log "Stopping container..."
podman stop "$CONTAINER_NAME" 2>/dev/null || true
podman rm "$CONTAINER_NAME" 2>/dev/null || true
# Prevent cleanup trap from double-stopping
trap - EXIT

# Pull latest changes from upstream before committing
cd "$SCRIPT_DIR"
log "Pulling latest changes from origin..."
git stash --include-untracked -- data/ 2>/dev/null || true
git pull --rebase origin main 2>&1 | tee -a "$LOG_FILE" || {
    log "WARNING: git pull --rebase failed, trying merge..."
    git rebase --abort 2>/dev/null || true
    git pull origin main 2>&1 | tee -a "$LOG_FILE"
}
git stash pop 2>/dev/null || true

# Check if there are any data changes to commit
DATA_CHANGES=$(git diff --name-only -- data/ 2>/dev/null || true)
UNTRACKED=$(git ls-files --others --exclude-standard -- data/ 2>/dev/null || true)

if [ -z "$DATA_CHANGES" ] && [ -z "$UNTRACKED" ]; then
    log "No data changes detected. Nothing to push."
    exit 0
fi

log "Data changes detected:"
if [ -n "$DATA_CHANGES" ]; then
    log "$DATA_CHANGES"
fi
if [ -n "$UNTRACKED" ]; then
    log "New files: $UNTRACKED"
fi

# Stage only data directory changes
git add data/

# Commit with a descriptive message
git commit -m "$(cat <<'EOF'
Update data

Automated data refresh via update-data.sh
EOF
)"

log "Changes committed."

# Push to upstream
log "Pushing to origin..."
git push origin main

log "=== Data update complete ==="
