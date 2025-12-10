# OpenShift ImageSetConfiguration Generator

This tool generates ImageSetConfiguration files for OpenShift disconnected installations using the oc-mirror tool. It takes OCP versions and operator suggestions as input and creates a YAML configuration that can be used to mirror container images and operators for air-gapped environments.  

## Quick Start

1 Build the application container Image with Podman and run the application 
  ```bash
  ./start-podman.sh
  ```

  Script should output web location 
  ![Command Output](./images/cmd-output.png)

2 Open Application WebPage

- Select the OCP Version you want to mirror, the channel and the min and max versions.
![Versions](./images/ocp-version.png)


- Select which OpenShift Catalogs you want to search operators from
![Catalogs](./images/ocp-catalogs.png)


- Search for the Operators you want based on Name or Keywords.
![Operator Search](./images/operator-search.png)

- On the Advanced configuration tab, fill in the storage configuration and available checkboxes.
![Storage Configuration](./images/storage-config.png)


- On the Preview & Generate tab select "Generate Preview" to obtain the output imageset configuration.Copy you output configuration using the copy to clipboard.
![Output](./images/preview-gen1.png)
![Output..Additional](./images/preview-gen2.png)


## Clean and Update Data
The data used is downloaded and stored in the ./data directory

To update run, the application in dev mode, delete the unnecessary info and open the webpage and update
```
rm -rf ./data/*. or rm -rf ./data/<the file you want updated>
./start-dev.sh
```