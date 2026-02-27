"""
Auth Blueprint — Pull secret upload and status endpoints.
"""

import json
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app

from routes.shared import PULL_SECRET_PATH

auth_bp = Blueprint('auth', __name__)


@auth_bp.route("/pull-secret", methods=["POST"])
def upload_pull_secret():
    """Upload a pull secret (dockerconfigjson) for registry authentication."""
    try:
        data = request.get_json()
        if not data or not data.get('pullSecret'):
            return jsonify({'status': 'error', 'message': 'No pull secret provided'}), 400

        pull_secret_content = data['pullSecret'].strip()

        # Validate it's valid JSON
        try:
            parsed = json.loads(pull_secret_content)
        except json.JSONDecodeError as e:
            return jsonify({'status': 'error', 'message': f'Invalid JSON: {str(e)}'}), 400

        # Basic validation: should have "auths" key
        if 'auths' not in parsed:
            return jsonify({
                'status': 'error',
                'message': 'Invalid pull secret format. Expected a JSON object with an "auths" key.'
            }), 400

        # Write to ~/.docker/config.json
        docker_dir = os.path.dirname(PULL_SECRET_PATH)
        os.makedirs(docker_dir, exist_ok=True)
        with open(PULL_SECRET_PATH, 'w') as f:
            json.dump(parsed, f, indent=2)

        registry_count = len(parsed.get('auths', {}))
        registries = list(parsed.get('auths', {}).keys())

        current_app.logger.info(f"Pull secret saved with {registry_count} registries: {registries}")

        return jsonify({
            'status': 'success',
            'message': f'Pull secret saved with {registry_count} registry credentials.',
            'registries': registries,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error saving pull secret: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Failed to save pull secret: {str(e)}'}), 500


@auth_bp.route("/pull-secret/status", methods=["GET"])
def pull_secret_status():
    """Check if a pull secret is configured."""
    try:
        if os.path.exists(PULL_SECRET_PATH):
            with open(PULL_SECRET_PATH, 'r') as f:
                parsed = json.load(f)
            registries = list(parsed.get('auths', {}).keys())
            return jsonify({
                'status': 'success',
                'configured': True,
                'registries': registries,
                'registry_count': len(registries),
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'success',
                'configured': False,
                'registries': [],
                'registry_count': 0,
                'timestamp': datetime.now().isoformat()
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error checking pull secret: {str(e)}'
        }), 500
