#!/usr/bin/env python3
"""
OpenShift ImageSetConfiguration Generator - Flask API Backend

This Flask application provides a REST API for the OpenShift ImageSetConfiguration generator.
It serves as the backend for the React frontend application.
"""

import os
from datetime import datetime
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from routes.ocp import ocp_bp
from routes.operators import operators_bp
from routes.generate import generate_bp
from routes.auth import auth_bp
from routes.maintenance import maintenance_bp

app = Flask(__name__, static_folder='frontend/build')
CORS(app)

# Register blueprints
app.register_blueprint(ocp_bp, url_prefix='/api')
app.register_blueprint(operators_bp, url_prefix='/api/operators')
app.register_blueprint(generate_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(maintenance_bp, url_prefix='/api')


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    """Serve React app"""
    if path.startswith('static/') or path.startswith('api/'):
        return app.send_static_file(path) if path.startswith('static/') else None

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
