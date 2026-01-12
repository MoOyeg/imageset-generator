#!/usr/bin/env python3
"""
OpenShift ImageSetConfiguration Generator

This script generates an ImageSetConfiguration file for OpenShift disconnected installations.
It takes OCP versions and operator suggestions as input and creates a YAML configuration
that can be used with the oc-mirror tool.

Usage:
    python generator.py --ocp-versions 4.14.1,4.14.2 --operators logging-operator,cluster-monitoring-operator
    python generator.py --config config.json
"""


import argparse
import yaml
import json
from typing import List, Dict, Any
from datetime import datetime
import sys
import os
import re


class ImageSetGenerator:
    """Generator for OpenShift ImageSetConfiguration files"""
    
    def __init__(self):
        self.config = {
            "apiVersion": "mirror.openshift.io/v1alpha2",
            "kind": "ImageSetConfiguration",
            "metadata": {
                "name": "openshift-imageset",
                "labels": {
                    "generated-by": "imageset-generator",
                    "generated-at": datetime.now().isoformat()
                }
            },
            "spec": {
                # 'archiveSize' will only be set if explicitly requested
                "mirror": {
                    "platform": {
                        "channels": [],
                        "graph": True
                    },
                    "operators": [],
                    "additionalImages": [],
                    "helm": {}
                }
            }
        }

    def set_archive_size(self, size: int):
        """
        Set the archiveSize in the configuration (optional)
        """
        self.config["spec"]["archiveSize"] = size
    
    def add_ocp_versions(self, versions: List[str] = None, channel: List[str] = "stable-4.14", min_version: str = None, max_version: str = None, graph: bool = True):
        """
        Add OpenShift platform versions to the configuration
        
        Args:
            versions: List of OCP version strings (e.g., ["4.14.1", "4.14.2"]) - legacy support
            channel: OCP channel name (default: "stable-4.14")
            min_version: Minimum version to mirror
            max_version: Maximum version to mirror (optional)
            graph: Whether to include version graph data (default: True)
        """
        # Set graph option in platform config
        self.config["spec"]["mirror"]["platform"]["graph"] = graph
        # Handle legacy versions list or new min/max approach
        if min_version or max_version:
            # Use the new min/max approach
            platform_config = {
                "name": channel,
                "type": "ocp"
            }
            
            if min_version:
                platform_config["minVersion"] = min_version
            if max_version:
                platform_config["maxVersion"] = max_version
        elif versions:
            # Legacy approach - use the versions list
            # Determine channel from versions if not specified
            if channel == "stable-4.14" and versions:
                major_minor = ".".join(versions[0].split(".")[:2])
                channel = f"stable-{major_minor}"
            
            platform_config = {
                "name": channel,
                "type": "ocp",
                "minVersion": min(versions),
                "maxVersion": max(versions)
            }
        else:
            return  # Nothing to add
        
        self.config["spec"]["mirror"]["platform"]["channels"].append(platform_config)
    
    def add_operators(self, operators: List[Any], catalog: str = "registry.redhat.io/redhat/redhat-operator-index", channels: Dict[str, str] = None, ocp_version: str = None,newest_channel: Dict[str, str] = None):
        """
        Add operators to the configuration
        Args:
            operators: List of operator dicts (with name, version, channel, etc.)
                      Each operator dict can contain:
                      - name: Name of the operator
                      - minVersion: Minimum version to include (optional)
                      - maxVersion: Maximum version to include (optional)
                      - selectedVersions: List of specific versions to include (optional)
                      - channel: Specific channel to use (optional)
                      - fileName: Path to the operator index file (optional)
            catalog: Operator catalog source (default: Red Hat operator index)
            channels: Optional dictionary mapping operator names to their channels
            ocp_version: Optional OCP version to use for catalog tag
        """
        if not operators:
            return
        # Common operator mappings
        operator_mappings = {
            "logging": "cluster-logging",
            "logging-operator": "cluster-logging", 
            "monitoring": "cluster-monitoring-operator",
            "cluster-monitoring": "cluster-monitoring-operator",
            "service-mesh": "servicemeshoperator",
            "istio": "servicemeshoperator",
            "serverless": "serverless-operator",
            "knative": "serverless-operator",
            "pipelines": "openshift-pipelines-operator-rh",
            "tekton": "openshift-pipelines-operator-rh",
            "gitops": "openshift-gitops-operator",
            "argocd": "openshift-gitops-operator",
            "storage": "odf-operator",
            "ocs": "odf-operator",
            "ceph": "odf-operator",
            "elasticsearch": "elasticsearch-operator",
            "jaeger": "jaeger-product",
            "kiali": "kiali-ossm"
        }
        # Ensure catalog includes OCP version as :v<version> if provided and not already present
        if ocp_version:
            # Remove any existing :vX.YY
            catalog = re.sub(r":v[\d.]+$", "", catalog)
            catalog = f"{catalog}:v{ocp_version}"
        operator_packages = []
        for op in operators:
            # Accept both string and dict for backward compatibility
            if isinstance(op, str):
                package_name = operator_mappings.get(op.lower(), op)
                operator_entry = {"name": package_name}
                if channels and (op in channels or package_name in channels):
                    channel = channels.get(op) or channels.get(package_name)
                    if channel:
                        operator_entry["channels"] = [{"name": channel}]
                operator_packages.append(operator_entry)
            elif isinstance(op, dict):
                package_name = operator_mappings.get(op.get("name", "").lower(), op.get("name", ""))
                operator_entry = {"name": package_name}

                # Handle selected versions if present
                selected_versions = op.get("selectedVersions", [])
                if selected_versions:
                    # If specific versions are selected, use them to determine min/max
                    if len(selected_versions) > 0:
                        operator_entry["minVersion"] = min(selected_versions)
                        operator_entry["maxVersion"] = max(selected_versions)
                else:
                    # Fall back to minVersion/maxVersion if no specific versions selected
                    if op.get("minVersion"):
                        operator_entry["minVersion"] = op["minVersion"]
                    if op.get("maxVersion"):
                        operator_entry["maxVersion"] = op["maxVersion"]

                # Add channel if present
                channel = (channels.get(op.get("name")) if channels else None)
                if channel is not None:
                    channel = list(channel)
                else:
                    channel = []

                if len(channel) > 0:
                    operator_entry["channels"] = []
                    for ch in channel:
                        operator_entry["channels"].append({"name": ch})

                    if newest_channel and package_name in newest_channel:
                        operator_entry["defaultChannel"] = newest_channel[package_name]
                    else:
                        operator_entry["defaultChannel"] = channel[-1]

                if channel is None:
                    channel = op.get("channel")
                    

                operator_packages.append(operator_entry)
        operator_config = {
            "catalog": catalog,
            "packages": operator_packages
        }
        self.config["spec"]["mirror"]["operators"].append(operator_config)
    
    def add_additional_images(self, images: List[str]):
        """
        Add additional container images to mirror
        
        Args:
            images: List of container image references
        """
        if not images:
            return
            
        for image in images:
            self.config["spec"]["mirror"]["additionalImages"].append({
                "name": image
            })
    
    def add_helm_charts(self, charts: List[Dict[str, str]]):
        """
        Add Helm charts to the configuration
        
        Args:
            charts: List of chart dictionaries with 'name' and 'repository' keys
        """
        if not charts:
            return
            
        for chart in charts:
            repo_name = chart.get("repository", "").replace("/", "-").replace(":", "-")
            if repo_name not in self.config["spec"]["mirror"]["helm"]:
                self.config["spec"]["mirror"]["helm"][repo_name] = []
            
            self.config["spec"]["mirror"]["helm"][repo_name].append({
                "name": chart["name"],
                "version": chart.get("version", "")
            })
    
    def set_kubevirt_container(self, enable: bool = True):
        """
        Enable/disable KubeVirt container mirroring
        
        Args:
            enable: Whether to enable KubeVirt container mirroring (default: True)
        """
        if enable:
            self.config["spec"]["mirror"]["platform"]["kubeVirtContainer"] = True
        else:
            # Remove the key if it exists
            if "kubeVirtContainer" in self.config["spec"]["mirror"]["platform"]:
                del self.config["spec"]["mirror"]["platform"]["kubeVirtContainer"]
    
    def generate_yaml(self) -> str:
        """Generate the YAML configuration string with no 'spec' or 'metadata' section; metadata as YAML comments."""
        config_copy = dict(self.config)
        spec = config_copy.pop('spec', {})
        metadata = config_copy.pop('metadata', {})
        # Move all keys from spec to the root
        config_copy.update(spec)
        # Prepare YAML comments for metadata
        comment_lines = []
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, dict):
                    for subk, subv in v.items():
                        comment_lines.append(f"# {k}.{subk}: {subv}")
                else:
                    comment_lines.append(f"# {k}: {v}")
        # Add storageConfig if present
        if 'storageConfig' in config_copy and config_copy['storageConfig'] is None:
            del config_copy['storageConfig']
        yaml_body = yaml.dump(config_copy, default_flow_style=False, sort_keys=False)
        return ("\n".join(comment_lines) + "\n" + yaml_body) if comment_lines else yaml_body
    
    def save_to_file(self, filename: str):
        """Save the configuration to a YAML file"""
        with open(filename, 'w') as f:
            f.write(self.generate_yaml())
        print(f"ImageSetConfiguration saved to {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate OpenShift ImageSetConfiguration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate from command line arguments
  python generator.py --ocp-versions 4.14.1,4.14.2 --operators logging,monitoring,pipelines
  
  # Specify custom output file
  python generator.py --ocp-versions 4.14.1 --operators logging --output my-imageset.yaml
        """
    )
    
    parser.add_argument(
        "--ocp-versions",
        type=str,
        help="Comma-separated list of OCP versions (e.g., '4.14.1,4.14.2')"
    )
    
    parser.add_argument(
        "--ocp-channel", 
        type=str,
        default="stable-4.14",
        help="OCP channel name (default: stable-4.14)"
    )
    
    parser.add_argument(
        "--operators",
        type=str,
        help="Comma-separated list of operator names/suggestions (e.g., 'logging,monitoring,pipelines')"
    )
    
    parser.add_argument(
        "--operator-catalog",
        type=str,
        default="registry.redhat.io/redhat/redhat-operator-index",
        help="Operator catalog source"
    )
    
    parser.add_argument(
        "--additional-images",
        type=str,
        help="Comma-separated list of additional container images"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="imageset-config.yaml",
        help="Output file name (default: imageset-config.yaml)"
    )
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = ImageSetGenerator()
    
    # Load from command line arguments
    if not args.ocp_versions and not args.operators:
        print("Error: Either --ocp-versions or --operators must be specified")
        parser.print_help()
        sys.exit(1)
    
    # Add OCP versions
    if args.ocp_versions:
        versions = [v.strip() for v in args.ocp_versions.split(",")]
        generator.add_ocp_versions(versions, args.ocp_channel)
    
    # Add operators
    if args.operators:
        operators = [op.strip() for op in args.operators.split(",")]
        generator.add_operators(operators, args.operator_catalog)
    
    # Add additional images
    if args.additional_images:
        images = [img.strip() for img in args.additional_images.split(",")]
        generator.add_additional_images(images)
    
    output_file = args.output
    
    # Generate and save the configuration
    generator.save_to_file(output_file)
    
    # Print the generated YAML for review
    print("\nGenerated ImageSetConfiguration:")
    print("=" * 50)
    print(generator.generate_yaml())


if __name__ == "__main__":
    main()