# CI/CD Setup Guide for AZTM

## GitHub Actions Configuration

### Required Secrets

To enable full CI/CD functionality including integration tests, configure the following GitHub repository secrets:

1. Go to your repository on GitHub
2. Navigate to Settings → Secrets and variables → Actions
3. Add the following secrets:

| Secret Name | Value | Description |
|-------------|--------|-------------|
| `AZTM_CLIENT_JID` | `aztmclient@sure.im` | XMPP client JID for testing |
| `AZTM_CLIENT_PASSWORD` | `[your-password]` | XMPP client password |
| `AZTM_SERVER_JID` | `aztmapi@sure.im` | XMPP server JID for testing |
| `AZTM_SERVER_PASSWORD` | `[your-password]` | XMPP server password |

### Workflow Overview

#### 1. CI - Continuous Integration (`ci.yml`)
- **Triggers**: Push to main/develop/Agentic branches, Pull requests
- **Jobs**:
  - Lint & Code Quality (black, isort, flake8)
  - Unit Tests (Python 3.10, 3.11, 3.12)
  - Integration Tests (if secrets configured)
  - Build & Package validation
  - Docker image build test
  - Coverage reporting to Codecov

#### 2. Release Workflow (`release.yml`)
- **Triggers**: Git tags matching `v*`
- **Jobs**:
  - Build and test release
  - Publish Docker images to GitHub Container Registry
  - Create GitHub release with artifacts
  - Publish to PyPI (optional)

#### 3. Nightly Regression Tests (`nightly.yml`)
- **Triggers**: Daily at 2 AM UTC, Manual dispatch
- **Jobs**:
  - Full regression test suite
  - Memory leak detection
  - Security vulnerability scanning
  - Stress testing
  - Performance benchmarks

### Manual Workflow Triggers

You can manually trigger workflows using GitHub CLI:

```bash
# Trigger CI workflow
gh workflow run ci.yml --ref Agentic --repo eladrave/aztm

# Trigger nightly tests with specific scope
gh workflow run nightly.yml --ref Agentic --repo eladrave/aztm \
  -f test-scope=integration

# Create a release
git tag v0.1.1
git push origin v0.1.1
```

### Monitoring CI Status

```bash
# List recent workflow runs
gh run list --repo eladrave/aztm --limit 10

# Watch a specific run
gh run watch <run-id> --repo eladrave/aztm

# View failed logs
gh run view <run-id> --repo eladrave/aztm --log-failed
```

### Local CI Testing

Before pushing, you can test locally:

```bash
# Run unit tests
pytest tests/unit/ -v --cov=aztm

# Run integration tests (requires XMPP credentials)
export AZTM_CLIENT_JID=aztmclient@sure.im
export AZTM_CLIENT_PASSWORD=yourpassword
export AZTM_SERVER_JID=aztmapi@sure.im  
export AZTM_SERVER_PASSWORD=yourpassword
pytest tests/regression/ -v --timeout=300

# Check code formatting
black aztm tests --check
isort aztm tests --check-only
flake8 aztm tests

# Build package
python -m build
twine check dist/*
```

### Troubleshooting

#### Common Issues

1. **Python 3.9 Compatibility Error**
   - AZTM requires Python 3.10+ due to slixmpp dependency
   - Solution: Use Python 3.10, 3.11, or 3.12

2. **Integration Tests Skipped**
   - Cause: Missing XMPP credentials in GitHub secrets
   - Solution: Configure the secrets as described above

3. **Docker Build Failures**
   - Ensure Dockerfile is present and valid
   - Check that all dependencies are correctly specified

4. **Coverage Upload Failures**
   - Non-critical: Coverage reports may fail without Codecov token
   - Solution: Add `CODECOV_TOKEN` to secrets (optional)

### Badge Integration

Add these badges to your README:

```markdown
[![CI](https://github.com/eladrave/aztm/actions/workflows/ci.yml/badge.svg)](https://github.com/eladrave/aztm/actions/workflows/ci.yml)
[![Release](https://github.com/eladrave/aztm/actions/workflows/release.yml/badge.svg)](https://github.com/eladrave/aztm/actions/workflows/release.yml)
[![Nightly](https://github.com/eladrave/aztm/actions/workflows/nightly.yml/badge.svg)](https://github.com/eladrave/aztm/actions/workflows/nightly.yml)
```

## Success Criteria

✅ **CI/CD is fully functional when:**
- Every push triggers automated testing
- All unit tests pass across Python 3.10, 3.11, 3.12
- Integration tests run when credentials are configured
- Docker images build successfully
- Package builds and validates correctly
- Release workflow creates GitHub releases and Docker images
- Nightly tests run on schedule