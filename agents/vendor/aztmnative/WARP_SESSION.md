# WARP Session Summary - 2025-11-25

## Session Overview
Discussed options for hosting the `aztm` package privately without using public PyPI. Reviewed options including GitHub Packages, AWS CodeArtifact, and direct git installation.

## Decisions
- Opted to avoid setting up a package registry for now.
- Selected the direct git installation method using `pip install "git+https://<user>:<token>@github.com/eladrave/aztm.git"`.
- This requires the `pyproject.toml` to be correctly configured for `pip` to build the package from source.

## Actions
- Verified `pyproject.toml` configuration.
- Committing pending changes to `pyproject.toml` to ensure the repo is in a deployable state for git-based installation.
