#!/usr/bin/env python3
"""
Test custom exception classes
Tests exception hierarchy, context preservation, and message formatting
"""


# Add the parent directory to the path so we can import exceptions

def test_base_exception():
    """Test base ImageSetGeneratorError exception"""
    from imageset_generator.exceptions import ImageSetGeneratorError
    
    # Test basic message
    error = ImageSetGeneratorError("Test error")
    assert str(error) == "Test error"
    assert error.message == "Test error"
    assert error.details == {}
    assert error.original_error is None
    
    # Test with details
    error = ImageSetGeneratorError("Test error", details={"key": "value", "number": 42})
    assert "Test error" in str(error)
    assert "key=value" in str(error)
    assert "number=42" in str(error)
    
    # Test with original error
    original = ValueError("Original problem")
    error = ImageSetGeneratorError("Wrapped error", original_error=original)
    assert "Wrapped error" in str(error)
    assert "Caused by: Original problem" in str(error)
    
    print("✓ Test passed: Base exception works correctly")

def test_catalog_error():
    """Test CatalogError and subclasses"""
    from imageset_generator.exceptions import CatalogError, CatalogRenderError, CatalogParseError
    
    # Test CatalogError
    error = CatalogError(
        "Failed to process catalog",
        catalog="registry.redhat.io/redhat/redhat-operator-index",
        version="v4.18"
    )
    assert "Failed to process catalog" in str(error)
    assert "catalog=registry.redhat.io/redhat/redhat-operator-index" in str(error)
    assert "version=v4.18" in str(error)
    
    # Test CatalogRenderError
    render_error = CatalogRenderError(
        "OPM render failed",
        catalog="redhat-operator-index",
        version="v4.18"
    )
    assert isinstance(render_error, CatalogError)
    assert "OPM render failed" in str(render_error)
    
    # Test CatalogParseError
    parse_error = CatalogParseError(
        "Invalid JSON in catalog",
        catalog="community-operator-index"
    )
    assert isinstance(parse_error, CatalogError)
    assert "Invalid JSON" in str(parse_error)
    
    print("✓ Test passed: Catalog errors work correctly")

def test_operator_error():
    """Test OperatorError and subclasses"""
    from imageset_generator.exceptions import OperatorError, OperatorNotFoundError, InvalidChannelError
    
    # Test OperatorError
    error = OperatorError(
        "Operator configuration invalid",
        operator="3scale-operator",
        channel="stable",
        version="0.11.0"
    )
    assert "Operator configuration invalid" in str(error)
    assert "operator=3scale-operator" in str(error)
    assert "channel=stable" in str(error)
    assert "version=0.11.0" in str(error)
    
    # Test OperatorNotFoundError
    not_found = OperatorNotFoundError(
        "Operator not found in catalog",
        operator="nonexistent-operator"
    )
    assert isinstance(not_found, OperatorError)
    assert "not found" in str(not_found)
    
    # Test InvalidChannelError
    invalid_channel = InvalidChannelError(
        "Channel does not exist",
        operator="3scale-operator",
        channel="nonexistent"
    )
    assert isinstance(invalid_channel, OperatorError)
    assert "Channel does not exist" in str(invalid_channel)
    
    print("✓ Test passed: Operator errors work correctly")

def test_version_error():
    """Test VersionError and subclasses"""
    from imageset_generator.exceptions import VersionError, InvalidVersionError, VersionComparisonError
    
    # Test VersionError
    error = VersionError(
        "Version out of range",
        version="4.20",
        min_version="4.16",
        max_version="4.18"
    )
    assert "Version out of range" in str(error)
    assert "version=4.20" in str(error)
    assert "min_version=4.16" in str(error)
    assert "max_version=4.18" in str(error)
    
    # Test InvalidVersionError
    invalid = InvalidVersionError(
        "Malformed version string",
        version="invalid.version.format"
    )
    assert isinstance(invalid, VersionError)
    assert "Malformed" in str(invalid)
    
    # Test VersionComparisonError
    comparison = VersionComparisonError(
        "Cannot compare versions",
        version="4.18",
        min_version="4.x"
    )
    assert isinstance(comparison, VersionError)
    assert "Cannot compare" in str(comparison)
    
    print("✓ Test passed: Version errors work correctly")

def test_configuration_error():
    """Test ConfigurationError"""
    from imageset_generator.exceptions import ConfigurationError
    
    error = ConfigurationError(
        "Invalid configuration value",
        config_key="timeout",
        config_value=-1
    )
    assert "Invalid configuration value" in str(error)
    assert "config_key=timeout" in str(error)
    assert "config_value=-1" in str(error)
    
    print("✓ Test passed: Configuration error works correctly")

def test_file_operation_error():
    """Test FileOperationError"""
    from imageset_generator.exceptions import FileOperationError
    
    error = FileOperationError(
        "Cannot write to file",
        file_path="/data/operators.json",
        operation="write"
    )
    assert "Cannot write to file" in str(error)
    assert "file_path=/data/operators.json" in str(error)
    assert "operation=write" in str(error)
    
    print("✓ Test passed: File operation error works correctly")

def test_network_error():
    """Test NetworkError"""
    from imageset_generator.exceptions import NetworkError
    
    error = NetworkError(
        "Connection timeout",
        url="https://registry.redhat.io/v2/",
        status_code=504
    )
    assert "Connection timeout" in str(error)
    assert "url=https://registry.redhat.io/v2/" in str(error)
    assert "status_code=504" in str(error)
    
    print("✓ Test passed: Network error works correctly")

def test_generation_error():
    """Test GenerationError"""
    from imageset_generator.exceptions import GenerationError
    
    error = GenerationError(
        "ImageSet generation failed",
        stage="validation"
    )
    assert "ImageSet generation failed" in str(error)
    assert "stage=validation" in str(error)
    
    print("✓ Test passed: Generation error works correctly")

def test_exception_hierarchy():
    """Test that all exceptions inherit from base class"""
    from imageset_generator.exceptions import (
        ImageSetGeneratorError,
        CatalogError,
        CatalogRenderError,
        CatalogParseError,
        OperatorError,
        OperatorNotFoundError,
        InvalidChannelError,
        VersionError,
        InvalidVersionError,
        VersionComparisonError,
        ConfigurationError,
        FileOperationError,
        NetworkError,
        GenerationError
    )
    
    # All custom exceptions should inherit from ImageSetGeneratorError
    exceptions_to_test = [
        CatalogError,
        CatalogRenderError,
        CatalogParseError,
        OperatorError,
        OperatorNotFoundError,
        InvalidChannelError,
        VersionError,
        InvalidVersionError,
        VersionComparisonError,
        ConfigurationError,
        FileOperationError,
        NetworkError,
        GenerationError
    ]
    
    for exc_class in exceptions_to_test:
        error = exc_class("Test")
        assert isinstance(error, ImageSetGeneratorError), \
            f"{exc_class.__name__} should inherit from ImageSetGeneratorError"
        assert isinstance(error, Exception), \
            f"{exc_class.__name__} should be an Exception"
    
    print("✓ Test passed: All exceptions inherit from base class")

def test_exception_catching():
    """Test that exceptions can be caught at different levels"""
    from imageset_generator.exceptions import (
        ImageSetGeneratorError,
        CatalogError,
        CatalogRenderError
    )
    
    # Test catching specific exception
    try:
        raise CatalogRenderError("Test render error")
    except CatalogRenderError as e:
        assert "Test render error" in str(e)
    
    # Test catching parent exception
    try:
        raise CatalogRenderError("Test render error")
    except CatalogError as e:
        assert "Test render error" in str(e)
    
    # Test catching base exception
    try:
        raise CatalogRenderError("Test render error")
    except ImageSetGeneratorError as e:
        assert "Test render error" in str(e)
    
    print("✓ Test passed: Exception hierarchy allows flexible catching")

if __name__ == '__main__':
    print("Testing custom exception classes...")
    print()
    
    try:
        test_base_exception()
        test_catalog_error()
        test_operator_error()
        test_version_error()
        test_configuration_error()
        test_file_operation_error()
        test_network_error()
        test_generation_error()
        test_exception_hierarchy()
        test_exception_catching()
        
        print()
        print("=" * 50)
        print("ALL TESTS PASSED")
        print("=" * 50)
        sys.exit(0)
        
    except AssertionError as e:
        print()
        print("=" * 50)
        print(f"TEST FAILED: {e}")
        print("=" * 50)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 50)
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 50)
        sys.exit(1)
