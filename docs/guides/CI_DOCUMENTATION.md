# CI/CD Pipeline Documentation

This document describes the Continuous Integration and Continuous Deployment (CI/CD) pipelines for the ImageSet Generator project.

## Overview

The project uses GitHub Actions for automated testing, security scanning, code quality checks, and container image building. All workflows are located in `.github/workflows/`.

## Workflows

### 1. Python Tests (`test.yml`)

**Trigger:** Push to main, Pull Requests  
**Purpose:** Run comprehensive test suite across multiple Python versions

**Jobs:**
- Tests on Python 3.10, 3.11, 3.12, and 3.13
- Runs all 5 test suites:
  - `test_validation_simple.py` - Input validation (4 tests)
  - `test_constants.py` - Constants structure (2 tests)
  - `test_tls_config.py` - TLS configuration (5 tests)
  - `test_refactoring.py` - Refactored functions (6 tests)
  - `test_exceptions.py` - Exception classes (10 tests)
- **Total: 27 tests**

**Badge:**
```markdown
![Python Tests](https://github.com/tomazb/imageset-generator/actions/workflows/test.yml/badge.svg)
```

### 2. Security Scan (`security.yml`)

**Trigger:** Push to main, Pull Requests, Weekly schedule (Monday 9 AM UTC)  
**Purpose:** Comprehensive security scanning

**Jobs:**

#### Bandit Security Scan
- Static analysis for Python security issues
- Detects common security vulnerabilities
- Generates JSON and text reports

#### Safety Dependency Scan
- Checks for known security vulnerabilities in dependencies
- Uses Safety database of CVEs
- Generates security report

#### CodeQL Analysis
- GitHub's semantic code analysis engine
- Analyzes Python and JavaScript code
- Identifies security vulnerabilities and coding errors
- Results appear in GitHub Security tab

#### Trivy Filesystem Scan
- Scans filesystem for vulnerabilities
- Checks dependencies and configuration files
- Results uploaded to GitHub Security tab

**Badge:**
```markdown
![Security Scan](https://github.com/tomazb/imageset-generator/actions/workflows/security.yml/badge.svg)
```

### 3. Container Build & Scan (`container.yml`)

**Trigger:** Push to main, Pull Requests, Tags (v*)  
**Purpose:** Build and scan container images

**Jobs:**

#### Build and Scan
- Builds Docker image with BuildKit
- Runs Trivy vulnerability scan on image
- Blocks on CRITICAL/HIGH vulnerabilities
- Publishes to GitHub Container Registry (ghcr.io)
- Tags:
  - `main` - Latest from main branch
  - `sha-<commit>` - Specific commit
  - `v*` - Version tags (e.g., v1.0.0)

#### Build Podman
- Tests Containerfile with Podman
- Ensures Podman compatibility
- Tests both Containerfile and Dockerfile

**Image Location:**
```
ghcr.io/tomazb/imageset-generator:main
ghcr.io/tomazb/imageset-generator:sha-<commit>
ghcr.io/tomazb/imageset-generator:v1.0.0
```

**Badge:**
```markdown
![Container Build](https://github.com/tomazb/imageset-generator/actions/workflows/container.yml/badge.svg)
```

### 4. Code Quality (`quality.yml`)

**Trigger:** Push to main, Pull Requests  
**Purpose:** Code quality and style checks

**Jobs:**

#### Python Linting
- **Black** - Code formatting
- **isort** - Import sorting
- **Flake8** - Style guide enforcement (PEP 8)
- **Pylint** - Code analysis
- **MyPy** - Static type checking

#### Complexity Check
- **Radon** - Cyclomatic complexity analysis
- **Maintainability Index** - Code maintainability score

#### Documentation Check
- Verifies required documentation files exist
- Checks Python module imports
- Lints Markdown files with markdownlint

**Badge:**
```markdown
![Code Quality](https://github.com/tomazb/imageset-generator/actions/workflows/quality.yml/badge.svg)
```

### 5. Dependency Updates (`dependencies.yml`)

**Trigger:** Weekly schedule (Monday 8 AM UTC), Manual dispatch  
**Purpose:** Monitor and update dependencies

**Jobs:**

#### Update Dependencies
- Checks for outdated Python packages
- Generates dependency update report
- Uploads report as artifact

#### Dependabot Auto-merge
- Automatically merges patch-level Dependabot PRs
- Requires passing tests

**Badge:**
```markdown
![Dependencies](https://github.com/tomazb/imageset-generator/actions/workflows/dependencies.yml/badge.svg)
```

## Dependabot Configuration

Located at `.github/dependabot.yml`

**Monitored Package Ecosystems:**
1. **Python (pip)** - Backend dependencies
2. **GitHub Actions** - Workflow dependencies
3. **npm** - Frontend dependencies

**Schedule:** Weekly on Monday at 8:00 AM UTC

**Features:**
- Automatic PR creation for updates
- Grouped updates by ecosystem
- Reviewer assignments
- Automated labels
- Conventional commit messages

## Security Features

### Automated Security Scanning

1. **Weekly Scheduled Scans**
   - Security workflow runs every Monday
   - Catches newly disclosed vulnerabilities

2. **PR Security Checks**
   - Every PR is scanned before merge
   - Blocks PRs with security issues

3. **Container Security**
   - Image scanning with Trivy
   - Fails on HIGH/CRITICAL vulnerabilities
   - Results in GitHub Security tab

### Security Tools

| Tool | Purpose | Coverage |
|------|---------|----------|
| Bandit | Python security issues | Static analysis |
| Safety | Dependency vulnerabilities | Known CVEs |
| CodeQL | Semantic code analysis | Python, JavaScript |
| Trivy | Container vulnerabilities | OS, libraries |

## Container Registry

Images are published to GitHub Container Registry:

```bash
# Pull latest image
docker pull ghcr.io/tomazb/imageset-generator:main

# Pull specific version
docker pull ghcr.io/tomazb/imageset-generator:v1.0.0

# Pull by commit SHA
docker pull ghcr.io/tomazb/imageset-generator:sha-abc123
```

### Image Tags

- `main` - Latest commit on main branch
- `v*` - Version releases (e.g., v1.0.0, v1.1.0)
- `sha-<commit>` - Specific commit SHA
- `pr-<number>` - Pull request builds (not published)

## Local Development

### Run Tests Locally

```bash
# Run all tests
for test in test_*.py; do python3 "$test"; done

# Run specific test
python3 test_validation_simple.py
```

### Security Scan Locally

```bash
# Install tools
pip install bandit safety

# Run Bandit
bandit -r . -f txt

# Run Safety
safety check
```

### Build Container Locally

```bash
# Docker
docker build -t imageset-generator:local .

# Podman
podman build -f Containerfile -t imageset-generator:local .
```

### Code Quality Checks Locally

```bash
# Install tools
pip install black isort flake8 pylint mypy radon

# Format code
black *.py
isort *.py

# Check style
flake8 --max-line-length=120 *.py

# Type check
mypy --ignore-missing-imports *.py

# Complexity
radon cc *.py -a
```

## Status Badges

Add these badges to your README:

```markdown
![Python Tests](https://github.com/tomazb/imageset-generator/actions/workflows/test.yml/badge.svg)
![Security Scan](https://github.com/tomazb/imageset-generator/actions/workflows/security.yml/badge.svg)
![Container Build](https://github.com/tomazb/imageset-generator/actions/workflows/container.yml/badge.svg)
![Code Quality](https://github.com/tomazb/imageset-generator/actions/workflows/quality.yml/badge.svg)
```

## Troubleshooting

### Test Failures

1. Check which test failed in the GitHub Actions logs
2. Run the specific test locally to reproduce
3. Fix the issue and push again

### Security Scan Failures

1. Review the security report in GitHub Security tab
2. Update vulnerable dependencies
3. If false positive, add to ignore list

### Container Build Failures

1. Check build logs for errors
2. Test build locally with same commands
3. Verify Dockerfile/Containerfile syntax

### Code Quality Failures

These are advisory only and won't block PRs. However:
1. Review linting suggestions
2. Fix critical issues
3. Consider improving code quality scores

## Contributing

When contributing, ensure:

1. All tests pass locally before pushing
2. No security vulnerabilities introduced
3. Code quality checks pass (or improve scores)
4. Container builds successfully
5. Documentation updated if needed

## Maintenance

### Weekly Tasks (Automated)

- Dependency updates checked
- Security scans run
- Reports generated

### Manual Tasks

- Review Dependabot PRs
- Address security findings
- Update GitHub Actions versions
- Review code quality trends

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
