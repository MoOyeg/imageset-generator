"""
Operators Blueprint — Catalog, operator list, mappings, and channel endpoints.
"""

import json
import os
import re
import subprocess
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app

from routes.shared import (
    return_base_catalog_info,
    load_operators_from_file,
    load_catalogs_from_file,
    load_dependencies_from_file,
    resolve_operator_dependencies,
    _extract_and_save_dependencies,
)

operators_bp = Blueprint('operators', __name__)


# ============================================================
# Core logic functions (called by route handlers AND maintenance)
# ============================================================

def do_refresh_ocp_operators(catalog, version):
    """Core logic: refresh operators for a catalog/version. Returns operator list. Raises on failure."""
    current_app.logger.debug("Refreshing OCP operators...")

    operator_output = []

    # Get file static path
    catalog_index = (catalog.split('/')[-1]).split(':')[0]
    static_file_path = os.path.join("data", f"operators-{catalog_index}-{version}.json")
    static_file_path_index = os.path.join("data", f"operators-{catalog_index}-{version}-index.json")
    static_file_path_data = os.path.join("data", f"operators-{catalog_index}-{version}-data.json")
    static_file_path_channel = os.path.join("data", f"operators-{catalog_index}-{version}-channel.json")

    # Get index file
    if not os.path.exists(static_file_path_index) or os.path.getsize(static_file_path_index) == 0:
        with open(static_file_path_index, 'w') as f:
            subprocess.run(['opm', 'render', catalog, '--skip-tls-verify', '--output', 'json'], stdout=f, check=True)

    # jq to extract operator data
    if os.path.exists(static_file_path_index):
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

        if not os.path.exists(static_file_path_data) or os.path.getsize(static_file_path_data) == 0:
            with open(static_file_path_index, "r") as infile, open(static_file_path_data, "w") as outfile:
                subprocess.run(["jq", "-r", jq_filter], stdin=infile, stdout=outfile, check=True)

        # jq to extract channel data
        jq_filter_channel = '''
        select(.schema == "olm.channel")
        | [.package, .name, .entries[]?.name, .channelName] | @tsv
        '''

        if not os.path.exists(static_file_path_channel) or os.path.getsize(static_file_path_channel) == 0:
            with open(static_file_path_index, "r") as infile, open(static_file_path_channel, "w") as outfile:
                subprocess.run(["jq", "-r", jq_filter_channel], stdin=infile, stdout=outfile, check=True)

        # Parse TSV output
        with open(static_file_path_data, "r") as f:
            data = f.read()
            lines = data.strip().split('\n')
            lines = [line for line in lines if line.strip()]
            for line in lines:
                fields = line.split('\t')
                if len(fields) < 5:
                    operator_output.append({
                        "package": fields[0],
                        "name": fields[0],
                        "version": fields[2] if len(fields) > 2 else ""
                    })
                if len(fields) >= 5:
                    operator_output.append({
                        "package": fields[0],
                        "name": fields[0],
                        "version": fields[2],
                        "keywords": fields[3].split(",") if fields[3] else [],
                        "description": fields[4],
                        "channel": fields[5] if len(fields) > 5 else ""
                    })

                # Search channel file
                if fields[1] is not None:
                    with open(static_file_path_channel, "r") as f:
                        channel_data = f.read()
                        ch_lines = channel_data.strip().split('\n')
                        ch_lines = [l for l in ch_lines if l.strip()]
                        for ch_line in ch_lines:
                            if fields[1] in ch_line:
                                channel_fields = ch_line.split('\t')
                                if channel_fields[1] is not None:
                                    operator_output[-1]["channel"] = channel_fields[1]
                                    break

        # Write output to file
        with open(static_file_path, "w") as f:
            json.dump({
                "operators": operator_output,
                "count": len(operator_output),
                "source": "opm",
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)

        # Extract dependency data from raw opm render output
        deps_file_path = os.path.join("data", f"deps-{catalog_index}-{version}.json")
        _extract_and_save_dependencies(static_file_path_index, deps_file_path)

        # Remove intermediate files
        try:
            os.remove(static_file_path_index)
            os.remove(static_file_path_channel)
            os.remove(static_file_path_data)
        except Exception as e:
            current_app.logger.error(f"Error removing intermediate files: {e}")

    return operator_output


def do_refresh_catalogs_for_version(version):
    """Core logic: refresh catalogs for a version. Returns dict of {version: [catalogs]}. Raises on failure."""
    version_list = []
    discovered_catalogs = {}

    if version is not None:
        version_list.append(version)
    else:
        static_file_path = os.path.join("data", "ocp-versions.json")
        if os.path.exists(static_file_path):
            with open(static_file_path, 'r') as f:
                data = json.load(f)
                releases = data.get("releases", [])
                current_app.logger.debug(f"Loaded {len(releases)} releases from static file")
                for release in releases:
                    if re.match(r'^\d+\.\d+$', release):
                        version_list.append(release)

    for ver in version_list:
        if '.' in ver:
            version_parts = ver.split('.')
            version_key = f"{version_parts[0]}.{version_parts[1]}"
        else:
            version_key = ver

        current_app.logger.info(f"Discovering catalogs for OCP version {version_key}...")

        cmd = ['oc-mirror', 'list', 'operators', '--catalogs', f'--version={version_key}']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise Exception(f"oc-mirror command failed: {result.stderr.strip()}")

        lines = result.stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('WARN') and not line.startswith('INFO'):
                if re.match(r'^Available OpenShift OperatorHub catalogs', line):
                    continue
                if re.match(r'OpenShift \d\.\d+', line):
                    continue
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

    # Write catalog info to file
    try:
        with open(f"data/catalogs-{version}.json", 'w') as f:
            json.dump(discovered_catalogs, f, indent=2)
    except Exception as e:
        current_app.logger.warning(f"Could not save catalog file: {e}")

    return discovered_catalogs


# ============================================================
# Route handlers
# ============================================================

@operators_bp.route('/refresh', methods=['POST'])
def refresh_ocp_operators(catalog=None, version=None):
    """Refresh the list of available OCP operators"""
    if catalog is None:
        return jsonify({
            'status': 'error',
            'message': 'Catalog parameter is required',
            'timestamp': datetime.now().isoformat()
        }), 400

    if version is None or not version.strip():
        version = catalog.split(':')[-1]

    try:
        operator_output = do_refresh_ocp_operators(catalog, version)
        return jsonify({
            'status': 'success',
            'data': operator_output,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"Error refreshing operators: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to refresh operators: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500


@operators_bp.route('/catalogs/<version>/refresh', methods=['POST'])
def refresh_catalogs_for_version(version=None):
    """Refresh available operator catalogs dynamically using oc-mirror"""
    try:
        discovered_catalogs = do_refresh_catalogs_for_version(version)
        return jsonify({
            'status': 'success',
            'version': version,
            'catalogs': discovered_catalogs,
            'source': 'oc-mirror',
            'timestamp': datetime.utcnow().isoformat()
        })
    except subprocess.TimeoutExpired:
        current_app.logger.error(f"Timeout while discovering catalogs for version {version}")
        return jsonify({
            'status': 'error',
            'message': f'Timeout while discovering catalogs for version {version}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    except Exception as e:
        current_app.logger.error(f"Error discovering catalogs: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to discover catalogs: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@operators_bp.route('/catalogs/<version>', methods=['GET'])
def get_operator_catalogs(version):
    """Get operator catalog data for a specific OCP version from static file or oc-mirror"""
    if '.' in version:
        version_parts = version.split('.')
        version_key = f"{version_parts[0]}.{version_parts[1]}"
    else:
        version_key = version

    static_file = os.path.join('data', f'catalogs-{version_key}.json')

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
            current_app.logger.warning(f"Could not load static catalog file: {e}")

    # If static file does not exist, run oc-mirror to obtain it
    try:
        discovered_catalogs = do_refresh_catalogs_for_version(version)
    except Exception as e:
        current_app.logger.error(f"Failed to get catalogs for version {version}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get operator catalogs for version {version}: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

    available_catalogs = discovered_catalogs.get(version_key, [])
    if not available_catalogs:
        current_app.logger.warning(f"No catalogs found for version {version}")
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


@operators_bp.route('/catalogs', methods=['GET'])
def get_available_catalogs():
    """Get all available operator catalogs using oc-mirror"""
    return None
    # Stub function — dead code below preserved from original
    try:
        standard_catalogs = [
            {"name": "Red Hat Operators", "url": "registry.redhat.io/redhat/redhat-operator-index", "description": "Official Red Hat certified operators"},
            {"name": "Community Operators", "url": "registry.redhat.io/redhat/community-operator-index", "description": "Community-maintained operators"},
            {"name": "Certified Operators", "url": "registry.redhat.io/redhat/certified-operator-index", "description": "Third-party certified operators"},
            {"name": "Red Hat Marketplace", "url": "registry.redhat.io/redhat/redhat-marketplace-index", "description": "Commercial operators from Red Hat Marketplace"}
        ]
        validated_catalogs = []
        for catalog in standard_catalogs:
            try:
                cmd = ['oc-mirror', 'list', 'operators', '--catalogs', catalog['url']]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                catalog_info = catalog.copy()
                catalog_info['validated'] = result.returncode == 0
                validated_catalogs.append(catalog_info)
            except subprocess.TimeoutExpired:
                catalog_info = catalog.copy()
                catalog_info['validated'] = False
                catalog_info['error'] = 'Timeout while validating'
                validated_catalogs.append(catalog_info)
            except Exception as e:
                catalog_info = catalog.copy()
                catalog_info['validated'] = False
                catalog_info['error'] = str(e)
                validated_catalogs.append(catalog_info)
        return jsonify({
            'status': 'success',
            'catalogs': validated_catalogs,
            'count': len(validated_catalogs),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get available catalogs: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@operators_bp.route('/catalogs/<version>/list', methods=['GET'])
def list_catalogs_for_version(version):
    """Use oc-mirror to list available catalogs for a specific OCP version"""
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


@operators_bp.route('/mappings', methods=['GET'])
def get_operator_mappings():
    """Get available operator mappings"""
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


@operators_bp.route('/list', methods=['GET'])
def get_operators_list():
    """Get list of available operators from cache files"""
    try:
        catalog = request.args.get('catalog')
        version = request.args.get('version')

        if not catalog:
            return jsonify({
                'status': 'error',
                'message': 'Catalog and version parameters are required'
            }), 400

        if version is None:
            version = catalog.split(':')[-1]

        if version is not None:
            if re.match(r'^\d+\.\d+$', version):
                if ':v' not in catalog:
                    catalog = f"{catalog}:v{version}"

        if '.' in version:
            version_parts = version.split('.')
            version_key = f"{version_parts[0]}.{version_parts[1]}"
        else:
            version_key = version

        operators = load_operators_from_file(catalog, version_key)

        if operators is None or operators == []:
            current_app.logger.info(f"No cached operators found for {catalog}:{version_key}, running refresh...")
            operator_output = do_refresh_ocp_operators(catalog=catalog, version=version_key)
            operators = operator_output

        return jsonify({
            'status': 'success',
            'operators': operators,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"Error loading operators from cache: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to load operators: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@operators_bp.route('/<operator_name>/channels', methods=['GET'])
def get_operator_channels(operator_name):
    """Get available channels for a specific operator using oc-mirror"""
    try:
        catalog = request.args.get('catalog', 'registry.redhat.io/redhat/redhat-operator-index')
        version = request.args.get('version', '4.18')

        if '.' in version:
            version_parts = version.split('.')
            version_key = f"{version_parts[0]}.{version_parts[1]}"
        else:
            version_key = version

        if ':v' not in catalog:
            catalog_url = f"{catalog}:v{version_key}"
        else:
            catalog_url = catalog

        current_app.logger.info(f"Fetching channels for operator {operator_name} from {catalog_url}")

        cmd = ['oc-mirror', 'list', 'operators', '--catalogs', catalog_url, '--version', version_key, operator_name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            current_app.logger.warning(f"oc-mirror failed for operator channels: {result.stderr}")
            return jsonify({
                'status': 'success',
                'operator': operator_name,
                'catalog': catalog_url,
                'channels': [{'name': 'stable', 'default': True}],
                'default_channel': 'stable',
                'timestamp': datetime.utcnow().isoformat()
            })

        channels = []
        default_channel = 'stable'

        lines = result.stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if 'channel' in line.lower() or 'stable' in line or 'fast' in line or 'alpha' in line or 'beta' in line:
                parts = line.split()
                for part in parts:
                    if part in ['stable', 'fast', 'alpha', 'beta'] or '-' in part:
                        channel_info = {
                            'name': part,
                            'default': part == 'stable'
                        }
                        if channel_info not in channels:
                            channels.append(channel_info)

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
        current_app.logger.error(f"Error fetching operator channels: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch operator channels: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@operators_bp.route('/<operator_name>/dependencies', methods=['GET'])
def get_operator_dependencies(operator_name):
    """Get resolved dependencies for a specific operator.

    Query params:
        catalog  – primary catalog URL (e.g. registry.redhat.io/redhat/redhat-operator-index)
        version  – OCP version (e.g. 4.16)
        all_catalogs – comma-separated list of all selected catalog URLs for cross-catalog resolution
    """
    try:
        catalog = request.args.get('catalog', 'registry.redhat.io/redhat/redhat-operator-index')
        version = request.args.get('version', '4.18')
        all_catalogs_param = request.args.get('all_catalogs', '')

        if '.' in version:
            version_parts = version.split('.')
            version_key = f"{version_parts[0]}.{version_parts[1]}"
        else:
            version_key = version

        all_catalogs = [c.strip() for c in all_catalogs_param.split(',') if c.strip()] if all_catalogs_param else None

        result = resolve_operator_dependencies(operator_name, catalog, version_key, all_catalogs)

        return jsonify({
            'status': 'success',
            'operator': operator_name,
            'dependencies': result['dependencies'],
            'unresolved': result['unresolved'],
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"Error resolving dependencies for {operator_name}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to resolve dependencies: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500
