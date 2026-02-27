"""
Shared constants, helper functions, and data-access utilities used across blueprints.
"""

import json
import os
import re
import subprocess
import yaml
from datetime import datetime
from flask import current_app


# ============================================================
# Constants
# ============================================================

RESET_MIN_VERSION = "4.13"

CATALOG_BASE_URLS = [
    "registry.redhat.io/redhat/redhat-operator-index",
    "registry.redhat.io/redhat/certified-operator-index",
    "registry.redhat.io/redhat/community-operator-index",
    "registry.redhat.io/redhat/redhat-marketplace-index",
]

PULL_SECRET_PATH = os.path.expanduser("~/.docker/config.json")


# ============================================================
# SSE helper
# ============================================================

def sse_event(event_type, data):
    """Format a Server-Sent Event string."""
    return f"event: {event_type}\ndata: {data}\n\n"


# ============================================================
# Operator / catalog data helpers
# ============================================================

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
        cmd = ['opm', 'render', '--skip-tls', full_catalog]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

        if result.returncode != 0:
            raise Exception(f"opm render failed: {result.stderr}")

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
    except Exception as e:
        raise Exception(f"Error getting operators from opm: {str(e)}")


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
        catalog_index = (catalog_key.split('/')[-1]).split(':')[0]
        static_file_path = os.path.join("data", f"operators-{catalog_index}-{version_key}.json")

        if os.path.exists(static_file_path):
            with open(static_file_path, 'r') as f:
                data = json.load(f)
                return data.get('operators', None)

        return None

    except Exception as e:
        current_app.logger.error(f"Error loading operators from file: {e}")
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
        current_app.logger.error(f"Error loading catalogs from file: {e}")
        return None


# ============================================================
# Reset/refresh helper functions (used by maintenance blueprint)
# ============================================================

def _reset_refresh_versions():
    """Refresh OCP versions list. Returns list of version strings."""
    result = subprocess.run(
        ['oc-mirror', 'list', 'releases'],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise Exception(f"oc-mirror list releases failed: {result.stderr}")

    releases = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if re.match(r'^\d+\.\d+$', line):
            releases.append(line)

    releases.sort(key=lambda x: tuple(map(int, x.split('.'))))

    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "ocp-versions.json"), 'w') as f:
        json.dump({
            "releases": releases,
            "count": len(releases),
            "source": "oc-mirror",
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)

    return releases


def _reset_refresh_channels(version):
    """Refresh channels for a single version. Returns list of channel strings."""
    result = subprocess.run(
        ['oc-mirror', 'list', 'releases', '--channels', '--version', version],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise Exception(f"oc-mirror channels failed for {version}: {result.stderr}")

    channels = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if re.match(r'^[A-Za-z]*\-\d.\d+$', line):
            channels.append(line)
    return channels


def _reset_save_channels(all_channels):
    """Save accumulated channels dict to ocp-channels.json."""
    os.makedirs("data", exist_ok=True)
    with open(os.path.join("data", "ocp-channels.json"), 'w') as f:
        json.dump({
            "channels": all_channels,
            "count": len(all_channels),
            "source": "oc-mirror",
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)


def _reset_refresh_catalogs(version):
    """Refresh catalogs for a single version. Saves catalogs-{version}.json."""
    result = subprocess.run(
        ['oc-mirror', 'list', 'operators', '--catalogs', f'--version={version}'],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        raise Exception(f"oc-mirror catalogs failed for {version}: {result.stderr}")

    discovered = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('WARN') or line.startswith('INFO'):
            continue
        if re.match(r'^Available OpenShift OperatorHub catalogs', line):
            continue
        if re.match(r'OpenShift \d\.\d+', line):
            continue
        match = re.match(r'^(.*?)(:v\d+\.\d+)?$', line)
        if match:
            catalog_url = match.group(1)
            if "Invalid" in line:
                continue
            catalog_info = return_base_catalog_info(catalog_url)
            if catalog_info:
                discovered.append({
                    'name': catalog_info['name'],
                    'url': catalog_url,
                    'description': catalog_info['description'],
                    'default': catalog_info['default']
                })

    os.makedirs("data", exist_ok=True)
    with open(os.path.join("data", f"catalogs-{version}.json"), 'w') as f:
        json.dump({version: discovered}, f, indent=2)

    return discovered


def _reset_refresh_releases(version, channel):
    """Refresh releases for a version/channel pair. Merges into channel-releases.json."""
    result = subprocess.run(
        ['oc-mirror', 'list', 'releases', '--channel', channel, '--version', version],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise Exception(f"oc-mirror releases failed for {channel}/{version}: {result.stderr}")

    releases = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        if re.match(r'^Architecture', line):
            continue
        if re.match(r'^Channel:', line):
            continue
        if re.match(r'^Listing', line):
            continue
        if re.match(r'.*oc-mirror.*', line):
            continue
        releases.append(line)

    static_file_path = os.path.join("data", "channel-releases.json")
    old_data = {}
    if os.path.exists(static_file_path):
        try:
            with open(static_file_path, 'r') as f:
                old_data = json.load(f).get("channel_releases", {})
        except Exception:
            pass

    old_data[channel] = releases
    os.makedirs("data", exist_ok=True)
    with open(static_file_path, 'w') as f:
        json.dump({
            "channel_releases": old_data,
            "count": len(old_data),
            "source": "oc-mirror",
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)

    return releases


def _reset_refresh_operators(catalog_url, version):
    """Refresh operators for a catalog/version. Saves operators-{catalog_index}-{version}.json."""
    full_catalog = f"{catalog_url}:v{version}"
    catalog_index = catalog_url.split('/')[-1]

    static_file_path = os.path.join("data", f"operators-{catalog_index}-{version}.json")
    static_file_path_index = os.path.join("data", f"operators-{catalog_index}-{version}-index.json")
    static_file_path_data = os.path.join("data", f"operators-{catalog_index}-{version}-data.json")
    static_file_path_channel = os.path.join("data", f"operators-{catalog_index}-{version}-channel.json")

    os.makedirs("data", exist_ok=True)

    # Step 1: opm render
    intermediate_files = [static_file_path_index, static_file_path_data, static_file_path_channel]
    try:
        with open(static_file_path_index, 'w') as f:
            proc = subprocess.run(
                ['opm', 'render', full_catalog, '--skip-tls-verify', '--output', 'json'],
                stdout=f, stderr=subprocess.PIPE, timeout=600
            )
        if proc.returncode != 0:
            raise Exception(f"opm render failed for {full_catalog}: {proc.stderr.decode() if isinstance(proc.stderr, bytes) else proc.stderr}")
    except Exception:
        for fp in intermediate_files:
            if os.path.exists(fp):
                os.remove(fp)
        raise

    # Step 2: jq to extract operator data
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
    with open(static_file_path_index, "r") as infile, open(static_file_path_data, "w") as outfile:
        subprocess.run(["jq", "-r", jq_filter], stdin=infile, stdout=outfile, check=True, timeout=300)

    # Step 3: jq to extract channel data
    jq_filter_channel = '''
    select(.schema == "olm.channel")
    | [.package, .name, .entries[]?.name, .channelName] | @tsv
    '''
    with open(static_file_path_index, "r") as infile, open(static_file_path_channel, "w") as outfile:
        subprocess.run(["jq", "-r", jq_filter_channel], stdin=infile, stdout=outfile, check=True, timeout=300)

    # Step 4: Parse TSV files
    operator_output = []
    with open(static_file_path_data, "r") as f:
        data_lines = [line for line in f.read().strip().split('\n') if line.strip()]

    channel_data_content = ""
    if os.path.exists(static_file_path_channel):
        with open(static_file_path_channel, "r") as f:
            channel_data_content = f.read()

    for line in data_lines:
        fields = line.split('\t')
        entry = {
            "package": fields[0],
            "name": fields[0],
            "version": fields[2] if len(fields) > 2 else "",
        }
        if len(fields) >= 5:
            entry["keywords"] = fields[3].split(",") if fields[3] else []
            entry["description"] = fields[4]
            entry["channel"] = fields[5] if len(fields) > 5 else ""

        if len(fields) > 1 and fields[1] and channel_data_content:
            for ch_line in channel_data_content.strip().split('\n'):
                if ch_line.strip() and fields[1] in ch_line:
                    ch_fields = ch_line.split('\t')
                    if len(ch_fields) > 1 and ch_fields[1]:
                        entry["channel"] = ch_fields[1]
                        break

        operator_output.append(entry)

    # Step 5: Write final output
    with open(static_file_path, "w") as f:
        json.dump({
            "operators": operator_output,
            "count": len(operator_output),
            "source": "opm",
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)

    # Step 6: Clean up intermediate files
    for fp in [static_file_path_index, static_file_path_data, static_file_path_channel]:
        try:
            if os.path.exists(fp):
                os.remove(fp)
        except Exception:
            pass

    return len(operator_output)
