#!/usr/bin/env python3
"""
Simple tests for validation utilities (no pytest required)
"""

from imageset_generator.validation import (
    validate_catalog_url,
    validate_version,
    validate_channel,
    safe_path_component,
    ValidationError
)


def test_catalog_validation():
    """Test catalog URL validation"""
    print("Testing catalog URL validation...")
    
    # Valid URLs
    valid_urls = [
        "registry.redhat.io/redhat/redhat-operator-index",
        "registry.redhat.io/redhat/community-operator-index",
        "registry.redhat.io/redhat/certified-operator-index:v4.16",
    ]
    for url in valid_urls:
        assert validate_catalog_url(url) == url, f"Failed for valid URL: {url}"
    
    # Invalid URLs
    invalid_urls = [
        "evil.com/malicious",
        "registry.redhat.io/../../etc/passwd",
        "http://registry.redhat.io/redhat/index",
    ]
    for url in invalid_urls:
        try:
            validate_catalog_url(url)
            assert False, f"Should have raised ValidationError for: {url}"
        except ValidationError:
            pass  # Expected
    
    print("  ✓ Catalog URL validation passed")


def test_version_validation():
    """Test version string validation"""
    print("Testing version validation...")
    
    # Valid versions
    valid_versions = ["4.16", "4.17", "4.18"]
    for version in valid_versions:
        assert validate_version(version) == version
    
    # Invalid versions
    invalid_versions = ["4", "4.16.0", "v4.16", "invalid"]
    for version in invalid_versions:
        try:
            validate_version(version)
            assert False, f"Should have raised ValidationError for: {version}"
        except ValidationError:
            pass  # Expected
    
    print("  ✓ Version validation passed")


def test_channel_validation():
    """Test channel string validation"""
    print("Testing channel validation...")
    
    # Valid channels
    valid_channels = ["stable-4.16", "fast-4.17", "eus-4.18"]
    for channel in valid_channels:
        assert validate_channel(channel) == channel
    
    # Invalid channels
    invalid_channels = ["stable", "../evil-4.16", "stable;rm"]
    for channel in invalid_channels:
        try:
            validate_channel(channel)
            assert False, f"Should have raised ValidationError for: {channel}"
        except ValidationError:
            pass  # Expected
    
    print("  ✓ Channel validation passed")


def test_path_validation():
    """Test path component validation"""
    print("Testing path component validation...")
    
    # Valid components
    valid_components = [
        "operators-4.16.json",
        "catalog-index.json",
        "ocp-versions.json",
    ]
    for component in valid_components:
        assert safe_path_component(component) == component
    
    # Invalid components (traversal attempts)
    invalid_components = [
        "../etc/passwd",
        "../../secret",
        "file/subdir",
        "file;rm",
    ]
    for component in invalid_components:
        try:
            safe_path_component(component)
            assert False, f"Should have raised ValidationError for: {component}"
        except ValidationError:
            pass  # Expected
    
    print("  ✓ Path component validation passed")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("VALIDATION MODULE TESTS")
    print("=" * 60 + "\n")
    
    test_catalog_validation()
    test_version_validation()
    test_channel_validation()
    test_path_validation()
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED")
    print("=" * 60 + "\n")
