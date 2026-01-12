#!/usr/bin/env python3
"""
Test refactored refresh_ocp_operators helper functions
Tests smaller, focused functions extracted from large monolithic function
"""

import sys
import os
import tempfile


def test_get_operator_file_paths():
    """Test file path generation"""
    from imageset_generator.app import _get_operator_file_paths
    
    main, index, data, channel = _get_operator_file_paths("redhat-operator-index", "v4.18")
    
    assert main == "data/operators-redhat-operator-index-v4.18.json"
    assert index == "data/operators-redhat-operator-index-v4.18-index.json"
    assert data == "data/operators-redhat-operator-index-v4.18-data.json"
    assert channel == "data/operators-redhat-operator-index-v4.18-channel.json"
    
    print("✓ Test passed: File path generation works correctly")

def test_cleanup_intermediate_files():
    """Test intermediate file cleanup"""
    from imageset_generator.app import _cleanup_intermediate_files
    
    # Create temporary files
    temp_files = []
    for i in range(3):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        temp_files.append(path)
    
    # Verify files exist
    for path in temp_files:
        assert os.path.exists(path), f"Temp file {path} should exist before cleanup"
    
    # Cleanup
    _cleanup_intermediate_files(*temp_files)
    
    # Verify files are removed
    for path in temp_files:
        assert not os.path.exists(path), f"Temp file {path} should be removed after cleanup"
    
    print("✓ Test passed: Cleanup removes intermediate files")

def test_cleanup_handles_missing_files():
    """Test that cleanup doesn't fail on missing files"""
    from imageset_generator.app import _cleanup_intermediate_files
    
    # Try to cleanup non-existent files (should not raise error)
    try:
        _cleanup_intermediate_files("/tmp/nonexistent1.txt", "/tmp/nonexistent2.txt")
        print("✓ Test passed: Cleanup handles missing files gracefully")
    except Exception as e:
        raise AssertionError(f"Cleanup should not fail on missing files: {e}")

def test_find_operator_channel():
    """Test channel finding logic"""
    from imageset_generator.app import _find_operator_channel
    
    # Create temporary channel file
    fd, channel_file = tempfile.mkstemp(suffix='.tsv')
    try:
        # Write test data
        test_data = """3scale-operator\tstable\t3scale-operator.v0.11.0\tstable
advanced-cluster-management\trelease-2.5\tacm-operator.v2.5.0\trelease-2.5
openshift-gitops-operator\tgitops-1.8\topenshift-gitops-operator.v1.8.0\tgitops-1.8"""
        
        with os.fdopen(fd, 'w') as f:
            f.write(test_data)
        
        # Test finding existing channel
        channel = _find_operator_channel("3scale-operator.v0.11.0", channel_file)
        assert channel == "stable", f"Expected 'stable', got '{channel}'"
        
        channel = _find_operator_channel("acm-operator.v2.5.0", channel_file)
        assert channel == "release-2.5", f"Expected 'release-2.5', got '{channel}'"
        
        # Test finding non-existent operator
        channel = _find_operator_channel("nonexistent-operator", channel_file)
        assert channel == "", f"Expected empty string for non-existent operator, got '{channel}'"
        
        print("✓ Test passed: Channel finding works correctly")
        
    finally:
        if os.path.exists(channel_file):
            os.remove(channel_file)

def test_parse_operator_data():
    """Test TSV parsing and enrichment"""
    from imageset_generator.app import _parse_operator_data
    
    # Create temporary data and channel files
    fd_data, data_file = tempfile.mkstemp(suffix='.tsv')
    fd_channel, channel_file = tempfile.mkstemp(suffix='.tsv')
    
    try:
        # Write test operator data
        test_data = """3scale-operator\t3scale-operator.v0.11.0\t0.11.0\tapi,management\t3scale API Management\tstable
advanced-cluster-management\tacm-operator.v2.5.0\t2.5.0\tmulticluster\tAdvanced Cluster Management\trelease-2.5"""
        
        with os.fdopen(fd_data, 'w') as f:
            f.write(test_data)
        
        # Write test channel data
        test_channels = """3scale-operator\tstable\t3scale-operator.v0.11.0\tstable
advanced-cluster-management\trelease-2.5\tacm-operator.v2.5.0\trelease-2.5"""
        
        with os.fdopen(fd_channel, 'w') as f:
            f.write(test_channels)
        
        # Parse data
        operators = _parse_operator_data(data_file, channel_file)
        
        # Verify results
        assert len(operators) == 2, f"Expected 2 operators, got {len(operators)}"
        
        # Check first operator
        op1 = operators[0]
        assert op1["package"] == "3scale-operator"
        assert op1["name"] == "3scale-operator"
        assert op1["version"] == "0.11.0"
        assert "api" in op1["keywords"]
        assert "management" in op1["keywords"]
        assert "3scale API Management" in op1["description"]
        assert op1["channel"] == "stable"
        
        # Check second operator
        op2 = operators[1]
        assert op2["package"] == "advanced-cluster-management"
        assert op2["version"] == "2.5.0"
        assert op2["channel"] == "release-2.5"
        
        print("✓ Test passed: TSV parsing and enrichment works correctly")
        
    finally:
        if os.path.exists(data_file):
            os.remove(data_file)
        if os.path.exists(channel_file):
            os.remove(channel_file)

def test_function_size_reduction():
    """Test that main function is significantly smaller"""
    import inspect
    from imageset_generator.app import refresh_ocp_operators
    
    # Get source code
    source = inspect.getsource(refresh_ocp_operators)
    lines = [line for line in source.split('\n') if line.strip() and not line.strip().startswith('#')]
    
    # Should be under 80 lines (down from 166)
    assert len(lines) < 80, f"Main function should be under 80 lines, got {len(lines)}"
    
    print(f"✓ Test passed: Main function reduced to {len(lines)} lines (from 166)")

if __name__ == '__main__':
    print("Testing refactored operator refresh functions...")
    print()
    
    try:
        test_get_operator_file_paths()
        test_cleanup_intermediate_files()
        test_cleanup_handles_missing_files()
        test_find_operator_channel()
        test_parse_operator_data()
        test_function_size_reduction()
        
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
