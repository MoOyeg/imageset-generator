# ImageSet Generator Automation

Complete automation system for discovering, configuring, and mirroring OpenShift releases in disconnected environments.

## Overview

This automation system enables hands-free operation of the ImageSet Generator in disconnected environments. It automatically:

1. **Discovers** the latest OCP version in your specified channel (stable/fast/eus)
2. **Generates** ImageSetConfiguration files
3. **Creates** Kubernetes Jobs to execute mirroring
4. **Monitors** job completion
5. **Notifies** stakeholders at key milestones

The system is designed to run in the last or second-to-last week of each month, ensuring you always have the latest content mirrored for your disconnected clusters.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Automation Scheduler                        │
│  (Runs in last/second-to-last week of month)                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Automation Engine                            │
│  1. Version Discovery    → oc-mirror list releases              │
│  2. Config Generation    → ImageSetGenerator                    │
│  3. Job Creation         → Kubernetes Job                       │
│  4. Job Monitoring       → Watch for completion                 │
│  5. Notifications        → Email/Slack/Webhook                  │
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
    ┌────────┐    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │Version │    │ImageSet  │   │K8s Job   │   │Notifier  │
    │Discovery   │Config    │   │Manager   │   │          │
    │        │    │Generator │   │          │   │          │
    └────────┘    └──────────┘   └──────────┘   └──────────┘
```

## Features

### 🗓️ Intelligent Scheduling
- Runs automatically in configurable monthly windows
- Last week (days 22-31) or second-to-last week (days 15-21)
- Uses fixed calendar windows for execution
- Timezone-aware scheduling

### 🔍 Smart Version Discovery
- Automatically finds latest version in specified channel
- Supports multiple strategies: `latest`, `latest-patch`, `latest-stable`
- Configurable minimum age before selecting versions
- Skips unchanged versions to avoid redundant mirroring

### ☸️ Kubernetes Integration
- Creates Jobs with proper resource limits
- Mounts PVCs for mirror storage (or emptyDir when disabled)
- Injects registry credentials
- Monitors job progress and completion
- Automatic cleanup of old jobs

### 📬 Multi-Channel Notifications
- **Email** (SMTP)
- **Slack** (Webhooks)
- **Generic Webhooks** (REST API)
- Notifications sent at:
  - Version selection
  - Mirror start
  - Mirror completion
  - Failures

### 🔒 Safety Features
- Dry-run mode for testing
- Prevent concurrent jobs
- Skip unchanged versions
- Manual approval option
- State persistence

## Installation

### 1. Install Dependencies

```bash
pip install -r automation/requirements.txt
```

### 2. Configure Automation

Edit `automation/config.yaml`:

```yaml
scheduler:
  enabled: true
  execution_window: "last-week"  # or "second-to-last-week" or "both"
  day_of_week: 1  # 0=Monday, 6=Sunday
  time: "02:00"
  timezone: "UTC"

version_discovery:
  channel: "stable"  # stable, fast, eus, candidate
  ocp_version: "latest"  # or specific version like "4.16"
  selection_strategy: "latest"

kubernetes:
  namespace: "openshift-imageset-mirror"
  service_account: "imageset-mirror-sa"
  # ... see config.yaml for full options

notifications:
  enabled: true
  email:
    enabled: true
    smtp_server: "smtp.example.com"
    # ...
  slack:
    enabled: true
    webhook_url: "${SLACK_WEBHOOK_URL}"
    # ...
```

### 3. Set Environment Variables

For sensitive configuration:

```bash
export SMTP_PASSWORD="your-smtp-password"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
export WEBHOOK_TOKEN="your-webhook-token"
```

### 4. Prepare Kubernetes Resources

#### Create Namespace

```bash
kubectl create namespace openshift-imageset-mirror
```

Note: Namespace creation is cluster-scoped. If the automation service account
does not have namespace permissions, pre-create the namespace (see
`automation/examples/kubernetes-rbac.yaml` for the optional ClusterRole).

#### Create Service Account

```bash
kubectl create serviceaccount imageset-mirror-sa -n openshift-imageset-mirror
```

#### Create PVC for Mirror Storage

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: imageset-mirror-storage
  namespace: openshift-imageset-mirror
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 500Gi
  storageClassName: ocs-storagecluster-ceph-rbd
```

```bash
kubectl apply -f pvc.yaml
```

#### Create Registry Credentials Secret

```bash
# If you have a pull secret file
kubectl create secret generic redhat-registry-pull-secret \
  --from-file=.dockerconfigjson=/path/to/pull-secret.json \
  --type=kubernetes.io/dockerconfigjson \
  -n openshift-imageset-mirror

# Or create from existing OpenShift pull secret
oc get secret pull-secret -n openshift-config -o json | \
  jq -r '.data.".dockerconfigjson"' | base64 -d > /tmp/pull-secret.json

kubectl create secret generic redhat-registry-pull-secret \
  --from-file=.dockerconfigjson=/tmp/pull-secret.json \
  --type=kubernetes.io/dockerconfigjson \
  -n openshift-imageset-mirror
```

## Usage

### Run as Scheduler (Continuous)

Start the scheduler to run automatically:

```bash
python -m automation.scheduler --config automation/config.yaml
```

Or with logging:

```bash
python -m automation.scheduler \
  --config automation/config.yaml \
  --log-level DEBUG
```

### Run Once (Manual Trigger)

Execute automation immediately:

```bash
python -m automation.scheduler \
  --config automation/config.yaml \
  --run-now
```

Or use the engine directly:

```bash
python -m automation.engine \
  --config automation/config.yaml
```

### Dry Run Mode

Test without creating actual Kubernetes jobs. Dry-run works even if the Kubernetes client is unavailable:

```bash
python -m automation.engine \
  --config automation/config.yaml \
  --dry-run
```

### Integrate with Flask Application

The automation can run as part of the web application:

```python
# In app.py
from automation.api import automation_bp, init_automation

# Register blueprint
app.register_blueprint(automation_bp)

# Initialize automation
init_automation('automation/config.yaml')
```

### API Endpoints

Once integrated with Flask:

```bash
# Get automation status
curl http://localhost:5000/api/automation/status

# Manually trigger automation
curl -X POST http://localhost:5000/api/automation/trigger

# Get execution history
curl http://localhost:5000/api/automation/history

# Get Kubernetes jobs status
curl http://localhost:5000/api/automation/jobs

# Get job logs
curl http://localhost:5000/api/automation/jobs/<job-name>/logs
```

## Configuration Reference

### Scheduler Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `enabled` | Enable scheduler | `true` |
| `execution_window` | When to run: `last-week`, `second-to-last-week`, `both` | `last-week` |
| `day_of_week` | Day to run (0=Monday, 6=Sunday) | `1` (Tuesday) |
| `time` | Time to run (24-hour format) | `02:00` |
| `timezone` | Timezone for scheduling | `UTC` |

### Version Discovery

| Parameter | Description | Default |
|-----------|-------------|---------|
| `channel` | OCP channel: `stable`, `fast`, `eus`, `candidate` | `stable` |
| `ocp_version` | Version to track: `latest` or specific (e.g., `4.16`) | `latest` |
| `selection_strategy` | How to select: `latest`, `latest-patch`, `latest-stable` | `latest` |
| `min_days_since_release` | Minimum age for `latest-stable` strategy | `7` |

### ImageSet Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `include_graph` | Include version graph data | `true` |
| `operators.enabled` | Include operators | `true` |
| `operators.packages` | List of operator packages | `[]` |
| `operators.catalogs` | Catalogs to use | `[]` |
| `additional_images.enabled` | Include additional images | `false` |
| `additional_images.images` | List of image URLs | `[]` |

### Kubernetes Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `namespace` | K8s namespace for jobs | `openshift-imageset-mirror` |
| `service_account` | Service account to use | `imageset-mirror-sa` |
| `job.backoff_limit` | Job retry limit | `3` |
| `job.resources.requests.memory` | Memory request | `4Gi` |
| `job.resources.limits.memory` | Memory limit | `8Gi` |
| `storage.pvc.name` | PVC name for mirror storage | `imageset-mirror-storage` |
| `storage.pvc.size` | PVC size | `500Gi` |

### Notification Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `enabled` | Enable notifications | `true` |
| `email.enabled` | Enable email | `false` |
| `email.smtp_server` | SMTP server | - |
| `email.smtp_port` | SMTP port | `587` |
| `slack.enabled` | Enable Slack | `false` |
| `slack.webhook_url` | Slack webhook URL | - |
| `webhook.enabled` | Enable generic webhook | `false` |
| `webhook.url` | Webhook URL | - |

## Deployment Patterns

### Pattern 1: Containerized Scheduler

Run as a container alongside the ImageSet Generator:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: imageset-automation
  namespace: openshift-imageset-mirror
spec:
  replicas: 1
  selector:
    matchLabels:
      app: imageset-automation
  template:
    metadata:
      labels:
        app: imageset-automation
    spec:
      serviceAccountName: imageset-mirror-sa
      containers:
      - name: automation
        image: your-registry/imageset-generator:latest
        command:
          - python
          - -m
          - automation.scheduler
          - --config
          - /config/config.yaml
        volumeMounts:
        - name: config
          mountPath: /config
        - name: data
          mountPath: /app/data
        env:
        - name: SMTP_PASSWORD
          valueFrom:
            secretKeyRef:
              name: automation-secrets
              key: smtp-password
        - name: SLACK_WEBHOOK_URL
          valueFrom:
            secretKeyRef:
              name: automation-secrets
              key: slack-webhook-url
      volumes:
      - name: config
        configMap:
          name: automation-config
      - name: data
        persistentVolumeClaim:
          claimName: automation-data
```

### Pattern 2: CronJob Trigger

Use Kubernetes CronJob to trigger automation:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: imageset-automation-trigger
  namespace: openshift-imageset-mirror
spec:
  schedule: "0 2 * * 2"  # Tuesday at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: imageset-mirror-sa
          containers:
          - name: trigger
            image: your-registry/imageset-generator:latest
            command:
              - python
              - -m
              - automation.engine
              - --config
              - /config/config.yaml
            volumeMounts:
            - name: config
              mountPath: /config
          restartPolicy: OnFailure
          volumes:
          - name: config
            configMap:
              name: automation-config
```

### Pattern 3: API-Triggered

Integrate with existing automation/CI systems:

```bash
# Trigger from Jenkins, GitLab CI, etc.
curl -X POST http://imageset-generator:5000/api/automation/trigger
```

## Monitoring

### Check Scheduler Status

```bash
# View schedule info
curl http://localhost:5000/api/automation/status | jq '.schedule'
```

### Check Execution History

```bash
# List recent executions
curl http://localhost:5000/api/automation/history | jq '.executions'

# Get specific execution
curl http://localhost:5000/api/automation/history/<execution-id>
```

### Monitor Kubernetes Jobs

```bash
# List all mirror jobs
kubectl get jobs -n openshift-imageset-mirror -l app=imageset-mirror

# Watch job progress
kubectl get jobs -n openshift-imageset-mirror -l app=imageset-mirror -w

# Get job logs
kubectl logs -n openshift-imageset-mirror job/<job-name>

# Or via API
curl http://localhost:5000/api/automation/jobs/<job-name>/logs
```

### View State File

```bash
cat data/automation-state.json
```

```json
{
  "last_processed_version": "4.16.3",
  "last_job_name": "imageset-mirror-20260115-020000",
  "last_status": "success",
  "last_execution_time": "2026-01-15T02:30:45.123456"
}
```

## Troubleshooting

### Scheduler Not Running

**Problem**: Automation doesn't execute on schedule

**Solutions**:
1. Check `scheduler.enabled` is `true` in config
2. Verify the scheduler process is running
3. Check logs for errors
4. Validate execution window logic

```bash
python -m automation.scheduler --config automation/config.yaml --log-level DEBUG
```

### Version Discovery Fails

**Problem**: Cannot discover OCP versions

**Solutions**:
1. Verify `oc-mirror` is installed and in PATH
2. Check network connectivity to Red Hat registries
3. Verify channel name is correct
4. Check timeout settings

```bash
# Test oc-mirror manually
oc-mirror list releases --channel stable-4.16 --version 4.16
```

### Job Creation Fails

**Problem**: Kubernetes Job not created

**Solutions**:
1. Verify Kubernetes credentials are configured
2. Check namespace exists
3. Verify service account exists
4. Check RBAC permissions
5. Verify PVC exists and is accessible

```bash
# Check service account
kubectl get sa imageset-mirror-sa -n openshift-imageset-mirror

# Check PVC
kubectl get pvc imageset-mirror-storage -n openshift-imageset-mirror

# Check RBAC
kubectl auth can-i create jobs --as=system:serviceaccount:openshift-imageset-mirror:imageset-mirror-sa -n openshift-imageset-mirror
```

### Job Fails During Execution

**Problem**: Mirror job fails

**Solutions**:
1. Check job logs for errors
2. Verify registry credentials
3. Check storage space
4. Verify network connectivity from job pods

```bash
# Get job status
kubectl describe job <job-name> -n openshift-imageset-mirror

# Get pod logs
kubectl logs -n openshift-imageset-mirror -l job=<job-name>

# Check PVC usage
kubectl exec -n openshift-imageset-mirror <pod-name> -- df -h /mirror
```

### Notifications Not Received

**Problem**: No notifications sent

**Solutions**:
1. Check `notifications.enabled` is `true`
2. Verify channel-specific settings (email, Slack, webhook)
3. Check environment variables for sensitive data
4. Review logs for notification errors
5. Test connectivity to SMTP/Slack/webhook endpoints

```bash
# Test SMTP connectivity
telnet smtp.example.com 587

# Test Slack webhook
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test message"}' \
  $SLACK_WEBHOOK_URL
```

## Security Considerations

### Credentials Management

- Store sensitive data in Kubernetes Secrets
- Use environment variables for passwords/tokens
- Never commit credentials to git
- Rotate credentials regularly

### RBAC Permissions

The service account needs:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: imageset-automation-role
  namespace: openshift-imageset-mirror
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "get", "list", "watch", "delete"]
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["create", "get", "list", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: imageset-automation-binding
  namespace: openshift-imageset-mirror
subjects:
- kind: ServiceAccount
  name: imageset-mirror-sa
  namespace: openshift-imageset-mirror
roleRef:
  kind: Role
  name: imageset-automation-role
  apiGroup: rbac.authorization.k8s.io
```

If you want automation to create namespaces automatically, add the optional
ClusterRole/ClusterRoleBinding from `automation/examples/kubernetes-rbac.yaml`
to grant `namespaces` create/get permissions.

### Network Policies

Restrict network access for mirror jobs:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: imageset-mirror-policy
  namespace: openshift-imageset-mirror
spec:
  podSelector:
    matchLabels:
      app: imageset-mirror
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443  # HTTPS to registries
```

## Performance Tuning

### Resource Allocation

Adjust based on your content size:

```yaml
kubernetes:
  job:
    resources:
      requests:
        memory: "8Gi"  # Increase for large operator catalogs
        cpu: "4"       # More CPUs speed up extraction
      limits:
        memory: "16Gi"
        cpu: "8"
```

### Storage Performance

Use high-performance storage classes for faster mirroring:

```yaml
kubernetes:
  storage:
    pvc:
      storage_class: "fast-ssd"  # Use SSD-backed storage
      size: "1Ti"  # Ensure adequate space
```

### Timeout Adjustments

For large mirror operations:

```yaml
monitoring:
  max_wait_time: 28800  # 8 hours for very large mirrors
  poll_interval: 60     # Check every minute
```

If `max_wait_time` is omitted or set to null, the default timeout is 4 hours.

## Advanced Usage

### Custom Version Selection

Implement custom version selection logic by extending `AutomationEngine`:

```python
from automation.engine import AutomationEngine

class CustomEngine(AutomationEngine):
    def _select_version(self, releases, strategy, discovery_config):
        # Your custom logic here
        return custom_selected_version
```

### Custom Notifications

Add custom notification channels:

```python
from automation.notifier import NotificationManager

class CustomNotifier(NotificationManager):
    def _send_notifications(self, subject, message, event_type, data):
        super()._send_notifications(subject, message, event_type, data)
        # Your custom notification logic
        self._send_teams(message)
```

### Multi-Channel Mirroring

Configure different automations for different channels:

```yaml
# config-stable.yaml - for stable channel
version_discovery:
  channel: "stable"

# config-fast.yaml - for fast channel
version_discovery:
  channel: "fast"
```

Run multiple schedulers:

```bash
python -m automation.scheduler --config automation/config-stable.yaml &
python -m automation.scheduler --config automation/config-fast.yaml &
```

## Contributing

When contributing to the automation module:

1. Add tests for new functionality
2. Update configuration schema in `config.yaml`
3. Document new features in this README
4. Follow existing code patterns
5. Test with `--dry-run` before production use

## License

Same as main ImageSet Generator project.

## Support

For issues and questions:
- GitHub Issues: [imageset-generator/issues](https://github.com/yourusername/imageset-generator/issues)
- Documentation: This README and inline code comments
- Examples: See `automation/config.yaml` for complete configuration example
