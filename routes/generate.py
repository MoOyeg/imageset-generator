"""
Generate Blueprint — YAML preview, download, and validation endpoints.
"""

import json
import os
import tempfile
import traceback
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from packaging.version import Version as Version_Checker

from generator import ImageSetGenerator
from routes.shared import process_operator_data, prepare_operator_entry

generate_bp = Blueprint('generate', __name__)


def _build_generator_and_yaml(data, oc_mirror_version=1):
    """Shared logic for both preview and download endpoints.
    Returns (generator, yaml_content) tuple.
    """
    # Ensure oc_mirror_version is always a valid int (1 or 2)
    if oc_mirror_version is None:
        oc_mirror_version = 1
    oc_mirror_version = int(oc_mirror_version)
    generator = ImageSetGenerator(oc_mirror_version=oc_mirror_version)
    newest_channel = {}

    # Add OCP versions
    if data.get('ocp_versions') or data.get('ocp_min_version') or data.get('ocp_max_version'):
        channel = data.get('ocp_channel', 'stable-4.14')
        min_version = data.get('ocp_min_version')
        max_version = data.get('ocp_max_version')

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
        catalog_to_operators = {}
        channels = {}

        for op in data['operators']:
            op_data = process_operator_data(op)
            if not op_data:
                continue

            op_entry = prepare_operator_entry(op_data)
            if not op_entry:
                continue

            available_versions = set([])
            possible_versions = []
            name = op_data.get('name')
            version_key = data.get('ocp_versions', [None])[0]
            catalog_name = op_data.get('catalog', "")
            catalog_index = (catalog_name.split('/')[-1]).split(':')[0]
            static_file_path = os.path.join("data", f"operators-{catalog_index}-{version_key}.json")
            temp_channel_version_map = {}

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
                    current_app.logger.warning(f"Version comparison error for {name} version {version} will try other method: {e}")

                try:
                    temp_version = version.split("-")[0]
                    temp_max_version = max_version.split("-")[0]
                    temp_min_version = min_version.split("-")[0]
                    if Version_Checker(temp_version) >= Version_Checker(temp_min_version) and Version_Checker(temp_version) <= Version_Checker(temp_max_version):
                        available_versions.add(version)
                        channel_list.add(temp_channel_version_map.get(version))
                        if temp_version == temp_max_version:
                            newest_channel[name] = temp_channel_version_map.get(version)
                        continue
                except Exception as e:
                    current_app.logger.warning(f"Version comparison error for {name} version {version} will try other method: {e}")

                try:
                    temp_version = version.split("+")[0]
                    temp_max_version = max_version.split("+")[0]
                    temp_min_version = min_version.split("+")[0]
                    if Version_Checker(temp_version) >= Version_Checker(temp_min_version) and Version_Checker(temp_version) <= Version_Checker(temp_max_version):
                        available_versions.add(version)
                        channel_list.add(temp_channel_version_map.get(version))
                        if temp_version == temp_max_version:
                            newest_channel[name] = temp_channel_version_map.get(version)
                        continue
                except Exception as e:
                    current_app.logger.warning(f"Version comparison error for {name} version {version} will try other method: {e}")
            channels[op_data["name"]] = channel_list

            catalog = op_data["catalog"] or 'registry.redhat.io/redhat/redhat-operator-index'
            catalog_to_operators.setdefault(catalog, []).append(op_entry)
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

    # Add storageConfig if present (v1 only — v2 uses --workspace CLI flag instead)
    if data.get('storageConfig') and int(oc_mirror_version) != 2:
        storage_config = {'registry': {}}
        if data['storageConfig'].get('registry'):
            storage_config['registry']['imageURL'] = data['storageConfig']['registry']
        if data['storageConfig'].get('skipTLS') is not None:
            storage_config['registry']['skipTLS'] = data['storageConfig']['skipTLS']
        generator.config['storageConfig'] = storage_config

    yaml_content = generator.generate_yaml()
    return generator, yaml_content


@generate_bp.route('/generate/preview', methods=['POST'])
def generate_preview():
    """Generate YAML preview without saving"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        oc_mirror_version = data.get('oc_mirror_version', 1)
        generator, yaml_content = _build_generator_and_yaml(data, oc_mirror_version)

        return jsonify({
            'success': True,
            'yaml': yaml_content,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error generating preview: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'error': f'Failed to generate preview: {str(e)}',
            'success': False
        }), 500


@generate_bp.route('/generate/download', methods=['POST'])
def generate_download():
    """Generate and return downloadable YAML file"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Use the same generation logic as preview
        oc_mirror_version = data.get('oc_mirror_version', 1)
        generator, yaml_content = _build_generator_and_yaml(data, oc_mirror_version)
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write(yaml_content)
            temp_filename = temp_file.name
        # Return file content for download
        response = current_app.response_class(
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
        current_app.logger.error(f"Error generating download: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'error': f'Failed to generate download: {str(e)}',
            'success': False
        }), 500


@generate_bp.route('/validate', methods=['POST'])
def validate_config():
    """Validate configuration data"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        errors = []
        warnings = []

        has_ocp = bool(data.get('ocp_versions'))
        has_operators = bool(data.get('operators'))
        has_images = bool(data.get('additional_images'))
        has_helm = bool(data.get('helm_charts'))

        if not (has_ocp or has_operators or has_images or has_helm):
            errors.append('At least one configuration section must be specified (OCP versions, operators, additional images, or Helm charts)')

        if has_ocp:
            for version in data.get('ocp_versions', []):
                if not version.strip():
                    continue
                version_parts = version.strip().split('.')
                if len(version_parts) < 3 or not all(part.isdigit() for part in version_parts[:3]):
                    warnings.append(f'OCP version "{version}" may not be in the expected format (e.g., 4.14.1)')

        if data.get('operator_catalog'):
            catalog = data.get('operator_catalog')
            if not catalog.startswith(('http://', 'https://', 'registry.')):
                warnings.append('Operator catalog should be a valid registry URL')

        if has_images:
            for image in data.get('additional_images', []):
                if not image.strip():
                    continue
                if ':' not in image:
                    warnings.append(f'Image "{image}" may be missing a tag (e.g., :latest)')

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
        current_app.logger.error(f"Error validating config: {str(e)}")
        return jsonify({
            'error': f'Failed to validate configuration: {str(e)}',
            'success': False
        }), 500
