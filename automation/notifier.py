"""
Notification System for ImageSet Automation

Supports multiple notification channels:
- Email (SMTP)
- Slack (Webhook)
- Generic Webhooks
"""

import os
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages notifications across multiple channels"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize notification manager

        Args:
            config: Notification configuration dictionary
        """
        self.config = config
        self.enabled = config.get('enabled', False)

        if not self.enabled:
            logger.info("Notifications are disabled")
            return

        # Initialize notification channels
        self.email_config = config.get('email', {})
        self.slack_config = config.get('slack', {})
        self.webhook_config = config.get('webhook', {})

        # Expand environment variables in configuration
        self._expand_env_vars()

    def _expand_env_vars(self):
        """Expand environment variables in configuration values"""
        def expand_value(value):
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                return os.environ.get(env_var, value)
            return value

        def expand_dict(d):
            for key, value in d.items():
                if isinstance(value, dict):
                    expand_dict(value)
                elif isinstance(value, str):
                    d[key] = expand_value(value)

        expand_dict(self.email_config)
        expand_dict(self.slack_config)
        expand_dict(self.webhook_config)

    def notify_version_selected(self, version: str, channel: str, metadata: Optional[Dict] = None):
        """
        Send notification when version is selected

        Args:
            version: Selected OCP version
            channel: Channel name
            metadata: Additional metadata about the selection
        """
        if not self.enabled:
            return

        metadata = metadata or {}
        subject = f"ImageSet Automation: Version {version} Selected"
        message = self._format_version_selected_message(version, channel, metadata)

        self._send_notifications(
            subject=subject,
            message=message,
            event_type="version_selected",
            data={
                "version": version,
                "channel": channel,
                "metadata": metadata,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    def notify_mirror_start(self, version: str, job_name: str, metadata: Optional[Dict] = None):
        """
        Send notification when mirroring starts

        Args:
            version: OCP version being mirrored
            job_name: Kubernetes job name
            metadata: Additional metadata
        """
        if not self.enabled:
            return

        metadata = metadata or {}
        subject = f"ImageSet Automation: Mirroring Started for {version}"
        message = self._format_mirror_start_message(version, job_name, metadata)

        self._send_notifications(
            subject=subject,
            message=message,
            event_type="mirror_start",
            data={
                "version": version,
                "job_name": job_name,
                "metadata": metadata,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    def notify_mirror_complete(self, version: str, job_name: str, duration: float, metadata: Optional[Dict] = None):
        """
        Send notification when mirroring completes

        Args:
            version: OCP version mirrored
            job_name: Kubernetes job name
            duration: Duration in seconds
            metadata: Additional metadata
        """
        if not self.enabled:
            return

        metadata = metadata or {}
        subject = f"ImageSet Automation: Mirroring Complete for {version}"
        message = self._format_mirror_complete_message(version, job_name, duration, metadata)

        self._send_notifications(
            subject=subject,
            message=message,
            event_type="mirror_complete",
            data={
                "version": version,
                "job_name": job_name,
                "duration_seconds": duration,
                "metadata": metadata,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    def notify_failure(self, error: str, context: Optional[Dict] = None):
        """
        Send notification on failure

        Args:
            error: Error message
            context: Additional context about the failure
        """
        if not self.enabled:
            return

        context = context or {}
        subject = "ImageSet Automation: Failure Occurred"
        message = self._format_failure_message(error, context)

        self._send_notifications(
            subject=subject,
            message=message,
            event_type="failure",
            data={
                "error": error,
                "context": context,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    def _send_notifications(self, subject: str, message: str, event_type: str, data: Dict):
        """
        Send notifications to all enabled channels

        Args:
            subject: Notification subject
            message: Notification message
            event_type: Type of event
            data: Structured data for webhooks
        """
        # Check if this event type should be notified
        notify_key = f"notify_on_{event_type}"

        # Email
        if self.email_config.get('enabled') and self.email_config.get(notify_key, True):
            try:
                self._send_email(subject, message)
            except Exception as e:
                logger.error(f"Failed to send email notification: {e}")

        # Slack
        if self.slack_config.get('enabled') and self.slack_config.get(notify_key, True):
            try:
                self._send_slack(subject, message, data, event_type)
            except Exception as e:
                logger.error(f"Failed to send Slack notification: {e}")

        # Webhook
        if self.webhook_config.get('enabled') and self.webhook_config.get(notify_key, True):
            try:
                self._send_webhook(subject, message, data)
            except Exception as e:
                logger.error(f"Failed to send webhook notification: {e}")

    def _send_email(self, subject: str, body: str):
        """Send email notification"""
        config = self.email_config

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config['from_address']
        msg['To'] = ', '.join(config['to_addresses'])

        # Add plain text body
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)

        # Add HTML body
        html_body = self._text_to_html(body)
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)

        # Send email
        smtp_class = smtplib.SMTP_SSL if config.get('use_ssl') else smtplib.SMTP
        with smtp_class(config['smtp_server'], config['smtp_port']) as server:
            if config.get('use_tls') and not config.get('use_ssl'):
                server.starttls()
            if config.get('smtp_user') and config.get('smtp_password'):
                server.login(config['smtp_user'], config['smtp_password'])
            server.send_message(msg)

        logger.info(f"Email notification sent: {subject}")

    def _send_slack(self, subject: str, message: str, data: Dict, event_type: str):
        """Send Slack notification"""
        config = self.slack_config

        # Format Slack message
        payload = {
            "channel": config.get('channel'),
            "username": config.get('username', 'ImageSet Automation'),
            "icon_emoji": config.get('icon_emoji', ':package:'),
            "text": f"*{subject}*",
            "attachments": [
                {
                    "color": self._get_color_for_event(event_type),
                    "text": message,
                    "footer": "ImageSet Generator",
                    "ts": int(datetime.utcnow().timestamp())
                }
            ]
        }

        response = requests.post(
            config['webhook_url'],
            json=payload,
            timeout=10
        )
        response.raise_for_status()

        logger.info(f"Slack notification sent: {subject}")

    def _send_webhook(self, subject: str, message: str, data: Dict):
        """Send generic webhook notification"""
        config = self.webhook_config

        # Prepare payload
        payload = {
            "subject": subject,
            "message": message,
            "data": data
        }

        # Prepare headers
        headers = config.get('headers', {})

        # Send webhook
        method = config.get('method', 'POST').upper()
        response = requests.request(
            method=method,
            url=config['url'],
            json=payload,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()

        logger.info(f"Webhook notification sent: {subject}")

    def _format_version_selected_message(self, version: str, channel: str, metadata: Dict) -> str:
        """Format version selected message"""
        lines = [
            "Version Selection Completed",
            "=" * 50,
            "",
            f"Selected Version: {version}",
            f"Channel: {channel}",
            f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            ""
        ]

        if metadata:
            lines.append("Additional Details:")
            for key, value in metadata.items():
                lines.append(f"  {key}: {value}")

        lines.extend([
            "",
            "Next Steps:",
            "- ImageSet configuration will be generated",
            "- Kubernetes Job will be created to start mirroring",
            "- You will receive another notification when mirroring completes"
        ])

        return "\n".join(lines)

    def _format_mirror_start_message(self, version: str, job_name: str, metadata: Dict) -> str:
        """Format mirror start message"""
        lines = [
            "Mirroring Process Started",
            "=" * 50,
            "",
            f"OCP Version: {version}",
            f"Kubernetes Job: {job_name}",
            f"Start Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            ""
        ]

        if metadata.get('operators'):
            lines.append(f"Operators: {len(metadata['operators'])} packages")
        if metadata.get('additional_images'):
            lines.append(f"Additional Images: {len(metadata['additional_images'])}")

        lines.extend([
            "",
            "Status:",
            "- The mirroring job is now running in Kubernetes",
            "- This process may take several hours depending on content size",
            "- You will receive a notification when mirroring completes"
        ])

        return "\n".join(lines)

    def _format_mirror_complete_message(self, version: str, job_name: str, duration: float, metadata: Dict) -> str:
        """Format mirror complete message"""
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)

        lines = [
            "Mirroring Process Completed Successfully",
            "=" * 50,
            "",
            f"OCP Version: {version}",
            f"Kubernetes Job: {job_name}",
            f"Completion Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Duration: {hours}h {minutes}m {seconds}s",
            ""
        ]

        if metadata.get('mirror_size'):
            lines.append(f"Mirror Size: {metadata['mirror_size']}")
        if metadata.get('image_count'):
            lines.append(f"Images Mirrored: {metadata['image_count']}")

        lines.extend([
            "",
            "Status: SUCCESS",
            "",
            "The mirrored content is now available and ready for use in your disconnected environment."
        ])

        return "\n".join(lines)

    def _format_failure_message(self, error: str, context: Dict) -> str:
        """Format failure message"""
        lines = [
            "Automation Failure",
            "=" * 50,
            "",
            f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "Error:",
            f"  {error}",
            ""
        ]

        if context:
            lines.append("Context:")
            for key, value in context.items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        lines.extend([
            "Action Required:",
            "- Review the automation logs for details",
            "- Check Kubernetes job status if a job was created",
            "- Verify configuration and credentials",
            "- Contact the platform team if the issue persists"
        ])

        return "\n".join(lines)

    def _text_to_html(self, text: str) -> str:
        """Convert plain text to simple HTML"""
        lines = text.split('\n')
        html_lines = ['<html><body><pre style="font-family: monospace;">']
        html_lines.extend(lines)
        html_lines.append('</pre></body></html>')
        return '\n'.join(html_lines)

    def _get_color_for_event(self, event_type: str) -> str:
        """Get color code for Slack attachments based on event type"""
        colors = {
            'version_selected': '#36a64f',  # Green
            'mirror_start': '#2196F3',      # Blue
            'mirror_complete': '#4CAF50',   # Success green
            'failure': '#f44336'            # Red
        }
        return colors.get(event_type, '#808080')  # Default gray


def create_notifier(config_path: Optional[str] = None) -> NotificationManager:
    """
    Create notification manager from configuration file

    Args:
        config_path: Path to configuration file (default: automation/config.yaml)

    Returns:
        NotificationManager instance
    """
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(__file__),
            'config.yaml'
        )

    import yaml
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    return NotificationManager(config.get('notifications', {}))
