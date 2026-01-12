#!/usr/bin/env python3
"""
Test constants module
"""

from imageset_generator.constants import (
    TIMEOUT_OC_MIRROR_SHORT,
    TIMEOUT_OPM_RENDER,
    DEFAULT_PORT,
    VERSION_PATTERN,
    BASE_CATALOGS,
    OPERATOR_MAPPINGS,
    CACHE_OCP_VERSIONS
)
import re


def test_constants_defined():
    """Test that constants are properly defined"""
    print("Testing constants are defined...")
    
    # Timeouts should be positive integers
    assert isinstance(TIMEOUT_OC_MIRROR_SHORT, int)
    assert TIMEOUT_OC_MIRROR_SHORT > 0
    assert isinstance(TIMEOUT_OPM_RENDER, int)
    assert TIMEOUT_OPM_RENDER > 0
    
    # Port should be valid
    assert isinstance(DEFAULT_PORT, int)
    assert 1024 <= DEFAULT_PORT <= 65535
    
    # Version pattern should be valid regex
    assert isinstance(VERSION_PATTERN, str)
    compiled = re.compile(VERSION_PATTERN)
    assert compiled.match("4.16")
    assert not compiled.match("invalid")
    
    # Base catalogs should be a list
    assert isinstance(BASE_CATALOGS, list)
    assert len(BASE_CATALOGS) > 0
    assert all('name' in catalog for catalog in BASE_CATALOGS)
    assert all('base_url' in catalog for catalog in BASE_CATALOGS)
    
    # Operator mappings should be a dict
    assert isinstance(OPERATOR_MAPPINGS, dict)
    assert len(OPERATOR_MAPPINGS) > 0
    assert 'logging' in OPERATOR_MAPPINGS
    assert OPERATOR_MAPPINGS['logging'] == 'cluster-logging'
    
    # Cache file names
    assert isinstance(CACHE_OCP_VERSIONS, str)
    assert CACHE_OCP_VERSIONS.endswith('.json')
    
    print("  ✓ All constants properly defined")


def test_catalog_structure():
    """Test BASE_CATALOGS structure"""
    print("Testing catalog structure...")
    
    required_keys = ['name', 'base_url', 'description', 'default']
    for catalog in BASE_CATALOGS:
        for key in required_keys:
            assert key in catalog, f"Missing key '{key}' in catalog"
        assert isinstance(catalog['name'], str)
        assert isinstance(catalog['base_url'], str)
        assert isinstance(catalog['description'], str)
        assert isinstance(catalog['default'], bool)
        assert catalog['base_url'].startswith('registry.redhat.io')
    
    # Should have at least one default catalog
    defaults = [c for c in BASE_CATALOGS if c['default']]
    assert len(defaults) >= 1, "Should have at least one default catalog"
    
    print("  ✓ Catalog structure valid")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CONSTANTS MODULE TESTS")
    print("=" * 60 + "\n")
    
    test_constants_defined()
    test_catalog_structure()
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED")
    print("=" * 60 + "\n")
