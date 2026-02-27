import React, { useState, useRef, useEffect } from 'react';
import {
  Card,
  CardTitle,
  CardBody,
  Button,
  Grid,
  GridItem,
  Title,
  Text,
  TextContent,
  Alert,
  Modal,
  ModalVariant,
  Progress,
  ProgressMeasureLocation,
  TextArea,
  Label
} from '@patternfly/react-core';
import SyncAltIcon from '@patternfly/react-icons/dist/esm/icons/sync-alt-icon';
import KeyIcon from '@patternfly/react-icons/dist/esm/icons/key-icon';
import UploadIcon from '@patternfly/react-icons/dist/esm/icons/upload-icon';
import CheckCircleIcon from '@patternfly/react-icons/dist/esm/icons/check-circle-icon';
import SearchIcon from '@patternfly/react-icons/dist/esm/icons/search-icon';

function ResetData() {
  const [isResetting, setIsResetting] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [logMessages, setLogMessages] = useState([]);
  const [progressStep, setProgressStep] = useState(0);
  const [progressTotal, setProgressTotal] = useState(5);
  const [progressDescription, setProgressDescription] = useState('');
  const [resetResult, setResetResult] = useState(null);
  const [resultMessage, setResultMessage] = useState('');
  const logEndRef = useRef(null);

  // Pull secret state
  const [pullSecretText, setPullSecretText] = useState('');
  const [pullSecretStatus, setPullSecretStatus] = useState(null);
  const [isUploadingSecret, setIsUploadingSecret] = useState(false);
  const [secretAlert, setSecretAlert] = useState(null);

  // Check data integrity state
  const [isChecking, setIsChecking] = useState(false);
  const [checkLogMessages, setCheckLogMessages] = useState([]);
  const [checkProgressStep, setCheckProgressStep] = useState(0);
  const [checkProgressTotal, setCheckProgressTotal] = useState(1);
  const [checkProgressDescription, setCheckProgressDescription] = useState('');
  const [checkResult, setCheckResult] = useState(null);
  const [checkResultMessage, setCheckResultMessage] = useState('');
  const [checkFailures, setCheckFailures] = useState([]);
  const checkLogEndRef = useRef(null);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logMessages]);

  useEffect(() => {
    if (checkLogEndRef.current) {
      checkLogEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [checkLogMessages]);

  // Check pull secret status on mount
  useEffect(() => {
    fetch('/api/pull-secret/status')
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          setPullSecretStatus(data);
        }
      })
      .catch(() => {});
  }, []);

  const handleUploadSecret = () => {
    if (!pullSecretText.trim()) {
      setSecretAlert({ variant: 'warning', message: 'Please paste your pull secret JSON first.' });
      return;
    }

    setIsUploadingSecret(true);
    setSecretAlert(null);

    fetch('/api/pull-secret', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pullSecret: pullSecretText })
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          setSecretAlert({ variant: 'success', message: data.message });
          setPullSecretStatus({ configured: true, registries: data.registries, registry_count: data.registries.length });
          setPullSecretText('');
        } else {
          setSecretAlert({ variant: 'danger', message: data.message });
        }
      })
      .catch(err => {
        setSecretAlert({ variant: 'danger', message: `Upload failed: ${err.message}` });
      })
      .finally(() => {
        setIsUploadingSecret(false);
      });
  };

  const handleCheckData = () => {
    setIsChecking(true);
    setCheckLogMessages([]);
    setCheckResult(null);
    setCheckResultMessage('');
    setCheckFailures([]);
    setCheckProgressStep(0);
    setCheckProgressDescription('Starting check...');

    fetch('/api/check', { method: 'POST' })
      .then(response => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function processStream() {
          return reader.read().then(({ done, value }) => {
            if (done) {
              if (buffer.trim()) processCheckSSEMessage(buffer);
              return;
            }
            buffer += decoder.decode(value, { stream: true });
            const messages = buffer.split('\n\n');
            buffer = messages.pop();
            messages.forEach(msg => {
              if (msg.trim()) processCheckSSEMessage(msg);
            });
            return processStream();
          });
        }
        return processStream();
      })
      .catch(err => {
        setCheckLogMessages(prev => [...prev, `Connection error: ${err.message}`]);
        setCheckResult('error');
        setCheckResultMessage(`Connection failed: ${err.message}`);
        setIsChecking(false);
      });
  };

  const processCheckSSEMessage = (rawMessage) => {
    let eventType = 'message';
    let data = '';
    const lines = rawMessage.split('\n');
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.substring(7).trim();
      } else if (line.startsWith('data: ')) {
        data = line.substring(6);
      }
    }
    switch (eventType) {
      case 'log':
        setCheckLogMessages(prev => [...prev, data]);
        break;
      case 'progress':
        try {
          const progress = JSON.parse(data);
          setCheckProgressStep(progress.step);
          setCheckProgressTotal(progress.total);
          setCheckProgressDescription(progress.description);
        } catch (e) { /* ignore */ }
        break;
      case 'complete':
        try {
          const result = JSON.parse(data);
          setCheckResult(result.status === 'success' ? 'success' : result.status === 'warning' ? 'warning' : 'error');
          setCheckResultMessage(result.message);
          setCheckFailures(result.failures || []);
          setCheckLogMessages(prev => [...prev, `\n=== ${result.message} ===`]);
        } catch (e) { /* ignore */ }
        setIsChecking(false);
        break;
      case 'error':
        try {
          const result = JSON.parse(data);
          setCheckResult('error');
          setCheckResultMessage(result.message);
          setCheckFailures(result.failures || []);
          setCheckLogMessages(prev => [...prev, `\nERROR: ${result.message}`]);
        } catch (e) { /* ignore */ }
        setIsChecking(false);
        break;
      default:
        break;
    }
  };

  const processSSEMessage = (rawMessage) => {
    let eventType = 'message';
    let data = '';

    const lines = rawMessage.split('\n');
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.substring(7).trim();
      } else if (line.startsWith('data: ')) {
        data = line.substring(6);
      }
    }

    switch (eventType) {
      case 'log':
        setLogMessages(prev => [...prev, data]);
        break;
      case 'progress':
        try {
          const progress = JSON.parse(data);
          setProgressStep(progress.step);
          setProgressTotal(progress.total);
          setProgressDescription(progress.description);
        } catch (e) { /* ignore parse errors */ }
        break;
      case 'complete':
        try {
          const result = JSON.parse(data);
          setResetResult('success');
          setResultMessage(result.message);
          setLogMessages(prev => [...prev, `\n=== ${result.message} ===`]);
        } catch (e) { /* ignore */ }
        setIsResetting(false);
        break;
      case 'error':
        try {
          const result = JSON.parse(data);
          setResetResult('error');
          setResultMessage(result.message);
          setLogMessages(prev => [...prev, `\nERROR: ${result.message}`]);
        } catch (e) { /* ignore */ }
        setIsResetting(false);
        break;
      default:
        break;
    }
  };

  const handleConfirmReset = () => {
    setIsModalOpen(false);
    setIsResetting(true);
    setLogMessages([]);
    setResetResult(null);
    setResultMessage('');
    setProgressStep(0);
    setProgressDescription('Starting reset...');

    fetch('/api/reset', { method: 'POST' })
      .then(response => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function processStream() {
          return reader.read().then(({ done, value }) => {
            if (done) {
              if (buffer.trim()) {
                processSSEMessage(buffer);
              }
              return;
            }
            buffer += decoder.decode(value, { stream: true });
            const messages = buffer.split('\n\n');
            buffer = messages.pop();
            messages.forEach(msg => {
              if (msg.trim()) processSSEMessage(msg);
            });
            return processStream();
          });
        }
        return processStream();
      })
      .catch(err => {
        setLogMessages(prev => [...prev, `Connection error: ${err.message}`]);
        setResetResult('error');
        setResultMessage(`Connection failed: ${err.message}`);
        setIsResetting(false);
      });
  };

  return (
    <Grid hasGutter>
      {/* Pull Secret Section */}
      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">
              <KeyIcon style={{ marginRight: '0.5rem' }} />
              Pull Secret
            </Title>
          </CardTitle>
          <CardBody>
            <TextContent style={{ marginBottom: '1rem' }}>
              <Text>
                A Red Hat pull secret is required to download operator catalog data.
                Obtain yours from{' '}
                <a href="https://console.redhat.com/openshift/install/pull-secret" target="_blank" rel="noopener noreferrer">
                  console.redhat.com
                </a>.
                Paste the full JSON content below.
              </Text>
            </TextContent>

            {pullSecretStatus && pullSecretStatus.configured && (
              <Alert variant="success" isInline isPlain title={
                <span>
                  <CheckCircleIcon style={{ marginRight: '0.5rem' }} />
                  Pull secret configured with {pullSecretStatus.registry_count} registries
                </span>
              } style={{ marginBottom: '1rem' }}>
                {pullSecretStatus.registries.map(r => (
                  <Label key={r} style={{ marginRight: '0.25rem', marginTop: '0.25rem' }}>{r}</Label>
                ))}
              </Alert>
            )}

            {pullSecretStatus && !pullSecretStatus.configured && (
              <Alert variant="warning" isInline isPlain title="No pull secret configured" style={{ marginBottom: '1rem' }}>
                Operator data refresh will fail without registry credentials.
              </Alert>
            )}

            <TextArea
              value={pullSecretText}
              onChange={(_event, value) => setPullSecretText(value)}
              placeholder='{"auths":{"cloud.openshift.com":{"auth":"..."},"registry.redhat.io":{"auth":"..."}}}'
              aria-label="Pull secret JSON"
              rows={5}
              resizeOrientation="vertical"
              style={{ fontFamily: 'monospace', fontSize: '0.85rem', marginBottom: '1rem' }}
            />

            <Button
              variant="primary"
              icon={<UploadIcon />}
              onClick={handleUploadSecret}
              isDisabled={isUploadingSecret || !pullSecretText.trim()}
              isLoading={isUploadingSecret}
            >
              {isUploadingSecret ? 'Uploading...' : 'Upload Pull Secret'}
            </Button>

            {secretAlert && (
              <Alert
                variant={secretAlert.variant}
                title={secretAlert.message}
                isInline
                style={{ marginTop: '1rem' }}
              />
            )}
          </CardBody>
        </Card>
      </GridItem>

      {/* Check Data Integrity Section */}
      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">
              <SearchIcon style={{ marginRight: '0.5rem' }} />
              Check Data Integrity
            </Title>
          </CardTitle>
          <CardBody>
            <TextContent style={{ marginBottom: '1rem' }}>
              <Text>
                Verify that all cached data files (versions, channels, catalogs, releases,
                and operator lists) load correctly for every version from 4.13 onward.
                Any missing or corrupt files will be automatically redownloaded.
              </Text>
            </TextContent>

            <Button
              variant="secondary"
              icon={<SearchIcon />}
              onClick={handleCheckData}
              isDisabled={isChecking || isResetting}
              isLoading={isChecking}
            >
              {isChecking ? 'Checking...' : 'Check Data Integrity'}
            </Button>
          </CardBody>
        </Card>
      </GridItem>

      {isChecking && (
        <GridItem span={12}>
          <Card>
            <CardBody>
              <Progress
                value={(checkProgressStep / checkProgressTotal) * 100}
                title={checkProgressDescription}
                measureLocation={ProgressMeasureLocation.top}
                label={`Version ${checkProgressStep} of ${checkProgressTotal}`}
                variant={checkProgressStep === checkProgressTotal ? 'success' : undefined}
              />
            </CardBody>
          </Card>
        </GridItem>
      )}

      {checkLogMessages.length > 0 && (
        <GridItem span={12}>
          <Card>
            <CardTitle>
              <Title headingLevel="h3">Check Log</Title>
            </CardTitle>
            <CardBody>
              <div style={{
                backgroundColor: '#1e1e1e',
                color: '#d4d4d4',
                fontFamily: 'monospace',
                fontSize: '0.85rem',
                padding: '1rem',
                borderRadius: '4px',
                maxHeight: '500px',
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all'
              }}>
                {checkLogMessages.map((msg, idx) => (
                  <div key={idx} style={{
                    color: msg.includes('FIXED') ? '#4caf50' :
                           msg.includes('ERROR') ? '#f44336' :
                           msg.includes('MISSING') ? '#ff9800' :
                           msg.includes('OK') ? '#8bc34a' : '#d4d4d4'
                  }}>{msg}</div>
                ))}
                <div ref={checkLogEndRef} />
              </div>
            </CardBody>
          </Card>
        </GridItem>
      )}

      {checkResult && (
        <GridItem span={12}>
          <Alert
            variant={checkResult === 'success' ? 'success' : checkResult === 'warning' ? 'warning' : 'danger'}
            title={checkResult === 'success' ? 'All Checks Passed' : checkResult === 'warning' ? 'Issues Found & Repaired' : 'Check Failed'}
          >
            {checkResultMessage}
            {checkFailures.length > 0 && (
              <div style={{ marginTop: '0.5rem' }}>
                {checkFailures.map((f, idx) => (
                  <div key={idx} style={{ fontSize: '0.9rem' }}>
                    {f.fixed ? '\u2705' : '\u274C'} <strong>{f.version}</strong> — {f.type}: {f.detail}
                  </div>
                ))}
              </div>
            )}
          </Alert>
        </GridItem>
      )}

      {/* Reset Section */}
      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">Reset & Re-download All Data</Title>
          </CardTitle>
          <CardBody>
            <TextContent style={{ marginBottom: '1rem' }}>
              <Text>
                This will delete all cached data files (versions, channels, catalogs, releases,
                and operator lists) and re-download them from scratch for OpenShift versions
                4.13 through the latest available release across all 4 operator catalogs.
              </Text>
              <Text component="small">
                This process may take a significant amount of time depending on network speed.
              </Text>
            </TextContent>

            <Button
              variant="danger"
              icon={<SyncAltIcon />}
              onClick={() => setIsModalOpen(true)}
              isDisabled={isResetting || isChecking}
              isLoading={isResetting}
            >
              {isResetting ? 'Resetting...' : 'Reset All Data'}
            </Button>
          </CardBody>
        </Card>
      </GridItem>

      {isResetting && (
        <GridItem span={12}>
          <Card>
            <CardBody>
              <Progress
                value={(progressStep / progressTotal) * 100}
                title={progressDescription}
                measureLocation={ProgressMeasureLocation.top}
                label={`Step ${progressStep} of ${progressTotal}`}
                variant={progressStep === progressTotal ? 'success' : undefined}
              />
            </CardBody>
          </Card>
        </GridItem>
      )}

      {logMessages.length > 0 && (
        <GridItem span={12}>
          <Card>
            <CardTitle>
              <Title headingLevel="h3">Log Output</Title>
            </CardTitle>
            <CardBody>
              <div style={{
                backgroundColor: '#1e1e1e',
                color: '#d4d4d4',
                fontFamily: 'monospace',
                fontSize: '0.85rem',
                padding: '1rem',
                borderRadius: '4px',
                maxHeight: '500px',
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all'
              }}>
                {logMessages.map((msg, idx) => (
                  <div key={idx}>{msg}</div>
                ))}
                <div ref={logEndRef} />
              </div>
            </CardBody>
          </Card>
        </GridItem>
      )}

      {resetResult && (
        <GridItem span={12}>
          <Alert
            variant={resetResult === 'success' ? 'success' : 'danger'}
            title={resetResult === 'success' ? 'Reset Complete' : 'Reset Failed'}
          >
            {resultMessage}
          </Alert>
        </GridItem>
      )}

      <Modal
        variant={ModalVariant.small}
        title="Confirm Data Reset"
        titleIconVariant="warning"
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        actions={[
          <Button key="confirm" variant="danger" onClick={handleConfirmReset}>
            Yes, Reset All Data
          </Button>,
          <Button key="cancel" variant="link" onClick={() => setIsModalOpen(false)}>
            Cancel
          </Button>
        ]}
      >
        <TextContent>
          <Text>
            <strong>Warning:</strong> This will delete all cached data and re-download
            everything from OpenShift versions 4.13 through the latest release.
          </Text>
          <Text>
            This includes versions, channels, catalogs, releases, and operator lists
            for all 4 catalogs. This process may take a significant amount of time.
          </Text>
          <Text>
            Are you sure you want to proceed?
          </Text>
        </TextContent>
      </Modal>
    </Grid>
  );
}

export default ResetData;
