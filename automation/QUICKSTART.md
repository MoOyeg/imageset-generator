# Quick Start Guide - ImageSet Automation

Get the automation system up and running in 15 minutes.

## Prerequisites

- Kubernetes cluster (OpenShift or vanilla K8s)
- `kubectl` or `oc` CLI access
- Registry credentials (Red Hat pull secret)
- Python 3.11+ (for local testing)

## Step 1: Install Dependencies (5 minutes)

```bash
# Install automation dependencies
pip install -r automation/requirements.txt

# Verify installation
python -c "import apscheduler, kubernetes; print('✓ Dependencies installed')"
```

## Step 2: Configure Automation (5 minutes)

Edit `automation/config.yaml`:

```yaml
scheduler:
  enabled: true
  execution_window: "last-week"  # Change if needed
  time: "02:00"                  # Your preferred time

version_discovery:
  channel: "stable"              # stable, fast, or eus
  ocp_version: "latest"          # or specific like "4.16"

kubernetes:
  namespace: "openshift-imageset-mirror"
  storage:
    pvc:
      name: "imageset-mirror-storage"
      size: "500Gi"              # Adjust for your content

notifications:
  enabled: true
  slack:
    enabled: true
    webhook_url: "${SLACK_WEBHOOK_URL}"  # Set environment variable
```

Set environment variables:

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK"
```

## Step 3: Deploy to Kubernetes (5 minutes)

### Quick Deploy (All-in-One)

```bash
# Create namespace
kubectl create namespace openshift-imageset-mirror

# Deploy RBAC, storage, and automation
kubectl apply -f automation/examples/kubernetes-rbac.yaml
kubectl apply -f automation/examples/kubernetes-storage.yaml

# Create secrets
kubectl create secret generic redhat-registry-pull-secret \
  --from-file=.dockerconfigjson=/path/to/pull-secret.json \
  --type=kubernetes.io/dockerconfigjson \
  -n openshift-imageset-mirror

kubectl create secret generic automation-secrets \
  --from-literal=slack-webhook-url="$SLACK_WEBHOOK_URL" \
  -n openshift-imageset-mirror

# Deploy automation
kubectl apply -f automation/examples/kubernetes-deployment.yaml
```

### Verify Deployment

```bash
# Check pod status
kubectl get pods -n openshift-imageset-mirror

# Check logs
kubectl logs -n openshift-imageset-mirror -l app=imageset-automation

# Should see:
# ✓ Automation scheduler initialized and started
# Scheduled for last week: day_of_week=1, time=02:00
```

## Step 4: Test the System

### Manual Trigger (Recommended for First Run)

```bash
# Trigger automation immediately with dry-run
kubectl exec -n openshift-imageset-mirror \
  deploy/imageset-automation -- \
  python -m automation.engine \
  --config /config/config.yaml \
  --dry-run

# Check the output
# Should see version discovery and job creation plan
```

### Check via API (if Flask app is running)

```bash
# Port forward (if needed)
kubectl port-forward -n openshift-imageset-mirror \
  deploy/imageset-automation 5000:5000

# Get status
curl http://localhost:5000/api/automation/status | jq

# Manually trigger
curl -X POST http://localhost:5000/api/automation/trigger
```

## What Happens Next?

1. **Scheduler Waits**: The automation will wait until the configured execution window (e.g., last Tuesday of the month)

2. **Automatic Execution**: When the time comes:
   - Discovers latest OCP version in your channel
   - Generates ImageSetConfiguration
   - Creates Kubernetes Job to run oc-mirror
   - Sends notification when version is selected

3. **Mirroring**: The Kubernetes Job runs oc-mirror:
   - Downloads OCP releases and operators
   - Saves to the PVC (`imageset-mirror-storage`)
   - Can take 2-8 hours depending on content

4. **Completion**: When mirroring finishes:
   - Sends completion notification
   - Records execution in history
   - Updates state file

## Common Adjustments

### Change Schedule

```yaml
# In automation/config.yaml
scheduler:
  execution_window: "second-to-last-week"  # Run earlier in month
  day_of_week: 3  # Wednesday instead of Tuesday
  time: "03:00"   # 3 AM instead of 2 AM
```

### Add More Operators

```yaml
imageset:
  operators:
    packages:
      - cluster-logging
      - local-storage-operator
      - odf-operator
      - advanced-cluster-management
      - openshift-gitops-operator
```

### Adjust Resources

```yaml
kubernetes:
  job:
    resources:
      requests:
        memory: "8Gi"  # More memory for large catalogs
        cpu: "4"       # More CPUs for faster processing
```

### Add Email Notifications

```yaml
notifications:
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    smtp_user: "your-email@gmail.com"
    smtp_password: "${SMTP_PASSWORD}"
    from_address: "your-email@gmail.com"
    to_addresses:
      - "team@example.com"
```

## Monitoring

### Check Schedule

```bash
# View next scheduled runs
kubectl logs -n openshift-imageset-mirror \
  -l app=imageset-automation | grep "Scheduled jobs"
```

### View Execution History

```bash
# From pod
kubectl exec -n openshift-imageset-mirror \
  deploy/imageset-automation -- \
  cat /app/data/automation-history.json | jq

# Via API
curl http://localhost:5000/api/automation/history | jq
```

### Monitor Mirror Jobs

```bash
# List all mirror jobs
kubectl get jobs -n openshift-imageset-mirror -l app=imageset-mirror

# Watch active job
kubectl get jobs -n openshift-imageset-mirror -l app=imageset-mirror -w

# Get job logs (replace JOB_NAME)
kubectl logs -n openshift-imageset-mirror job/JOB_NAME --follow
```

### Check Storage Usage

```bash
# Check PVC size
kubectl get pvc -n openshift-imageset-mirror

# Check actual usage
kubectl exec -n openshift-imageset-mirror \
  deploy/imageset-automation -- \
  df -h /mirror
```

## Troubleshooting

### "Kubernetes manager not available"

```bash
# Install Kubernetes Python client
pip install kubernetes

# Verify kubeconfig
kubectl cluster-info
```

### "Permission denied" on Job creation

```bash
# Verify RBAC
kubectl auth can-i create jobs \
  --as=system:serviceaccount:openshift-imageset-mirror:imageset-mirror-sa \
  -n openshift-imageset-mirror

# If false, reapply RBAC
kubectl apply -f automation/examples/kubernetes-rbac.yaml
```

### "PVC not found"

```bash
# Create PVC
kubectl apply -f automation/examples/kubernetes-storage.yaml

# Verify
kubectl get pvc -n openshift-imageset-mirror
```

### Version discovery fails

```bash
# Test oc-mirror manually
oc-mirror list releases --version 4.16

# Check if oc-mirror is installed
which oc-mirror
```

## Next Steps

1. **Review Full Documentation**: See `automation/README.md` for comprehensive guide
2. **Customize Configuration**: Adjust `automation/config.yaml` to your needs
3. **Set Up Monitoring**: Configure Prometheus/Grafana for job metrics
4. **Test Notifications**: Verify all notification channels work
5. **Plan Maintenance**: Schedule regular cleanup of old jobs

## Support

- Full Documentation: `automation/README.md`
- Configuration Reference: `automation/config.yaml` (inline comments)
- Examples: `automation/examples/` directory
- GitHub Issues: Report problems and request features

## Success Checklist

- [ ] Dependencies installed
- [ ] Configuration file customized
- [ ] Kubernetes namespace created
- [ ] RBAC configured
- [ ] Storage PVCs created
- [ ] Secrets created (pull secret, notification credentials)
- [ ] Automation deployed
- [ ] Dry-run test successful
- [ ] Schedule verified
- [ ] Notifications tested
- [ ] Monitoring set up

Once all items are checked, your automation is ready for production! 🎉
