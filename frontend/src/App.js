

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Page,
  PageSection,
  Title,
  Text,
  TextContent,
  Tabs,
  Tab,
  TabTitleText,
  PageSectionVariants,
  Alert,
  AlertGroup,
  AlertActionCloseButton,
  Button
} from '@patternfly/react-core';
import SyncAltIcon from '@patternfly/react-icons/dist/esm/icons/sync-alt-icon';
import '@patternfly/patternfly/patternfly.css';
import BasicConfig from './components/BasicConfig';
import AdvancedConfig from './components/AdvancedConfig';
import PreviewGenerate from './components/PreviewGenerate';
import StatusBar from './components/StatusBar';
import ResetData from './components/ResetData';

// Utility to deeply sanitize config for JSON serialization
function deepSanitizeConfig(obj) {
  if (Array.isArray(obj)) {
    return obj.map(deepSanitizeConfig);
  } else if (obj && typeof obj === 'object' && obj.constructor === Object) {
    const out = {};
    for (const key in obj) {
      const v = obj[key];
      if (
        typeof v === 'string' ||
        typeof v === 'boolean' ||
        typeof v === 'number' ||
        v === null ||
        v === undefined
      ) {
        out[key] = v;
      } else if (Array.isArray(v) || (v && typeof v === 'object' && v.constructor === Object)) {
        out[key] = deepSanitizeConfig(v);
      } else {
        // skip DOM nodes, functions, etc.
        console.warn('Sanitizing out non-serializable config value:', key, v);
      }
    }
    return out;
  } else {
    return obj;
  }
}

const API_BASE = '';

function App() {
  console.log('App component is initializing...');
  
  const [activeTab, setActiveTab] = useState(0);
  const [config, setConfig] = useState({
    ocp_versions: [],
    ocp_channel: 'stable-4.14',
    ocp_min_version: '',
    ocp_max_version: '',
    operators: [],
    operator_catalogs: [],
    additional_images: [],
    helm_charts: [],
    output_file: 'imageset-config.yaml',
    kubevirt_container: false,
    storageConfig: { registry: '', skipTLS: false }
  });
  const [yamlPreview, setYamlPreview] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [status, setStatus] = useState('Ready');
  const [alertMessage, setAlertMessage] = useState('');
  const [alertVariant, setAlertVariant] = useState('info');
  const [operatorMappings, setOperatorMappings] = useState({});
  const [ocpReleases, setOcpReleases] = useState([]);
  const [ocpChannels, setOcpChannels] = useState([]);
  const [channelReleases, setChannelReleases] = useState([]);
  const [isLoadingReleases, setIsLoadingReleases] = useState(false);
  const [isLoadingChannels, setIsLoadingChannels] = useState(false);
  const [isLoadingChannelReleases, setIsLoadingChannelReleases] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState('');

  const updateConfig = (updates) => {
    // Always create a new array reference for operator_catalogs if present
    if (updates.operator_catalogs) {
      updates.operator_catalogs = [...updates.operator_catalogs];
    }
    // Deep merge for storageConfig to avoid [object Object] bug
    let newConfig;
    if (updates.storageConfig) {
      // Remove any non-serializable fields from storageConfig
      const safeStorageConfig = {};
      for (const key in updates.storageConfig) {
        const v = updates.storageConfig[key];
        if (typeof v === 'string' || typeof v === 'boolean' || typeof v === 'number' || v === null || v === undefined) {
          safeStorageConfig[key] = v;
        } else {
          // Defensive: skip objects, functions, DOM nodes, etc.
          console.warn('Skipped non-serializable storageConfig value:', key, v);
        }
      }
      newConfig = {
        ...config,
        ...updates,
        storageConfig: {
          ...config.storageConfig,
          ...safeStorageConfig
        }
      };
    } else {
      newConfig = { ...config, ...updates };
    }
    console.log('Config updated:', newConfig);
  setConfig(newConfig);
  // Force re-render for debugging
  setTimeout(() => setConfig(c => ({ ...c })), 10);
  };

  const fetchReleasesForChannelAndVersion = async (channel) => {
    // Extract the version from the current channel (e.g., "stable-4.14" → "4.14")
    const version = channel.split('-')[1] || config.ocp_channel.split('-')[1];
    console.log(`Fetching releases for channel: ${channel}, version: ${version}`);

    if (!channel || !version) return;
    setIsLoadingChannelReleases(true);
    try {
      const response = await axios.get(`${API_BASE}/api/releases/${version}/${channel}`);
      if (response.data.status === 'success') {
        console.log(`Releases for ${channel}:`, response.data.releases);
        setChannelReleases(response.data.releases);
      } else {
        console.error('Failed to fetch releases:', response.data.message);
        setChannelReleases([]);
      }
    } catch (error) {
      console.error('Failed to load releases:', error);
      setChannelReleases([]);
    } finally {
      setIsLoadingChannelReleases(false);
    }
  };
  
  const fetchChannelsForVersion = async (version) => {
    if (!version) return;
    setIsLoadingChannels(true);
    try {
      const response = await axios.get(`${API_BASE}/api/channels/${version}`);
      if (response.data.status === 'success') {
        setOcpChannels(response.data.channels);
      }
    } catch (error) {
      console.error('Failed to load channels:', error);
      setOcpChannels([`stable-${version}`, `fast-${version}`, `candidate-${version}`]);
    } finally {
      setIsLoadingChannels(false);
    }
  };

  const generatePreview = async () => {
    setIsGenerating(true);
    setStatus('Generating preview...');
    setAlertMessage('');
    // Deep sanitize config before JSON.stringify
    const safeConfig = deepSanitizeConfig(config);
    try {
      const response = await axios.post(`${API_BASE}/api/generate/preview`, safeConfig);
      setYamlPreview(response.data.yaml);
      setStatus('Preview generated successfully');
      setAlertMessage('YAML preview generated successfully');
      setAlertVariant('success');
    } catch (error) {
      console.error('Failed to generate preview:', error);
      const errorMsg = 'Error generating preview: ' + (error.response?.data?.error || error.message);
      setStatus(errorMsg);
      setAlertMessage(errorMsg);
      setAlertVariant('danger');
      setYamlPreview('');
    } finally {
      setIsGenerating(false);
    }
  };

  const downloadConfig = async () => {
    try {
      setStatus('Generating configuration file...');
      setAlertMessage('');
      // Deep sanitize config before JSON.stringify
      const safeConfig = deepSanitizeConfig(config);
      const response = await axios.post(`${API_BASE}/api/generate/download`, safeConfig, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = config.output_file || 'imageset-config.yaml';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      setStatus('Configuration file downloaded successfully');
      setAlertMessage('Configuration file downloaded successfully');
      setAlertVariant('success');
    } catch (error) {
      console.error('Failed to download config:', error);
      const errorMsg = 'Error downloading configuration: ' + (error.response?.data?.error || error.message);
      setStatus(errorMsg);
      setAlertMessage(errorMsg);
      setAlertVariant('danger');
    }
  };

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    setRefreshStatus('Refreshing all static data...');
    try {
      const resp = await axios.post('/api/refresh/all');
      setRefreshStatus(resp.data.message || 'Refresh complete!');
    } catch (err) {
      setRefreshStatus('Refresh failed: ' + (err.response?.data?.error || err.message));
    }
    setIsRefreshing(false);
  };

  useEffect(() => {
    const loadData = async () => {
      setIsLoadingReleases(true);
      try {
        const [mappingsResponse, releasesResponse] = await Promise.all([
          axios.get(`${API_BASE}/api/operators/mappings`),
          axios.get(`${API_BASE}/api/versions`)
        ]);
        setOperatorMappings(mappingsResponse.data.mappings);
        if (releasesResponse.data.status === 'success') {
          // Ensure releases is always an array
          const releases = Array.isArray(releasesResponse.data.releases) ? releasesResponse.data.releases : [];
          setOcpReleases(releases);
        }
      } catch (error) {
        console.error('Failed to load data:', error);
        setOcpReleases(['4.14', '4.15', '4.16', '4.17', '4.18']);
      } finally {
        setIsLoadingReleases(false);
      }
    };
    loadData();
  }, []);

  return (
    <Page>
      <PageSection variant={PageSectionVariants.darker}>
        <TextContent>
          <Title headingLevel="h1" size="2xl">
            OpenShift ImageSetConfiguration Generator
          </Title>
          <Text>
            Generate ImageSetConfiguration files for OpenShift disconnected installations
          </Text>
        </TextContent>
      </PageSection>

      {alertMessage && (
        <PageSection>
          <AlertGroup>
            <Alert
              variant={alertVariant}
              title={alertMessage}
              actionClose={
                <AlertActionCloseButton onClose={() => setAlertMessage('')} />
              }
            />
          </AlertGroup>
        </PageSection>
      )}

      {/* <PageSection>
        <Button
          variant="secondary"
          icon={<SyncAltIcon />}
          isLoading={isRefreshing}
          isDisabled={isRefreshing}
          onClick={handleRefreshAll}
          style={{ marginBottom: '1rem' }}
        >
          Refresh All Data
        </Button>
        {refreshStatus && <div style={{ marginBottom: '1rem' }}>{refreshStatus}</div>}
      </PageSection> */}

      <PageSection>
        <Tabs
          activeKey={activeTab}
          onSelect={(event, tabIndex) => setActiveTab(tabIndex)}
        >
          <Tab eventKey={0} title={<TabTitleText>Basic Configuration</TabTitleText>}>
            <BasicConfig
              config={config}
              updateConfig={updateConfig}
              operatorMappings={operatorMappings}
              ocpReleases={ocpReleases}
              ocpChannels={ocpChannels}
              channelReleases={channelReleases}
              onVersionChange={fetchChannelsForVersion}
              onChannelChange={fetchReleasesForChannelAndVersion}
              isLoadingReleases={isLoadingReleases}
              isLoadingChannels={isLoadingChannels}
              isLoadingChannelReleases={isLoadingChannelReleases}
            />
          </Tab>

          <Tab eventKey={1} title={<TabTitleText>Advanced Configuration</TabTitleText>}>
            <AdvancedConfig
              config={config}
              updateConfig={updateConfig}
            />
          </Tab>

          <Tab eventKey={2} title={<TabTitleText>Preview & Generate</TabTitleText>}>
            <PreviewGenerate
              config={config}
              yamlPreview={yamlPreview}
              isGenerating={isGenerating}
              onGeneratePreview={generatePreview}
              onDownloadConfig={downloadConfig}
            />
          </Tab>

          <Tab eventKey={3} title={<TabTitleText>Reset</TabTitleText>}>
            <ResetData />
          </Tab>
        </Tabs>
      </PageSection>

      <StatusBar status={status} />
    </Page>
  );
}

export default App;
