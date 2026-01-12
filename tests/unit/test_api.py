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
import pytest


def test_api(base_url="http://localhost:5000"):
    """Smoke test for the Flask API endpoints.

    Skips if the API server is not running locally.
    """

    print(f"Testing API at {base_url}")
    print("=" * 50)

    test_config = {
        "ocp_versions": ["4.14.1", "4.14.2"],
        "ocp_channel": "stable-4.14",
        "operators": ["logging", "monitoring"],
        "operator_catalog": "registry.redhat.io/redhat/redhat-operator-index",
        "additional_images": ["registry.redhat.io/ubi8/ubi:latest"],
        "output_file": "test-config.yaml",
    }

    try:
        # Test health endpoint
        print("1. Testing health endpoint...")
        response = requests.get(f"{base_url}/api/health")
        if response.status_code != 200:
            pytest.fail(f"Health check failed: {response.status_code}")

        # Test operator mappings
        print("\n2. Testing operator mappings...")
        response = requests.get(f"{base_url}/api/operators/mappings")
        if response.status_code != 200:
            pytest.fail(f"Operator mappings failed: {response.status_code}")
        data = response.json()
        assert isinstance(data.get("mappings", {}), dict)

        # Test preview generation
        print("\n3. Testing preview generation...")
        response = requests.post(f"{base_url}/api/generate/preview", json=test_config)
        if response.status_code != 200:
            content_type = response.headers.get("content-type", "")
            extra = response.json() if content_type.startswith("application/json") else response.text
            pytest.fail(f"Preview generation failed: {response.status_code}, {extra}")
        data = response.json()
        assert "yaml" in data

        # Test sample config
        print("\n4. Testing sample config...")
        response = requests.get(f"{base_url}/api/config/sample")
        if response.status_code != 200:
            pytest.fail(f"Sample config failed: {response.status_code}")
        data = response.json()
        assert "config" in data

        # Test validation
        print("\n5. Testing configuration validation...")
        response = requests.post(f"{base_url}/api/validate", json=test_config)
        if response.status_code != 200:
            pytest.fail(f"Configuration validation failed: {response.status_code}")
        data = response.json()
        assert "valid" in data

        print("\n" + "=" * 50)
        print("✓ All API tests passed!")

    except requests.exceptions.ConnectionError:
        pytest.skip(f"API server not running at {base_url}")
    except Exception as e:
        pytest.fail(f"Test failed with error: {e}")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    success = test_api(base_url)
    sys.exit(0 if success else 1)
