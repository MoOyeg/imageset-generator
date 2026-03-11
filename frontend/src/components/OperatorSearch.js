import React, { useState, useEffect, useCallback } from 'react';
import { Slider, Tooltip } from '@patternfly/react-core';
import {
  Card,
  CardTitle,
  CardBody,
  Form,
  FormGroup,
  TextInput,
  Button,
  Grid,
  GridItem,
  Select,
  SelectOption,
  Spinner,
  Alert,
  Title,
  Text,
  Divider,
  Badge
} from '@patternfly/react-core';
import { SearchIcon, TimesIcon, LinkIcon } from '@patternfly/react-icons';

function OperatorSearch({
  selectedOperators,
  onOperatorsChange,
  selectedCatalogs,
  selectedVersion
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [availableOperators, setAvailableOperators] = useState([]);
  const [filteredOperators, setFilteredOperators] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [isChannelSelectOpen, setIsChannelSelectOpen] = useState({});
  const [operatorChannels, setOperatorChannels] = useState({});
  const [operatorLimit] = useState(25);
  const [page, setPage] = useState(0);
  // For each operator, store [minIndex, maxIndex] for the version range slider
  const [selectedVersionRangeByName, setSelectedVersionRangeByName] = useState({});
  // Dependency resolution alerts
  const [dependencyAlerts, setDependencyAlerts] = useState([]);
  const [isResolvingDeps, setIsResolvingDeps] = useState(false);

  // Reset local state when catalogs or version change (via key prop)
  useEffect(() => {
    setSearchTerm('');
    setAvailableOperators([]);
    setFilteredOperators([]);
    setIsLoading(false);
    setError('');
    setIsChannelSelectOpen({});
    setOperatorChannels({});
    setSelectedVersionRangeByName({});
    setPage(0);
    setDependencyAlerts([]);
    setIsResolvingDeps(false);
  }, [selectedCatalogs, selectedVersion]);

  // Define fetchOperators function FIRST before any useEffect that uses it
  const fetchOperators = useCallback(async () => {
    if (!selectedVersion || !selectedCatalogs || selectedCatalogs.length === 0) {
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      // Fetch from all selected catalogs in parallel
      const fetches = selectedCatalogs.map(catalog =>
        fetch(`/api/operators/list?catalog=${encodeURIComponent(catalog)}&version=${encodeURIComponent(selectedVersion)}`)
          .then(res => res.json().catch(() => ({ status: 'error', message: 'Invalid JSON' })))
          .then(data => ({ catalog, data }))
      );
      const results = await Promise.all(fetches);
      // Merge and deduplicate operators by unique name+version+channel
      const allOperators = [];
      const seen = new Set();
      results.forEach(({ catalog, data }) => {
        if (data.status === 'success' && Array.isArray(data.operators)) {
          data.operators.forEach(op => {
            const key = `${op.name}|${op.version}|${op.channel}`;
            if (!seen.has(key)) {
              seen.add(key);
              allOperators.push({ ...op, catalog });
            }
          });
        }
      });
      setAvailableOperators(allOperators);
      // If all failed, show error
      if (allOperators.length === 0 && results.some(r => r.data.status !== 'success')) {
        setError(results.map(r => r.data.message).filter(Boolean).join('; ') || 'Failed to fetch operators');
      }
    } catch (err) {
      console.error('Error fetching operators:', err);
      setError('Failed to fetch operators');
      setAvailableOperators([]);
    } finally {
      setIsLoading(false);
    }
  }, [selectedVersion, selectedCatalogs]);

  useEffect(() => {
    if (selectedCatalogs && selectedCatalogs.length > 0 && selectedVersion) {
      fetchOperators();
    }
  }, [selectedCatalogs, selectedVersion, fetchOperators]);

  // Aggregate operators by base name (before first dot), collect all versions for each base name
  useEffect(() => {
    let filtered = availableOperators;
    if (searchTerm.trim() !== '') {
      const lowerSearch = searchTerm.toLowerCase();
      filtered = availableOperators.filter(op => {
        // Name or display name match
        if (op.name && op.name.toLowerCase().includes(lowerSearch)) return true;
        if (op.display_name && op.display_name.toLowerCase().includes(lowerSearch)) return true;
        // Keyword match (array of strings)
        if (Array.isArray(op.keywords)) {
          for (const kw of op.keywords) {
            if (typeof kw === 'string' && kw.toLowerCase().includes(lowerSearch)) {
              return true;
            }
          }
        }
        return false;
      });
    }
    // Aggregate by base name (before first dot)
    const agg = {};
    filtered.forEach(op => {
      // Extract base name (before first dot)
      const baseName = op.name.split('.')[0];
      const version = op.version || (op.name.split('.').slice(1).join('.') || op.name);
      if (!agg[baseName]) {
        agg[baseName] = {
          ...op,
          name: baseName,
          versions: version ? [version] : [],
          versionCatalogMap: version ? { [version]: op.catalog } : {},
          allOps: [op]
        };
      } else {
        if (version && !agg[baseName].versions.includes(version)) {
          agg[baseName].versions.push(version);
        }
        if (version) {
          agg[baseName].versionCatalogMap[version] = op.catalog;
        }
        agg[baseName].allOps.push(op);
      }
    });
    // Sort versions descending (newest first, by string)
    Object.values(agg).forEach(entry => {
      entry.versions = entry.versions.filter(Boolean).sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
    });
    setFilteredOperators(Object.values(agg));
    setPage(0); // Reset to first page on filter change
  }, [searchTerm, availableOperators]);

  // Resolve dependencies for an operator after it's been added
  const resolveDependencies = useCallback(async (operatorName, catalog, currentOperators) => {
    if (!selectedVersion || !selectedCatalogs || selectedCatalogs.length === 0) return;

    setIsResolvingDeps(true);
    try {
      const params = new URLSearchParams({
        catalog: catalog || selectedCatalogs[0] || '',
        version: selectedVersion,
        all_catalogs: (selectedCatalogs || []).join(',')
      });
      const resp = await fetch(`/api/operators/${encodeURIComponent(operatorName)}/dependencies?${params}`);
      const data = await resp.json();

      if (data.status !== 'success') return;

      const depOperators = [];
      const newAlerts = [];

      // Process resolved dependencies
      if (data.dependencies && data.dependencies.length > 0) {
        const addedNames = [];
        for (const dep of data.dependencies) {
          // Skip if already selected
          if (currentOperators.some(op => op.name === dep.package)) continue;

          // Try to find the dep in available operators for display info
          const depInfo = availableOperators.find(
            op => op.name === dep.package || op.package === dep.package
          );
          depOperators.push({
            name: dep.package,
            display_name: depInfo?.display_name || dep.package,
            channel: depInfo?.channel || 'stable',
            catalog: depInfo?.catalog || catalog,
            isDependency: true,
            dependencyOf: operatorName
          });
          const label = dep.type === 'gvk'
            ? `${dep.package} (provides ${dep.gvk})`
            : `${dep.package}${dep.versionRange ? ' ' + dep.versionRange : ''}`;
          addedNames.push(label);
        }
        if (addedNames.length > 0) {
          newAlerts.push({
            variant: 'info',
            title: `Auto-selected ${addedNames.length} dependenc${addedNames.length === 1 ? 'y' : 'ies'} for "${operatorName}"`,
            message: addedNames.join(', ')
          });
        }
      }

      // Process unresolved dependencies
      if (data.unresolved && data.unresolved.length > 0) {
        const descs = data.unresolved.map(u => `${u.kind} (${u.group}/${u.version})`);
        newAlerts.push({
          variant: 'danger',
          title: `Could not find provider${data.unresolved.length > 1 ? 's' : ''} for dependenc${data.unresolved.length === 1 ? 'y' : 'ies'} of "${operatorName}"`,
          message: `Missing API/CRD providers: ${descs.join(', ')}. You may need to manually add the operator that provides ${data.unresolved.length === 1 ? 'this API' : 'these APIs'}.`
        });
      }

      if (depOperators.length > 0) {
        onOperatorsChange([...currentOperators, ...depOperators]);
      }
      if (newAlerts.length > 0) {
        setDependencyAlerts(prev => [...prev, ...newAlerts]);
      }
    } catch (err) {
      console.error('Error resolving dependencies:', err);
    } finally {
      setIsResolvingDeps(false);
    }
  }, [selectedVersion, selectedCatalogs, availableOperators, onOperatorsChange]);


  const addOperator = (operator, minVersion, maxVersion) => {
    // Find the catalog for the selected minVersion (for display)
    let catalog = undefined;
    if (operator.versionCatalogMap && minVersion) {
      catalog = operator.versionCatalogMap[minVersion];
    } else if (operator.catalog) {
      catalog = operator.catalog;
    }
    // Always include minVersion/maxVersion for all operators
    const versions = operator.versions || [];
    const newOperator = {
      name: operator.name,
      display_name: operator.display_name,
      channel: operator.channel || 'stable',
      catalog: catalog,
      minVersion: minVersion,
      maxVersion: maxVersion
    };
    const updatedOperators = [...(selectedOperators || []), newOperator];
    onOperatorsChange(updatedOperators);

    // Resolve dependencies asynchronously
    resolveDependencies(operator.name, catalog, updatedOperators);
  };

  const removeOperator = (operatorName) => {
    const updatedOperators = (selectedOperators || []).filter(op => op.name !== operatorName);
    onOperatorsChange(updatedOperators);
    // Clear dependency alerts related to this operator
    setDependencyAlerts(prev => prev.filter(a => !a.title.includes(`"${operatorName}"`)));
  };

  const dismissDependencyAlert = (index) => {
    setDependencyAlerts(prev => prev.filter((_, i) => i !== index));
  };

  const isOperatorSelected = (operatorName, minVersion, maxVersion) => {
    return (selectedOperators || []).some(op => op.name === operatorName && String(op.minVersion) === String(minVersion) && String(op.maxVersion) === String(maxVersion));
  };

  if (!selectedCatalogs || selectedCatalogs.length === 0) {
    return (
      <Card>
        <CardTitle>Operator Search</CardTitle>
        <CardBody>
          <Alert variant="info" title="No catalogs selected">
            Please select one or more operator catalogs to search for operators.
          </Alert>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardTitle>
        <Title headingLevel="h3" size="lg">
          Operator Search
        </Title>
        <Text component="small">
          Search and select operators from {selectedCatalogs.join(', ')} catalog(s)
        </Text>
      </CardTitle>
      <CardBody>
        <Form>
          <FormGroup label="Search Operators" fieldId="operator-search">
            <TextInput
              type="text"
              id="operator-search"
              value={searchTerm}
              onChange={(event, value) => setSearchTerm(value)}
              placeholder="Search operators by name..."
            />
          </FormGroup>

          {error && (
            <Alert variant="danger" title="Error loading operators">
              {error}
              <div style={{ marginTop: '8px' }}>
                <Button variant="link" onClick={fetchOperators}>
                  Retry
                </Button>
              </div>
            </Alert>
          )}

          {isLoading && (
            <div style={{ textAlign: 'center', margin: '16px 0' }}>
              <Spinner size="lg" />
              <div style={{ marginTop: '8px' }}>Loading operators...</div>
            </div>
          )}

          {!isLoading && filteredOperators.length === 0 && !error && (
            <Alert variant="info" title="No operators found">
              {availableOperators.length === 0
                ? "No operators available in the selected catalog(s)."
                : searchTerm
                  ? `No operators match "${searchTerm}". Try a different search term.`
                  : "No operators to display."
              }
            </Alert>
          )}

          {!isLoading && filteredOperators.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                <Title headingLevel="h4" size="md" style={{ marginBottom: 0, marginRight: '16px' }}>
                  Available Operators (Page {page + 1} of {Math.ceil(filteredOperators.length / operatorLimit)})
                </Title>
                <span style={{ marginLeft: 'auto', fontSize: '0.95em' }}>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    isDisabled={page === 0}
                    style={{ marginRight: 8 }}
                  >
                    Back
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPage(p => Math.min(Math.ceil(filteredOperators.length / operatorLimit) - 1, p + 1))}
                    isDisabled={page >= Math.ceil(filteredOperators.length / operatorLimit) - 1}
                  >
                    Next
                  </Button>
                </span>
              </div>
              <Grid hasGutter>
                {filteredOperators.slice(page * operatorLimit, (page + 1) * operatorLimit).map((operator) => {
                  const versions = operator.versions || [];
                  // Default minVersion to 0 (latest in reversed slider), maxVersion to 0 (oldest in reversed slider) if not set
                  let range = selectedVersionRangeByName[operator.name];
                  if (!range) {
                    range = [versions.length - 1, 0];
                  }
                  const minVersion = versions[range[0]];
                  const maxVersion = versions[range[1]];
                  // Only show catalog for minVersion
                  const catalogForVersion = operator.versionCatalogMap && minVersion ? operator.versionCatalogMap[minVersion] : undefined;
                  return (
                    <GridItem span={12} md={6} lg={4} key={operator.name}>
                      <Card>
                        <CardBody>
                          <Title headingLevel="h5" size="sm">
                            {operator.display_name || operator.name}
                          </Title>
                          {catalogForVersion ? (
                            <Text component="small" style={{ color: '#0088cc', fontWeight: 500 }}>
                              Catalog: {catalogForVersion}
                            </Text>
                          ) : null}
                          {operator.description && (
                            <Text component="p" style={{ marginTop: '8px', fontSize: '14px' }}>
                              {operator.description.length > 100
                                ? `${operator.description.substring(0, 100)}...`
                                : operator.description
                              }
                            </Text>
                          )}
                          {versions.length > 1 && (
                            <div style={{ marginTop: '12px', marginBottom: '8px' }}>
                              <span style={{ fontWeight: 500 }}>Version Range:&nbsp;</span>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <Tooltip content={`Minimum version: ${minVersion}`} position="top">
                                  <div style={{ width: 120 }}>
                                    <Slider
                                      min={0}
                                      max={versions.length - 1}
                                      value={versions.length - 1 - range[0]}
                                      onChange={(_e, v) => {
                                        setSelectedVersionRangeByName(prev => ({ ...prev, [operator.name]: [versions.length - 1 - v, range[1]] }));
                                      }}
                                      showTicks
                                      step={1}
                                      aria-label={`Select minimum version for ${operator.name}`}
                                      marks={versions.slice().reverse().map((ver, idx) => ({ value: idx, label: ver }))}
                                    />
                                  </div>
                                </Tooltip>
                                <span style={{ fontWeight: 500, fontSize: 18 }}>–</span>
                                <Tooltip content={`Maximum version: ${maxVersion}`} position="top">
                                  <div style={{ width: 120 }}>
                                    <Slider
                                      min={0}
                                      max={versions.length - 1}
                                      value={versions.length - 1 - range[1]}
                                      onChange={(_e, v) => {
                                        // Reverse the index for the max slider
                                        setSelectedVersionRangeByName(prev => ({ ...prev, [operator.name]: [range[0], versions.length - 1 - v] }));
                                      }}
                                      showTicks
                                      step={1}
                                      aria-label={`Select maximum version for ${operator.name}`}
                                      marks={versions.slice().reverse().map((ver, idx) => ({ value: idx, label: ver }))}
                                    />
                                  </div>
                                </Tooltip>
                              </div>
                              <span style={{ marginLeft: 8 }}>{minVersion} - {maxVersion}</span>
                            </div>
                          )}
                          {versions.length === 1 && (
                            <div style={{ marginTop: '12px', marginBottom: '8px' }}>
                              <span style={{ fontWeight: 500 }}>Version:&nbsp;</span>
                              <span>{versions[0]}</span>
                            </div>
                          )}
                          <div style={{ marginTop: '16px' }}>
                            {!isOperatorSelected(operator.name, minVersion, maxVersion) ? (
                              <Button
                                variant="primary"
                                size="sm"
                                onClick={() => addOperator(operator, minVersion, maxVersion)}
                                isDisabled={isResolvingDeps}
                              >
                                Add Operator
                              </Button>
                            ) : (
                              <Badge>Selected</Badge>
                            )}
                          </div>
                        </CardBody>
                      </Card>
                    </GridItem>
                  );
                })}
              </Grid>
            </div>
          )}

          {/* Dependency resolution alerts */}
          {dependencyAlerts.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              {dependencyAlerts.map((alert, index) => (
                <Alert
                  key={index}
                  variant={alert.variant}
                  title={alert.title}
                  isInline
                  actionClose={
                    <Button variant="plain" onClick={() => dismissDependencyAlert(index)} aria-label="Dismiss">
                      <TimesIcon />
                    </Button>
                  }
                  style={{ marginBottom: '8px' }}
                >
                  {alert.message}
                </Alert>
              ))}
            </div>
          )}

          {isResolvingDeps && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px' }}>
              <Spinner size="sm" />
              <Text component="small">Resolving operator dependencies...</Text>
            </div>
          )}

          {selectedOperators && selectedOperators.length > 0 && (
            <div style={{ marginTop: '24px' }}>
              <Divider style={{ margin: '16px 0' }} />
              <Title headingLevel="h4" size="md" style={{ marginBottom: '16px' }}>
                Selected Operators ({selectedOperators.length})
              </Title>
              <Grid hasGutter>
                {selectedOperators.map((operator) => (
                  <GridItem span={12} md={6} key={operator.name}>
                    <Card style={operator.isDependency ? { borderLeft: '3px solid var(--pf-v5-global--info-color--100, #2b9af3)' } : undefined}>
                      <CardBody>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div>
                            <Title headingLevel="h6" size="sm">
                              {operator.display_name || operator.name}
                            </Title>
                            <Text component="small" style={{ color: '#6a6e73' }}>
                              {operator.name}
                            </Text>
                          </div>
                          <Button
                            variant="plain"
                            size="sm"
                            onClick={() => removeOperator(operator.name)}
                            aria-label={`Remove ${operator.name}`}
                          >
                            <TimesIcon />
                          </Button>
                        </div>
                        <div style={{ marginTop: '8px' }}>
                          <Text component="small">
                            Channel: {operator.channel || 'stable'}
                          </Text>
                        </div>
                        {operator.isDependency && (
                          <div style={{ marginTop: '6px' }}>
                            <Badge style={{ backgroundColor: 'var(--pf-v5-global--info-color--100, #2b9af3)', color: '#fff', fontSize: '0.75rem' }}>
                              <LinkIcon style={{ marginRight: '4px' }} />
                              Dependency of {operator.dependencyOf}
                            </Badge>
                          </div>
                        )}
                      </CardBody>
                    </Card>
                  </GridItem>
                ))}
              </Grid>
            </div>
          )}
        </Form>
      </CardBody>
    </Card>
  );
}

export default OperatorSearch;
