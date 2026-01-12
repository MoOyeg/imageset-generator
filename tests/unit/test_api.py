#!/usr/bin/env python3
"""
Test script for the OpenShift ImageSetConfiguration Generator Web API
"""

try:
    import requests
except ImportError:
    print("Error: requests library not found.")
    print("Install with: pip install requests")
    exit(1)

import json
import sys

def test_api(base_url="http://localhost:5000"):
    """Test the Flask API endpoints"""
    
    print(f"Testing API at {base_url}")
    print("=" * 50)
    
    try:
        # Test health endpoint
        print("1. Testing health endpoint...")
        response = requests.get(f"{base_url}/api/health")
        if response.status_code == 200:
            print("✓ Health check passed")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
        
        # Test operator mappings
        print("\n2. Testing operator mappings...")
        response = requests.get(f"{base_url}/api/operators/mappings")
        if response.status_code == 200:
            data = response.json()
            print("✓ Operator mappings retrieved")
            print(f"  Found {len(data.get('mappings', {}))} operator mappings")
        else:
            print(f"✗ Operator mappings failed: {response.status_code}")
            return False
        
        # Test preview generation
        print("\n3. Testing preview generation...")
        test_config = {
            "ocp_versions": ["4.14.1", "4.14.2"],
            "ocp_channel": "stable-4.14",
            "operators": ["logging", "monitoring"],
            "operator_catalog": "registry.redhat.io/redhat/redhat-operator-index",
            "additional_images": ["registry.redhat.io/ubi8/ubi:latest"],
            "output_file": "test-config.yaml"
        }
        
        response = requests.post(f"{base_url}/api/generate/preview", json=test_config)
        if response.status_code == 200:
            data = response.json()
            print("✓ Preview generation successful")
            print(f"  Generated YAML length: {len(data.get('yaml', ''))}")
        else:
            print(f"✗ Preview generation failed: {response.status_code}")
            if response.headers.get('content-type', '').startswith('application/json'):
                print(f"  Error: {response.json()}")
            return False
        
        # Test sample config
        print("\n4. Testing sample config...")
        response = requests.get(f"{base_url}/api/config/sample")
        if response.status_code == 200:
            data = response.json()
            print("✓ Sample config retrieved")
            config = data.get('config', {})
            print(f"  OCP versions: {config.get('ocp_versions', [])}")
            print(f"  Operators: {len(config.get('operators', []))}")
        else:
            print(f"✗ Sample config failed: {response.status_code}")
            return False
        
        # Test validation
        print("\n5. Testing configuration validation...")
        response = requests.post(f"{base_url}/api/validate", json=test_config)
        if response.status_code == 200:
            data = response.json()
            print("✓ Configuration validation successful")
            print(f"  Valid: {data.get('valid', False)}")
            print(f"  Errors: {len(data.get('errors', []))}")
            print(f"  Warnings: {len(data.get('warnings', []))}")
        else:
            print(f"✗ Configuration validation failed: {response.status_code}")
            return False
        
        print("\n" + "=" * 50)
        print("✓ All API tests passed!")
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"✗ Could not connect to {base_url}")
        print("  Make sure the Flask server is running:")
        print(f"  python app.py --host 127.0.0.1 --port 5000")
        return False
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    success = test_api(base_url)
    sys.exit(0 if success else 1)
