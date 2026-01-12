#!/usr/bin/env python3
"""
Input validation utilities for ImageSet Generator

Provides validation functions for user inputs to prevent injection attacks,
path traversal, and other security issues.
"""

import re
from typing import Optional


class ValidationError(ValueError):
    """Custom exception for validation errors with detailed context"""
    pass


def validate_catalog_url(url: str) -> str:
    """
    Validate and sanitize catalog URL.
    
    Allows only registry.redhat.io URLs with specific format.
    
    Args:
        url: Catalog URL to validate
        
    Returns:
        Validated URL string
        
    Raises:
        ValidationError: If URL format is invalid
        
    Examples:
        >>> validate_catalog_url("registry.redhat.io/redhat/redhat-operator-index:v4.16")
        'registry.redhat.io/redhat/redhat-operator-index:v4.16'
    """
    if not url or not isinstance(url, str):
        raise ValidationError("Catalog URL must be a non-empty string")
    
    url = url.strip()
    
    # Allowlist pattern for Red Hat registries
    # Format: registry.redhat.io/<org>/<catalog-name>[:v<version>]
    pattern = r'^registry\.redhat\.io/[\w\-]+/[\w\-]+(?::v\d+\.\d+)?$'
    
    if not re.match(pattern, url):
        raise ValidationError(
            f"Invalid catalog URL format. Must match pattern: "
            f"registry.redhat.io/<org>/<catalog>[:v<version>]. Got: {url}"
        )
    
    return url


def validate_version(version: str) -> str:
    """
    Validate OCP version string.
    
    Ensures version follows X.Y format (e.g., 4.16, 4.17).
    
    Args:
        version: Version string to validate
        
    Returns:
        Validated version string
        
    Raises:
        ValidationError: If version format is invalid
        
    Examples:
        >>> validate_version("4.16")
        '4.16'
    """
    if not version or not isinstance(version, str):
        raise ValidationError("Version must be a non-empty string")
    
    version = version.strip()
    
    # Semantic version format: X.Y
    pattern = r'^\d+\.\d+$'
    
    if not re.match(pattern, version):
        raise ValidationError(
            f"Invalid version format. Expected X.Y (e.g., 4.16). Got: {version}"
        )
    
    return version


def validate_channel(channel: str) -> str:
    """
    Validate OCP channel string.
    
    Ensures channel follows valid format (e.g., stable-4.16, fast-4.17).
    
    Args:
        channel: Channel string to validate
        
    Returns:
        Validated channel string
        
    Raises:
        ValidationError: If channel format is invalid
        
    Examples:
        >>> validate_channel("stable-4.16")
        'stable-4.16'
    """
    if not channel or not isinstance(channel, str):
        raise ValidationError("Channel must be a non-empty string")
    
    channel = channel.strip()
    
    # Channel format: <name>-X.Y where name is alphanumeric with hyphens
    # Must have a hyphen before the version number
    pattern = r'^[a-zA-Z][a-zA-Z0-9\-]*-\d+\.\d+$'
    
    if not re.match(pattern, channel):
        raise ValidationError(
            f"Invalid channel format. Expected <name>-X.Y (e.g., stable-4.16). Got: {channel}"
        )
    
    return channel


def safe_path_component(component: str) -> str:
    """
    Validate path component to prevent directory traversal.
    
    Args:
        component: Path component to validate
        
    Returns:
        Validated component
        
    Raises:
        ValidationError: If component contains path traversal attempts
        
    Examples:
        >>> safe_path_component("operators-4.16.json")
        'operators-4.16.json'
    """
    if not component or not isinstance(component, str):
        raise ValidationError("Path component must be a non-empty string")
    
    component = component.strip()
    
    # Check for path traversal attempts
    if '..' in component or '/' in component or '\\' in component:
        raise ValidationError(
            f"Invalid path component. Cannot contain '..',  '/', or '\\'. Got: {component}"
        )
    
    # Allowlist valid filename characters
    pattern = r'^[\w\-\.]+$'
    if not re.match(pattern, component):
        raise ValidationError(
            f"Invalid path component. Must contain only alphanumeric, dash, dot, underscore. Got: {component}"
        )
    
    return component


if __name__ == "__main__":
    import doctest
    doctest.testmod()
