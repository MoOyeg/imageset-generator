# Changelog

All notable changes to the OpenShift ImageSetConfiguration Generator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Security & Input Validation (2025-10-28)
- **Input Validation Module** (`validation.py`)
  - `validate_catalog_url()`: Allowlist validation for Red Hat registry URLs
  - `validate_version()`: OCP version format enforcement (X.Y pattern)
  - `validate_channel()`: Channel name format validation
  - `safe_path_component()`: Path traversal prevention for file operations
  - `ValidationError`: Custom exception for validation failures
  - Comprehensive test suite (test_validation_simple.py)

#### Configuration Management (2025-10-28)
- **Constants Module** (`constants.py`)
  - Centralized timeout configurations:
    - `TIMEOUT_OC_MIRROR_SHORT = 30`: Short operations
    - `TIMEOUT_OC_MIRROR_MEDIUM = 120`: Medium operations
    - `TIMEOUT_OC_MIRROR_LONG = 180`: Long operations
    - `TIMEOUT_OPM_RENDER = 180`: OPM render operations
    - `TIMEOUT_CATALOG_DISCOVERY = 300`: Catalog discovery
  - Application defaults: `DEFAULT_HOST`, `DEFAULT_PORT = 5000`
  - Validation patterns: `VERSION_PATTERN`, `CHANNEL_PATTERN`
  - Catalog definitions: `BASE_CATALOGS` (4 Red Hat registries)
  - Operator mappings: `OPERATOR_MAPPINGS` (18 common aliases)
  - Security settings: `TLS_VERIFY = True` (secure by default)
  - Comprehensive test suite (test_constants.py)

#### TLS Configuration (2025-10-28)
- **Configurable TLS Verification**
  - `build_opm_command()`: Helper function for OPM command construction
  - Integrates `TLS_VERIFY` constant from constants.py
  - Supports explicit `skip_tls` parameter override
  - Secure by default (TLS verification enabled)
  - Replaced all hardcoded `--skip-tls` and `--skip-tls-verify` flags
  - Updated `get_operators_from_opm()` to use new helper
  - Uses `TIMEOUT_OPM_RENDER` constant for timeouts
  - Comprehensive test suite (test_tls_config.py)

#### Error Handling (2025-10-28)
- **Custom Exception Classes** (`exceptions.py`)
  - Base class: `ImageSetGeneratorError` with context preservation
  - Catalog exceptions:
    - `CatalogError`: General catalog operation failures
    - `CatalogRenderError`: OPM render command failures
    - `CatalogParseError`: Catalog data parsing failures
  - Operator exceptions:
    - `OperatorError`: General operator operation failures
    - `OperatorNotFoundError`: Operator not found in catalog
    - `InvalidChannelError`: Invalid or unavailable channel
  - Version exceptions:
    - `VersionError`: General version operation failures
    - `InvalidVersionError`: Malformed version strings
    - `VersionComparisonError`: Version comparison failures
  - System exceptions:
    - `ConfigurationError`: Invalid configuration
    - `FileOperationError`: File operation failures
    - `NetworkError`: Network operation failures
    - `GenerationError`: ImageSet generation failures
  - All exceptions include:
    - Detailed error messages with context
    - Optional `details` dict for structured data
    - Original error wrapping for exception chains
    - Proper inheritance hierarchy
  - Comprehensive test suite (test_exceptions.py)

### Changed

#### Dependencies (2026-01-12)
- Added `pytest` and `requests` to `requirements.txt`

#### Code Quality & Refactoring (2025-10-28)
- **Function Refactoring**
  - Refactored `refresh_ocp_operators()` from 166 lines to 45 lines (73% reduction)
  - Extracted 7 focused helper functions:
    - `_get_operator_file_paths()`: Generate storage paths (18 lines)
    - `_render_catalog_index()`: Execute OPM render (17 lines)
    - `_extract_operator_data()`: JQ filtering for operators (26 lines)
    - `_extract_channel_data()`: JQ filtering for channels (22 lines)
    - `_find_operator_channel()`: Channel lookup logic (20 lines)
    - `_parse_operator_data()`: TSV parsing and enrichment (40 lines)
    - `_cleanup_intermediate_files()`: File cleanup (13 lines)
  - Each helper function has single responsibility
  - All helpers are independently testable
  - Comprehensive test suite (test_refactoring.py)

#### Documentation (2025-10-28)
- Updated `CODE-SMELL-ANALYSIS-RESOLUTION.md` with completion status
- Marked 8 high-priority security/quality improvements as completed
- Added detailed completion notes with commit references

### Fixed

#### Automation Reliability (2026-01-12)
- Ensure mirror jobs always mount storage, using `emptyDir` when PVCs are disabled
- Make job cleanup timezone-safe when comparing completion timestamps
- Allow dry-run executions without an available Kubernetes client
- Align scheduler window checks to the configured day ranges
- Use event types for Slack notification color selection
- Sort release versions safely when suffixes are present
- Keep in-memory execution history trimmed to the configured size

#### Security Improvements (2025-10-28)
- Fixed command injection vulnerabilities with input validation
- Fixed path traversal vulnerabilities with path sanitization
- Fixed hardcoded TLS bypass flags (now configurable)
- Removed magic numbers and hardcoded values
- Improved error messages with detailed context

## Test Coverage

### Test Suites Added (2025-10-28)
1. **test_validation_simple.py** - 4 tests for input validation
2. **test_constants.py** - 2 tests for constants structure
3. **test_tls_config.py** - 5 tests for TLS configuration
4. **test_refactoring.py** - 6 tests for refactored functions
5. **test_exceptions.py** - 10 tests for exception hierarchy

**Total: 27 tests, all passing** ✓

## Commits

### Recent Commits (2025-10-28)
- `052a7de` - docs: mark all remaining items as completed in resolution doc
- `fb192e4` - feat: add custom exception classes with detailed context
- `6ae02ba` - refactor: break down refresh_ocp_operators into focused helper functions
- `5aee348` - docs: mark TLS configuration as completed in resolution doc
- `6a498d2` - feat: make TLS verification configurable via constants
- `d99a73e` - docs: update resolution document with completed security improvements
- `083be26` - feat: extract magic numbers to constants module
- `d33b49a` - feat: add comprehensive input validation module

## Migration Guide

### For Developers

If you're extending or modifying the codebase:

#### Using the Validation Module
```python
from validation import validate_catalog_url, validate_version, ValidationError

try:
    validate_catalog_url("registry.redhat.io/redhat/redhat-operator-index")
    validate_version("4.18")
except ValidationError as e:
    print(f"Validation failed: {e}")
```

#### Using Constants
```python
from constants import TLS_VERIFY, TIMEOUT_OPM_RENDER, BASE_CATALOGS

# Use centralized timeout values
subprocess.run(cmd, timeout=TIMEOUT_OPM_RENDER)

# Use centralized catalog definitions
for catalog in BASE_CATALOGS:
    process_catalog(catalog)
```

#### Using Custom Exceptions
```python
from exceptions import CatalogRenderError, OperatorNotFoundError

try:
    render_catalog(catalog_url)
except CatalogRenderError as e:
    # Exception includes catalog, version, and original error
    logger.error(f"Catalog render failed: {e}")
    logger.debug(f"Details: {e.details}")
```

#### Building OPM Commands
```python
from app import build_opm_command

# Default: uses TLS_VERIFY from constants.py
cmd = build_opm_command("registry.redhat.io/redhat/redhat-operator-index:v4.18")

# Override TLS verification if needed
cmd = build_opm_command(catalog_url, skip_tls=True)

# Specify output format
cmd = build_opm_command(catalog_url, output_format='json')
```

### Configuration Changes

#### TLS Verification
TLS verification is now configurable via `constants.py`. To disable TLS verification globally (not recommended for production):

```python
# In constants.py
TLS_VERIFY = False  # Default is True
```

Or override per-command:
```python
cmd = build_opm_command(catalog_url, skip_tls=True)
```

## [Previous Versions]

### Earlier Features
- Web-based UI for OpenShift ImageSet configuration
- OCP version and channel selection
- Operator search with keyword filtering
- Multi-catalog support (Red Hat, Certified, Community, Marketplace)
- YAML configuration generation for oc-mirror
- Container-based deployment with Podman
- Flask REST API backend
- React frontend application

---

For more information, see:
- [README.md](README.md) - Getting started guide
- [CODE-SMELL-ANALYSIS-RESOLUTION.md](CODE-SMELL-ANALYSIS-RESOLUTION.md) - Security audit results
