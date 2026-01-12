"""
ImageSet Generator - OpenShift ImageSetConfiguration Generator

A tool for generating oc-mirror ImageSetConfiguration YAML files
for disconnected OpenShift installations.
"""

from .generator import ImageSetGenerator
from .constants import (
    TLS_VERIFY,
    TIMEOUT_OPM_RENDER,
    TIMEOUT_CHANNELS,
    DEFAULT_CATALOGS,
    DEFAULT_CATALOG_VERSIONS,
)
from .validation import (
    validate_version,
    validate_channel,
    validate_registry_url,
    validate_path_component,
    ValidationError,
)
from .exceptions import (
    ImageSetError,
    CatalogError,
    OperatorError,
    VersionError,
    ConfigurationError,
    NetworkError,
    ImageSetGenerationError,
)

__version__ = "1.0.0"
__all__ = [
    "ImageSetGenerator",
    "TLS_VERIFY",
    "TIMEOUT_OPM_RENDER",
    "TIMEOUT_CHANNELS",
    "DEFAULT_CATALOGS",
    "DEFAULT_CATALOG_VERSIONS",
    "validate_version",
    "validate_channel",
    "validate_registry_url",
    "validate_path_component",
    "ValidationError",
    "ImageSetError",
    "CatalogError",
    "OperatorError",
    "VersionError",
    "ConfigurationError",
    "NetworkError",
    "ImageSetGenerationError",
]
