#!/usr/bin/env python3
"""
Tests for validation utilities
"""

import pytest
from imageset_generator.validation import (
    validate_catalog_url,
    validate_version,
    validate_channel,
    safe_path_component,
    ValidationError
)


class TestCatalogURLValidation:
    """Test catalog URL validation"""
    
    def test_valid_catalog_urls(self):
        """Test valid catalog URL patterns"""
        valid_urls = [
            "registry.redhat.io/redhat/redhat-operator-index",
            "registry.redhat.io/redhat/community-operator-index",
            "registry.redhat.io/redhat/certified-operator-index:v4.16",
            "registry.redhat.io/redhat/redhat-marketplace-index:v4.17",
        ]
        for url in valid_urls:
            assert validate_catalog_url(url) == url
    
    def test_invalid_catalog_urls(self):
        """Test invalid catalog URLs are rejected"""
        invalid_urls = [
            "evil.com/malicious",
            "registry.redhat.io/../../etc/passwd",
            "http://registry.redhat.io/redhat/index",
            "registry.redhat.io/redhat/index; rm -rf /",
            "",
            "   ",
        ]
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                validate_catalog_url(url)
    
    def test_none_catalog_url(self):
        """Test None raises ValidationError"""
        with pytest.raises(ValidationError):
            validate_catalog_url(None)
    
    def test_whitespace_trimming(self):
        """Test leading/trailing whitespace is trimmed"""
        url = "  registry.redhat.io/redhat/redhat-operator-index  "
        expected = "registry.redhat.io/redhat/redhat-operator-index"
        assert validate_catalog_url(url) == expected


class TestVersionValidation:
    """Test version string validation"""
    
    def test_valid_versions(self):
        """Test valid version patterns"""
        valid_versions = ["4.16", "4.17", "4.18", "4.19", "4.20"]
        for version in valid_versions:
            assert validate_version(version) == version
    
    def test_invalid_versions(self):
        """Test invalid version formats are rejected"""
        invalid_versions = [
            "4",
            "4.16.0",
            "v4.16",
            "4.16-stable",
            "invalid",
            "../4.16",
            "",
        ]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                validate_version(version)
    
    def test_whitespace_trimming(self):
        """Test version whitespace trimming"""
        assert validate_version("  4.16  ") == "4.16"


class TestChannelValidation:
    """Test channel string validation"""
    
    def test_valid_channels(self):
        """Test valid channel patterns"""
        valid_channels = [
            "stable-4.16",
            "fast-4.17",
            "eus-4.18",
            "candidate-4.19",
        ]
        for channel in valid_channels:
            assert validate_channel(channel) == channel
    
    def test_invalid_channels(self):
        """Test invalid channel formats are rejected"""
        invalid_channels = [
            "stable",
            "../evil-4.16",
            "stable/4.16",
            "stable;rm -rf",
            "",
        ]
        for channel in invalid_channels:
            with pytest.raises(ValidationError):
                validate_channel(channel)


class TestPathComponentValidation:
    """Test path component validation for traversal prevention"""
    
    def test_valid_components(self):
        """Test valid path components"""
        valid_components = [
            "operators-4.16.json",
            "catalog-index.json",
            "ocp-versions.json",
            "file_name-123.txt",
        ]
        for component in valid_components:
            assert safe_path_component(component) == component
    
    def test_traversal_attempts(self):
        """Test directory traversal attempts are blocked"""
        traversal_attempts = [
            "../etc/passwd",
            "../../secret",
            "file/../other",
            "file/subdir",
            "file\\windows",
        ]
        for attempt in traversal_attempts:
            with pytest.raises(ValidationError):
                safe_path_component(attempt)
    
    def test_special_characters(self):
        """Test special characters are rejected"""
        invalid_components = [
            "file;rm -rf",
            "file|cmd",
            "file&cmd",
            "file$var",
        ]
        for component in invalid_components:
            with pytest.raises(ValidationError):
                safe_path_component(component)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
