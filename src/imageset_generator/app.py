#!/usr/bin/env python3
"""
OpenShift ImageSetConfiguration Generator - Flask API Backend

This Flask application provides a REST API for the OpenShift ImageSetConfiguration generator.
It serves as the backend for the React frontend application.
"""

import json
import re
from flask import Flask, request, jsonify, send_from_directory
from packaging.version import Version as Version_Checker
from flask_cors import CORS
import yaml
import os
import subprocess
import tempfile
from datetime import datetime
from .generator import ImageSetGenerator
import traceback
from .constants import TLS_VERIFY, TIMEOUT_OPM_RENDER
from .validation import validate_version, validate_channel, safe_path_component, ValidationError
from .exceptions import (
    ImageSetGeneratorError,
    CatalogError,
    CatalogRenderError,
    CatalogParseError,
    OperatorError,
    OperatorNotFoundError,
    VersionError,
    ConfigurationError,
    FileOperationError,
    NetworkError,
    GenerationError,
)

def build_opm_command(catalog_url, output_format='yaml', skip_tls=None):
    """
    Build OPM render command with configurable TLS verification.
    
    Args:
        catalog_url: Full catalog URL (e.g., registry.redhat.io/redhat/redhat-operator-index:v4.18)
        output_format: Output format for OPM (default: 'yaml', can be 'json')
        skip_tls: Override TLS verification (None uses TLS_VERIFY constant from constants.py)
    
    Returns:
        List of command arguments for subprocess
    """
    cmd = ['opm', 'render']
    
    # Use provided skip_tls value, or default to TLS_VERIFY constant
    should_skip_tls = skip_tls if skip_tls is not None else not TLS_VERIFY
    
    if should_skip_tls:
        cmd.append('--skip-tls')
    
    if output_format == 'json':
        cmd.extend(['--output', 'json'])
    
    cmd.append(catalog_url)
    return cmd

def process_operator_data(operator):
    """Process operator data to handle selected versions and other parameters"""
    if isinstance(operator, str):
        return {
            "name": operator.strip(),
            "catalog": None,
            "channel": None,
            "version": None,
            "minVersion": None,
            "maxVersion": None,
            "selectedVersions": None
        }
    elif isinstance(operator, dict):
        return {
            "name": operator.get('name', '').strip() if isinstance(operator.get('name'), str) else '',
            "catalog": operator.get('catalog', '').strip() if isinstance(operator.get('catalog'), str) else None,
            "channel": operator.get('channel', '').strip() if isinstance(operator.get('channel'), str) else None,
            "version": operator.get('version', '').strip() if isinstance(operator.get('version'), str) else None,
            "minVersion": operator.get('minVersion', '').strip() if isinstance(operator.get('minVersion'), str) else None,
            "maxVersion": operator.get('maxVersion', '').strip() if isinstance(operator.get('maxVersion'), str) else None,
            "selectedVersions": operator.get('selectedVersions', []) if isinstance(operator.get('selectedVersions'), list) else None,
            "fileName": operator.get('fileName') if operator.get('fileName') else None
        }
    else:
        return None

def prepare_operator_entry(op_data):
    """Prepare operator entry for the generator from processed data"""
    if not op_data or not op_data["name"]:
        return None
        
    entry = {"name": op_data["name"]}
    
    if op_data["channel"]:
        entry["channel"] = op_data["channel"]
    
    if op_data["selectedVersions"]:
        entry["selectedVersions"] = op_data["selectedVersions"]
    else:
        if op_data["minVersion"]:
            entry["minVersion"] = op_data["minVersion"]
        if op_data["maxVersion"]:
            entry["maxVersion"] = op_data["maxVersion"]
    
    if op_data["fileName"]:
        entry["fileName"] = op_data["fileName"]
        
    return entry

app = Flask(__name__, static_folder='frontend/build')
CORS(app)  # Enable CORS for all routes

# Initialize automation (optional - only if config exists)
try:
    from automation.api import automation_bp, init_automation

    # Register automation blueprint
    app.register_blueprint(automation_bp)

    # Initialize and start automation scheduler
    automation_config_path = 'automation/config.yaml'
    if os.path.exists(automation_config_path):
        scheduler = init_automation(automation_config_path)
        if scheduler:
            app.logger.info("Automation scheduler initialized and started")
        else:
            app.logger.info("Automation scheduler is disabled in configuration")
    else:
        app.logger.info(f"Automation config not found at {automation_config_path}, skipping automation")
except ImportError as e:
    app.logger.info(f"Automation module not available: {e}")
except Exception:
    app.logger.exception("Failed to initialize automation")

def return_base_catalog_info(catalog_url):
    base_catalogs = [
            {
                "name": "Red Hat Operators",
                "base_url": "registry.redhat.io/redhat/redhat-operator-index",
                "description": "Official Red Hat certified operators",
                "default": True
            },
            {
                "name": "Community Operators",
                "base_url": "registry.redhat.io/redhat/community-operator-index",
                "description": "Community-maintained operators",
                "default": False
            },
            {
                "name": "Certified Operators", 
                "base_url": "registry.redhat.io/redhat/certified-operator-index",
                "description": "Third-party certified operators",
                "default": False
            },
            {
                "name": "Red Hat Marketplace",
                "base_url": "registry.redhat.io/redhat/redhat-marketplace-index",
                "description": "Commercial operators from Red Hat Marketplace",
                "default": False
            }
        ]
    
    for catalog in base_catalogs:
        if catalog_url.startswith(catalog['base_url']):
            return {
                "name": catalog['name'],
                "base_url": catalog['base_url'],
                "description": catalog['description'],
                "default": catalog['default']
            }
    return None

def get_operators_from_opm(catalog_url, version_key):
    """Get operators from a catalog using opm render"""
    try:
        full_catalog = f"{catalog_url}:v{version_key}"
        cmd = build_opm_command(full_catalog)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_OPM_RENDER)
        
        if result.returncode != 0:
            raise CatalogRenderError(
                f"opm render failed: {result.stderr}",
                catalog=full_catalog,
                version=version_key
            )
            
        operators = set()
        docs = list(yaml.safe_load_all(result.stdout))
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if doc.get('kind') == 'ClusterServiceVersion':
                metadata = doc.get('metadata', {})
                name = metadata.get('name')
                if name:
                    op_name = name.split('.')[0]
                    operators.add(op_name)
                    
        return sorted(list(operators))
    except CatalogRenderError:
        raise
    except Exception as e:
        raise CatalogError(
            f"Error getting operators from opm",
            catalog=catalog_url,
            version=version_key,
            original_error=e
        )

def get_cached_operators(cache_file):
    """Get operators from cache file if it exists and is not expired"""
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                return data.get('operators', [])
        except Exception:
            pass
    return None

def load_operators_from_file(catalog_key, version_key):
    """Load operators from cached JSON files"""
    try:

        # Try to load from cache file first
        catalog_index= (catalog_key.split('/')[-1]).split(':')[0]
        static_file_path = os.path.join("data", f"operators-{catalog_index}-{version_key}.json")

        if os.path.exists(static_file_path):
            with open(static_file_path, 'r') as f:
                data = json.load(f)
                return data.get('operators', None)
        
        return None
        
    except Exception as e:
        app.logger.error(f"Error loading operators from file: {e}")
        return None

def load_catalogs_from_file(version_key):
    """Load catalog information from cached JSON files"""

    try:
        filename = f'catalogs-{version_key}.json'
        filepath = os.path.join('data', filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                catalogs = json.load(f)
                return catalogs
        
        return None
        
    except Exception as e:
        app.logger.error(f"Error loading catalogs from file: {e}")
        return None



@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    """Serve React app"""
    # Don't interfere with static files or API routes
    if path.startswith('static/') or path.startswith('api/'):
        return app.send_static_file(path) if path.startswith('static/') else None
    
    # For all other paths, check if the file exists in static folder
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route("/api/versions/refresh", methods=["POST"])
def refresh_versions():
    """Refresh the list of available OCP releases"""
    # Logic to refresh the releases (e.g., by re-running oc-mirror)
    app.logger.debug("Refreshing OCP releases...")
    releases = []
    static_file_path = os.path.join("data", "ocp-versions.json")
    
    try:
        # Run oc-mirror to get the latest releases
        app.logger.debug("Running oc-mirror to refresh releases...")
        result = subprocess.run(['oc-mirror', 'list', 'releases'], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            app.logger.error(f"oc-mirror command failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to refresh releases',
                'error': result.stderr,
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Parse the output to extract releases
        lines = result.stdout.strip().split('\n')
        
        for line in lines:

            line = line.strip()
            if re.match(r'^\d+\.\d+$', line):  # Match semantic versioning
                releases.append(line)
        
        # Sort releases in semantic version order
        releases.sort(key=lambda x: tuple(map(int, x.split('.'))))
        
        # Save to static file for future use
        app.logger.debug(f"Saving refreshed releases to {static_file_path}")
        with open(static_file_path, 'w') as f:
            json.dump({
                "releases": releases,
                "count": len(releases),
                "source": "oc-mirror",
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
            
    except Exception as e:
        app.logger.error(f"Error refreshing releases: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to refresh releases: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500
        
    return jsonify({
        'status': 'success',
        'releases': releases,
        'count': len(releases),
        'timestamp': datetime.now().isoformat(),
        'source': 'oc-mirror'
    })

def _get_operator_file_paths(catalog_index, version):
    """
    Generate file paths for operator data storage.
    
    Args:
        catalog_index: Catalog index name (e.g., 'redhat-operator-index')
        version: Version string (e.g., 'v4.18')
    
    Returns:
        Tuple of (main_path, index_path, data_path, channel_path)
    """
    base_name = f"operators-{catalog_index}-{version}"
    return (
        os.path.join("data", f"{base_name}.json"),
        os.path.join("data", f"{base_name}-index.json"),
        os.path.join("data", f"{base_name}-data.json"),
        os.path.join("data", f"{base_name}-channel.json")
    )

def _render_catalog_index(catalog, output_path):
    """
    Render catalog using OPM and save to file.
    
    Args:
        catalog: Full catalog URL
        output_path: Path to save rendered output
    
    Raises:
        subprocess.CalledProcessError: If OPM command fails
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return  # File already exists and is not empty
    
    with open(output_path, 'w') as f:
        cmd = build_opm_command(catalog, output_format='json')
        subprocess.run(cmd, stdout=f, check=True)

def _extract_operator_data(index_path, output_path):
    """
    Extract operator field data using jq filter.
    
    Args:
        index_path: Path to catalog index file
        output_path: Path to save filtered data
    
    Raises:
        subprocess.CalledProcessError: If jq command fails
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return  # File already exists and is not empty
    
    jq_filter = '''
    select(.schema == "olm.bundle")
    | [
        .package,
        .name,
        (.properties[]? | select(.type == "olm.package") | .value.version),
        ((.properties[]? | select(.type == "olm.csv.metadata") | .value.keywords | join(",")) // ""),
        (.properties[]? | select(.type == "olm.csv.metadata") | .value.annotations.description),
        (.properties[]? | select(.schema == "olm.channel") | .name)
    ] | @tsv
    '''
    
    cmd = ["jq", "-r", jq_filter]
    with open(index_path, "r") as infile, open(output_path, "w") as outfile:
        subprocess.run(cmd, stdin=infile, stdout=outfile, check=True)

def _extract_channel_data(index_path, output_path):
    """
    Extract operator channel data using jq filter.
    
    Args:
        index_path: Path to catalog index file
        output_path: Path to save channel data
    
    Raises:
        subprocess.CalledProcessError: If jq command fails
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return  # File already exists and is not empty
    
    jq_filter = '''
    select(.schema == "olm.channel")
    | [.package, .name, .entries[]?.name, .channelName] | @tsv
    '''
    
    cmd = ["jq", "-r", jq_filter]
    with open(index_path, "r") as infile, open(output_path, "w") as outfile:
        subprocess.run(cmd, stdin=infile, stdout=outfile, check=True)

def _find_operator_channel(operator_name, channel_path):
    """
    Find the channel for a specific operator.
    
    Args:
        operator_name: Name of the operator to search for
        channel_path: Path to channel data file
    
    Returns:
        Channel name if found, empty string otherwise
    """
    try:
        with open(channel_path, "r") as f:
            for line in f:
                if operator_name in line:
                    fields = line.strip().split('\t')
                    if len(fields) > 1 and fields[1]:
                        return fields[1]
    except Exception as e:
        app.logger.warning(f"Could not find channel for {operator_name}: {e}")
    
    return ""

def _parse_operator_data(data_path, channel_path):
    """
    Parse TSV operator data and enrich with channel information.
    
    Args:
        data_path: Path to operator data TSV file
        channel_path: Path to channel data TSV file
    
    Returns:
        List of operator dictionaries
    """
    operators = []
    
    with open(data_path, "r") as f:
        lines = [line for line in f if line.strip()]
        
        for line in lines:
            fields = line.strip().split('\t')
            
            if len(fields) < 3:
                continue  # Skip malformed lines
            
            operator = {
                "package": fields[0],
                "name": fields[0],
                "version": fields[2] if len(fields) > 2 else ""
            }
            
            # Add optional fields if available
            if len(fields) >= 5:
                operator["keywords"] = fields[3].split(",") if fields[3] else []
                operator["description"] = fields[4]
                operator["channel"] = fields[5] if len(fields) > 5 else ""
            
            # Find channel from channel file if not set or to override
            if len(fields) > 1 and fields[1]:
                channel = _find_operator_channel(fields[1], channel_path)
                if channel:
                    operator["channel"] = channel
            
            operators.append(operator)
    
    return operators

def _cleanup_intermediate_files(*file_paths):
    """
    Remove intermediate processing files.
    
    Args:
        *file_paths: Variable number of file paths to remove
    """
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            app.logger.error(f"Error removing {path}: {e}")

@app.route('/api/operators/refresh', methods=['POST'])
def refresh_ocp_operators(catalog=None, version=None):
    """Refresh the list of available OCP operators"""
    app.logger.debug("Refreshing OCP operators...")
    
    # Validate required parameters
    if catalog is None:
        return jsonify({
            'status': 'error',
            'message': 'Catalog parameter is required',
            'timestamp': datetime.now().isoformat()
        }), 400

    # Extract version from catalog if not provided
    if version is None or not version.strip():
        version = catalog.split(':')[-1]

    # Generate file paths
    catalog_index = (catalog.split('/')[-1]).split(':')[0]
    main_path, index_path, data_path, channel_path = _get_operator_file_paths(catalog_index, version)

    try:
        # Step 1: Render catalog index
        _render_catalog_index(catalog, index_path)
        
        # Step 2: Extract operator data
        _extract_operator_data(index_path, data_path)
        
        # Step 3: Extract channel data
        _extract_channel_data(index_path, channel_path)
        
        # Step 4: Parse and combine data
        operators = _parse_operator_data(data_path, channel_path)
        
        # Step 5: Write final output
        with open(main_path, "w") as f:
            json.dump({
                "operators": operators,
                "count": len(operators),
                "source": "opm",
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        # Step 6: Cleanup intermediate files
        _cleanup_intermediate_files(index_path, data_path, channel_path)
        
        return jsonify({
            'status': 'success',
            'data': operators,
            'timestamp': datetime.now().isoformat()
        })
        
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Error processing catalog: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to refresh operators: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500
    except Exception as e:
        app.logger.error(f"Error refreshing operators: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to refresh operators: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/releases/refresh', methods=['POST'])
def refresh_ocp_releases(version=None, channel=None):
    """Refresh the list of available OCP releases for a specific version and channel"""
    app.logger.debug("Refreshing OCP releases...")
    if version is None or channel is None:
        return jsonify({
            'status': 'error',
            'message': 'Version and channel parameter is required',
            'timestamp': datetime.now().isoformat()
        }), 400
        
    # Validate version format using centralized validation
    try:
        version = validate_version(version)
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 400
        
    # Validate channel format using centralized validation
    try:
        channel = validate_channel(channel)
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 400
        
    channels_releases = {}
    static_file_path = os.path.join("data", "channel-releases.json")
    try:
        # Run oc-mirror to get the latest releases for the specified version and channel
        app.logger.debug(f"Running oc-mirror to refresh releases for version {version} and channel {channel}...")
        result = subprocess.run(['oc-mirror', 'list', 'releases', '--channel', channel, '--version', version], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            app.logger.error(f"oc-mirror command failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to refresh releases for version {version} and channel {channel}',
                'error': result.stderr,
                'timestamp': datetime.now().isoformat()
            }), 500
            
        # Parse the output to extract releases
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line == "":
                continue
            if re.match(r'^Architecture',line):
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
        
        # Try to load from static file first
        old_channels_releases = {}
        try:
            if os.path.exists(static_file_path):
                with open(static_file_path, 'r') as f:
                    data = json.load(f)
                old_channels_releases = data.get("channel_releases", {})
        except Exception as e:
            app.logger.warning(f"Could not load static OCP versions file: {e}")
        
        # Merge old channels with new ones
        old_channels_releases.update(channels_releases)

        # Save to static file for future use
        app.logger.debug(f"Saving refreshed releases to {static_file_path}")
        with open(static_file_path, 'w') as f:
            json.dump({
                "channel_releases": old_channels_releases,
                "count": len(old_channels_releases),
                "source": "oc-mirror",
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
            
    except Exception as e:
        app.logger.error(f"Error refreshing releases: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to refresh releases: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500
        
    return jsonify({
        'status': 'success',
        'channel_releases': channels_releases,
        'count': len(channels_releases),
        'timestamp': datetime.now().isoformat(),
        'source': 'oc-mirror'
    })

@app.route('/api/channels/refresh', methods=['POST'])
def refresh_ocp_channels(version=None):
    """Refresh the list of available OCP channels for each version"""
    app.logger.debug("Refreshing OCP channels...")
    channels = {}
    
    static_file_path = os.path.join("data", "ocp-channels.json")
    version_list = []
    # Use Version if provided, or get available versions if not provided
    if version:
        app.logger.debug(f"Fetching channels for specific version: {version}")
        version_list.append(version)
    else:
        app.logger.debug("Fetching channels for all available versions")
        try:
        # Try to load from static file first
            static_file_path = os.path.join("data", "ocp-versions.json")
            if os.path.exists(static_file_path):
                with open(static_file_path, 'r') as f:
                    data = json.load(f)
                    releases = data.get("releases", [])
                    app.logger.debug(f"Loaded {len(releases)} releases from static file")
                    for release in releases:
                        if re.match(r'^\d+\.\d+$', release):
                            version_list.append(release)
        except Exception as e:
            app.logger.error(f"Error loading static OCP versions file: {e}")
            
    if not version_list:
        app.logger.error("No valid OCP versions found to refresh channels")
        return jsonify({
            'status': 'error',
            'message': 'No valid OCP versions found to refresh channels',
            'timestamp': datetime.now().isoformat()
        }), 400


    try:
        for version in version_list:
            app.logger.debug(f"Running oc-mirror to refresh channels for version {version}...")
            result = subprocess.run(['oc-mirror', 'list', 'releases', '--channels','--version', version], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                app.logger.error(f"oc-mirror command failed for version {version}: {result.stderr}")
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to refresh channels for version {version}',
                    'error': result.stderr,
                    'timestamp': datetime.now().isoformat()
                }), 500
                
        
            # Parse the output to extract channels
            lines = result.stdout.strip().split('\n')
        
            for line in lines:
                line = line.strip()
                if re.match(r'^[A-Z,a-z]*\-\d.\d+$', line):  # Match semantic versioning
                    if version not in channels:
                        channels[version] = []
                    channels[version].append(line)
        
        # Try to load from static file first
        old_channels = {}
        try:
            if os.path.exists(static_file_path):
                with open(static_file_path, 'r') as f:
                    data = json.load(f)
                old_channels = data.get("channels", {})
        except Exception as e:
            app.logger.warning(f"Could not load static OCP versions file: {e}")
        
        # Merge old channels with new ones
        for version in version_list:
            old_channels.update({version: channels.get(version, [])})

        # Save to static file for future use
        app.logger.debug(f"Saving refreshed channels to {static_file_path}")
        with open(static_file_path, 'w') as f:
            json.dump({
                "channels": old_channels,
                "count": len(old_channels),
                "source": "oc-mirror",
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
            
    except Exception as e:
        app.logger.error(f"Error refreshing channels: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to refresh channels: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500
        
    return jsonify({
        'status': 'success',
        'channels': channels,
        'count': len(channels),
        'timestamp': datetime.now().isoformat(),
        'source': 'oc-mirror'
    })

@app.route('/api/operators/catalogs/<version>/refresh', methods=['POST'])
def refresh_catalogs_for_version(version=None):
    """Refresh available operator catalogs dynamically using oc-mirror"""
    version_list = []
    discovered_catalogs = {}
    
    try:
        if version is not None:
            # Extract major.minor version from version string
            version_list.append(version)
        else:
            # If no version provided, refresh for all available versions
            static_file_path = os.path.join("data", "ocp-versions.json")
            if os.path.exists(static_file_path):
                with open(static_file_path, 'r') as f:
                    data = json.load(f)
                    releases = data.get("releases", [])
                    app.logger.debug(f"Loaded {len(releases)} releases from static file")
                    for release in releases:
                        if re.match(r'^\d+\.\d+$', release):
                            version_list.append(release)

        
        for version in version_list:
            # Extract major.minor version from version string
            if '.' in version:
                version_parts = version.split('.')
                major = version_parts[0]
                minor = version_parts[1]
                version_key = f"{major}.{minor}"
            else:
                version_key = version
            
            app.logger.info(f"Discovering catalogs for OCP version {version_key}...")
            
            try:
                app.logger.info(f"Discovering catalogs for OCP version {version_key}...")
                
                #Obtain available catalogs by running oc-mirror list operators --catalogs --version=<version>
                cmd = ['oc-mirror', 'list', 'operators', '--catalogs', f'--version={version_key}']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    app.logger.error(f"oc-mirror command failed: {result.stderr}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Failed to discover catalogs: {result.stderr.strip()}',
                        'timestamp': datetime.utcnow().isoformat()
                    }), 500
                    
                # Parse the output to extract catalog names and URLs
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('WARN') and not line.startswith('INFO'):
                        # Assume the line contains a catalog URL that looks like registry.redhat.io/redhat/redhat-operator-index:v4.20
                        if re.match(r'^Available OpenShift OperatorHub catalogs',line):
                            continue  # Skip header lines
                        if re.match(r'OpenShift \d\.\d+',line):
                            continue  # Skip version header lines                            
                        match = re.match(r'^(.*?)(:v\d+\.\d+)?$', line)
                        if match:
                            catalog_url = match.group(1)
                            if "Invalid" in line:
                                catalog_info = {
                                    'name': catalog_url,
                                    'description': 'Invalid catalog or Deprecated Catalog',
                                    'default': False
                                }
                            else:
                                catalog_info = return_base_catalog_info(catalog_url)
                            if catalog_info:
                                catalog_name = catalog_info['name']
                                if version_key not in discovered_catalogs:
                                    discovered_catalogs[version_key] = []
                                discovered_catalogs[version_key].append({
                                    'name': catalog_name,
                                    'url': catalog_url,
                                    'description': catalog_info['description'],
                                    'default': catalog_info['default']
                                })
            except subprocess.TimeoutExpired:
                app.logger.error(f"Timeout while discovering catalogs for version {version_key}")
                return jsonify({
                    'status': 'error',
                    'message': f'Timeout while discovering catalogs for version {version_key}',
                    'timestamp': datetime.utcnow().isoformat()
                }), 500
                
    except Exception as e:
        app.logger.error(f"Error discovering catalogs: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to discover catalogs: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

    # Write Catalog info to File
    try:
        with open(f"data/catalogs-{version}.json", 'w') as f:
            json.dump(discovered_catalogs, f, indent=2)
    except Exception as e:
        app.logger.warning(f"Could not save catalog file: {e}")

    return jsonify({
        'status': 'success',
        'version': version,
        'catalogs': discovered_catalogs,
        'source': 'oc-mirror',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/versions/', methods=['GET'])
def get_versions():
    # Get available OCP releases using static files or oc-mirror
    app.logger.debug("Fetching OCP releases...")
    releases = []

  
    try:
        # Try to load from static file first
        static_file_path = os.path.join("data", "ocp-versions.json")
        if os.path.exists(static_file_path):
            with open(static_file_path, 'r') as f:
                data = json.load(f)
                releases = data.get("releases", [])
                app.logger.debug(f"Loaded {len(releases)} releases from static file")
    except Exception as e:
        app.logger.error(f"Error loading static OCP versions file: {e}")



    # If static file does not exist, run oc-mirror to get releases
    if releases != []:
        app.logger.debug("Static file found, using cached releases")
        return jsonify({
            'status': 'success',
            'releases': releases,
            'count': len(releases),
            'timestamp': datetime.now().isoformat(),
            'source': 'static_file'
        })

    release_update = refresh_versions()

    if release_update.json.get("status") == "success":
        releases = release_update.json.get("releases", [])
        return jsonify({
            'status': 'success',
            'releases': releases,
            'count': len(releases),
            'timestamp': datetime.now().isoformat(),
            'source': 'oc-mirror'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch releases from oc-mirror',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route("/api/releases/<version>/<channel>", methods=["GET"])
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
        
    # Validate version format using centralized validation
    try:
        version = validate_version(version)
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 400
        
    # Validate channel format using centralized validation
    try:
        channel = validate_channel(channel)
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 400
        
    # Try to load from static file first
    app.logger.debug(f"Checking static file for releases for version {version} and channel {channel}")
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
        app.logger.warning(f"Could not load static channel releases file: {e}")
        
    # If static file does not exist, run oc-mirror to get releases
    try:
        release_data = refresh_ocp_releases(version, channel)
        if release_data.json.get("status") == "success":
            return jsonify({
                'status': 'success',
                'version': version,
                'channel': channel,
                'releases': release_data.json.get("channel_releases", []),
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'No releases found for version {version} and channel {channel}',
                'timestamp': datetime.now().isoformat()
            }), 404
    except Exception as e:
        app.logger.error(f"Error getting OCP releases for version {version} and channel {channel}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get OCP releases for version {version} and channel {channel}: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route("/api/channels/<version>", methods=["GET"])
def get_ocp_channels(version):
    """Get available OCP channels for a specific version using oc-mirror"""
    
    if version is None:
        return jsonify({
            'status': 'error',
            'message': 'Version parameter is required',
            'timestamp': datetime.now().isoformat()
        }), 400
        
    # Validate version format using centralized validation
    try:
        version = validate_version(version)
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 400
        
    static_file_path = os.path.join("data", f"ocp-channels.json")
          
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
        app.logger.warning(f"Could not load static OCP versions file: {e}")
                 
    # If static file does not exist, run oc-mirror to get channels
    try:
        channel_data = refresh_ocp_channels(version)
        if channel_data.json.get("status") == "success":
            channels = channel_data.json.get("channels", {})
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
        app.logger.error(f"Error running oc-mirror to get channels for version {version}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get OCP channels for version {version}: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500
        

@app.route('/api/operators/mappings', methods=['GET'])
def get_operator_mappings():
    """Get available operator mappings"""
    # Extract operator mappings from generator
    operator_mappings = {
        "logging": "cluster-logging",
        "logging-operator": "cluster-logging", 
        "monitoring": "cluster-monitoring-operator",
        "cluster-monitoring": "cluster-monitoring-operator",
        "service-mesh": "servicemeshoperator",
        "istio": "servicemeshoperator",
        "serverless": "serverless-operator",
        "knative": "serverless-operator",
        "pipelines": "openshift-pipelines-operator-rh",
        "tekton": "openshift-pipelines-operator-rh",
        "gitops": "openshift-gitops-operator",
        "argocd": "openshift-gitops-operator",
        "storage": "odf-operator",
        "ocs": "odf-operator",
        "ceph": "odf-operator",
        "elasticsearch": "elasticsearch-operator",
        "jaeger": "jaeger-product",
        "kiali": "kiali-ossm"
    }
    
    return jsonify({
        'mappings': operator_mappings,
        'suggestions': list(operator_mappings.keys())
    })


@app.route('/api/operators/catalogs/<version>', methods=['GET'])
def get_operator_catalogs(version):
    """Get operator catalog data for a specific OCP version from static file or oc-mirror"""

    # Extract major.minor version from version string
    if '.' in version:
        version_parts = version.split('.')
        major = version_parts[0]
        minor = version_parts[1]
        version_key = f"{major}.{minor}"
    else:
        version_key = version

    static_file = os.path.join('data', f'catalogs-{version_key}.json')

    # Try to load from static file first
    if os.path.exists(static_file):
        try:
            with open(static_file, 'r') as f:
                catalogs = json.load(f)
            return jsonify({
                'status': 'success',
                'version': version,
                'catalogs': catalogs,
                'source': 'static_file',
                'timestamp': datetime.utcnow().isoformat()
            })
        except Exception as e:
            app.logger.warning(f"Could not load static catalog file: {e}")

    # If static file does not exist, run oc-mirror to obtain it
    catalogs = refresh_catalogs_for_version(version)
    if catalogs.json.get("status") != "success":
        app.logger.error(f"Failed to get catalogs for version {version}: {catalogs.json.get('message')}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get operator catalogs for version {version}: {catalogs.json.get("message")}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

    # If oc-mirror was successful, save the catalogs
    available_catalogs = catalogs.json.get("data", [])
    if not available_catalogs:
        app.logger.warning(f"No catalogs found for version {version}")
        return jsonify({
            'status': 'error',
            'message': f'No operator catalogs found for version {version}',
            'timestamp': datetime.utcnow().isoformat()
        }), 404

    return jsonify({
        'status': 'success',
        'version': version,
        'catalogs': available_catalogs,
        'source': 'oc-mirror',
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/api/operators/catalogs', methods=['GET'])
def get_available_catalogs():
    """Get all available operator catalogs using oc-mirror"""
    return None
    try:
        import subprocess
        import json
        
        # Define standard catalog URLs to check
        standard_catalogs = [
            {
                "name": "Red Hat Operators",
                "url": "registry.redhat.io/redhat/redhat-operator-index",
                "description": "Official Red Hat certified operators"
            },
            {
                "name": "Community Operators", 
                "url": "registry.redhat.io/redhat/community-operator-index",
                "description": "Community-maintained operators"
            },
            {
                "name": "Certified Operators",
                "url": "registry.redhat.io/redhat/certified-operator-index", 
                "description": "Third-party certified operators"
            },
            {
                "name": "Red Hat Marketplace",
                "url": "registry.redhat.io/redhat/redhat-marketplace-index",
                "description": "Commercial operators from Red Hat Marketplace"
            }
        ]
        
        validated_catalogs = []
        
        # Try to validate each catalog with oc-mirror
        for catalog in standard_catalogs:
            try:
                # Test if oc-mirror can access this catalog
                cmd = ['oc-mirror', 'list', 'operators', '--catalogs', catalog['url']]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                catalog_info = catalog.copy()
                if result.returncode == 0:
                    catalog_info['validated'] = True
                    app.logger.info(f"Validated catalog: {catalog['url']}")
                else:
                    catalog_info['validated'] = False
                    app.logger.warning(f"Could not validate catalog: {catalog['url']}")
                
                validated_catalogs.append(catalog_info)
                
            except subprocess.TimeoutExpired:
                catalog_info = catalog.copy()
                catalog_info['validated'] = False
                catalog_info['error'] = 'Timeout while validating'
                validated_catalogs.append(catalog_info)
                app.logger.warning(f"Timeout validating catalog: {catalog['url']}")
                
            except Exception as e:
                catalog_info = catalog.copy()
                catalog_info['validated'] = False
                catalog_info['error'] = str(e)
                validated_catalogs.append(catalog_info)
                app.logger.warning(f"Error validating catalog {catalog['url']}: {e}")
        
        return jsonify({
            'status': 'success',
            'catalogs': validated_catalogs,
            'count': len(validated_catalogs),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error getting available catalogs: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get available catalogs: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/api/operators/catalogs/<version>/list', methods=['GET'])
def list_catalogs_for_version(version):
    """Use oc-mirror to list available catalogs for a specific OCP version"""

    #Check if catalogs for this version are cached
    cached_catalogs = load_catalogs_from_file(version)
    
    if cached_catalogs is not None:
        return jsonify({
            'status': 'success',
            'version': version,
            'catalogs': cached_catalogs,
            'source': 'static_file',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    # If not cached, discover catalogs dynamically
    return refresh_catalogs_for_version(version)


@app.route('/api/operators/list', methods=['GET'])
def get_operators_list():
    """Get list of available operators from cache files"""
    try:
        # Get parameters from query string return none if not provided
        catalog = request.args.get('catalog')
        version = request.args.get('version')
        
        if not catalog:
            return jsonify({
                'status': 'error',
                'message': 'Catalog and version parameters are required'
            }), 400
        
        #Extract version from catalog if empty
        if version is None:
            version = catalog.split(':')[-1]
            
        #if no version present in catalog append version value to catalog
        if version is not None:
            if re.match(r'^\d+\.\d+$', version):
                # If version is in X.Y format, append it to catalog
                if ':v' not in catalog:
                    catalog = f"{catalog}:v{version}"


        # Extract major.minor version from version string
        if '.' in version:
            version_parts = version.split('.')
            major = version_parts[0]
            minor = version_parts[1]
            version_key = f"{major}.{minor}"
        else:
            version_key = version
        


        #Read static file path for operators
        operators = load_operators_from_file(catalog, version_key)

        if operators is None or operators == []:
            app.logger.info(f"No cached operators found for {catalog}:{version_key}, running refresh...")
            #Run Refresh on File
            operators=refresh_ocp_operators(catalog=catalog, version=version_key)

        # Return the operators list
        return jsonify({
            'status': 'success',
            'operators': operators,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        app.logger.error(f"Error loading operators from cache: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to load operators: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/api/operators/<operator_name>/channels', methods=['GET'])
def get_operator_channels(operator_name):
    """Get available channels for a specific operator using oc-mirror"""
    try:
        import subprocess
        import json
        
        # Get parameters from query string
        catalog = request.args.get('catalog', 'registry.redhat.io/redhat/redhat-operator-index')
        version = request.args.get('version', '4.18')
        
        # Extract major.minor version from version string
        if '.' in version:
            version_parts = version.split('.')
            major = version_parts[0]
            minor = version_parts[1]
            version_key = f"{major}.{minor}"
        else:
            version_key = version
        
        # Create versioned catalog URL if not already versioned
        if ':v' not in catalog:
            catalog_url = f"{catalog}:v{version_key}"
        else:
            catalog_url = catalog
        
        app.logger.info(f"Fetching channels for operator {operator_name} from {catalog_url}")
        
        # Run oc-mirror command to list operator details
        cmd = ['oc-mirror', 'list', 'operators', '--catalogs', catalog_url, '--version', version_key, operator_name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            app.logger.warning(f"oc-mirror failed for operator channels: {result.stderr}")
            # Return default channel structure if command fails
            return jsonify({
                'status': 'success',
                'operator': operator_name,
                'catalog': catalog_url,
                'channels': [{'name': 'stable', 'default': True}],
                'default_channel': 'stable',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Parse the output to extract channel information
        channels = []
        default_channel = 'stable'
        
        lines = result.stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            # Look for channel information in the output
            if 'channel' in line.lower() or 'stable' in line or 'fast' in line or 'alpha' in line or 'beta' in line:
                # Extract channel names
                parts = line.split()
                for part in parts:
                    if part in ['stable', 'fast', 'alpha', 'beta'] or '-' in part:
                        channel_info = {
                            'name': part,
                            'default': part == 'stable'
                        }
                        if channel_info not in channels:
                            channels.append(channel_info)
        
        # If no channels found, provide defaults
        if not channels:
            channels = [
                {'name': 'stable', 'default': True},
                {'name': 'fast', 'default': False}
            ]
        
        return jsonify({
            'status': 'success',
            'operator': operator_name,
            'catalog': catalog_url,
            'channels': channels,
            'default_channel': default_channel,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({
            'status': 'error',
            'message': 'Request timeout while fetching operator channels',
            'timestamp': datetime.utcnow().isoformat()
        }), 504
    except Exception as e:
        app.logger.error(f"Error fetching operator channels: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch operator channels: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/api/generate/preview', methods=['POST'])
def generate_preview():
    """Generate YAML preview without saving"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Create generator instance
        generator = ImageSetGenerator()
        newest_channel = {}

        # Add OCP versions
        if data.get('ocp_versions') or data.get('ocp_min_version') or data.get('ocp_max_version'):
            # New approach with min/max versions
            channel = data.get('ocp_channel', 'stable-4.14')
            min_version = data.get('ocp_min_version')
            max_version = data.get('ocp_max_version')
            
            # Support legacy versions list for backward compatibility
            legacy_versions = None
            if data.get('ocp_versions'):
                legacy_versions = [v.strip() for v in data['ocp_versions'] if v.strip()]

            generator.add_ocp_versions(
                versions=legacy_versions,
                channel=channel,
                min_version=min_version,
                max_version=max_version
            )
        
        # Add operators
        if data.get('operators'):
            # Group operators by catalog and version
            catalog_to_operators = {}
            channels = {}
            
            for op in data['operators']:
                # Process operator data using helper function
                op_data = process_operator_data(op)
                if not op_data:
                    continue
                    
                # Prepare operator entry
                op_entry = prepare_operator_entry(op_data)
                if not op_entry:
                    continue
                    
                # Store channel mapping if present
                available_versions = set([])
                possible_versions = []
                name = op_data.get('name')
                version_key = data.get('ocp_versions', [None])[0]
                catalog_name = op_data.get('catalog', "")
                catalog_index = (catalog_name.split('/')[-1]).split(':')[0]
                static_file_path = os.path.join("data", f"operators-{catalog_index}-{version_key}.json")
                temp_channel_version_map = {}
                
                #Open static_file_path and get all available versions of operator between the selected min and max values
                with open(static_file_path, 'r') as f:
                    operator_catalog_data = json.load(f)
                    for operator in operator_catalog_data.get('operators', []):
                        if operator.get('name') == name:
                            possible_versions.append(operator.get('version', []))
                            temp_channel_version_map[operator.get('version')] = operator.get('channel')

                min_version = op_data.get('minVersion')
                max_version = op_data.get('maxVersion')

                channel_list = set([])
                        
                for version in possible_versions:
                    try:
                        if Version_Checker(version) >= Version_Checker(min_version) and Version_Checker(version) <= Version_Checker(max_version):
                            available_versions.add(version)
                            channel_list.add(temp_channel_version_map.get(version))
                            if version == max_version:
                                newest_channel[name] = temp_channel_version_map.get(version)
                            continue
                    except Exception as e:
                        app.logger.warning(f"Version comparison error for {name} version {version} will try other method: {e}") 
                        
                    try:
                        temp_version=version.split("-")[0]
                        temp_max_version=max_version.split("-")[0]
                        temp_min_version=min_version.split("-")[0]
                        if Version_Checker(temp_version) >= Version_Checker(temp_min_version) and Version_Checker(temp_version) <= Version_Checker(temp_max_version):
                            available_versions.add(version)
                            channel_list.add(temp_channel_version_map.get(version))
                            if temp_version == temp_max_version:
                                newest_channel[name] = temp_channel_version_map.get(version)
                            continue
                    except Exception as e:
                        app.logger.warning(f"Version comparison error for {name} version {version} will try other method: {e}") 

                    try:
                        temp_version=version.split("+")[0]
                        temp_max_version=max_version.split("+")[0]
                        temp_min_version=min_version.split("+")[0]
                        if Version_Checker(temp_version) >= Version_Checker(temp_min_version) and Version_Checker(temp_version) <= Version_Checker(temp_max_version):
                            available_versions.add(version)
                            channel_list.add(temp_channel_version_map.get(version))
                            if temp_version == temp_max_version:
                                newest_channel[name] = temp_channel_version_map.get(version)
                            continue
                    except Exception as e:
                        app.logger.warning(f"Version comparison error for {name} version {version} will try other method: {e}") 
                channels[op_data["name"]] = channel_list

                # Group by catalog
                catalog = op_data["catalog"] or 'registry.redhat.io/redhat/redhat-operator-index'
                catalog_to_operators.setdefault(catalog, []).append(op_entry)
            # Add operators for each catalog, passing full operator dicts
            ocp_version = data.get('ocp_versions', [None])[0] or data.get('ocp_min_version') or data.get('ocp_max_version')
            for catalog, ops in catalog_to_operators.items():
                generator.add_operators(ops, catalog, channels, ocp_version=ocp_version, newest_channel=newest_channel)

        # Add additional images
        if data.get('additional_images'):
            images = []
            for img in data['additional_images']:
                if isinstance(img, str):
                    img_val = img.strip()
                elif isinstance(img, dict):
                    img_val = img.get('name', '').strip() if 'name' in img and isinstance(img['name'], str) else ''
                else:
                    img_val = ''
                if img_val:
                    images.append(img_val)
            generator.add_additional_images(images)
        
        # Add helm charts
        if data.get('helm_charts'):
            generator.add_helm_charts(data['helm_charts'])
        
        # Set KubeVirt container mirroring
        if data.get('kubevirt_container', False):
            generator.set_kubevirt_container(True)
        
        # Set archive size if provided
        if data.get('archive_size'):
            try:
                generator.set_archive_size(int(data['archive_size']))
            except Exception:
                pass
        # Add storageConfig if present
        if data.get('storageConfig'):
            storage_config = {'registry': {}}
            if data['storageConfig'].get('registry'):
                storage_config['registry']['imageURL'] = data['storageConfig']['registry']
            if data['storageConfig'].get('skipTLS') is not None:
                storage_config['registry']['skipTLS'] = data['storageConfig']['skipTLS']
            generator.config['storageConfig'] = storage_config
        # Generate YAML
        yaml_content = generator.generate_yaml()
        return jsonify({
            'success': True,
            'yaml': yaml_content,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error generating preview: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'error': f'Failed to generate preview: {str(e)}',
            'success': False
        }), 500


@app.route('/api/generate/download', methods=['POST'])
def generate_download():
    """Generate and return downloadable YAML file"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Create generator instance
        generator = ImageSetGenerator()
        
        # Add OCP versions
        if data.get('ocp_versions') or data.get('ocp_min_version') or data.get('ocp_max_version'):
            # New approach with min/max versions
            channel = data.get('ocp_channel', 'stable-4.14')
            min_version = data.get('ocp_min_version')
            max_version = data.get('ocp_max_version')
            
            # Support legacy versions list for backward compatibility
            legacy_versions = None
            if data.get('ocp_versions'):
                legacy_versions = [v.strip() for v in data['ocp_versions'] if v.strip()]
            
            generator.add_ocp_versions(
                versions=legacy_versions,
                channel=channel,
                min_version=min_version,
                max_version=max_version
            )
        
        # Add operators
        if data.get('operators'):
            # Group operators by catalog and version, preserving version and channel
            catalog_to_operators = {}
            channels = {}
            for op in data['operators']:
                if isinstance(op, str):
                    op_name = op.strip()
                    op_channel = None
                    op_catalog = None
                    op_version = None
                    op_min_version = None
                    op_max_version = None
                elif isinstance(op, dict):
                    op_name = op.get('name', '').strip() if 'name' in op and isinstance(op['name'], str) else ''
                    op_channel = op.get('channel', '').strip() if 'channel' in op and isinstance(op['channel'], str) else None
                    op_catalog = op.get('catalog', '').strip() if 'catalog' in op and isinstance(op['catalog'], str) else None
                    op_version = op.get('version', '').strip() if 'version' in op and isinstance(op['version'], str) else None
                    op_min_version = op.get('minVersion', '').strip() if 'minVersion' in op and isinstance(op['minVersion'], str) else None
                    op_max_version = op.get('maxVersion', '').strip() if 'maxVersion' in op and isinstance(op['maxVersion'], str) else None
                else:
                    op_name = ''
                    op_channel = None
                    op_catalog = None
                    op_version = None
                    op_min_version = None
                    op_max_version = None
                if op_name:
                    op_entry = {"name": op_name}
                    if op_channel:
                        op_entry["channel"] = op_channel
                        channels[op_name] = op_channel
                    if op_version:
                        op_entry["version"] = op_version
                    if op_min_version:
                        op_entry["minVersion"] = op_min_version
                    if op_max_version:
                        op_entry["maxVersion"] = op_max_version
                    if op_catalog:
                        catalog_to_operators.setdefault(op_catalog, []).append(op_entry)
                    else:
                        catalog_to_operators.setdefault('registry.redhat.io/redhat/redhat-operator-index', []).append(op_entry)
            ocp_version = data.get('ocp_versions', [None])[0] or data.get('ocp_min_version') or data.get('ocp_max_version')
            for catalog, ops in catalog_to_operators.items():
                generator.add_operators(ops, catalog, channels, ocp_version=ocp_version)
        
        # Add additional images
        if data.get('additional_images'):
            images = []
            for img in data['additional_images']:
                if isinstance(img, str):
                    img_val = img.strip()
                elif isinstance(img, dict):
                    img_val = img.get('name', '').strip() if 'name' in img and isinstance(img['name'], str) else ''
                else:
                    img_val = ''
                if img_val:
                    images.append(img_val)
            generator.add_additional_images(images)
        
        # Add helm charts
        if data.get('helm_charts'):
            generator.add_helm_charts(data['helm_charts'])
        
        # Set KubeVirt container mirroring
        if data.get('kubevirt_container', False):
            generator.set_kubevirt_container(True)
        
        # Set archive size if provided
        if data.get('archive_size'):
            try:
                generator.set_archive_size(int(data['archive_size']))
            except Exception:
                pass
        # Add storageConfig if present
        if data.get('storageConfig'):
            storage_config = {'registry': {}}
            if data['storageConfig'].get('registry'):
                storage_config['registry']['imageURL'] = data['storageConfig']['registry']
            if data['storageConfig'].get('skipTLS') is not None:
                storage_config['registry']['skipTLS'] = data['storageConfig']['skipTLS']
            generator.config['storageConfig'] = storage_config
        # Generate YAML
        yaml_content = generator.generate_yaml()
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(yaml_content)
            temp_filename = temp_file.name
        # Return file content for download
        response = app.response_class(
            yaml_content,
            mimetype='application/x-yaml',
            headers={
                'Content-Disposition': f'attachment; filename=imageset-config.yaml'
            }
        )
        # Clean up temp file
        try:
            os.unlink(temp_filename)
        except:
            pass
        return response
        
    except Exception as e:
        app.logger.error(f"Error generating download: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'error': f'Failed to generate download: {str(e)}',
            'success': False
        }), 500


@app.route('/api/validate', methods=['POST'])
def validate_config():
    """Validate configuration data"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        errors = []
        warnings = []
        
        # Check if at least one configuration is provided
        has_ocp = bool(data.get('ocp_versions'))
        has_operators = bool(data.get('operators'))
        has_images = bool(data.get('additional_images'))
        has_helm = bool(data.get('helm_charts'))
        
        if not (has_ocp or has_operators or has_images or has_helm):
            errors.append('At least one configuration section must be specified (OCP versions, operators, additional images, or Helm charts)')
        
        # Validate OCP versions format
        if has_ocp:
            for version in data.get('ocp_versions', []):
                if not version.strip():
                    continue
                version_parts = version.strip().split('.')
                if len(version_parts) < 3 or not all(part.isdigit() for part in version_parts[:3]):
                    warnings.append(f'OCP version "{version}" may not be in the expected format (e.g., 4.14.1)')
        
        # Validate operator catalog URL
        if data.get('operator_catalog'):
            catalog = data.get('operator_catalog')
            if not catalog.startswith(('http://', 'https://', 'registry.')):
                warnings.append('Operator catalog should be a valid registry URL')
        
        # Validate additional images
        if has_images:
            for image in data.get('additional_images', []):
                if not image.strip():
                    continue
                if ':' not in image:
                    warnings.append(f'Image "{image}" may be missing a tag (e.g., :latest)')
        
        # Validate Helm charts
        if has_helm:
            for chart in data.get('helm_charts', []):
                if not chart.get('name'):
                    errors.append('Helm chart name is required')
                if not chart.get('repository'):
                    errors.append('Helm chart repository is required')
        
        return jsonify({
            'success': True,
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        })
        
    except Exception as e:
        app.logger.error(f"Error validating config: {str(e)}")
        return jsonify({
            'error': f'Failed to validate configuration: {str(e)}',
            'success': False
        }), 500


@app.route("/api/refresh/all", methods=["GET"])
def refresh_all_static_data():
    """
    Refresh all static data files by calling oc-mirror for:
    - OCP releases
    - Operator catalogs for all known OCP versions
    """

    try:

        refresh_versions()
        refresh_ocp_channels()
        refresh_ocp_releases()
        refresh_ocp_operators()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error refreshing static data: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

    return jsonify({
        "status": "success",
        "message": "All static data refreshed",
        "timestamp": datetime.now().isoformat()
    })


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors by serving React app"""
    return send_from_directory(app.static_folder, 'index.html')


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'success': False
    }), 500


@app.route("/api/ocp-versions", methods=["GET"])
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


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='OpenShift ImageSetConfiguration Generator Web API')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting OpenShift ImageSetConfiguration Generator Web API...")
    print(f"Access the application at: http://{args.host}:{args.port}")
    
    app.run(host=args.host, port=args.port, debug=args.debug)

