# Dynamic OCP Channels Integration

## Overview
The application now dynamically fetches available OpenShift Container Platform (OCP) channels for any selected version using the `oc-mirror` tool. This ensures users always have access to the most current and relevant channel options for their chosen OCP version.

## Features

### New API Endpoint
**Endpoint:** `GET /api/channels/<version>`

**Parameters:**
- `version`: OCP version in format `X.Y` (e.g., `4.14`, `4.18`)

**Response Format:**
```json
{
  "status": "success",
  "version": "4.14",
  "channels": [
    "candidate-4.12",
    "candidate-4.13", 
    "candidate-4.14",
    "candidate-4.15",
    "candidate-4.16",
    "eus-4.12",
    "eus-4.14",
    "eus-4.16",
    "fast-4.12",
    "fast-4.13",
    "fast-4.14",
    "fast-4.15",
    "fast-4.16",
    "stable-4.12",
    "stable-4.13",
    "stable-4.14",
    "stable-4.15",
    "stable-4.16"
  ],
  "count": 18,
  "timestamp": "2025-07-30T02:58:45.108946"
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Invalid version format. Expected format: X.Y (e.g., 4.14)",
  "timestamp": "2025-07-30T03:00:19.600136"
}
```

## Technical Implementation

### Backend Changes (app.py)
- **New Route:** `/api/channels/<version>` endpoint
- **oc-mirror Integration:** Uses `oc-mirror list releases --channels --version=X.Y`
- **Input Validation:** Validates version format using regex `^\d+\.\d+$`
- **Output Parsing:** Filters and sorts channel names from oc-mirror output
- **Error Handling:** Comprehensive error handling with timeouts and validation
- **Response Format:** Structured JSON with metadata

### Frontend Changes

#### App.js Updates
- **New State:** `ocpChannels` to store fetched channels
- **Channel Fetching:** `fetchChannelsForVersion()` function to call channels API
- **Fallback Channels:** Default channel generation if API fails
- **Props Passing:** Passes channels and fetch function to BasicConfig

#### BasicConfig.js Updates
- **Dynamic Channel Dropdown:** Replaces static channel list with dynamic data
- **Version-triggered Fetching:** Automatically fetches channels when primary version changes
- **Disabled State:** Channel dropdown disabled until version is selected
- **Loading States:** Shows appropriate messages during loading
- **Help Text:** Dynamic help text showing channel count and version context

### UI/UX Improvements
- **Smart Workflow:** Version selection → automatic channel fetching → channel selection
- **Visual Feedback:** Different states for no version, loading, and loaded channels
- **Error Resilience:** Graceful fallback to generated channels if API fails
- **User Guidance:** Clear help text explaining the relationship between versions and channels

## Channel Types Explained

### Stable Channels
- **Format:** `stable-X.Y`
- **Purpose:** Production-ready releases with full testing
- **Recommendation:** Use for production deployments

### Fast Channels
- **Format:** `fast-X.Y`
- **Purpose:** Latest releases with minimal additional testing
- **Recommendation:** Use for development or testing environments

### Candidate Channels
- **Format:** `candidate-X.Y`
- **Purpose:** Release candidates and pre-release versions
- **Recommendation:** Use for early testing and preview

### EUS Channels
- **Format:** `eus-X.Y`
- **Purpose:** Extended Update Support channels for long-term maintenance
- **Recommendation:** Use for environments requiring extended support lifecycles

## Usage Examples

### API Testing
```bash
# Get channels for version 4.14
curl -s http://localhost:5000/api/channels/4.14 | jq .

# Get channel count for version 4.18
curl -s http://localhost:5000/api/channels/4.18 | jq '.count'

# Test error handling
curl -s http://localhost:5000/api/channels/invalid | jq .
```

### Frontend Integration Flow
1. User selects primary OCP version (e.g., "4.14")
2. `handleSingleOcpVersionChange` triggers
3. `fetchChannelsForVersion("4.14")` called automatically
4. API request to `/api/channels/4.14`
5. Channels dropdown populated with 18 available channels
6. User can select appropriate channel for their use case

## Benefits

1. **Real-time Accuracy:** Always shows current channels from OpenShift registry
2. **Version-specific:** Only shows channels relevant to selected OCP version
3. **Reduced Errors:** Eliminates invalid channel selections
4. **Better UX:** Guided workflow from version to channel selection
5. **Comprehensive Coverage:** Includes all channel types (stable, fast, candidate, eus)
6. **Performance:** Efficient caching and error handling

## Performance Considerations

- **On-demand Fetching:** Channels only fetched when version is selected
- **30-second Timeout:** Prevents hanging API calls
- **Fallback Strategy:** Generated channels if API is unavailable
- **Single Request:** One API call per version selection
- **Client-side Caching:** Results cached in React component state

## Future Enhancements

1. **Channel Metadata:** Include release dates, support status, architecture info
2. **Channel Filtering:** Filter by channel type (stable, fast, candidate, eus)
3. **Version Validation:** Ensure selected channel is compatible with version
4. **Release Timeline:** Show channel progression and upgrade paths
5. **Caching Strategy:** Server-side caching to improve response times
6. **Channel Descriptions:** Add tooltips explaining each channel type

## Error Scenarios & Handling

| Scenario | Frontend Behavior | API Response |
|----------|------------------|--------------|
| Invalid version format | Shows fallback channels | 400 error with validation message |
| Network timeout | Shows fallback channels | 504 timeout error |
| oc-mirror failure | Shows fallback channels | 500 error with details |
| No version selected | Channel dropdown disabled | N/A |
| API unavailable | Shows fallback channels | Connection error |

This implementation provides a robust, user-friendly experience for selecting appropriate OpenShift channels based on real-time data from the oc-mirror tool.
