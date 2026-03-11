import React, { useState } from 'react';
import {
  Card,
  CardTitle,
  CardBody,
  Form,
  FormGroup,
  FormSelect,
  FormSelectOption,
  TextArea,
  TextInput,
  Button,
  Grid,
  GridItem,
  Title,
  ActionGroup,
  Alert,
  List,
  ListItem,
  HelperText,
  HelperTextItem,
  Checkbox
} from '@patternfly/react-core';
import { PlusIcon, TrashIcon } from '@patternfly/react-icons';


function AdvancedConfig({ config, updateConfig }) {
  const [helmChartForm, setHelmChartForm] = useState({
    name: '',
    repository: '',
    version: ''
  });
  const [showHelmForm, setShowHelmForm] = useState(false);

  const handleAdditionalImagesChange = (_event, value) => {
    const images = value
      .split(',')
      .map(img => img.trim())
      .filter(img => img.length > 0);
    updateConfig({ additional_images: images });
  };

  const handleArchiveSizeChange = (_event, value) => {
    // Only allow positive integers or empty string
    if (value === '' || (/^\d+$/.test(value) && parseInt(value) > 0)) {
      updateConfig({ archive_size: value === '' ? '' : parseInt(value) });
    }
  };

  const addHelmChart = () => {
    if (helmChartForm.name && helmChartForm.repository) {
      const newChart = {
        name: helmChartForm.name,
        repository: helmChartForm.repository,
        version: helmChartForm.version || ''
      };
      const currentCharts = config.helm_charts || [];
      updateConfig({ helm_charts: [...currentCharts, newChart] });
      setHelmChartForm({ name: '', repository: '', version: '' });
      setShowHelmForm(false);
    }
  };

  const removeHelmChart = (index) => {
    const currentCharts = config.helm_charts || [];
    const updatedCharts = currentCharts.filter((_, i) => i !== index);
    updateConfig({ helm_charts: updatedCharts });
  };

  const isV2 = config.oc_mirror_version === 2;

  return (
    <Grid hasGutter>
      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">oc-mirror Version</Title>
          </CardTitle>
          <CardBody>
            <Form>
              <FormGroup
                label="oc-mirror Version"
                fieldId="oc-mirror-version"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      {isV2
                        ? 'v2 generates v2alpha1 configs. storageConfig and archiveSize are managed via CLI flags (--workspace).'
                        : 'v1 generates v1alpha2 configs with storageConfig and archiveSize in the YAML.'}
                    </HelperTextItem>
                  </HelperText>
                }
              >
                <FormSelect
                  value={config.oc_mirror_version || 1}
                  onChange={(_event, value) => updateConfig({ oc_mirror_version: parseInt(value) })}
                  id="oc-mirror-version"
                >
                  <FormSelectOption value={1} label="oc-mirror v1 (v1alpha2)" />
                  <FormSelectOption value={2} label="oc-mirror v2 (v2alpha1)" />
                </FormSelect>
              </FormGroup>
            </Form>
          </CardBody>
        </Card>
      </GridItem>

      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">Platform Configuration</Title>
          </CardTitle>
          <CardBody>
            <Form>
              {!isV2 && (
                <FormGroup
                  label="Archive Size (optional, GiB)"
                  fieldId="archive-size"
                  helperText="Set the maximum archive size in GiB (Gibibytes) for oc-mirror. Leave blank to omit."
                >
                  <TextInput
                    id="archive-size"
                    type="number"
                    min={1}
                    value={config.archive_size === undefined ? '' : config.archive_size}
                    onChange={handleArchiveSizeChange}
                    placeholder="4"
                  />
                </FormGroup>
              )}
              <FormGroup>
                <Checkbox
                  label="Enable KubeVirt Container Mirroring"
                  isChecked={config.kubevirt_container || false}
                  onChange={(_event, checked) => updateConfig({ kubevirt_container: checked })}
                  id="kubevirt-container-checkbox"
                  description="Enables mirroring of KubeVirt container images by setting mirror.platform.kubeVirtContainer: true"
                />
              </FormGroup>
              <FormGroup>
                <Checkbox
                  label="Enable Graph Mirroring"
                  isChecked={config.graph || false}
                  onChange={(_event, checked) => updateConfig({ graph: checked })}
                  id="graph-checkbox"
                  description="Enables mirroring of graph data and related components by setting mirror.platform.graph: true"
                />
              </FormGroup>
            </Form>
          </CardBody>
        </Card>
      </GridItem>

      {/* Storage Configuration Card — v1 only (v2 uses --workspace CLI flag) */}
      {!isV2 && (
        <GridItem span={12}>
          <Card>
            <CardTitle>
              <Title headingLevel="h2">Storage Configuration</Title>
            </CardTitle>
            <CardBody>
              <Form isHorizontal>
                <FormGroup label="Registry imageURL" fieldId="storage-registry">
                  <input
                    type="text"
                    id="storage-registry"
                    value={typeof config.storageConfig?.registry === 'string' ? config.storageConfig.registry : ''}
                    onChange={e => {
                      let value = '';
                      if (e && e.target && typeof e.target.value === 'string') {
                        value = e.target.value;
                      } else if (typeof e === 'string') {
                        value = e;
                      }
                      // Defensive: never allow DOM nodes or events
                      if (typeof value !== 'string') value = '';
                      updateConfig({ storageConfig: { ...config.storageConfig, registry: value } });
                    }}
                    placeholder="quay.io/your-registry"
                    style={{ width: '100%', padding: '6px', fontSize: '1rem' }}
                  />
                </FormGroup>
                <FormGroup label="Skip TLS" fieldId="storage-skip-tls">
                  <Checkbox
                    id="storage-skip-tls"
                    label="Skip TLS verification for registry"
                    isChecked={!!config.storageConfig?.skipTLS}
                    onChange={(event, checked) => updateConfig({ storageConfig: { ...config.storageConfig, skipTLS: checked } })}
                  />
                </FormGroup>
              </Form>
            </CardBody>
          </Card>
        </GridItem>
      )}

      {isV2 && (
        <GridItem span={12}>
          <Alert variant="info" title="Storage configuration not available in oc-mirror v2">
            In oc-mirror v2, storage is configured via the <code>--workspace</code> CLI flag instead of the YAML configuration.
            For example: <code>oc-mirror --config imageset-config.yaml --workspace file:///path docker://registry --v2</code>
          </Alert>
        </GridItem>
      )}

      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">Additional Images</Title>
          </CardTitle>
          <CardBody>
            <Form>
              <FormGroup
                label="Additional Container Images"
                fieldId="additional-images"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      Enter comma-separated container image references to include in the mirror
                    </HelperTextItem>
                  </HelperText>
                }
              >
                <TextArea
                  id="additional-images"
                  rows={4}
                  value={config.additional_images?.join(', ') || ''}
                  onChange={handleAdditionalImagesChange}
                  placeholder="registry.redhat.io/ubi8/ubi:latest, quay.io/my-org/app:v1.0.0"
                />
              </FormGroup>
            </Form>
          </CardBody>
        </Card>
      </GridItem>

      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">Helm Charts</Title>
          </CardTitle>
          <CardBody>
            <Form>
              <ActionGroup>
                <Button
                  variant={showHelmForm ? "secondary" : "primary"}
                  onClick={() => setShowHelmForm(!showHelmForm)}
                  icon={showHelmForm ? undefined : <PlusIcon />}
                >
                  {showHelmForm ? 'Cancel' : 'Add Helm Chart'}
                </Button>
              </ActionGroup>

              {showHelmForm && (
                <Grid hasGutter style={{ marginTop: '1rem', padding: '1rem', border: '1px solid var(--pf-global--BorderColor--100)', borderRadius: '4px' }}>
                  <GridItem span={12}>
                    <FormGroup
                      label="Chart Name"
                      fieldId="helm-name"
                      isRequired
                    >
                      <TextInput
                        id="helm-name"
                        type="text"
                        value={helmChartForm.name}
                        onChange={(_event, value) => setHelmChartForm({ ...helmChartForm, name: value })}
                        placeholder="prometheus"
                      />
                    </FormGroup>
                  </GridItem>

                  <GridItem span={12}>
                    <FormGroup
                      label="Repository"
                      fieldId="helm-repository"
                      isRequired
                    >
                      <TextInput
                        id="helm-repository"
                        type="text"
                        value={helmChartForm.repository}
                        onChange={(_event, value) => setHelmChartForm({ ...helmChartForm, repository: value })}
                        placeholder="https://prometheus-community.github.io/helm-charts"
                      />
                    </FormGroup>
                  </GridItem>

                  <GridItem span={12}>
                    <FormGroup
                      label="Version (optional)"
                      fieldId="helm-version"
                    >
                      <TextInput
                        id="helm-version"
                        type="text"
                        value={helmChartForm.version}
                        onChange={(_event, value) => setHelmChartForm({ ...helmChartForm, version: value })}
                        placeholder="15.0.0"
                      />
                    </FormGroup>
                  </GridItem>

                  <GridItem span={12}>
                    <ActionGroup>
                      <Button
                        variant="primary"
                        onClick={addHelmChart}
                        isDisabled={!helmChartForm.name || !helmChartForm.repository}
                      >
                        Add Chart
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setShowHelmForm(false);
                          setHelmChartForm({ name: '', repository: '', version: '' });
                        }}
                      >
                        Cancel
                      </Button>
                    </ActionGroup>
                  </GridItem>
                </Grid>
              )}

              {config.helm_charts && config.helm_charts.length > 0 && (
                <List style={{ marginTop: '1rem' }}>
                  {config.helm_charts.map((chart, index) => (
                    <ListItem key={index}>
                      <Grid hasGutter>
                        <GridItem span={10}>
                          <div>
                            <strong>{chart.name}</strong>
                            <br />
                            <small>{chart.repository}</small>
                            {chart.version && (
                              <>
                                <br />
                                <small><strong>Version:</strong> {chart.version}</small>
                              </>
                            )}
                          </div>
                        </GridItem>
                        <GridItem span={2}>
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => removeHelmChart(index)}
                            icon={<TrashIcon />}
                          >
                            Remove
                          </Button>
                        </GridItem>
                      </Grid>
                    </ListItem>
                  ))}
                </List>
              )}

              {(!config.helm_charts || config.helm_charts.length === 0) && !showHelmForm && (
                <Alert variant="info" title="No Helm charts configured">
                  Click "Add Helm Chart" to add a Helm chart to your configuration.
                </Alert>
              )}
            </Form>
          </CardBody>
        </Card>
      </GridItem>
    </Grid>
  );
}

export default AdvancedConfig;
