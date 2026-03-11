import React, { useState, useEffect, useRef } from 'react';
import {
  Card, CardTitle, CardBody,
  Form, FormGroup,
  TextInput,
  Checkbox,
  Select, SelectOption, SelectVariant,
  FormSelect, FormSelectOption,
  Title,
  HelperText, HelperTextItem,
  Spinner,
  Divider,
  Grid, GridItem
} from '@patternfly/react-core';
import OperatorSearch from './OperatorSearch';

function BasicConfig({ config, updateConfig, operatorMappings, ocpReleases, ocpChannels, channelReleases, onVersionChange, onChannelChange, isLoadingReleases, isLoadingChannels, isLoadingChannelReleases }) {
  // State for operator catalogs
  const [availableCatalogs, setAvailableCatalogs] = useState([]);
  const [isLoadingCatalogs, setIsLoadingCatalogs] = useState(false);

  // Fetch available catalogs when OCP version changes
  const fetchCatalogsForVersion = async (version) => {
    if (!version) {
      setAvailableCatalogs([]);
      return;
    }
    setIsLoadingCatalogs(true);
    try {
      const response = await fetch(`/api/operators/catalogs/${version}/list`);
      const data = await response.json();
      let catalogs = [];
      if (data.status === 'success') {
        if (Array.isArray(data.catalogs)) {
          catalogs = data.catalogs;
          console.log('Fetched catalogs (array):', catalogs);
        } else if (data.catalogs && typeof data.catalogs === 'object') {
          // Flatten all values into a single array
          catalogs = Object.values(data.catalogs).flat();
        }
        setAvailableCatalogs(catalogs);
  // Do not auto-select default catalogs; allow user to fully deselect all catalogs
      } else {
        console.error('Failed to fetch catalogs:', data.message);
        setAvailableCatalogs([]);
      }
    } catch (error) {
      console.error('Error fetching catalogs:', error);
      setAvailableCatalogs([]);
    } finally {
      setIsLoadingCatalogs(false);
    }
  };

  // Helper to check if a string is a valid URL (for registry URLs, allow without protocol)
  const isValidCatalogUrl = (url) => {
    if (typeof url !== 'string' || !url.trim()) return false;
    // Accept registry URLs like registry.redhat.io/... optionally with :vX.XX
    return /^registry\.[\w.-]+\/[\w.-]+\/[\w.-]+(-index)?(:v\d+\.\d+)?$/.test(url.trim());
  };

  // Handle catalog selection changes
  const handleCatalogSelectionChange = (selection, isSelected) => {
    const currentCatalogs = Array.isArray(config.operator_catalogs) ? config.operator_catalogs.filter(isValidCatalogUrl) : [];
    let newCatalogs;
    if (isSelected) {
      if (isValidCatalogUrl(selection)) {
        newCatalogs = Array.from(new Set([...currentCatalogs, selection.trim()]));
      } else {
        console.warn('Attempted to add invalid catalog URL:', selection);
        newCatalogs = [...currentCatalogs];
      }
    } else {
      newCatalogs = currentCatalogs.filter(catalog => catalog !== selection);
    }
    // Always update config, even if newCatalogs is empty (allow full deselect)
    if (!Array.isArray(newCatalogs)) newCatalogs = [];
    console.log('Catalog selection changed, sending:', newCatalogs);
    // If all catalogs are deselected, also clear selected operators to reset OperatorSearch
    if (newCatalogs.length === 0) {
      updateConfig({ operator_catalogs: [], operators: [] });
    } else {
      updateConfig({ operator_catalogs: [...newCatalogs] });
    }
  };

  const handleOcpVersionsChange = (e) => {
    const selectedOptions = Array.from(e.target.selectedOptions);
    const versions = selectedOptions.map(option => option.value);
    updateConfig({ ocp_versions: versions });
  };

  // Track last selected version to allow re-selecting the same version
  const lastSelectedVersion = useRef('');
  const handleSingleOcpVersionChange = (_event, selectedValue) => {
    // Always update config, even if the same version is selected again
    updateConfig({ ocp_versions: selectedValue ? [selectedValue] : [] });
    lastSelectedVersion.current = selectedValue;
    if (onVersionChange && selectedValue) {
      onVersionChange(selectedValue);
    }
    if (selectedValue) {
      fetchCatalogsForVersion(selectedValue);
    }
  };

  // If ocpReleases changes and the selected version is no longer present, reset selection
  useEffect(() => {
    if (Array.isArray(ocpReleases) && config.ocp_versions && config.ocp_versions[0]) {
      if (!ocpReleases.includes(config.ocp_versions[0])) {
        updateConfig({ ocp_versions: [] });
      }
    }
  }, [ocpReleases]);

  const handleChannelChange = (_event, selectedValue) => {
    updateConfig({
      ocp_channel: selectedValue,
      ocp_min_version: '', // Reset min/max when channel changes
      ocp_max_version: ''
    });
    
    // Fetch releases for the selected channel
    if (onChannelChange && selectedValue) {
      console.log(`Fetching releases for channel: ${selectedValue}`);
      onChannelChange(selectedValue);
    }
  };

  const handleMinVersionChange = (_event, selectedValue) => {
    updateConfig({ ocp_min_version: selectedValue });
  };

  const handleMaxVersionChange = (_event, selectedValue) => {
    updateConfig({ ocp_max_version: selectedValue });
  };

  // New handler for modern operator objects with channels
  const handleModernOperatorsChange = (operators) => {
    updateConfig({ operators });
  };

  return (
    <Grid hasGutter>
      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">OpenShift Platform Versions</Title>
          </CardTitle>
          <CardBody>
            <Form>
              <FormGroup
                label="Primary OCP Version"
                fieldId="ocp-version-single"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      Select the primary OpenShift version for your deployment
                    </HelperTextItem>
                  </HelperText>
                }
                labelIcon={isLoadingReleases && <Spinner size="sm" />}
              >
                <FormSelect
                  value={config.ocp_versions?.[0] || ''}
                  onChange={handleSingleOcpVersionChange}
                  id="ocp-version-single"
                  isDisabled={isLoadingReleases}
                >
                  <FormSelectOption
                    value=""
                    label={isLoadingReleases ? 'Loading releases...' : 'Select a version...'}
                  />
                  {Array.isArray(ocpReleases) ? ocpReleases.slice().reverse().map(version => (
                    <FormSelectOption key={version} value={version} label={version} />
                  )) : null}
                </FormSelect>
              </FormGroup>

              <FormGroup
                label="OCP Channel"
                fieldId="ocp-channel"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      {config.ocp_versions?.[0] && ocpChannels.length > 0 && !isLoadingChannels
                        ? `${ocpChannels.length} channels available for version ${config.ocp_versions[0]}`
                        : isLoadingChannels
                          ? 'Loading channels for selected version...'
                          : 'Channels will be loaded when you select a version above'}
                    </HelperTextItem>
                  </HelperText>
                }
                labelIcon={isLoadingChannels && <Spinner size="sm" />}
              >
                <FormSelect
                  value={config.ocp_channel || ''}
                  onChange={handleChannelChange}
                  id="ocp-channel"
                  isDisabled={!config.ocp_versions?.[0] || isLoadingChannels}
                >
                  <FormSelectOption
                    value=""
                    label={
                      !config.ocp_versions?.[0] 
                        ? 'Select a version first...' 
                        : isLoadingChannels
                          ? 'Loading channels...'
                          : ocpChannels.length === 0 
                            ? 'No channels available' 
                            : 'Select a channel...'
                    }
                  />
                  {Array.isArray(ocpChannels) ? ocpChannels.map(channel => (
                    <FormSelectOption key={channel} value={channel} label={channel} />
                  )) : null}
                </FormSelect>
              </FormGroup>

              <FormGroup
                label="Minimum Release Version"
                fieldId="ocp-min-version"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      {config.ocp_channel && (channelReleases || []).length > 0 && !isLoadingChannelReleases
                        ? `${(channelReleases || []).length} releases available for channel ${config.ocp_channel}`
                        : isLoadingChannelReleases
                          ? 'Loading releases for selected channel...'
                          : 'Releases will be loaded when you select a channel above'}
                    </HelperTextItem>
                  </HelperText>
                }
                labelIcon={isLoadingChannelReleases && <Spinner size="sm" />}
              >
                <FormSelect
                  value={config.ocp_min_version || ''}
                  onChange={handleMinVersionChange}
                  id="ocp-min-version"
                  isDisabled={!config.ocp_channel || isLoadingChannelReleases || (channelReleases || []).length === 0}
                >
                  <FormSelectOption
                    value=""
                    label={
                      !config.ocp_channel 
                        ? 'Select a channel first...' 
                        : isLoadingChannelReleases
                          ? 'Loading releases...'
                          : (channelReleases || []).length === 0 
                            ? 'No releases available' 
                            : 'Select minimum version...'
                    }
                  />
                  {Array.isArray(channelReleases) ? channelReleases.map(release => (
                    <FormSelectOption key={release} value={release} label={release} />
                  )) : null}
                </FormSelect>
              </FormGroup>

              <FormGroup
                label="Maximum Release Version"
                fieldId="ocp-max-version"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      Optional: Leave empty to mirror all releases from minimum version onwards
                    </HelperTextItem>
                  </HelperText>
                }
                labelIcon={isLoadingChannelReleases && <Spinner size="sm" />}
              >
                <FormSelect
                  value={config.ocp_max_version || ''}
                  onChange={handleMaxVersionChange}
                  id="ocp-max-version"
                  isDisabled={!config.ocp_channel || isLoadingChannelReleases || (channelReleases || []).length === 0}
                >
                  <FormSelectOption
                    value=""
                    label={
                      !config.ocp_channel 
                        ? 'Select a channel first...' 
                        : isLoadingChannelReleases
                          ? 'Loading releases...'
                          : (channelReleases || []).length === 0 
                            ? 'No releases available' 
                            : 'Select maximum version...'
                    }
                  />
                  {Array.isArray(channelReleases) ? channelReleases.map(release => (
                    <FormSelectOption key={release} value={release} label={release} />
                  )) : null}
                </FormSelect>
              </FormGroup>
            </Form>
          </CardBody>
        </Card>
      </GridItem>

      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">Operator Catalogs</Title>
          </CardTitle>
          <CardBody>
            <Form>
              <FormGroup
                label="Operator Catalogs"
                fieldId="operator-catalogs"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      Select one or more operator catalogs based on your OCP version. You may deselect all catalogs if desired.
                    </HelperTextItem>
                  </HelperText>
                }
              >
                {isLoadingCatalogs ? (
                  <Spinner size="md" />
                ) : (
                  <div>
                    {availableCatalogs.length > 0 ? (
                      <div>
                        {availableCatalogs.map((catalog, index) => (
                          <div key={index} style={{ marginBottom: '0.5rem' }}>
                            <Checkbox
                              label={
                                <div>
                                  <strong>
                                    {catalog.name}
                                    {catalog.validated && (
                                      <span style={{ color: 'var(--pf-global--success-color--100)', marginLeft: '0.5rem' }}>
                                        ✓
                                      </span>
                                    )}
                                    {!catalog.validated && catalog.error && (
                                      <span style={{ color: 'var(--pf-global--warning-color--100)', marginLeft: '0.5rem' }}>
                                        ⚠
                                      </span>
                                    )}
                                  </strong>
                                  {catalog.operators_count > 0 && (
                                    <span style={{ color: 'var(--pf-global--info-color--100)', marginLeft: '0.5rem', fontSize: '0.8em' }}>
                                      ({catalog.operators_count} operators)
                                    </span>
                                  )}
                                  <br />
                                  <small style={{ color: 'var(--pf-global--Color--200)' }}>
                                    {catalog.url}
                                  </small>
                                  <br />
                                  <small style={{ fontStyle: 'italic' }}>
                                    {catalog.description}
                                    {catalog.error && (
                                      <span style={{ color: 'var(--pf-global--warning-color--100)' }}>
                                        {' '}- {catalog.error}
                                      </span>
                                    )}
                                  </small>
                                </div>
                              }
                              isChecked={(config.operator_catalogs || []).includes(catalog.url)}
                              onChange={(_event, checked) => handleCatalogSelectionChange(catalog.url, checked)}
                              id={`catalog-${index}`}
                            />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <TextInput
                        value={(config.operator_catalogs || []).filter(isValidCatalogUrl).join(', ')}
                        onChange={(_event, value) => {
                          const catalogs = value
                            .split(',')
                            .map(c => c.trim())
                            .filter(isValidCatalogUrl);
                          const invalids = value
                            .split(',')
                            .map(c => c.trim())
                            .filter(c => c && !isValidCatalogUrl(c));
                          if (invalids.length > 0) {
                            console.warn('Ignored invalid catalog URLs:', invalids);
                          }
                          updateConfig({ operator_catalogs: catalogs });
                        }}
                        id="operator-catalogs-manual"
                        placeholder="registry.redhat.io/redhat/redhat-operator-index:v4.18"
                        helperText="Enter comma-separated catalog URLs"
                      />
                    )}
                  </div>
                )}
              </FormGroup>
            </Form>
          </CardBody>
        </Card>
      </GridItem>


      <GridItem span={12}>
        <OperatorSearch 
          key={(config.operator_catalogs || []).join(',') + (config.ocp_versions?.[0] || '')}
          selectedOperators={config.operators || []}
          onOperatorsChange={handleModernOperatorsChange}
          selectedCatalogs={config.operator_catalogs || []}
          selectedVersion={config.ocp_versions?.[0] || ''}
        />
      </GridItem>


  {/* Output Configuration card removed as requested */}
    </Grid>
  );
}

export default BasicConfig;
