"""
Flask API Endpoints for Automation

Provides REST API endpoints for managing and monitoring automation.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any
from flask import Blueprint, jsonify, request

from automation.scheduler import AutomationScheduler
from automation.engine import AutomationEngine, load_config

logger = logging.getLogger(__name__)

# Create Blueprint
automation_bp = Blueprint('automation', __name__, url_prefix='/api/automation')

# Global scheduler instance (initialized by app)
_scheduler = None
_config = None


def init_automation(config_path: str = 'automation/config.yaml'):
    """
    Initialize automation components

    Args:
        config_path: Path to automation configuration file

    Returns:
        AutomationScheduler instance or None if disabled/error
    """
    global _scheduler, _config

    try:
        if not os.path.exists(config_path):
            logger.warning(f"Automation config not found: {config_path}")
            return None

        _config = load_config(config_path)

        if not _config.get('scheduler', {}).get('enabled', False):
            logger.info("Automation scheduler is disabled")
            return None

        _scheduler = AutomationScheduler(_config)
        _scheduler.start()

        logger.info("Automation initialized and started")
        return _scheduler

    except Exception as e:
        logger.exception(f"Failed to initialize automation: {e}")
        return None


@automation_bp.route('/status', methods=['GET'])
def get_status():
    """Get automation status"""
    try:
        if _scheduler is None:
            return jsonify({
                "enabled": False,
                "message": "Automation is not initialized"
            }), 200

        schedule_info = _scheduler.get_schedule_info()

        # Get state and history
        engine = _scheduler.engine
        state = engine.state
        history = engine.history[-10:] if engine.history else []  # Last 10 executions

        return jsonify({
            "enabled": True,
            "schedule": schedule_info,
            "state": state,
            "recent_executions": history
        }), 200

    except Exception as e:
        logger.exception(f"Error getting automation status: {e}")
        return jsonify({"error": str(e)}), 500


@automation_bp.route('/trigger', methods=['POST'])
def trigger_automation():
    """Manually trigger automation execution"""
    try:
        if _scheduler is None:
            return jsonify({"error": "Automation is not initialized"}), 400

        logger.info("Manual automation trigger requested")

        # Run automation
        result = _scheduler.run_now()

        status_code = 200 if result.get('success') else 500

        return jsonify({
            "message": "Automation execution completed",
            "result": result
        }), status_code

    except Exception as e:
        logger.exception(f"Error triggering automation: {e}")
        return jsonify({"error": str(e)}), 500


@automation_bp.route('/config', methods=['GET'])
def get_config():
    """Get automation configuration (sanitized)"""
    try:
        if _config is None:
            return jsonify({"error": "Automation is not initialized"}), 400

        # Create sanitized config (remove sensitive data)
        sanitized = sanitize_config(_config)

        return jsonify(sanitized), 200

    except Exception as e:
        logger.exception(f"Error getting automation config: {e}")
        return jsonify({"error": str(e)}), 500


@automation_bp.route('/config', methods=['PUT'])
def update_config():
    """Update automation configuration"""
    try:
        if _config is None:
            return jsonify({"error": "Automation is not initialized"}), 400

        new_config = request.get_json()

        if not new_config:
            return jsonify({"error": "No configuration provided"}), 400

        # Validate and update config
        # In production, this should save to file and restart scheduler
        return jsonify({
            "message": "Configuration update not implemented in this version",
            "note": "Please update automation/config.yaml manually and restart"
        }), 501

    except Exception as e:
        logger.exception(f"Error updating automation config: {e}")
        return jsonify({"error": str(e)}), 500


@automation_bp.route('/history', methods=['GET'])
def get_history():
    """Get execution history"""
    try:
        if _scheduler is None:
            return jsonify({"error": "Automation is not initialized"}), 400

        # Get query parameters
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)

        history = _scheduler.engine.history

        # Apply pagination
        paginated = history[offset:offset + limit]

        return jsonify({
            "total": len(history),
            "limit": limit,
            "offset": offset,
            "executions": paginated
        }), 200

    except Exception as e:
        logger.exception(f"Error getting automation history: {e}")
        return jsonify({"error": str(e)}), 500


@automation_bp.route('/history/<execution_id>', methods=['GET'])
def get_execution(execution_id: str):
    """Get specific execution details"""
    try:
        if _scheduler is None:
            return jsonify({"error": "Automation is not initialized"}), 400

        history = _scheduler.engine.history

        # Find execution
        execution = next(
            (e for e in history if e.get('execution_id') == execution_id),
            None
        )

        if not execution:
            return jsonify({"error": "Execution not found"}), 404

        return jsonify(execution), 200

    except Exception as e:
        logger.exception(f"Error getting execution: {e}")
        return jsonify({"error": str(e)}), 500


@automation_bp.route('/jobs', methods=['GET'])
def get_jobs():
    """Get Kubernetes jobs status"""
    try:
        if _scheduler is None:
            return jsonify({"error": "Automation is not initialized"}), 400

        k8s_manager = _scheduler.engine.k8s_manager
        if not k8s_manager:
            return jsonify({"error": "Kubernetes manager not available"}), 400

        # List jobs
        jobs = k8s_manager.batch_v1.list_namespaced_job(
            namespace=k8s_manager.namespace,
            label_selector="app=imageset-mirror"
        )

        job_list = []
        for job in jobs.items:
            job_info = {
                "name": job.metadata.name,
                "namespace": job.metadata.namespace,
                "creation_timestamp": job.metadata.creation_timestamp.isoformat(),
                "active": job.status.active or 0,
                "succeeded": job.status.succeeded or 0,
                "failed": job.status.failed or 0,
                "completion_time": job.status.completion_time.isoformat() if job.status.completion_time else None
            }
            job_list.append(job_info)

        return jsonify({"jobs": job_list}), 200

    except Exception as e:
        logger.exception(f"Error getting jobs: {e}")
        return jsonify({"error": str(e)}), 500


@automation_bp.route('/jobs/<job_name>', methods=['GET'])
def get_job(job_name: str):
    """Get specific job status"""
    try:
        if _scheduler is None:
            return jsonify({"error": "Automation is not initialized"}), 400

        k8s_manager = _scheduler.engine.k8s_manager
        if not k8s_manager:
            return jsonify({"error": "Kubernetes manager not available"}), 400

        # Get job
        job = k8s_manager.batch_v1.read_namespaced_job_status(
            name=job_name,
            namespace=k8s_manager.namespace
        )

        job_info = {
            "name": job.metadata.name,
            "namespace": job.metadata.namespace,
            "creation_timestamp": job.metadata.creation_timestamp.isoformat(),
            "active": job.status.active or 0,
            "succeeded": job.status.succeeded or 0,
            "failed": job.status.failed or 0,
            "start_time": job.status.start_time.isoformat() if job.status.start_time else None,
            "completion_time": job.status.completion_time.isoformat() if job.status.completion_time else None,
            "conditions": []
        }

        if job.status.conditions:
            for condition in job.status.conditions:
                job_info["conditions"].append({
                    "type": condition.type,
                    "status": condition.status,
                    "reason": condition.reason,
                    "message": condition.message
                })

        return jsonify(job_info), 200

    except Exception as e:
        if hasattr(e, 'status') and e.status == 404:
            return jsonify({"error": "Job not found"}), 404
        logger.exception(f"Error getting job: {e}")
        return jsonify({"error": str(e)}), 500


@automation_bp.route('/jobs/<job_name>/logs', methods=['GET'])
def get_job_logs(job_name: str):
    """Get job logs"""
    try:
        if _scheduler is None:
            return jsonify({"error": "Automation is not initialized"}), 400

        k8s_manager = _scheduler.engine.k8s_manager
        if not k8s_manager:
            return jsonify({"error": "Kubernetes manager not available"}), 400

        tail_lines = request.args.get('tail', default=100, type=int)

        logs = k8s_manager.get_job_logs(job_name, tail_lines=tail_lines)

        return jsonify({
            "job_name": job_name,
            "tail_lines": tail_lines,
            "logs": logs
        }), 200

    except Exception as e:
        logger.exception(f"Error getting job logs: {e}")
        return jsonify({"error": str(e)}), 500


def sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove sensitive information from configuration

    Args:
        config: Original configuration

    Returns:
        Sanitized configuration
    """
    import copy

    sanitized = copy.deepcopy(config)

    # Remove sensitive notification settings
    if 'notifications' in sanitized:
        if 'email' in sanitized['notifications']:
            email = sanitized['notifications']['email']
            if 'smtp_password' in email:
                email['smtp_password'] = '***'

        if 'slack' in sanitized['notifications']:
            slack = sanitized['notifications']['slack']
            if 'webhook_url' in slack:
                slack['webhook_url'] = '***'

        if 'webhook' in sanitized['notifications']:
            webhook = sanitized['notifications']['webhook']
            if 'url' in webhook:
                webhook['url'] = '***'
            if 'headers' in webhook and isinstance(webhook['headers'], dict):
                for key in webhook['headers']:
                    if 'auth' in key.lower() or 'token' in key.lower():
                        webhook['headers'][key] = '***'

    return sanitized
