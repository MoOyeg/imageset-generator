# OC-Mirror Integration Documentation

## Overview
The OpenShift ImageSetConfiguration Generator now includes integration with the `oc-mirror` tool to automatically fetch and display available OpenShift Container Platform (OCP) releases.

## Features

### Startup Integration
- The `oc-mirror` tool is automatically downloaded and installed during container build
- On each application startup, `oc-mirror list releases` is executed to fetch the latest available OCP releases
- The releases list is displayed in the container logs for reference
- The application continues to start even if the releases fetch fails (graceful degradation)

### API Endpoint
A new REST API endpoint is available to fetch OCP releases programmatically:

**Endpoint:** `GET /api/versions`

**Response Format:**
```json
{
  "status": "success",
  "releases": [
    "4.0", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9",
    "4.10", "4.11", "4.12", "4.13", "4.14", "4.15", "4.16", "4.17", "4.18", "4.19", "4.20"
  ],
  "count": 21,
  "timestamp": "2025-07-30T02:33:39.810676"
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Error description",
  "timestamp": "2025-07-30T02:33:39.810676"
}
```

## Technical Implementation

### Container Updates
- **Containerfile:** Added dependencies for `oc-mirror` tool:
  - `libgpgme11` - GPG signature verification
  - `libassuan0` - GPG assistant library
  - `libdevmapper1.02.1` - Device mapper library
- **Startup Script:** Created `startup.sh` that:
  1. Runs `oc-mirror list releases` with 30-second timeout
  2. Displays results or graceful error handling
  3. Starts the Flask application

### Backend Changes
- **New API Route:** `/api/versions` in `app.py`
- **Subprocess Integration:** Uses Python's `subprocess` module to execute `oc-mirror`
- **Error Handling:** Includes timeout handling and graceful error responses
- **Response Parsing:** Automatically parses `oc-mirror` output into structured JSON

## Usage Examples

### Command Line Testing
```bash
# Test the releases endpoint
curl -s http://localhost:5000/api/versions | jq .

# Test application health
curl -s http://localhost:5000/api/health | jq .
```

### Frontend Integration
The releases can be fetched from the React frontend:
```javascript
fetch('/api/versions')
  .then(response => response.json())
  .then(data => {
    if (data.status === 'success') {
      console.log('Available releases:', data.releases);
    }
  });
```

## Benefits
1. **Real-time Data:** Always displays the most current available OCP releases
2. **No Manual Updates:** Eliminates need to manually maintain release lists
3. **API Access:** Programmatic access to releases data for frontend integration
4. **Graceful Degradation:** Application continues to work even if releases fetch fails
5. **Comprehensive Logging:** Startup logs show available releases for troubleshooting

## Future Enhancements
- Cache releases data to reduce startup time
- Add release metadata (channels, architectures, etc.)
- Integration with release selection in the frontend UI
- Support for filtering releases by version patterns
