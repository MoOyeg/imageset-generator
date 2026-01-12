"""
Automation Engine for ImageSet Generator

Orchestrates the complete workflow:
1. Version discovery
2. Configuration generation
3. Kubernetes job creation
4. Job monitoring
5. Notifications
"""

import os
import sys
import json
import logging
import time
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import ImageSetGenerator
from automation.notifier import NotificationManager
from automation.k8s_manager import KubernetesManager, DEFAULT_MONITOR_MAX_WAIT_TIME

logger = logging.getLogger(__name__)


class AutomationEngine:
    """Main automation engine"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize automation engine

        Args:
            config: Complete automation configuration
        """
        self.config = config
        self.dry_run = config.get('safety', {}).get('dry_run', False)

        # Initialize components
        self.notifier = NotificationManager(config.get('notifications', {}))

        try:
            self.k8s_manager = KubernetesManager(
                config.get('kubernetes', {}),
                dry_run=self.dry_run
            )
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes manager: {e}")
            self.k8s_manager = None

        # State management
        self.state_file = config.get('persistence', {}).get('state_file', 'data/automation-state.json')
        self.history_file = config.get('persistence', {}).get('history_file', 'data/automation-history.json')
        self.state = self._load_state()
        self.history = self._load_history()

    def run_automation(self) -> Dict[str, Any]:
        """
        Execute the complete automation workflow

        Returns:
            Execution results and metadata
        """
        execution_id = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        logger.info(f"Starting automation execution: {execution_id}")

        result = {
            "execution_id": execution_id,
            "start_time": datetime.utcnow().isoformat(),
            "success": False,
            "steps": {}
        }

        try:
            # Step 1: Safety checks
            logger.info("Step 1: Running safety checks")
            if not self._safety_checks():
                result["error"] = "Safety checks failed"
                return result
            result["steps"]["safety_checks"] = {"success": True}

            # Step 2: Discover version
            logger.info("Step 2: Discovering OCP version")
            version_info = self._discover_version()
            if not version_info:
                result["error"] = "Version discovery failed"
                return result

            result["steps"]["version_discovery"] = {
                "success": True,
                "version": version_info['version'],
                "channel": version_info['channel']
            }

            # Check if version unchanged
            if self._should_skip_unchanged_version(version_info['version']):
                logger.info(f"Version {version_info['version']} already processed, skipping")
                result["skipped"] = True
                result["reason"] = "Version unchanged"
                return result

            # Send version selection notification
            self.notifier.notify_version_selected(
                version=version_info['version'],
                channel=version_info['channel'],
                metadata=version_info
            )

            # Step 3: Generate ImageSet configuration
            logger.info("Step 3: Generating ImageSet configuration")
            imageset_config = self._generate_imageset_config(version_info)
            if not imageset_config:
                result["error"] = "ImageSet configuration generation failed"
                return result

            result["steps"]["config_generation"] = {"success": True}

            # Step 4: Create Kubernetes job
            logger.info("Step 4: Creating Kubernetes job")
            if not self.k8s_manager:
                if self.dry_run:
                    job_prefix = self.config.get('kubernetes', {}).get('job', {}).get('name_prefix', 'imageset-mirror')
                    job_name = f"{job_prefix}-{execution_id}"
                    job_metadata = {"dry_run": True, "reason": "Kubernetes manager not available"}
                else:
                    result["error"] = "Kubernetes manager not available"
                    return result
            else:
                job_name, job_metadata = self.k8s_manager.create_mirror_job(
                    version=version_info['version'],
                    imageset_config=imageset_config
                )

            result["steps"]["job_creation"] = {
                "success": True,
                "job_name": job_name,
                "metadata": job_metadata
            }

            # Send mirror start notification
            self.notifier.notify_mirror_start(
                version=version_info['version'],
                job_name=job_name,
                metadata={
                    "operators": self.config.get('imageset', {}).get('operators', {}).get('packages', []),
                    "additional_images": self.config.get('imageset', {}).get('additional_images', {}).get('images', [])
                }
            )

            # Step 5: Monitor job (if not dry run)
            if not self.dry_run:
                logger.info("Step 5: Monitoring job execution")
                monitoring_config = self.config.get('monitoring', {})

                max_wait_time = monitoring_config.get('max_wait_time')
                if max_wait_time is None:
                    max_wait_time = DEFAULT_MONITOR_MAX_WAIT_TIME

                job_result = self.k8s_manager.monitor_job(
                    job_name=job_name,
                    poll_interval=monitoring_config.get('poll_interval', 30),
                    max_wait_time=max_wait_time
                )

                result["steps"]["job_monitoring"] = job_result

                if job_result['succeeded']:
                    # Success notification
                    self.notifier.notify_mirror_complete(
                        version=version_info['version'],
                        job_name=job_name,
                        duration=job_result['duration'],
                        metadata={}
                    )

                    # Update state
                    self._update_state(version_info['version'], job_name, "success")
                    result["success"] = True

                else:
                    # Failure notification
                    self.notifier.notify_failure(
                        error=f"Job {job_name} failed",
                        context={
                            "job_name": job_name,
                            "version": version_info['version'],
                            "reason": job_result.get('reason', 'Unknown'),
                            "message": job_result.get('message', 'No details')
                        }
                    )

                    result["error"] = f"Job failed: {job_result.get('reason', 'Unknown')}"

            else:
                logger.info("Dry run mode: Skipping job monitoring")
                result["success"] = True
                result["dry_run"] = True

        except Exception as e:
            logger.exception(f"Automation execution failed: {e}")
            result["error"] = str(e)

            # Send failure notification
            self.notifier.notify_failure(
                error=str(e),
                context={"execution_id": execution_id}
            )

        finally:
            result["end_time"] = datetime.utcnow().isoformat()
            self._save_to_history(result)

        return result

    def _safety_checks(self) -> bool:
        """Run safety checks before execution"""
        safety_config = self.config.get('safety', {})

        # Check if approval required
        if safety_config.get('require_approval', False):
            logger.error("Manual approval is required but not implemented in automated mode")
            return False

        # Check for concurrent jobs
        if safety_config.get('prevent_concurrent_jobs', True):
            if self.k8s_manager and not self.dry_run:
                # Check for running jobs
                try:
                    jobs = self.k8s_manager.batch_v1.list_namespaced_job(
                        namespace=self.k8s_manager.namespace,
                        label_selector="app=imageset-mirror"
                    )

                    for job in jobs.items:
                        if job.status.active and job.status.active > 0:
                            logger.error(f"Concurrent job detected: {job.metadata.name}")
                            return False

                except Exception as e:
                    logger.warning(f"Could not check for concurrent jobs: {e}")

        return True

    def _discover_version(self) -> Optional[Dict[str, Any]]:
        """
        Discover the target OCP version based on configuration

        Returns:
            Version information dictionary or None on failure
        """
        discovery_config = self.config.get('version_discovery', {})
        channel = discovery_config.get('channel', 'stable')
        ocp_version = discovery_config.get('ocp_version', 'latest')
        strategy = discovery_config.get('selection_strategy', 'latest')

        logger.info(f"Discovering version: ocp_version={ocp_version}, channel={channel}, strategy={strategy}")

        try:
            # Step 1: Get available OCP versions
            if ocp_version == 'latest':
                ocp_version = self._get_latest_ocp_version()
                if not ocp_version:
                    logger.error("Failed to determine latest OCP version")
                    return None

            logger.info(f"Using OCP version: {ocp_version}")

            # Step 2: Get channel name
            full_channel = f"{channel}-{ocp_version}"

            # Step 3: Get releases in channel
            releases = self._get_channel_releases(ocp_version, full_channel)
            if not releases:
                logger.error(f"No releases found in channel {full_channel}")
                return None

            # Step 4: Select version based on strategy
            selected_version = self._select_version(releases, strategy, discovery_config)
            if not selected_version:
                logger.error("Version selection failed")
                return None

            logger.info(f"Selected version: {selected_version}")

            return {
                "version": selected_version,
                "channel": full_channel,
                "ocp_major_minor": ocp_version,
                "available_releases": releases,
                "selection_strategy": strategy,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.exception(f"Version discovery failed: {e}")
            return None

    def _get_latest_ocp_version(self) -> Optional[str]:
        """Get the latest available OCP major.minor version"""
        try:
            result = subprocess.run(
                ['oc-mirror', 'list', 'releases'],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                logger.error(f"oc-mirror list releases failed: {result.stderr}")
                return None

            # Parse output to find versions
            versions = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and '.' in line and not line.startswith('#'):
                    # Extract version pattern like "4.16", "4.17", etc.
                    parts = line.split()
                    for part in parts:
                        if part.count('.') == 1:
                            try:
                                major, minor = part.split('.')
                                if major.isdigit() and minor.isdigit():
                                    versions.append(part)
                            except ValueError:
                                continue

            if versions:
                # Sort and return latest
                versions.sort(key=self._version_key)
                latest = versions[-1]
                logger.info(f"Latest OCP version: {latest}")
                return latest

            return None

        except Exception as e:
            logger.exception(f"Failed to get latest OCP version: {e}")
            return None

    def _get_channel_releases(self, version: str, channel: str) -> List[str]:
        """Get available releases in a channel"""
        try:
            result = subprocess.run(
                ['oc-mirror', 'list', 'releases', '--channel', channel, '--version', version],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                logger.error(f"oc-mirror list releases failed: {result.stderr}")
                return []

            # Parse releases
            releases = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and line.startswith(version):
                    releases.append(line)

            releases.sort(key=self._version_key)
            logger.info(f"Found {len(releases)} releases in {channel}")
            return releases

        except Exception as e:
            logger.exception(f"Failed to get channel releases: {e}")
            return []

    def _version_key(self, version: str) -> List[int]:
        """Convert a version string into sortable integers."""
        parts = version.split('.')
        numbers = []
        for part in parts:
            match = re.match(r"(\d+)", part)
            numbers.append(int(match.group(1)) if match else 0)
        return numbers

    def _select_version(
        self,
        releases: List[str],
        strategy: str,
        discovery_config: Dict
    ) -> Optional[str]:
        """Select a version based on strategy"""
        if not releases:
            return None

        if strategy == 'latest':
            return releases[-1]

        elif strategy == 'latest-patch':
            # Latest patch of the major.minor
            return releases[-1]

        elif strategy == 'latest-stable':
            # Latest version with minimum days since release
            min_days = discovery_config.get('min_days_since_release', 7)
            # For now, just return latest (would need release date info for real implementation)
            logger.warning(f"latest-stable strategy not fully implemented, using latest")
            return releases[-1]

        else:
            logger.error(f"Unknown selection strategy: {strategy}")
            return None

    def _should_skip_unchanged_version(self, version: str) -> bool:
        """Check if version should be skipped because it's unchanged"""
        if not self.config.get('safety', {}).get('skip_if_version_unchanged', True):
            return False

        last_version = self.state.get('last_processed_version')
        if last_version == version:
            last_status = self.state.get('last_status')
            if last_status == 'success':
                return True

        return False

    def _generate_imageset_config(self, version_info: Dict[str, Any]) -> Optional[str]:
        """Generate ImageSet configuration YAML"""
        try:
            generator = ImageSetGenerator()

            # Add platform/OCP configuration
            imageset_config = self.config.get('imageset', {})
            version = version_info['version']
            channel = version_info['channel']

            generator.add_ocp_versions(
                versions=[version],
                channel=channel,
                min_version=version,
                max_version=version,
                graph=imageset_config.get('include_graph', True)
            )

            # Add operators if enabled
            operators_config = imageset_config.get('operators', {})
            if operators_config.get('enabled', False):
                packages = operators_config.get('packages', [])
                catalogs = operators_config.get('catalogs', [])

                if packages and catalogs:
                    ocp_major_minor = version_info['ocp_major_minor']

                    for catalog_short_name in catalogs:
                        # Build full catalog URL
                        catalog_url = f"registry.redhat.io/redhat/{catalog_short_name}:v{ocp_major_minor}"

                        # Build operator list for add_operators (expects list of operator names/dicts)
                        operator_list = [{'name': pkg} for pkg in packages]
                        generator.add_operators(
                            operators=operator_list,
                            catalog=catalog_url,
                            ocp_version=ocp_major_minor
                        )

            # Add additional images if enabled
            additional_images_config = imageset_config.get('additional_images', {})
            if additional_images_config.get('enabled', False):
                images = additional_images_config.get('images', [])
                if images:
                    generator.add_additional_images(images)

            # Generate YAML
            yaml_content = generator.generate_yaml()
            logger.info("Generated ImageSet configuration")
            logger.debug(f"Configuration:\n{yaml_content}")

            return yaml_content

        except Exception as e:
            logger.exception(f"Failed to generate ImageSet configuration: {e}")
            return None

    def _load_state(self) -> Dict:
        """Load automation state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

        return {}

    def _save_state(self, state: Dict):
        """Save automation state to file"""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _update_state(self, version: str, job_name: str, status: str):
        """Update automation state after execution"""
        self.state.update({
            "last_processed_version": version,
            "last_job_name": job_name,
            "last_status": status,
            "last_execution_time": datetime.utcnow().isoformat()
        })
        self._save_state(self.state)

    def _load_history(self) -> List[Dict]:
        """Load execution history"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")

        return []

    def _save_history(self, history: List[Dict]):
        """Save execution history"""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)

            # Limit history size
            max_entries = self.config.get('persistence', {}).get('max_history_entries', 50)
            if len(history) > max_entries:
                history = history[-max_entries:]

            self.history = history

            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def _save_to_history(self, result: Dict):
        """Add execution result to history"""
        self.history.append(result)
        self._save_history(self.history)


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load automation configuration from file

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary
    """
    import yaml

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    return config


def main():
    """Main entry point for automation"""
    import argparse

    parser = argparse.ArgumentParser(description='ImageSet Generator Automation')
    parser.add_argument(
        '--config',
        default='automation/config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode (no actual changes)'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load configuration
    config = load_config(args.config)

    # Override dry-run if specified
    if args.dry_run:
        config.setdefault('safety', {})['dry_run'] = True

    # Create and run engine
    engine = AutomationEngine(config)
    result = engine.run_automation()

    # Print result
    print(json.dumps(result, indent=2))

    # Exit with appropriate code
    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
