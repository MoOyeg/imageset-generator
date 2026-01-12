#!/usr/bin/env python3
"""
Constants for ImageSet Generator

Centralized configuration constants for timeouts, ports, patterns, and defaults.
"""

import os

# Network Timeouts (seconds)
TIMEOUT_OC_MIRROR_SHORT = 30      # For list operations
TIMEOUT_OC_MIRROR_MEDIUM = 120    # For catalog listings
TIMEOUT_OC_MIRROR_LONG = 180      # For render operations
TIMEOUT_OPM_RENDER = 180          # For opm render commands
TIMEOUT_CATALOG_DISCOVERY = 300   # For catalog discovery

# Server Configuration
DEFAULT_PORT = 5000
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'False').lower() == 'true'

# Version Patterns
VERSION_PATTERN = r'^\d+\.\d+$'                    # X.Y format
CHANNEL_PATTERN = r'^[a-zA-Z][a-zA-Z0-9\-]*\d+\.\d+$'  # stable-X.Y format

# Catalog Configuration
CATALOG_REGISTRY = "registry.redhat.io"
CATALOG_ORG = "redhat"

# Base Catalogs
BASE_CATALOGS = [
    {
        "name": "Red Hat Operators",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/redhat-operator-index",
        "description": "Official Red Hat certified operators",
        "default": True
    },
    {
        "name": "Community Operators",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/community-operator-index",
        "description": "Community-maintained operators",
        "default": False
    },
    {
        "name": "Certified Operators",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/certified-operator-index",
        "description": "Third-party certified operators",
        "default": False
    },
    {
        "name": "Red Hat Marketplace",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/redhat-marketplace-index",
        "description": "Commercial operators from Red Hat Marketplace",
        "default": False
    }
]

# Operator Name Mappings
OPERATOR_MAPPINGS = {
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

# File Paths
DATA_DIR = "data"
FRONTEND_BUILD_DIR = "frontend/build"

# Cache File Names
CACHE_OCP_VERSIONS = "ocp-versions.json"
CACHE_OCP_CHANNELS = "ocp-channels.json"
CACHE_CHANNEL_RELEASES = "channel-releases.json"

# TLS Configuration
TLS_VERIFY = True  # Set to False to skip TLS verification (not recommended)

# API Response Metadata
API_VERSION = "1.0.0"
API_NAME = "ImageSet Generator API"
