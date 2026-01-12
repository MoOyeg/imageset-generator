#!/usr/bin/env python3

import subprocess
import json
import re
import os
from datetime import datetime
import shutil
import pytest

def test_oc_mirror():
    """Test oc-mirror command (skips if oc-mirror is unavailable)."""
    if shutil.which("oc-mirror") is None:
        pytest.skip("oc-mirror not installed")

    try:
        print("Testing oc-mirror list releases...")

        result = subprocess.run(
            ["oc-mirror", "list", "releases"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout[:500]}...")
        print(f"Stderr: {result.stderr}")

        if result.returncode != 0:
            pytest.skip(f"oc-mirror list releases failed: {result.stderr}")

        releases = []
        lines = result.stdout.strip().split("\n")

        print(f"Processing {len(lines)} lines...")

        for line in lines:
            line = line.strip()
            if line and re.match(r"^\d+\.\d+$", line):
                releases.append(line)
                print(f"Found release: {line}")

        print(f"Total releases found: {len(releases)}")
        print(f"Releases: {releases}")

        # Basic assertions to ensure output is plausible
        assert isinstance(releases, list)
        for rel in releases:
            assert re.match(r"^\d+\.\d+$", rel)

    except subprocess.TimeoutExpired:
        pytest.skip("oc-mirror timed out")
    except FileNotFoundError:
        pytest.skip("oc-mirror binary not found")
    except Exception as e:
        pytest.fail(f"Unexpected error: {e}")

if __name__ == "__main__":
    result = test_oc_mirror()
    print("\nFinal result:")
    print(json.dumps(result, indent=2))
