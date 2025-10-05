# tiger_guides Test Strategy

This document outlines the unit and integration tests required to validate the
portable TIGER workflow as well as the legacy HPC wrappers that import it.

## 1. Unit Tests (pytest)

| Area | Tests | Notes |
| ---- | ----- | ----- |
| Configuration | `tests/unit/test_config.py` | Validates species resolution, default merging, and invalid inputs. Add extra cases for overriding thread counts, top-N values, and catching missing config files. |
| Ensembl downloads | `tests/unit/test_download.py` | Uses responses/pytest to mock REST endpoints. Add parametrized tests for case-insensitive gene symbols, fallback to canonical transcripts, rate-limit handling, and HTTP error logging. |
| Reference utilities | `tests/unit/test_download.py` | Expand to cover checksum failures, gz → fasta decompression, smoke-data fallback, and cache reuse. |
| Model loader | `tests/unit/test_models.py` (new) | Verify `ensure_model` handles local archives, URL downloads (requests mock), checksum mismatches, and missing required files. |
| Off-target wrapper | `tests/unit/test_offtarget.py` | Mock the C binary using subprocess monkeypatch; confirm chunking logic, temporary file cleanup, and error propagation. |
| Filtering pipeline | `tests/unit/test_filters.py` | Ensure adaptive MM0 logic, mm0_tolerance edge cases, and top-N selection behave as expected. |
| Workflow runner helpers | `tests/unit/test_workflow_utils.py` (new) | Validate dry-run plan output, alias registration, and reference path resolution logic via fixtures. |

All unit tests run with `pytest tests/unit -q` under the package virtual env.

## 2. Integration Tests

| Scenario | Location | Coverage |
| -------- | -------- | -------- |
| CLI smoke | `tests/integration/test_cli_smoke.py` | Runs the bundled smoke dataset end-to-end, skipping if the binary is missing. |
| Workflow (mouse) | `tests/integration/test_workflow_mouse.py` | Executes `WorkflowRunner` with temporary output dir, using ensured references and model paths. |
| Workflow (human) | `tests/integration/test_workflow_human.py` (new) | Confirms proper failure when references absent, and success when fetched (fixture copies sample). |
| Ensembl live (optional) | `tests/integration/test_ensembl_live.py` (new) | Behind marker `@pytest.mark.network`, performs a real lookup for a well-known gene to ensure compatibility with current REST API. |
| HPC wrapper | `tests/integration/test_hpc_wrapper.py` (new) | Invokes `scripts/04_run_workflow.sh --dry-run` inside a temporary copy of the repo (requires make/binary). |
| Docker smoke | `tests/integration/test_docker_smoke.py` (new) | Builds the container using `docker build` (skip if docker unavailable), runs `tiger-guides smoke` inside container, ensures exit 0 and artifacts exist. |

Integration suite command:
```bash
pytest tests/integration -m "not network"  # default
pytest tests/integration -m network         # optional live tests
```

## 3. Test Data & Fixtures

- Use `pytest` fixtures in `conftest.py` to provide temp workspaces, fake requests
  responses, and environment variables (`TIGER_MODEL_ARCHIVE`, `PYTHONPATH`).
- Mocking tools: [`responses`](https://github.com/getsentry/responses) for HTTP,
  `pytest-subprocess` or manual monkeypatch for `subprocess.run`.
- Reuse smoke assets under `tiger_guides_pkg/src/tiger_guides/data/smoke/` for
  end-to-end comparisons.

## 4. Continuous Integration

Add two GitHub Actions workflows (`.github/workflows`):

1. **`package-tests.yml`** – runs unit + integration tests (without Docker) on
   Ubuntu 22.04 with Python 3.10/3.12. Installs the package in editable mode,
   ensures the off-target C binary is compiled, and runs pytest with coverage.

2. **`docker-smoke.yml`** – builds the multi-stage Docker image and executes the
   container smoke test. Triggered on pushes to main and PRs touching Docker or
   workflow code.

Both workflows cache pip and C build artifacts to reduce runtime.

## 5. Manual / Periodic Tests

- Quarterly: run live Ensembl integration test and full human pipeline against a
  curated target list to ensure no API/regression issues. Document results in
  `docs/WORKFLOW_STATUS.txt`.
- When updating model weights: re-run `tiger-guides fetch-model`, verify checksum
  updates, rerun smoke + integration tests, and update `MODEL_CATALOG` metadata.

## 6. Command Summary

```bash
# Unit tests
pytest tests/unit -q

# Integration tests (no network)
pytest tests/integration -m "not network" -q

# Docker smoke (requires Docker engine)
pytest tests/integration/test_docker_smoke.py -q

# GitHub Actions (locally via act or tox optional)
python -m build
```
