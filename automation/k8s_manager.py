"""
Kubernetes Manager for ImageSet Automation

Handles creation, monitoring, and management of Kubernetes Jobs
for executing oc-mirror in disconnected environments.
"""

import os
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
import yaml

try:
    from kubernetes import client, config as k8s_config
    from kubernetes.client.rest import ApiException
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    logging.warning("Kubernetes Python client not available")

logger = logging.getLogger(__name__)


class KubernetesManager:
    """Manages Kubernetes Jobs for oc-mirror operations"""

    def __init__(self, kubernetes_config: Dict[str, Any], dry_run: bool = False):
        """
        Initialize Kubernetes manager

        Args:
            kubernetes_config: Kubernetes configuration from automation config
            dry_run: If True, don't actually create resources
        """
        if not KUBERNETES_AVAILABLE:
            raise ImportError("kubernetes Python package is required for automation")

        self.config = kubernetes_config
        self.dry_run = dry_run
        self.namespace = kubernetes_config.get('namespace', 'default')

        # Initialize Kubernetes clients
        try:
            k8s_config.load_incluster_config()
            logger.info("Using in-cluster Kubernetes configuration")
        except Exception:
            try:
                k8s_config.load_kube_config()
                logger.info("Using kubeconfig for Kubernetes configuration")
            except Exception as e:
                logger.error(f"Failed to load Kubernetes configuration: {e}")
                raise

        self.batch_v1 = client.BatchV1Api()
        self.core_v1 = client.CoreV1Api()

    def create_mirror_job(
        self,
        version: str,
        imageset_config: str,
        job_name: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Create a Kubernetes Job to run oc-mirror

        Args:
            version: OCP version being mirrored
            imageset_config: ImageSet configuration YAML content
            job_name: Optional job name (generated if not provided)

        Returns:
            Tuple of (job_name, job_metadata)
        """
        if job_name is None:
            timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
            job_name = f"{self.config['job']['name_prefix']}-{timestamp}"

        # Create ConfigMap for imageset configuration
        config_map_name = self._create_config_map(job_name, imageset_config)

        # Create Job
        job_manifest = self._build_job_manifest(job_name, config_map_name, version)

        if self.dry_run:
            logger.info(f"DRY RUN: Would create job {job_name}")
            logger.debug(f"Job manifest:\n{yaml.dump(job_manifest)}")
            return job_name, {"dry_run": True, "manifest": job_manifest}

        try:
            # Ensure namespace exists
            self._ensure_namespace()

            # Create the Job
            job = self.batch_v1.create_namespaced_job(
                namespace=self.namespace,
                body=job_manifest
            )

            logger.info(f"Created Kubernetes Job: {job_name} in namespace {self.namespace}")

            metadata = {
                "name": job_name,
                "namespace": self.namespace,
                "uid": job.metadata.uid,
                "creation_timestamp": job.metadata.creation_timestamp.isoformat(),
                "config_map": config_map_name
            }

            return job_name, metadata

        except ApiException as e:
            logger.error(f"Failed to create Job: {e}")
            raise

    def monitor_job(
        self,
        job_name: str,
        poll_interval: int = 30,
        max_wait_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Monitor a Job until completion

        Args:
            job_name: Name of the Job to monitor
            poll_interval: Seconds between status checks
            max_wait_time: Maximum seconds to wait (None for unlimited)

        Returns:
            Job completion status and metadata
        """
        start_time = time.time()
        logger.info(f"Monitoring Job {job_name}")

        while True:
            try:
                job = self.batch_v1.read_namespaced_job_status(
                    name=job_name,
                    namespace=self.namespace
                )

                status = job.status
                conditions = status.conditions or []

                # Check for completion
                for condition in conditions:
                    if condition.type == "Complete" and condition.status == "True":
                        elapsed = time.time() - start_time
                        logger.info(f"Job {job_name} completed successfully in {elapsed:.1f}s")
                        return {
                            "status": "completed",
                            "succeeded": True,
                            "duration": elapsed,
                            "completion_time": datetime.utcnow().isoformat()
                        }

                    if condition.type == "Failed" and condition.status == "True":
                        elapsed = time.time() - start_time
                        logger.error(f"Job {job_name} failed after {elapsed:.1f}s")

                        # Get pod logs for debugging
                        logs = self._get_job_logs(job_name)

                        return {
                            "status": "failed",
                            "succeeded": False,
                            "duration": elapsed,
                            "failure_time": datetime.utcnow().isoformat(),
                            "reason": condition.reason if condition.reason else "Unknown",
                            "message": condition.message if condition.message else "No details",
                            "logs": logs
                        }

                # Check timeout
                if max_wait_time and (time.time() - start_time) > max_wait_time:
                    logger.warning(f"Job {job_name} monitoring timeout after {max_wait_time}s")
                    return {
                        "status": "timeout",
                        "succeeded": False,
                        "duration": time.time() - start_time
                    }

                # Log progress
                active = status.active or 0
                succeeded = status.succeeded or 0
                failed = status.failed or 0
                logger.debug(f"Job {job_name} status: active={active}, succeeded={succeeded}, failed={failed}")

                # Wait before next check
                time.sleep(poll_interval)

            except ApiException as e:
                logger.error(f"Error checking Job status: {e}")
                if e.status == 404:
                    return {
                        "status": "not_found",
                        "succeeded": False,
                        "error": "Job not found"
                    }
                raise

    def get_job_logs(self, job_name: str, tail_lines: int = 100) -> str:
        """
        Get logs from a Job's pods

        Args:
            job_name: Name of the Job
            tail_lines: Number of lines to retrieve from end

        Returns:
            Combined logs from all pods
        """
        return self._get_job_logs(job_name, tail_lines)

    def delete_job(self, job_name: str, delete_pods: bool = True) -> bool:
        """
        Delete a Job and optionally its pods

        Args:
            job_name: Name of the Job
            delete_pods: Also delete associated pods

        Returns:
            True if successful
        """
        try:
            # Delete the Job
            self.batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=self.namespace,
                propagation_policy='Foreground' if delete_pods else 'Orphan'
            )
            logger.info(f"Deleted Job {job_name}")
            return True

        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Job {job_name} not found")
                return True
            logger.error(f"Failed to delete Job: {e}")
            return False

    def cleanup_old_jobs(self, older_than_days: int = 7) -> int:
        """
        Clean up old completed Jobs

        Args:
            older_than_days: Delete jobs older than this many days

        Returns:
            Number of jobs deleted
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        deleted_count = 0

        try:
            jobs = self.batch_v1.list_namespaced_job(namespace=self.namespace)

            for job in jobs.items:
                # Check if job matches our prefix
                if not job.metadata.name.startswith(self.config['job']['name_prefix']):
                    continue

                # Check if completed
                if not job.status.completion_time:
                    continue

                # Check age
                completion_time = job.status.completion_time
                if completion_time.tzinfo is None:
                    completion_time = completion_time.replace(tzinfo=timezone.utc)
                if completion_time < cutoff_time:
                    self.delete_job(job.metadata.name)
                    deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} old jobs")
            return deleted_count

        except ApiException as e:
            logger.error(f"Failed to list jobs for cleanup: {e}")
            return deleted_count

    def _create_config_map(self, job_name: str, imageset_config: str) -> str:
        """Create ConfigMap with imageset configuration"""
        config_map_name = f"{self.config['config_map']['name_prefix']}-{job_name}"

        config_map = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=config_map_name),
            data={"imageset-config.yaml": imageset_config}
        )

        if not self.dry_run:
            self.core_v1.create_namespaced_config_map(
                namespace=self.namespace,
                body=config_map
            )
            logger.info(f"Created ConfigMap {config_map_name}")

        return config_map_name

    def _build_job_manifest(self, job_name: str, config_map_name: str, version: str) -> Dict:
        """Build Kubernetes Job manifest"""
        job_config = self.config['job']
        storage_config = self.config['storage']
        registry_config = self.config['registry_credentials']

        # Build volumes
        volumes = [
            {
                "name": "imageset-config",
                "configMap": {"name": config_map_name}
            },
            {
                "name": "registry-credentials",
                "secret": {"secretName": registry_config['secret_name']}
            }
        ]

        # Build volume mounts
        volume_mounts = [
            {
                "name": "imageset-config",
                "mountPath": "/config",
                "readOnly": True
            },
            {
                "name": "registry-credentials",
                "mountPath": registry_config['mount_path'],
                "readOnly": True
            }
        ]

        # Add storage volume and mount
        if storage_config.get('pvc', {}).get('enabled'):
            volumes.append({
                "name": "mirror-storage",
                "persistentVolumeClaim": {
                    "claimName": storage_config['pvc']['name']
                }
            })
        else:
            volumes.append({
                "name": "mirror-storage",
                "emptyDir": {}
            })

        volume_mounts.append({
            "name": "mirror-storage",
            "mountPath": storage_config['mount_path']
        })

        # Build oc-mirror command
        mirror_path = storage_config['mount_path']
        command = [
            "/bin/bash",
            "-c",
            f"oc-mirror --config /config/imageset-config.yaml file://{mirror_path}"
        ]

        # Build container spec
        container = {
            "name": "oc-mirror",
            "image": job_config['image'],
            "imagePullPolicy": job_config['image_pull_policy'],
            "command": command,
            "volumeMounts": volume_mounts,
            "resources": job_config.get('resources', {}),
            "env": [
                {"name": "OCP_VERSION", "value": version},
                {"name": "REGISTRY_AUTH_FILE", "value": f"{registry_config['mount_path']}/.dockerconfigjson"}
            ]
        }

        # Build Job manifest
        manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "labels": {
                    "app": "imageset-mirror",
                    "version": version,
                    "managed-by": "imageset-automation"
                },
                "annotations": {
                    "imageset.automation/version": version,
                    "imageset.automation/created-at": datetime.utcnow().isoformat()
                }
            },
            "spec": {
                "backoffLimit": job_config.get('backoff_limit', 3),
                "ttlSecondsAfterFinished": job_config.get('ttl_seconds_after_finished', 86400),
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "imageset-mirror",
                            "job": job_name
                        }
                    },
                    "spec": {
                        "restartPolicy": job_config.get('restart_policy', 'OnFailure'),
                        "serviceAccountName": self.config.get('service_account'),
                        "containers": [container],
                        "volumes": volumes
                    }
                }
            }
        }

        # Add image pull secrets if configured
        if job_config.get('image_pull_secrets'):
            manifest['spec']['template']['spec']['imagePullSecrets'] = job_config['image_pull_secrets']

        return manifest

    def _ensure_namespace(self):
        """Ensure the namespace exists"""
        try:
            self.core_v1.read_namespace(name=self.namespace)
        except ApiException as e:
            if e.status == 404:
                # Create namespace
                namespace = client.V1Namespace(
                    metadata=client.V1ObjectMeta(name=self.namespace)
                )
                self.core_v1.create_namespace(body=namespace)
                logger.info(f"Created namespace {self.namespace}")
            else:
                raise

    def _get_job_logs(self, job_name: str, tail_lines: int = 100) -> str:
        """Get logs from Job's pods"""
        try:
            # Find pods for this job
            pods = self.core_v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"job={job_name}"
            )

            if not pods.items:
                return "No pods found for job"

            # Collect logs from all pods
            all_logs = []
            for pod in pods.items:
                try:
                    logs = self.core_v1.read_namespaced_pod_log(
                        name=pod.metadata.name,
                        namespace=self.namespace,
                        tail_lines=tail_lines
                    )
                    all_logs.append(f"=== Pod: {pod.metadata.name} ===\n{logs}")
                except ApiException as e:
                    all_logs.append(f"=== Pod: {pod.metadata.name} ===\nFailed to retrieve logs: {e}")

            return "\n\n".join(all_logs)

        except ApiException as e:
            logger.error(f"Failed to get job logs: {e}")
            return f"Error retrieving logs: {e}"
