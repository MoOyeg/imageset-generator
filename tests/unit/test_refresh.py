#!/usr/bin/env python3

import subprocess
import json
import re
import os
from datetime import datetime

def test_oc_mirror():
    """Test oc-mirror command"""
    try:
        print("Testing oc-mirror list releases...")
        
        # Run oc-mirror list releases command
        result = subprocess.run(
            ['oc-mirror', 'list', 'releases'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout[:500]}...")
        print(f"Stderr: {result.stderr}")
        
        if result.returncode == 0:
            # Parse the output to extract version numbers
            releases = []
            lines = result.stdout.strip().split('\n')
            
            print(f"Processing {len(lines)} lines...")
            
            for line in lines:
                line = line.strip()
                if line and re.match(r'^\d+\.\d+$', line):
                    releases.append(line)
                    print(f"Found release: {line}")
            
            print(f"Total releases found: {len(releases)}")
            print(f"Releases: {releases}")
            
            return {
                'status': 'success',
                'releases': releases,
                'count': len(releases)
            }
        else:
            return {
                'status': 'error',
                'message': f'Command failed: {result.stderr}'
            }
            
    except Exception as e:
        print(f"Exception: {e}")
        return {
            'status': 'error', 
            'message': str(e)
        }

if __name__ == "__main__":
    result = test_oc_mirror()
    print("\nFinal result:")
    print(json.dumps(result, indent=2))
