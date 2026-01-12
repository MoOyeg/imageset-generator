#!/usr/bin/env python3
"""
Test TLS configuration integration in app.py
Tests that build_opm_command respects TLS_VERIFY constant
"""

import sys
import os


def test_build_opm_command_default():
    """Test that build_opm_command uses TLS_VERIFY constant by default"""
    from imageset_generator.app import build_opm_command
    from imageset_generator.constants import TLS_VERIFY
    
    cmd = build_opm_command('registry.redhat.io/redhat/redhat-operator-index:v4.18')
    
    # Check that the command respects the TLS_VERIFY constant
    if TLS_VERIFY:
        # When TLS_VERIFY=True, should NOT include --skip-tls (secure by default)
        assert '--skip-tls' not in cmd, f"Expected no --skip-tls flag with TLS_VERIFY=True, got: {cmd}"
        print(f"✓ Test passed: Default TLS_VERIFY=True produces secure command (no --skip-tls)")
    else:
        # When TLS_VERIFY=False, should include --skip-tls
        assert '--skip-tls' in cmd, f"Expected --skip-tls flag with TLS_VERIFY=False, got: {cmd}"
        print(f"✓ Test passed: Default TLS_VERIFY=False produces insecure command (with --skip-tls)")
    
    assert 'opm' in cmd, "Command should start with 'opm'"
    assert 'render' in cmd, "Command should include 'render'"
    assert 'registry.redhat.io/redhat/redhat-operator-index:v4.18' in cmd

def test_build_opm_command_explicit_skip_tls():
    """Test explicit skip_tls parameter overrides"""
    from imageset_generator.app import build_opm_command
    
    # Test explicit skip_tls=True
    cmd = build_opm_command('registry.redhat.io/redhat/redhat-operator-index:v4.18', skip_tls=True)
    assert '--skip-tls' in cmd, f"Explicit skip_tls=True should add --skip-tls flag, got: {cmd}"
    print("✓ Test passed: Explicit skip_tls=True override works")
    
    # Test explicit skip_tls=False  
    cmd = build_opm_command('registry.redhat.io/redhat/redhat-operator-index:v4.18', skip_tls=False)
    assert '--skip-tls' not in cmd, f"Explicit skip_tls=False should not add --skip-tls flag, got: {cmd}"
    print("✓ Test passed: Explicit skip_tls=False override works")

def test_build_opm_command_json_output():
    """Test that build_opm_command handles JSON output format correctly"""
    from imageset_generator.app import build_opm_command
    
    cmd = build_opm_command('registry.redhat.io/redhat/redhat-operator-index:v4.18', output_format='json')
    
    assert '--output' in cmd, "JSON format should include --output flag"
    assert 'json' in cmd, "JSON format should include 'json' argument"
    
    # Find position of --output and verify json comes after it
    output_idx = cmd.index('--output')
    assert cmd[output_idx + 1] == 'json', "JSON should be the argument after --output"
    
    print("✓ Test passed: JSON output format configured correctly")

def test_build_opm_command_yaml_output():
    """Test that build_opm_command handles YAML output (default) correctly"""
    from imageset_generator.app import build_opm_command
    
    cmd = build_opm_command('registry.redhat.io/redhat/redhat-operator-index:v4.18')
    
    # YAML is default, should not include explicit --output flag
    assert '--output' not in cmd, "YAML format (default) should not include --output flag"
    
    print("✓ Test passed: YAML output format (default) configured correctly")

def test_tls_verify_constant_default():
    """Test that TLS_VERIFY constant defaults to True (secure by default)"""
    from imageset_generator.constants import TLS_VERIFY
    
    assert TLS_VERIFY == True, f"TLS_VERIFY should default to True for security, got: {TLS_VERIFY}"
    print("✓ Test passed: TLS_VERIFY constant defaults to True (secure by default)")

if __name__ == '__main__':
    print("Testing TLS configuration integration...")
    print()
    
    try:
        test_tls_verify_constant_default()
        test_build_opm_command_default()
        test_build_opm_command_explicit_skip_tls()
        test_build_opm_command_json_output()
        test_build_opm_command_yaml_output()
        
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
