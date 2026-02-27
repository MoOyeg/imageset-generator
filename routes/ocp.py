"""
OCP Blueprint — Versions, channels, and releases endpoints.
"""

import json
import os
import re
import subprocess
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app

ocp_bp = Blueprint('ocp', __name__)


# ============================================================
# Core logic functions (called by route handlers AND maintenance)
# ============================================================

def do_refresh_versions():
    """Core logic: run oc-mirror, parse, save file. Returns list of release strings. Raises on failure."""
    current_app.logger.debug("Refreshing OCP releases...")
    releases = []
    static_file_path = os.path.join("data", "ocp-versions.json")

    result = subprocess.run(['oc-mirror', 'list', 'releases'], capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        raise Exception(f"oc-mirror command failed: {result.stderr}")

    lines = result.stdout.strip().split('\n')
    for line in lines:
        line = line.strip()
        if re.match(r'^\d+\.\d+$', line):
            releases.append(line)

    releases.sort(key=lambda x: tuple(map(int, x.split('.'))))

    current_app.logger.debug(f"Saving refreshed releases to {static_file_path}")
    with open(static_file_path, 'w') as f:
        json.dump({
            "releases": releases,
            "count": len(releases),
            "source": "oc-mirror",
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)

    return releases


def do_refresh_ocp_channels(version=None):
    """Core logic: refresh channels. Returns dict of {version: [channels]}. Raises on failure."""
    current_app.logger.debug("Refreshing OCP channels...")
    channels = {}

    static_file_path = os.path.join("data", "ocp-channels.json")
    version_list = []
    if version:
        current_app.logger.debug(f"Fetching channels for specific version: {version}")
        version_list.append(version)
    else:
        current_app.logger.debug("Fetching channels for all available versions")
        try:
            versions_file = os.path.join("data", "ocp-versions.json")
            if os.path.exists(versions_file):
                with open(versions_file, 'r') as f:
                    data = json.load(f)
                    releases = data.get("releases", [])
                    current_app.logger.debug(f"Loaded {len(releases)} releases from static file")
                    for release in releases:
                        if re.match(r'^\d+\.\d+$', release):
                            version_list.append(release)
        except Exception as e:
            current_app.logger.error(f"Error loading static OCP versions file: {e}")

    if not version_list:
        raise Exception("No valid OCP versions found to refresh channels")

    for ver in version_list:
        current_app.logger.debug(f"Running oc-mirror to refresh channels for version {ver}...")
        result = subprocess.run(['oc-mirror', 'list', 'releases', '--channels', '--version', ver], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            raise Exception(f"oc-mirror command failed for version {ver}: {result.stderr}")

        lines = result.stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if re.match(r'^[A-Z,a-z]*\-\d.\d+$', line):
                if ver not in channels:
                    channels[ver] = []
                channels[ver].append(line)

    # Merge with existing
    old_channels = {}
    try:
        if os.path.exists(static_file_path):
            with open(static_file_path, 'r') as f:
                data = json.load(f)
            old_channels = data.get("channels", {})
    except Exception as e:
        current_app.logger.warning(f"Could not load static OCP versions file: {e}")

    for ver in version_list:
        old_channels.update({ver: channels.get(ver, [])})

    current_app.logger.debug(f"Saving refreshed channels to {static_file_path}")
    with open(static_file_path, 'w') as f:
        json.dump({
            "channels": old_channels,
            "count": len(old_channels),
            "source": "oc-mirror",
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)

    return channels


def do_refresh_ocp_releases(version, channel):
    """Core logic: refresh releases for a version/channel. Returns dict of {channel: [releases]}. Raises on failure."""
    current_app.logger.debug("Refreshing OCP releases...")

    if not re.match(r'^\d+\.\d+$', version):
        raise ValueError('Invalid version format. Expected format is X.Y (e.g., 4.14)')
    if not re.match(r'^[A-Za-z0-9\-]+\d+\.\d+$', channel):
        raise ValueError('Invalid channel format. Expected alphanumeric characters and hyphens only')

    channels_releases = {}
    static_file_path = os.path.join("data", "channel-releases.json")

    current_app.logger.debug(f"Running oc-mirror to refresh releases for version {version} and channel {channel}...")
    result = subprocess.run(['oc-mirror', 'list', 'releases', '--channel', channel, '--version', version], capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        raise Exception(f"oc-mirror command failed: {result.stderr}")

    lines = result.stdout.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line == "":
            continue
        if re.match(r'^Architecture', line):
            continue
        if re.match(r'^Channel:', line):
            continue
        if re.match(r'^Listing', line):
            continue
        if re.match(r'.*oc-mirror.*', line):
            continue
        if channel not in channels_releases:
            channels_releases[channel] = []
        channels_releases[channel].append(line)

    # Merge with existing
    old_channels_releases = {}
    try:
        if os.path.exists(static_file_path):
            with open(static_file_path, 'r') as f:
                data = json.load(f)
            old_channels_releases = data.get("channel_releases", {})
    except Exception as e:
        current_app.logger.warning(f"Could not load static OCP versions file: {e}")

    old_channels_releases.update(channels_releases)

    current_app.logger.debug(f"Saving refreshed releases to {static_file_path}")
    with open(static_file_path, 'w') as f:
        json.dump({
            "channel_releases": old_channels_releases,
            "count": len(old_channels_releases),
            "source": "oc-mirror",
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)

    return channels_releases


# ============================================================
# Route handlers
# ============================================================

@ocp_bp.route("/versions/refresh", methods=["POST"])
def refresh_versions():
    """Refresh the list of available OCP releases"""
    try:
        releases = do_refresh_versions()
        return jsonify({
            'status': 'success',
            'releases': releases,
            'count': len(releases),
            'timestamp': datetime.now().isoformat(),
            'source': 'oc-mirror'
        })
    except Exception as e:
        current_app.logger.error(f"Error refreshing releases: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to refresh releases: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500


@ocp_bp.route('/versions/', methods=['GET'])
def get_versions():
    """Get available OCP releases using static files or oc-mirror"""
    current_app.logger.debug("Fetching OCP releases...")
    releases = []

    try:
        static_file_path = os.path.join("data", "ocp-versions.json")
        if os.path.exists(static_file_path):
            with open(static_file_path, 'r') as f:
                data = json.load(f)
                releases = data.get("releases", [])
                current_app.logger.debug(f"Loaded {len(releases)} releases from static file")
    except Exception as e:
        current_app.logger.error(f"Error loading static OCP versions file: {e}")

    if releases:
        current_app.logger.debug("Static file found, using cached releases")
        return jsonify({
            'status': 'success',
            'releases': releases,
            'count': len(releases),
            'timestamp': datetime.now().isoformat(),
            'source': 'static_file'
        })

    try:
        releases = do_refresh_versions()
        return jsonify({
            'status': 'success',
            'releases': releases,
            'count': len(releases),
            'timestamp': datetime.now().isoformat(),
            'source': 'oc-mirror'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch releases from oc-mirror: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500


@ocp_bp.route("/ocp-versions", methods=["GET"])
def get_ocp_versions_static():
    """Get OCP versions from static file"""
    try:
        static_file_path = os.path.join("data", "ocp-versions.json")
        if os.path.exists(static_file_path):
            with open(static_file_path, "r") as f:
                data = json.load(f)
                return jsonify({
                    "status": "success",
                    "message": "OCP versions from static file",
                    "releases": data.get("releases", []),
                    "available_versions": data.get("releases", []),
                    "count": data.get("count", 0),
                    "source": data.get("source", "static_file"),
                    "timestamp": datetime.now().isoformat()
                })
        else:
            return jsonify({
                "status": "error",
                "message": "Static OCP versions file not found",
                "timestamp": datetime.now().isoformat()
            }), 404
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error reading OCP versions: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500


@ocp_bp.route('/channels/refresh', methods=['POST'])
def refresh_ocp_channels():
    """Refresh the list of available OCP channels for each version"""
    try:
        channels = do_refresh_ocp_channels()
        return jsonify({
            'status': 'success',
            'channels': channels,
            'count': len(channels),
            'timestamp': datetime.now().isoformat(),
            'source': 'oc-mirror'
        })
    except Exception as e:
        current_app.logger.error(f"Error refreshing channels: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to refresh channels: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500


@ocp_bp.route("/channels/<version>", methods=["GET"])
def get_ocp_channels(version):
    """Get available OCP channels for a specific version using oc-mirror"""
    if version is None:
        return jsonify({
            'status': 'error',
            'message': 'Version parameter is required',
            'timestamp': datetime.now().isoformat()
        }), 400

    if not re.match(r'^\d+\.\d+$', version):
        return jsonify({
            'status': 'error',
            'message': 'Invalid version format. Expected format is X.Y (e.g., 4.14)',
            'timestamp': datetime.now().isoformat()
        }), 400

    static_file_path = os.path.join("data", "ocp-channels.json")

    # Try to load from static file first
    try:
        if os.path.exists(static_file_path):
            with open(static_file_path, 'r') as f:
                data = json.load(f)
            channels = data.get("channels", [])
            channel_data = channels.get(version, [])
            if channel_data:
                return jsonify({
                    'status': 'success',
                    'version': version,
                    'channels': channel_data,
                    'source': 'static_file',
                    'timestamp': datetime.utcnow().isoformat()
                })
    except Exception as e:
        current_app.logger.warning(f"Could not load static OCP versions file: {e}")

    # If static file does not exist, run oc-mirror to get channels
    try:
        channels = do_refresh_ocp_channels(version)
        if version in channels:
            return jsonify({
                'status': 'success',
                'version': version,
                'channels': channels[version],
                'source': 'oc-mirror',
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'No channels found for version {version}',
                'timestamp': datetime.utcnow().isoformat()
            }), 404
    except Exception as e:
        current_app.logger.error(f"Error running oc-mirror to get channels for version {version}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get OCP channels for version {version}: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500


@ocp_bp.route('/releases/refresh', methods=['POST'])
def refresh_ocp_releases():
    """Refresh the list of available OCP releases for a specific version and channel"""
    version = request.args.get('version')
    channel = request.args.get('channel')

    if version is None or channel is None:
        return jsonify({
            'status': 'error',
            'message': 'Version and channel parameter is required',
            'timestamp': datetime.now().isoformat()
        }), 400

    try:
        channels_releases = do_refresh_ocp_releases(version, channel)
        return jsonify({
            'status': 'success',
            'channel_releases': channels_releases,
            'count': len(channels_releases),
            'timestamp': datetime.now().isoformat(),
            'source': 'oc-mirror'
        })
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 400
    except Exception as e:
        current_app.logger.error(f"Error refreshing releases: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to refresh releases: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500


@ocp_bp.route("/releases/<version>/<channel>", methods=["GET"])
def get_ocp_releases(version, channel):
    """Get available OCP releases for a specific version and channel using oc-mirror"""
    if version is None:
        return jsonify({
            'status': 'error',
            'message': 'Version parameter is required',
            'timestamp': datetime.now().isoformat()
        }), 400

    if channel is None:
        return jsonify({
            'status': 'error',
            'message': 'Channel parameter is required',
            'timestamp': datetime.now().isoformat()
        }), 400

    if not re.match(r'^\d+\.\d+$', version):
        return jsonify({
            'status': 'error',
            'message': 'Invalid version format. Expected format is X.Y (e.g., 4.14)',
            'timestamp': datetime.now().isoformat()
        }), 400

    if not re.match(r'^[A-Za-z0-9\-]+\d+\.\d+$', channel):
        return jsonify({
            'status': 'error',
            'message': 'Invalid channel format. Expected alphanumeric characters and hyphens only',
            'timestamp': datetime.now().isoformat()
        }), 400

    # Try to load from static file first
    current_app.logger.debug(f"Checking static file for releases for version {version} and channel {channel}")
    static_file_path = os.path.join("data", "channel-releases.json")

    try:
        with open(static_file_path, 'r') as f:
            data = json.load(f)
        channel_releases = data.get("channel_releases", {}).get(channel, [])
        if channel_releases:
            return jsonify({
                'status': 'success',
                'version': version,
                'channel': channel,
                'releases': channel_releases,
                'source': 'static_file',
                'timestamp': datetime.now().isoformat()
            })
    except Exception as e:
        current_app.logger.warning(f"Could not load static channel releases file: {e}")

    # If static file does not exist, run oc-mirror to get releases
    try:
        channels_releases = do_refresh_ocp_releases(version, channel)
        return jsonify({
            'status': 'success',
            'version': version,
            'channel': channel,
            'releases': channels_releases.get(channel, []),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"Error getting OCP releases for version {version} and channel {channel}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get OCP releases for version {version} and channel {channel}: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500
